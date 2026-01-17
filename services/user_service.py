"""
خدمات إدارة المستخدمين - سرعة فائقة
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import time

from core.database import db
from core.cache import cache
from core.security import input_validator, rate_limiter
from core.logger import get_logger, performance_logger
from models.user import User, UserModel
from models.ichancy import IchancyModel
from models.referral import ReferralModel
from models.admin import AdminModel

logger = get_logger(__name__)


class UserService:
    """خدمات المستخدمين الرئيسية"""
    
    def __init__(self):
        self.cache = cache
        self.rate_limiter = rate_limiter
    
    @performance_logger
    def get_or_create_user(self, user_id: int) -> Optional[User]:
        """جلب أو إنشاء مستخدم"""
        # التحقق من rate limiting
        allowed, remaining = self.rate_limiter.is_allowed(user_id)
        if not allowed:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return None
        
        user = UserModel.get(user_id)
        if user:
            user.update_activity()
            return user
        
        # إنشاء مستخدم جديد
        if UserModel.create(user_id):
            user = UserModel.get(user_id)
            
            # تسجيل الحدث
            logger.info(f"مستخدم جديد: {user_id}")
            return user
        
        return None
    
    @performance_logger
    def get_user_balance(self, user_id: int) -> int:
        """جلب رصيد المستخدم بسرعة"""
        user = self.get_or_create_user(user_id)
        return user.balance if user else 0
    
    @performance_logger
    def update_balance(self, user_id: int, amount: int, operation: str = 'add') -> Dict[str, Any]:
        """تحديث رصيد المستخدم"""
        try:
            if amount <= 0:
                return {"success": False, "message": "المبلغ يجب أن يكون أكبر من صفر"}
            
            user = self.get_or_create_user(user_id)
            if not user:
                return {"success": False, "message": "المستخدم غير موجود"}
            
            if operation == 'subtract' and user.balance < amount:
                return {"success": False, "message": "الرصيد غير كافي"}
            
            if UserModel.update_balance(user_id, amount, operation):
                # إبطال الكاش
                self.cache.delete_user(user_id)
                
                # جلب الرصيد الجديد
                user = UserModel.get(user_id)
                
                return {
                    "success": True,
                    "old_balance": user.balance - amount if operation == 'add' else user.balance + amount,
                    "new_balance": user.balance,
                    "operation": operation,
                    "amount": amount
                }
            
            return {"success": False, "message": "خطأ في تحديث الرصيد"}
        except Exception as e:
            logger.error(f"خطأ في update_balance: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def ban_user(self, user_id: int, reason: str = "", ban_until: str = None) -> bool:
        """حظر مستخدم"""
        return UserModel.ban(user_id, reason, ban_until)
    
    @performance_logger
    def unban_user(self, user_id: int) -> bool:
        """فك حظر مستخدم"""
        return UserModel.unban(user_id)
    
    @performance_logger
    def delete_user(self, user_id: int) -> bool:
        """حذف مستخدم"""
        # حذف حسابات مرتبطة أولاً
        IchancyModel.delete(user_id)
        
        # حذف المستخدم
        return UserModel.delete(user_id)
    
    @performance_logger
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """جلب جميع المستخدمين"""
        return UserModel.get_all(limit, offset)
    
    @performance_logger
    def get_top_users_by_balance(self, limit: int = 20) -> List[User]:
        """جلب أعلى المستخدمين حسب الرصيد"""
        return UserModel.get_top_by_balance(limit)
    
    @performance_logger
    def get_top_users_by_deposit(self, limit: int = 10) -> List[User]:
        """جلب أعلى المستخدمين حسب الإيداع"""
        return UserModel.get_top_by_deposit(limit)
    
    @performance_logger
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """إحصائيات مستخدم"""
        user = self.get_or_create_user(user_id)
        if not user:
            return {}
        
        # جلب معلومات Ichancy
        ichancy_account = IchancyModel.get(user_id)
        
        # جلب إحصائيات الإحالات
        total_refs, active_refs = ReferralModel.get_active_referrals_count(user_id)
        
        return {
            "user_id": user_id,
            "balance": user.balance,
            "total_deposit": user.total_deposit,
            "total_withdraw": user.total_withdraw,
            "created_at": user.created_at,
            "last_active": user.last_active,
            "is_banned": user.is_banned,
            "has_ichancy": ichancy_account is not None,
            "ichancy_balance": ichancy_account.ichancy_balance if ichancy_account else 0,
            "total_referrals": total_refs,
            "active_referrals": active_refs,
            "referral_code": user.referral_code
        }
    
    @performance_logger
    def get_system_stats(self) -> Dict[str, Any]:
        """إحصائيات النظام"""
        total_users = UserModel.count_all()
        banned_users = UserModel.count_banned()
        active_users = total_users - banned_users
        
        total_admins = AdminModel.count_all()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "total_admins": total_admins,
            "cache_stats": self.cache.get_detailed_stats(),
            "rate_limit_stats": len(self.rate_limiter.requests)
        }
    
    @performance_logger
    def reset_all_balances(self, confirm: bool = False) -> Dict[str, Any]:
        """تصفير جميع الأرصدة"""
        if not confirm:
            return {
                "success": False,
                "message": "يتطلب تأكيد",
                "action_required": True
            }
        
        affected = UserModel.reset_all_balances()
        return {
            "success": True,
            "affected_users": affected,
            "message": f"تم تصفير أرصدة {affected} مستخدم"
        }
    
    @performance_logger
    def is_admin(self, user_id: int) -> bool:
        """التحقق إذا كان أدمن"""
        return AdminModel.is_admin(user_id)
    
    @performance_logger
    def can_manage_admins(self, user_id: int) -> bool:
        """التحقق إذا كان يمكنه إدارة الأدمن"""
        return AdminModel.can_manage_admins(user_id)
    
    @performance_logger
    def search_users(self, query: str, limit: int = 20) -> List[User]:
        """بحث عن مستخدمين"""
        # حالياً تبحث فقط بالرقم، يمكن توسيعها للبحث بالاسم لاحقاً
        try:
            if query.isdigit():
                user_id = int(query)
                user = UserModel.get(user_id)
                return [user] if user else []
            
            # في المستقبل: بحث بأسماء المستخدمين
            return []
        except:
            return []