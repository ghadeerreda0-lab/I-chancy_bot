"""
نظام الجدولة - سرعة فائقة
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from core.logger import get_logger

logger = get_logger(__name__)


def setup_scheduler():
    """إعداد وتكوين المجدول"""
    try:
        # إعدادات المجدول
        jobstores = {
            'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
        }
        
        executors = {
            'default': ThreadPoolExecutor(4)
        }
        
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        }
        
        # إنشاء المجدول
        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Damascus'
        )
        
        # بدء المجدول
        scheduler.start()
        
        logger.info("✅ تم تشغيل نظام الجدولة")
        return scheduler
        
    except Exception as e:
        logger.error(f"❌ خطأ في إعداد المجدول: {e}")
        return None