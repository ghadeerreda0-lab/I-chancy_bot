"""
خدمات نظام الهدايا - سرعة فائقة
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time

from core.database import db
from core.cache import cache
from core.security import input_validator
from core.logger import get_logger, performance_logger
from models.gift import GiftCode, GiftTransaction, GiftModel
from models.user import UserModel
from models.transaction import TransactionModel

logger = get_logger(__name__)


class GiftService:
    """خدمات نظام الهدايا"""
    
    def __init__(self):
        self.cache = cache
    
    @performance_logger
    def create_gift_code(self, amount: int, max_uses: int = 1, 
                         expires_days: int = 30, created_by: int = None) -> Dict[str, Any]:
        """إنشاء كود هدية جديد"""
        try:
            if amount <= 0:
                return {"success": False, "message": "المبلغ يجب أن يكون أكبر من صفر"}
            
            if max_uses <= 0:
                return {"success": False, "message": "عدد الاستخدامات يجب أن يكون أكبر من صفر"}
            
            gift_code = GiftModel.create_code(amount, max_uses, expires_days, created_by)
            if not gift_code:
                return {"success": False, "message": "خطأ في إنشاء الكود"}
            
            return {
                "success": True,
                "code": gift_code.code,
                "amount": gift_code.amount,
                "max_uses": gift_code.max_uses,
                "expires_at": gift_code.expires_at,
                "message": f"تم إنشاء كود هدية: {gift_code.code}"
            }
        except Exception as e:
            logger.error(f"خطأ في create_gift_code: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def use_gift_code(self, code_str: str, user_id: int) -> Dict[str, Any]:
        """استخدام كود هدية"""
        try:
            # جلب الكود
            gift_code = GiftModel.get_code(code_str)
            if not gift_code:
                return {"success": False, "message": "كود الهدية غير صحيح"}
            
            # التحقق من الصلاحية
            if not gift_code.is_valid():
                if gift_code.used_count >= gift_code.max_uses:
                    return {"success": False, "message": "هذا الكود مستخدم بالفعل"}
                elif gift_code.expires_at and datetime.fromisoformat(gift_code.expires_at) < datetime.now():
                    return {"success": False, "message": "انتهت صلاحية هذا الكود"}
                else:
                    return {"success": False, "message": "الكود غير صالح"}
            
            # التحقق إذا استخدمه المستخدم سابقاً
            used_codes = GiftModel.get_user_used_codes(user_id)
            if code_str in used_codes:
                return {"success": False, "message": "لقد استخدمت هذا الكود مسبقاً"}
            
            # استخدام الكود
            if GiftModel.use_code(code_str, user_id):
                # إضافة الرصيد للمستخدم
                from services.user_service import UserService
                user_service = UserService()
                
                result = user_service.update_balance(user_id, gift_code.amount, 'add')
                if result['success']:
                    # تسجيل المعاملة
                    transaction = TransactionModel()
                    transaction.create(
                        user_id=user_id,
                        type='bonus',
                        amount=gift_code.amount,
                        notes=f"كود هدية: {code_str}"
                    )
                    
                    return {
                        "success": True,
                        "message": f"✅ تم تفعيل الكود بنجاح! تم إضافة {gift_code.amount:,} ليرة إلى رصيدك",
                        "amount": gift_code.amount,
                        "new_balance": result['new_balance'],
                        "remaining_uses": gift_code.max_uses - gift_code.used_count - 1
                    }
                else:
                    # التراجع عن استخدام الكود في حالة الخطأ
                    # (هذا يتطلب آلية تراجع أكثر تعقيداً)
                    return {"success": False, "message": "خطأ في إضافة الرصيد"}
            
            return {"success": False, "message": "خطأ في تفعيل الكود"}
        except Exception as e:
            logger.error(f"خطأ في use_gift_code: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def send_gift(self, sender_id: int, receiver_id: int, amount: int) -> Dict[str, Any]:
        """إرسال هدية من مستخدم لآخر"""
        try:
            if amount <= 0:
                return {"success": False, "message": "المبلغ يجب أن يكون أكبر من صفر"}
            
            if sender_id == receiver_id:
                return {"success": False, "message": "لا يمكن إهداء نفسك"}
            
            # التحقق من وجود المستلم
            receiver = UserModel.get(receiver_id)
            if not receiver:
                return {"success": False, "message": "المستخدم غير موجود"}
            
            if receiver.is_banned:
                return {"success": False, "message": "لا يمكن إهداء مستخدم محظور"}
            
            # التحقق من رصيد المرسل
            from services.user_service import UserService
            user_service = UserService()
            sender_balance = user_service.get_user_balance(sender_id)
            
            if amount > sender_balance:
                return {"success": False, "message": "رصيدك غير كافي"}
            
            # تطبيق نسبة الإهداء
            from services.system_service import SystemService
            system_service = SystemService()
            gift_percentage = system_service.get_setting('gift_percentage', '0')
            
            net_amount = amount
            deduction = 0
            
            if gift_percentage and gift_percentage != '0':
                percentage = int(gift_percentage)
                deduction = int(amount * percentage / 100)
                net_amount = amount - deduction
            
            # خصم من المرسل
            sender_result = user_service.update_balance(sender_id, amount, 'subtract')
            if not sender_result['success']:
                return sender_result
            
            # إضافة للمستلم
            receiver_result = user_service.update_balance(receiver_id, net_amount, 'add')
            if not receiver_result['success']:
                # إرجاع الرصيد في حالة الخطأ
                user_service.update_balance(sender_id, amount, 'add')
                return receiver_result
            
            # تسجيل معاملة الإهداء
            gift_transaction = GiftTransaction(
                sender_id=sender_id,
                receiver_id=receiver_id,
                original_amount=amount,
                net_amount=net_amount,
                gift_percentage=int(gift_percentage) if gift_percentage else 0
            )
            
            GiftModel.create_gift_transaction(gift_transaction)
            
            # تسجيل معاملات منفصلة
            TransactionModel().create(
                user_id=sender_id,
                type='gift_sent',
                amount=amount,
                notes=f"إهداء للمستخدم {receiver_id}"
            )
            
            TransactionModel().create(
                user_id=receiver_id,
                type='gift_received',
                amount=net_amount,
                notes=f"هدية من المستخدم {sender_id}"
            )
            
            return {
                "success": True,
                "message": f"✅ تم إرسال الهدية بنجاح!\nالمستلم سيحصل على {net_amount:,} ليرة (بعد خصم {deduction:,} ليرة)",
                "net_amount": net_amount,
                "deduction": deduction,
                "sender_balance": sender_result['new_balance'],
                "receiver_balance": receiver_result['new_balance']
            }
        except Exception as e:
            logger.error(f"خطأ في send_gift: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def get_gift_transactions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """جلب معاملات الإهداء للمستخدم"""
        return GiftModel.get_user_gift_transactions(user_id, limit)
    
    @performance_logger
    def get_all_gift_codes(self, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب جميع أكواد الهدايا"""
        codes = GiftModel.get_all_codes(limit)
        return [code.to_dict() for code in codes]
    
    @performance_logger
    def cleanup_expired_codes(self) -> int:
        """تنظيف الأكواد المنتهية الصلاحية"""
        return GiftModel.delete_expired_codes()
    
    @performance_logger
    def validate_gift_code(self, code_str: str) -> Dict[str, Any]:
        """التحقق من صلاحية كود هدية"""
        gift_code = GiftModel.get_code(code_str)
        if not gift_code:
            return {"valid": False, "message": "الكود غير صحيح"}
        
        if not gift_code.is_valid():
            if gift_code.used_count >= gift_code.max_uses:
                return {"valid": False, "message": "الكود مستخدم مسبقاً"}
            elif gift_code.expires_at and datetime.fromisoformat(gift_code.expires_at) < datetime.now():
                return {"valid": False, "message": "الكود منتهي الصلاحية"}
            else:
                return {"valid": False, "message": "الكود غير صالح"}
        
        return {
            "valid": True,
            "message": "الكود صالح",
            "amount": gift_code.amount,
            "remaining_uses": gift_code.max_uses - gift_code.used_count
        }