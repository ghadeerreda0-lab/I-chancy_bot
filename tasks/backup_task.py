"""
مهمة النسخ الاحتياطي التلقائي
"""

import os
import shutil
from datetime import datetime
from core.config import BACKUP_DIR, DB_PATH
from core.logger import get_logger
from core.database import db

logger = get_logger(__name__)


def create_backup():
    """إنشاء نسخة احتياطية"""
    try:
        # إنشاء اسم الملف
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.sqlite")
        
        # نسخ قاعدة البيانات
        shutil.copy2(DB_PATH, backup_file)
        
        # تسجيل حجم الملف
        file_size = os.path.getsize(backup_file)
        size_str = f"{file_size / 1024 / 1024:.2f} MB"
        
        logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_file} ({size_str})")
        
        return {
            "success": True,
            "file_name": os.path.basename(backup_file),
            "file_path": backup_file,
            "file_size": size_str,
            "timestamp": timestamp
        }
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def cleanup_old_backups(max_backups: int = 30):
    """تنظيف النسخ الاحتياطية القديمة"""
    try:
        if not os.path.exists(BACKUP_DIR):
            return 0
        
        # جلب جميع ملفات النسخ الاحتياطي
        backup_files = []
        for file in os.listdir(BACKUP_DIR):
            if file.startswith("backup_") and file.endswith(".sqlite"):
                file_path = os.path.join(BACKUP_DIR, file)
                backup_files.append((file_path, os.path.getmtime(file_path)))
        
        # ترتيب حسب التاريخ (الأقدم أولاً)
        backup_files.sort(key=lambda x: x[1])
        
        # حذف الملفات الزائدة
        deleted_count = 0
        while len(backup_files) > max_backups:
            oldest_file = backup_files.pop(0)[0]
            os.remove(oldest_file)
            deleted_count += 1
            logger.debug(f"🧹 تم حذف نسخة احتياطية قديمة: {oldest_file}")
        
        if deleted_count > 0:
            logger.info(f"🧹 تم حذف {deleted_count} نسخة احتياطية قديمة")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف النسخ الاحتياطية: {e}")
        return 0


def setup_backup_task(scheduler):
    """إعداد مهمة النسخ الاحتياطي المجدولة"""
    try:
        from core.config import BACKUP_CONFIG
        
        if not BACKUP_CONFIG["ENABLED"]:
            logger.info("⏸️ النسخ الاحتياطي التلقائي معطل")
            return
        
        interval_hours = BACKUP_CONFIG["INTERVAL_HOURS"]
        
        # إضافة المهمة المجدولة
        scheduler.add_job(
            create_backup,
            'interval',
            hours=interval_hours,
            id='auto_backup',
            name='النسخ الاحتياطي التلقائي'
        )
        
        # مهمة تنظيف النسخ القديمة (يومياً)
        scheduler.add_job(
            cleanup_old_backups,
            'interval',
            days=1,
            id='cleanup_backups',
            name='تنظيف النسخ الاحتياطية القديمة'
        )
        
        logger.info(f"✅ تم جدولة النسخ الاحتياطي كل {interval_hours} ساعات")
        
    except Exception as e:
        logger.error(f"❌ خطأ في إعداد مهمة النسخ الاحتياطي: {e}")