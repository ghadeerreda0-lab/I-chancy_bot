"""
خدمات الدفع والشحن - سرعة فائقة
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import time

from core.database import db
from core.cache import cache
from core.config import PAYMENT_METHODS, SYSTEM_CONSTANTS
from core.security import input_validator
from core.logger import get_logger, performance_logger
from models.user import UserModel
from models.transaction import Transaction, TransactionModel

logger = get_logger(__name__)


class PaymentService:
    """خدمات الدفع والشحن"""
    
    def __init__(self):
        self.cache = cache
        self.init_payment_settings()
    
    @performance_logger
    def init_payment_settings(self):
        """تهيئة إعدادات الدفع الافتراضية"""
        try:
            for method_id, method_name in PAYMENT_METHODS.items():
                # إعدادات الدفع
                settings_query = """
                    INSERT OR IGNORE INTO payment_settings 
                    (payment_method, is_visible, is_active, pause_message)
                    VALUES (?, 1, 1, ?)
                """
                db.execute_query(settings_query, (method_id, f'⏸️ خدمة {method_name} متوقفة مؤقتاً'))
                
                # حدود المبالغ
                min_amount = 1000
                max_amount = 50000
                if method_id == 'sham_cash_usd':
                    min_amount = 10
                    max_amount = 500
                
                limits_query = """
                    INSERT OR IGNORE INTO payment_limits 
                    (payment_method, min_amount, max_amount, updated_by)
                    VALUES (?, ?, ?, 0)
                """
                db.execute_query(limits_query, (method_id, min_amount, max_amount))
            
            logger.info("تم تهيئة إعدادات الدفع الافتراضية")
        except Exception as e:
            logger.error(f"خطأ في تهيئة إعدادات الدفع: {e}")
    
    @performance_logger
    def get_payment_settings(self, payment_method: str) -> Optional[Dict[str, Any]]:
        """جلب إعدادات طريقة دفع"""
        cache_key = f"payment_settings_{payment_method}"
        cached = self.cache.get_setting(cache_key)
        if cached:
            return cached
        
        query = """
            SELECT payment_method, is_visible, is_active, pause_message
            FROM payment_settings WHERE payment_method = ?
        """
        
        result = db.fetch_one(query, (payment_method,))
        if result:
            settings = {
                "payment_method": result['payment_method'],
                "is_visible": bool(result['is_visible']),
                "is_active": bool(result['is_active']),
                "pause_message": result['pause_message']
            }
            self.cache.set_setting(cache_key, settings, ttl=60)
            return settings
        
        return None
    
    @performance_logger
    def update_payment_settings(self, payment_method: str, **kwargs) -> bool:
        """تحديث إعدادات الدفع"""
        try:
            updates = []
            params = []
            
            if 'is_visible' in kwargs:
                updates.append("is_visible = ?")
                params.append(1 if kwargs['is_visible'] else 0)
            
            if 'is_active' in kwargs:
                updates.append("is_active = ?")
                params.append(1 if kwargs['is_active'] else 0)
            
            if 'pause_message' in kwargs:
                updates.append("pause_message = ?")
                params.append(kwargs['pause_message'])
            
            if updates:
                updates.append("updated_at = datetime('now')")
                query = f"UPDATE payment_settings SET {', '.join(updates)} WHERE payment_method = ?"
                params.append(payment_method)
                
                db.execute_query(query, tuple(params))
                
                # إبطال الكاش
                self.cache.delete_setting(f"payment_settings_{payment_method}")
                
                logger.info(f"تم تحديث إعدادات الدفع: {payment_method}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"خطأ في تحديث إعدادات الدفع: {e}")
            return False
    
    @performance_logger
    def get_payment_limits(self, payment_method: str) -> Optional[Dict[str, Any]]:
        """جلب حدود المبالغ لطريقة دفع"""
        cache_key = f"payment_limits_{payment_method}"
        cached = self.cache.get_setting(cache_key)
        if cached:
            return cached
        
        query = """
            SELECT payment_method, min_amount, max_amount
            FROM payment_limits WHERE payment_method = ?
        """
        
        result = db.fetch_one(query, (payment_method,))
        if result:
            limits = {
                "payment_method": result['payment_method'],
                "min_amount": result['min_amount'],
                "max_amount": result['max_amount']
            }
            self.cache.set_setting(cache_key, limits, ttl=60)
            return limits
        
        return None
    
    @performance_logger
    def update_payment_limits(self, payment_method: str, min_amount: int, max_amount: int) -> bool:
        """تحديث حدود المبالغ"""
        try:
            query = """
                UPDATE payment_limits 
                SET min_amount = ?, max_amount = ?, updated_at = datetime('now')
                WHERE payment_method = ?
            """
            
            db.execute_query(query, (min_amount, max_amount, payment_method))
            
            # إبطال الكاش
            self.cache.delete_setting(f"payment_limits_{payment_method}")
            
            logger.info(f"تم تحديث حدود الدفع لـ {payment_method}: {min_amount}-{max_amount}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث حدود الدفع: {e}")
            return False
    
    @performance_logger
    def validate_payment_amount(self, payment_method: str, amount: int) -> Dict[str, Any]:
        """التحقق من صحة مبلغ الدفع"""
        limits = self.get_payment_limits(payment_method)
        if not limits:
            return {"valid": False, "message": "طريقة الدفع غير معروفة"}
        
        if amount < limits['min_amount']:
            return {
                "valid": False,
                "message": f"الحد الأدنى للشحن هو {limits['min_amount']:,} {'دولار' if payment_method == 'sham_cash_usd' else 'ليرة'}"
            }
        
        if amount > limits['max_amount']:
            return {
                "valid": False,
                "message": f"الحد الأقصى للشحن هو {limits['max_amount']:,} {'دولار' if payment_method == 'sham_cash_usd' else 'ليرة'}"
            }
        
        return {"valid": True, "message": "المبلغ صالح"}
    
    @performance_logger
    def create_deposit_request(self, user_id: int, amount: int, 
                               payment_method: str, transaction_id: str) -> Dict[str, Any]:
        """إنشاء طلب شحن"""
        try:
            # التحقق من إعدادات الدفع
            settings = self.get_payment_settings(payment_method)
            if not settings or not settings['is_active']:
                return {
                    "success": False,
                    "message": settings['pause_message'] if settings else "طريقة الدفع غير متاحة"
                }
            
            # التحقق من المبلغ
            validation = self.validate_payment_amount(payment_method, amount)
            if not validation['valid']:
                return {"success": False, "message": validation['message']}
            
            # سعر الصرف للدولار
            final_amount = amount
            exchange_rate = 13000  # يمكن جعله متغيراً
            
            if payment_method == 'sham_cash_usd':
                final_amount = amount * exchange_rate
            
            # إنشاء المعاملة
            transaction = Transaction(
                user_id=user_id,
                type='charge',
                amount=final_amount,
                payment_method=payment_method,
                transaction_id=transaction_id,
                status='pending'
            )
            
            tx_id = TransactionModel.create(transaction)
            if not tx_id:
                return {"success": False, "message": "خطأ في إنشاء المعاملة"}
            
            # رقم الطلب الشهري
            month = datetime.now().strftime('%Y%m')
            order_number = f"{month}{tx_id:04d}"
            
            return {
                "success": True,
                "transaction_id": tx_id,
                "order_number": order_number,
                "amount": final_amount,
                "message": "تم إرسال طلب الشحن للمراجعة"
            }
        except Exception as e:
            logger.error(f"خطأ في create_deposit_request: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def create_withdraw_request(self, user_id: int, amount: int, 
                                account_details: str) -> Dict[str, Any]:
        """إنشاء طلب سحب"""
        try:
            # التحقق من الرصيد
            from services.user_service import UserService
            user_service = UserService()
            user_balance = user_service.get_user_balance(user_id)
            
            if amount > user_balance:
                return {"success": False, "message": "الرصيد غير كافي"}
            
            # تطبيق نسبة السحب
            from services.system_service import SystemService
            system_service = SystemService()
            withdraw_percentage = system_service.get_setting('withdraw_percentage', '0')
            
            net_amount = amount
            deduction = 0
            
            if withdraw_percentage and withdraw_percentage != '0':
                percentage = int(withdraw_percentage)
                deduction = int(amount * percentage / 100)
                net_amount = amount - deduction
            
            # خصم المبلغ من الرصيد
            result = user_service.update_balance(user_id, amount, 'subtract')
            if not result['success']:
                return result
            
            # إنشاء المعاملة
            transaction = Transaction(
                user_id=user_id,
                type='withdraw',
                amount=amount,
                payment_method='withdraw',
                account_number=account_details,
                status='pending',
                notes=f"الصافي: {net_amount:,} ليرة (خصم: {deduction:,} ليرة)"
            )
            
            tx_id = TransactionModel.create(transaction)
            if not tx_id:
                # إرجاع الرصيد في حالة الخطأ
                user_service.update_balance(user_id, amount, 'add')
                return {"success": False, "message": "خطأ في إنشاء المعاملة"}
            
            return {
                "success": True,
                "transaction_id": tx_id,
                "amount": amount,
                "net_amount": net_amount,
                "deduction": deduction,
                "new_balance": result['new_balance'],
                "message": "تم إرسال طلب السحب للمراجعة"
            }
        except Exception as e:
            logger.error(f"خطأ في create_withdraw_request: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def process_transaction(self, transaction_id: int, action: str, 
                           admin_id: int = None) -> Dict[str, Any]:
        """معالجة معاملة (قبول/رفض)"""
        try:
            transaction = TransactionModel.get(transaction_id)
            if not transaction:
                return {"success": False, "message": "المعاملة غير موجودة"}
            
            if transaction.status != 'pending':
                return {"success": False, "message": f"المعاملة تم معالجتها مسبقاً ({transaction.status})"}
            
            from services.user_service import UserService
            user_service = UserService()
            
            if action == 'approve':
                new_status = 'approved'
                notes = f"تمت الموافقة بواسطة {admin_id}" if admin_id else "تمت الموافقة تلقائياً"
                
                if transaction.type == 'charge':
                    # إضافة الرصيد للمستخدم
                    user_service.update_balance(transaction.user_id, transaction.amount, 'add')
                    
                elif transaction.type == 'withdraw':
                    # للسحب، الرصيد تم خصمه مسبقاً
                    pass
            
            elif action == 'reject':
                new_status = 'rejected'
                notes = f"تم الرفض بواسطة {admin_id}" if admin_id else "تم الرفض تلقائياً"
                
                if transaction.type == 'withdraw':
                    # إرجاع الرصيد للمستخدم
                    user_service.update_balance(transaction.user_id, transaction.amount, 'add')
            
            else:
                return {"success": False, "message": "إجراء غير معروف"}
            
            # تحديث حالة المعاملة
            TransactionModel.update_status(transaction_id, new_status, notes)
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "new_status": new_status,
                "message": f"تم {new_status} المعاملة #{transaction_id}"
            }
        except Exception as e:
            logger.error(f"خطأ في process_transaction: {e}")
            return {"success": False, "message": "خطأ داخلي"}
    
    @performance_logger
    def get_daily_report(self, date_str: str = None) -> Dict[str, Any]:
        """تقرير يومي للمعاملات"""
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        return TransactionModel.get_daily_transactions(date_str)
    
    @performance_logger
    def get_pending_transactions(self, transaction_type: str = None) -> List[Transaction]:
        """جلب المعاملات المعلقة"""
        return TransactionModel.get_pending_transactions(transaction_type)