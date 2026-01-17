"""
النقطة الرئيسية لتشغيل البوت - نظام كامل متكامل
"""

import os
import sys
import time
import threading
from datetime import datetime

# إضافة المسار للمكتبات
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logger import get_logger, system_logger
from core.database import db
from core.cache import cache
from core.security import rate_limiter
from core.config import VERSION, LAST_UPDATE, ADMIN_ID

from handlers.commands import bot, setup_commands
from handlers.callbacks import setup_callbacks
from handlers.messages import setup_messages
from handlers.sessions import cleanup_expired_sessions

from tasks.scheduler import setup_scheduler
from tasks.backup_task import setup_backup_task
from tasks.report_task import setup_report_task
from tasks.cleanup_task import setup_cleanup_task
from tasks.referral_task import setup_referral_task

logger = get_logger(__name__)


class BotManager:
    """مدير البوت الرئيسي"""
    
    def __init__(self):
        self.bot = bot
        self.is_running = False
        self.start_time = None
        self.stats = {
            "messages_processed": 0,
            "callbacks_processed": 0,
            "errors": 0,
            "users_served": 0
        }
    
    def initialize(self):
        """تهيئة النظام"""
        try:
            system_logger.info("=" * 60)
            system_logger.info("🚀 بدء تشغيل نظام البوت الاحترافي")
            system_logger.info(f"🔄 الإصدار: {VERSION}")
            system_logger.info(f"📅 آخر تحديث: {LAST_UPDATE}")
            system_logger.info(f"👑 الإدمن الرئيسي: {ADMIN_ID}")
            system_logger.info("=" * 60)
            
            # اختبار الاتصال بقاعدة البيانات
            db_status = self._test_database()
            if not db_status:
                system_logger.critical("❌ فشل الاتصال بقاعدة البيانات!")
                return False
            
            # اختبار الكاش
            cache_status = self._test_cache()
            if not cache_status:
                system_logger.warning("⚠️ مشكلة في نظام الكاش، لكن النظام سيستمر")
            
            # إعداد المعالجات
            setup_commands()
            setup_callbacks()
            setup_messages()
            
            # إعداد المهام المجدولة
            self._setup_scheduled_tasks()
            
            # تنظيف أولي
            self._initial_cleanup()
            
            system_logger.info("✅ تم تهيئة النظام بنجاح")
            return True
            
        except Exception as e:
            system_logger.critical(f"❌ فشل تهيئة النظام: {e}")
            return False
    
    def _test_database(self):
        """اختبار قاعدة البيانات"""
        try:
            # اختبار استعلام بسيط
            result = db.fetch_one("SELECT 1 as test")
            if result and result['test'] == 1:
                system_logger.info("✅ قاعدة البيانات تعمل بشكل صحيح")
                
                # إحصائيات قاعدة البيانات
                user_count = db.fetch_one("SELECT COUNT(*) as count FROM users")['count']
                system_logger.info(f"👥 عدد المستخدمين في قاعدة البيانات: {user_count}")
                return True
            return False
        except Exception as e:
            system_logger.error(f"❌ خطأ في قاعدة البيانات: {e}")
            return False
    
    def _test_cache(self):
        """اختبار نظام الكاش"""
        try:
            # اختبار كتابة وقراءة
            test_key = "system_test"
            test_value = "cache_working"
            
            cache.cache.set(test_key, test_value, ttl=10)
            retrieved = cache.cache.get(test_key)
            
            if retrieved == test_value:
                system_logger.info("✅ نظام الكاش يعمل بشكل صحيح")
                
                # عرض إحصائيات الكاش
                cache_stats = cache.get_detailed_stats()
                system_logger.info(f"💾 حجم الكاش: {cache_stats['lru_cache']['size']}/{cache_stats['lru_cache']['max_size']}")
                return True
            return False
        except Exception as e:
            system_logger.error(f"❌ خطأ في نظام الكاش: {e}")
            return False
    
    def _setup_scheduled_tasks(self):
        """إعداد المهام المجدولة"""
        try:
            # الجدولة الرئيسية
            scheduler = setup_scheduler()
            
            # المهام المجدولة
            setup_backup_task(scheduler)
            setup_report_task(scheduler)
            setup_cleanup_task(scheduler)
            setup_referral_task(scheduler)
            
            # مهمة مراقبة النظام
            scheduler.add_job(
                self._system_monitor,
                'interval',
                minutes=5,
                id='system_monitor',
                name='مراقبة النظام'
            )
            
            system_logger.info("✅ تم إعداد المهام المجدولة")
            return True
        except Exception as e:
            system_logger.error(f"❌ خطأ في إعداد المهام المجدولة: {e}")
            return False
    
    def _initial_cleanup(self):
        """تنظيف أولي للنظام"""
        try:
            # تنظيف الجلسات المنتهية
            sessions_cleaned = cleanup_expired_sessions()
            if sessions_cleaned > 0:
                system_logger.info(f"🧹 تم تنظيف {sessions_cleaned} جلسة منتهية")
            
            # تنظيف Rate Limiter
            rate_limiter.cleanup_old_requests()
            
            # تنظيف الكاش
            cache.auto_cleanup()
            
            system_logger.info("✅ تم التنظيف الأولي للنظام")
        except Exception as e:
            system_logger.error(f"❌ خطأ في التنظيف الأولي: {e}")
    
    def _system_monitor(self):
        """مراقبة النظام"""
        try:
            # إحصائيات قاعدة البيانات
            db_stats = db.get_stats()
            
            # إحصائيات الكاش
            cache_stats = cache.get_detailed_stats()
            
            # تسجيل المعلومات
            logger.info(f"📊 مراقبة النظام - الكاش: {cache_stats['lru_cache']['hit_rate']} - DB Pool: {db_stats['available']}/{db_stats['pool_size']}")
            
            # تحذير إذا كان هناك مشاكل
            if cache_stats['lru_cache']['hit_rate'] < '50.00%':
                logger.warning("⚠️ نسبة ضربات الكاش منخفضة!")
            
            if db_stats['available'] < 2:
                logger.warning("⚠️ عدد اتصالات قاعدة البيانات المتاحة منخفض!")
            
        except Exception as e:
            logger.error(f"❌ خطأ في مراقبة النظام: {e}")
    
    def start(self):
        """بدء تشغيل البوت"""
        try:
            system_logger.info("▶️ بدء تشغيل البوت...")
            
            # تسجيل وقت البدء
            self.start_time = datetime.now()
            self.is_running = True
            
            # عرض معلومات النظام
            self._show_system_info()
            
            # بدء البوت
            system_logger.info("🤖 البوت جاهز للعمل!")
            system_logger.info("=" * 60)
            
            # تشغيل البوت مع إعادة التشغيل التلقائي
            while self.is_running:
                try:
                    self.bot.infinity_polling(
                        timeout=60,
                        long_polling_timeout=60,
                        skip_pending=True,
                        restart_on_change=True
                    )
                except Exception as e:
                    logger.error(f"❌ توقف البوت بشكل غير متوقع: {e}")
                    
                    # محاولة إعادة التشغيل بعد 10 ثواني
                    logger.info("🔄 إعادة تشغيل البوت بعد 10 ثواني...")
                    time.sleep(10)
                    
                    # تنظيف قبل إعادة التشغيل
                    self._cleanup_before_restart()
            
        except KeyboardInterrupt:
            system_logger.info("⏹️ إيقاف البوت بواسطة المستخدم...")
            self.stop()
        except Exception as e:
            system_logger.critical(f"❌ خطأ حرج في تشغيل البوت: {e}")
            self.stop()
    
    def _show_system_info(self):
        """عرض معلومات النظام"""
        try:
            from services.system_service import SystemService
            system_service = SystemService()
            
            from services.user_service import UserService
            user_service = UserService()
            
            system_info = system_service.get_system_info()
            user_stats = user_service.get_system_stats()
            
            info_text = f"""
🎯 **معلومات النظام التشغيلية**

📊 **المستخدمون:**
• الإجمالي: {user_stats['total_users']:,}
• النشطين: {user_stats['active_users']:,}
• المحظورين: {user_stats['banned_users']:,}
• الأدمن: {user_stats['total_admins']:,}

⚙️ **النظام:**
• الإصدار: {system_info['version']}
• المعاملات: {system_info['transactions_count']:,}
• نسبة ضربات الكاش: {system_info['cache_stats']['lru_cache']['hit_rate']}

💾 **الأداء:**
• حجم الكاش: {system_info['cache_stats']['lru_cache']['size']}
• اتصالات DB المتاحة: {system_info.get('db_connections', 'N/A')}

🕒 **وقت البدء:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # إرسال للمشرف الرئيسي
            try:
                self.bot.send_message(
                    ADMIN_ID,
                    info_text,
                    parse_mode="Markdown"
                )
            except:
                pass
            
            system_logger.info("📨 تم إرسال معلومات النظام للمشرف")
            
        except Exception as e:
            system_logger.error(f"❌ خطأ في عرض معلومات النظام: {e}")
    
    def _cleanup_before_restart(self):
        """تنظيف قبل إعادة التشغيل"""
        try:
            # تنظيف الكاش
            cache.clear()
            
            # تنظيف قاعدة البيانات
            db.vacuum()
            
            # تنظيف Rate Limiter
            rate_limiter.cleanup_old_requests()
            
            system_logger.info("🧹 تم تنظيف النظام قبل إعادة التشغيل")
        except Exception as e:
            system_logger.error(f"❌ خطأ في التنظيف: {e}")
    
    def stop(self):
        """إيقاف البوت"""
        try:
            system_logger.info("⏹️ جاري إيقاف البوت...")
            self.is_running = False
            
            # حفظ الإحصائيات
            self._save_stats()
            
            # تنظيف نهائي
            self._final_cleanup()
            
            # إرسال رسالة إيقاف
            uptime = datetime.now() - self.start_time if self.start_time else None
            stop_msg = f"🛑 **تم إيقاف البوت**\n\n"
            
            if uptime:
                hours, remainder = divmod(uptime.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                stop_msg += f"⏱️ وقت التشغيل: {int(hours)}س {int(minutes)}د {int(seconds)}ث\n"
            
            stop_msg += f"📊 المعالجات: {self.stats['messages_processed']} رسائل، {self.stats['callbacks_processed']} كال باكات\n"
            stop_msg += f"👥 المستخدمون: {self.stats['users_served']}\n"
            stop_msg += f"🕒 وقت الإيقاف: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            try:
                self.bot.send_message(ADMIN_ID, stop_msg, parse_mode="Markdown")
            except:
                pass
            
            system_logger.info("✅ تم إيقاف البوت بنجاح")
            
        except Exception as e:
            system_logger.error(f"❌ خطأ في إيقاف البوت: {e}")
        finally:
            sys.exit(0)
    
    def _save_stats(self):
        """حفظ الإحصائيات"""
        try:
            # يمكن حفظ الإحصائيات في قاعدة البيانات هنا
            pass
        except Exception as e:
            system_logger.error(f"❌ خطأ في حفظ الإحصائيات: {e}")
    
    def _final_cleanup(self):
        """تنظيف نهائي"""
        try:
            # تنظيف قاعدة البيانات
            db.vacuum()
            
            # إغلاق اتصالات قاعدة البيانات
            # (يتم إغلاقها تلقائياً عند إنهاء البرنامج)
            
            system_logger.info("🧹 تم التنظيف النهائي")
        except Exception as e:
            system_logger.error(f"❌ خطأ في التنظيف النهائي: {e}")


def main():
    """الدالة الرئيسية"""
    try:
        # إنشاء مدير البوت
        bot_manager = BotManager()
        
        # تهيئة النظام
        if not bot_manager.initialize():
            system_logger.critical("❌ فشل تهيئة النظام، الخروج...")
            sys.exit(1)
        
        # بدء تشغيل البوت
        bot_manager.start()
        
    except Exception as e:
        system_logger.critical(f"❌ خطأ غير متوقع: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # تشغيل البوت
    main()