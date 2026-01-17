"""
نموذج إدارة الأدمن
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
import json

from core.database import db
from core.cache import cache
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Admin:
    """نموذج بيانات الأدمن"""
    user_id: int
    added_by: int
    added_at: str = None
    permissions: str = 'limited'  # 'limited', 'full'
    
    def __post_init__(self):
        if self.added_at is None:
            self.added_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return asdict(self)
    
    def has_permission(self, permission: str) -> bool:
        """التحقق من الصلاحية"""
        if self.permissions == 'full':
            return True
        return permission in self.permissions.split(',')


class AdminModel:
    """نموذج إدارة الأدمن"""
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """التحقق إذا كان المستخدم أدمن"""
        # التحقق من الكاش أولاً
        cached = cache.get_admin_status(user_id)
        if cached is not None:
            return cached
        
        # التحقق من الإدمن الرئيسي
        from core.config import ADMIN_ID
        if user_id == ADMIN_ID:
            cache.set_admin_status(user_id, True)
            return True
        
        # التحقق من قاعدة البيانات
        query = "SELECT 1 FROM admins WHERE user_id = ?"
        result = db.fetch_one(query, (user_id,))
        
        is_admin = result is not None
        cache.set_admin_status(user_id, is_admin)
        
        return is_admin
    
    @staticmethod
    def can_manage_admins(user_id: int) -> bool:
        """التحقق إذا كان يمكنه إدارة الأدمن"""
        from core.config import ADMIN_ID
        return user_id == ADMIN_ID
    
    @staticmethod
    def add_admin(user_id: int, added_by: int, permissions: str = 'limited') -> bool:
        """إضافة أدمن جديد"""
        try:
            # التحقق من عدد الأدمن
            current_admins = AdminModel.get_all()
            max_admins = 10  # يمكن جعله إعداد
            
            if len(current_admins) >= max_admins:
                logger.warning(f"وصل للحد الأقصى للأدمن ({max_admins})")
                return False
            
            query = """
                INSERT INTO admins (user_id, added_by, added_at, permissions)
                VALUES (?, ?, datetime('now'), ?)
            """
            
            db.execute_query(query, (user_id, added_by, permissions))
            
            # تحديث الكاش
            cache.set_admin_status(user_id, True)
            
            logger.info(f"تم إضافة أدمن جديد: {user_id} بواسطة {added_by}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إضافة أدمن: {e}")
            return False
    
    @staticmethod
    def remove_admin(user_id: int) -> bool:
        """حذف أدمن"""
        try:
            query = "DELETE FROM admins WHERE user_id = ?"
            db.execute_query(query, (user_id,))
            
            # تحديث الكاش
            cache.delete_admin_status(user_id)
            
            logger.info(f"تم حذف أدمن: {user_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في حذف أدمن: {e}")
            return False
    
    @staticmethod
    def get_all() -> List[Admin]:
        """جلب جميع الأدمن"""
        query = """
            SELECT a.user_id, a.added_by, a.added_at, a.permissions,
                   u.created_at as user_created
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.added_at DESC
        """
        
        results = db.fetch_all(query)
        return [
            Admin(
                user_id=row['user_id'],
                added_by=row['added_by'],
                added_at=row['added_at'],
                permissions=row['permissions']
            ) for row in results
        ]
    
    @staticmethod
    def get_admin(user_id: int) -> Optional[Admin]:
        """جلب بيانات أدمن معين"""
        query = """
            SELECT user_id, added_by, added_at, permissions
            FROM admins WHERE user_id = ?
        """
        
        result = db.fetch_one(query, (user_id,))
        if result:
            return Admin(
                user_id=result['user_id'],
                added_by=result['added_by'],
                added_at=result['added_at'],
                permissions=result['permissions']
            )
        return None
    
    @staticmethod
    def update_permissions(user_id: int, permissions: str) -> bool:
        """تحديث صلاحيات الأدمن"""
        try:
            query = "UPDATE admins SET permissions = ? WHERE user_id = ?"
            db.execute_query(query, (permissions, user_id))
            
            logger.info(f"تم تحديث صلاحيات الأدمن {user_id} إلى: {permissions}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث صلاحيات الأدمن: {e}")
            return False
    
    @staticmethod
    def count_all() -> int:
        """عد جميع الأدمن"""
        query = "SELECT COUNT(*) as count FROM admins"
        result = db.fetch_one(query)
        return result['count'] if result else 0
    
    @staticmethod
    def get_admin_actions(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """جلب إجراءات الأدمن"""
        # يمكن توسيع هذه الدالة لتسجيل إجراءات الأدمن
        # حالياً ترجع قائمة فارغة
        return []