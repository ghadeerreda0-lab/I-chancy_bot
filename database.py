"""
database.py - دوال قاعدة البيانات
"""

import sqlite3
import json
import datetime
import random
import string
import hashlib
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

from config import DB_PATH, ADMIN_ID, PAYMENT_METHODS, DEFAULT_SETTINGS
from utils import safe_execute, CacheWithTTL

logger = logging.getLogger(__name__)
cache = CacheWithTTL()

# =========================
# دوال تهيئة قاعدة البيانات
# =========================

@safe_execute
def init_db():
    """
    تهيئة قاعدة البيانات وإنشاء جميع الجداول
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # إنشاء جميع الجداول
            from models import ALL_TABLES, INDICES
            for table_sql in ALL_TABLES:
                c.execute(table_sql)
            
            conn.commit()

        # تهيئة الإعدادات الافتراضية
        init_default_settings()
        init_default_payment_settings()
        init_default_limits()
        init_referral_settings()

        # إنشاء المؤشرات
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            for idx_name, idx_sql in INDICES:
                try:
                    c.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_sql}")
                except Exception as idx_error:
                    logger.warning(f"⚠️ خطأ في إنشاء المؤشر {idx_name}: {idx_error}")
            
            conn.commit()

        logger.info("✅ تم تهيئة قاعدة البيانات مع جميع الجداول الجديدة")
        return True

    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
        return False

@safe_execute
def init_default_settings():
    """
    تهيئة الإعدادات الافتراضية للنظام
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            for key, value in DEFAULT_SETTINGS:
                c.execute("""
                    INSERT OR IGNORE INTO system_settings (key, value, updated_by) 
                    VALUES (?, ?, ?)
                """, (key, value, ADMIN_ID))
            conn.commit()

        logger.info("✅ تم تهيئة الإعدادات الافتراضية")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة الإعدادات: {e}")
        return False

@safe_execute 
def init_default_payment_settings():
    """
    تهيئة إعدادات طرق الدفع الافتراضية
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            for method_id, method_name in PAYMENT_METHODS:
                c.execute("""
                    INSERT OR IGNORE INTO payment_settings 
                    (payment_method, is_visible, is_active, pause_message)
                    VALUES (?, 1, 1, ?)
                """, (method_id, f'⏸️ خدمة {method_name} متوقفة مؤقتاً'))
            conn.commit()

        logger.info("✅ تم تهيئة إعدادات الدفع الافتراضية")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة إعدادات الدفع: {e}")
        return False

@safe_execute
def init_default_limits():
    """
    تهيئة حدود المبالغ الافتراضية
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            for method_id, method_name in PAYMENT_METHODS:
                min_amount = 1000
                max_amount = 50000
                if method_id == 'sham_cash_usd':
                    min_amount = 10
                    max_amount = 500

                c.execute("""
                    INSERT OR IGNORE INTO payment_limits 
                    (payment_method, min_amount, max_amount, updated_by)
                    VALUES (?, ?, ?, ?)
                """, (method_id, min_amount, max_amount, ADMIN_ID))
            conn.commit()

        logger.info("✅ تم تهيئة حدود المبالغ الافتراضية")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة الحدود: {e}")
        return False

@safe_execute
def init_referral_settings():
    """
    تهيئة إعدادات الإحالات الافتراضية
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO referral_settings 
                (commission_rate, bonus_amount, min_active_referrals, min_charge_amount)
                VALUES (10, 2000, 5, 100000)
            """)
            conn.commit()
        logger.info("✅ تم تهيئة إعدادات الإحالات الافتراضية")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة إعدادات الإحالات: {e}")
        return False

# =========================
# دوال نظام الإعدادات
# =========================

@safe_execute
def get_setting(key: str, default: Any = None) -> Any:
    """
    جلب إعداد من قاعدة البيانات مع التخزين المؤقت
    """
    cached = cache.get(f"setting_{key}")
    if cached is not None:
        return cached

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM system_settings WHERE key=?", (key,))
            row = c.fetchone()
            if row:
                cache.set(f"setting_{key}", row[0], ttl=60)
                return row[0]
            return default
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الإعداد {key}: {e}")
        return default

@safe_execute
def update_setting(key: str, value: str, admin_id: int = ADMIN_ID, reason: str = "") -> bool:
    """
    تحديث إعداد في النظام
    """
    try:
        old_value = get_setting(key)

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at, updated_by)
                VALUES (?, ?, datetime('now'), ?)
            """, (key, value, admin_id))

            if reason:
                c.execute("""
                    INSERT INTO settings_logs (admin_id, setting_key, old_value, new_value, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (admin_id, key, old_value, value, reason))

            conn.commit()

        cache.delete(f"setting_{key}")
        logger.info(f"✅ تم تحديث الإعداد: {key} = {value}")
        return True

    except Exception as e:
        logger.error(f"❌ خطأ في تحديث الإعداد {key}: {e}")
        return False

# =========================
# دوال نظام الأدمن
# =========================

@safe_execute
def is_admin(user_id: int) -> bool:
    """
    التحقق إذا كان المستخدم أدمن
    """
    if user_id == ADMIN_ID:
        return True

    cached = cache.get(f"admin_{user_id}")
    if cached is not None:
        return cached

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
            result = c.fetchone() is not None
            cache.set(f"admin_{user_id}", result, ttl=300)
            return result
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من الأدمن: {e}")
        return False

@safe_execute
def can_manage_admins(user_id: int) -> bool:
    """
    التحقق إذا كان المستخدم يمكنه إدارة الأدمن
    """
    return user_id == ADMIN_ID

@safe_execute
def get_all_admins() -> List[Tuple]:
    """
    جلب جميع الأدمن
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT u.user_id, u.created_at, a.added_at, a.added_by
                FROM admins a
                JOIN users u ON a.user_id = u.user_id
                ORDER BY a.added_at DESC
            """)
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب جميع الأدمن: {e}")
        return []

@safe_execute
def add_admin(user_id: int, added_by: int = ADMIN_ID) -> Dict[str, Any]:
    """
    إضافة أدمن جديد
    """
    if not is_admin(added_by) and added_by != ADMIN_ID:
        return {"success": False, "message": "❌ ليس لديك صلاحية إضافة أدمن"}

    if user_id == ADMIN_ID:
        return {"success": False, "message": "❌ المشرف الرئيسي مضاف بالفعل"}

    try:
        # التحقق من عدد الأدمن
        admins = get_all_admins()
        max_admins = int(get_setting('max_admins', 10))
        if len(admins) >= max_admins:
            return {"success": False, "message": f"❌ وصلت للحد الأقصى ({max_admins} أدمن)"}

        # التحقق إذا كان المستخدم موجوداً
        if not get_user(user_id):
            return {"success": False, "message": "❌ المستخدم غير موجود في البوت"}

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
            if c.fetchone():
                return {"success": False, "message": "❌ المستخدم أدمن بالفعل"}

            c.execute("""
                INSERT INTO admins (user_id, added_by, added_at)
                VALUES (?, ?, datetime('now'))
            """, (user_id, added_by))
            conn.commit()

        cache.delete(f"admin_{user_id}")
        logger.info(f"✅ تم إضافة أدمن جديد: {user_id}")
        return {"success": True, "message": f"✅ تم إضافة المستخدم {user_id} كأدمن"}

    except Exception as e:
        logger.error(f"❌ خطأ في إضافة أدمن: {e}")
        return {"success": False, "message": f"❌ خطأ في الإضافة: {str(e)[:100]}"}

@safe_execute
def remove_admin(user_id: int, removed_by: int = ADMIN_ID) -> Dict[str, Any]:
    """
    حذف أدمن
    """
    if not can_manage_admins(removed_by):
        return {"success": False, "message": "❌ ليس لديك صلاحية حذف أدمن"}

    if user_id == ADMIN_ID:
        return {"success": False, "message": "❌ لا يمكن حذف المشرف الرئيسي"}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
            if not c.fetchone():
                return {"success": False, "message": "❌ المستخدم ليس أدمن"}

            c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
            conn.commit()

        cache.delete(f"admin_{user_id}")
        logger.info(f"✅ تم حذف أدمن: {user_id}")
        return {"success": True, "message": f"✅ تم حذف المستخدم {user_id} من قائمة الأدمن"}

    except Exception as e:
        logger.error(f"❌ خطأ في حذف أدمن: {e}")
        return {"success": False, "message": f"❌ خطأ في الحذف: {str(e)[:100]}"}

# =========================
# دوال نظام Ichancy
# =========================

def generate_ichancy_username() -> str:
    """
    توليد اسم مستخدم فريد لـ Ichancy
    """
    adjectives = ["Swift", "Smart", "Fast", "Pro", "Elite", "Gold", "Prime", "Max", "Ultra", "Mega"]
    nouns = ["Player", "Trader", "Master", "Champion", "Warrior", "King", "Legend", "Hero", "Star", "Ace"]

    while True:
        adjective = random.choice(adjectives)
        noun = random.choice(nouns)
        number = random.randint(100, 9999)
        username = f"{adjective}{noun}{number}"

        # التحقق من التكرار
        try:
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM ichancy_accounts WHERE ichancy_username=?", (username,))
                if not c.fetchone():
                    return username
        except:
            return username

def generate_strong_password(length: int = 10) -> str:
    """
    توليد كلمة مرور قوية
    """
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*"

    # التأكد من وجود حرف كبير، صغير، رقم، ورمز
    password = [
        random.choice(uppercase),
        random.choice(lowercase),
        random.choice(digits),
        random.choice(symbols)
    ]

    # إكمال الباقي عشوائياً
    all_chars = uppercase + lowercase + digits + symbols
    password += [random.choice(all_chars) for _ in range(length - 4)]

    # خلط الأحرف
    random.shuffle(password)
    return ''.join(password)

@safe_execute
def create_ichancy_account(user_id: int) -> Dict[str, Any]:
    """
    إنشاء حساب Ichancy للمستخدم
    """
    try:
        # التحقق إذا كان لديه حساب بالفعل
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM ichancy_accounts WHERE user_id=?", (user_id,))
            if c.fetchone():
                return {"success": False, "message": "❌ لديك حساب Ichancy بالفعل"}

            # توليد اسم مستخدم فريد
            username = generate_ichancy_username()
            # توليد كلمة مرور قوية
            password = generate_strong_password()

            c.execute("""
                INSERT INTO ichancy_accounts (user_id, ichancy_username, ichancy_password, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (user_id, username, password))
            conn.commit()

        logger.info(f"✅ تم إنشاء حساب Ichancy للمستخدم {user_id}")
        return {
            "success": True, 
            "message": "✅ تم إنشاء حساب Ichancy بنجاح!",
            "username": username,
            "password": password
        }

    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء حساب Ichancy: {e}")
        return {"success": False, "message": f"❌ خطأ في إنشاء الحساب: {str(e)[:100]}"}

@safe_execute
def get_ichancy_account(user_id: int) -> Optional[Dict[str, Any]]:
    """
    جلب بيانات حساب Ichancy للمستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT ichancy_username, ichancy_password, ichancy_balance, created_at, last_login
                FROM ichancy_accounts WHERE user_id=?
            """, (user_id,))
            row = c.fetchone()

            if row:
                return {
                    "username": row[0],
                    "password": row[1],
                    "balance": row[2],
                    "created_at": row[3],
                    "last_login": row[4]
                }
            return None
    except Exception as e:
        logger.error(f"❌ خطأ في جلب حساب Ichancy: {e}")
        return None

@safe_execute
def update_ichancy_balance(user_id: int, amount: int, operation: str = 'add') -> Dict[str, Any]:
    """
    تحديث رصيد حساب Ichancy
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            if operation == 'add':
                c.execute("""
                    UPDATE ichancy_accounts 
                    SET ichancy_balance = ichancy_balance + ?, last_login = datetime('now')
                    WHERE user_id=?
                """, (amount, user_id))
            elif operation == 'subtract':
                c.execute("""
                    UPDATE ichancy_accounts 
                    SET ichancy_balance = MAX(0, ichancy_balance - ?), last_login = datetime('now')
                    WHERE user_id=?
                """, (amount, user_id))

            c.execute("SELECT ichancy_balance FROM ichancy_accounts WHERE user_id=?", (user_id,))
            new_balance = c.fetchone()[0]
            conn.commit()

            return {"success": True, "new_balance": new_balance}

    except Exception as e:
        logger.error(f"❌ خطأ في تحديث رصيد Ichancy: {e}")
        return {"success": False, "message": str(e)}

# =========================
# دوال نظام الإحالات
# =========================

@safe_execute
def get_referral_settings() -> Optional[Dict[str, Any]]:
    """
    جلب إعدادات الإحالات
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM referral_settings ORDER BY id DESC LIMIT 1")
            row = c.fetchone()

            if row:
                return {
                    "commission_rate": row[1],
                    "bonus_amount": row[2],
                    "min_active_referrals": row[3],
                    "min_charge_amount": row[4],
                    "next_distribution": row[5]
                }
            return None
    except Exception as e:
        logger.error(f"❌ خطأ في جلب إعدادات الإحالات: {e}")
        return None

@safe_execute
def update_referral_settings(
    commission_rate: Optional[int] = None,
    bonus_amount: Optional[int] = None,
    min_active_referrals: Optional[int] = None,
    min_charge_amount: Optional[int] = None,
    next_distribution: Optional[str] = None
) -> bool:
    """
    تحديث إعدادات الإحالات
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # جلب الإعدادات الحالية
            current = get_referral_settings()
            if not current:
                return False

            updates = []
            params = []

            if commission_rate is not None:
                updates.append("commission_rate = ?")
                params.append(commission_rate)

            if bonus_amount is not None:
                updates.append("bonus_amount = ?")
                params.append(bonus_amount)

            if min_active_referrals is not None:
                updates.append("min_active_referrals = ?")
                params.append(min_active_referrals)

            if min_charge_amount is not None:
                updates.append("min_charge_amount = ?")
                params.append(min_charge_amount)

            if next_distribution is not None:
                updates.append("next_distribution = ?")
                params.append(next_distribution)

            if updates:
                updates.append("updated_at = datetime('now')")
                query = f"UPDATE referral_settings SET {', '.join(updates)} WHERE id = (SELECT MAX(id) FROM referral_settings)"
                c.execute(query, params)
                conn.commit()

                logger.info("✅ تم تحديث إعدادات الإحالات")
                return True

        return False
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث إعدادات الإحالات: {e}")
        return False

@safe_execute
def generate_referral_code(user_id: int) -> str:
    """
    توليد كود إحالة فريد للمستخدم
    """
    # استخدام آخر 6 أرقام من user_id مع أحرف عشوائية
    base = str(user_id)[-6:] if len(str(user_id)) >= 6 else str(user_id).zfill(6)
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=2))
    code = f"REF{base}{random_part}"

    # التحقق من التكرار
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM users WHERE referral_code=?", (code,))
            if not c.fetchone():
                return code
            else:
                # إذا كان مكرراً، توليد آخر
                return generate_referral_code(user_id + 1)
    except:
        return code

@safe_execute
def get_user_referrals(user_id: int) -> List[Tuple]:
    """
    جلب إحالات المستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT r.referred_id, u.created_at, r.amount_charged, r.is_active,
                       (SELECT COALESCE(SUM(amount), 0) FROM transactions 
                        WHERE user_id = r.referred_id AND type = 'charge' AND status = 'approved') as total_charged
                FROM referrals r
                JOIN users u ON r.referred_id = u.user_id
                WHERE r.referrer_id = ?
                ORDER BY r.created_at DESC
            """, (user_id,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب إحالات المستخدم: {e}")
        return []

@safe_execute
def get_top_referrals(limit: int = 10) -> List[Tuple]:
    """
    جلب أعلى الإحالات
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT r.referrer_id, COUNT(*) as total_refs,
                       SUM(CASE WHEN r.amount_charged >= 10000 THEN 1 ELSE 0 END) as active_refs,
                       SUM(r.commission_earned) as total_commission,
                       (SELECT username FROM users WHERE user_id = r.referrer_id) as username
                FROM referrals r
                GROUP BY r.referrer_id
                ORDER BY total_refs DESC
                LIMIT ?
            """, (limit,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب أعلى الإحالات: {e}")
        return []

@safe_execute 
def calculate_referral_commissions() -> List[Tuple[int, int]]:
    """
    حساب عمولات الإحالات المستحقة للتوزيع
    """
    try:
        settings = get_referral_settings()
        if not settings:
            return []

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # النظام الأول: نسبة من الإحالات النشطة
            c.execute("""
                SELECT r.referrer_id, 
                       COUNT(*) as total_active,
                       SUM(r.amount_charged) as total_charged,
                       (SUM(r.amount_charged) * ? / 100) as commission
                FROM referrals r
                WHERE r.is_active = 1 
                AND r.amount_charged >= ?
                GROUP BY r.referrer_id
                HAVING COUNT(*) >= ?
            """, (settings['commission_rate'], 
                  settings['min_charge_amount'], 
                  settings['min_active_referrals']))

            system1_commissions = c.fetchall()

            # النظام الثاني: مكافأة ثابتة لكل إحالة نشطة
            c.execute("""
                SELECT referrer_id, 
                       COUNT(*) as eligible_refs,
                       (COUNT(*) * ?) as bonus
                FROM referrals 
                WHERE is_active = 1 
                AND amount_charged >= 10000
                GROUP BY referrer_id
            """, (settings['bonus_amount'],))

            system2_bonuses = c.fetchall()

            # دمج النتائج
            commissions = {}

            for ref_id, total_active, total_charged, commission in system1_commissions:
                if ref_id not in commissions:
                    commissions[ref_id] = 0
                commissions[ref_id] += commission

            for ref_id, eligible_refs, bonus in system2_bonuses:
                if ref_id not in commissions:
                    commissions[ref_id] = 0
                commissions[ref_id] += bonus

            # تحويل إلى قائمة
            result = [(ref_id, amount) for ref_id, amount in commissions.items() if amount > 0]
            return result

    except Exception as e:
        logger.error(f"❌ خطأ في حساب عمولات الإحالات: {e}")
        return []

@safe_execute
def distribute_referral_commissions() -> Dict[str, Any]:
    """
    توزيع عمولات الإحالات تلقائياً
    """
    try:
        commissions = calculate_referral_commissions()
        if not commissions:
            return {"success": False, "message": "⚠️ لا توجد عمولات مستحقة للتوزيع", "distributed": 0}

        total_distributed = 0
        distributed_users = []

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            for user_id, amount in commissions:
                # إضافة الرصيد للمستخدم
                old_balance = get_user_balance(user_id)
                new_balance = old_balance + int(amount)

                c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

                # تسجيل المعاملة
                c.execute("""
                    INSERT INTO transactions (user_id, type, amount, status, created_at, notes)
                    VALUES (?, 'referral', ?, 'completed', datetime('now'), ?)
                """, (user_id, int(amount), f"عمولة إحالة تلقائية"))

                total_distributed += int(amount)
                distributed_users.append((user_id, int(amount)))

                # إرسال إشعار للمستخدم
                try:
                    from bot_main import bot
                    bot.send_message(
                        user_id,
                        f"🎉 **تمت إضافة عمولة إحالة إلى رصيدك!**\n\n"
                        f"💰 المبلغ: {int(amount):,} ليرة\n"
                        f"💳 رصيدك الجديد: {new_balance:,} ليرة\n\n"
                        f"شكراً لدعمك لنظام الإحالات! 🤝"
                    )
                except:
                    pass

            conn.commit()

        logger.info(f"✅ تم توزيع عمولات الإحالات: {total_distributed:,} ليرة على {len(distributed_users)} مستخدم")
        return {
            "success": True,
            "message": f"✅ تم توزيع {total_distributed:,} ليرة على {len(distributed_users)} مستخدم",
            "distributed": total_distributed,
            "users": distributed_users
        }

    except Exception as e:
        logger.error(f"❌ خطأ في توزيع عمولات الإحالات: {e}")
        return {"success": False, "message": f"❌ خطأ في التوزيع: {str(e)[:100]}"}
# استمرار database.py

# =========================
# دوال نظام أكواد الهدايا
# =========================

@safe_execute
def generate_gift_code(amount: int, max_uses: int = 1, expires_days: int = 30, created_by: Optional[int] = None) -> Dict[str, Any]:
    """
    توليد كود هدية فريد
    """
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=8))

        # التحقق من التكرار
        try:
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM gift_codes WHERE code=?", (code,))
                if not c.fetchone():
                    # حساب تاريخ الانتهاء
                    expires_at = None
                    if expires_days > 0:
                        expires_at = (datetime.datetime.now() + 
                                    datetime.timedelta(days=expires_days)).strftime('%Y-%m-%d %H:%M:%S')

                    # حفظ الكود
                    c.execute("""
                        INSERT INTO gift_codes (code, amount, max_uses, created_by, expires_at, created_at)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """, (code, amount, max_uses, created_by, expires_at))
                    conn.commit()

                    return {"success": True, "code": code}
        except Exception as e:
            logger.error(f"❌ خطأ في توليد كود هدية: {e}")
            return {"success": False, "message": str(e)}

@safe_execute
def use_gift_code(code: str, user_id: int) -> Dict[str, Any]:
    """
    استخدام كود هدية
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # التحقق من صلاحية الكود
            c.execute("""
                SELECT amount, max_uses, used_count, expires_at 
                FROM gift_codes WHERE code=?
            """, (code,))
            row = c.fetchone()

            if not row:
                return {"success": False, "message": "❌ كود الهدية غير صحيح"}

            amount, max_uses, used_count, expires_at = row

            # التحقق من عدد الاستخدامات
            if used_count >= max_uses:
                return {"success": False, "message": "❌ هذا الكود مستخدم بالفعل"}

            # التحقق من الصلاحية الزمنية
            if expires_at and datetime.datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S') < datetime.datetime.now():
                return {"success": False, "message": "❌ انتهت صلاحية هذا الكود"}

            # التحقق إذا استخدمه المستخدم سابقاً
            c.execute("SELECT 1 FROM gift_code_usage WHERE code=? AND user_id=?", (code, user_id))
            if c.fetchone():
                return {"success": False, "message": "❌ لقد استخدمت هذا الكود مسبقاً"}

            # زيادة عداد الاستخدام
            c.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code,))

            # تسجيل الاستخدام
            c.execute("""
                INSERT INTO gift_code_usage (code, user_id, used_at)
                VALUES (?, ?, datetime('now'))
            """, (code, user_id))

            # إضافة الرصيد للمستخدم
            old_balance = get_user_balance(user_id)
            new_balance = old_balance + amount

            c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

            # تسجيل المعاملة
            c.execute("""
                INSERT INTO transactions (user_id, type, amount, status, created_at, notes)
                VALUES (?, 'bonus', ?, 'completed', datetime('now'), ?)
            """, (user_id, amount, f"كود هدية: {code}"))

            conn.commit()

            return {
                "success": True,
                "message": f"✅ تم تفعيل الكود بنجاح! تم إضافة {amount:,} ليرة إلى رصيدك",
                "amount": amount,
                "new_balance": new_balance
            }

    except Exception as e:
        logger.error(f"❌ خطأ في استخدام كود هدية: {e}")
        return {"success": False, "message": f"❌ خطأ في تفعيل الكود: {str(e)[:100]}"}

# =========================
# دوال نظام الإهداء
# =========================

@safe_execute
def send_gift(sender_id: int, receiver_id: int, amount: int) -> Dict[str, Any]:
    """
    إرسال هدية من مستخدم لآخر
    """
    try:
        # التحقق من وجود المستلم
        receiver = get_user(receiver_id)
        if not receiver:
            return {"success": False, "message": "❌ المستخدم غير موجود"}

        # التحقق من رصيد المرسل
        sender_balance = get_user_balance(sender_id)
        if sender_balance < amount:
            return {"success": False, "message": "❌ رصيدك غير كافي"}

        # التحقق من عدم إهداء النفس
        if sender_id == receiver_id:
            return {"success": False, "message": "❌ لا يمكن إهداء نفسك"}

        # تطبيق نسبة الإهداء إذا كانت مفعلة
        gift_percentage = int(get_setting('gift_percentage', 0))
        net_amount = amount

        if gift_percentage > 0:
            deduction = int(amount * gift_percentage / 100)
            net_amount = amount - deduction

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # خصم المبلغ من المرسل
            new_sender_balance = sender_balance - amount
            c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_sender_balance, sender_id))

            # إضافة المبلغ للمستلم (بعد خصم النسبة)
            receiver_balance = get_user_balance(receiver_id)
            new_receiver_balance = receiver_balance + net_amount
            c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_receiver_balance, receiver_id))

            # تسجيل عملية الإهداء
            c.execute("""
                INSERT INTO gift_transactions (sender_id, receiver_id, original_amount, 
                                              net_amount, gift_percentage, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (sender_id, receiver_id, amount, net_amount, gift_percentage))

            # تسجيل معاملات للمرسل والمستلم
            gift_id = c.lastrowid

            # للمرسل
            c.execute("""
                INSERT INTO transactions (user_id, type, amount, status, created_at, notes)
                VALUES (?, 'gift_sent', ?, 'completed', datetime('now'), ?)
            """, (sender_id, amount, f"إهداء للمستخدم {receiver_id}"))

            # للمستلم
            c.execute("""
                INSERT INTO transactions (user_id, type, amount, status, created_at, notes)
                VALUES (?, 'gift_received', ?, 'completed', datetime('now'), ?)
            """, (receiver_id, net_amount, f"هدية من المستخدم {sender_id}"))

            conn.commit()

        # إرسال إشعار للمستلم
        try:
            from bot_main import bot
            bot.send_message(
                receiver_id,
                f"🎁 **تلقيت هدية جديدة!**\n\n"
                f"👤 المرسل: {sender_id}\n"
                f"💰 المبلغ: {amount:,} ليرة\n"
                f"🎯 المستلم: {net_amount:,} ليرة (بعد خصم {gift_percentage}%)\n"
                f"💳 رصيدك الجديد: {new_receiver_balance:,} ليرة\n\n"
                f"شكراً لك! 🎉"
            )
        except:
            pass

        return {
            "success": True,
            "message": f"✅ تم إرسال الهدية بنجاح!\nالمستلم سيحصل على {net_amount:,} ليرة (بعد خصم {gift_percentage}%)",
            "net_amount": net_amount,
            "new_sender_balance": new_sender_balance
        }

    except Exception as e:
        logger.error(f"❌ خطأ في إرسال هدية: {e}")
        return {"success": False, "message": f"❌ خطأ في إرسال الهدية: {str(e)[:100]}"}

# =========================
# دوال المستخدمين الأساسية
# =========================

@safe_execute
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """
    جلب بيانات مستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users 
                SET last_active = datetime('now') 
                WHERE user_id = ?
            """, (user_id,))
            c.execute("""
                SELECT user_id, balance, created_at, last_active, referral_code, 
                       is_banned, ban_reason, ban_until 
                FROM users WHERE user_id=?
            """, (user_id,))
            result = c.fetchone()
            conn.commit()

            if result:
                return {
                    "user_id": result[0],
                    "balance": result[1],
                    "created_at": result[2],
                    "last_active": result[3],
                    "referral_code": result[4],
                    "is_banned": bool(result[5]),
                    "ban_reason": result[6],
                    "ban_until": result[7]
                }
            return None
    except Exception as e:
        logger.error(f"❌ خطأ في جلب بيانات المستخدم: {e}")
        return None

@safe_execute
def get_user_balance(user_id: int) -> int:
    """
    جلب رصيد المستخدم
    """
    user_data = get_user(user_id)
    return user_data['balance'] if user_data else 0

@safe_execute
def create_user(user_id: int) -> bool:
    """
    إنشاء مستخدم جديد
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # التحقق من وجود المستخدم
            c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
            if c.fetchone():
                return True

            # توليد كود إحالة
            referral_code = generate_referral_code(user_id)

            c.execute("""
                INSERT INTO users (user_id, balance, created_at, last_active, referral_code) 
                VALUES (?, 0, datetime('now'), datetime('now'), ?)
            """, (user_id, referral_code))
            conn.commit()

            return True
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء مستخدم: {e}")
        return False

@safe_execute
def add_balance(user_id: int, amount: int) -> Dict[str, int]:
    """
    إضافة رصيد للمستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
            old = row[0] if row else 0
            new = old + amount
            c.execute("UPDATE users SET balance=? WHERE user_id=?", (new, user_id))
            conn.commit()
            return {"old": old, "new": new}
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة رصيد: {e}")
        return {"old": 0, "new": 0}

@safe_execute
def subtract_balance(user_id: int, amount: int) -> Dict[str, int]:
    """
    خصم رصيد من المستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
            old = row[0] if row else 0
            new = max(0, old - amount)
            c.execute("UPDATE users SET balance=? WHERE user_id=?", (new, user_id))
            conn.commit()
            return {"old": old, "new": new}
    except Exception as e:
        logger.error(f"❌ خطأ في خصم رصيد: {e}")
        return {"old": 0, "new": 0}

@safe_execute
def get_all_users(limit: int = 1000, offset: int = 0) -> List[Tuple]:
    """
    جلب جميع المستخدمين
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT user_id, balance, created_at, last_active, is_banned
                FROM users 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب جميع المستخدمين: {e}")
        return []

@safe_execute
def get_top_users_by_balance(limit: int = 20) -> List[Tuple]:
    """
    جلب أعلى المستخدمين حسب الرصيد
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT user_id, balance, created_at, last_active
                FROM users 
                WHERE is_banned = 0
                ORDER BY balance DESC
                LIMIT ?
            """, (limit,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب أعلى المستخدمين: {e}")
        return []

@safe_execute
def get_top_users_by_deposit(limit: int = 10) -> List[Tuple]:
    """
    جلب أعلى المستخدمين حسب الإيداع
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT user_id, SUM(amount) as total_deposit
                FROM transactions 
                WHERE type = 'charge' AND status = 'approved'
                GROUP BY user_id
                ORDER BY total_deposit DESC
                LIMIT ?
            """, (limit,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب أعلى المودعين: {e}")
        return []

@safe_execute
def get_user_transactions(user_id: int, limit: int = 50, offset: int = 0) -> List[Tuple]:
    """
    جلب معاملات المستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, type, amount, payment_method, status, created_at, notes
                FROM transactions 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            return c.fetchall()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب معاملات المستخدم: {e}")
        return []

@safe_execute
def ban_user(user_id: int, reason: str = "", ban_until: Optional[str] = None, admin_id: int = ADMIN_ID) -> bool:
    """
    حظر مستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users 
                SET is_banned = 1, ban_reason = ?, ban_until = ?
                WHERE user_id = ?
            """, (reason, ban_until, user_id))
            conn.commit()

        logger.info(f"✅ تم حظر المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حظر المستخدم: {e}")
        return False

@safe_execute
def unban_user(user_id: int) -> bool:
    """
    فك حظر مستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users 
                SET is_banned = 0, ban_reason = NULL, ban_until = NULL
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()

        logger.info(f"✅ تم فك حظر المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في فك حظر المستخدم: {e}")
        return False

@safe_execute
def delete_user(user_id: int) -> bool:
    """
    حذف مستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # حذف جميع بيانات المستخدم
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM ichancy_accounts WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()

        cache.delete(f"admin_{user_id}")
        logger.info(f"✅ تم حذف المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حذف المستخدم: {e}")
        return False

@safe_execute
def reset_all_balances() -> Dict[str, Any]:
    """
    تصفير جميع أرصدة المستخدمين
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET balance = 0 WHERE is_banned = 0")
            affected = c.rowcount
            conn.commit()

        logger.info(f"✅ تم تصفير أرصدة {affected} مستخدم")
        return {"success": True, "affected": affected}
    except Exception as e:
        logger.error(f"❌ خطأ في تصفير الأرصدة: {e}")
        return {"success": False, "message": str(e)}

# =========================
# دوال نظام الجلسات
# =========================

@safe_execute
def set_session(user_id: int, step: str, temp_data: Optional[Dict] = None, ttl_minutes: int = 30) -> bool:
    """
    حفظ جلسة مستخدم
    """
    try:
        json_data = json.dumps(temp_data, ensure_ascii=False) if temp_data is not None else None
        expires_at = (datetime.datetime.now() + 
                     datetime.timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO sessions (user_id, step, temp_data, expires_at, created_at) 
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (user_id, step, json_data, expires_at))
            conn.commit()
        return True

    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الجلسة: {e}")
        return False

@safe_execute
def get_session(user_id: int) -> Optional[Dict[str, Any]]:
    """
    جلب جلسة مستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
            c.execute("SELECT step, temp_data, expires_at FROM sessions WHERE user_id=?", (user_id,))
            row = c.fetchone()
            conn.commit()

            if row:
                temp_data = None
                if row[1]:
                    try:
                        temp_data = json.loads(row[1])
                    except json.JSONDecodeError:
                        temp_data = row[1]

                return {
                    "step": row[0],
                    "temp_data": temp_data,
                    "expires_at": row[2]
                }
        return None

    except Exception as e:
        logger.error(f"❌ خطأ في جلب الجلسة: {e}")
        return None

@safe_execute
def clear_session(user_id: int) -> bool:
    """
    مسح جلسة مستخدم
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في مسح الجلسة: {e}")
        return False

# =========================
# دوال نظام التقارير والإحصائيات
# =========================

@safe_execute
def get_daily_report(date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    جلب التقرير اليومي
    """
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # إحصائيات المستخدمين
            c.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = ?", (date_str,))
            new_users = c.fetchone()[0] or 0

            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0] or 0

            c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM transactions 
                WHERE date(created_at) = ?
            """, (date_str,))
            active_users = c.fetchone()[0] or 0

            # إحصائيات مالية
            c.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE type = 'charge' AND status = 'approved' AND date(created_at) = ?
            """, (date_str,))
            total_deposit = c.fetchone()[0] or 0

            c.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE type = 'withdraw' AND status = 'approved' AND date(created_at) = ?
            """, (date_str,))
            total_withdraw = c.fetchone()[0] or 0

            c.execute("SELECT COUNT(*) FROM transactions WHERE date(created_at) = ?", (date_str,))
            total_transactions = c.fetchone()[0] or 0

            c.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending' AND date(created_at) = ?", (date_str,))
            pending_transactions = c.fetchone()[0] or 0

            # إحصائيات الإحالات
            c.execute("SELECT COUNT(*) FROM referrals WHERE date(created_at) = ?", (date_str,))
            new_referrals = c.fetchone()[0] or 0

            # إحصائيات الأكواد
            c.execute("SELECT COUNT(*) FROM syriatel_codes WHERE is_active = 1")
            active_codes = c.fetchone()[0] or 0

            c.execute("SELECT SUM(current_amount) FROM syriatel_codes WHERE is_active = 1")
            used_capacity = c.fetchone()[0] or 0

            total_capacity = active_codes * CODE_CAPACITY
            fill_percentage = round((used_capacity / total_capacity * 100), 2) if total_capacity > 0 else 0

            return {
                "date": date_str,
                "new_users": new_users,
                "total_users": total_users,
                "active_users": active_users,
                "total_deposit": total_deposit,
                "total_withdraw": total_withdraw,
                "total_transactions": total_transactions,
                "pending_transactions": pending_transactions,
                "new_referrals": new_referrals,
                "active_codes": active_codes,
                "used_capacity": used_capacity,
                "total_capacity": total_capacity,
                "fill_percentage": fill_percentage,
                "net_flow": total_deposit - total_withdraw
            }

    except Exception as e:
        logger.error(f"❌ خطأ في جلب التقرير اليومي: {e}")
        return None

@safe_execute
def get_deposit_report(payment_method: Optional[str] = None, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    جلب تقرير الشحن
    """
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            query = """
                SELECT t.id, t.user_id, t.amount, t.payment_method, t.created_at, t.status,
                       u.balance as user_balance
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.type = 'charge' AND date(t.created_at) = ?
            """
            params = [date_str]

            if payment_method:
                query += " AND t.payment_method = ?"
                params.append(payment_method)

            query += " ORDER BY t.created_at DESC"

            c.execute(query, params)
            transactions = c.fetchall()

            # حساب الإجماليات
            total_query = """
                SELECT COALESCE(SUM(amount), 0), COUNT(*)
                FROM transactions 
                WHERE type = 'charge' AND date(created_at) = ?
            """
            total_params = [date_str]

            if payment_method:
                total_query += " AND payment_method = ?"
                total_params.append(payment_method)

            c.execute(total_query, total_params)
            total_amount, total_count = c.fetchone()

            return {
                "transactions": transactions,
                "total_amount": total_amount or 0,
                "total_count": total_count or 0,
                "payment_method": payment_method or "جميع الطرق",
                "date": date_str
            }

    except Exception as e:
        logger.error(f"❌ خطأ في جلب تقرير الشحن: {e}")
        return None

@safe_execute
def get_withdraw_report(date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    جلب تقرير السحب
    """
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            c.execute("""
                SELECT t.id, t.user_id, t.amount, t.payment_method, t.created_at, t.status,
                       u.balance as user_balance
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.type = 'withdraw' AND date(t.created_at) = ?
                ORDER BY t.created_at DESC
            """, (date_str,))
            transactions = c.fetchall()

            c.execute("""
                SELECT COALESCE(SUM(amount), 0), COUNT(*)
                FROM transactions 
                WHERE type = 'withdraw' AND date(created_at) = ?
            """, (date_str,))
            total_amount, total_count = c.fetchone()

            return {
                "transactions": transactions,
                "total_amount": total_amount or 0,
                "total_count": total_count or 0,
                "date": date_str
            }

    except Exception as e:
        logger.error(f"❌ خطأ في جلب تقرير السحب: {e}")
        return None

# =========================
# دوال إدارة الرسائل والإشعارات
# =========================

@safe_execute
def send_message_to_user(user_id: int, message: str, admin_id: int = ADMIN_ID) -> bool:
    """
    إرسال رسالة لمستخدم
    """
    try:
        from bot_main import bot
        bot.send_message(user_id, message)

        # تسجيل في قاعدة البيانات
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO broadcast_messages (admin_id, message_text, message_type, sent_count, created_at)
                VALUES (?, ?, 'text', 1, datetime('now'))
            """, (admin_id, message))
            conn.commit()

        return True
    except Exception as e:
        logger.error(f"❌ فشل إرسال رسالة للمستخدم {user_id}: {e}")
        return False

@safe_execute
def send_photo_to_user(user_id: int, photo_file_id: str, caption: str = "", admin_id: int = ADMIN_ID) -> bool:
    """
    إرسال صورة لمستخدم
    """
    try:
        from bot_main import bot
        bot.send_photo(user_id, photo_file_id, caption=caption)

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO broadcast_messages (admin_id, message_text, message_type, file_id, sent_count, created_at)
                VALUES (?, ?, 'photo', ?, 1, datetime('now'))
            """, (admin_id, caption, photo_file_id))
            conn.commit()

        return True
    except Exception as e:
        logger.error(f"❌ فشل إرسال صورة للمستخدم {user_id}: {e}")
        return False

@safe_execute
def broadcast_message(message: str, message_type: str = 'text', file_id: Optional[str] = None) -> Dict[str, Any]:
    """
    بث رسالة لجميع المستخدمين
    """
    try:
        sent_count = 0
        failed_count = 0

        # جلب جميع المستخدمين غير المحظورين
        users = get_all_users(limit=10000)

        for user in users:
            user_id = user[0]
            is_banned = user[4]

            if is_banned:
                continue

            try:
                from bot_main import bot
                if message_type == 'text':
                    bot.send_message(user_id, message)
                elif message_type == 'photo' and file_id:
                    bot.send_photo(user_id, file_id, caption=message)

                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"⚠️ فشل إرسال للمستخدم {user_id}: {e}")

        # تسجيل النتيجة
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO broadcast_messages (admin_id, message_text, message_type, file_id, sent_count, failed_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (ADMIN_ID, message, message_type, file_id, sent_count, failed_count))
            conn.commit()

        return {
            "success": True,
            "sent": sent_count,
            "failed": failed_count,
            "total": sent_count + failed_count
        }

    except Exception as e:
        logger.error(f"❌ خطأ في البث للجميع: {e}")
        return {"success": False, "message": str(e)}

# =========================
# دوال نظام الأكواد والحدود
# =========================

@safe_execute
def get_available_code_for_amount(amount: int) -> Dict[str, Any]:
    """
    البحث عن كود سيرياتيل يمكنه استيعاب المبلغ
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # البحث عن كود يمكنه استيعاب المبلغ
            c.execute("""
                SELECT id, code_number, current_amount 
                FROM syriatel_codes 
                WHERE is_active = 1 
                AND (current_amount + ?) <= 5400
                ORDER BY current_amount ASC
                LIMIT 1
            """, (amount,))
            
            row = c.fetchone()
            
            if row:
                return {
                    "success": True,
                    "code_id": row[0],
                    "code_number": row[1],
                    "current_amount": row[2],
                    "max_available": 5400 - row[2]
                }
            else:
                # إذا لم يوجد كود، البحث عن أكبر مساحة متوفرة
                c.execute("""
                    SELECT MAX(5400 - current_amount) as max_space
                    FROM syriatel_codes 
                    WHERE is_active = 1
                """)
                
                max_space = c.fetchone()[0] or 0
                
                return {
                    "success": False,
                    "message": "لا يوجد كود متاح",
                    "max_available": max_space
                }
                
    except Exception as e:
        logger.error(f"❌ خطأ في البحث عن كود: {e}")
        return {"success": False, "message": str(e)}

@safe_execute  
def fill_code_with_amount(code_id: int, user_id: int, amount: int) -> Dict[str, Any]:
    """
    تعبئة كود سيرياتيل بمبلغ
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # التحقق من سعة الكود
            c.execute("SELECT current_amount FROM syriatel_codes WHERE id=?", (code_id,))
            current_amount = c.fetchone()[0]
            
            if current_amount + amount > 5400:
                return {
                    "success": False,
                    "message": f"❌ الكود لا يمكنه استيعاب {amount:,} ليرة. المساحة المتبقية: {5400 - current_amount:,} ليرة"
                }
            
            # تحديث الكود
            c.execute("""
                UPDATE syriatel_codes 
                SET current_amount = current_amount + ?, 
                    last_used = datetime('now'),
                    usage_count = usage_count + 1
                WHERE id = ?
            """, (amount, code_id))
            
            # تسجيل في السجل
            remaining = 5400 - (current_amount + amount)
            c.execute("""
                INSERT INTO code_fill_logs (code_id, user_id, amount, remaining_in_code, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (code_id, user_id, amount, remaining))
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"✅ تم تعبئة الكود بمبلغ {amount:,} ليرة",
                "remaining": remaining
            }
            
    except Exception as e:
        logger.error(f"❌ خطأ في تعبئة الكود: {e}")
        return {"success": False, "message": str(e)}

@safe_execute
def add_transaction(user_id: int, type_: str, amount: int, payment_method: str, 
                   transaction_id: str, account_number: str = "") -> Tuple[int, int, str]:
    """
    إضافة معاملة جديدة
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            # الحصول على الرقم الشهري
            now = datetime.datetime.now()
            month, year = now.month, now.year
            
            c.execute("""
                SELECT counter FROM monthly_counter 
                WHERE month = ? AND year = ? AND payment_method = ?
            """, (month, year, payment_method))
            
            row = c.fetchone()
            
            if row:
                order_number = row[0]
                c.execute("""
                    UPDATE monthly_counter 
                    SET counter = counter + 1 
                    WHERE month = ? AND year = ? AND payment_method = ?
                """, (month, year, payment_method))
            else:
                order_number = 1
                c.execute("""
                    INSERT INTO monthly_counter (month, year, payment_method, counter)
                    VALUES (?, ?, ?, 1)
                """, (month, year, payment_method))
            
            # إضافة المعاملة
            c.execute("""
                INSERT INTO transactions 
                (user_id, type, amount, payment_method, transaction_id, account_number, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
            """, (user_id, type_, amount, payment_method, transaction_id, account_number))
            
            tx_id = c.lastrowid
            conn.commit()
            
            return tx_id, order_number, now.strftime("%Y-%m-%d %H:%M:%S")
            
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة المعاملة: {e}")
        return 0, 0, ""

@safe_execute
def get_payment_settings(payment_method: str) -> Optional[Dict[str, Any]]:
    """
    جلب إعدادات طريقة دفع
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT payment_method, is_visible, is_active, pause_message
                FROM payment_settings 
                WHERE payment_method = ?
            """, (payment_method,))
            
            row = c.fetchone()
            
            if row:
                return {
                    "payment_method": row[0],
                    "is_visible": bool(row[1]),
                    "is_active": bool(row[2]),
                    "pause_message": row[3]
                }
            return None
            
    except Exception as e:
        logger.error(f"❌ خطأ في جلب إعدادات الدفع: {e}")
        return None

@safe_execute
def update_payment_settings(payment_method: str, is_visible: Optional[bool] = None, 
                           is_active: Optional[bool] = None, pause_message: Optional[str] = None, 
                           admin_id: int = ADMIN_ID) -> bool:
    """
    تحديث إعدادات طريقة دفع
    """
    try:
        updates = []
        params = []
        
        if is_visible is not None:
            updates.append("is_visible = ?")
            params.append(1 if is_visible else 0)
            
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
            
        if pause_message is not None:
            updates.append("pause_message = ?")
            params.append(pause_message)
            
        if updates:
            updates.append("updated_at = datetime('now')")
            updates.append("updated_by = ?")
            params.append(admin_id)
            params.append(payment_method)
            
            query = f"UPDATE payment_settings SET {', '.join(updates)} WHERE payment_method = ?"
            
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute(query, params)
                conn.commit()
                
            logger.info(f"✅ تم تحديث إعدادات الدفع: {payment_method}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث إعدادات الدفع: {e}")
        return False

@safe_execute
def get_payment_limits(payment_method: str) -> Optional[Dict[str, Any]]:
    """
    جلب حدود طريقة دفع
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT payment_method, min_amount, max_amount
                FROM payment_limits 
                WHERE payment_method = ?
            """, (payment_method,))
            
            row = c.fetchone()
            
            if row:
                return {
                    "payment_method": row[0],
                    "min_amount": row[1],
                    "max_amount": row[2]
                }
            return None
            
    except Exception as e:
        logger.error(f"❌ خطأ في جلب حدود الدفع: {e}")
        return None

@safe_execute
def send_urgent_notification(user_id: int, amount: int, max_available: int):
    """
    إرسال إشعار عاجل للأدمن
    """
    try:
        message = f"🚨 **إشعار عاجل!**\n\n"
        message += f"👤 المستخدم `{user_id}` حاول شحن {amount:,} ليرة\n"
        message += f"⚠️ أكبر كود متاح: {max_available:,} ليرة\n"
        message += f"🕒 الوقت: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # إرسال للقناة
        from bot_main import bot
        bot.send_message(CHANNEL_URGENT_REQUESTS, message, parse_mode="Markdown")
        
        # تسجيل في قاعدة البيانات
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO urgent_notifications (user_id, amount, max_available, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (user_id, amount, max_available))
            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال إشعار عاجل: {e}")

@safe_execute
def get_exchange_rate() -> int:
    """
    جلب سعر صرف الدولار
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT rate FROM exchange_rates ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            
            if row:
                return row[0]
            
            # القيمة الافتراضية
            c.execute("INSERT INTO exchange_rates (rate, changed_at) VALUES (?, datetime('now'))", (15000,))
            conn.commit()
            return 15000
            
    except Exception as e:
        logger.error(f"❌ خطأ في جلب سعر الصرف: {e}")
        return 15000