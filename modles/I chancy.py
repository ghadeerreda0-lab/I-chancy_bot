"""
نموذج حساب Ichancy
"""

from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import json

from core.database import db
from core.cache import cache
from core.security import password_manager, encryption_manager
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IchancyAccount:
    """نموذج حساب Ichancy"""
    user_id: int
    ichancy_username: str
    ichancy_password: str
    ichancy_balance: int = 0
    created_at: str = None
    last_login: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        
        # تشفير كلمة المرور عند الإنشاء
        if self.ichancy_password and not self.ichancy_password.startswith('$2b$'):
            self.ichancy_password = password_manager.hash_password(self.ichancy_password)
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        data = asdict(self)
        # إخفاء كلمة المرور المشفرة
        data['ichancy_password'] = '********'
        return data
    
    def to_secure_dict(self) -> Dict[str, Any]:
        """تحويل مع تشفير كامل"""
        data = asdict(self)
        # تشفير كلمة المرور للمراجعة
        data['encrypted_password'] = encryption_manager.encrypt(self.ichancy_password)
        return data
    
    def update_login(self):
        """تحديث وقت الدخول الأخير"""
        self.last_login = datetime.now().isoformat()
        self.save()
    
    def verify_password(self, password: str) -> bool:
        """التحقق من كلمة المرور"""
        return password_manager.verify_password(self.ichancy_password, password)
    
    def save(self):
        """حفظ في قاعدة البيانات"""
        IchancyModel.update(self)


class IchancyModel:
    """نموذج إدارة حسابات Ichancy"""
    
    @staticmethod
    def create(user_id: int, username: str, password: str) -> Optional[IchancyAccount]:
        """إنشاء حساب Ichancy جديد"""
        try:
            # تشفير كلمة المرور
            hashed_password = password_manager.hash_password(password)
            
            query = """
                INSERT INTO ichancy_accounts 
                (user_id, ichancy_username, ichancy_password, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """
            
            db.execute_query(query, (user_id, username, hashed_password))
            
            account = IchancyAccount(
                user_id=user_id,
                ichancy_username=username,
                ichancy_password=hashed_password
            )
            
            logger.info(f"تم إنشاء حساب Ichancy للمستخدم {user_id}: {username}")
            return account
        except Exception as e:
            logger.error(f"خطأ في إنشاء حساب Ichancy: {e}")
            return None
    
    @staticmethod
    def get(user_id: int) -> Optional[IchancyAccount]:
        """جلب حساب Ichancy"""
        # التحقق من الكاش
        cache_key = f"ichancy_{user_id}"
        cached = cache.cache.get(cache_key)
        if cached:
            return IchancyAccount(**cached)
        
        query = """
            SELECT user_id, ichancy_username, ichancy_password, 
                   ichancy_balance, created_at, last_login
            FROM ichancy_accounts 
            WHERE user_id = ?
        """
        
        result = db.fetch_one(query, (user_id,))
        if result:
            account = IchancyAccount(
                user_id=result['user_id'],
                ichancy_username=result['ichancy_username'],
                ichancy_password=result['ichancy_password'],
                ichancy_balance=result['ichancy_balance'],
                created_at=result['created_at'],
                last_login=result['last_login']
            )
            
            # حفظ في الكاش
            cache.cache.set(cache_key, asdict(account), ttl=300)
            
            return account
        
        return None
    
    @staticmethod
    def get_by_username(username: str) -> Optional[IchancyAccount]:
        """جلب حساب بواسطة اسم المستخدم"""
        query = """
            SELECT user_id, ichancy_username, ichancy_password, 
                   ichancy_balance, created_at, last_login
            FROM ichancy_accounts 
            WHERE ichancy_username = ?
        """
        
        result = db.fetch_one(query, (username,))
        if result:
            return IchancyAccount(
                user_id=result['user_id'],
                ichancy_username=result['ichancy_username'],
                ichancy_password=result['ichancy_password'],
                ichancy_balance=result['ichancy_balance'],
                created_at=result['created_at'],
                last_login=result['last_login']
            )
        
        return None
    
    @staticmethod
    def update(account: IchancyAccount) -> bool:
        """تحديث حساب"""
        try:
            query = """
                UPDATE ichancy_accounts 
                SET ichancy_balance = ?, last_login = ?
                WHERE user_id = ?
            """
            
            db.execute_query(query, (
                account.ichancy_balance,
                account.last_login or datetime.now().isoformat(),
                account.user_id
            ))
            
            # تحديث الكاش
            cache_key = f"ichancy_{account.user_id}"
            cache.cache.delete(cache_key)
            
            logger.debug(f"تم تحديث حساب Ichancy للمستخدم {account.user_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث حساب Ichancy: {e}")
            return False
    
    @staticmethod
    def update_balance(user_id: int, amount: int, operation: str = 'add') -> bool:
        """تحديث رصيد Ichancy"""
        try:
            if operation == 'add':
                query = """
                    UPDATE ichancy_accounts 
                    SET ichancy_balance = ichancy_balance + ?, 
                        last_login = datetime('now')
                    WHERE user_id = ?
                """
            elif operation == 'subtract':
                query = """
                    UPDATE ichancy_accounts 
                    SET ichancy_balance = MAX(0, ichancy_balance - ?),
                        last_login = datetime('now')
                    WHERE user_id = ?
                """
            else:
                return False
            
            db.execute_query(query, (amount, user_id))
            
            # تحديث الكاش
            cache_key = f"ichancy_{user_id}"
            cache.cache.delete(cache_key)
            
            logger.debug(f"تم تحديث رصيد Ichancy للمستخدم {user_id}: {operation} {amount}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث رصيد Ichancy: {e}")
            return False
    
    @staticmethod
    def delete(user_id: int) -> bool:
        """حذف حساب Ichancy"""
        try:
            query = "DELETE FROM ichancy_accounts WHERE user_id = ?"
            db.execute_query(query, (user_id,))
            
            # حذف من الكاش
            cache_key = f"ichancy_{user_id}"
            cache.cache.delete(cache_key)
            
            logger.info(f"تم حذف حساب Ichancy للمستخدم {user_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حذف حساب Ichancy: {e}")
            return False
    
    @staticmethod
    def exists(user_id: int) -> bool:
        """التحقق من وجود حساب"""
        account = IchancyModel.get(user_id)
        return account is not None
    
    @staticmethod
    def get_all(limit: int = 100) -> list:
        """جلب جميع الحسابات"""
        query = """
            SELECT user_id, ichancy_username, ichancy_balance, 
                   created_at, last_login
            FROM ichancy_accounts 
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        results = db.fetch_all(query, (limit,))
        return [
            IchancyAccount(
                user_id=row['user_id'],
                ichancy_username=row['ichancy_username'],
                ichancy_password='********',  # مخفي
                ichancy_balance=row['ichancy_balance'],
                created_at=row['created_at'],
                last_login=row['last_login']
            ) for row in results
        ]
    
    @staticmethod
    def count_all() -> int:
        """عد جميع حسابات Ichancy"""
        query = "SELECT COUNT(*) as count FROM ichancy_accounts"
        result = db.fetch_one(query)
        return result['count'] if result else 0