"""
نموذج المعاملات المالية
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import json

from core.database import db
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Transaction:
    """نموذج بيانات المعاملة"""
    id: int = None
    user_id: int = None
    type: str = None  # 'charge', 'withdraw', 'gift_sent', 'gift_received', 'referral', 'bonus'
    amount: int = 0
    payment_method: str = None
    transaction_id: str = None
    account_number: str = None
    status: str = 'pending'  # 'pending', 'approved', 'rejected', 'completed'
    created_at: str = None
    notes: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return asdict(self)
    
    def to_json(self) -> str:
        """تحويل إلى JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class TransactionModel:
    """نموذج إدارة المعاملات"""
    
    @staticmethod
    def create(transaction: Transaction) -> Optional[int]:
        """إنشاء معاملة جديدة"""
        try:
            query = """
                INSERT INTO transactions 
                (user_id, type, amount, payment_method, transaction_id, 
                 account_number, status, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            tx_id = db.insert_and_get_id(
                query,
                (
                    transaction.user_id,
                    transaction.type,
                    transaction.amount,
                    transaction.payment_method,
                    transaction.transaction_id,
                    transaction.account_number,
                    transaction.status,
                    transaction.created_at or datetime.now().isoformat(),
                    transaction.notes
                )
            )
            
            logger.debug(f"تم إنشاء معاملة #{tx_id} للمستخدم {transaction.user_id}")
            return tx_id
        except Exception as e:
            logger.error(f"خطأ في إنشاء معاملة: {e}")
            return None
    
    @staticmethod
    def get(transaction_id: int) -> Optional[Transaction]:
        """جلب معاملة"""
        query = """
            SELECT id, user_id, type, amount, payment_method, transaction_id,
                   account_number, status, created_at, notes
            FROM transactions WHERE id = ?
        """
        
        result = db.fetch_one(query, (transaction_id,))
        if result:
            return Transaction(
                id=result['id'],
                user_id=result['user_id'],
                type=result['type'],
                amount=result['amount'],
                payment_method=result['payment_method'],
                transaction_id=result['transaction_id'],
                account_number=result['account_number'],
                status=result['status'],
                created_at=result['created_at'],
                notes=result['notes']
            )
        return None
    
    @staticmethod
    def update_status(transaction_id: int, status: str, notes: str = None) -> bool:
        """تحديث حالة المعاملة"""
        try:
            query = """
                UPDATE transactions 
                SET status = ?, notes = COALESCE(?, notes)
                WHERE id = ?
            """
            db.execute_query(query, (status, notes, transaction_id))
            
            logger.info(f"تم تحديث حالة المعاملة #{transaction_id} إلى {status}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث حالة المعاملة #{transaction_id}: {e}")
            return False
    
    @staticmethod
    def get_user_transactions(user_id: int, limit: int = 50, offset: int = 0) -> List[Transaction]:
        """جلب معاملات مستخدم"""
        query = """
            SELECT id, user_id, type, amount, payment_method, transaction_id,
                   account_number, status, created_at, notes
            FROM transactions 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        
        results = db.fetch_all(query, (user_id, limit, offset))
        return [
            Transaction(
                id=row['id'],
                user_id=row['user_id'],
                type=row['type'],
                amount=row['amount'],
                payment_method=row['payment_method'],
                transaction_id=row['transaction_id'],
                account_number=row['account_number'],
                status=row['status'],
                created_at=row['created_at'],
                notes=row['notes']
            ) for row in results
        ]
    
    @staticmethod
    def get_pending_transactions(transaction_type: str = None) -> List[Transaction]:
        """جلب المعاملات المعلقة"""
        if transaction_type:
            query = """
                SELECT id, user_id, type, amount, payment_method, transaction_id,
                       account_number, status, created_at, notes
                FROM transactions 
                WHERE status = 'pending' AND type = ?
                ORDER BY created_at ASC
            """
            results = db.fetch_all(query, (transaction_type,))
        else:
            query = """
                SELECT id, user_id, type, amount, payment_method, transaction_id,
                       account_number, status, created_at, notes
                FROM transactions 
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """
            results = db.fetch_all(query)
        
        return [
            Transaction(
                id=row['id'],
                user_id=row['user_id'],
                type=row['type'],
                amount=row['amount'],
                payment_method=row['payment_method'],
                transaction_id=row['transaction_id'],
                account_number=row['account_number'],
                status=row['status'],
                created_at=row['created_at'],
                notes=row['notes']
            ) for row in results
        ]
    
    @staticmethod
    def get_daily_transactions(date_str: str) -> Dict[str, Any]:
        """جلب معاملات يوم معين"""
        # الشحنات
        deposit_query = """
            SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
            FROM transactions 
            WHERE type = 'charge' AND status = 'approved' 
            AND date(created_at) = ?
        """
        deposit_result = db.fetch_one(deposit_query, (date_str,))
        
        # السحوبات
        withdraw_query = """
            SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
            FROM transactions 
            WHERE type = 'withdraw' AND status = 'approved'
            AND date(created_at) = ?
        """
        withdraw_result = db.fetch_one(withdraw_query, (date_str,))
        
        # المعلقة
        pending_query = """
            SELECT COUNT(*) as count
            FROM transactions 
            WHERE status = 'pending' AND date(created_at) = ?
        """
        pending_result = db.fetch_one(pending_query, (date_str,))
        
        return {
            'date': date_str,
            'total_deposit': deposit_result['total'] if deposit_result else 0,
            'deposit_count': deposit_result['count'] if deposit_result else 0,
            'total_withdraw': withdraw_result['total'] if withdraw_result else 0,
            'withdraw_count': withdraw_result['count'] if withdraw_result else 0,
            'pending_count': pending_result['count'] if pending_result else 0
        }
    
    @staticmethod
    def get_user_summary(user_id: int) -> Dict[str, Any]:
        """ملخص معاملات المستخدم"""
        # إجمالي الإيداع
        deposit_query = """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions 
            WHERE user_id = ? AND type = 'charge' AND status = 'approved'
        """
        deposit_result = db.fetch_one(deposit_query, (user_id,))
        
        # إجمالي السحب
        withdraw_query = """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions 
            WHERE user_id = ? AND type = 'withdraw' AND status = 'approved'
        """
        withdraw_result = db.fetch_one(withdraw_query, (user_id,))
        
        # عدد المعاملات
        count_query = """
            SELECT COUNT(*) as count
            FROM transactions 
            WHERE user_id = ?
        """
        count_result = db.fetch_one(count_query, (user_id,))
        
        return {
            'total_deposit': deposit_result['total'] if deposit_result else 0,
            'total_withdraw': withdraw_result['total'] if withdraw_result else 0,
            'total_transactions': count_result['count'] if count_result else 0,
            'net_flow': (deposit_result['total'] if deposit_result else 0) - 
                       (withdraw_result['total'] if withdraw_result else 0)
        }