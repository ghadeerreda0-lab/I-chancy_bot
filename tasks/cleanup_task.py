"""
مهام التنظيف التلقائي
"""

from datetime import datetime, timedelta
from core.logger import get_logger
from handlers.sessions import cleanup_expired_sessions
from services.gift_service import GiftService
from core.security import rate_limiter
from core.cache import cache

logger = get_logger(__name__)


def cleanup_system():
    """تنظيف النظام"""
    try:
        cleaned_items = 0
        
        # 1. تنظيف الجلسات المنتهية
        sessions_cleaned = cleanup_expired_sessions()
        cleaned_items += sessions_cleaned
        
        # 2. تنظيف أكواد الهدايا المنتهية
        gift_service = GiftService()
        codes_cleaned = gift_service.cleanup_expired_codes()
        cleaned_items += codes_cleaned
        
        # 3. تنظيف Rate Limiter
        rate_limiter.cleanup_old_requests()
        
        # 4. تنظيف الكاش
        cache_expired = cache.auto_cleanup()
        cleaned_items += cache_expired
        
        if cleaned_items > 0:
            logger.info(f"🧹 تم تنظيف {cleaned_items} عنصر من النظام")
        
        return cleaned_items
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف النظام: {e}")
        return 0


def cleanup_old_transactions(days: int = 30):
    """تنظيف المعاملات القديمة"""
    try:
        from core.database import db
        
        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # حذف المعاملات المكتملة القديمة
        query = """
            DELETE FROM transactions 
            WHERE status IN ('approved', 'rejected', 'completed')
            AND date(created_at) < ?
        """
        
        cursor = db.execute_query(query, (date_limit,))
        deleted_count = cursor.rowcount
        
        if deleted_count > 0:
            logger.info(f"🧹 تم حذف {deleted_count} معاملة قديمة (أقدم من {days} يوم)")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف المعاملات: {e}")
        return 0


def cleanup_inactive_users(days: int = 90):
    """تنظيف المستخدمين غير النشطين"""
    try:
        from core.database import db
        
        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # حذف المستخدمين غير النشطين بدون رصيد
        query = """
            DELETE FROM users 
            WHERE balance = 0 
            AND is_banned = 0
            AND last_active < ?
            AND user_id NOT IN (SELECT user_id FROM admins)
        """
        
        cursor = db.execute_query(query, (date_limit,))
        deleted_count = cursor.rowcount
        
        if deleted_count > 0:
            logger.info(f"🧹 تم حذف {deleted_count} مستخدم غير نشط (أقدم من {days} يوم)")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف المستخدمين: {e}")
        return 0


def setup_cleanup_task(scheduler):
    """إعداد مهام التنظيف المجدولة"""
    try:
        # تنظيف النظام كل ساعة
        scheduler.add_job(
            cleanup_system,
            'interval',
            hours=1,
            id='system_cleanup',
            name='تنظيف النظام'
        )
        
        # تنظيف المعاملات القديمة أسبوعياً
        scheduler.add_job(
            cleanup_old_transactions,
            'interval',
            weeks=1,
            id='transactions_cleanup',
            name='تنظيف المعاملات القديمة'
        )
        
        # تنظيف المستخدمين غير النشطين شهرياً
        scheduler.add_job(
            cleanup_inactive_users,
            'interval',
            days=30,
            id='users_cleanup',
            name='تنظيف المستخدمين غير النشطين'
        )
        
        logger.info("✅ تم جدولة مهام التنظيف التلقائي")
        
    except Exception as e:
        logger.error(f"❌ خطأ في إعداد مهام التنظيف: {e}")