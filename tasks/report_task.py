"""
مهمة التقارير التلقائية
"""

from datetime import datetime, timedelta
from core.config import REPORT_CONFIG, CHANNELS
from core.logger import get_logger
from services.payment_service import PaymentService
from services.user_service import UserService

logger = get_logger(__name__)


def generate_daily_report():
    """توليد تقرير يومي"""
    try:
        payment_service = PaymentService()
        user_service = UserService()
        
        # تاريخ اليوم
        today = datetime.now().strftime('%Y-%m-%d')
        
        # جلب تقرير اليوم
        report = payment_service.get_daily_report(today)
        
        # إحصائيات المستخدمين
        user_stats = user_service.get_system_stats()
        
        # بناء الرسالة
        msg = f"📊 **تقرير اليوم - {today}**\n\n"
        
        msg += "👥 **المستخدمون:**\n"
        msg += f"• 👤 مستخدمين جدد: {report.get('new_users', 0)}\n"
        msg += f"• 📊 الإجمالي: {user_stats['total_users']:,}\n"
        msg += f"• 🎯 النشطين: {report.get('active_users', 0)}\n\n"
        
        msg += "💰 **الأداء المالي:**\n"
        msg += f"• 💳 إجمالي الإيداع: {report['total_deposit']:,} ليرة\n"
        msg += f"• 💸 إجمالي السحب: {report['total_withdraw']:,} ليرة\n"
        msg += f"• 📈 صافي التدفق: {report['total_deposit'] - report['total_withdraw']:,} ليرة\n"
        msg += f"• 📋 المعاملات: {report['deposit_count'] + report['withdraw_count']}\n"
        msg += f"• ⏳ المعلقة: {report['pending_count']}\n\n"
        
        # إحصائيات الإحالات
        from services.referral_service import ReferralService
        referral_service = ReferralService()
        top_referrers = referral_service.get_top_referrers(3)
        
        if top_referrers:
            msg += "🏆 **أفضل المحيلين اليوم:**\n"
            for i, ref in enumerate(top_referrers[:3], 1):
                msg += f"{i}. `{ref['referrer_id']}` - {ref['total_refs']} إحالة\n"
            msg += "\n"
        
        msg += f"🕒 **وقت التقرير:** {datetime.now().strftime('%H:%M:%S')}"
        
        # إرسال التقرير
        if REPORT_CONFIG["SEND_TO_CHANNEL"]:
            from handlers.commands import bot
            try:
                bot.send_message(
                    CHANNELS["DAILY_STATS"],
                    msg,
                    parse_mode="Markdown"
                )
                logger.info("✅ تم إرسال التقرير اليومي للقناة")
            except Exception as e:
                logger.error(f"❌ خطأ في إرسال التقرير: {e}")
        
        return msg
        
    except Exception as e:
        logger.error(f"❌ خطأ في توليد التقرير اليومي: {e}")
        return None


def setup_report_task(scheduler):
    """إعداد مهمة التقارير المجدولة"""
    try:
        if not REPORT_CONFIG["AUTO_GENERATE"]:
            logger.info("⏸️ التقارير التلقائية معطلة")
            return
        
        report_time = REPORT_CONFIG["DAILY_REPORT_TIME"]
        
        if ':' in report_time:
            hour, minute = map(int, report_time.split(':'))
            
            # إضافة المهمة المجدولة
            scheduler.add_job(
                generate_daily_report,
                'cron',
                hour=hour,
                minute=minute,
                id='daily_report',
                name='التقرير اليومي التلقائي'
            )
            
            logger.info(f"✅ تم جدولة التقرير اليومي للساعة: {report_time}")
        else:
            logger.warning("❌ وقت التقرير غير صحيح")
        
    except Exception as e:
        logger.error(f"❌ خطأ في إعداد مهمة التقارير: {e}")