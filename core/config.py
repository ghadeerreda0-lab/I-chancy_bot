"""
إعدادات وتكوين البوت - السرعة والأمان
"""

import os
import secrets
from datetime import datetime

# ==================== أمان عالي ====================
SECRET_KEY = secrets.token_hex(32)  # مفتاح تشفير قوي
TOKEN = "8563127617:AAEqQh1bWM8k2gMFqmAWLUJvWTK3rFyp4k8"
ADMIN_ID = 8146077656

# ==================== إصدار النظام ====================
VERSION = "7.0.0"
LAST_UPDATE = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ==================== القنوات ====================
CHANNELS = {
    "SYR_CASH": -1003597919374,
    "SCH_CASH": -1003464319533,
    "ADMIN_LOGS": -1003577468648,
    "WITHDRAW": -1003443113179,
    "SUPPORT": -1003514396473,
    "ERROR_LOGS": -1003661244115,
    "DAILY_STATS": -1003478157091,
    "DB_BACKUP": -1003612263016,
    "URGENT_REQUESTS": -1003577468648
}

# ==================== مسارات الملفات ====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "bot_database.sqlite")
LOG_PATH = os.path.join(BASE_DIR, "logs", "bot.log")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

# إنشاء المجلدات إذا لم تكن موجودة
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# ==================== ثوابت النظام ====================
SYSTEM_CONSTANTS = {
    "MAX_CODES": 20,
    "CODE_CAPACITY": 5400,
    "MAX_ADMINS": 10,
    "REFERRAL_CODE_LENGTH": 8,
    "GIFT_CODE_LENGTH": 8,
    "SESSION_TTL_MINUTES": 30,
    "CACHE_TTL_SECONDS": 300,
    "RATE_LIMIT_REQUESTS": 10,
    "RATE_LIMIT_WINDOW": 60
}

# ==================== إعدادات الأداء ====================
PERFORMANCE = {
    "CACHE_MAX_SIZE": 1000,
    "DB_POOL_SIZE": 10,
    "THREAD_POOL_SIZE": 4,
    "BATCH_SIZE": 50,
    "QUERY_TIMEOUT": 5
}

# ==================== إعدادات الدفع ====================
PAYMENT_METHODS = {
    "syriatel_cash": "📱 سيرياتيل كاش",
    "sham_cash": "💰 شام كاش", 
    "sham_cash_usd": "💵 شام كاش دولار"
}

# ==================== إعدادات Ichancy ====================
ICHANCY_CONFIG = {
    "USERNAME_LENGTH": 8,
    "PASSWORD_LENGTH": 12,
    "MIN_USERNAME": 4,
    "MAX_USERNAME": 20
}

# ==================== إعدادات النسخ الاحتياطي ====================
BACKUP_CONFIG = {
    "ENABLED": True,
    "INTERVAL_HOURS": 6,
    "MAX_BACKUPS": 30,
    "COMPRESS": True
}

# ==================== إعدادات التقارير ====================
REPORT_CONFIG = {
    "DAILY_REPORT_TIME": "23:59",
    "AUTO_GENERATE": True,
    "SEND_TO_CHANNEL": True
}

print("✅ تم تحميل config.py بنجاح")