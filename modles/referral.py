"""
نموذج نظام الإحالات
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
import json

from core.database import db
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Referral:
    """نموذج بيانات الإحالة"""
    id: int = None
    referrer_id: int = None
    referred_id: int = None
    amount_charged: int = 0
    commission_earned: int = 0
    is_active: bool = False
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return asdict(self)
    
    def mark_active(self, amount: int):
        """تحديث الإحالة كنشطة"""
        self.is_active = True
        self.amount_charged = amount


@dataclass
class ReferralSettings:
    """نموذج إعدادات الإحالات"""
    commission_rate: int = 10
    bonus_amount: int = 2000
    min_active_referrals: int = 5
    min_charge_amount: int = 100000
    next_distribution: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return asdict(self)


class ReferralModel:
    """نموذج إدارة الإحالات"""
    
    @staticmethod
    def create(referrer_id: int, referred_id: int) -> bool:
        """إنشاء إحالة جديدة"""
        try:
            query = """
                INSERT INTO referrals (referrer_id, referred_id, created_at)
                VALUES (?, ?, datetime('now'))
            """
            
            db.execute_query(query, (referrer_id, referred_id))
            
            logger.info(f"تم إنشاء إحالة: {referrer_id} → {referred_id}")
            return True
        except Exception as e:
            logger.error(f"خطأ في إنشاء إحالة: {e}")
            return False
    
    @staticmethod
    def get_referrals(referrer_id: int) -> List[Referral]:
        """جلب إحالات شخص معين"""
        query = """
            SELECT id, referrer_id, referred_id, amount_charged, 
                   commission_earned, is_active, created_at
            FROM referrals 
            WHERE referrer_id = ?
            ORDER BY created_at DESC
        """
        
        results = db.fetch_all(query, (referrer_id,))
        return [
            Referral(
                id=row['id'],
                referrer_id=row['referrer_id'],
                referred_id=row['referred_id'],
                amount_charged=row['amount_charged'],
                commission_earned=row['commission_earned'],
                is_active=bool(row['is_active']),
                created_at=row['created_at']
            ) for row in results
        ]
    
    @staticmethod
    def get_referrer(referred_id: int) -> Optional[int]:
        """جلب الشخص الذي أحاله"""
        query = "SELECT referrer_id FROM referrals WHERE referred_id = ?"
        result = db.fetch_one(query, (referred_id,))
        return result['referrer_id'] if result else None
    
    @staticmethod
    def update_charged_amount(referred_id: int, amount: int) -> bool:
        """تحديث المبلغ المحروق للإحالة"""
        try:
            # تحديث كحالة نشطة إذا تجاوز الحد
            from .user import UserModel
            user = UserModel.get(referred_id)
            if user and user.total_deposit >= 10000:
                query = """
                    UPDATE referrals 
                    SET amount_charged = amount_charged + ?, 
                        is_active = 1
                    WHERE referred_id = ?
                """
            else:
                query = """
                    UPDATE referrals 
                    SET amount_charged = amount_charged + ?
                    WHERE referred_id = ?
                """
            
            db.execute_query(query, (amount, referred_id))
            
            logger.debug(f"تم تحديث مبلغ الإحالة للمستخدم {referred_id}: +{amount}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث مبلغ الإحالة: {e}")
            return False
    
    @staticmethod
    def get_active_referrals_count(referrer_id: int) -> Tuple[int, int]:
        """جلب عدد الإحالات النشطة والإجمالية"""
        query_total = "SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?"
        query_active = """
            SELECT COUNT(*) as count FROM referrals 
            WHERE referrer_id = ? AND is_active = 1
        """
        
        total_result = db.fetch_one(query_total, (referrer_id,))
        active_result = db.fetch_one(query_active, (referrer_id,))
        
        total = total_result['count'] if total_result else 0
        active = active_result['count'] if active_result else 0
        
        return total, active
    
    @staticmethod
    def get_top_referrers(limit: int = 10) -> List[Dict[str, Any]]:
        """جلب أفضل المحيلين"""
        query = """
            SELECT r.referrer_id, 
                   COUNT(*) as total_refs,
                   SUM(CASE WHEN r.is_active = 1 THEN 1 ELSE 0 END) as active_refs,
                   SUM(r.commission_earned) as total_commission,
                   u.total_deposit as referrer_deposit
            FROM referrals r
            LEFT JOIN users u ON r.referrer_id = u.user_id
            GROUP BY r.referrer_id
            ORDER BY total_refs DESC
            LIMIT ?
        """
        
        results = db.fetch_all(query, (limit,))
        return [
            {
                'referrer_id': row['referrer_id'],
                'total_refs': row['total_refs'],
                'active_refs': row['active_refs'],
                'total_commission': row['total_commission'],
                'referrer_deposit': row['referrer_deposit']
            } for row in results
        ]
    
    @staticmethod
    def get_settings() -> Optional[ReferralSettings]:
        """جلب إعدادات الإحالات"""
        query = """
            SELECT commission_rate, bonus_amount, min_active_referrals,
                   min_charge_amount, next_distribution, updated_at
            FROM referral_settings 
            ORDER BY id DESC LIMIT 1
        """
        
        result = db.fetch_one(query)
        if result:
            return ReferralSettings(
                commission_rate=result['commission_rate'],
                bonus_amount=result['bonus_amount'],
                min_active_referrals=result['min_active_referrals'],
                min_charge_amount=result['min_charge_amount'],
                next_distribution=result['next_distribution'],
                updated_at=result['updated_at']
            )
        
        return None
    
    @staticmethod
    def update_settings(settings: ReferralSettings) -> bool:
        """تحديث إعدادات الإحالات"""
        try:
            query = """
                INSERT OR REPLACE INTO referral_settings 
                (commission_rate, bonus_amount, min_active_referrals,
                 min_charge_amount, next_distribution, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """
            
            db.execute_query(query, (
                settings.commission_rate,
                settings.bonus_amount,
                settings.min_active_referrals,
                settings.min_charge_amount,
                settings.next_distribution
            ))
            
            logger.info("تم تحديث إعدادات الإحالات")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث إعدادات الإحالات: {e}")
            return False
    
    @staticmethod
    def calculate_commissions() -> List[Dict[str, Any]]:
        """حساب العمولات المستحقة"""
        settings = ReferralModel.get_settings()
        if not settings:
            return []
        
        # المستخدمون الذين يستحقون العمولة
        query = """
            SELECT r.referrer_id, 
                   COUNT(*) as eligible_refs,
                   SUM(r.amount_charged) as total_charged
            FROM referrals r
            WHERE r.is_active = 1 
            AND r.amount_charged >= ?
            GROUP BY r.referrer_id
            HAVING COUNT(*) >= ?
        """
        
        results = db.fetch_all(query, (
            settings.min_charge_amount,
            settings.min_active_referrals
        ))
        
        commissions = []
        for row in results:
            referrer_id = row['referrer_id']
            eligible_refs = row['eligible_refs']
            total_charged = row['total_charged']
            
            # حساب العمولة
            commission = int(total_charged * settings.commission_rate / 100)
            bonus = eligible_refs * settings.bonus_amount
            total_commission = commission + bonus
            
            if total_commission > 0:
                commissions.append({
                    'referrer_id': referrer_id,
                    'eligible_refs': eligible_refs,
                    'total_charged': total_charged,
                    'commission': commission,
                    'bonus': bonus,
                    'total_commission': total_commission
                })
        
        return commissions