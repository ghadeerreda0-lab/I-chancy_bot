"""
config.py - إعدادات البوت والثوابت
"""

import datetime

# =========================
# إعدادات البوت - التوكن كما هو
# =========================
TOKEN = "8563127617:AAEqQh1bWM8k2gMFqmAWLUJvWTK3rFyp4k8"
ADMIN_ID = 8146077656
VERSION = "6.0.0"
LAST_UPDATE = datetime.datetime.now().strftime("%Y-%m-%d")

# القنوات
CHANNEL_SYR_CASH = -1003597919374
CHANNEL_SCH_CASH = -1003464319533
CHANNEL_ADMIN_LOGS = -1003577468648
CHANNEL_WITHDRAW = -1003443113179
CHANNEL_SUPPORT = -1003514396473
CHANNEL_ERROR_LOGS = -1003661244115
CHANNEL_DAILY_STATS = -1003478157091
CHANNEL_DB_BACKUP = -1003612263016
CHANNEL_URGENT_REQUESTS = -1003577468648

# =========================
# ثوابت النظام
# =========================
MAX_CODES = 20
CODE_CAPACITY = 5400
MAX_ADMINS = 10
REFERRAL_CODE_LENGTH = 8

# مسارات الملفات
DB_PATH = "/tmp/bot_db.sqlite" if os.path.exists("/tmp") else "bot_db.sqlite"
LOG_FILE = "/tmp/bot_logs.log" if os.path.exists("/tmp") else "bot_logs.log"