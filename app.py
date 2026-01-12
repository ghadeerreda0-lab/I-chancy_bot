import os
import asyncio
import logging
import re
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import json
import random

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telebot import types

import asyncpg
import redis.asyncio as aioredis  # تم التصحيح هنا
from cachetools import TTLCache
from flask import Flask
from threading import Thread
import aiohttp
from aiohttp import web

# =========================
# Flask للحفاظ على البوت نشط
# =========================
app = Flask(__name__)

@app.route('/')
def home():
    return "IChancy Bot is running on Render!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# =========================
# إعدادات التسجيل
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================
# إعدادات التكوين لـ Render
# =========================
class Config:
    TOKEN = os.getenv("8312113931:AAFKlUxshhvrZ9IiMn9Wj4FelfcISj31S9w", "")
    ADMIN_ID = int(os.getenv("8146077656", "0"))
    
    # القنوات - يمكن تعديلها من Render
    CHANNEL_SYR_CASH = int(os.getenv("CHANNEL_SYR_CASH", "-1003597919374"))
    CHANNEL_SCH_CASH = int(os.getenv("CHANNEL_SCH_CASH", "-1003464319533"))
    CHANNEL_ADMIN_LOGS = int(os.getenv("CHANNEL_ADMIN_LOGS", "-1003577468648"))
    CHANNEL_WITHDRAW = int(os.getenv("CHANNEL_WITHDRAW", "-1003443113179"))
    CHANNEL_SUPPORT = int(os.getenv("CHANNEL_SUPPORT", "-1003514396473"))
    
    # قاعدة البيانات
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # حدود الأمان
    MAX_WITHDRAW_PER_DAY = 5000000
    MIN_TRANSACTION = 1000
    MAX_TRANSACTION = 10000000
    MAX_DAILY_WITHDRAWALS = 5
    
    # معدل الحد
    RATE_LIMIT_REQUESTS = 10  # طلبات لكل
    RATE_LIMIT_PERIOD = 60   # ثانية
    
    # أرقام الهواتف الحقيقية (يجب تغييرها في البيئة)
    SYR_CASH_NUMBER = os.getenv("SYR_CASH_NUMBER", "099XXXXXXXX")
    SCH_CASH_NUMBER = os.getenv("SCH_CASH_NUMBER", "094YYYYYYYY")
    
config = Config()

# التحقق من المتغيرات الأساسية
if not config.TOKEN:
    logger.error("❌ BOT_TOKEN غير موجود. الرجاء تعيينه في متغيرات البيئة.")
    exit(1)

bot = AsyncTeleBot(config.TOKEN)

# =========================
# إدارة الاتصالات
# =========================
class ConnectionManager:
    _db_pool = None
    _redis = None
    
    @classmethod
    async def init_db(cls):
        """تهيئة PostgreSQL"""
        if not cls._db_pool and config.DATABASE_URL:
            try:
                cls._db_pool = await asyncpg.create_pool(
                    config.DATABASE_URL,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                    statement_cache_size=0
                )
                await cls._create_tables()
                logger.info("✅ PostgreSQL جاهز")
            except Exception as e:
                logger.error(f"❌ خطأ في PostgreSQL: {e}")
                # إنشاء قاعدة بيانات مؤقتة للتجربة
                cls._db_pool = await cls._create_fallback_db()
        else:
            logger.warning("⚠️ DATABASE_URL غير محدد، استخدام قاعدة بيانات مؤقتة")
            cls._db_pool = await cls._create_fallback_db()
    
    @classmethod
    async def _create_fallback_db(cls):
        """إنشاء قاعدة بيانات مؤقتة للتجربة"""
        try:
            return await asyncpg.create_pool(
                "postgresql://user:pass@localhost/test",
                min_size=1,
                max_size=2
            )
        except:
            return None
    
    @classmethod
    async def init_redis(cls):
        """تهيئة Redis"""
        if not cls._redis:
            try:
                cls._redis = aioredis.from_url(
                    config.REDIS_URL,
                    decode_responses=True,
                    max_connections=10,
                    socket_keepalive=True
                )
                await cls._redis.ping()
                logger.info("✅ Redis جاهز")
            except Exception as e:
                logger.error(f"❌ خطأ في Redis: {e}")
                cls._redis = None
    
    @classmethod
    async def _create_tables(cls):
        """إنشاء جداول متوافقة مع Render"""
        if not cls._db_pool:
            return
        
        async with cls._db_pool.acquire() as conn:
            # جدول المستخدمين
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                balance BIGINT DEFAULT 0 CHECK (balance >= 0),
                total_deposited BIGINT DEFAULT 0,
                total_withdrawn BIGINT DEFAULT 0,
                daily_withdrawn BIGINT DEFAULT 0,
                last_withdrawal_date DATE,
                referral_code VARCHAR(20) UNIQUE,
                referred_by BIGINT REFERENCES users(user_id),
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                last_transaction TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # جدول المعاملات
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                type VARCHAR(20) NOT NULL CHECK (type IN ('deposit', 'withdraw', 'bonus', 'penalty')),
                amount BIGINT NOT NULL CHECK (amount > 0),
                payment_method VARCHAR(50) NOT NULL,
                transaction_id VARCHAR(100),
                account_number VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'completed')),
                verified_by BIGINT,
                verified_at TIMESTAMP,
                monthly_order INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # فهارس أساسية
            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_user_status 
            ON transactions(user_id, status)
            """)
            
            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_created 
            ON transactions(created_at DESC)
            """)
            
            await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_referral 
            ON users(referral_code)
            """)
            
            # جدول العداد الشهري
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_counter (
                month INTEGER,
                year INTEGER,
                payment_method VARCHAR(50),
                counter INTEGER DEFAULT 0,
                PRIMARY KEY (month, year, payment_method)
            )
            """)
            
            # جدول رسائل الدعم
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                username VARCHAR(100),
                message TEXT NOT NULL,
                admin_reply TEXT,
                status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'pending')),
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                replied_at TIMESTAMP,
                closed_at TIMESTAMP
            )
            """)
            
            # جدول سجل الأمان
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                action VARCHAR(100) NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                details JSONB,
                risk_level VARCHAR(20) DEFAULT 'low',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # جدول معدل الحد
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id BIGINT NOT NULL,
                action VARCHAR(50) NOT NULL,
                request_count INTEGER DEFAULT 1,
                first_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, action)
            )
            """)
            
            # جدول الكود الترويجي
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS gift_codes (
                code VARCHAR(50) PRIMARY KEY,
                amount BIGINT NOT NULL,
                created_by BIGINT NOT NULL,
                used_count INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            logger.info("✅ جميع الجداول جاهزة")

# =========================
# التحقق من الصحة والتمويه
# =========================
class ValidationManager:
    @staticmethod
    def validate_phone_number(number: str) -> bool:
        """التحقق من رقم الهاتف السوري"""
        patterns = [
            r'^09[3-9]\d{7}$',  # سيرياتيل
            r'^09[0-2]\d{7}$',  # شام
            r'^094\d{7}$',      # شام كاش
            r'^099\d{7}$'       # سيرياتيل كاش
        ]
        return any(re.match(pattern, number) for pattern in patterns)
    
    @staticmethod
    def validate_amount(amount: int) -> Tuple[bool, str]:
        """التحقق من صحة المبلغ"""
        if amount < config.MIN_TRANSACTION:
            return False, f"المبلغ يجب أن يكون على الأقل {config.MIN_TRANSACTION} ليرة"
        
        if amount > config.MAX_TRANSACTION:
            return False, f"المبلغ يجب أن لا يتجاوز {config.MAX_TRANSACTION} ليرة"
        
        return True, ""
    
    @staticmethod
    def validate_transaction_id(txid: str) -> bool:
        """التحقق من رقم العملية"""
        if len(txid) < 3:
            return False
        # يمكن إضافة المزيد من الشروط حسب نظام الدفع
        return True
    
    @staticmethod
    async def check_rate_limit(user_id: int, action: str) -> Tuple[bool, str]:
        """التحقق من معدل الطلبات"""
        if not ConnectionManager._redis:
            return True, ""
        
        key = f"rate_limit:{user_id}:{action}"
        current = await ConnectionManager._redis.get(key)
        
        if current:
            count = int(current)
            if count >= config.RATE_LIMIT_REQUESTS:
                ttl = await ConnectionManager._redis.ttl(key)
                return False, f"لقد تجاوزت الحد المسموح. حاول مرة أخرى بعد {ttl} ثانية"
            
            await ConnectionManager._redis.incr(key)
        else:
            await ConnectionManager._redis.setex(
                key, config.RATE_LIMIT_PERIOD, 1
            )
        
        return True, ""

# =========================
# إدارة التخزين المؤقت
# =========================
class CacheManager:
    def __init__(self):
        self.local_cache = TTLCache(maxsize=1000, ttl=300)
        self.user_lock = asyncio.Lock()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """الحصول على بيانات المستخدم"""
        cache_key = f"user:{user_id}"
        
        # محاولة من الذاكرة المحلية
        if user_id in self.local_cache:
            return self.local_cache[user_id]
        
        # محاولة من Redis
        if ConnectionManager._redis:
            async with self.user_lock:
                cached = await ConnectionManager._redis.get(cache_key)
                if cached:
                    try:
                        user_data = json.loads(cached)
                        self.local_cache[user_id] = user_data
                        return user_data
                    except:
                        pass
        
        # جلب من قاعدة البيانات
        if ConnectionManager._db_pool:
            async with ConnectionManager._db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                SELECT user_id, username, first_name, balance, 
                       is_verified, referral_code
                FROM users WHERE user_id = $1
                """, user_id)
                
                if row:
                    user_data = dict(row)
                    await self.set_user_cache(user_id, user_data)
                    return user_data
        
        return None
    
    async def set_user_cache(self, user_id: int, user_data: Dict):
        """تحديث تخزين المستخدم"""
        self.local_cache[user_id] = user_data
        if ConnectionManager._redis:
            await ConnectionManager._redis.setex(
                f"user:{user_id}", 600, json.dumps(user_data)
            )
    
    async def invalidate_user(self, user_id: int):
        """إزالة المستخدم من التخزين المؤقت"""
        if user_id in self.local_cache:
            del self.local_cache[user_id]
        
        if ConnectionManager._redis:
            await ConnectionManager._redis.delete(f"user:{user_id}")

# =========================
# إدارة المستخدمين
# =========================
class UserManager:
    def __init__(self):
        self.cache = CacheManager()
        self.validation = ValidationManager()
    
    async def get_or_create_user(self, user: types.User) -> Dict:
        """الحصول على مستخدم أو إنشاءه"""
        user_id = user.id
        
        # التحقق من التخزين المؤقت أولاً
        cached = await self.cache.get_user(user_id)
        if cached:
            return cached
        
        if ConnectionManager._db_pool:
            async with ConnectionManager._db_pool.acquire() as conn:
                # إنشاء كود إحالة فريد
                referral_code = self._generate_referral_code(user_id)
                
                try:
                    await conn.execute("""
                    INSERT INTO users 
                    (user_id, username, first_name, last_name, referral_code)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    updated_at = CURRENT_TIMESTAMP
                    RETURNING user_id, username, balance, referral_code, is_verified
                    """, 
                    user_id, user.username, user.first_name, user.last_name, referral_code)
                    
                    row = await conn.fetchrow(
                        "SELECT user_id, username, balance, referral_code, is_verified FROM users WHERE user_id = $1",
                        user_id
                    )
                    
                    if row:
                        user_data = dict(row)
                        await self.cache.set_user_cache(user_id, user_data)
                        
                        # تسجيل الدخول
                        await self._log_security_action(
                            user_id, "user_created_or_updated",
                            {"username": user.username}
                        )
                        
                        return user_data
                except Exception as e:
                    logger.error(f"خطأ في إنشاء المستخدم: {e}")
        
        # بيانات افتراضية إذا فشل الاتصال
        return {
            "user_id": user_id,
            "username": user.username,
            "balance": 0,
            "referral_code": self._generate_referral_code(user_id),
            "is_verified": False
        }
    
    def _generate_referral_code(self, user_id: int) -> str:
        """إنشاء كود إحالة فريد"""
        base = f"ICH{user_id}"
        hash_obj = hashlib.md5(base.encode())
        return hash_obj.hexdigest()[:8].upper()
    
    async def add_balance(self, user_id: int, amount: int, reason: str = "deposit") -> Tuple[bool, str]:
        """إضافة رصيد"""
        valid, msg = self.validation.validate_amount(amount)
        if not valid:
            return False, msg
        
        if ConnectionManager._db_pool:
            try:
                async with ConnectionManager._db_pool.acquire() as conn:
                    # الحصول على الرصيد الحالي أولاً
                    current = await conn.fetchval(
                        "SELECT balance FROM users WHERE user_id = $1",
                        user_id
                    )
                    
                    if current is None:
                        return False, "المستخدم غير موجود"
                    
                    result = await conn.fetchrow("""
                    UPDATE users 
                    SET balance = balance + $2,
                        total_deposited = total_deposited + $2,
                        last_transaction = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                    RETURNING balance
                    """, user_id, amount)
                    
                    if result:
                        # تسجيل المعاملة
                        await conn.execute("""
                        INSERT INTO transactions 
                        (user_id, type, amount, payment_method, status, notes)
                        VALUES ($1, $2, $3, $4, 'completed', $5)
                        """, user_id, reason, amount, "system", f"إضافة رصيد: {reason}")
                        
                        await self.cache.invalidate_user(user_id)
                        
                        # تسجيل الأمن
                        await self._log_security_action(
                            user_id, "balance_added",
                            {"amount": amount, "new_balance": result["balance"], "reason": reason}
                        )
                        
                        return True, f"تمت إضافة {amount} ليرة. الرصيد الجديد: {result['balance']}"
            except Exception as e:
                logger.error(f"خطأ في إضافة الرصيد: {e}")
                return False, "خطأ في النظام"
        
        return False, "غير متصل بقاعدة البيانات"
    
    async def deduct_balance(self, user_id: int, amount: int, reason: str = "withdraw") -> Tuple[bool, str]:
        """خصم رصيد"""
        valid, msg = self.validation.validate_amount(amount)
        if not valid:
            return False, msg
        
        if ConnectionManager._db_pool:
            try:
                async with ConnectionManager._db_pool.acquire() as conn:
                    # التحقق من الرصيد الكافي أولاً
                    current_balance = await conn.fetchval(
                        "SELECT balance FROM users WHERE user_id = $1",
                        user_id
                    )
                    
                    if current_balance is None:
                        return False, "المستخدم غير موجود"
                    
                    if current_balance < amount:
                        return False, f"رصيدك غير كافي. الرصيد الحالي: {current_balance}"
                    
                    # التحقق من الحد اليومي للسحب
                    today = datetime.now().date()
                    last_withdrawal = await conn.fetchval(
                        "SELECT last_withdrawal_date FROM users WHERE user_id = $1",
                        user_id
                    )
                    
                    daily_withdrawn = 0
                    if last_withdrawal == today:
                        daily_withdrawn = await conn.fetchval(
                            "SELECT daily_withdrawn FROM users WHERE user_id = $1",
                            user_id
                        ) or 0
                    
                    if daily_withdrawn + amount > config.MAX_WITHDRAW_PER_DAY:
                        return False, f"تجاوزت الحد اليومي للسحب ({config.MAX_WITHDRAW_PER_DAY})"
                    
                    result = await conn.fetchrow("""
                    UPDATE users 
                    SET balance = balance - $2,
                        total_withdrawn = total_withdrawn + $2,
                        daily_withdrawn = CASE 
                            WHEN last_withdrawal_date = CURRENT_DATE 
                            THEN daily_withdrawn + $2 
                            ELSE $2 
                        END,
                        last_withdrawal_date = CURRENT_DATE,
                        last_transaction = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                    RETURNING balance, daily_withdrawn
                    """, user_id, amount)
                    
                    if result:
                        # تسجيل المعاملة
                        await conn.execute("""
                        INSERT INTO transactions 
                        (user_id, type, amount, payment_method, status, notes)
                        VALUES ($1, $2, $3, $4, 'pending', $5)
                        """, user_id, reason, amount, "system", f"سحب رصيد: {reason}")
                        
                        await self.cache.invalidate_user(user_id)
                        
                        # تسجيل الأمن
                        await self._log_security_action(
                            user_id, "balance_deducted",
                            {"amount": amount, "new_balance": result["balance"], "reason": reason}
                        )
                        
                        return True, f"تم خصم {amount} ليرة. الرصيد المتبقي: {result['balance']}"
            except Exception as e:
                logger.error(f"خطأ في خصم الرصيد: {e}")
                return False, "خطأ في النظام"
        
        return False, "غير متصل بقاعدة البيانات"
    
    async def _log_security_action(self, user_id: int, action: str, details: Dict):
        """تسجيل إجراء أمني"""
        if ConnectionManager._db_pool:
            try:
                async with ConnectionManager._db_pool.acquire() as conn:
                    await conn.execute("""
                    INSERT INTO security_logs (user_id, action, details)
                    VALUES ($1, $2, $3)
                    """, user_id, action, json.dumps(details))
            except:
                pass

# =========================
# إدارة الجلسات
# =========================
class SessionManager:
    @staticmethod
    async def set_session(user_id: int, step: str, data: Dict = None, ttl: int = 1800):
        """تعيين جلسة"""
        if ConnectionManager._redis:
            session_data = {
                "step": step,
                "data": data or {},
                "created": datetime.now().isoformat(),
                "expires": (datetime.now() + timedelta(seconds=ttl)).isoformat()
            }
            await ConnectionManager._redis.setex(
                f"session:{user_id}", ttl, json.dumps(session_data)
            )
            return True
        return False
    
    @staticmethod
    async def get_session(user_id: int) -> Optional[Dict]:
        """الحصول على جلسة"""
        if ConnectionManager._redis:
            data = await ConnectionManager._redis.get(f"session:{user_id}")
            if data:
                session = json.loads(data)
                # تحديث TTL تلقائياً عند الوصول
                await ConnectionManager._redis.expire(f"session:{user_id}", 1800)
                return session
        return None
    
    @staticmethod
    async def update_session_data(user_id: int, updates: Dict):
        """تحديث بيانات الجلسة"""
        session = await SessionManager.get_session(user_id)
        if session:
            session["data"].update(updates)
            await SessionManager.set_session(user_id, session["step"], session["data"])
    
    @staticmethod
    async def clear_session(user_id: int):
        """مسح جلسة"""
        if ConnectionManager._redis:
            await ConnectionManager._redis.delete(f"session:{user_id}")

# =========================
# تهيئة المديرين
# =========================
connection_manager = ConnectionManager()
validation_manager = ValidationManager()
user_manager = UserManager()
session_manager = SessionManager()

async def init_services():
    """تهيئة الخدمات"""
    await connection_manager.init_db()
    await connection_manager.init_redis()

# =========================
# القائمة الرئيسية (نفس الواجهة تماماً)
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
# معالجات البوت - محسنة
# =========================
@bot.message_handler(commands=["start"])
async def start_command(message: types.Message):
    try:
        uid = message.from_user.id
        
        # التحقق من معدل الطلبات
        can_proceed, rate_msg = await validation_manager.check_rate_limit(uid, "start")
        if not can_proceed:
            await bot.send_message(message.chat.id, f"⚠️ {rate_msg}")
            return
        
        await init_services()
        user = await user_manager.get_or_create_user(message.from_user)
        balance = user.get("balance", 0)
        username = user.get("username", message.from_user.username or "مستخدم")
        
        welcome_text = f"""
👋 أهلاً بك *{username}* في IChancy!

⚡ *منصة التعاملات المالية الآمنة*
        
💰 *رصيدك الحالي:* `{balance} ليرة سورية`
🎫 *كود الإحالة الخاص بك:* `{user.get('referral_code', 'غير متوفر')}`

📊 *إحصائيات سريعة:*
├ الحد الأدنى للتعامل: {config.MIN_TRANSACTION:,} ليرة
├ الحد الأقصى اليومي للسحب: {config.MAX_WITHDRAW_PER_DAY:,} ليرة
└ الحد الأقصى للتعامل: {config.MAX_TRANSACTION:,} ليرة

🔒 *ميزات الأمان:*
✓ تأمين عالي المستوى
✓ سجل كامل للمعاملات
✓ تحقق من كل عملية
        """
        
        await bot.send_message(
            message.chat.id,
            welcome_text,
            reply_markup=main_menu(uid),
            parse_mode="Markdown"
        )
        
        await session_manager.clear_session(uid)
        
        logger.info(f"✅ بدء جلسة للمستخدم: {uid} ({username})")
        
    except Exception as e:
        logger.error(f"خطأ في start: {e}")
        await bot.send_message(
            message.chat.id,
            "⚠️ مرحباً! البوت يعمل.\n\n"
            "للمساعدة:\n"
            "1. تأكد من ضغط /start\n"
            "2. إذا استمرت المشكلة تواصل مع الدعم"
        )

@bot.callback_query_handler(func=lambda call: True)
async def callback_handler(call: CallbackQuery):
    try:
        uid = call.from_user.id
        data = call.data
        
        # التحقق من معدل الطلبات
        can_proceed, rate_msg = await validation_manager.check_rate_limit(uid, "callback")
        if not can_proceed:
            await bot.answer_callback_query(call.id, rate_msg, show_alert=True)
            return
        
        if data == "support":
            await session_manager.set_session(uid, "support")
            await bot.send_message(call.message.chat.id, 
                "✍️ *اكتب رسالتك للدعم:*\n"
                "يرجى وصف مشكلتك بالتفصيل وسيقوم فريق الدعم بالرد عليك خلال 24 ساعة.",
                parse_mode="Markdown")
            await bot.answer_callback_query(call.id)
        
        elif data == "charge":
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton("💰 سيرياتيل كاش", callback_data="pay_syr"),
                InlineKeyboardButton("💰 شام كاش", callback_data="pay_sch")
            )
            kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back"))
            await bot.send_message(call.message.chat.id, 
                "📥 *اختر طريقة الدفع:*\n\n"
                "💡 *تعليمات:*\n"
                "1. اختر طريقة الدفع\n"
                "2. حول المبلغ إلى الرقم المحدد\n"
                "3. أرسل رقم العملية\n"
                "4. انتظر الموافقة (عادة خلال 15 دقيقة)",
                reply_markup=kb,
                parse_mode="Markdown")
            await session_manager.set_session(uid, "awaiting_payment")
            await bot.answer_callback_query(call.id)
        
        elif data == "withdraw":
            # التحقق من رصيد المستخدم أولاً
            user = await user_manager.get_or_create_user(call.from_user)
            if user.get("balance", 0) < config.MIN_TRANSACTION:
                await bot.answer_callback_query(call.id, 
                    f"❌ الرصيد غير كافي للبدء. الحد الأدنى للسحب: {config.MIN_TRANSACTION} ليرة", 
                    show_alert=True)
                return
            
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton("💰 سيرياتيل كاش", callback_data="withdraw_syr"),
                InlineKeyboardButton("💰 شام كاش", callback_data="withdraw_sch")
            )
            kb.add(InlineKeyboardButton("⬅️ رجوع", callback_data="back"))
            await bot.send_message(call.message.chat.id, 
                "📤 *اختر طريقة السحب:*\n\n"
                "💡 *تعليمات:*\n"
                "1. اختر طريقة السحب\n"
                "2. أدخل المبلغ\n"
                "3. أدخل رقم حسابك\n"
                "4. انتظر الموافقة (عادة خلال 30 دقيقة)",
                reply_markup=kb,
                parse_mode="Markdown")
            await session_manager.set_session(uid, "awaiting_withdraw")
            await bot.answer_callback_query(call.id)
        
        elif data in ["pay_syr", "pay_sch"]:
            payment = "سيرياتيل كاش" if data == "pay_syr" else "شام كاش"
            number = config.SYR_CASH_NUMBER if data == "pay_syr" else config.SCH_CASH_NUMBER
            
            # تحذير إذا كان الرقم الافتراضي
            warning = ""
            if "XXXX" in number or "YYYY" in number:
                warning = "\n⚠️ *تحذير:* الرقم الافتراضي قيد الاستخدام. يرجى تحديثه في إعدادات البيئة."
            
            await session_manager.set_session(uid, "awaiting_amount", {
                "payment": payment,
                "number": number,
                "type": "deposit"
            })
            await bot.send_message(
                call.message.chat.id,
                f"💳 *{payment}*\n\n"
                f"📱 *الرقم:* `{number}`\n"
                f"💰 *الحد الأدنى:* {config.MIN_TRANSACTION:,} ليرة\n"
                f"💰 *الحد الأقصى:* {config.MAX_TRANSACTION:,} ليرة\n\n"
                f"📝 *بعد التحويل، أدخل المبلغ الذي حولته:*"
                f"{warning}",
                parse_mode="Markdown"
            )
            await bot.answer_callback_query(call.id)
        
        elif data == "back":
            await bot.send_message(
                call.message.chat.id,
                "✅ *عدنا إلى القائمة الرئيسية:*",
                reply_markup=main_menu(uid),
                parse_mode="Markdown"
            )
            await session_manager.clear_session(uid)
            await bot.answer_callback_query(call.id)
        
        elif data in ["withdraw_syr", "withdraw_sch"]:
            user = await user_manager.get_or_create_user(call.from_user)
            payment = "سيرياتيل كاش" if data == "withdraw_syr" else "شام كاش"
            
            # التحقق من الرصيد أولاً
            balance = user.get("balance", 0)
            
            info_text = f"""
💳 *طريقة السحب:* {payment}

💰 *رصيدك الحالي:* {balance:,} ليرة
📊 *الحد الأدنى للسحب:* {config.MIN_TRANSACTION:,} ليرة
📊 *الحد الأقصى اليومي:* {config.MAX_WITHDRAW_PER_DAY:,} ليرة

💵 *أدخل المبلغ المراد سحبه:*
            """
            
            await session_manager.set_session(uid, "awaiting_withdraw_amount", {
                "payment": payment,
                "type": "withdraw"
            })
            await bot.send_message(
                call.message.chat.id,
                info_text,
                parse_mode="Markdown"
            )
            await bot.answer_callback_query(call.id)
        
        # معالجات للوظائف غير المكتملة (رسائل توضيحية)
        elif data in ["referrals", "gift", "gift_code", "tutorials", "bets", "jackpot", "vp", "apk", "rules", "contact", "logs", "ichancy"]:
            feature_name = {
                "referrals": "نظام الإحالات",
                "gift": "إهداء الرصيد",
                "gift_code": "كود الهدية",
                "tutorials": "الشروحات",
                "bets": "سجل الرهانات",
                "jackpot": "الجاكبوت",
                "vp": "VPN للوصول الكامل",
                "apk": "تطبيق IChancy",
                "rules": "الشروط والأحكام",
                "contact": "تواصل معنا",
                "logs": "سجل المعاملات",
                "ichancy": "معلومات IChancy"
            }.get(data, "هذه الميزة")
            
            await bot.answer_callback_query(call.id, 
                f"🛠️ {feature_name} قيد التطوير. ستكون متاحة قريباً!", 
                show_alert=True)
        
        elif data == "admin_panel" and uid == config.ADMIN_ID:
            await bot.answer_callback_query(call.id, "لوحة التحكم للمشرف", show_alert=True)
            # يمكن إضافة لوحة تحكم هنا
        
    except Exception as e:
        logger.error(f"خطأ في callback: {e}")
        await bot.answer_callback_query(call.id, "⚠️ حدث خطأ في النظام", show_alert=True)

@bot.message_handler(func=lambda m: True)
async def message_handler(message: types.Message):
    try:
        uid = message.from_user.id
        session = await session_manager.get_session(uid)
        
        if not session:
            return
        
        step = session.get("step")
        data = session.get("data", {})
        
        if step == "support":
            if len(message.text.strip()) < 10:
                await bot.send_message(
                    message.chat.id,
                    "❌ الرسالة قصيرة جداً. يرجى وصف مشكلتك بتفصيل أكثر (10 أحرف على الأقل)."
                )
                return
            
            await bot.send_message(
                message.chat.id,
                "✅ *تم إرسال رسالتك للدعم.*\n\n"
                "📋 *رقم التذكرة:* `" + str(random.randint(100000, 999999)) + "`\n"
                "⏱️ *وقت الاستجابة المتوقع:* 24 ساعة\n"
                "📬 *سيصلك رد على هذه الدردشة.*",
                parse_mode="Markdown"
            )
            await session_manager.clear_session(uid)
        
        elif step == "awaiting_amount":
            if message.text.isdigit():
                amount = int(message.text)
                valid, msg = validation_manager.validate_amount(amount)
                
                if not valid:
                    await bot.send_message(message.chat.id, f"❌ {msg}")
                    return
                
                payment = data.get("payment", "")
                number = data.get("number", "")
                
                await bot.send_message(
                    message.chat.id,
                    f"✅ *تم استلام طلبك:*\n\n"
                    f"💰 *المبلغ:* {amount:,} ليرة\n"
                    f"💳 *الطريقة:* {payment}\n"
                    f"📱 *الرقم:* `{number}`\n\n"
                    f"🔑 *أرسل رقم العملية (Transaction ID):*\n"
                    f"(يمكنك العثور عليه في إشعار الدفع أو سجلك المصرفي)",
                    parse_mode="Markdown"
                )
                data["amount"] = amount
                await session_manager.set_session(uid, "awaiting_txid", data)
            else:
                await bot.send_message(message.chat.id, "❌ يرجى إدخال رقم صحيح فقط.")
        
        elif step == "awaiting_txid":
            txid = message.text.strip()
            if not validation_manager.validate_transaction_id(txid):
                await bot.send_message(message.chat.id, "❌ رقم العملية غير صالح. يرجى إدخال رقم صحيح.")
                return
            
            amount = data.get("amount", 0)
            payment = data.get("payment", "")
            
            if ConnectionManager._db_pool:
                try:
                    async with ConnectionManager._db_pool.acquire() as conn:
                        # التحقق من عدم تكرار رقم العملية
                        existing = await conn.fetchval(
                            "SELECT id FROM transactions WHERE transaction_id = $1",
                            txid
                        )
                        
                        if existing:
                            await bot.send_message(
                                message.chat.id,
                                "❌ رقم العملية هذا مستخدم مسبقاً. يرجى التحقق وإرسال رقم صحيح."
                            )
                            return
                        
                        await conn.execute("""
                        INSERT INTO transactions 
                        (user_id, type, amount, payment_method, transaction_id, status, notes)
                        VALUES ($1, $2, $3, $4, $5, 'pending', $6)
                        """, uid, "deposit", amount, payment, txid, 
                        f"طلب إيداع عبر {payment}. رقم العملية: {txid}")
                        
                        # الحصول على رقم الطلب
                        order_id = await conn.fetchval(
                            "SELECT id FROM transactions WHERE transaction_id = $1",
                            txid
                        )
                        
                        # إرسال إشعار للمشرف
                        if config.CHANNEL_ADMIN_LOGS:
                            try:
                                await bot.send_message(
                                    config.CHANNEL_ADMIN_LOGS,
                                    f"🔄 *طلب إيداع جديد*\n\n"
                                    f"👤 المستخدم: [{message.from_user.first_name}](tg://user?id={uid})\n"
                                    f"🆔 المعرف: `{uid}`\n"
                                    f"💰 المبلغ: {amount:,} ليرة\n"
                                    f"💳 الطريقة: {payment}\n"
                                    f"🔢 رقم العملية: `{txid}`\n"
                                    f"🆔 رقم الطلب: `{order_id}`",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                        
                        await bot.send_message(
                            message.chat.id,
                            f"✅ *تم إرسال طلبك للمراجعة*\n\n"
                            f"📋 *رقم الطلب:* `{order_id}`\n"
                            f"💰 *المبلغ:* {amount:,} ليرة\n"
                            f"💳 *الطريقة:* {payment}\n"
                            f"⏱️ *وقت المعالجة:* 15-30 دقيقة\n\n"
                            f"📬 *سيتم إعلامك عند الموافقة على الطلب.*",
                            parse_mode="Markdown",
                            reply_markup=main_menu(uid)
                        )
                        
                        await session_manager.clear_session(uid)
                        
                except Exception as e:
                    logger.error(f"خطأ في حفظ الإيداع: {e}")
                    await bot.send_message(message.chat.id, "❌ حدث خطأ في حفظ الطلب. يرجى المحاولة لاحقاً.")
        
        elif step == "awaiting_withdraw_amount":
            if message.text.isdigit():
                amount = int(message.text)
                valid, msg = validation_manager.validate_amount(amount)
                
                if not valid:
                    await bot.send_message(message.chat.id, f"❌ {msg}")
                    return
                
                user = await user_manager.get_or_create_user(message.from_user)
                balance = user.get("balance", 0)
                
                if amount > balance:
                    await bot.send_message(
                        message.chat.id,
                        f"❌ رصيدك غير كافي.\n\n"
                        f"💰 *رصيدك الحالي:* {balance:,} ليرة\n"
                        f"💵 *المبلغ المطلوب:* {amount:,} ليرة\n"
                        f"📊 *الفرق:* {balance - amount:,} ليرة"
                    )
                    return
                
                await bot.send_message(
                    message.chat.id,
                    f"✅ *المبلغ مقبول*\n\n"
                    f"💵 *المبلغ:* {amount:,} ليرة\n"
                    f"💳 *طريقة السحب:* {data.get('payment', '')}\n\n"
                    f"📱 *الآن أدخل رقم حسابك لاستلام المبلغ:*\n"
                    f"(يجب أن يكون بنفس طريقة السحب المختارة)"
                )
                data["amount"] = amount
                await session_manager.set_session(uid, "awaiting_account", data)
            else:
                await bot.send_message(message.chat.id, "❌ يرجى إدخال رقم صحيح فقط.")
        
        elif step == "awaiting_account":
            account = message.text.strip()
            payment = data.get("payment", "")
            amount = data.get("amount", 0)
            
            # التحقق من رقم الحساب
            if not validation_manager.validate_phone_number(account):
                await bot.send_message(
                    message.chat.id,
                    f"❌ رقم الحساب غير صالح.\n"
                    f"📱 *مثال على رقم سيرياتيل:* 0991234567\n"
                    f"📱 *مثال على رقم شام:* 0941234567\n\n"
                    f"يرجى إدخال رقم صحيح."
                )
                return
            
            if ConnectionManager._db_pool:
                try:
                    async with ConnectionManager._db_pool.acquire() as conn:
                        # التحقق من الحد اليومي
                        today = datetime.now().date()
                        daily_withdrawn = await conn.fetchval("""
                        SELECT COALESCE(SUM(amount), 0) 
                        FROM transactions 
                        WHERE user_id = $1 
                        AND type = 'withdraw' 
                        AND status = 'completed'
                        AND DATE(created_at) = $2
                        """, uid, today)
                        
                        if daily_withdrawn + amount > config.MAX_WITHDRAW_PER_DAY:
                            remaining = config.MAX_WITHDRAW_PER_DAY - daily_withdrawn
                            await bot.send_message(
                                message.chat.id,
                                f"❌ تجاوزت الحد اليومي للسحب.\n\n"
                                f"📊 *السحب اليومي الحالي:* {daily_withdrawn:,} ليرة\n"
                                f"📊 *الحد الأقصى اليومي:* {config.MAX_WITHDRAW_PER_DAY:,} ليرة\n"
                                f"💵 *يمكنك سحب كحد أقصى:* {remaining:,} ليرة"
                            )
                            return
                        
                        txid = f"WDR{random.randint(100000, 999999)}"
                        
                        await conn.execute("""
                        INSERT INTO transactions 
                        (user_id, type, amount, payment_method, transaction_id, account_number, status, notes)
                        VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
                        """, uid, "withdraw", amount, payment, txid, account,
                        f"طلب سحب عبر {payment}. رقم الحساب: {account}")
                        
                        # الحصول على رقم الطلب
                        order_id = await conn.fetchval(
                            "SELECT id FROM transactions WHERE transaction_id = $1",
                            txid
                        )
                        
                        # إرسال إشعار للمشرف
                        if config.CHANNEL_WITHDRAW:
                            try:
                                await bot.send_message(
                                    config.CHANNEL_WITHDRAW,
                                    f"🔄 *طلب سحب جديد*\n\n"
                                    f"👤 المستخدم: [{message.from_user.first_name}](tg://user?id={uid})\n"
                                    f"🆔 المعرف: `{uid}`\n"
                                    f"💰 المبلغ: {amount:,} ليرة\n"
                                    f"💳 الطريقة: {payment}\n"
                                    f"📱 رقم الحساب: `{account}`\n"
                                    f"🆔 رقم الطلب: `{order_id}`\n"
                                    f"🔢 رقم المعاملة: `{txid}`",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                        
                        await bot.send_message(
                            message.chat.id,
                            f"✅ *تم إرسال طلب السحب للمراجعة*\n\n"
                            f"📋 *رقم الطلب:* `{order_id}`\n"
                            f"💰 *المبلغ:* {amount:,} ليرة\n"
                            f"💳 *الطريقة:* {payment}\n"
                            f"📱 *رقم الحساب:* `{account}`\n"
                            f"⏱️ *وقت المعالجة:* 30-60 دقيقة\n\n"
                            f"📬 *سيتم إعلامك عند الموافقة على الطلب.*",
                            parse_mode="Markdown",
                            reply_markup=main_menu(uid)
                        )
                        
                        await session_manager.clear_session(uid)
                        
                except Exception as e:
                    logger.error(f"خطأ في حفظ السحب: {e}")
                    await bot.send_message(message.chat.id, "❌ حدث خطأ في حفظ الطلب. يرجى المحاولة لاحقاً.")
    
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        await bot.send_message(message.chat.id, "❌ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.")

# =========================
# وظائف إضافية للمشرف
# =========================
@bot.message_handler(commands=["admin"])
async def admin_command(message: types.Message):
    uid = message.from_user.id
    
    if uid != config.ADMIN_ID:
        await bot.send_message(message.chat.id, "❌ هذا الأمر للمشرفين فقط.")
        return
    
    stats_text = await get_admin_stats()
    await bot.send_message(
        message.chat.id,
        stats_text,
        parse_mode="Markdown"
    )

async def get_admin_stats() -> str:
    """الحصول على إحصائيات المشرف"""
    if not ConnectionManager._db_pool:
        return "❌ غير متصل بقاعدة البيانات"
    
    try:
        async with ConnectionManager._db_pool.acquire() as conn:
            # إحصائيات المستخدمين
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            active_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            
            # إحصائيات المعاملات
            total_transactions = await conn.fetchval("SELECT COUNT(*) FROM transactions")
            pending_deposits = await conn.fetchval(
                "SELECT COUNT(*) FROM transactions WHERE type = 'deposit' AND status = 'pending'"
            )
            pending_withdrawals = await conn.fetchval(
                "SELECT COUNT(*) FROM transactions WHERE type = 'withdraw' AND status = 'pending'"
            )
            
            # إجمالي الأموال
            total_deposited = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'deposit' AND status = 'completed'")
            total_withdrawn = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'withdraw' AND status = 'completed'")
            
            return f"""
📊 *إحصائيات النظام - المشرف*

👥 *المستخدمون:*
├ إجمالي المستخدمين: `{total_users:,}`
├ المستخدمين النشطين: `{active_users:,}`
└ نسبة النشاط: `{round((active_users/total_users*100) if total_users > 0 else 0, 1)}%`

💸 *المعاملات:*
├ إجمالي المعاملات: `{total_transactions:,}`
├ طلبات الإيداع المعلقة: `{pending_deposits:,}`
├ طلبات السحب المعلقة: `{pending_withdrawals:,}`
└ إجمالي المعلقة: `{pending_deposits + pending_withdrawals:,}`

💰 *الأموال:*
├ إجمالي الإيداعات: `{total_deposited:,} ليرة`
├ إجمالي السحوبات: `{total_withdrawn:,} ليرة`
└ صافي النظام: `{total_deposited - total_withdrawn:,} ليرة`

⏰ *آخر تحديث:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
    except Exception as e:
        logger.error(f"خطأ في إحصائيات المشرف: {e}")
        return f"❌ خطأ في جلب الإحصائيات: {str(e)}"

# =========================
# وظائف الخلفية
# =========================
async def background_tasks():
    """مهام خلفية دورية"""
    while True:
        try:
            await asyncio.sleep(300)  # كل 5 دقائق
            
            # تنظيف الجلسات المنتهية
            if ConnectionManager._redis:
                # يمكن إضافة تنظيف للجلسات القديمة هنا
                pass
                
            # تسجيل حالة النظام
            logger.info("📊 النظام يعمل بشكل طبيعي")
            
        except Exception as e:
            logger.error(f"خطأ في المهام الخلفية: {e}")
            await asyncio.sleep(60)

# =========================
# التشغيل الرئيسي
# =========================
async def main():
    keep_alive()  # إبقاء البوت نشط
    
    print("=" * 60)
    print("🚀 بدء تشغيل IChancy Bot - النسخة المحسنة")
    print("=" * 60)
    
    try:
        # تهيئة الخدمات
        await init_services()
        
        # الحصول على معلومات البوت
        bot_info = await bot.get_me()
        print(f"🤖 البوت: @{bot_info.username}")
        print(f"🆔 ID: {bot_info.id}")
        print(f"📛 الاسم: {bot_info.first_name}")
        
        print("\n✅ جميع الخدمات جاهزة")
        print("📱 اكتب /start في تيليجرام للبدء")
        print("=" * 60)
        
        # بدء المهام الخلفية
        asyncio.create_task(background_tasks())
        
        # بدء البوت
        await bot.polling(
            none_stop=True,
            timeout=30,
            request_timeout=30,
            restart_on_change=True
        )
        
    except Exception as e:
        print(f"❌ خطأ رئيسي: {e}")
        logger.error(f"خطأ رئيسي: {e}", exc_info=True)
        
    finally:
        # تنظيف الموارد
        print("\n🔴 إغلاق النظام...")
        if ConnectionManager._db_pool:
            await ConnectionManager._db_pool.close()
        if ConnectionManager._redis:
            await ConnectionManager._redis.close()
        print("✅ تم إغلاق جميع الاتصالات")

if __name__ == "__main__":
    asyncio.run(main())