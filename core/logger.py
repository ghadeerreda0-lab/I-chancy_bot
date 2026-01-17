"""
نظام تسجيل متقدم مع تخصيص
"""

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
from datetime import datetime
from .config import LOG_PATH

# إنشاء مجلد اللوجات إذا لم يكن موجوداً
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


class CustomFormatter(logging.Formatter):
    """فورماتور مخصص مع ألوان"""
    
    # ألوان ANSI
    COLORS = {
        'DEBUG': '\033[94m',     # أزرق
        'INFO': '\033[92m',      # أخضر
        'WARNING': '\033[93m',   # أصفر
        'ERROR': '\033[91m',     # أحمر
        'CRITICAL': '\033[95m',  # بنفسجي
        'RESET': '\033[0m'       # إعادة الضبط
    }
    
    def format(self, record):
        # إضافة الوقت والاسم
        log_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record.asctime = log_time
        
        # تلوين الرسالة حسب المستوى
        if record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
            record.msg = f"{color}{record.msg}{reset}"
        
        return super().format(record)


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """إعداد وتكوين اللوجر"""
    
    # إنشاء اللوجر
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # منع التكرار
    if logger.handlers:
        return logger
    
    # تنسيق اللوج
    formatter = CustomFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler للملف مع تدوير حسب الحجم
    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Handler للملف اليومي
    daily_handler = TimedRotatingFileHandler(
        LOG_PATH.replace('.log', '_daily.log'),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    daily_handler.setLevel(logging.INFO)
    daily_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Handler للكونسول
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # إضافة ال handlers
    logger.addHandler(file_handler)
    logger.addHandler(daily_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """الحصول على لوجر مكون مسبقاً"""
    return setup_logger(name)


# لوجر النظام الرئيسي
system_logger = get_logger("System")
bot_logger = get_logger("Bot")
db_logger = get_logger("Database")
cache_logger = get_logger("Cache")
error_logger = get_logger("Error")

# دالة لرصد الأداء
def performance_logger(func):
    """ديكورير لقياس وقت التنفيذ"""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        
        execution_time = (end_time - start_time).total_seconds()
        
        if execution_time > 0.1:  # أكثر من 100ms
            bot_logger.warning(
                f"الأداء: {func.__name__} استغرق {execution_time:.3f} ثانية"
            )
        elif execution_time > 1.0:  # أكثر من 1 ثانية
            bot_logger.error(
                f"الأداء البطيء: {func.__name__} استغرق {execution_time:.3f} ثانية"
            )
        
        return result
    return wrapper


# دالة لتسجيل الأحداث المهمة
def log_event(event_type: str, user_id: int = None, details: str = ""):
    """تسجيل حدث مهم في النظام"""
    user_info = f"المستخدم: {user_id}" if user_id else "النظام"
    bot_logger.info(f"📊 [{event_type}] {user_info} - {details}")


# بداية النظام
system_logger.info("=" * 60)
system_logger.info("🚀 بدء تشغيل نظام البوت الاحترافي")
system_logger.info(f"🕒 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
system_logger.info("=" * 60)