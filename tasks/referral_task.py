"""
مهام نظام الإحالات المجدولة
"""

from datetime import datetime
from core.logger import get_logger
from services.referral_service import ReferralService

logger = get_logger(__name__)


def distribute_referral_commissions():
    """توزيع عمولات الإحالات"""
    try:
        referral_service = ReferralService()
        
        # توزيع العمولات
        result = referral_service.distribute_commissions()
        
        if result['success']:
            logger.info(f"✅ تم توزيع عمولات الإحالات: {result['total_distributed']:,} ليرة على {result['users_count']} مستخدم")
            
            # إرسال تقرير
            if result['total_distributed'] > 0:
                report_msg = f"💰 **تقرير توزيع عمولات الإحالات**\n\n"
                report_msg += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                report_msg += f"💸 المبلغ الموزع: {result['total_distributed']:,} ليرة\n"
                report_msg += f"👥 عدد المستفيدين: {result['users_count']}\n\n"
                
                # عرض أفضل 5 مستفيدين
                if result['users']:
                    report_msg += "🏆 **أفضل المستفيدين:**\n"
                    for i, user in enumerate(result['users'][:5], 1):
                        report_msg += f"{i}. `{user['user_id']}` - {user['amount']:,} ليرة ({user['eligible_refs']} إحالات)\n"
                
                # إرسال التقرير
                from handlers.commands import bot
                from core.config import CHANNELS
                
                try:
                    bot.send_message(
                        CHANNELS["ADMIN_LOGS"],
                        report_msg,
                        parse_mode="Markdown"
                    )
                except:
                    pass
        else:
            logger.info(f"⏸️ لا توجد عمولات للتوزيع: {result['message']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ خطأ في توزيع عمولات الإحالات: {e}")
        return {
            "success": False,
            "message": f"خطأ: {str(e)}"
        }


def check_referral_distribution_time():
    """التحقق من موعد توزيع عمولات الإحالات"""
    try:
        referral_service = ReferralService()
        settings = referral_service.get_settings()
        
        if not settings or not settings.next_distribution:
            return False
        
        # التحقق إذا حان وقت التوزيع
        now = datetime.now()
        try:
            distribution_time = datetime.strptime(settings.next_distribution, '%Y-%m-%d %H:%M')
            
            if now >= distribution_time:
                # توزيع العمولات
                distribute_referral_commissions()
                
                # تحديث موعد التوزيع التالي (شهرياً)
                next_month = now.replace(day=1) + timedelta(days=32)
                next_month = next_month.replace(day=1, hour=23, minute=59, second=0)
                
                referral_service.update_settings(
                    next_distribution=next_month.strftime('%Y-%m-%d %H:%M')
                )
                
                return True
        
        except ValueError:
            logger.warning("❌ تنسيق وقت توزيع الإحالات غير صحيح")
        
        return False
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من موعد التوزيع: {e}")
        return False


def setup_referral_task(scheduler):
    """إعداد مهام نظام الإحالات المجدولة"""
    try:
        # التحقق من موعد التوزيع كل ساعة
        scheduler.add_job(
            check_referral_distribution_time,
            'interval',
            hours=1,
            id='check_referral_distribution',
            name='التحقق من توزيع الإحالات'
        )
        
        # توزيع عمولات الإحالات يومياً في منتصف الليل (كاحتياطي)
        scheduler.add_job(
            distribute_referral_commissions,
            'cron',
            hour=0,
            minute=5,
            id='daily_referral_distribution',
            name='توزيع الإحالات اليومي'
        )
        
        logger.info("✅ تم جدولة مهام نظام الإحالات")
        
    except Exception as e:
        logger.error(f"❌ خطأ في إعداد مهام الإحالات: {e}")