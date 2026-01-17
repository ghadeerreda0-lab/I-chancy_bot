"""
نموذج نظام الهدايا والأكواد
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import json

from core.database import db
from core.security import token_generator
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GiftCode:
    """نموذج كود الهدية"""
    code: str
    amount: int
    max_uses: int = 1
    used_count: int = 0
    created_by: int = None
    created_at: str = None
    expires_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """التحقق من صلاحية الكود"""
        now = datetime.now()
        
        # التحقق من عدد الاستخدامات
        if self.used_count >= self.max_uses:
            return False
        
        # التحقق من تاريخ الانتهاء
        if self.expires_at:
            expiry_date = datetime.fromisoformat(self.expires_at)
            if now > expiry_date:
                return False
        
        return True
    
    def increment_usage(self) -> bool:
        """زيادة عداد الاستخدام"""
        if self.used_count < self.max_uses:
            self.used_count += 1
            return True
        return False


@dataclass
class GiftTransaction:
    """نموذج معاملة الإهداء"""
    sender_id: int
    receiver_id: int
    original_amount: int
    net_amount: int
    gift_percentage: int = 0
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class GiftModel:
    """نموذج إدارة الهدايا"""
    
    @staticmethod
    def create_code(amount: int, max_uses: int = 1, expires_days: int = 30, 
                    created_by: int = None) -> Optional[GiftCode]:
        """إنشاء كود هدية جديد"""
        try:
            # توليد كود فريد
            code = token_generator.generate_gift_code()
            
            # حساب تاريخ الانتهاء
            expires_at = None
            if expires_days > 0:
                expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
            
            query = """
                INSERT INTO gift_codes 
                (code, amount, max_uses, created_by, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            
            db.execute_query(query, (
                code, amount, max_uses, created_by, expires_at,
                datetime.now().isoformat()
            ))
            
            gift_code = GiftCode(
                code=code,
                amount=amount,
                max_uses=max_uses,
                created_by=created_by,
                expires_at=expires_at
            )
            
            logger.info(f"تم إنشاء كود هدية: {code} بقيمة {amount}")
            return gift_code
        except Exception as e:
            logger.error(f"خطأ في إنشاء كود هدية: {e}")
            return None
    
    @staticmethod
    def get_code(code_str: str) -> Optional[GiftCode]:
        """جلب كود هدية"""
        query = """
            SELECT code, amount, max_uses, used_count, 
                   created_by, created_at, expires_at
            FROM gift_codes WHERE code = ?
        """
        
        result = db.fetch_one(query, (code_str,))
        if result:
            return GiftCode(
                code=result['code'],
                amount=result['amount'],
                max_uses=result['max_uses'],
                used_count=result['used_count'],
                created_by=result['created_by'],
                created_at=result['created_at'],
                expires_at=result['expires_at']
            )
        return None
    
    @staticmethod
    def use_code(code_str: str, user_id: int) -> bool:
        """استخدام كود هدية"""
        try:
            # التحقق إذا تم استخدامه مسبقاً
            check_query = """
                SELECT 1 FROM gift_code_usage 
                WHERE code = ? AND user_id = ?
            """
            check_result = db.fetch_one(check_query, (code_str, user_id))
            if check_result:
                logger.warning(f"المستخدم {user_id} حاول استخدام كود مستخدم مسبقاً: {code_str}")
                return False
            
            # زيادة عداد الاستخدام
            update_query = """
                UPDATE gift_codes 
                SET used_count = used_count + 1
                WHERE code = ? AND used_count < max_uses
            """
            db.execute_query(update_query, (code_str,))
            
            # تسجيل الاستخدام
            usage_query = """
                INSERT INTO gift_code_usage (code, user_id, used_at)
                VALUES (?, ?, datetime('now'))
            """
            db.execute_query(usage_query, (code_str, user_id))
            
            logger.info(f"المستخدم {user_id} استخدم كود الهدية: {code_str}")
            return True
        except Exception as e:
            logger.error(f"خطأ في استخدام كود هدية: {e}")
            return False
    
    @staticmethod
    def get_user_used_codes(user_id: int) -> List[str]:
        """جلب الأكواد التي استخدمها المستخدم"""
        query = """
            SELECT code FROM gift_code_usage 
            WHERE user_id = ? 
            ORDER BY used_at DESC
        """
        
        results = db.fetch_all(query, (user_id,))
        return [row['code'] for row in results]
    
    @staticmethod
    def create_gift_transaction(transaction: GiftTransaction) -> bool:
        """إنشاء معاملة إهداء"""
        try:
            query = """
                INSERT INTO gift_transactions 
                (sender_id, receiver_id, original_amount, net_amount, 
                 gift_percentage, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            
            db.execute_query(query, (
                transaction.sender_id,
                transaction.receiver_id,
                transaction.original_amount,
                transaction.net_amount,
                transaction.gift_percentage,
                transaction.created_at
            ))
            
            logger.info(f"تم إنشاء معاملة إهداء: {transaction.sender_id} → {transaction.receiver_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إنشاء معاملة إهداء: {e}")
            return False
    
    @staticmethod
    def get_user_gift_transactions(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """جلب معاملات الإهداء للمستخدم"""
        # كمرسل
        sent_query = """
            SELECT sender_id, receiver_id, original_amount, net_amount,
                   gift_percentage, created_at
            FROM gift_transactions 
            WHERE sender_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        # كمستلم
        received_query = """
            SELECT sender_id, receiver_id, original_amount, net_amount,
                   gift_percentage, created_at
            FROM gift_transactions 
            WHERE receiver_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        sent_results = db.fetch_all(sent_query, (user_id, limit))
        received_results = db.fetch_all(received_query, (user_id, limit))
        
        transactions = []
        
        for row in sent_results:
            transactions.append({
                'type': 'sent',
                'partner_id': row['receiver_id'],
                'original_amount': row['original_amount'],
                'net_amount': row['net_amount'],
                'gift_percentage': row['gift_percentage'],
                'created_at': row['created_at']
            })
        
        for row in received_results:
            transactions.append({
                'type': 'received',
                'partner_id': row['sender_id'],
                'original_amount': row['original_amount'],
                'net_amount': row['net_amount'],
                'gift_percentage': row['gift_percentage'],
                'created_at': row['created_at']
            })
        
        # ترتيب حسب التاريخ
        transactions.sort(key=lambda x: x['created_at'], reverse=True)
        return transactions[:limit]
    
    @staticmethod
    def get_all_codes(limit: int = 100) -> List[GiftCode]:
        """جلب جميع أكواد الهدايا"""
        query = """
            SELECT code, amount, max_uses, used_count, 
                   created_by, created_at, expires_at
            FROM gift_codes 
            ORDER BY created_at DESC
            LIMIT ?
        """
        
        results = db.fetch_all(query, (limit,))
        return [
            GiftCode(
                code=row['code'],
                amount=row['amount'],
                max_uses=row['max_uses'],
                used_count=row['used_count'],
                created_by=row['created_by'],
                created_at=row['created_at'],
                expires_at=row['expires_at']
            ) for row in results
        ]
    
    @staticmethod
    def delete_expired_codes() -> int:
        """حذف الأكواد المنتهية الصلاحية"""
        try:
            query = """
                DELETE FROM gift_codes 
                WHERE expires_at IS NOT NULL 
                AND expires_at < datetime('now')
            """
            
            cursor = db.execute_query(query)
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                logger.info(f"تم حذف {deleted_count} كود منتهي الصلاحية")
            
            return deleted_count
        except Exception as e:
            logger.error(f"خطأ في حذف الأكواد المنتهية: {e}")
            return 0