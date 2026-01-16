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