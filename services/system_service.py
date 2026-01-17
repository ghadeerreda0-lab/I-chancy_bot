"""
خدمات النظام العام والإعدادات - سرعة فائقة
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from core.database import db
from core.cache import cache
from core.logger import get_logger, performance_logger

logger = get_logger(__name__)


class SystemService:
    """خدمات النظام العام"""
    
    def __init__(self):
        self.cache = cache
        self.init_default_settings()
    
    @performance_logger
    def init_default_settings(self):
        """تهيئة الإعدادات الافتراضية"""
        try:
            default_settings = [
                ('maintenance_mode', 'false'),
                ('maintenance_message', '🔧 البوت تحت الصيانة حاليًا. الرجاء المحاولة لاحقًا.'),
                ('welcome_message', '👋 أهلاً بك!\nرصيدك الحالي: {balance} ليرة سورية'),
                ('contact_info', '📞 للاستفسار: @username'),
                ('auto_backup', 'true'),
                ('backup_interval_hours', '6'),
                ('daily_report_time', '23:59'),
                ('enable_error_notifications', 'true'),
                ('auto_reset_codes_daily', 'true'),
                ('ichancy_enabled', 'true'),
                ('ichancy_create_account_enabled', 'true'),
                ('ichancy_deposit_enabled', 'true'),
                ('ichancy_withdraw_enabled', 'true'),
                ('ichancy_welcome_message', '⚡ مرحباً بك في نظام Ichancy!'),
                ('deposit_enabled', 'true'),
                ('deposit_message', '💰 نظام الشحن مفعل حالياً'),
                ('withdraw_enabled', 'true'),
                ('withdraw_message', '💸 نظام السحب مفعل حالياً'),
                ('withdraw_percentage', '0'),
                ('withdraw_button_visible', 'true'),
                ('gift_percentage', '0'),
                ('max_admins', '10'),
                ('exchange_rate', '13000')  # سعر صرف الدولار
            ]
            
            for key, value in default_settings:
                self.set_setting(key, value, 0, "التهيئة الافتراضية")
            
            logger.info("تم تهيئة الإعدادات الافتراضية")
        except Exception as e:
            logger.error(f"خطأ في تهيئة الإعدادات: {e}")
    
    @performance_logger
    def get_setting(self, key: str, default: Any = None) -> Any:
        """جلب إعداد"""
        cache_key = f"system_setting_{key}"
        cached = self.cache.get_setting(cache_key)
        if cached is not None:
            return cached
        
        query = "SELECT value FROM system_settings WHERE key = ?"
        result = db.fetch_one(query, (key,))
        
        if result:
            value = result['value']
            self.cache.set_setting(cache_key, value, ttl=60)
            return value
        
        return default
    
    @performance_logger
    def set_setting(self, key: str, value: Any, admin_id: int = 0, reason: str = "") -> bool:
        """تحديث إعداد"""
        try:
            # جلب القيمة القديمة
            old_value = self.get_setting(key)
            
            query = """
                INSERT OR REPLACE INTO system_settings 
                (key, value, updated_at, updated_by)
                VALUES (?, ?, datetime('now'), ?)
            """
            
            value_str = str(value) if not isinstance(value, str) else value
            
            db.execute_query(query, (key, value_str, admin_id))
            
            # إبطال الكاش
            self.cache.delete_setting(f"system_setting_{key}")
            
            # تسجيل التغيير إذا كان هناك سبب
            if reason and admin_id:
                log_query = """
                    INSERT INTO settings_logs 
                    (admin_id, setting_key, old_value, new_value, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                """
                db.execute_query(log_query, (admin_id, key, str(old_value), value_str, reason))
            
            logger.info(f"تم تحديث الإعداد: {key} = {value_str}")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث الإعداد {key}: {e}")
            return False
    
    @performance_logger
    def toggle_setting(self, key: str, admin_id: int = 0) -> Dict[str, Any]:
        """تبديل إعداد (تفعيل/إيقاف)"""
        try:
            current = self.get_setting(key)
            if current is None:
                current = 'false'
            
            new_value = 'false' if current.lower() == 'true' else 'true'
            
            self.set_setting(key, new_value, admin_id, f"تبديل {key}")
            
            status_text = "مفعل ✅" if new_value == 'true' else "معطل ❌"
            
            return {
                "success": True,
                "key": key,
                "old_value": current,
                "new_value": new_value,
                "status": status_text,
                "message": f"تم {status_text} {key}"
            }
        except Exception as e:
            logger.error(f"خطأ في toggle_setting {key}: {e}")
            return {"success": False, "message": f"خطأ في تبديل {key}"}
    
    @performance_logger
    def get_all_settings(self) -> Dict[str, Any]:
        """جلب جميع الإعدادات"""
        query = """
            SELECT key, value, updated_at, updated_by
            FROM system_settings 
            ORDER BY key
        """
        
        results = db.fetch_all(query)
        settings = {}
        
        for row in results:
            settings[row['key']] = {
                'value': row['value'],
                'updated_at': row['updated_at'],
                'updated_by': row['updated_by']
            }
        
        return settings
    
    @performance_logger
    def is_maintenance_mode(self) -> bool:
        """التحقق من وضع الصيانة"""
        return self.get_setting('maintenance_mode') == 'true'
    
    @performance_logger
    def get_maintenance_message(self) -> str:
        """جلب رسالة الصيانة"""
        return self.get_setting('maintenance_message', '🔧 البوت تحت الصيانة حاليًا.')
    
    @performance_logger
    def get_welcome_message(self, balance: int = 0) -> str:
        """جلب رسالة الترحيب"""
        template = self.get_setting('welcome_message', '👋 أهلاً بك!\nرصيدك الحالي: {balance} ليرة سورية')
        return template.format(balance=balance)
    
    @performance_logger
    def is_deposit_enabled(self) -> bool:
        """التحقق من تفعيل الشحن"""
        return self.get_setting('deposit_enabled') == 'true'
    
    @performance_logger
    def is_withdraw_enabled(self) -> bool:
        """التحقق من تفعيل السحب"""
        return self.get_setting('withdraw_enabled') == 'true'
    
    @performance_logger
    def is_withdraw_button_visible(self) -> bool:
        """التحقق من ظهور زر السحب"""
        return self.get_setting('withdraw_button_visible') == 'true'
    
    @performance_logger
    def is_ichancy_enabled(self) -> bool:
        """التحقق من تفعيل Ichancy"""
        return self.get_setting('ichancy_enabled') == 'true'
    
    @performance_logger
    def can_create_ichancy_account(self) -> bool:
        """التحقق من تفعيل إنشاء حساب Ichancy"""
        return (self.get_setting('ichancy_enabled') == 'true' and 
                self.get_setting('ichancy_create_account_enabled') == 'true')
    
    @performance_logger
    def get_exchange_rate(self) -> int:
        """جلب سعر صرف الدولار"""
        rate = self.get_setting('exchange_rate', '13000')
        try:
            return int(rate)
        except:
            return 13000
    
    @performance_logger
    def update_exchange_rate(self, rate: int, admin_id: int) -> bool:
        """تحديث سعر صرف الدولار"""
        if rate <= 0:
            return False
        
        return self.set_setting('exchange_rate', str(rate), admin_id, "تحديث سعر الصرف")
    
    @performance_logger
    def get_system_info(self) -> Dict[str, Any]:
        """معلومات النظام"""
        from core.config import VERSION, LAST_UPDATE, SYSTEM_CONSTANTS
        
        # إحصائيات قاعدة البيانات
        user_count = db.fetch_one("SELECT COUNT(*) as count FROM users")['count']
        transaction_count = db.fetch_one("SELECT COUNT(*) as count FROM transactions")['count']
        
        # إحصائيات الكاش
        cache_stats = self.cache.get_detailed_stats()
        
        return {
            "version": VERSION,
            "last_update": LAST_UPDATE,
            "users_count": user_count,
            "transactions_count": transaction_count,
            "system_constants": SYSTEM_CONSTANTS,
            "cache_stats": cache_stats,
            "uptime": "N/A",  # يمكن إضافته لاحقاً
            "database_size": "N/A"  # يمكن إضافته لاحقاً
        }
    
    @performance_logger
    def cleanup_old_logs(self, days: int = 30) -> int:
        """تنظيف السجلات القديمة"""
        try:
            query = """
                DELETE FROM settings_logs 
                WHERE created_at < datetime('now', ?)
            """
            
            cursor = db.execute_query(query, (f'-{days} days',))
            deleted = cursor.rowcount
            
            if deleted > 0:
                logger.info(f"تم حذف {deleted} سجل قديم")
            
            return deleted
        except Exception as e:
            logger.error(f"خطأ في تنظيف السجلات: {e}")
            return 0