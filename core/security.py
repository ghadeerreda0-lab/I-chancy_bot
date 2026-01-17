"""
نظام الأمان والتشفير المتقدم
"""

import hashlib
import secrets
import string
import time
from typing import Optional, Tuple
import bcrypt
from cryptography.fernet import Fernet
import base64
import os

from .config import SECRET_KEY
from .logger import get_logger

logger = get_logger(__name__)


class PasswordManager:
    """مدير كلمات المرور مع تشفير قوي"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """تشفير كلمة المرور باستخدام bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    
    @staticmethod
    def verify_password(hashed_password: str, password: str) -> bool:
        """التحقق من كلمة المرور"""
        try:
            return bcrypt.checkpw(password.encode(), hashed_password.encode())
        except Exception as e:
            logger.error(f"خطأ في التحقق من كلمة المرور: {e}")
            return False
    
    @staticmethod
    def generate_strong_password(length: int = 12) -> str:
        """توليد كلمة مرور قوية"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        
        # التأكد من وجود حرف كبير، صغير، رقم، ورمز
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*")
        ]
        
        # إكمال الباقي
        password += [secrets.choice(characters) for _ in range(length - 4)]
        
        # خلط الأحرف
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)


class EncryptionManager:
    """مدير التشفير للنصوص الحساسة"""
    
    def __init__(self):
        # توليد مفتاح من SECRET_KEY
        key = hashlib.sha256(SECRET_KEY.encode()).digest()
        self.key = base64.urlsafe_b64encode(key)
        self.cipher = Fernet(self.key)
    
    def encrypt(self, text: str) -> str:
        """تشفير نص"""
        try:
            encrypted = self.cipher.encrypt(text.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"خطأ في التشفير: {e}")
            return text
    
    def decrypt(self, encrypted_text: str) -> Optional[str]:
        """فك تشفير نص"""
        try:
            decrypted = self.cipher.decrypt(encrypted_text.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"خطأ في فك التشفير: {e}")
            return None


class RateLimiter:
    """محدد المعدل لمنع الإساءة"""
    
    def __init__(self, max_requests: int = 10, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests = {}
        self.lock = threading.Lock()
        logger.info(f"تم تهيئة RateLimiter: {max_requests} طلب في {window} ثانية")
    
    def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """التحقق إذا كان المستخدم مسموح له"""
        with self.lock:
            now = time.time()
            
            # تجاهل المشرف الرئيسي
            from .config import ADMIN_ID
            if user_id == ADMIN_ID:
                return True, 0
            
            if user_id not in self.requests:
                self.requests[user_id] = []
            
            # تنظيف الطلبات القديمة
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id]
                if now - req_time < self.window
            ]
            
            # التحقق من الحد
            if len(self.requests[user_id]) >= self.max_requests:
                # حساب الوقت المتبقي
                oldest_request = min(self.requests[user_id])
                remaining = self.window - (now - oldest_request)
                return False, int(remaining)
            
            # تسجيل الطلب الجديد
            self.requests[user_id].append(now)
            return True, 0
    
    def cleanup_old_requests(self):
        """تنظيف الطلبات القديمة"""
        with self.lock:
            now = time.time()
            cleaned_count = 0
            
            for user_id in list(self.requests.keys()):
                self.requests[user_id] = [
                    req_time for req_time in self.requests[user_id]
                    if now - req_time < self.window * 2  # ضعف النافذة للتنظيف
                ]
                
                if not self.requests[user_id]:
                    del self.requests[user_id]
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.debug(f"تم تنظيف {cleaned_count} مستخدم من RateLimiter")


class InputValidator:
    """مدقق الإدخال لمنع الهجمات"""
    
    @staticmethod
    def validate_user_id(user_id: str) -> Optional[int]:
        """التحقق من صحة ID المستخدم"""
        try:
            uid = int(user_id)
            if uid > 0 and len(str(uid)) <= 20:
                return uid
            return None
        except ValueError:
            return None
    
    @staticmethod
    def validate_amount(amount: str, min_val: int = 1, max_val: int = 1000000) -> Optional[int]:
        """التحقق من صحة المبلغ"""
        try:
            amt = int(amount)
            if min_val <= amt <= max_val:
                return amt
            return None
        except ValueError:
            return None
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """التحقق من صحة اسم المستخدم"""
        if not username:
            return False
        
        # الطول
        if len(username) < 3 or len(username) > 20:
            return False
        
        # الأحور المسموحة
        allowed_chars = string.ascii_letters + string.digits + "_-."
        if any(char not in allowed_chars for char in username):
            return False
        
        return True
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """تنظيف النص من الأحرف الخطرة"""
        # إزالة الأحرف الخاصة الخطرة مع الحفاظ على العربية
        safe_chars = string.ascii_letters + string.digits + " \n\r\t.,!?@#$%^&*()-_=+[]{}|;:'\"<>/~`"
        arabic_chars = "ابتثجحخدذرزسشصضطظعغفقكلمنهويءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهويى"
        
        allowed_chars = safe_chars + arabic_chars
        return ''.join(char for char in text if char in allowed_chars)


class TokenGenerator:
    """مولد الرموز والعناصر الفريدة"""
    
    @staticmethod
    def generate_referral_code(user_id: int) -> str:
        """توليد كود إحالة فريد"""
        base = str(user_id)[-6:].zfill(6)
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(secrets.choice(chars) for _ in range(4))
        return f"REF{base}{random_part}"
    
    @staticmethod
    def generate_gift_code() -> str:
        """توليد كود هدية فريد"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(8))
    
    @staticmethod
    def generate_transaction_id() -> str:
        """توليد معرف معاملة فريد"""
        timestamp = int(time.time())
        random_part = secrets.token_hex(4)
        return f"TX{timestamp}{random_part}".upper()
    
    @staticmethod
    def generate_ichancy_username(base_name: str) -> str:
        """توليد اسم مستخدم Ichancy فريد"""
        random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        return f"{base_name}{random_suffix}"


# إنشاء نسخ عامة
password_manager = PasswordManager()
encryption_manager = EncryptionManager()
rate_limiter = RateLimiter()
input_validator = InputValidator()
token_generator = TokenGenerator()

# دالة أمان عامة
def require_admin(func):
    """ديكورير يتطلب صلاحيات أدمن"""
    def wrapper(*args, **kwargs):
        from services.user_service import UserService
        user_service = UserService()
        
        # البحث عن user_id في الوسائط
        user_id = None
        for arg in args:
            if hasattr(arg, 'from_user'):
                user_id = arg.from_user.id
                break
            elif hasattr(arg, 'message') and hasattr(arg.message, 'from_user'):
                user_id = arg.message.from_user.id
                break
        
        if not user_id:
            logger.warning("لم يتم العثور على user_id في require_admin")
            return None
        
        if not user_service.is_admin(user_id):
            logger.warning(f"محاولة وصول غير مصرح بها من المستخدم {user_id}")
            return None
        
        return func(*args, **kwargs)
    return wrapper