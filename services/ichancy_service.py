"""
خدمات نظام Ichancy - سرعة فائقة
"""

from typing import Optional, Dict, Any, List
import time

from core.database import db
from core.cache import cache
from core.security import password_manager, token_generator, input_validator
from core.config import ICHANCY_CONFIG
from core.logger import get_logger, performance_logger
from models.ichancy import IchancyAccount, IchancyModel
from models.user import UserModel

logger = get_logger(__name__)


class IchancyService:
    """خدمات نظام Ichancy"""
    
    def __init__(self):
        self.cache = cache
    
    @performance_logger
    def create_account(self, user_id: int, base_username: str = None) -> Dict[str, Any]:
        """إنشاء حساب Ichancy"""
        try:
            # التحقق من وجود حساب مسبق
            existing_account = IchancyModel.get(user_id)
            if existing_account:
                return {
                    "success": False,
                    "message": "لديك حساب Ichancy بالفعل"
                }
            
            # توليد اسم المستخدم
            if not base_username or not input_validator.validate_username(base_username):
                base_username = "User"
            
            username = token_generator.generate_ichancy_username(base_username)
            
            # التحقق من التكرار
            while IchancyModel.get_by_username(username):
                username = token_generator.generate_ichancy_username(base_username)
            
            # توليد كلمة مرور قوية
            password = password_manager.generate_strong_password(
                ICHANCY_CONFIG["PASSWORD_LENGTH"]
            )
            
            # إنشاء الحساب
            account = IchancyModel.create(user_id, username, password)
            if not account:
                return {"success": False, "message": "خطأ في إنشاء الحساب"}
            
            return {
                "success": True,
                "message": "تم إنشاء حساب Ichancy بنجاح",
                "username": username,
                "password": password,
                "account": account.to_dict()
            }
        except Exception as e:
            logger.error(f"خطأ في create_account: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def get_account_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """جلب معلومات حساب Ichancy"""
        account = IchancyModel.get(user_id)
        if not account:
            return None
        
        return {
            "username": account.ichancy_username,
            "balance": account.ichancy_balance,
            "created_at": account.created_at,
            "last_login": account.last_login,
            "has_password": True
        }
    
    @performance_logger
    def update_balance(self, user_id: int, amount: int, operation: str = 'add') -> Dict[str, Any]:
        """تحديث رصيد Ichancy"""
        try:
            if amount <= 0:
                return {"success": False, "message": "المبلغ يجب أن يكون أكبر من صفر"}
            
            account = IchancyModel.get(user_id)
            if not account:
                return {"success": False, "message": "ليس لديك حساب Ichancy"}
            
            if operation == 'subtract' and account.ichancy_balance < amount:
                return {"success": False, "message": "الرصيد غير كافي في Ichancy"}
            
            if IchancyModel.update_balance(user_id, amount, operation):
                # إبطال الكاش
                cache_key = f"ichancy_{user_id}"
                self.cache.cache.delete(cache_key)
                
                # جلب الرصيد الجديد
                account = IchancyModel.get(user_id)
                
                return {
                    "success": True,
                    "old_balance": account.ichancy_balance - amount if operation == 'add' else account.ichancy_balance + amount,
                    "new_balance": account.ichancy_balance,
                    "operation": operation,
                    "amount": amount
                }
            
            return {"success": False, "message": "خطأ في تحديث الرصيد"}
        except Exception as e:
            logger.error(f"خطأ في update_balance Ichancy: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def deposit_to_ichancy(self, user_id: int, amount: int) -> Dict[str, Any]:
        """شحن رصيد من البوت إلى Ichancy"""
        try:
            # التحقق من رصيد البوت
            from services.user_service import UserService
            user_service = UserService()
            bot_balance = user_service.get_user_balance(user_id)
            
            if amount > bot_balance:
                return {"success": False, "message": "الرصيد غير كافي في البوت"}
            
            # خصم من البوت
            bot_result = user_service.update_balance(user_id, amount, 'subtract')
            if not bot_result['success']:
                return bot_result
            
            # إضافة إلى Ichancy
            ichancy_result = self.update_balance(user_id, amount, 'add')
            if not ichancy_result['success']:
                # إرجاع الرصيد في حالة الخطأ
                user_service.update_balance(user_id, amount, 'add')
                return ichancy_result
            
            return {
                "success": True,
                "message": f"تم تحويل {amount:,} ليرة إلى حساب Ichancy",
                "bot_balance": bot_result['new_balance'],
                "ichancy_balance": ichancy_result['new_balance']
            }
        except Exception as e:
            logger.error(f"خطأ في deposit_to_ichancy: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def withdraw_from_ichancy(self, user_id: int, amount: int) -> Dict[str, Any]:
        """سحب رصيد من Ichancy إلى البوت"""
        try:
            # التحقق من رصيد Ichancy
            ichancy_result = self.update_balance(user_id, amount, 'subtract')
            if not ichancy_result['success']:
                return ichancy_result
            
            # إضافة إلى البوت
            from services.user_service import UserService
            user_service = UserService()
            bot_result = user_service.update_balance(user_id, amount, 'add')
            
            if not bot_result['success']:
                # إرجاع الرصيد في حالة الخطأ
                self.update_balance(user_id, amount, 'add')
                return bot_result
            
            return {
                "success": True,
                "message": f"تم تحويل {amount:,} ليرة من حساب Ichancy إلى البوت",
                "bot_balance": bot_result['new_balance'],
                "ichancy_balance": ichancy_result['new_balance']
            }
        except Exception as e:
            logger.error(f"خطأ في withdraw_from_ichancy: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def get_all_accounts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب جميع حسابات Ichancy"""
        accounts = IchancyModel.get_all(limit)
        return [account.to_dict() for account in accounts]
    
    @performance_logger
    def count_accounts(self) -> int:
        """عد حسابات Ichancy"""
        return IchancyModel.count_all()
    
    @performance_logger
    def delete_account(self, user_id: int) -> bool:
        """حذف حساب Ichancy"""
        return IchancyModel.delete(user_id)
    
    @performance_logger
    def verify_login(self, username: str, password: str) -> Optional[int]:
        """التحقق من تسجيل الدخول"""
        account = IchancyModel.get_by_username(username)
        if not account:
            return None
        
        if account.verify_password(password):
            account.update_login()
            return account.user_id
        
        return None