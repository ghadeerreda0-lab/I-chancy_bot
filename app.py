import os
import asyncio
import logging
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import ujson as json
import random

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telebot import types

import psycopg2
from psycopg2 import pool
import redis.asyncio as aioredis
from cachetools import TTLCache
from flask import Flask, jsonify
from threading import Thread
import aiohttp

# =========================
# Flask مع إعدادات قوية
# =========================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "IChancy Bot",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/metrics')
def metrics():
    return jsonify({
        "uptime": (datetime.now() - app_start_time).total_seconds(),
        "active_users": len(user_cache) if 'user_cache' in globals() else 0,
        "timestamp": datetime.now().isoformat()
    })

def run_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# =========================
# إعدادات متقدمة
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
app_start_time = datetime.now()

# =========================
# Configuration
# =========================
class Config:
    TOKEN = os.getenv("8312113931:AAFKlUxshhvrZ9IiMn9Wj4FelfcISj31S9w", "")
    ADMIN_ID = int(os.getenv("814607765", "0"))
    
    # Payment numbers
    SYR_CASH_NUMBER = os.getenv("SYR_CASH_NUMBER", "0990000000")
    SCH_CASH_NUMBER = os.getenv("SCH_CASH_NUMBER", "0940000000")
    
    # Channels
    CHANNEL_SYR_CASH = int(os.getenv("CHANNEL_SYR_CASH", "-1003597919374)
    CHANNEL_SCH_CASH = int(os.getenv("CHANNEL_SCH_CASH", "-1003464319533"))
    CHANNEL_ADMIN_LOGS = int(os.getenv("CHANNEL_ADMIN_LOGS", "-1003577468648))
    CHANNEL_WITHDRAW = int(os.getenv("CHANNEL_WITHDRAW", "-1003443113179"))
    CHANNEL_SUPPORT = int(os.getenv("CHANNEL_SUPPORT", "-1003514396473"))
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Security limits
    MAX_WITHDRAW_PER_DAY = 5000000
    MIN_TRANSACTION = 1000
    MAX_TRANSACTION = 10000000
    MAX_REQUESTS_PER_MINUTE = 60
    
    # Performance
    DB_POOL_MIN = 2
    DB_POOL_MAX = 20
    CACHE_SIZE = 10000
    CACHE_TTL = 300

config = Config()

# تحقق من التوكن
if not config.TOKEN or config.TOKEN == "ضع_توكن_البوت_هنا":
    logger.error("❌ BOT_TOKEN غير موجود!")
    exit(1)

bot = AsyncTeleBot(config.TOKEN, parse_mode="HTML")

# =========================
# Database Manager (باستخدام psycopg2)
# =========================
class ConnectionManager:
    _db_pool = None
    _redis = None
    
    @classmethod
    async def init_db(cls):
        """تهيئة PostgreSQL مع Connection Pool"""
        if not cls._db_pool and config.DATABASE_URL:
            try:
                cls._db_pool = pool.SimpleConnectionPool(
                    config.DB_POOL_MIN,
                    config.DB_POOL_MAX,
                    config.DATABASE_URL
                )
                await cls._create_tables()
                logger.info(f"✅ PostgreSQL جاهز (Pool: {config.DB_POOL_MIN}-{config.DB_POOL_MAX})")
            except Exception as e:
                logger.error(f"❌ خطأ في PostgreSQL: {e}")
                cls._db_pool = None
        else:
            logger.warning("⚠️ DATABASE_URL غير محدد")
    
    @classmethod
    async def init_redis(cls):
        """تهيئة Redis مع Connection Pool"""
        if not cls._redis:
            try:
                cls._redis = aioredis.from_url(
                    config.REDIS_URL,
                    decode_responses=True,
                    max_connections=50,
                    socket_keepalive=True,
                    retry_on_timeout=True
                )
                # Test connection
                await cls._redis.ping()
                logger.info("✅ Redis جاهز مع Connection Pool")
            except Exception as e:
                logger.error(f"❌ خطأ في Redis: {e}")
                cls._redis = None
    
    @classmethod
    def _create_tables(cls):
        """إنشاء الجداول (تعديل للـ psycopg2)"""
        if not cls._db_pool:
            return
        
        conn = cls._db_pool.getconn()
        try:
            cur = conn.cursor()
            
            # جدول المستخدمين
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(100),
                    first_name VARCHAR(100),
                    balance BIGINT DEFAULT 0 CHECK (balance >= 0),
                    total_deposited BIGINT DEFAULT 0,
                    total_withdrawn BIGINT DEFAULT 0,
                    daily_withdrawn BIGINT DEFAULT 0,
                    last_withdrawal_date DATE,
                    referral_code VARCHAR(20) UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    last_transaction TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # جدول المعاملات
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    type VARCHAR(20) NOT NULL CHECK (type IN ('deposit', 'withdraw')),
                    amount BIGINT NOT NULL CHECK (amount > 0),
                    payment_method VARCHAR(50) NOT NULL,
                    transaction_id VARCHAR(100),
                    account_number VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'completed')),
                    monthly_order INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # إنشاء الفهارس
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_user_created 
                ON transactions(user_id, created_at DESC)
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_referral 
                ON users(referral_code)
            """)
            
            conn.commit()
            logger.info("✅ تم إنشاء الجداول والفهارس")
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الجداول: {e}")
            conn.rollback()
        finally:
            cls._db_pool.putconn(conn)

# =========================
# Cache Manager متقدم
# =========================
class AdvancedCache:
    def __init__(self):
        self.user_cache = TTLCache(maxsize=config.CACHE_SIZE, ttl=config.CACHE_TTL)
        self.session_cache = TTLCache(maxsize=5000, ttl=1800)
        self.rate_limit_cache = TTLCache(maxsize=10000, ttl=60)
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """الحصول على بيانات المستخدم من التخزين المؤقت"""
        # 1. من الذاكرة المحلية
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        
        # 2. من Redis
        if ConnectionManager._redis:
            try:
                cached = await ConnectionManager._redis.get(f"user:{user_id}")
                if cached:
                    user_data = json.loads(cached)
                    self.user_cache[user_id] = user_data
                    return user_data
            except:
                pass
        
        # 3. من قاعدة البيانات
        if ConnectionManager._db_pool:
            conn = ConnectionManager._db_pool.getconn()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT user_id, username, balance, is_verified 
                    FROM users WHERE user_id = %s
                """, (user_id,))
                row = cur.fetchone()
                
                if row:
                    user_data = {
                        "user_id": row[0],
                        "username": row[1],
                        "balance": row[2] or 0,
                        "is_verified": row[3]
                    }
                    await self.set_user(user_id, user_data)
                    return user_data
            except Exception as e:
                logger.error(f"خطأ في جلب المستخدم: {e}")
            finally:
                ConnectionManager._db_pool.putconn(conn)
        
        return None
    
    async def set_user(self, user_id: int, user_data: Dict):
        """تحديث تخزين المستخدم"""
        self.user_cache[user_id] = user_data
        if ConnectionManager._redis:
            await ConnectionManager._redis.setex(
                f"user:{user_id}", config.CACHE_TTL, json.dumps(user_data)
            )
    
    async def check_rate_limit(self, user_id: int, action: str) -> bool:
        """التحقق من معدل الطلبات"""
        key = f"ratelimit:{user_id}:{action}"
        
        if key in self.rate_limit_cache:
            count = self.rate_limit_cache[key]
            if count >= config.MAX_REQUESTS_PER_MINUTE:
                return False
            self.rate_limit_cache[key] = count + 1
        else:
            self.rate_limit_cache[key] = 1
        
        return True

# =========================
# User Manager متقدم
# =========================
class AdvancedUserManager:
    def __init__(self):
        self.cache = AdvancedCache()
    
    async def get_or_create_user(self, telegram_user: types.User) -> Dict:
        """الحصول على مستخدم أو إنشاءه"""
        user_id = telegram_user.id
        
        # التحقق من التخزين المؤقت أولاً
        cached = await self.cache.get_user(user_id)
        if cached:
            return cached
        
        if ConnectionManager._db_pool:
            conn = ConnectionManager._db_pool.getconn()
            try:
                cur = conn.cursor()
                
                # إنشاء كود إحالة
                referral_code = f"ICH{user_id}{random.randint(1000, 9999)}"
                
                # محاولة الإدراج أو التحديث
                cur.execute("""
                    INSERT INTO users (user_id, username, first_name, referral_code, balance)
                    VALUES (%s, %s, %s, %s, 50000)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    updated_at = CURRENT_TIMESTAMP
                    RETURNING user_id, username, balance, referral_code
                """, (
                    user_id,
                    telegram_user.username,
                    telegram_user.first_name,
                    referral_code
                ))
                
                row = cur.fetchone()
                conn.commit()
                
                if row:
                    user_data = {
                        "user_id": row[0],
                        "username": row[1],
                        "balance": row[2],
                        "referral_code": row[3]
                    }
                    await self.cache.set_user(user_id, user_data)
                    return user_data
                    
            except Exception as e:
                logger.error(f"خطأ في إنشاء المستخدم: {e}")
                conn.rollback()
            finally:
                ConnectionManager._db_pool.putconn(conn)
        
        # Fallback إذا فشل الاتصال
        return {
            "user_id": user_id,
            "username": telegram_user.username,
            "balance": 50000,  # رصيد تجريبي
            "referral_code": f"ICH{user_id}{random.randint(1000, 9999)}"
        }
    
    async def update_balance(self, user_id: int, amount: int, transaction_type: str) -> Dict:
        """تحديث رصيد المستخدم"""
        if ConnectionManager._db_pool:
            conn = ConnectionManager._db_pool.getconn()
            try:
                cur = conn.cursor()
                
                if transaction_type == "deposit":
                    cur.execute("""
                        UPDATE users 
                        SET balance = balance + %s,
                            total_deposited = total_deposited + %s,
                            last_transaction = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                        RETURNING balance
                    """, (amount, amount, user_id))
                else:  # withdraw
                    cur.execute("""
                        UPDATE users 
                        SET balance = balance - %s,
                            total_withdrawn = total_withdrawn + %s,
                            last_transaction = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND balance >= %s
                        RETURNING balance
                    """, (amount, amount, user_id, amount))
                
                row = cur.fetchone()
                if row:
                    conn.commit()
                    
                    # تحديث التخزين المؤقت
                    await self.cache.set_user(user_id, {
                        "user_id": user_id,
                        "balance": row[0]
                    })
                    
                    return {"success": True, "new_balance": row[0]}
                else:
                    return {"success": False, "error": "رصيد غير كافي"}
                    
            except Exception as e:
                logger.error(f"خطأ في تحديث الرصيد: {e}")
                return {"success": False, "error": str(e)}
            finally:
                ConnectionManager._db_pool.putconn(conn)
        
        return {"success": False, "error": "غير متصل بقاعدة البيانات"}

# =========================
# تهيئة المديرين
# =========================
connection_manager = ConnectionManager()
cache_manager = AdvancedCache()
user_manager = AdvancedUserManager()

async def init_services():
    """تهيئة جميع الخدمات"""
    await connection_manager.init_db()
    await connection_manager.init_redis()
    logger.info("✅ جميع الخدمات جاهزة")

# =========================
# القائمة الرئيسية (نفس الواجهة)
# =========================
def main_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("⚡ Ichancy", callback_data="ichancy"))
    kb.add(
        InlineKeyboardButton("📥 شحن رصيد", callback_data="charge"),
        InlineKeyboardButton("📤 سحب رصيد", callback_data="withdraw")
    )
    kb.add(InlineKeyboardButton("💰 نظام الاحالات", callback_data="referrals"))
    kb.add(
        InlineKeyboardButton("🎁 اهداء رصيد", callback_data="gift"),
        InlineKeyboardButton("🎁 كود هدية", callback_data="gift_code")
    )
    kb.add(
        InlineKeyboardButton("✉️ تواصل مع الدعم", callback_data="support"),
        InlineKeyboardButton("✉️ تواصل معنا", callback_data="contact")
    )
    kb.add(
        InlineKeyboardButton("🔁 السجل", callback_data="logs"),
        InlineKeyboardButton("☁️ الشروحات", callback_data="tutorials")
    )
    kb.add(InlineKeyboardButton("🔁 سجل الرهانات", callback_data="bets"))
    kb.add(InlineKeyboardButton("🆕 🃏 الجاكبوت", callback_data="jackpot"))
    kb.add(
        InlineKeyboardButton("↗️ Vp لتشغيل كامل اقسام الموقع", callback_data="vp"),
        InlineKeyboardButton("↗️ ichancy apk", callback_data="apk")
    )
    kb.add(InlineKeyboardButton("📌 الشروط والأحكام", callback_data="rules"))
    
    if user_id == config.ADMIN_ID:
        kb.add(InlineKeyboardButton("🎛 لوحة التحكم", callback_data="admin_panel"))
    
    return kb

# =========================
# معالجات البوت - محسنة للأداء
# =========================
@bot.message_handler(commands=["start"])
async def start_command(message: types.Message):
    """معالجة أمر /start"""
    try:
        # Rate limiting
        if not await cache_manager.check_rate_limit(message.from_user.id, "start"):
            await bot.send_message(message.chat.id, "⏳ لقد تجاوزت الحد المسموح. حاول بعد قليل.")
            return
        
        user = await user_manager.get_or_create_user(message.from_user)
        balance = user.get("balance", 0)
        
        welcome_text = f"""
👋 أهلاً بك <b>{message.from_user.first_name}</b> في <b>IChancy</b>!

⚡ <b>منصة التعاملات المالية الآمنة</b>

💰 <b>رصيدك الحالي:</b> <code>{balance:,} ليرة سورية</code>
🎫 <b>كود الإحالة:</b> <code>{user.get('referral_code', '')}</code>

📊 <b>إحصائيات سريعة:</b>
• الحد الأدنى: {config.MIN_TRANSACTION:,} ليرة
• الحد اليومي للسحب: {config.MAX_WITHDRAW_PER_DAY:,} ليرة
• الحد الأقصى: {config.MAX_TRANSACTION:,} ليرة

🔒 <b>ميزات الأمان:</b>
✓ تأمين عالي المستوى
✓ سجل كامل للمعاملات
✓ تحقق من كل عملية
        """
        
        await bot.send_message(
            message.chat.id,
            welcome_text,
            reply_markup=main_menu(message.from_user.id),
            parse_mode="HTML"
        )
        
        logger.info(f"✅ بدء جلسة: {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"خطأ في start: {e}")
        await bot.send_message(
            message.chat.id,
            "⚠️ مرحباً! البوت يعمل بشكل طبيعي.\n\nللمساعدة:\n1. تأكد من ضغط /start\n2. إذا استمرت المشكلة تواصل مع الدعم"
        )

@bot.callback_query_handler(func=lambda call: True)
async def callback_handler(call: CallbackQuery):
    """معالجة Callback Queries"""
    try:
        user_id = call.from_user.id
        
        # Rate limiting
        if not await cache_manager.check_rate_limit(user_id, "callback"):
            await bot.answer_callback_query(call.id, "⏳ لقد تجاوزت الحد المسموح", show_alert=True)
            return
        
        data = call.data
        
        if data == "support":
            await bot.send_message(
                call.message.chat.id,
                "✍️ <b>اكتب رسالتك للدعم:</b>\n"
                "يرجى وصف مشكلتك بالتفصيل وسيقوم فريق الدعم بالرد عليك خلال 24 ساعة.",
                parse_mode="HTML"
            )
            await bot.answer_callback_query(call.id)
        
        elif data == "charge":
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton("💰 سيرياتيل كاش", callback_data="pay_syr"),
                InlineKeyboardButton("💰 شام كاش", callback_data="pay_sch")
            )
            kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back"))
            
            await bot.send_message(
                call.message.chat.id,
                "📥 <b>اختر طريقة الدفع:</b>\n\n"
                "💡 <b>تعليمات:</b>\n"
                "1. اختر طريقة الدفع\n"
                "2. حول المبلغ إلى الرقم المحدد\n"
                "3. أرسل رقم العملية\n"
                "4. انتظر الموافقة (عادة خلال 15 دقيقة)",
                reply_markup=kb,
                parse_mode="HTML"
            )
            await bot.answer_callback_query(call.id)
        
        elif data == "withdraw":
            user = await user_manager.get_or_create_user(call.from_user)
            if user.get("balance", 0) < config.MIN_TRANSACTION:
                await bot.answer_callback_query(
                    call.id,
                    f"❌ الرصيد غير كافي للبدء. الحد الأدنى للسحب: {config.MIN_TRANSACTION} ليرة",
                    show_alert=True
                )
                return
            
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton("💰 سيرياتيل كاش", callback_data="withdraw_syr"),
                InlineKeyboardButton("💰 شام كاش", callback_data="withdraw_sch")
            )
            kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back"))
            
            await bot.send_message(
                call.message.chat.id,
                "📤 <b>اختر طريقة السحب:</b>\n\n"
                "💡 <b>تعليمات:</b>\n"
                "1. اختر طريقة السحب\n"
                "2. أدخل المبلغ\n"
                "3. أدخل رقم حسابك\n"
                "4. انتظر الموافقة (عادة خلال 30 دقيقة)",
                reply_markup=kb,
                parse_mode="HTML"
            )
            await bot.answer_callback_query(call.id)
        
        elif data in ["pay_syr", "pay_sch"]:
            payment = "سيرياتيل كاش" if data == "pay_syr" else "شام كاش"
            number = config.SYR_CASH_NUMBER if data == "pay_syr" else config.SCH_CASH_NUMBER
            
            await bot.send_message(
                call.message.chat.id,
                f"💳 <b>{payment}</b>\n\n"
                f"📱 <b>الرقم:</b> <code>{number}</code>\n"
                f"💰 <b>الحد الأدنى:</b> {config.MIN_TRANSACTION:,} ليرة\n"
                f"💰 <b>الحد الأقصى:</b> {config.MAX_TRANSACTION:,} ليرة\n\n"
                f"📝 <b>بعد التحويل، أدخل المبلغ الذي حولته:</b>",
                parse_mode="HTML"
            )
            await bot.answer_callback_query(call.id)
        
        elif data == "back":
            await bot.send_message(
                call.message.chat.id,
                "✅ <b>عدنا إلى القائمة الرئيسية:</b>",
                reply_markup=main_menu(user_id),
                parse_mode="HTML"
            )
            await bot.answer_callback_query(call.id)
        
        elif data in ["withdraw_syr", "withdraw_sch"]:
            payment = "سيرياتيل كاش" if data == "withdraw_syr" else "شام كاش"
            
            await bot.send_message(
                call.message.chat.id,
                f"💳 <b>طريقة السحب:</b> {payment}\n\n"
                f"💵 <b>أدخل المبلغ المراد سحبه:</b>\n"
                f"(الحد الأدنى: {config.MIN_TRANSACTION:,} ليرة)",
                parse_mode="HTML"
            )
            await bot.answer_callback_query(call.id)
        
        # معالجة الأزرار الأخرى
        else:
            feature_messages = {
                "referrals": "💰 نظام الإحالات",
                "gift": "🎁 إهداء الرصيد",
                "gift_code": "🎁 كود الهدية",
                "tutorials": "☁️ الشروحات",
                "bets": "🔁 سجل الرهانات",
                "jackpot": "🃏 الجاكبوت",
                "vp": "↗️ VPN",
                "apk": "↗️ تطبيق IChancy",
                "rules": "📌 الشروط والأحكام",
                "contact": "✉️ تواصل معنا",
                "logs": "🔁 السجل",
                "ichancy": "⚡ Ichancy",
                "admin_panel": "🎛 لوحة التحكم"
            }
            
            message_text = feature_messages.get(data, "هذه الميزة")
            await bot.answer_callback_query(
                call.id,
                f"🛠️ {message_text} قيد التطوير. ستكون متاحة قريباً!",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"خطأ في callback: {e}")
        await bot.answer_callback_query(call.id, "⚠️ حدث خطأ في النظام", show_alert=True)

# =========================
# معالجة الرسائل النصية
# =========================
@bot.message_handler(func=lambda m: True, content_types=['text'])
async def text_message_handler(message: types.Message):
    """معالجة الرسائل النصية"""
    try:
        user_id = message.from_user.id
        
        # Rate limiting
        if not await cache_manager.check_rate_limit(user_id, "message"):
            return
        
        # يمكن إضافة معالجة الرسائل هنا
        if message.text.startswith('/'):
            return
        
        await bot.send_message(
            message.chat.id,
            "📝 يمكنك استخدام الأزرار في القائمة للتنقل بين الميزات.",
            reply_markup=main_menu(user_id)
        )
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")

# =========================
# مهام خلفية
# =========================
async def background_tasks():
    """مهام خلفية دورية"""
    while True:
        try:
            await asyncio.sleep(300)  # كل 5 دقائق
            
            # تنظيف الذاكرة المؤقتة
            current_time = datetime.now()
            logger.info(f"📊 النظام يعمل - Uptime: {(current_time - app_start_time).total_seconds():.0f} ثانية")
            
            # إعادة الاتصال إذا انقطع
            if ConnectionManager._redis:
                try:
                    await ConnectionManager._redis.ping()
                except:
                    logger.warning("🔄 إعادة الاتصال بـ Redis...")
                    await connection_manager.init_redis()
                    
        except Exception as e:
            logger.error(f"خطأ في المهام الخلفية: {e}")
            await asyncio.sleep(60)

# =========================
# التشغيل الرئيسي
# =========================
async def main():
    """الدالة الرئيسية للتشغيل"""
    # إبقاء البوت نشطاً
    keep_alive()
    
    print("=" * 60)
    print("🚀 بدء تشغيل IChancy Bot - النسخة الاحترافية")
    print("=" * 60)
    
    try:
        # تهيئة الخدمات
        await init_services()
        
        # معلومات البوت
        bot_info = await bot.get_me()
        print(f"🤖 البوت: @{bot_info.username}")
        print(f"🆔 ID: {bot_info.id}")
        print(f"📛 الاسم: {bot_info.first_name}")
        
        print("\n✅ جميع الخدمات جاهزة")
        print(f"💾 Cache Size: {config.CACHE_SIZE}")
        print(f"🔗 DB Pool: {config.DB_POOL_MIN}-{config.DB_POOL_MAX}")
        print("📱 اكتب /start في تيليجرام للبدء")
        print("=" * 60)
        
        # بدء المهام الخلفية
        asyncio.create_task(background_tasks())
        
        # بدء البوت مع إعدادات متقدمة
        await bot.polling(
            none_stop=True,
            timeout=90,
            request_timeout=90,
            skip_pending=True,
            allowed_updates=["message", "callback_query"]
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ رئيسي: {e}", exc_info=True)
        print(f"❌ خطأ: {e}")
        
        # محاولة إعادة التشغيل بعد 10 ثواني
        await asyncio.sleep(10)
        print("🔄 إعادة تشغيل البوت...")
        os.execv(sys.executable, ['python'] + sys.argv)
        
    finally:
        # تنظيف الموارد
        print("\n🔴 إغلاق النظام...")
        if ConnectionManager._db_pool:
            ConnectionManager._db_pool.closeall()
        if ConnectionManager._redis:
            await ConnectionManager._redis.close()
        print("✅ تم إغلاق جميع الاتصالات")

# =========================
# نقطة الدخول
# =========================
if __name__ == "__main__":
    import sys
    
    # تشغيل البوت
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 إيقاف البوت...")
        sys.exit(0)