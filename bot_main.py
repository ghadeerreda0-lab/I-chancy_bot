"""
bot_main.py - الملف الرئيسي لتشغيل البوت
"""

import os
import sys
import time
import datetime
import logging
import traceback
from threading import Thread

from telebot import TeleBot
from telebot.types import Message, CallbackQuery
from apscheduler.schedulers.background import BackgroundScheduler

from config import (
    TOKEN, ADMIN_ID, VERSION, LAST_UPDATE,
    CHANNEL_SYR_CASH, CHANNEL_SCH_CASH, CHANNEL_WITHDRAW,
    DB_PATH, LOG_FILE
)

from database import (
    init_db, get_user, create_user, get_user_balance, add_balance,
    subtract_balance, get_all_users, get_top_users_by_balance,
    get_top_users_by_deposit, get_user_transactions, ban_user,
    unban_user, delete_user, reset_all_balances, set_session,
    get_session, clear_session, get_daily_report, get_deposit_report,
    get_withdraw_report, send_message_to_user, send_photo_to_user,
    broadcast_message, get_available_code_for_amount, fill_code_with_amount,
    add_transaction, get_payment_settings, update_payment_settings,
    get_payment_limits, send_urgent_notification, get_exchange_rate,
    create_ichancy_account, get_ichancy_account, update_ichancy_balance,
    get_referral_settings, update_referral_settings, get_user_referrals,
    get_top_referrals, calculate_referral_commissions, distribute_referral_commissions,
    generate_gift_code, use_gift_code, send_gift, get_setting, update_setting,
    is_admin, can_manage_admins, get_all_admins, add_admin, remove_admin
)

from keyboards import (
    main_menu, deposit_menu_keyboard, user_logs_keyboard, ichancy_info_keyboard,
    admin_panel_keyboard, general_settings_keyboard, payment_settings_keyboard,
    withdraw_settings_keyboard, users_management_keyboard, referral_settings_keyboard,
    ichancy_settings_keyboard, reports_keyboard, manage_admins_keyboard,
    deposit_report_keyboard, transaction_approval_buttons, confirmation_keyboard
)

from utils import (
    safe_execute, rate_limit, CacheWithTTL, RateLimiter,
    check_maintenance, check_payment_enabled, check_withdraw_enabled,
    check_ichancy_enabled, format_currency, format_date
)

# =========================
# تهيئة البوت
# =========================
bot = TeleBot(TOKEN)
scheduler = BackgroundScheduler()
cache = CacheWithTTL()
rate_limiter = RateLimiter()

# =========================
# إعدادات التسجيل
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================
# معالجة الأوامر الأساسية
# =========================

@bot.message_handler(commands=["start"])
@rate_limit()
@safe_execute
def start_command(message: Message):
    """
    معالجة أمر /start
    """
    uid = message.from_user.id

    # التحقق من الصيانة
    if check_maintenance(uid):
        return

    # إنشاء المستخدم إذا لم يكن موجوداً
    if not get_user(uid):
        create_user(uid)

    user_data = get_user(uid)
    bal = user_data['balance'] if user_data else 0

    # التحقق من الحظر
    if user_data and user_data['is_banned']:
        ban_reason = user_data['ban_reason'] or "غير محدد"
        ban_until = user_data['ban_until'] or "غير محدد"
        bot.send_message(
            uid,
            f"🚫 **حسابك محظور!**\n\n"
            f"📝 السبب: {ban_reason}\n"
            f"⏰ حتى: {ban_until}\n\n"
            f"للمساعدة راسل الدعم."
        )
        return

    # إرسال رسالة الترحيب
    welcome_template = get_setting('welcome_message')
    if not welcome_template:
        welcome_template = "👋 أهلاً بك!\nرصيدك الحالي: {balance} ليرة سورية"
    
    welcome_msg = welcome_template.format(balance=format_currency(bal))

    bot.send_message(message.chat.id, welcome_msg, reply_markup=main_menu(uid))
    clear_session(uid)

@bot.callback_query_handler(func=lambda call: True)
@rate_limit()
@safe_execute 
def all_callbacks(call: CallbackQuery):
    """
    معالجة جميع الكال باكات
    """
    uid = call.from_user.id

    # التحقق من الصيانة
    if check_maintenance(uid):
        bot.answer_callback_query(call.id)
        return

    data = call.data

    try:
        # ===== الأزرار الأساسية =====
        if data == "back":
            bot.edit_message_text(
                "✅ عدنا إلى القائمة الرئيسية:",
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=main_menu(uid)
            )
            clear_session(uid)
            bot.answer_callback_query(call.id)
            return

        if data == "admin_back_to_panel":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "🎛 **لوحة تحكم الإدمن**\n\nاختر القسم الذي تريد إدارته:",
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=admin_panel_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== نظام Ichancy =====
        if data == "ichancy_info":
            account = get_ichancy_account(uid)
            if not account:
                bot.answer_callback_query(call.id, "❌ ليس لديك حساب Ichancy")
                return

            message_text = (
                f"⚡ **معلومات حساب Ichancy**\n\n"
                f"👤 **اسم المستخدم:** `{account['username']}`\n"
                f"🔑 **كلمة المرور:** `{account['password']}`\n"
                f"💰 **الرصيد:** {format_currency(account['balance'])}\n"
                f"📅 **تاريخ الإنشاء:** {format_date(account['created_at'])}\n"
                f"🔐 **آخر دخول:** {account['last_login'] or 'لم يسجل دخول بعد'}\n\n"
                f"*احتفظ ببيانات حسابك في مكان آمن!*"
            )

            bot.edit_message_text(
                message_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=ichancy_info_keyboard(uid),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "ichancy_create":
            if not check_ichancy_enabled(uid, 'create'):
                bot.answer_callback_query(call.id)
                return

            result = create_ichancy_account(uid)
            if result['success']:
                message_text = (
                    f"✅ **تم إنشاء حساب Ichancy بنجاح!**\n\n"
                    f"👤 **اسم المستخدم:** `{result['username']}`\n"
                    f"🔑 **كلمة المرور:** `{result['password']}`\n\n"
                    f"💰 **الرصيد الابتدائي:** 0 ليرة\n\n"
                    f"⚠️ **احتفظ ببيانات حسابك في مكان آمن!**\n"
                    f"*يمكنك الآن استخدام جميع خدمات Ichancy*"
                )

                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("⚡ عرض معلومات الحساب", callback_data="ichancy_info"))
                kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))

                bot.edit_message_text(
                    message_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            else:
                bot.answer_callback_query(call.id, result['message'])
            return

        # ===== قائمة الشحن الموحدة =====
        if data == "deposit_menu":
            bot.edit_message_text(
                "💰 **اختر طريقة الشحن:**",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=deposit_menu_keyboard()
            )
            bot.answer_callback_query(call.id)
            return

        # ===== زر إهداء الرصيد =====
        if data == "gift_balance":
            set_session(uid, "awaiting_gift_amount")
            bot.edit_message_text(
                "🎁 **إهداء رصيد**\n\n"
                "أدخل المبلغ الذي تريد إهداءه:",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            return

        # ===== كود الهدية =====
        if data == "gift_code":
            set_session(uid, "awaiting_gift_code")
            bot.edit_message_text(
                "🎁 **تفعيل كود هدية**\n\n"
                "أدخل كود الهدية:",
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            return

        # ===== السجل الشخصي =====
        if data == "user_logs":
            bot.edit_message_text(
                "📜 **سجلك الشخصي**\n\n"
                "اختر نوع السجل الذي تريد عرضه:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=user_logs_keyboard()
            )
            bot.answer_callback_query(call.id)
            return

        if data == "user_deposit_logs":
            transactions = get_user_transactions(uid)
            if not transactions:
                bot.answer_callback_query(call.id, "❌ لا توجد عمليات شحن")
                return

            message_text = "💳 **سجل شحناتك:**\n\n"
            total = 0

            for tx in transactions:
                if tx[1] == 'charge':  # type = charge
                    tx_id, _, amount, method, status, created_at, notes = tx
                    status_icon = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
                    message_text += f"{status_icon} **{format_date(created_at)}**\n"
                    message_text += f"💰 المبلغ: {format_currency(amount)}\n"
                    if method:
                        message_text += f"📱 الطريقة: {method}\n"
                    message_text += f"🆔 العملية: #{tx_id}\n"
                    message_text += "─" * 20 + "\n"

                    if status == 'approved':
                        total += amount

            message_text += f"\n📊 **المجموع:** {format_currency(total)}"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للسجل", callback_data="user_logs"))
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للقائمة", callback_data="back"))

            bot.edit_message_text(
                message_text[:4000],  # حدود تليجرام
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "user_withdraw_logs":
            transactions = get_user_transactions(uid)
            if not transactions:
                bot.answer_callback_query(call.id, "❌ لا توجد عمليات سحب")
                return

            message_text = "💸 **سجل سحوباتك:**\n\n"
            total = 0

            for tx in transactions:
                if tx[1] == 'withdraw':  # type = withdraw
                    tx_id, _, amount, method, status, created_at, notes = tx
                    status_icon = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
                    message_text += f"{status_icon} **{format_date(created_at)}**\n"
                    message_text += f"💰 المبلغ: {format_currency(amount)}\n"
                    if method:
                        message_text += f"📱 الطريقة: {method}\n"
                    message_text += f"🆔 العملية: #{tx_id}\n"
                    message_text += "─" * 20 + "\n"

                    if status == 'approved':
                        total += amount

            message_text += f"\n📊 **المجموع:** {format_currency(total)}"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للسجل", callback_data="user_logs"))
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للقائمة", callback_data="back"))

            bot.edit_message_text(
                message_text[:4000],
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== لوحة التحكم =====
        if data == "admin_panel":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "🎛 **لوحة تحكم الإدمن**\n\nاختر القسم الذي تريد إدارته:",
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=admin_panel_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== الإعدادات العامة =====
        if data == "admin_general_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "⚙️ **الإعدادات العامة**\n\nإدارة جميع إعدادات النظام:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=general_settings_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # تبديل إعدادات Ichancy
        if data == "admin_toggle_ichancy":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            current = get_setting('ichancy_enabled') == 'true'
            new_value = 'false' if current else 'true'
            update_setting('ichancy_enabled', new_value, uid, "تبديل تفعيل Ichancy")

            bot.answer_callback_query(call.id, f"✅ أصبح Ichancy: {'مفعل' if new_value == 'true' else 'معطل'}")

            # تحديث الواجهة
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=general_settings_keyboard()
                )
            except:
                pass
            return

        if data in ["admin_toggle_ichancy_create", "admin_toggle_ichancy_deposit", "admin_toggle_ichancy_withdraw"]:
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            setting_map = {
                "admin_toggle_ichancy_create": "ichancy_create_account_enabled",
                "admin_toggle_ichancy_deposit": "ichancy_deposit_enabled", 
                "admin_toggle_ichancy_withdraw": "ichancy_withdraw_enabled"
            }

            setting_key = setting_map[data]
            current = get_setting(setting_key) == 'true'
            new_value = 'false' if current else 'true'
            update_setting(setting_key, new_value, uid, f"تبديل {setting_key}")

            status = "مفعل" if new_value == 'true' else "معطل"
            bot.answer_callback_query(call.id, f"✅ تم: {status}")

            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=general_settings_keyboard()
                )
            except:
                pass
            return

        # تبديل إعدادات الشحن والسحب
        if data in ["admin_toggle_deposit", "admin_toggle_withdraw", "admin_toggle_withdraw_button", "admin_toggle_maintenance"]:
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            setting_map = {
                "admin_toggle_deposit": "deposit_enabled",
                "admin_toggle_withdraw": "withdraw_enabled",
                "admin_toggle_withdraw_button": "withdraw_button_visible",
                "admin_toggle_maintenance": "maintenance_mode"
            }

            setting_key = setting_map[data]
            current = get_setting(setting_key) == 'true'
            new_value = 'false' if current else 'true'
            update_setting(setting_key, new_value, uid, f"تبديل {setting_key}")

            status = "مفعل" if new_value == 'true' else "معطل"
            if data == "admin_toggle_withdraw_button":
                status = "مرئي" if new_value == 'true' else "مخفي"

            bot.answer_callback_query(call.id, f"✅ تم: {status}")

            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=general_settings_keyboard()
                )
            except:
                pass
            return

        # ===== إعدادات الدفع =====
        if data == "admin_payment_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "💰 **إعدادات الدفع**\n\nإدارة جميع طرق الدفع:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=payment_settings_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # إعدادات سيرياتيل كاش
        if data == "admin_syriatel_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            settings = get_payment_settings('syriatel_cash')
            status_text = f"📱 **إعدادات سيرياتيل كاش**\n\n"
            if settings:
                status_text += f"👁️ الحالة: {'مرئي' if settings['is_visible'] else 'مخفي'}\n"
                status_text += f"⚡ الخدمة: {'مفعلة' if settings['is_active'] else 'متوقفة'}\n"

            kb = InlineKeyboardMarkup(row_width=2)
            kb.row(
                InlineKeyboardButton(f"👁️ {'إخفاء' if settings and settings['is_visible'] else 'إظهار'}", 
                                   callback_data="admin_toggle_syriatel_visible"),
                InlineKeyboardButton(f"⚡ {'إيقاف' if settings and settings['is_active'] else 'تفعيل'}", 
                                   callback_data="admin_toggle_syriatel_active")
            )
            kb.row(
                InlineKeyboardButton("🔢 إدارة الأكواد", callback_data="admin_syriatel_codes"),
                InlineKeyboardButton("🎁 إدارة البونص", callback_data="admin_syriatel_bonus")
            )
            kb.row(
                InlineKeyboardButton("📝 رسالة التوقف", callback_data="admin_edit_syriatel_msg"),
                InlineKeyboardButton("💰 حدود المبالغ", callback_data="admin_edit_syriatel_limits")
            )
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_payment_settings"))

            bot.edit_message_text(
                status_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_toggle_syriatel_visible":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            settings = get_payment_settings('syriatel_cash')
            if settings:
                new_visible = not settings['is_visible']
                update_payment_settings('syriatel_cash', is_visible=new_visible, admin_id=uid)
                status = "مرئي 👁️" if new_visible else "مخفي 👁️‍🗨️"
                bot.answer_callback_query(call.id, f"✅ أصبح سيرياتيل كاش: {status}")

                try:
                    bot.edit_message_reply_markup(
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=payment_settings_keyboard()
                    )
                except:
                    pass
            return

        if data == "admin_toggle_syriatel_active":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            settings = get_payment_settings('syriatel_cash')
            if settings:
                new_active = not settings['is_active']
                update_payment_settings('syriatel_cash', is_active=new_active, admin_id=uid)
                status = "مفعل ✅" if new_active else "متوقف ⏸️"
                bot.answer_callback_query(call.id, f"✅ أصبح سيرياتيل كاش: {status}")

                try:
                    bot.edit_message_reply_markup(
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=payment_settings_keyboard()
                    )
                except:
                    pass
            return

        # ===== إعدادات السحب =====
        if data == "admin_withdraw_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "💸 **إعدادات السحب**\n\nإدارة جميع إعدادات نظام السحب:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=withdraw_settings_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_edit_withdraw_percentage":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_edit_withdraw_percentage")
            bot.send_message(
                uid,
                "📊 **تعديل نسبة السحب**\n\n"
                "أدخل نسبة السحب (0-100):\n"
                "0 يعني بدون نسبة خصم\n"
                "مثال: 10 ← نسبة 10%"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== إدارة المستخدمين =====
        if data == "admin_users_management":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "👥 **إدارة المستخدمين**\n\nاختر الإجراء المطلوب:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=users_management_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_users_count":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            users = get_all_users()
            total = len(users)

            # عد المستخدمين المحظورين
            banned = sum(1 for u in users if u[4])  # العمود 4 هو is_banned

            message = (
                f"👥 **إحصائيات المستخدمين**\n\n"
                f"📊 **إجمالي المستخدمين:** {total}\n"
                f"🚫 **المحظورين:** {banned}\n"
                f"✅ **النشطين:** {total - banned}\n\n"
                f"📈 **آخر 5 مستخدمين جدد:**\n"
            )

            for user in users[:5]:
                user_id, balance, created_at, last_active, is_banned = user
                message += f"• `{user_id}` - {format_currency(balance)} - {created_at[:10]}\n"

            bot.send_message(uid, message, parse_mode="Markdown")
            bot.answer_callback_query(call.id, f"✅ العدد: {total}")
            return

        if data == "admin_add_balance":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_add_balance_user")
            bot.send_message(
                uid,
                "💰 **إضافة رصيد لمستخدم**\n\n"
                "أدخل ID المستخدم:"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_edit_gift_percentage":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_edit_gift_percentage")
            bot.send_message(
                uid,
                "🎁 **تعديل نسبة الإهداء**\n\n"
                "أدخل نسبة الإهداء (0-100):\n"
                "0 يعني بدون نسبة خصم\n"
                "مثال: 5 ← نسبة 5% على المبلغ المُهدى"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_top_balance":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_top_balance_count")
            bot.send_message(
                uid,
                "🏆 **أعلى رصيد مستخدمين**\n\n"
                "أدخل عدد المستخدمين المطلوب عرضهم (مثال: 20):"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_reset_all_balances":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            # طلب تأكيد
            kb = confirmation_keyboard("confirm_reset_balances", "admin_back_to_panel")

            bot.edit_message_text(
                "⚠️ **تصفير جميع الأرصدة**\n\n"
                "هل أنت متأكد أنك تريد تصفير أرصدة جميع المستخدمين؟\n"
                "هذا الإجراء لا يمكن التراجع عنه!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb
            )
            bot.answer_callback_query(call.id)
            return

        if data == "confirm_reset_balances":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            result = reset_all_balances()
            if result['success']:
                message = f"✅ تم تصفير أرصدة {result['affected']} مستخدم"
            else:
                message = f"❌ خطأ: {result.get('message', 'غير معروف')}"

            bot.edit_message_text(
                message,
                call.message.chat.id,
                call.message.message_id
            )
            bot.answer_callback_query(call.id, message)
            return

        # ===== إعدادات الإحالات =====
        if data == "admin_referral_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "🤝 **إعدادات الإحالات**\n\nإدارة نظام الإحالات والمكافآت:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=referral_settings_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_edit_referral_rate":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_edit_referral_rate")
            bot.send_message(
                uid,
                "📊 **تعديل نسبة الإحالات**\n\n"
                "أدخل نسبة العمولة (0-100):\n"
                "0 يعني بدون عمولة\n"
                "مثال: 10 ← نسبة 10% من الشحن"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_top_referrals":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_top_referrals_count")
            bot.send_message(
                uid,
                "📈 **أعلى الإحالات**\n\n"
                "أدخل عدد الإحالات المطلوب عرضهم (مثال: 15):"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_distribute_referrals":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            result = distribute_referral_commissions()
            bot.answer_callback_query(call.id, result['message'])
            return

        # ===== نظام Ichancy في الأدمن =====
        if data == "admin_ichancy_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "⚡ **إعدادات نظام Ichancy**\n\nإدارة نظام Ichancy بالكامل:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=ichancy_settings_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== التقارير =====
        if data == "admin_reports":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "📊 **التقارير والإحصائيات**\n\nاختر نوع التقرير:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=reports_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "report_today":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            report = get_daily_report()
            if not report:
                bot.answer_callback_query(call.id, "❌ فشل في جلب التقرير")
                return

            message = (
                f"📊 **تقرير اليوم - {report['date']}**\n\n"
                f"👥 **المستخدمون:**\n"
                f"• 👤 مستخدمين جدد: {report['new_users']}\n"
                f"• 📊 الإجمالي: {report['total_users']}\n"
                f"• 🎯 النشطين: {report['active_users']}\n\n"
                f"💰 **الأداء المالي:**\n"
                f"• 💳 إجمالي الإيداع: {format_currency(report['total_deposit'])}\n"
                f"• 💸 إجمالي السحب: {format_currency(report['total_withdraw'])}\n"
                f"• 📈 صافي التدفق: {format_currency(report['net_flow'])}\n"
                f"• 📋 المعاملات: {report['total_transactions']}\n"
                f"• ⏳ المعلقة: {report['pending_transactions']}\n\n"
                f"🤝 **الإحالات:**\n"
                f"• 👥 إحالات جديدة: {report['new_referrals']}\n\n"
                f"📱 **أكواد سيرياتيل:**\n"
                f"• 🔢 عدد الأكواد: {report['active_codes']}\n"
                f"• 💰 المستخدم: {format_currency(report['used_capacity'])}\n"
                f"• 📊 السعة: {format_currency(report['total_capacity'])}\n"
                f"• 📈 النسبة: {report['fill_percentage']}%\n\n"
                f"🕒 **التاريخ:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            bot.send_message(uid, message, parse_mode="Markdown")
            bot.answer_callback_query(call.id, "✅ تم إرسال التقرير")
            return

        if data == "report_deposit":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "💰 **تقرير عمليات الشحن**\n\nاختر طريقة الدفع:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=deposit_report_keyboard()
            )
            bot.answer_callback_query(call.id)
            return

        if data.startswith("report_deposit_"):
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            method_map = {
                "report_deposit_syriatel": "سيرياتيل كاش",
                "report_deposit_sham": "شام كاش",
                "report_deposit_sham_usd": "شام كاش دولار",
                "report_deposit_all": None
            }

            method_name = method_map[data]
            report = get_deposit_report(method_name)

            if not report:
                bot.answer_callback_query(call.id, "❌ فشل في جلب التقرير")
                return

            message = (
                f"💳 **تقرير الشحن - {report['date']}**\n\n"
                f"📱 **الطريقة:** {report['payment_method']}\n"
                f"💰 **إجمالي المبلغ:** {format_currency(report['total_amount'])}\n"
                f"📋 **عدد العمليات:** {report['total_count']}\n\n"
            )

            if report['transactions']:
                message += "📅 **آخر 10 عمليات:**\n\n"
                for tx in report['transactions'][:10]:
                    tx_id, user_id, amount, method, created_at, status, user_balance = tx
                    status_icon = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
                    message += f"{status_icon} **{format_date(created_at)}**\n"
                    message += f"👤 المستخدم: `{user_id}`\n"
                    message += f"💰 المبلغ: {format_currency(amount)}\n"
                    message += f"💳 الرصيد: {format_currency(user_balance)}\n"
                    message += f"🆔 العملية: #{tx_id}\n"
                    message += "─" * 20 + "\n"
            else:
                message += "❌ لا توجد عمليات شحن لهذا اليوم\n"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للتقارير", callback_data="admin_reports"))

            bot.send_message(uid, message[:4000], parse_mode="Markdown", reply_markup=kb)
            bot.answer_callback_query(call.id, "✅ تم إرسال التقرير")
            return

        if data == "report_withdraw":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            report = get_withdraw_report()
            if not report:
                bot.answer_callback_query(call.id, "❌ فشل في جلب التقرير")
                return

            message = (
                f"💸 **تقرير السحب - {report['date']}**\n\n"
                f"💰 **إجمالي المبلغ:** {format_currency(report['total_amount'])}\n"
                f"📋 **عدد العمليات:** {report['total_count']}\n\n"
            )

            if report['transactions']:
                message += "📅 **آخر 10 عمليات:**\n\n"
                for tx in report['transactions'][:10]:
                    tx_id, user_id, amount, method, created_at, status, user_balance = tx
                    status_icon = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
                    message += f"{status_icon} **{format_date(created_at)}**\n"
                    message += f"👤 المستخدم: `{user_id}`\n"
                    message += f"💰 المبلغ: {format_currency(amount)}\n"
                    message += f"💳 الرصيد: {format_currency(user_balance)}\n"
                    message += f"🆔 العملية: #{tx_id}\n"
                    message += "─" * 20 + "\n"
            else:
                message += "❌ لا توجد عمليات سحب لهذا اليوم\n"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للتقارير", callback_data="admin_reports"))

            bot.send_message(uid, message[:4000], parse_mode="Markdown", reply_markup=kb)
            bot.answer_callback_query(call.id, "✅ تم إرسال التقرير")
            return

        # ===== إدارة الأدمن =====
        if data == "admin_manage_admins":
            if not can_manage_admins(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            bot.edit_message_text(
                "👑 **إدارة الأدمن**\n\nإضافة وحذف الأدمن الثانويين:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=manage_admins_keyboard(),
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_add_admin":
            if not can_manage_admins(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_add_admin")
            bot.send_message(
                uid,
                "➕ **إضافة أدمن جديد**\n\n"
                "أدخل ID المستخدم المراد ترقيته لأدمن:"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_remove_admin":
            if not can_manage_admins(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            set_session(uid, "admin_remove_admin")
            bot.send_message(
                uid,
                "🗑️ **حذف أدمن**\n\n"
                "أدخل ID الأدمن المراد حذفه:"
            )
            bot.answer_callback_query(call.id)
            return

        if data == "admin_list_admins":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return

            admins = get_all_admins()
            if not admins:
                bot.answer_callback_query(call.id, "❌ لا توجد أدمن ثانويين")
                return

            message = "👑 **قائمة الأدمن الثانويين:**\n\n"

            for admin in admins:
                user_id, created_at, added_at, added_by = admin
                message += f"👤 **المستخدم:** `{user_id}`\n"
                message += f"📅 انضم للبوت: {created_at[:10]}\n"
                message += f"👑 أصبح أدمن: {added_at[:10]}\n"
                message += f"➕ تمت الإضافة بواسطة: `{added_by}`\n"
                message += "─" * 20 + "\n"

            message += f"\n📊 **المجموع:** {len(admins)} أدمن ثانوي"

            bot.send_message(uid, message, parse_mode="Markdown")
            bot.answer_callback_query(call.id, f"✅ عدد الأدمن: {len(admins)}")
            return

        # ===== طرق الدفع من القائمة الفرعية =====
        if data.startswith("pay_"):
            method = data.replace("pay_", "")

            if not check_payment_enabled(uid, method):
                bot.answer_callback_query(call.id)
                return

            method_names = {
                'syriatel_cash': 'سيرياتيل كاش',
                'sham_cash': 'شام كاش',
                'sham_cash_usd': 'شام كاش دولار'
            }

            method_name = method_names.get(method, method)
            set_session(uid, f"awaiting_{method}_amount", {
                "payment_method": method_name,
                "type": "charge"
            })

            # جلب الحدود
            limits = get_payment_limits(method)
            message = f"💰 **{method_name}**\n\n"

            if method == 'sham_cash_usd':
                exchange_rate = get_exchange_rate()
                message += f"💱 **سعر الصرف:** 1$ = {format_currency(exchange_rate)}\n"

            if limits:
                min_amount = limits['min_amount']
                max_amount = limits['max_amount']

                if method == 'sham_cash_usd':
                    message += f"📊 **الحدود المسموحة:**\n"
                    message += f"• الحد الأدنى: {format_currency(min_amount, 'دولار')}\n"
                    message += f"• الحد الأقصى: {format_currency(max_amount, 'دولار')}\n\n"
                    message += f"💸 أدخل المبلغ بالدولار:"
                else:
                    message += f"📊 **الحدود المسموحة:**\n"
                    message += f"• الحد الأدنى: {format_currency(min_amount)}\n"
                    message += f"• الحد الأقصى: {format_currency(max_amount)}\n\n"
                    message += f"💸 أدخل المبلغ بالليرة السورية:"
            else:
                if method == 'sham_cash_usd':
                    message += f"💸 أدخل المبلغ بالدولار:"
                else:
                    message += f"💸 أدخل المبلغ بالليرة السورية:"

            bot.edit_message_text(
                message,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== زر السحب من القائمة الرئيسية =====
        if data == "withdraw":
            if not check_withdraw_enabled(uid):
                bot.answer_callback_query(call.id)
                return

            set_session(uid, "awaiting_withdraw_amount")

            withdraw_percentage = int(get_setting('withdraw_percentage', 0))
            message = "💸 **سحب رصيد**\n\n"

            if withdraw_percentage > 0:
                message += f"📊 **نسبة السحب:** {withdraw_percentage}%\n"
                message += f"*سيتم خصم {withdraw_percentage}% من المبلغ المسحوب*\n\n"

            message += "💰 أدخل المبلغ المراد سحبه:"

            bot.edit_message_text(
                message,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== نظام الإحالات للمستخدم =====
        if data == "referrals":
            user_data = get_user(uid)
            if not user_data:
                bot.answer_callback_query(call.id, "❌ خطأ في جلب البيانات")
                return

            referrals = get_user_referrals(uid)
            settings = get_referral_settings()

            message = "🤝 **نظام الإحالات**\n\n"

            # معلومات النظام
            if settings:
                message += f"📊 **النظام الأول:**\n"
                message += f"• نسبة الربح: {settings['commission_rate']}% من رابط الإحالة\n"
                message += f"• شروط الحصول:\n"
                message += f"  - {settings['min_active_referrals']} إحالات نشطة على الأقل\n"
                message += f"  - إحالة واحدة على الأقل بحرق {format_currency(settings['min_charge_amount'])}+\n\n"

                message += f"💰 **النظام الثاني:**\n"
                message += f"• مكافأة: {format_currency(settings['bonus_amount'])} لكل إحالة نشطة\n"
                message += f"• قامت بشحن 10,000+ ليرة (أي عملة)\n\n"

                if settings['next_distribution']:
                    message += f"⏰ **موعد توزيع الجوائز القادم:**\n"
                    message += f"{settings['next_distribution']}\n\n"

            # رابط الإحالة
            referral_code = user_data['referral_code']
            if referral_code:
                bot_username = bot.get_me().username
                message += f"🔗 **رابط إحالتك:**\n"
                message += f"`https://t.me/{bot_username}?start=ref_{referral_code}`\n\n"

            # إحصائيات المستخدم
            total_refs = len(referrals)
            active_refs = sum(1 for r in referrals if r[3])  # r[3] هو is_active

            message += f"📈 **إحصائياتك:**\n"
            message += f"• عدد إحالاتك: {total_refs}\n"
            message += f"• الإحالات النشطة: {active_refs}\n"

            # حساب الأرباح المستحقة (مبسط)
            if active_refs >= settings.get('min_active_referrals', 5) if settings else False:
                eligible_refs = [r for r in referrals if r[2] >= (settings.get('min_charge_amount', 100000) if settings else 100000)]
                if eligible_refs:
                    total_charged = sum(r[2] for r in eligible_refs)
                    commission = total_charged * (settings.get('commission_rate', 10) / 100)
                    bonus = len(eligible_refs) * (settings.get('bonus_amount', 2000) if settings else 2000)
                    total_commission = commission + bonus

                    message += f"• 💰 الأرباح المستحقة: {format_currency(int(total_commission))}\n"

            message += f"\n*لزيادة فرصك في الحصول على المكافآت، شارك رابط الإحالة الخاص بك مع أصدقائك!*"

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))

            bot.edit_message_text(
                message,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        # ===== أزرار أخرى (مؤقتة) =====
        if data in ["support", "contact", "rules", "tutorials", "bets", "jackpot", "vp", "apk"]:
            bot.answer_callback_query(call.id, "⚙️ هذه الميزة قيد التطوير")
            return

        # ===== معالجة أزرار الموافقة/الرفض للمعاملات =====
        if data.startswith("approve_") or data.startswith("reject_"):
            process_transaction_callback(call)
            return

    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الكال باك: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ حدث خطأ، حاول مرة أخرى")
        except:
            pass
# استمرار bot_main.py

# =========================
# معالجة الرسائل النصية
# =========================

@bot.message_handler(func=lambda m: True)
@rate_limit()
@safe_execute
def handle_message(message: Message):
    """
    معالجة جميع الرسائل النصية
    """
    uid = message.from_user.id

    # التحقق من الصيانة
    if check_maintenance(uid):
        return

    # التحقق من الحظر
    user_data = get_user(uid)
    if user_data and user_data['is_banned']:
        bot.send_message(uid, "🚫 حسابك محظور ولا يمكنك استخدام البوت.")
        return

    session = get_session(uid)
    if not session:
        # إذا لم تكن هناك جلسة، عرض القائمة الرئيسية
        bot.send_message(uid, "اختر من القائمة:", reply_markup=main_menu(uid))
        return

    step = session.get("step")
    temp_data = session.get("temp_data")

    # ===== نظام الإهداء =====
    if step == "awaiting_gift_amount":
        handle_gift_amount(message, uid)
        return

    if step == "awaiting_gift_receiver":
        handle_gift_receiver(message, uid, temp_data)
        return

    # ===== كود الهدية =====
    if step == "awaiting_gift_code":
        handle_gift_code(message, uid)
        return

    # ===== إدخال المبلغ للشحن =====
    for method in ['syriatel_cash', 'sham_cash', 'sham_cash_usd']:
        if step == f"awaiting_{method}_amount":
            handle_deposit_amount(message, uid, method, temp_data)
            return

    # ===== إدخال رقم العملية للشحن =====
    for method in ['syriatel_cash', 'sham_cash', 'sham_cash_usd']:
        if step == f"awaiting_{method}_txid":
            handle_deposit_txid(message, uid, method, temp_data)
            return

    # ===== إدخال المبلغ للسحب =====
    if step == "awaiting_withdraw_amount":
        handle_withdraw_amount(message, uid)
        return

    if step == "awaiting_withdraw_details":
        handle_withdraw_details(message, uid, temp_data)
        return

    # ===== إدخالات الأدمن =====

    # إضافة رصيد لمستخدم
    if step == "admin_add_balance_user":
        handle_admin_add_balance_user(message, uid)
        return

    if step == "admin_add_balance_amount":
        handle_admin_add_balance_amount(message, uid, temp_data)
        return

    # تعديل نسبة الإهداء
    if step == "admin_edit_gift_percentage":
        handle_admin_edit_gift_percentage(message, uid)
        return

    # تعديل نسبة السحب
    if step == "admin_edit_withdraw_percentage":
        handle_admin_edit_withdraw_percentage(message, uid)
        return

    # أعلى رصيد مستخدمين
    if step == "admin_top_balance_count":
        handle_admin_top_balance_count(message, uid)
        return

    # أعلى الإحالات
    if step == "admin_top_referrals_count":
        handle_admin_top_referrals_count(message, uid)
        return

    # تعديل نسبة الإحالات
    if step == "admin_edit_referral_rate":
        handle_admin_edit_referral_rate(message, uid)
        return

    # إضافة أدمن
    if step == "admin_add_admin":
        handle_admin_add_admin(message, uid)
        return

    # حذف أدمن
    if step == "admin_remove_admin":
        handle_admin_remove_admin(message, uid)
        return

    # إذا لم تكن هناك جلسة مطابقة، عرض القائمة الرئيسية
    bot.send_message(uid, "اختر من القائمة:", reply_markup=main_menu(uid))

# =========================
# دوال مساعدة للمعالجة
# =========================

def handle_gift_amount(message: Message, user_id: int):
    """
    معالجة إدخال مبلغ الإهداء
    """
    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
            return

        amount = int(message.text)
        user_balance = get_user_balance(user_id)

        if amount <= 0:
            bot.send_message(message.chat.id, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return

        if amount > user_balance:
            bot.send_message(message.chat.id, f"❌ رصيدك غير كافي. رصيدك الحالي: {format_currency(user_balance)}")
            clear_session(user_id)
            return

        # حفظ المبلغ والانتقال للخطوة التالية
        set_session(user_id, "awaiting_gift_receiver", {"amount": amount})

        bot.send_message(
            message.chat.id,
            f"🎁 **إهداء رصيد**\n\n"
            f"💰 المبلغ: {format_currency(amount)}\n\n"
            f"أدخل ID المستخدم المراد إهداؤه:"
        )

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)
        logger.error(f"خطأ في إدخال مبلغ الإهداء: {e}")

def handle_gift_receiver(message: Message, user_id: int, temp_data: dict):
    """
    معالجة إدخال مستلم الإهداء
    """
    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ ID غير صحيح، أدخل رقم صحيح فقط")
            return

        receiver_id = int(message.text)
        amount = temp_data.get("amount")

        if receiver_id == user_id:
            bot.send_message(message.chat.id, "❌ لا يمكن إهداء نفسك")
            clear_session(user_id)
            return

        # التحقق من وجود المستلم
        receiver = get_user(receiver_id)
        if not receiver:
            bot.send_message(message.chat.id, "❌ المستخدم غير موجود في البوت")
            clear_session(user_id)
            return

        # التحقق من حظر المستلم
        if receiver.get('is_banned'):
            bot.send_message(message.chat.id, "❌ لا يمكن إهداء مستخدم محظور")
            clear_session(user_id)
            return

        # إرسال الهدية
        result = send_gift(user_id, receiver_id, amount)

        if result['success']:
            bot.send_message(
                message.chat.id,
                f"✅ **تم إرسال الهدية بنجاح!**\n\n"
                f"👤 إلى المستخدم: `{receiver_id}`\n"
                f"💰 المبلغ المُرسل: {format_currency(amount)}\n"
                f"🎯 المبلغ المُستلم: {format_currency(result['net_amount'])}\n"
                f"💳 رصيدك الجديد: {format_currency(result['new_sender_balance'])}"
            )
        else:
            bot.send_message(message.chat.id, result['message'])

        clear_session(user_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)
        logger.error(f"خطأ في إدخال مستلم الإهداء: {e}")

def handle_gift_code(message: Message, user_id: int):
    """
    معالجة إدخال كود الهدية
    """
    try:
        code = message.text.strip().upper()
        if not code:
            bot.send_message(message.chat.id, "❌ الكود فارغ")
            return

        result = use_gift_code(code, user_id)
        bot.send_message(message.chat.id, result['message'])
        clear_session(user_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)
        logger.error(f"خطأ في استخدام كود الهدية: {e}")

def handle_deposit_amount(message: Message, user_id: int, method: str, temp_data: dict):
    """
    معالجة إدخال مبلغ الشحن
    """
    try:
        if not message.text.replace('.', '').isdigit():
            bot.send_message(message.chat.id, "❌ المبلغ غير صحيح")
            return

        amount = float(message.text) if method == 'sham_cash_usd' else int(message.text)

        # التحقق من الحدود
        limits = get_payment_limits(method)
        if limits:
            min_amount = limits['min_amount']
            max_amount = limits['max_amount']

            if amount < min_amount:
                bot.send_message(
                    message.chat.id,
                    f"❌ الحد الأدنى للشحن هو {format_currency(min_amount, 'دولار' if method == 'sham_cash_usd' else 'ليرة')}"
                )
                return

            if amount > max_amount:
                bot.send_message(
                    message.chat.id,
                    f"❌ الحد الأقصى للشحن هو {format_currency(max_amount, 'دولار' if method == 'sham_cash_usd' else 'ليرة')}"
                )
                return

        # تحويل الدولار لليرة إذا لزم
        final_amount = amount
        if method == 'sham_cash_usd':
            exchange_rate = get_exchange_rate()
            final_amount = int(amount * exchange_rate)

        # حفظ البيانات
        set_session(user_id, f"awaiting_{method}_txid", {
            "payment_method": temp_data["payment_method"],
            "amount": amount,
            "final_amount": final_amount,
            "method": method,
            "type": "charge"
        })

        # إرسال رسالة التأكيد
        message_text = f"💰 **تفاصيل التحويل**\n\n"

        if method == 'sham_cash_usd':
            exchange_rate = get_exchange_rate()
            message_text += f"💵 المبلغ: {format_currency(amount, 'دولار')}\n"
            message_text += f"💱 سعر الصرف: 1$ = {format_currency(exchange_rate)}\n"
            message_text += f"📊 القيمة: {format_currency(final_amount)}\n\n"
        else:
            message_text += f"💰 المبلغ: {format_currency(amount)}\n\n"

        message_text += f"🔑 الآن أدخل رقم العملية (Transaction ID) لإكمال الطلب:"

        bot.send_message(message.chat.id, message_text)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)
        logger.error(f"خطأ في إدخال مبلغ الشحن: {e}")

def handle_deposit_txid(message: Message, user_id: int, method: str, temp_data: dict):
    """
    معالجة إدخال رقم العملية للشحن
    """
    try:
        transaction_id = message.text.strip()
        if not transaction_id:
            bot.send_message(message.chat.id, "❌ رقم العملية فارغ")
            return

        amount = temp_data.get("amount")
        final_amount = temp_data.get("final_amount")
        method_name = temp_data.get("payment_method")

        # التحقق من كود سيرياتيل إذا كانت الطريقة سيرياتيل
        if method == 'syriatel_cash':
            code_result = get_available_code_for_amount(final_amount)

            if not code_result["success"]:
                # إشعار عاجل
                send_urgent_notification(user_id, final_amount, code_result.get("max_available", 0))

                bot.send_message(
                    message.chat.id,
                    f"❌ **لا يوجد كود يمكنه استيعاب {format_currency(final_amount)}**\n\n"
                    f"⚠️ أكبر كود متاح: {format_currency(code_result.get('max_available', 0))}\n"
                    f"📢 تم إرسال إشعار للأدمن\n"
                    f"🔁 يمكنك المحاولة بمبلغ أقل"
                )
                clear_session(user_id)
                return

            # تعبئة الكود
            fill_result = fill_code_with_amount(
                code_result["code_id"], 
                user_id, 
                final_amount
            )

            if not fill_result["success"]:
                bot.send_message(message.chat.id, fill_result["message"])
                clear_session(user_id)
                return

            # تحديث بيانات الجلسة
            temp_data["code_id"] = code_result["code_id"]
            temp_data["code_number"] = code_result["code_number"]

        # إضافة المعاملة
        tx_id, order_number, order_datetime = add_transaction(
            user_id, "charge", final_amount, method_name, transaction_id
        )

        if tx_id:
            # إرسال للقناة المخصصة
            channel = CHANNEL_SYR_CASH if method == 'syriatel_cash' else CHANNEL_SCH_CASH
            kb_admin = transaction_approval_buttons(tx_id)

            admin_message = f"💳 **طلب شحن جديد ({method_name})!**\n"
            admin_message += f"🆔 رقم الطلب الشهري: #{order_number}\n"

            if method == 'sham_cash_usd':
                admin_message += f"💵 المبلغ: {format_currency(amount, 'دولار')}\n"
                admin_message += f"💰 القيمة: {format_currency(final_amount)}\n"
            else:
                admin_message += f"💰 المبلغ: {format_currency(final_amount)}\n"

            admin_message += (
                f"🔑 رقم العملية: {transaction_id}\n"
                f"👤 المستخدم: {user_id}\n"
                f"🗓 التاريخ: {order_datetime}"
            )

            if method == 'syriatel_cash' and 'code_number' in temp_data:
                admin_message += f"\n🔢 الكود: {temp_data['code_number']}"

            bot.send_message(channel, admin_message, reply_markup=kb_admin)

            # رسالة للمستخدم
            user_message = f"✅ **تم إرسال طلبك للمراجعة**\n\n"

            if method == 'sham_cash_usd':
                user_message += f"💵 المبلغ: {format_currency(amount, 'دولار')}\n"
                user_message += f"💰 القيمة: {format_currency(final_amount)}\n"
            else:
                user_message += f"💰 المبلغ: {format_currency(final_amount)}\n"

            user_message += f"⏳ سيتم تفعيل الرصيد بعد الموافقة"

            bot.send_message(message.chat.id, user_message)

        clear_session(user_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء معالجة الطلب")
        clear_session(user_id)
        logger.error(f"خطأ في إدخال رقم العملية: {e}")

def handle_withdraw_amount(message: Message, user_id: int):
    """
    معالجة إدخال مبلغ السحب
    """
    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
            return

        amount = int(message.text)
        user_balance = get_user_balance(user_id)

        if amount <= 0:
            bot.send_message(message.chat.id, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return

        if amount > user_balance:
            bot.send_message(message.chat.id, f"❌ رصيدك غير كافي. رصيدك الحالي: {format_currency(user_balance)}")
            clear_session(user_id)
            return

        # تطبيق نسبة السحب
        withdraw_percentage = int(get_setting('withdraw_percentage', 0))
        net_amount = amount

        if withdraw_percentage > 0:
            deduction = int(amount * withdraw_percentage / 100)
            net_amount = amount - deduction

        # حفظ البيانات والانتقال للخطوة التالية
        set_session(user_id, "awaiting_withdraw_details", {
            "amount": amount,
            "net_amount": net_amount,
            "deduction": amount - net_amount if withdraw_percentage > 0 else 0
        })

        message_text = (
            f"💸 **تفاصيل السحب**\n\n"
            f"💰 المبلغ المطلوب: {format_currency(amount)}\n"
        )

        if withdraw_percentage > 0:
            message_text += f"📊 نسبة السحب: {withdraw_percentage}%\n"
            message_text += f"💸 المبلغ المخصوم: {format_currency(amount - net_amount)}\n"
            message_text += f"🎯 المبلغ الذي ستستلمه: {format_currency(net_amount)}\n\n"

        message_text += f"💳 رصيدك الحالي: {format_currency(user_balance)}\n\n"
        message_text += "📝 أدخل رقم الحساب أو التفاصيل المطلوبة:"

        bot.send_message(message.chat.id, message_text)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)
        logger.error(f"خطأ في إدخال مبلغ السحب: {e}")

def handle_withdraw_details(message: Message, user_id: int, temp_data: dict):
    """
    معالجة إدخال تفاصيل السحب
    """
    try:
        account_details = message.text.strip()
        if not account_details:
            bot.send_message(message.chat.id, "❌ التفاصيل فارغة")
            return

        data = temp_data
        amount = data.get("amount")
        net_amount = data.get("net_amount")
        deduction = data.get("deduction", 0)

        # خصم المبلغ من رصيد المستخدم
        result = subtract_balance(user_id, amount)

        if result['new'] < 0:
            bot.send_message(message.chat.id, "❌ خطأ في الرصيد")
            clear_session(user_id)
            return

        # إضافة المعاملة
        tx_id = add_transaction(
            user_id, "withdraw", amount, "manual", "withdraw", account_details
        )[0]

        # إرسال إشعار للأدمن
        kb_admin = transaction_approval_buttons(tx_id)

        admin_message = (
            f"💸 **طلب سحب جديد!**\n\n"
            f"👤 المستخدم: `{user_id}`\n"
            f"💰 المبلغ: {format_currency(amount)}\n"
        )

        if deduction > 0:
            admin_message += f"💸 الخصم: {format_currency(deduction)}\n"
            admin_message += f"🎯 الصافي: {format_currency(net_amount)}\n"

        admin_message += (
            f"📝 التفاصيل: {account_details}\n"
            f"💳 الرصيد السابق: {format_currency(result['old'])}\n"
            f"💳 الرصيد الحالي: {format_currency(result['new'])}\n"
            f"🕒 الوقت: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        try:
            bot.send_message(CHANNEL_WITHDRAW, admin_message, parse_mode="Markdown", reply_markup=kb_admin)
        except:
            # إذا فشل إرسال للقناة، أرسل للإدمن
            admins = [ADMIN_ID] + [admin[0] for admin in get_all_admins()]
            for admin_id in admins:
                try:
                    bot.send_message(admin_id, admin_message, parse_mode="Markdown", reply_markup=kb_admin)
                except:
                    pass

        # إرسال رسالة للمستخدم
        user_message = (
            f"✅ **تم إرسال طلب السحب للمراجعة**\n\n"
            f"💰 المبلغ: {format_currency(amount)}\n"
        )

        if deduction > 0:
            user_message += f"💸 الخصم: {format_currency(deduction)}\n"
            user_message += f"🎯 المبلغ المستلم: {format_currency(net_amount)}\n"

        user_message += (
            f"📝 التفاصيل: {account_details}\n"
            f"💳 رصيدك الجديد: {format_currency(result['new'])}\n\n"
            f"⏳ سيتم معالجة طلبك في أقرب وقت"
        )

        bot.send_message(message.chat.id, user_message)
        clear_session(user_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)
        logger.error(f"خطأ في إدخال تفاصيل السحب: {e}")

# =========================
# معالجات الأدمن
# =========================

def handle_admin_add_balance_user(message: Message, admin_id: int):
    """
    معالجة إدخال ID المستخدم للإضافة
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ ID غير صحيح")
            return

        target_id = int(message.text)
        target_user = get_user(target_id)

        if not target_user:
            bot.send_message(message.chat.id, "❌ المستخدم غير موجود")
            clear_session(admin_id)
            return

        set_session(admin_id, "admin_add_balance_amount", {"target_id": target_id})
        bot.send_message(
            message.chat.id,
            f"👤 **المستخدم:** `{target_id}`\n"
            f"💳 **الرصيد الحالي:** {format_currency(target_user['balance'])}\n\n"
            f"💰 أدخل المبلغ المراد إضافته:"
        )

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في إدخال ID للإضافة: {e}")

def handle_admin_add_balance_amount(message: Message, admin_id: int, temp_data: dict):
    """
    معالجة إدخال مبلغ الإضافة
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ المبلغ غير صحيح")
            return

        amount = int(message.text)
        target_id = temp_data.get("target_id")

        if amount <= 0:
            bot.send_message(message.chat.id, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return

        result = add_balance(target_id, amount)

        bot.send_message(
            message.chat.id,
            f"✅ **تم إضافة الرصيد بنجاح**\n\n"
            f"👤 المستخدم: `{target_id}`\n"
            f"💰 المبلغ: {format_currency(amount)}\n"
            f"💳 الرصيد السابق: {format_currency(result['old'])}\n"
            f"💳 الرصيد الجديد: {format_currency(result['new'])}"
        )

        # إرسال إشعار للمستخدم
        try:
            bot.send_message(
                target_id,
                f"🎉 **تم إضافة رصيد إلى حسابك!**\n\n"
                f"💰 المبلغ: {format_currency(amount)}\n"
                f"💳 رصيدك الجديد: {format_currency(result['new'])}\n\n"
                f"من قبل الإدارة 👑"
            )
        except:
            pass

        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في إدخال مبلغ للإضافة: {e}")

def handle_admin_edit_gift_percentage(message: Message, admin_id: int):
    """
    معالجة تعديل نسبة الإهداء
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ النسبة غير صحيحة")
            return

        percentage = int(message.text)

        if percentage < 0 or percentage > 100:
            bot.send_message(message.chat.id, "❌ النسبة يجب أن تكون بين 0 و 100")
            return

        update_setting('gift_percentage', str(percentage), admin_id, "تعديل نسبة الإهداء")

        bot.send_message(
            message.chat.id,
            f"✅ **تم تعديل نسبة الإهداء**\n\n"
            f"📊 النسبة الجديدة: {percentage}%\n\n"
            f"*{'بدون خصم' if percentage == 0 else f'سيتم خصم {percentage}% من المبلغ المُهدى'}*"
        )

        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في تعديل نسبة الإهداء: {e}")

def handle_admin_edit_withdraw_percentage(message: Message, admin_id: int):
    """
    معالجة تعديل نسبة السحب
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ النسبة غير صحيحة")
            return

        percentage = int(message.text)

        if percentage < 0 or percentage > 100:
            bot.send_message(message.chat.id, "❌ النسبة يجب أن تكون بين 0 و 100")
            return

        update_setting('withdraw_percentage', str(percentage), admin_id, "تعديل نسبة السحب")

        bot.send_message(
            message.chat.id,
            f"✅ **تم تعديل نسبة السحب**\n\n"
            f"📊 النسبة الجديدة: {percentage}%\n\n"
            f"*{'بدون خصم' if percentage == 0 else f'سيتم خصم {percentage}% من المبلغ المسحوب'}*"
        )

        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في تعديل نسبة السحب: {e}")

def handle_admin_top_balance_count(message: Message, admin_id: int):
    """
    معالجة طلب أعلى الرصيد
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ العدد غير صحيح")
            return

        limit = int(message.text)

        if limit <= 0 or limit > 100:
            bot.send_message(message.chat.id, "❌ العدد يجب أن يكون بين 1 و 100")
            return

        users = get_top_users_by_balance(limit)

        message_text = f"🏆 **أعلى {limit} رصيد مستخدمين**\n\n"

        for i, user in enumerate(users, 1):
            user_id, balance, created_at, last_active = user
            message_text += f"{i}. `{user_id}`\n"
            message_text += f"   💰 الرصيد: {format_currency(balance)}\n"
            message_text += f"   📅 الانضمام: {created_at[:10]}\n"
            message_text += f"   🕒 آخر نشاط: {last_active[:16] if last_active else 'غير معروف'}\n\n"

        bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في جلب أعلى الرصيد: {e}")

def handle_admin_top_referrals_count(message: Message, admin_id: int):
    """
    معالجة طلب أعلى الإحالات
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ العدد غير صحيح")
            return

        limit = int(message.text)

        if limit <= 0 or limit > 50:
            bot.send_message(message.chat.id, "❌ العدد يجب أن يكون بين 1 و 50")
            return

        referrals = get_top_referrals(limit)

        if not referrals:
            bot.send_message(message.chat.id, "❌ لا توجد إحالات")
            clear_session(admin_id)
            return

        message_text = f"📈 **أعلى {len(referrals)} إحالة**\n\n"

        for i, ref in enumerate(referrals, 1):
            referrer_id, total_refs, active_refs, total_commission, username = ref
            message_text += f"{i}. `{referrer_id}`\n"
            message_text += f"   👥 الإجمالي: {total_refs} إحالة\n"
            message_text += f"   ✅ النشطة: {active_refs} إحالة\n"
            message_text += f"   💰 العمولة: {format_currency(total_commission or 0)}\n\n"

        bot.send_message(message.chat.id, message_text, parse_mode="Markdown")
        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في جلب أعلى الإحالات: {e}")

def handle_admin_edit_referral_rate(message: Message, admin_id: int):
    """
    معالجة تعديل نسبة الإحالات
    """
    if not is_admin(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ النسبة غير صحيحة")
            return

        rate = int(message.text)

        if rate < 0 or rate > 100:
            bot.send_message(message.chat.id, "❌ النسبة يجب أن تكون بين 0 و 100")
            return

        update_referral_settings(commission_rate=rate)

        bot.send_message(
            message.chat.id,
            f"✅ **تم تعديل نسبة الإحالات**\n\n"
            f"📊 النسبة الجديدة: {rate}%\n\n"
            f"*{'بدون عمولة' if rate == 0 else f'عمولة {rate}% من الشحن'}*"
        )

        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في تعديل نسبة الإحالات: {e}")

def handle_admin_add_admin(message: Message, admin_id: int):
    """
    معالجة إضافة أدمن
    """
    if not can_manage_admins(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ ID غير صحيح")
            return

        target_id = int(message.text)

        if target_id == admin_id:
            bot.send_message(message.chat.id, "❌ لا يمكن إضافة نفسك")
            clear_session(admin_id)
            return

        result = add_admin(target_id, admin_id)
        bot.send_message(message.chat.id, result['message'])
        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في إضافة أدمن: {e}")

def handle_admin_remove_admin(message: Message, admin_id: int):
    """
    معالجة حذف أدمن
    """
    if not can_manage_admins(admin_id):
        clear_session(admin_id)
        return

    try:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ ID غير صحيح")
            return

        target_id = int(message.text)

        if target_id == admin_id:
            bot.send_message(message.chat.id, "❌ لا يمكن حذف نفسك")
            clear_session(admin_id)
            return

        if target_id == ADMIN_ID:
            bot.send_message(message.chat.id, "❌ لا يمكن حذف المشرف الرئيسي")
            clear_session(admin_id)
            return

        result = remove_admin(target_id, admin_id)
        bot.send_message(message.chat.id, result['message'])
        clear_session(admin_id)

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ")
        clear_session(admin_id)
        logger.error(f"خطأ في حذف أدمن: {e}")

# =========================
# معالجة أزرار الموافقة/الرفض
# =========================

@safe_execute
def process_transaction_callback(call: CallbackQuery):
    """
    معالجة أزرار الموافقة/الرفض للمعاملات
    """
    try:
        data = call.data
        uid = call.from_user.id

        if not is_admin(uid):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية")
            return

        action, tx_id_str = data.split("_", 1)
        tx_id = int(tx_id_str)

        from database import conn
        
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT t.user_id, t.amount, t.status, t.type, t.payment_method, t.notes,
                       u.balance as user_balance
                FROM transactions t
                JOIN users u ON t.user_id = u.user_id
                WHERE t.id = ?
            """, (tx_id,))
            tx = c.fetchone()

            if not tx:
                bot.answer_callback_query(call.id, "⚠️ العملية غير موجودة")
                return

            user_id, amount, status, tx_type, payment_method, notes, user_balance = tx

            if status != 'pending':
                bot.answer_callback_query(call.id, f"⚠️ تم معالجة العملية مسبقاً ({status})")
                return

            if action == "approve":
                new_status = 'approved'
                status_text = "✅ مقبول"

                if tx_type == 'charge':
                    # إضافة الرصيد للمستخدم
                    new_balance = user_balance + amount
                    c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

                    # إرسال رسالة للمستخدم
                    try:
                        bot.send_message(
                            user_id,
                            f"✅ **تم قبول طلب الشحن!**\n\n"
                            f"💰 المبلغ: {format_currency(amount)}\n"
                            f"💳 رصيدك الجديد: {format_currency(new_balance)}\n\n"
                            f"شكراً لاستخدامك خدماتنا! 🎉"
                        )
                    except:
                        pass

                    # تحديث رسالة الأدمن
                    admin_message = call.message.text + f"\n\n{status_text}\n💰 الرصيد الجديد: {format_currency(new_balance)}"
                    bot.edit_message_text(
                        admin_message,
                        call.message.chat.id,
                        call.message.message_id
                    )

                elif tx_type == 'withdraw':
                    # للسحب، الرصيد تم خصمه مسبقاً، فقط نغير الحالة
                    try:
                        bot.send_message(
                            user_id,
                            f"✅ **تم قبول طلب السحب!**\n\n"
                            f"💰 المبلغ: {format_currency(amount)}\n"
                            f"💳 سيتم تحويل المبلغ قريباً\n\n"
                            f"تفاصيل: {notes}"
                        )
                    except:
                        pass

                    admin_message = call.message.text + f"\n\n{status_text}"
                    bot.edit_message_text(
                        admin_message,
                        call.message.chat.id,
                        call.message.message_id
                    )

                bot.answer_callback_query(call.id, "✅ تمت الموافقة")

            elif action == "reject":
                new_status = 'rejected'
                status_text = "❌ مرفوض"

                if tx_type == 'withdraw':
                    # إرجاع الرصيد للمستخدم إذا كان سحب مرفوض
                    new_balance = user_balance + amount
                    c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

                    try:
                        bot.send_message(
                            user_id,
                            f"❌ **تم رفض طلب السحب**\n\n"
                            f"💰 المبلغ: {format_currency(amount)}\n"
                            f"💳 تم إرجاع المبلغ لرصيدك\n"
                            f"💳 رصيدك الجديد: {format_currency(new_balance)}\n\n"
                            f"للتفاصيل راسل الدعم"
                        )
                    except:
                        pass

                    admin_message = call.message.text + f"\n\n{status_text}\n💰 تم إرجاع الرصيد"
                    bot.edit_message_text(
                        admin_message,
                        call.message.chat.id,
                        call.message.message_id
                    )
                else:
                    try:
                        bot.send_message(user_id, f"❌ تم رفض طلب الشحن بمبلغ {format_currency(amount)}")
                    except:
                        pass

                    admin_message = call.message.text + f"\n\n{status_text}"
                    bot.edit_message_text(
                        admin_message,
                        call.message.chat.id,
                        call.message.message_id
                    )

                bot.answer_callback_query(call.id, "❌ تم الرفض")

            # تحديث حالة المعاملة
            c.execute("UPDATE transactions SET status=? WHERE id=?", (new_status, tx_id))
            conn.commit()

    except Exception as e:
        logger.error(f"❌ خطأ في معالجة زر المعاملة: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ خطأ في المعالجة")
        except:
            pass

# =========================
# نظام الجدولة التلقائية
# =========================

def schedule_daily_report():
    """
    جدولة التقرير اليومي التلقائي
    """
    try:
        report_time = get_setting('daily_report_time') or '23:59'
        if ':' in report_time:
            hour, minute = map(int, report_time.split(':'))
            scheduler.add_job(
                generate_daily_report,
                'cron',
                hour=hour,
                minute=minute,
                id='daily_report',
                name='التقرير اليومي التلقائي'
            )
            logger.info(f"✅ تم جدولة التقرير اليومي للساعة: {report_time}")
    except Exception as e:
        logger.error(f"❌ خطأ في جدولة التقرير اليومي: {e}")

def schedule_auto_backup():
    """
    جدولة النسخ الاحتياطي التلقائي
    """
    try:
        interval = int(get_setting('backup_interval_hours') or 6)
        scheduler.add_job(
            backup_database,
            'interval',
            hours=interval,
            id='auto_backup',
            name='النسخ الاحتياطي التلقائي'
        )
        logger.info(f"✅ تم جدولة النسخ الاحتياطي كل {interval} ساعات")
    except Exception as e:
        logger.error(f"❌ خطأ في جدولة النسخ الاحتياطي: {e}")

def schedule_sessions_cleanup():
    """
    جدولة تنظيف الجلسات القديمة
    """
    try:
        scheduler.add_job(
            cleanup_old_sessions,
            'interval',
            hours=1,
            id='sessions_cleanup',
            name='تنظيف الجلسات القديمة'
        )
        logger.info("✅ تم جدولة تنظيف الجلسات كل ساعة")
    except Exception as e:
        logger.error(f"❌ خطأ في جدولة تنظيف الجلسات: {e}")

@safe_execute
def generate_daily_report(date_str: Optional[str] = None, send_to_channel: bool = True):
    """
    إنشاء التقرير اليومي
    """
    try:
        report = get_daily_report(date_str)
        if not report:
            logger.error("❌ فشل في إنشاء التقرير اليومي")
            return

        message = (
            f"📊 **تقرير يومي - {report['date']}**\n\n"
            f"👥 **المستخدمون:**\n"
            f"• 👤 مستخدمين جدد: {report['new_users']}\n"
            f"• 📊 الإجمالي: {report['total_users']}\n"
            f"• 🎯 النشطين: {report['active_users']}\n\n"
            f"💰 **الأداء المالي:**\n"
            f"• 💳 إجمالي الإيداع: {format_currency(report['total_deposit'])}\n"
            f"• 💸 إجمالي السحب: {format_currency(report['total_withdraw'])}\n"
            f"• 📈 صافي التدفق: {format_currency(report['net_flow'])}\n"
            f"• 📋 المعاملات: {report['total_transactions']}\n"
            f"• ⏳ المعلقة: {report['pending_transactions']}\n\n"
            f"🤝 **الإحالات:**\n"
            f"• 👥 إحالات جديدة: {report['new_referrals']}\n\n"
            f"📱 **أكواد سيرياتيل:**\n"
            f"• 🔢 عدد الأكواد: {report['active_codes']}\n"
            f"• 💰 المستخدم: {format_currency(report['used_capacity'])}\n"
            f"• 📊 السعة: {format_currency(report['total_capacity'])}\n"
            f"• 📈 النسبة: {report['fill_percentage']}%\n\n"
            f"🕒 **التاريخ:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if send_to_channel:
            try:
                bot.send_message(CHANNEL_DAILY_STATS, message, parse_mode="Markdown")
                logger.info("✅ تم إرسال التقرير اليومي للقناة")
            except Exception as e:
                logger.error(f"❌ فشل إرسال التقرير للقناة: {e}")
        
        return message
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء التقرير اليومي: {e}")
        return None

@safe_execute
def backup_database():
    """
    نسخ قاعدة البيانات احتياطياً
    """
    try:
        import os
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = "backups"
        
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        backup_path = os.path.join(backup_dir, f"bot_backup_{timestamp}.sqlite")
        shutil.copy2(DB_PATH, backup_path)
        
        file_size = os.path.getsize(backup_path)
        
        # تسجيل في قاعدة البيانات
        from database import conn
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO backup_logs (backup_type, file_path, file_size, status, created_at)
                VALUES ('auto', ?, ?, 'success', datetime('now'))
            """, (backup_path, file_size))
            conn.commit()
        
        # تنظيف النسخ القديمة
        cleanup_old_backups()
        
        logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_path} ({file_size} بايت)")
        
    except Exception as e:
        logger.error(f"❌ خطأ في النسخ الاحتياطي: {e}")

@safe_execute
def cleanup_old_sessions():
    """
    تنظيف الجلسات القديمة
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
            deleted = c.rowcount
            conn.commit()
            
            if deleted > 0:
                logger.info(f"✅ تم تنظيف {deleted} جلسة منتهية الصلاحية")
                
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف الجلسات: {e}")

def cleanup_old_backups(max_backups: int = 10):
    """
    تنظيف النسخ الاحتياطية القديمة
    """
    try:
        import os
        import glob
        
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            return
        
        backups = glob.glob(os.path.join(backup_dir, "bot_backup_*.sqlite"))
        backups.sort(key=os.path.getmtime, reverse=True)
        
        if len(backups) > max_backups:
            for backup in backups[max_backups:]:
                try:
                    os.remove(backup)
                    logger.info(f"✅ تم حذف نسخة احتياطية قديمة: {backup}")
                except Exception as e:
                    logger.error(f"❌ خطأ في حذف نسخة احتياطية: {e}")
                    
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف النسخ الاحتياطية: {e}")

# =========================
# أوامر إضافية
# =========================

@bot.message_handler(commands=["fixdb"])
@rate_limit()
@safe_execute
def fix_database_cmd(message: Message):
    """
    إصلاح قاعدة البيانات
    """
    if not is_admin(message.from_user.id):
        return

    bot.reply_to(message, "🛠 جاري إصلاح قاعدة البيانات...")
    try:
        init_db()
        bot.reply_to(message, "✅ تم إصلاح قاعدة البيانات بنجاح!")
    except Exception as e:
        bot.reply_to(message, f"❌ فشل إصلاح قاعدة البيانات: {e}")

@bot.message_handler(commands=["debug"])
@rate_limit()
@safe_execute
def debug_cmd(message: Message):
    """
    تصحيح النظام
    """
    if not is_admin(message.from_user.id):
        return

    uid = message.from_user.id
    session = get_session(uid)

    reply = f"""🔧 **تصحيح النظام**

👤 المستخدم: {uid}
👑 أدمن: {'✅' if is_admin(uid) else '❌'}
💾 قاعدة البيانات: {DB_PATH}
📊 الجلسة: {session}
💱 سعر الصرف: {get_exchange_rate()} ليرة للدولار
🕒 الوقت: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.reply_to(message, reply, parse_mode="Markdown")

@bot.message_handler(commands=["stats"])
@rate_limit()
@safe_execute
def stats_cmd(message: Message):
    """
    إحصائيات النظام
    """
    if not is_admin(message.from_user.id):
        return

    try:
        users = get_all_users()
        total_users = len(users)
        banned_users = sum(1 for u in users if u[4])

        admins_list = get_all_admins()
        total_admins = len(admins_list) + 2

        reply = f"""📊 **إحصائيات النظام**

👥 **المستخدمون:**
• الإجمالي: {total_users}
• المحظورين: {banned_users}
• النشطين: {total_users - banned_users}

👑 **الأدمن:**
• الإجمالي: {total_admins}
• الرئيسي: 1
• الثانوي: {total_admins - 1}

⚡ **Ichancy:**
• مفعل: {'✅' if get_setting('ichancy_enabled') == 'true' else '❌'}
• حسابات: {len([u for u in users if get_ichancy_account(u[0])])}

💰 **المالية:**
• إجمالي الرصيد: {format_currency(sum(u[1] for u in users))}
• متوسط الرصيد: {format_currency(sum(u[1] for u in users) // total_users if total_users > 0 else 0)}

🔄 الإصدار: {VERSION}
📅 آخر تحديث: {LAST_UPDATE}
"""
        bot.reply_to(message, reply, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في جلب الإحصائيات: {e}")

# =========================
# النظام الرئيسي
# =========================

def main():
    """
    الدالة الرئيسية لتشغيل البوت
    """
    # تنظيف بيئة العمل
    try:
        if os.path.exists('/home/runner/'):
            import glob
            for pyc in glob.glob("**/*.pyc", recursive=True):
                try:
                    os.remove(pyc)
                except:
                    pass
    except:
        pass

    # تهيئة قاعدة البيانات
    if not init_db():
        print("❌ فشل تهيئة قاعدة البيانات!")
        exit(1)

    # بدء نظام الجدولة
    try:
        scheduler.start()
        schedule_auto_backup()
        schedule_daily_report()
        schedule_sessions_cleanup()
        logger.info("✅ تم بدء نظام الجدولة")
    except Exception as e:
        logger.error(f"❌ خطأ في بدء نظام الجدولة: {e}")

    # عرض معلومات النظام
    print("=" * 70)
    print("🤖 **البوت الاحترافي - الإصدار 6.0.0**")
    print("=" * 70)
    print(f"👑 الإدمن الرئيسي: {ADMIN_ID}")
    print(f"🔄 الإصدار: {VERSION}")
    print(f"📅 آخر تحديث: {LAST_UPDATE}")
    print("=" * 70)
    print("✅ **نظام التشغيل:**")
    
    # التحقق من حالة الأنظمة
    syr_settings = get_payment_settings('syriatel_cash')
    sham_settings = get_payment_settings('sham_cash')
    sham_usd_settings = get_payment_settings('sham_cash_usd')
    
    print(f"   📱 سيرياتيل كاش: {'✅' if syr_settings and syr_settings['is_active'] else '⏸️'}")
    print(f"   💰 شام كاش: {'✅' if sham_settings and sham_settings['is_active'] else '⏸️'}")
    print(f"   💵 شام كاش دولار: {'✅' if sham_usd_settings and sham_usd_settings['is_active'] else '⏸️'}")
    print(f"   ⚡ Ichancy: {'✅' if get_setting('ichancy_enabled') == 'true' else '❌'}")
    print(f"   💸 السحب: {'✅' if get_setting('withdraw_enabled') == 'true' else '❌'}")
    print(f"   🤝 الإحالات: ✅")
    print(f"   🎁 الإهداء: ✅")
    print(f"   👑 الأدمن الثانوي: ✅")
    print(f"   📊 التقارير: ✅")
    
    print("✅ البوت يعمل")
    print("=" * 70)
    print("✅ **الميزات الجديدة:**")
    print("   ⚡ نظام Ichancy الكامل")
    print("   👑 نظام الأدمن المتطور")
    print("   💸 إعدادات السحب المتكاملة")
    print("   🤝 نظام الإحالات الكامل")
    print("   🎁 نظام الإهداء وأكواد الهدايا")
    print("   📊 التقارير المتقدمة")
    print("   👥 إدارة المستخدمين المتكاملة")
    print("=" * 70)
    print("🚀 **البوت جاهز للعمل!**")
    print("=" * 70)
    print("📝 **الأوامر المتاحة:**")
    print("   /start - بدء الاستخدام")
    print("   /fixdb - إصلاح قاعدة البيانات (للإدمن)")
    print("   /debug - تصحيح النظام (للإدمن)")
    print("   /stats - إحصائيات النظام (للإدمن)")
    print("=" * 70)

    # بدء البوت
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
    except Exception as e:
        logger.critical(f"🚨 توقف البوت بشكل غير متوقع: {e}")
        # محاولة إعادة التشغيل إذا لم يكن على Replit
        if not os.path.exists('/home/runner/'):
            logger.info("🔄 إعادة تشغيل البوت بعد 5 ثواني...")
            time.sleep(5)
            os.execv(sys.executable, [sys.executable] + sys.argv)

if __name__ == "__main__":
    main()