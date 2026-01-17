"""
نظام قاعدة البيانات المتقدم مع Connection Pool
"""

import sqlite3
import threading
import time
from queue import Queue
from typing import Optional, List, Dict, Any, Tuple
import logging
from contextlib import contextmanager

from .config import DB_PATH, PERFORMANCE
from .logger import get_logger

logger = get_logger(__name__)

class DatabasePool:
    """Connection Pool لأداء عالي"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """تهيئة البوول"""
        self.pool_size = PERFORMANCE["DB_POOL_SIZE"]
        self.pool = Queue(maxsize=self.pool_size)
        self._create_connections()
        self.stats = {"hits": 0, "misses": 0, "timeouts": 0}
        logger.info(f"تم تهيئة Database Pool بحجم {self.pool_size}")
    
    def _create_connections(self):
        """إنشاء الاتصالات"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(
                DB_PATH,
                timeout=PERFORMANCE["QUERY_TIMEOUT"],
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            # تفعيل WAL mode لأداء أفضل
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-2000")  # 2MB cache
            self.pool.put(conn)
    
    @contextmanager
    def get_connection(self):
        """الحصول على اتصال من البوول"""
        conn = None
        start_time = time.time()
        
        try:
            conn = self.pool.get(timeout=2)
            self.stats["hits"] += 1
            yield conn
        except Exception as e:
            self.stats["misses"] += 1
            logger.error(f"خطأ في الحصول على اتصال: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.commit()
                    self.pool.put(conn)
                except Exception as e:
                    logger.error(f"خطأ في إرجاع الاتصال: {e}")
                    try:
                        conn.close()
                    except:
                        pass
    
    def get_stats(self) -> Dict:
        """الحصول على إحصائيات البوول"""
        return {
            **self.stats,
            "pool_size": self.pool_size,
            "queue_size": self.pool.qsize(),
            "available": self.pool.qsize()
        }


class DatabaseManager:
    """مدير قاعدة البيانات الرئيسي"""
    
    def __init__(self):
        self.pool = DatabasePool()
        self._init_database()
    
    def _init_database(self):
        """تهيئة قاعدة البيانات مع جميع الجداول"""
        tables = self._get_table_schemas()
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # إنشاء جميع الجداول
            for table_name, schema in tables.items():
                try:
                    cursor.execute(schema)
                    logger.debug(f"تم إنشاء/التحقق من جدول: {table_name}")
                except Exception as e:
                    logger.error(f"خطأ في إنشاء جدول {table_name}: {e}")
            
            # إنشاء المؤشرات
            indices = self._get_table_indices()
            for idx_name, idx_sql in indices:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_sql}")
                except Exception as e:
                    logger.warning(f"خطأ في إنشاء مؤشر {idx_name}: {e}")
            
            conn.commit()
            logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
    
    def _get_table_schemas(self) -> Dict[str, str]:
        """جلب مخططات جميع الجداول"""
        return {
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0 CHECK(balance >= 0),
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_active TEXT,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    is_banned BOOLEAN DEFAULT 0,
                    ban_reason TEXT,
                    ban_until TEXT,
                    total_deposit INTEGER DEFAULT 0,
                    total_withdraw INTEGER DEFAULT 0
                )
            """,
            "transactions": """
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
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """,
            "syriatel_codes": """
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
            "ichancy_accounts": """
                CREATE TABLE IF NOT EXISTS ichancy_accounts (
                    user_id INTEGER PRIMARY KEY,
                    ichancy_username TEXT UNIQUE NOT NULL,
                    ichancy_password TEXT NOT NULL,
                    ichancy_balance INTEGER DEFAULT 0 CHECK(ichancy_balance >= 0),
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_login TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """,
            "admins": """
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER NOT NULL,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    permissions TEXT DEFAULT 'limited',
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (added_by) REFERENCES users (user_id)
                )
            """,
            "referrals": """
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL,
                    amount_charged INTEGER DEFAULT 0,
                    commission_earned INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (referred_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    UNIQUE(referred_id)
                )
            """,
            "referral_settings": """
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
            "gift_codes": """
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
            "gift_code_usage": """
                CREATE TABLE IF NOT EXISTS gift_code_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (code) REFERENCES gift_codes (code) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """,
            "gift_transactions": """
                CREATE TABLE IF NOT EXISTS gift_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    original_amount INTEGER NOT NULL,
                    net_amount INTEGER NOT NULL,
                    gift_percentage INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (receiver_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """,
            "system_settings": """
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_by INTEGER
                )
            """,
            "payment_settings": """
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
            "payment_limits": """
                CREATE TABLE IF NOT EXISTS payment_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_method TEXT NOT NULL UNIQUE,
                    min_amount INTEGER DEFAULT 1000,
                    max_amount INTEGER DEFAULT 50000,
                    updated_by INTEGER,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "daily_stats": """
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
            """
        }
    
    def _get_table_indices(self) -> List[Tuple]:
        """جلب قائمة المؤشرات"""
        return [
            ("idx_users_balance", "users(balance DESC)"),
            ("idx_users_banned", "users(is_banned)"),
            ("idx_users_created", "users(created_at DESC)"),
            ("idx_transactions_user", "transactions(user_id)"),
            ("idx_transactions_status", "transactions(status)"),
            ("idx_transactions_created", "transactions(created_at DESC)"),
            ("idx_transactions_type", "transactions(type)"),
            ("idx_ichancy_username", "ichancy_accounts(ichancy_username)"),
            ("idx_admins_added", "admins(added_at DESC)"),
            ("idx_referrals_referrer", "referrals(referrer_id)"),
            ("idx_referrals_referred", "referrals(referred_id)"),
            ("idx_gift_codes_expires", "gift_codes(expires_at)"),
            ("idx_gift_codes_used", "gift_codes(used_count)"),
            ("idx_codes_active", "syriatel_codes(is_active)"),
            ("idx_codes_amount", "syriatel_codes(current_amount)")
        ]
    
    def execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """تنفيذ استعلام بأداء عالي"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor
    
    def execute_many(self, query: str, params_list: list) -> None:
        """تنفيذ عدة استعلامات دفعة واحدة"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """جلب صف واحد"""
        cursor = self.execute_query(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """جلب جميع الصفوف"""
        cursor = self.execute_query(query, params)
        return cursor.fetchall()
    
    def insert_and_get_id(self, query: str, params: tuple = ()) -> int:
        """إدخال وعرض المعرف"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    def table_exists(self, table_name: str) -> bool:
        """التحقق من وجود جدول"""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.fetch_one(query, (table_name,))
        return result is not None
    
    def vacuum(self):
        """تنظيف وتحسين قاعدة البيانات"""
        with self.pool.get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("تم تنظيف قاعدة البيانات (VACUUM)")
    
    def backup(self, backup_path: str) -> bool:
        """إنشاء نسخة احتياطية"""
        try:
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"خطأ في النسخ الاحتياطي: {e}")
            return False


# إنشاء نسخة عامة للاستخدام
db = DatabaseManager()