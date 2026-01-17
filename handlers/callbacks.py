"""
معالجات الكال باك - سرعة فائقة
"""

import time
from datetime import datetime
from telebot import TeleBot
from telebot.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import TOKEN
from core.cache import cache
from core.security import rate_limiter
from core.logger import get_logger, performance_logger
from services.user_service import UserService
from services.system_service import SystemService
from services.payment_service import PaymentService
from services.ichancy_service import IchancyService
from services.referral_service import ReferralService
from services.gift_service import GiftService
from services.admin_service import AdminService
from keyboards.user_keyboards import *
from keyboards.admin_keyboards import *
from handlers.sessions import get_session, set_session, clear_session

logger = get_logger(__name__)

# إنشاء البوت
bot = TeleBot(TOKEN)

# الخدمات
user_service = UserService()
system_service = SystemService()
payment_service = PaymentService()
ichancy_service = IchancyService()
referral_service = ReferralService()
gift_service = GiftService()
admin_service = AdminService()


@bot.callback_query_handler(func=lambda call: True)
@performance_logger
def handle_all_callbacks(call: CallbackQuery):
    """معالجة جميع الكال باكات"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        # قياس وقت الاستجابة
        start_time = time.time()
        
        # التحقق من الصيانة
        if system_service.is_maintenance_mode() and not user_service.is_admin(user_id):
            bot.answer_callback_query(call.id, "🔧 البوت تحت الصيانة")
            return
        
        # Rate limiting
        allowed, remaining = rate_limiter.is_allowed(user_id)
        if not allowed:
            bot.answer_callback_query(
                call.id,
                f"⏳ كثير طلبات! حاول بعد {remaining} ثانية",
                show_alert=True
            )
            return
        
        # توجيه الكال باك إلى الدالة المناسبة
        if data == "back":
            handle_back(call)
        elif data == "main_menu":
            handle_main_menu(call)
        elif data.startswith("ichancy_"):
            handle_ichancy_callbacks(call)
        elif data.startswith("deposit_"):
            handle_deposit_callbacks(call)
        elif data.startswith("withdraw_"):
            handle_withdraw_callbacks(call)
        elif data.startswith("referral_"):
            handle_referral_callbacks(call)
        elif data.startswith("gift_"):
            handle_gift_callbacks(call)
        elif data.startswith("admin_"):
            handle_admin_callbacks(call)
        elif data.startswith("approve_") or data.startswith("reject_"):
            handle_transaction_callbacks(call)
        else:
            bot.answer_callback_query(call.id, "⚙️ هذه الميزة قيد التطوير")
        
        # تسجيل وقت الاستجابة
        response_time = time.time() - start_time
        if response_time > 0.1:  # أكثر من 100ms
            logger.warning(f"استجابة بطيئة للكال باك {data}: {response_time:.3f}ث")
        
    except Exception as e:
        logger.error(f"خطأ في handle_all_callbacks: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ حدث خطأ، حاول مرة أخرى")
        except:
            pass


def handle_back(call: CallbackQuery):
    """معالجة زر الرجوع"""
    try:
        user_id = call.from_user.id
        
        # مسح الجلسة
        clear_session(user_id)
        
        # عرض القائمة الرئيسية
        user = user_service.get_or_create_user(user_id)
        if user:
            welcome_msg = system_service.get_welcome_message(user.balance)
            bot.edit_message_text(
                welcome_msg,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_main_menu(user_id),
                parse_mode="Markdown"
            )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"خطأ في handle_back: {e}")


def handle_main_menu(call: CallbackQuery):
    """العودة للقائمة الرئيسية"""
    handle_back(call)


def handle_ichancy_callbacks(call: CallbackQuery):
    """معالجة كال باكات Ichancy"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        if data == "ichancy_menu":
            # عرض قائمة Ichancy
            ichancy_info = ichancy_service.get_account_info(user_id)
            
            if ichancy_info:
                # لديه حساب
                msg = f"⚡ **حساب Ichancy الخاص بك**\n\n"
                msg += f"👤 **اسم المستخدم:** `{ichancy_info['username']}`\n"
                msg += f"💰 **الرصيد:** {ichancy_info['balance']:,} ليرة\n"
                msg += f"📅 **تاريخ الإنشاء:** {ichancy_info['created_at'][:10]}\n"
                
                if ichancy_info['last_login']:
                    msg += f"🔐 **آخر دخول:** {ichancy_info['last_login'][:16]}\n"
                
                msg += f"\n*احتفظ ببيانات حسابك في مكان آمن!*"
                
                bot.edit_message_text(
                    msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_ichancy_menu(has_account=True),
                    parse_mode="Markdown"
                )
            else:
                # لا يوجد حساب
                msg = "⚡ **نظام Ichancy**\n\n"
                msg += "ليس لديك حساب في Ichancy بعد!\n"
                msg += "يمكنك إنشاء حساب مجاني والاستفادة من جميع المزايا."
                
                bot.edit_message_text(
                    msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_ichancy_menu(has_account=False),
                    parse_mode="Markdown"
                )
            
            bot.answer_callback_query(call.id)
            
        elif data == "ichancy_create":
            # إنشاء حساب Ichancy
            if not system_service.can_create_ichancy_account():
                bot.answer_callback_query(
                    call.id,
                    "❌ إنشاء حسابات Ichancy معطل حالياً"
                )
                return
            
            result = ichancy_service.create_account(user_id)
            
            if result['success']:
                msg = f"✅ **تم إنشاء حساب Ichancy بنجاح!**\n\n"
                msg += f"👤 **اسم المستخدم:** `{result['username']}`\n"
                msg += f"🔑 **كلمة المرور:** `{result['password']}`\n\n"
                msg += f"💰 **الرصيد الابتدائي:** 0 ليرة\n\n"
                msg += f"⚠️ **احتفظ ببيانات حسابك في مكان آمن!**\n"
                msg += f"*يمكنك الآن استخدام جميع خدمات Ichancy*"
                
                bot.edit_message_text(
                    msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=get_ichancy_menu(has_account=True),
                    parse_mode="Markdown"
                )
            else:
                bot.answer_callback_query(call.id, result['message'])
            
        elif data == "ichancy_deposit":
            # شحن رصيد في Ichancy
            if not system_service.get_setting('ichancy_deposit_enabled') == 'true':
                bot.answer_callback_query(
                    call.id,
                    "❌ شحن رصيد في Ichancy معطل حالياً"
                )
                return
            
            set_session(user_id, "awaiting_ichancy_deposit_amount")
            
            msg = "💰 **شحن رصيد في Ichancy**\n\n"
            msg += "أدخل المبلغ الذي تريد شحنه في حساب Ichancy:\n"
            msg += "(سيتم خصمه من رصيدك في البوت)"
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        elif data == "ichancy_withdraw":
            # سحب رصيد من Ichancy
            if not system_service.get_setting('ichancy_withdraw_enabled') == 'true':
                bot.answer_callback_query(
                    call.id,
                    "❌ سحب رصيد من Ichancy معطل حالياً"
                )
                return
            
            set_session(user_id, "awaiting_ichancy_withdraw_amount")
            
            msg = "💸 **سحب رصيد من Ichancy**\n\n"
            msg += "أدخل المبلغ الذي تريد سحبه من حساب Ichancy:\n"
            msg += "(سيتم إضافته لرصيدك في البوت)"
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"خطأ في handle_ichancy_callbacks: {e}")


def handle_deposit_callbacks(call: CallbackQuery):
    """معالجة كال باكات الشحن"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        if data == "deposit_menu":
            # عرض قائمة طرق الدفع
            if not system_service.is_deposit_enabled():
                bot.answer_callback_query(
                    call.id,
                    system_service.get_setting('deposit_message', '💰 نظام الشحن معطل حالياً')
                )
                return
            
            msg = "💰 **اختر طريقة الشحن:**"
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_deposit_menu(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        elif data.startswith("pay_"):
            # اختيار طريقة دفع معينة
            payment_method = data.replace("pay_", "")
            
            # التحقق من إعدادات الدفع
            settings = payment_service.get_payment_settings(payment_method)
            if not settings or not settings['is_visible']:
                bot.answer_callback_query(call.id, "❌ طريقة الدفع غير متاحة")
                return
            
            if not settings['is_active']:
                bot.answer_callback_query(call.id, settings['pause_message'])
                return
            
            # حفظ الجلسة
            set_session(user_id, f"awaiting_{payment_method}_amount", {
                "payment_method": payment_method,
                "payment_name": payment_service.get_payment_method_name(payment_method)
            })
            
            # جلب الحدود
            limits = payment_service.get_payment_limits(payment_method)
            
            msg = f"💰 **{payment_service.get_payment_method_name(payment_method)}**\n\n"
            
            if payment_method == 'sham_cash_usd':
                exchange_rate = system_service.get_exchange_rate()
                msg += f"💱 **سعر الصرف:** 1$ = {exchange_rate:,} ليرة\n"
            
            if limits:
                min_amount = limits['min_amount']
                max_amount = limits['max_amount']
                
                if payment_method == 'sham_cash_usd':
                    msg += f"📊 **الحدود المسموحة:**\n"
                    msg += f"• الحد الأدنى: {min_amount:,} دولار\n"
                    msg += f"• الحد الأقصى: {max_amount:,} دولار\n\n"
                    msg += f"💸 أدخل المبلغ بالدولار:"
                else:
                    msg += f"📊 **الحدود المسموحة:**\n"
                    msg += f"• الحد الأدنى: {min_amount:,} ليرة\n"
                    msg += f"• الحد الأقصى: {max_amount:,} ليرة\n\n"
                    msg += f"💸 أدخل المبلغ بالليرة السورية:"
            else:
                if payment_method == 'sham_cash_usd':
                    msg += f"💸 أدخل المبلغ بالدولار:"
                else:
                    msg += f"💸 أدخل المبلغ بالليرة السورية:"
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"خطأ في handle_deposit_callbacks: {e}")


def handle_withdraw_callbacks(call: CallbackQuery):
    """معالجة كال باكات السحب"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        if data == "withdraw_menu":
            # عرض صفحة السحب
            if not system_service.is_withdraw_enabled():
                bot.answer_callback_query(
                    call.id,
                    system_service.get_setting('withdraw_message', '💸 نظام السحب معطل حالياً')
                )
                return
            
            # التحقق من ظهور زر السحب
            if not system_service.is_withdraw_button_visible():
                bot.answer_callback_query(call.id, "❌ زر السحب مخفي حالياً")
                return
            
            # تطبيق نسبة السحب
            withdraw_percentage = system_service.get_setting('withdraw_percentage', '0')
            
            msg = "💸 **سحب رصيد**\n\n"
            
            if withdraw_percentage != '0':
                msg += f"📊 **نسبة السحب:** {withdraw_percentage}%\n"
                msg += f"*سيتم خصم {withdraw_percentage}% من المبلغ المسحوب*\n\n"
            
            msg += "💰 أدخل المبلغ المراد سحبه:"
            
            set_session(user_id, "awaiting_withdraw_amount")
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"خطأ في handle_withdraw_callbacks: {e}")


def handle_referral_callbacks(call: CallbackQuery):
    """معالجة كال باكات الإحالات"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        if data == "referral_menu":
            # عرض صفحة الإحالات
            stats = referral_service.get_referral_stats(user_id)
            
            msg = "🤝 **نظام الإحالات**\n\n"
            
            msg += "📊 **النظام الأول:**\n"
            msg += f"• نسبة الربح: {stats['min_requirements']['commission_rate']}% من رابط الإحالة\n"
            msg += f"• شروط الحصول:\n"
            msg += f"  - {stats['min_requirements']['active_referrals']} إحالات نشطة على الأقل\n"
            msg += f"  - إحالة واحدة على الأقل بحرق {stats['min_requirements']['min_charge']:,}+ ليرة\n\n"
            
            msg += f"💰 **النظام الثاني:**\n"
            msg += f"• مكافأة: {stats['min_requirements']['bonus_amount']:,} ليرة لكل إحالة نشطة\n"
            msg += f"• قامت بشحن 10,000+ ليرة (أي عملة)\n\n"
            
            if stats['next_distribution']:
                msg += f"⏰ **موعد توزيع الجوائز القادم:**\n"
                msg += f"{stats['next_distribution']}\n\n"
            
            # رابط الإحالة
            if stats['referral_code']:
                msg += f"🔗 **رابط إحالتك:**\n"
                msg += f"`https://t.me/{bot.get_me().username}?start=ref_{stats['referral_code']}`\n\n"
            
            # إحصائيات المستخدم
            msg += f"📈 **إحصائياتك:**\n"
            msg += f"• عدد إحالاتك: {stats['total_referrals']}\n"
            msg += f"• الإحالات النشطة: {stats['active_referrals']}\n"
            
            if stats['total_commission'] > 0:
                msg += f"• 💰 الأرباح المستحقة: {stats['total_commission']:,} ليرة\n"
            
            msg += f"\n*لزيادة فرصك في الحصول على المكافآت، شارك رابط الإحالة الخاص بك مع أصدقائك!*"
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_referral_menu(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"خطأ في handle_referral_callbacks: {e}")


def handle_gift_callbacks(call: CallbackQuery):
    """معالجة كال باكات الهدايا"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        if data == "gift_menu":
            # عرض قائمة الهدايا
            msg = "🎁 **نظام الهدايا**\n\n"
            msg += "يمكنك:\n"
            msg += "• إهداء رصيد لأصدقائك\n"
            msg += "• تفعيل أكواد الهدايا\n"
            msg += "• مشاهدة سجل الهدايا"
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_gift_menu(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        elif data == "gift_send":
            # إهداء رصيد
            gift_percentage = system_service.get_setting('gift_percentage', '0')
            
            msg = "🎁 **إهداء رصيد**\n\n"
            
            if gift_percentage != '0':
                msg += f"📊 **نسبة الإهداء:** {gift_percentage}%\n"
                msg += f"*سيتم خصم {gift_percentage}% من المبلغ المُهدى*\n\n"
            
            msg += "💰 أدخل المبلغ الذي تريد إهداءه:"
            
            set_session(user_id, "awaiting_gift_amount")
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        elif data == "gift_code":
            # تفعيل كود هدية
            msg = "🎟️ **تفعيل كود هدية**\n\n"
            msg += "أدخل كود الهدية:"
            
            set_session(user_id, "awaiting_gift_code")
            
            bot.edit_message_text(
                msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        elif data == "gift_logs":
            # سجل الهدايا
            transactions = gift_service.get_gift_transactions(user_id, limit=20)
            
            if not transactions:
                bot.answer_callback_query(call.id, "❌ لا توجد معاملات إهداء")
                return
            
            msg = "📜 **سجل الهدايا**\n\n"
            
            for tx in transactions[:10]:  # عرض أول 10 فقط
                if tx['type'] == 'sent':
                    msg += f"⬆️ **أهديت إلى:** `{tx['partner_id']}`\n"
                else:
                    msg += f"⬇️ **تلقيت من:** `{tx['partner_id']}`\n"
                
                msg += f"💰 المبلغ: {tx['original_amount']:,} ليرة\n"
                
                if tx['gift_percentage'] > 0:
                    msg += f"📊 النسبة: {tx['gift_percentage']}%\n"
                    msg += f"🎯 الصافي: {tx['net_amount']:,} ليرة\n"
                
                msg += f"📅 التاريخ: {tx['created_at'][:16]}\n"
                msg += "─" * 20 + "\n"
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="gift_menu"))
            
            bot.edit_message_text(
                msg[:4000],  # حدود تليجرام
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"خطأ في handle_gift_callbacks: {e}")


def handle_admin_callbacks(call: CallbackQuery):
    """معالجة كال باكات الأدمن"""
    try:
        user_id = call.from_user.id
        data = call.data
        
        if not user_service.is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
            return
        
        if data == "admin_panel":
            # عرض لوحة التحكم
            from keyboards.admin_keyboards import get_admin_panel
            admin_panel = get_admin_panel(user_id)
            
            admin_msg = "👑 **لوحة تحكم الإدمن**\n\n"
            admin_msg += "اختر القسم الذي تريد إدارته:"
            
            bot.edit_message_text(
                admin_msg,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_panel,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        elif data == "admin_back_to_panel":
            # العودة للوحة التحكم
            handle_admin_callbacks(call)
        
        elif data.startswith("admin_"):
            # توجيه إلى service الأدمن
            admin_service.handle_admin_callback(call)
        
    except Exception as e:
        logger.error(f"خطأ في handle_admin_callbacks: {e}")


def handle_transaction_callbacks(call: CallbackQuery):
    """معالجة كال باكات الموافقة/الرفض على المعاملات"""
    try:
        user_id = call.from_user.id
        
        if not user_service.is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية")
            return
        
        data = call.data
        action, tx_id_str = data.split("_", 1)
        transaction_id = int(tx_id_str)
        
        # معالجة المعاملة
        result = payment_service.process_transaction(transaction_id, action, user_id)
        
        if result['success']:
            # تحديث الرسالة
            new_text = call.message.text + f"\n\n{result['message']}"
            bot.edit_message_text(
                new_text,
                call.message.chat.id,
                call.message.message_id
            )
            
            bot.answer_callback_query(call.id, result['message'])
        else:
            bot.answer_callback_query(call.id, result['message'])
        
    except Exception as e:
        logger.error(f"خطأ في handle_transaction_callbacks: {e}")
        bot.answer_callback_query(call.id, "❌ خطأ في المعالجة")


# إعداد الكال باكات
def setup_callbacks():
    """إعداد معالجات الكال باكات"""
    logger.info("✅ تم تحميل معالجات الكال باكات")