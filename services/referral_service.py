"""
خدمات نظام الإحالات - سرعة فائقة
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import time

from core.database import db
from core.cache import cache
from core.security import token_generator
from core.logger import get_logger, performance_logger
from models.referral import Referral, ReferralSettings, ReferralModel
from models.user import UserModel
from models.transaction import TransactionModel

logger = get_logger(__name__)


class ReferralService:
    """خدمات نظام الإحالات"""
    
    def __init__(self):
        self.cache = cache
        self.init_default_settings()
    
    @performance_logger
    def init_default_settings(self):
        """تهيئة الإعدادات الافتراضية"""
        try:
            settings = ReferralModel.get_settings()
            if not settings:
                default_settings = ReferralSettings()
                ReferralModel.update_settings(default_settings)
                logger.info("تم تهيئة إعدادات الإحالات الافتراضية")
        except Exception as e:
            logger.error(f"خطأ في تهيئة إعدادات الإحالات: {e}")
    
    @performance_logger
    def get_settings(self) -> Optional[ReferralSettings]:
        """جلب إعدادات الإحالات"""
        cache_key = "referral_settings"
        cached = self.cache.get_setting(cache_key)
        if cached:
            return ReferralSettings(**cached)
        
        settings = ReferralModel.get_settings()
        if settings:
            self.cache.set_setting(cache_key, settings.to_dict(), ttl=60)
        
        return settings
    
    @performance_logger
    def update_settings(self, **kwargs) -> bool:
        """تحديث إعدادات الإحالات"""
        try:
            current_settings = self.get_settings()
            if not current_settings:
                current_settings = ReferralSettings()
            
            # تحديث القيم
            if 'commission_rate' in kwargs:
                current_settings.commission_rate = kwargs['commission_rate']
            
            if 'bonus_amount' in kwargs:
                current_settings.bonus_amount = kwargs['bonus_amount']
            
            if 'min_active_referrals' in kwargs:
                current_settings.min_active_referrals = kwargs['min_active_referrals']
            
            if 'min_charge_amount' in kwargs:
                current_settings.min_charge_amount = kwargs['min_charge_amount']
            
            if 'next_distribution' in kwargs:
                current_settings.next_distribution = kwargs['next_distribution']
            
            # الحفظ
            if ReferralModel.update_settings(current_settings):
                # إبطال الكاش
                self.cache.delete_setting("referral_settings")
                
                logger.info("تم تحديث إعدادات الإحالات")
                return True
            
            return False
        except Exception as e:
            logger.error(f"خطأ في تحديث إعدادات الإحالات: {e}")
            return False
    
    @performance_logger
    def create_referral(self, referrer_id: int, referred_id: int) -> bool:
        """إنشاء إحالة جديدة"""
        # التحقق من عدم إحالة النفس
        if referrer_id == referred_id:
            return False
        
        # التحقق من وجود إحالة مسبقة
        existing = ReferralModel.get_referrer(referred_id)
        if existing:
            return False
        
        return ReferralModel.create(referrer_id, referred_id)
    
    @performance_logger
    def get_user_referrals(self, user_id: int) -> List[Dict[str, Any]]:
        """جلب إحالات مستخدم"""
        referrals = ReferralModel.get_referrals(user_id)
        
        result = []
        for referral in referrals:
            # جلب معلومات المستخدم المحال
            referred_user = UserModel.get(referral.referred_id)
            if referred_user:
                result.append({
                    "referred_id": referral.referred_id,
                    "is_active": referral.is_active,
                    "amount_charged": referral.amount_charged,
                    "created_at": referral.created_at,
                    "referred_user_created": referred_user.created_at,
                    "referred_user_deposit": referred_user.total_deposit
                })
        
        return result
    
    @performance_logger
    def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """إحصائيات الإحالات لمستخدم"""
        settings = self.get_settings()
        if not settings:
            return {}
        
        referrals = self.get_user_referrals(user_id)
        total_refs = len(referrals)
        active_refs = sum(1 for r in referrals if r['is_active'])
        
        # حساب الأرباح المستحقة
        eligible_refs = [
            r for r in referrals 
            if r['is_active'] and r['amount_charged'] >= settings.min_charge_amount
        ]
        
        total_commission = 0
        if len(eligible_refs) >= settings.min_active_referrals:
            total_charged = sum(r['amount_charged'] for r in eligible_refs)
            commission = int(total_charged * settings.commission_rate / 100)
            bonus = len(eligible_refs) * settings.bonus_amount
            total_commission = commission + bonus
        
        # جلب رابط الإحالة
        user = UserModel.get(user_id)
        
        return {
            "total_referrals": total_refs,
            "active_referrals": active_refs,
            "eligible_referrals": len(eligible_refs),
            "total_commission": total_commission,
            "referral_code": user.referral_code if user else None,
            "next_distribution": settings.next_distribution,
            "min_requirements": {
                "active_referrals": settings.min_active_referrals,
                "min_charge": settings.min_charge_amount,
                "commission_rate": settings.commission_rate,
                "bonus_amount": settings.bonus_amount
            }
        }
    
    @performance_logger
    def record_deposit_for_referral(self, user_id: int, amount: int):
        """تسجيل إيداع للإحالة"""
        try:
            # تحديث مبلغ الإحالة
            ReferralModel.update_charged_amount(user_id, amount)
            
            # إضافة عمولة للمحيل إذا كانت مؤهلة
            referrer_id = ReferralModel.get_referrer(user_id)
            if referrer_id:
                self._check_and_award_commission(referrer_id, user_id, amount)
            
            logger.debug(f"تم تسجيل إيداع {amount} للإحالة للمستخدم {user_id}")
        except Exception as e:
            logger.error(f"خطأ في record_deposit_for_referral: {e}")
    
    @performance_logger
    def _check_and_award_commission(self, referrer_id: int, referred_id: int, amount: int):
        """التحقق ومنح العمولة"""
        try:
            settings = self.get_settings()
            if not settings:
                return
            
            # جلب إحصائيات المحيل
            stats = self.get_referral_stats(referrer_id)
            
            # التحقق إذا أصبح مؤهلاً للعمولة
            if (stats['eligible_referrals'] >= settings.min_active_referrals and
                amount >= settings.min_charge_amount):
                
                # حساب العمولة
                commission = int(amount * settings.commission_rate / 100)
                bonus = settings.bonus_amount
                total_award = commission + bonus
                
                # إضافة الرصيد للمحيل
                from services.user_service import UserService
                user_service = UserService()
                user_service.update_balance(referrer_id, total_award, 'add')
                
                # تسجيل المعاملة
                transaction = TransactionModel()
                transaction.create(
                    user_id=referrer_id,
                    type='referral',
                    amount=total_award,
                    notes=f"عمولة إحالة من {referred_id} (شحن: {amount:,})"
                )
                
                logger.info(f"تم منح عمولة إحالة {total_award} للمستخدم {referrer_id}")
        except Exception as e:
            logger.error(f"خطأ في _check_and_award_commission: {e}")
    
    @performance_logger
    def distribute_commissions(self) -> Dict[str, Any]:
        """توزيع عمولات الإحالات"""
        try:
            commissions = ReferralModel.calculate_commissions()
            if not commissions:
                return {
                    "success": False,
                    "message": "لا توجد عمولات مستحقة للتوزيع",
                    "distributed": 0,
                    "users": 0
                }
            
            total_distributed = 0
            distributed_users = []
            
            from services.user_service import UserService
            user_service = UserService()
            
            for commission in commissions:
                referrer_id = commission['referrer_id']
                total_commission = commission['total_commission']
                
                # إضافة الرصيد
                result = user_service.update_balance(referrer_id, total_commission, 'add')
                if result['success']:
                    total_distributed += total_commission
                    distributed_users.append({
                        "user_id": referrer_id,
                        "amount": total_commission,
                        "eligible_refs": commission['eligible_refs'],
                        "total_charged": commission['total_charged']
                    })
                    
                    # تسجيل المعاملة
                    transaction = TransactionModel()
                    transaction.create(
                        user_id=referrer_id,
                        type='referral',
                        amount=total_commission,
                        notes=f"توزيع عمولات إحالة تلقائي ({commission['eligible_refs']} إحالات)"
                    )
            
            return {
                "success": True,
                "message": f"تم توزيع {total_distributed:,} ليرة على {len(distributed_users)} مستخدم",
                "total_distributed": total_distributed,
                "users_count": len(distributed_users),
                "users": distributed_users
            }
        except Exception as e:
            logger.error(f"خطأ في distribute_commissions: {e}")
            return {
                "success": False,
                "message": f"خطأ في التوزيع: {str(e)}",
                "distributed": 0,
                "users": 0
            }
    
    @performance_logger
    def get_top_referrers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """جلب أفضل المحيلين"""
        return ReferralModel.get_top_referrers(limit)
    
    @performance_logger
    def generate_referral_link(self, user_id: int, bot_username: str) -> str:
        """توليد رابط إحالة"""
        user = UserModel.get(user_id)
        if not user or not user.referral_code:
            return ""
        
        return f"https://t.me/{bot_username}?start=ref_{user.referral_code}"