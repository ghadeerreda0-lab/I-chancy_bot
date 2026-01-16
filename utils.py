"""
utils.py - دوال مساعدة ومولدات
"""

import time
import hashlib
import string
import random
import datetime
import json
import logging
import traceback
from typing import Dict, Any, Optional
from threading import Lock

from telebot import TeleBot
from config import (
    TOKEN, ADMIN_ID, CHANNEL_ERROR_LOGS, 
    CHANNEL_ADMIN_LOGS, LOG_FILE
)

logger = logging.getLogger(__name__)

# =========================
# ذاكرة التخزين المؤقت مع TTL
# =========================

class CacheWithTTL:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = Lock()

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time() + ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                if time.time() < self._timestamps.get(key, 0):
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._timestamps[key]
            return None

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

# =========================
# ديكوراتور معالجة الأخطاء
# =========================

def safe_execute(func):
    """
    ديكوراتور لمعالجة الأخطاء وتسجيلها
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"❌ خطأ في {func.__name__}: {str(e)[:200]}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            try:
                bot = TeleBot(TOKEN)
                bot.send_message(
                    CHANNEL_ERROR_LOGS,
                    f"🚨 **خطأ في النظام**\n\n"
                    f"📍 الدالة: `{func.__name__}`\n"
                    f"💻 الخطأ: `{str(e)[:100]}`\n"
                    f"🕒 الوقت: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"🔧 **التفاصيل:**\n```\n{traceback.format_exc()[:500]}\n```",
                    parse_mode="Markdown"
                )
            except Exception as notify_error:
                logger.error(f"❌ فشل إرسال إشعار الخطأ: {notify_error}")
            try:
                if ADMIN_ID:
                    bot = TeleBot(TOKEN)
                    bot.send_message(ADMIN_ID, f"⚠️ خطأ في البوت:\n{func.__name__}: {str(e)[:100]}")
            except:
                pass
            return None
    return wrapper

# =========================
# مولدات عامة
# =========================

def generate_random_string(length: int = 8, use_digits: bool = True, use_letters: bool = True) -> str:
    """
    توليد سلسلة عشوائية
    """
    chars = ''
    if use_digits:
        chars += string.digits
    if use_letters:
        chars += string.ascii_uppercase
    
    if not chars:
        chars = string.ascii_uppercase + string.digits
    
    return ''.join(random.choices(chars, k=length))

def generate_hash(text: str, algorithm: str = 'sha256') -> str:
    """
    توليد هاش للنص
    """
    hasher = hashlib.new(algorithm)
    hasher.update(text.encode('utf-8'))
    return hasher.hexdigest()

def format_currency(amount: int, currency: str = "ليرة") -> str:
    """
    تنسيق المبلغ مع فواصل
    """
    return f"{amount:,} {currency}"

def format_date(date_str: str, format_from: str = "%Y-%m-%d %H:%M:%S", 
                format_to: str = "%Y-%m-%d %H:%M") -> str:
    """
    تنسيق التاريخ
    """
    try:
        date_obj = datetime.datetime.strptime(date_str, format_from)
        return date_obj.strftime(format_to)
    except:
        return date_str

def parse_date(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime.datetime]:
    """
    تحليل تاريخ من سلسلة نصية
    """
    try:
        return datetime.datetime.strptime(date_str, format_str)
    except:
        return None

# =========================
# دوال التحقق
# =========================

def is_valid_amount(amount_str: str, allow_float: bool = False) -> bool:
    """
    التحقق من صحة المبلغ
    """
    try:
        if allow_float:
            amount = float(amount_str)
            return amount > 0
        else:
            amount = int(amount_str)
            return amount > 0
    except:
        return False

def is_valid_user_id(user_id_str: str) -> bool:
    """
    التحقق من صحة ID المستخدم
    """
    try:
        user_id = int(user_id_str)
        return user_id > 0
    except:
        return False

def sanitize_input(text: str) -> str:
    """
    تنظيف النص المدخل من الأحرف الخطرة
    """
    import re
    # إزالة الأحرف الخاصة الخطيرة مع الاحتفاظ بالعربية والإنجليزية والأرقام
    return re.sub(r'[^\w\s\-@\.\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', '', str(text))

# =========================
# نظام Rate Limiting
# =========================

class RateLimiter:
    def __init__(self):
        self.requests = {}
        self.lock = Lock()

    def is_allowed(self, user_id: int, limit: int = 10, window: int = 60) -> bool:
        """
        التحقق إذا كان المستخدم يمكنه إرسال طلب
        """
        with self.lock:
            now = time.time()

            if user_id == ADMIN_ID:
                return True

            if user_id not in self.requests:
                self.requests[user_id] = []

            # إزالة الطلبات القديمة
            self.requests[user_id] = [req_time for req_time in self.requests[user_id] 
                                     if now - req_time < window]

            if len(self.requests[user_id]) >= limit:
                return False

            self.requests[user_id].append(now)
            return True

    def get_remaining_time(self, user_id: int, window: int = 60) -> int:
        """
        الحصول على الوقت المتبقي للسماح بالطلب التالي
        """
        with self.lock:
            if user_id not in self.requests:
                return 0

            now = time.time()
            self.requests[user_id] = [req_time for req_time in self.requests[user_id] 
                                     if now - req_time < window]

            if len(self.requests[user_id]) >= 10:
                oldest_request = min(self.requests[user_id])
                remaining = window - (now - oldest_request)
                return max(0, int(remaining))
            return 0

    def clear_user(self, user_id: int) -> None:
        """
        مسح طلبات مستخدم
        """
        with self.lock:
            if user_id in self.requests:
                del self.requests[user_id]

# =========================
# ديكوراتور Rate Limiting
# =========================

def rate_limit(limit: int = 10, window: int = 60):
    """
    ديكوراتور لتحديد معدل الطلبات
    """
    rate_limiter = RateLimiter()
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_id = None

            # استخراج user_id من الوسائط
            for arg in args:
                if hasattr(arg, 'from_user'):
                    user_id = arg.from_user.id
                    break
                elif hasattr(arg, 'message') and hasattr(arg.message, 'from_user'):
                    user_id = arg.message.from_user.id
                    break
                elif hasattr(arg, 'chat') and hasattr(arg.chat, 'id'):
                    user_id = arg.chat.id
                    break

            if user_id and not rate_limiter.is_allowed(user_id, limit, window):
                remaining = rate_limiter.get_remaining_time(user_id, window)
                if remaining > 0:
                    try:
                        # حاول إرسال رسالة للمستخدم
                        from bot_main import bot
                        for arg in args:
                            if hasattr(arg, 'answer_callback_query'):
                                arg.answer_callback_query(
                                    f"⏳ كثير طلبات! حاول بعد {remaining} ثانية",
                                    show_alert=True
                                )
                                break
                            elif hasattr(arg, 'reply_to'):
                                arg.reply_to(
                                    arg,
                                    f"⏳ كثير طلبات! حاول بعد {remaining} ثانية"
                                )
                                break
                        else:
                            # إذا لم نجد طريقة للإجابة، أرسل رسالة مباشرة
                            bot.send_message(user_id, f"⏳ كثير طلبات! حاول بعد {remaining} ثانية")
                    except:
                        pass
                    return None
            return func(*args, **kwargs)
        return wrapper
    return decorator

# =========================
# دوال الرسائل والتنسيق
# =========================

def create_welcome_message(user_id: int, balance: int) -> str:
    """
    إنشاء رسالة ترحيب
    """
    welcome_template = get_setting('welcome_message') or "👋 أهلاً بك!\nرصيدك الحالي: {balance} ليرة سورية"
    try:
        return welcome_template.format(balance=format_currency(balance))
    except:
        return f"👋 أهلاً بك!\nرصيدك الحالي: {format_currency(balance)}"

def create_ichancy_welcome_message() -> str:
    """
    إنشاء رسالة ترحيب Ichancy
    """
    return get_setting('ichancy_welcome_message') or "⚡ مرحباً بك في نظام Ichancy!"

def format_transaction_message(transaction: tuple) -> str:
    """
    تنسيق رسالة المعاملة
    """
    tx_id, tx_type, amount, method, status, created_at, notes = transaction
    
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        'completed': '✅'
    }
    
    type_names = {
        'charge': 'شحن',
        'withdraw': 'سحب',
        'gift_sent': 'إهداء مرسل',
        'gift_received': 'إهداء مستلم',
        'referral': 'عمولة إحالة',
        'bonus': 'بونص'
    }
    
    icon = status_icons.get(status, '❓')
    type_name = type_names.get(tx_type, tx_type)
    
    message = f"{icon} **{format_date(created_at)}**\n"
    message += f"📋 النوع: {type_name}\n"
    message += f"💰 المبلغ: {format_currency(amount)}\n"
    
    if method:
        message += f"📱 الطريقة: {method}\n"
    
    message += f"🆔 العملية: #{tx_id}\n"
    
    if notes:
        message += f"📝 الملاحظات: {notes}\n"
    
    return message

# =========================
# دوال النسخ الاحتياطي
# =========================

def create_backup() -> Dict[str, Any]:
    """
    إنشاء نسخة احتياطية
    """
    import os
    import shutil
    from config import DB_PATH
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = "backups"
        
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        backup_path = os.path.join(backup_dir, f"bot_backup_{timestamp}.sqlite")
        shutil.copy2(DB_PATH, backup_path)
        
        file_size = os.path.getsize(backup_path)
        
        return {
            "success": True,
            "path": backup_path,
            "size": file_size,
            "timestamp": timestamp
        }
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        return {"success": False, "error": str(e)}

def cleanup_old_backups(max_backups: int = 10):
    """
    تنظيف النسخ الاحتياطية القديمة
    """
    import os
    import glob
    
    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            return
        
        backups = glob.glob(os.path.join(backup_dir, "bot_backup_*.sqlite"))
        backups.sort(key=os.path.getmtime, reverse=True)
        
        if len(backups) > max_backups:
            for backup in backups[max_backups:]:
                try:
                    os.remove(backup)
                    logger.info(f"✅ تم حذف نسخة احتياطية قديمة: {backup}")
                except Exception as e:
                    logger.error(f"❌ خطأ في حذف نسخة احتياطية: {e}")
                    
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف النسخ الاحتياطية: {e}")

# =========================
# دوال المساعدة للنظام
# =========================

def get_setting(key: str, default: Any = None) -> Any:
    """
    دالة مساعدة لجلب الإعدادات (لتجنب الاستيراد الدائري)
    """
    try:
        from database import get_setting as db_get_setting
        return db_get_setting(key, default)
    except:
        return default

def is_admin(user_id: int) -> bool:
    """
    دالة مساعدة للتحقق من الأدمن (لتجنب الاستيراد الدائري)
    """
    try:
        from database import is_admin as db_is_admin
        return db_is_admin(user_id)
    except:
        return user_id == ADMIN_ID

def can_manage_admins(user_id: int) -> bool:
    """
    دالة مساعدة للتحقق من صلاحية إدارة الأدمن
    """
    try:
        from database import can_manage_admins as db_can_manage
        return db_can_manage(user_id)
    except:
        return user_id == ADMIN_ID

def check_maintenance(user_id: int) -> bool:
    """
    التحقق من وضع الصيانة
    """
    try:
        if get_setting('maintenance_mode') == 'true' and not is_admin(user_id):
            message = get_setting('maintenance_message') or '🔧 البوت تحت الصيانة حاليًا.'
            from bot_main import bot
            bot.send_message(user_id, message)
            return True
        return False
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من الصيانة: {e}")
        return False

def check_payment_enabled(user_id: int, payment_method: str) -> bool:
    """
    التحقق من تفعيل طريقة الدفع
    """
    try:
        from database import get_payment_settings
        settings = get_payment_settings(payment_method)
        if not settings:
            return False

        if not settings['is_visible']:
            return False

        if not settings['is_active']:
            from bot_main import bot
            bot.send_message(user_id, settings['pause_message'])
            return False

        return True
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من الدفع: {e}")
        return False

def check_withdraw_enabled(user_id: int) -> bool:
    """
    التحقق من تفعيل السحب
    """
    try:
        if get_setting('withdraw_enabled') != 'true':
            from bot_main import bot
            bot.send_message(user_id, get_setting('withdraw_message', '💸 نظام السحب معطل حالياً'))
            return False
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من السحب: {e}")
        return False

def check_ichancy_enabled(user_id: int, feature: Optional[str] = None) -> bool:
    """
    التحقق من تفعيل Ichancy
    """
    try:
        if get_setting('ichancy_enabled') != 'true':
            from bot_main import bot
            bot.send_message(user_id, get_setting('ichancy_welcome_message', '⚡ نظام Ichancy معطل حالياً'))
            return False

        if feature == 'create' and get_setting('ichancy_create_account_enabled') != 'true':
            from bot_main import bot
            bot.send_message(user_id, "❌ إنشاء حسابات Ichancy معطل حالياً")
            return False

        if feature == 'deposit' and get_setting('ichancy_deposit_enabled') != 'true':
            from bot_main import bot
            bot.send_message(user_id, "❌ شحن رصيد في Ichancy معطل حالياً")
            return False

        if feature == 'withdraw' and get_setting('ichancy_withdraw_enabled') != 'true':
            from bot_main import bot
            bot.send_message(user_id, "❌ سحب رصيد من Ichancy معطل حالياً")
            return False

        return True
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من Ichancy: {e}")
        return False