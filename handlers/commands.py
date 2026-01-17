"""
معالجات الأوامر الأساسية - سرعة فائقة
"""

import time
from datetime import datetime
from telebot import TeleBot
from telebot.types import Message, CallbackQuery

from core.config import TOKEN, ADMIN_ID
from core.cache import cache
from core.security import rate_limiter, require_admin
from core.logger import get_logger, performance_logger
from services.user_service import UserService
from services.system_service import SystemService
from services.ichancy_service import IchancyService
from keyboards.user_keyboards import (
    get_main_menu, get_ichancy_menu, get_deposit_menu, 
    get_referral_menu, get_gift_menu, get_logs_menu
)

logger = get_logger(__name__)

# إنشاء البوت
bot = TeleBot(TOKEN)

# الخدمات
user_service = UserService()
system_service = SystemService()
ichancy_service = IchancyService()


@bot.message_handler(commands=['start'])
@performance_logger
def start_command(message: Message):
    """معالجة أمر /start"""
    try:
        user_id = message.from_user.id
        
        # التحقق من الصيانة
        if system_service.is_maintenance_mode() and not user_service.is_admin(user_id):
            maintenance_msg = system_service.get_maintenance_message()
            bot.reply_to(message, maintenance_msg)
            return
        
        # جلب أو إنشاء المستخدم
        user = user_service.get_or_create_user(user_id)
        if not user:
            bot.reply_to(message, "❌ حدث خطأ في إنشاء حسابك")
            return
        
        # التحقق من الحظر
        if user.is_banned:
            ban_msg = f"🚫 **حسابك محظور!**\n\n"
            ban_msg += f"📝 السبب: {user.ban_reason or 'غير محدد'}\n"
            if user.ban_until:
                ban_msg += f"⏰ حتى: {user.ban_until}\n"
            ban_msg += f"\nللمساعدة راسل الدعم."
            
            bot.reply_to(message, ban_msg, parse_mode="Markdown")
            return
        
        # إرسال رسالة الترحيب
        welcome_msg = system_service.get_welcome_message(user.balance)
        
        # إرسال القائمة الرئيسية
        bot.send_message(
            message.chat.id,
            welcome_msg,
            reply_markup=get_main_menu(user_id),
            parse_mode="Markdown"
        )
        
        # مسح الجلسة القديمة
        from handlers.sessions import clear_session
        clear_session(user_id)
        
        logger.info(f"المستخدم {user_id} بدأ البوت")
        
    except Exception as e:
        logger.error(f"خطأ في start_command: {e}")
        try:
            bot.reply_to(message, "❌ حدث خطأ، حاول مرة أخرى")
        except:
            pass


@bot.message_handler(commands=['help'])
@performance_logger
def help_command(message: Message):
    """معالجة أمر /help"""
    try:
        help_text = """
🆘 **مركز المساعدة**

**الأوامر المتاحة:**
/start - بدء الاستخدام
/help - عرض هذه الرسالة
/balance - عرض رصيدك

**للدعم الفني:**
- راسل @username
- أو استخدم زر 'تواصل مع الدعم'

**معلومات مهمة:**
- الحد الأدنى للشحن: 1,000 ليرة
- الحد الأقصى للشحن: 50,000 ليرة
- عمليات السحب تتم خلال 24 ساعة
        """
        
        bot.reply_to(message, help_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"خطأ في help_command: {e}")


@bot.message_handler(commands=['balance'])
@performance_logger
def balance_command(message: Message):
    """عرض الرصيد"""
    try:
        user_id = message.from_user.id
        
        # التحقق من الصيانة
        if system_service.is_maintenance_mode() and not user_service.is_admin(user_id):
            return
        
        user = user_service.get_or_create_user(user_id)
        if not user:
            bot.reply_to(message, "❌ المستخدم غير موجود")
            return
        
        # جلب رصيد Ichancy إن وجد
        ichancy_info = ichancy_service.get_account_info(user_id)
        
        balance_msg = f"💰 **رصيدك الحالي:**\n\n"
        balance_msg += f"📊 **البوت:** {user.balance:,} ليرة سورية\n"
        
        if ichancy_info:
            balance_msg += f"⚡ **Ichancy:** {ichancy_info['balance']:,} ليرة\n"
        
        balance_msg += f"\n📅 **آخر نشاط:** {user.last_active[:16]}"
        
        bot.reply_to(message, balance_msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"خطأ في balance_command: {e}")


@bot.message_handler(commands=['admin'])
@performance_logger
@require_admin
def admin_command(message: Message):
    """لوحة تحكم الأدمن"""
    try:
        user_id = message.from_user.id
        
        if not user_service.is_admin(user_id):
            return
        
        from keyboards.admin_keyboards import get_admin_panel
        admin_panel = get_admin_panel(user_id)
        
        admin_msg = "👑 **لوحة تحكم الإدمن**\n\n"
        admin_msg += "اختر القسم الذي تريد إدارته:"
        
        bot.send_message(
            message.chat.id,
            admin_msg,
            reply_markup=admin_panel,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"خطأ في admin_command: {e}")


@bot.message_handler(commands=['stats'])
@performance_logger
@require_admin
def stats_command(message: Message):
    """إحصائيات النظام"""
    try:
        user_id = message.from_user.id
        
        if not user_service.is_admin(user_id):
            return
        
        # جلب إحصائيات النظام
        system_info = system_service.get_system_info()
        user_stats = user_service.get_system_stats()
        
        stats_msg = "📊 **إحصائيات النظام**\n\n"
        
        stats_msg += "👥 **المستخدمون:**\n"
        stats_msg += f"• الإجمالي: {user_stats['total_users']:,}\n"
        stats_msg += f"• النشطين: {user_stats['active_users']:,}\n"
        stats_msg += f"• المحظورين: {user_stats['banned_users']:,}\n\n"
        
        stats_msg += "👑 **الأدمن:**\n"
        stats_msg += f"• الإجمالي: {user_stats['total_admins']:,}\n\n"
        
        stats_msg += "⚙️ **النظام:**\n"
        stats_msg += f"• الإصدار: {system_info['version']}\n"
        stats_msg += f"• آخر تحديث: {system_info['last_update']}\n"
        stats_msg += f"• المعاملات: {system_info['transactions_count']:,}\n\n"
        
        stats_msg += "💾 **الكاش:**\n"
        stats_msg += f"• نسبة الضربات: {system_info['cache_stats']['lru_cache']['hit_rate']}\n"
        stats_msg += f"• العناصر المخزنة: {system_info['cache_stats']['lru_cache']['size']}\n\n"
        
        stats_msg += f"🕒 **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        bot.reply_to(message, stats_msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"خطأ في stats_command: {e}")


@bot.message_handler(commands=['fixdb'])
@performance_logger
@require_admin
def fixdb_command(message: Message):
    """إصلاح قاعدة البيانات"""
    try:
        user_id = message.from_user.id
        
        if not user_service.is_admin(user_id):
            return
        
        bot.reply_to(message, "🛠 جاري إصلاح قاعدة البيانات...")
        
        from core.database import db
        db.vacuum()
        
        # إعادة تهيئة الإعدادات
        system_service.init_default_settings()
        
        bot.reply_to(message, "✅ تم إصلاح قاعدة البيانات بنجاح!")
        
    except Exception as e:
        logger.error(f"خطأ في fixdb_command: {e}")
        bot.reply_to(message, f"❌ فشل إصلاح قاعدة البيانات: {e}")


@bot.message_handler(commands=['broadcast'])
@performance_logger
@require_admin
def broadcast_command(message: Message):
    """بث رسالة للجميع"""
    try:
        user_id = message.from_user.id
        
        if not user_service.is_admin(user_id):
            return
        
        # حفظ الجلسة للخطوة التالية
        from handlers.sessions import set_session
        set_session(user_id, "awaiting_broadcast_message")
        
        broadcast_msg = "📣 **بث رسالة للجميع**\n\n"
        broadcast_msg += "أدخل نص الرسالة التي تريد إرسالها لجميع المستخدمين:\n"
        broadcast_msg += "(يمكنك استخدام Markdown)"
        
        bot.send_message(message.chat.id, broadcast_msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"خطأ في broadcast_command: {e}")


@bot.message_handler(commands=['backup'])
@performance_logger
@require_admin
def backup_command(message: Message):
    """إنشاء نسخة احتياطية"""
    try:
        user_id = message.from_user.id
        
        if not user_service.is_admin(user_id):
            return
        
        bot.reply_to(message, "💾 جاري إنشاء نسخة احتياطية...")
        
        from tasks.backup_task import create_backup
        backup_result = create_backup()
        
        if backup_result['success']:
            backup_msg = f"✅ **تم إنشاء نسخة احتياطية**\n\n"
            backup_msg += f"📁 الملف: `{backup_result['file_name']}`\n"
            backup_msg += f"📊 الحجم: {backup_result['file_size']}\n"
            backup_msg += f"⏰ الوقت: {backup_result['timestamp']}"
            
            bot.reply_to(message, backup_msg, parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ فشل إنشاء النسخة: {backup_result['error']}")
        
    except Exception as e:
        logger.error(f"خطأ في backup_command: {e}")
        bot.reply_to(message, f"❌ خطأ في النسخ الاحتياطي: {e}")


# إعداد البوت
def setup_commands():
    """إعداد معالجات الأوامر"""
    logger.info("✅ تم تحميل معالجات الأوامر")