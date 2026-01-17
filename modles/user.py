"""
نموذج المستخدم مع جميع الخصائص
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
class User:
    """نموذج بيانات المستخدم"""
    user_id: int
    balance: int = 0
    created_at: str = None
    last_active: str = None
    referral_code: str = None
    referred_by: int = None
    is_banned: bool = False
    ban_reason: str = None
    ban_until: str = None
    total_deposit: int = 0
    total_withdraw: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.last_active is None:
            self.last_active = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return asdict(self)
    
    def to_json(self) -> str:
        """تحويل إلى JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def update_activity(self):
        """تحديث وقت النشاط الأخير"""
        self.last_active = datetime.now().isoformat()
        self.save_to_cache()
    
    def save_to_cache(self):
        """حفظ في الكاش"""
        cache.set_user(self.user_id, self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """إنشاء من قاموس"""
        return cls(**data)


class UserModel:
    """نموذج إدارة المستخدمين في قاعدة البيانات"""
    
    @staticmethod
    def create(user_id: int) -> bool:
        """إنشاء مستخدم جديد"""
        try:
            from core.security import token_generator
            
            referral_code = token_generator.generate_referral_code(user_id)
            
            query = """
                INSERT INTO users (user_id, referral_code, created_at, last_active)
                VALUES (?, ?, datetime('now'), datetime('now'))
            """
            
            db.execute_query(query, (user_id, referral_code))
            logger.info(f"تم إنشاء مستخدم جديد: {user_id}")
            
            # إضافة للكاش
            user = User(user_id=user_id, referral_code=referral_code)
            user.save_to_cache()
            
            return True
        except Exception as e:
            logger.error(f"خطأ في إنشاء مستخدم {user_id}: {e}")
            return False
    
    @staticmethod
    def get(user_id: int) -> Optional[User]:
        """جلب بيانات مستخدم"""
        # التحقق من الكاش أولاً
        cached_user = cache.get_user(user_id)
        if cached_user:
            return User.from_dict(cached_user)
        
        # جلب من قاعدة البيانات
        query = """
            SELECT user_id, balance, created_at, last_active, referral_code,
                   referred_by, is_banned, ban_reason, ban_until,
                   total_deposit, total_withdraw
            FROM users WHERE user_id = ?
        """
        
        result = db.fetch_one(query, (user_id,))
        if result:
            user = User(
                user_id=result['user_id'],
                balance=result['balance'],
                created_at=result['created_at'],
                last_active=result['last_active'],
                referral_code=result['referral_code'],
                referred_by=result['referred_by'],
                is_banned=bool(result['is_banned']),
                ban_reason=result['ban_reason'],
                ban_until=result['ban_until'],
                total_deposit=result['total_deposit'],
                total_withdraw=result['total_withdraw']
            )
            
            # حفظ في الكاش
            user.save_to_cache()
            
            return user
        
        return None
    
    @staticmethod
    def update_balance(user_id: int, amount: int, operation: str = 'add') -> bool:
        """تحديث رصيد المستخدم"""
        try:
            if operation == 'add':
                query = """
                    UPDATE users 
                    SET balance = balance + ?, 
                        total_deposit = total_deposit + ?,
                        last_active = datetime('now')
                    WHERE user_id = ?
                """
                params = (amount, amount, user_id)
            elif operation == 'subtract':
                query = """
                    UPDATE users 
                    SET balance = MAX(0, balance - ?),
                        total_withdraw = total_withdraw + ?,
                        last_active = datetime('now')
                    WHERE user_id = ?
                """
                params = (amount, amount, user_id)
            else:
                return False
            
            db.execute_query(query, params)
            
            # تحديث الكاش
            cache.delete_user(user_id)
            
            logger.debug(f"تم تحديث رصيد المستخدم {user_id}: {operation} {amount}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث رصيد المستخدم {user_id}: {e}")
            return False
    
    @staticmethod
    def ban(user_id: int, reason: str = "", ban_until: str = None) -> bool:
        """حظر مستخدم"""
        try:
            query = """
                UPDATE users 
                SET is_banned = 1, ban_reason = ?, ban_until = ?
                WHERE user_id = ?
            """
            db.execute_query(query, (reason, ban_until, user_id))
            
            # تحديث الكاش
            cache.delete_user(user_id)
            
            logger.info(f"تم حظر المستخدم {user_id}: {reason}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حظر المستخدم {user_id}: {e}")
            return False
    
    @staticmethod
    def unban(user_id: int) -> bool:
        """فك حظر مستخدم"""
        try:
            query = """
                UPDATE users 
                SET is_banned = 0, ban_reason = NULL, ban_until = NULL
                WHERE user_id = ?
            """
            db.execute_query(query, (user_id,))
            
            # تحديث الكاش
            cache.delete_user(user_id)
            
            logger.info(f"تم فك حظر المستخدم {user_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في فك حظر المستخدم {user_id}: {e}")
            return False
    
    @staticmethod
    def delete(user_id: int) -> bool:
        """حذف مستخدم"""
        try:
            query = "DELETE FROM users WHERE user_id = ?"
            db.execute_query(query, (user_id,))
            
            # حذف من الكاش
            cache.delete_user(user_id)
            cache.delete_admin_status(user_id)
            
            logger.info(f"تم حذف المستخدم {user_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حذف المستخدم {user_id}: {e}")
            return False
    
    @staticmethod
    def get_all(limit: int = 100, offset: int = 0) -> list:
        """جلب جميع المستخدمين"""
        query = """
            SELECT user_id, balance, created_at, last_active, is_banned,
                   total_deposit, total_withdraw
            FROM users 
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        
        results = db.fetch_all(query, (limit, offset))
        return [
            User(
                user_id=row['user_id'],
                balance=row['balance'],
                created_at=row['created_at'],
                last_active=row['last_active'],
                is_banned=bool(row['is_banned']),
                total_deposit=row['total_deposit'],
                total_withdraw=row['total_withdraw']
            ) for row in results
        ]
    
    @staticmethod
    def get_top_by_balance(limit: int = 20) -> list:
        """جلب أعلى المستخدمين حسب الرصيد"""
        query = """
            SELECT user_id, balance, created_at, last_active
            FROM users 
            WHERE is_banned = 0
            ORDER BY balance DESC
            LIMIT ?
        """
        
        results = db.fetch_all(query, (limit,))
        return [
            User(
                user_id=row['user_id'],
                balance=row['balance'],
                created_at=row['created_at'],
                last_active=row['last_active']
            ) for row in results
        ]
    
    @staticmethod
    def get_top_by_deposit(limit: int = 10) -> list:
        """جلب أعلى المستخدمين حسب الإيداع"""
        query = """
            SELECT user_id, total_deposit, created_at, last_active
            FROM users 
            WHERE is_banned = 0
            ORDER BY total_deposit DESC
            LIMIT ?
        """
        
        results = db.fetch_all(query, (limit,))
        return [
            User(
                user_id=row['user_id'],
                total_deposit=row['total_deposit'],
                created_at=row['created_at'],
                last_active=row['last_active']
            ) for row in results
        ]
    
    @staticmethod
    def count_all() -> int:
        """عد جميع المستخدمين"""
        query = "SELECT COUNT(*) as count FROM users"
        result = db.fetch_one(query)
        return result['count'] if result else 0
    
    @staticmethod
    def count_banned() -> int:
        """عد المستخدمين المحظورين"""
        query = "SELECT COUNT(*) as count FROM users WHERE is_banned = 1"
        result = db.fetch_one(query)
        return result['count'] if result else 0
    
    @staticmethod
    def reset_all_balances() -> int:
        """تصفير جميع الأرصدة"""
        try:
            query = "UPDATE users SET balance = 0 WHERE is_banned = 0"
            cursor = db.execute_query(query)
            
            # إبطال كاش جميع المستخدمين
            cache.invalidate_pattern("user_")
            
            affected = cursor.rowcount
            logger.warning(f"تم تصفير أرصدة {affected} مستخدم")
            return affected
        except Exception as e:
            logger.error(f"خطأ في تصفير الأرصدة: {e}")
            return 0