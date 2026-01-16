"""
models.py - تعريف جداول قاعدة البيانات
"""

# تعريفات SQL لإنشاء الجداول

SYSTEM_TABLES = [
    # جدول المستخدمين
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0 CHECK(balance >= 0),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT,
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        is_banned BOOLEAN DEFAULT 0,
        ban_reason TEXT,
        ban_until TEXT
    )
    """,
    
    # جدول المعاملات
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('charge', 'withdraw', 'gift_sent', 'gift_received', 'referral', 'bonus')),
        amount INTEGER NOT NULL CHECK(amount > 0),
        payment_method TEXT,
        transaction_id TEXT,
        account_number TEXT,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'completed')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # جدول أكواد سيرياتيل
    """
    CREATE TABLE IF NOT EXISTS syriatel_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_number TEXT NOT NULL UNIQUE,
        current_amount INTEGER DEFAULT 0 CHECK(current_amount >= 0 AND current_amount <= 5400),
        is_active BOOLEAN DEFAULT 1,
        added_by INTEGER,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_used TEXT,
        usage_count INTEGER DEFAULT 0
    )
    """,
    
    # سجل تعبئة الأكواد
    """
    CREATE TABLE IF NOT EXISTS code_fill_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL CHECK(amount > 0),
        remaining_in_code INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (code_id) REFERENCES syriatel_codes (id),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # جدول البونص
    """
    CREATE TABLE IF NOT EXISTS bonus_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_method TEXT NOT NULL,
        bonus_type TEXT NOT NULL CHECK(bonus_type IN ('normal', 'conditional')),
        percentage INTEGER CHECK(percentage >= 0 AND percentage <= 100),
        fixed_amount INTEGER CHECK(fixed_amount >= 0),
        condition_amount INTEGER,
        expiry_date TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # استخدام البونص
    """
    CREATE TABLE IF NOT EXISTS bonus_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bonus_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        transaction_id INTEGER NOT NULL,
        original_amount INTEGER NOT NULL,
        bonus_amount INTEGER NOT NULL,
        total_amount INTEGER NOT NULL,
        used_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bonus_id) REFERENCES bonus_offers (id),
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    )
    """,
    
    # سعر الصرف
    """
    CREATE TABLE IF NOT EXISTS exchange_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rate INTEGER NOT NULL CHECK(rate > 0),
        changed_by INTEGER,
        changed_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # حدود المبالغ
    """
    CREATE TABLE IF NOT EXISTS payment_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_method TEXT NOT NULL UNIQUE,
        min_amount INTEGER DEFAULT 1000,
        max_amount INTEGER DEFAULT 50000,
        updated_by INTEGER,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # إعدادات الدفع
    """
    CREATE TABLE IF NOT EXISTS payment_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_method TEXT NOT NULL UNIQUE,
        is_visible BOOLEAN DEFAULT 1,
        is_active BOOLEAN DEFAULT 1,
        pause_message TEXT,
        updated_by INTEGER,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # طلبات معلقة
    """
    CREATE TABLE IF NOT EXISTS pending_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL CHECK(amount > 0),
        status TEXT DEFAULT 'waiting' CHECK(status IN ('waiting', 'processing', 'completed', 'cancelled')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # عداد شهري
    """
    CREATE TABLE IF NOT EXISTS monthly_counter (
        month INTEGER,
        year INTEGER,
        payment_method TEXT,
        counter INTEGER DEFAULT 1,
        PRIMARY KEY (month, year, payment_method)
    )
    """,
    
    # رسائل الدعم
    """
    CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        message TEXT NOT NULL,
        admin_reply TEXT,
        status TEXT DEFAULT 'open' CHECK(status IN ('open', 'replied', 'closed')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        replied_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # الجلسات
    """
    CREATE TABLE IF NOT EXISTS sessions (
        user_id INTEGER PRIMARY KEY,
        step TEXT NOT NULL,
        temp_data TEXT,
        expires_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # إعدادات النظام
    """
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_by INTEGER
    )
    """,
    
    # إحصائيات يومية
    """
    CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY,
        total_users INTEGER DEFAULT 0,
        new_users INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0,
        total_deposit INTEGER DEFAULT 0,
        total_withdraw INTEGER DEFAULT 0,
        pending_transactions INTEGER DEFAULT 0,
        support_tickets INTEGER DEFAULT 0,
        resolved_tickets INTEGER DEFAULT 0,
        avg_response_time REAL DEFAULT 0.0,
        system_errors INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # سجل التعديلات
    """
    CREATE TABLE IF NOT EXISTS settings_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        setting_key TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT NOT NULL,
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # سجل النسخ الاحتياطي
    """
    CREATE TABLE IF NOT EXISTS backup_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backup_type TEXT NOT NULL CHECK(backup_type IN ('auto', 'manual')),
        file_path TEXT NOT NULL,
        file_size INTEGER,
        status TEXT NOT NULL CHECK(status IN ('success', 'failed')),
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # إشعارات عاجلة
    """
    CREATE TABLE IF NOT EXISTS urgent_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        max_available INTEGER NOT NULL,
        is_resolved BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """
]

# الجداول الجديدة للنظام المتكامل
NEW_TABLES = [
    # جدول نظام Ichancy
    """
    CREATE TABLE IF NOT EXISTS ichancy_accounts (
        user_id INTEGER PRIMARY KEY,
        ichancy_username TEXT UNIQUE NOT NULL,
        ichancy_password TEXT NOT NULL,
        ichancy_balance INTEGER DEFAULT 0 CHECK(ichancy_balance >= 0),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # جدول الأدمن الثانوي
    """
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        added_by INTEGER NOT NULL,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP,
        permissions TEXT DEFAULT 'limited',
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (added_by) REFERENCES users (user_id)
    )
    """,
    
    # جدول الإحالات
    """
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL,
        amount_charged INTEGER DEFAULT 0,
        commission_earned INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES users (user_id),
        FOREIGN KEY (referred_id) REFERENCES users (user_id),
        UNIQUE(referred_id)
    )
    """,
    
    # جدول إعدادات الإحالات
    """
    CREATE TABLE IF NOT EXISTS referral_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        commission_rate INTEGER DEFAULT 10,
        bonus_amount INTEGER DEFAULT 2000,
        min_active_referrals INTEGER DEFAULT 5,
        min_charge_amount INTEGER DEFAULT 100000,
        next_distribution TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    
    # جدول أكواد الهدايا
    """
    CREATE TABLE IF NOT EXISTS gift_codes (
        code TEXT PRIMARY KEY,
        amount INTEGER NOT NULL CHECK(amount > 0),
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT
    )
    """,
    
    # جدول استخدام أكواد الهدايا
    """
    CREATE TABLE IF NOT EXISTS gift_code_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (code) REFERENCES gift_codes (code),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """,
    
    # جدول عمليات الإهداء
    """
    CREATE TABLE IF NOT EXISTS gift_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        original_amount INTEGER NOT NULL,
        net_amount INTEGER NOT NULL,
        gift_percentage INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users (user_id),
        FOREIGN KEY (receiver_id) REFERENCES users (user_id)
    )
    """,
    
    # جدول رسائل النظام
    """
    CREATE TABLE IF NOT EXISTS broadcast_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        message_text TEXT NOT NULL,
        message_type TEXT CHECK(message_type IN ('text', 'photo')),
        file_id TEXT,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (admin_id) REFERENCES users (user_id)
    )
    """
]

# جميع الجداول
ALL_TABLES = SYSTEM_TABLES + NEW_TABLES

# تعريفات المؤشرات
INDICES = [
    ("idx_transactions_user", "transactions(user_id)"),
    ("idx_transactions_status", "transactions(status)"),
    ("idx_transactions_created", "transactions(created_at)"),
    ("idx_sessions_user", "sessions(user_id)"),
    ("idx_codes_active", "syriatel_codes(is_active)"),
    ("idx_codes_amount", "syriatel_codes(current_amount)"),
    ("idx_bonus_active", "bonus_offers(is_active)"),
    ("idx_bonus_method", "bonus_offers(payment_method)"),
    ("idx_referrals_referrer", "referrals(referrer_id)"),
    ("idx_referrals_referred", "referrals(referred_id)"),
    ("idx_gift_codes_expires", "gift_codes(expires_at)"),
    ("idx_gift_code_usage", "gift_code_usage(code, user_id)"),
    ("idx_admins_added", "admins(added_at)"),
    ("idx_users_banned", "users(is_banned)")
]

# الإعدادات الافتراضية
DEFAULT_SETTINGS = [
    ('maintenance_mode', 'false'),
    ('maintenance_message', '🔧 البوت تحت الصيانة حاليًا. الرجاء المحاولة لاحقًا.'),
    ('welcome_message', '👋 أهلاً بك!\nرصيدك الحالي: {balance} ليرة سورية'),
    ('contact_info', '📞 للاستفسار: @username'),
    ('auto_backup', 'true'),
    ('backup_interval_hours', '6'),
    ('daily_report_time', '23:59'),
    ('enable_error_notifications', 'true'),
    ('auto_reset_codes_daily', 'true'),
    
    # إعدادات Ichancy
    ('ichancy_enabled', 'true'),
    ('ichancy_create_account_enabled', 'true'),
    ('ichancy_deposit_enabled', 'true'),
    ('ichancy_withdraw_enabled', 'true'),
    ('ichancy_welcome_message', '⚡ مرحباً بك في نظام Ichancy!'),
    
    # إعدادات الشحن والسحب
    ('deposit_enabled', 'true'),
    ('deposit_message', '💰 نظام الشحن مفعل حالياً'),
    ('withdraw_enabled', 'true'),
    ('withdraw_message', '💸 نظام السحب مفعل حالياً'),
    ('withdraw_percentage', '0'),
    ('withdraw_button_visible', 'true'),
    
    # إعدادات الإهداء
    ('gift_percentage', '0'),
    
    # إعدادات الأدمن
    ('max_admins', '10')
]

# طرق الدفع الافتراضية
PAYMENT_METHODS = [
    ('syriatel_cash', '📱 سيرياتيل كاش'),
    ('sham_cash', '💰 شام كاش'),
    ('sham_cash_usd', '💵 شام كاش دولار')
]