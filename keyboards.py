"""
keyboards.py - لوحات المفاتيح والأزرار
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database import (
    get_setting, is_admin, can_manage_admins, get_payment_settings,
    get_referral_settings, get_ichancy_account, get_user
)
from config import ADMIN_ID

# =========================
# لوحات المستخدم الرئيسية
# =========================

def main_menu(user_id: int) -> InlineKeyboardMarkup:
    """
    القائمة الرئيسية للمستخدم
    """
    kb = InlineKeyboardMarkup(row_width=2)

    # زر Ichancy (أول زر)
    ichancy_account = get_ichancy_account(user_id)
    if ichancy_account:
        kb.add(InlineKeyboardButton("⚡ Ichancy - معلومات الحساب", callback_data="ichancy_info"))
    else:
        kb.add(InlineKeyboardButton("⚡ Ichancy - إنشاء حساب", callback_data="ichancy_create"))

    # زر شحن رصيد موحد
    kb.add(InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit_menu"))

    # زر سحب رصيد (إذا كان مفعلاً ومرئياً)
    withdraw_enabled = get_setting('withdraw_enabled') == 'true'
    withdraw_visible = get_setting('withdraw_button_visible') == 'true'

    if withdraw_enabled and withdraw_visible:
        kb.add(InlineKeyboardButton("📤 سحب رصيد", callback_data="withdraw"))

    # باقي الأزرار
    kb.row(
        InlineKeyboardButton("🤝 نظام الاحالات", callback_data="referrals"),
        InlineKeyboardButton("🎁 اهداء رصيد", callback_data="gift_balance")
    )

    kb.row(
        InlineKeyboardButton("🎁 كود هدية", callback_data="gift_code"),
        InlineKeyboardButton("📜 السجل", callback_data="user_logs")
    )

    kb.row(
        InlineKeyboardButton("✉️ تواصل مع الدعم", callback_data="support"),
        InlineKeyboardButton("📞 تواصل معنا", callback_data="contact")
    )

    kb.add(InlineKeyboardButton("📌 الشروط والأحكام", callback_data="rules"))

    # زر لوحة التحكم للأدمن
    if is_admin(user_id):
        kb.add(InlineKeyboardButton("🎛 لوحة التحكم", callback_data="admin_panel"))

    return kb

def deposit_menu_keyboard() -> InlineKeyboardMarkup:
    """
    قائمة طرق الشحن
    """
    kb = InlineKeyboardMarkup(row_width=2)

    # التحقق من كل طريقة دفع إذا كانت مرئية ومفعلة
    payment_methods = [
        ('syriatel_cash', '📱 سيرياتيل كاش'),
        ('sham_cash', '💰 شام كاش'),
        ('sham_cash_usd', '💵 شام كاش دولار')
    ]

    visible_methods = []
    for method_id, method_name in payment_methods:
        settings = get_payment_settings(method_id)
        if settings and settings['is_visible']:
            if settings['is_active']:
                visible_methods.append(InlineKeyboardButton(method_name, callback_data=f"pay_{method_id}"))
            else:
                # يمكن إضافة زر مع رسالة أن الخدمة متوقفة
                pass

    # ترتيب الأزرار
    if len(visible_methods) >= 2:
        kb.row(visible_methods[0], visible_methods[1])
        if len(visible_methods) > 2:
            kb.add(visible_methods[2])
    elif visible_methods:
        kb.add(visible_methods[0])

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="back"))
    return kb

def user_logs_keyboard() -> InlineKeyboardMarkup:
    """
    سجل المستخدم الشخصي
    """
    kb = InlineKeyboardMarkup(row_width=2)

    kb.row(
        InlineKeyboardButton("💳 عمليات الشحن", callback_data="user_deposit_logs"),
        InlineKeyboardButton("💸 عمليات السحب", callback_data="user_withdraw_logs")
    )

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="back"))

    return kb

def ichancy_info_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    لوحة معلومات حساب Ichancy
    """
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("💰 شحن في Ichancy", callback_data="ichancy_deposit"),
        InlineKeyboardButton("💸 سحب من Ichancy", callback_data="ichancy_withdraw")
    )
    
    kb.add(InlineKeyboardButton("🔄 تحديث البيانات", callback_data="ichancy_info"))
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb

# =========================
# لوحات الأدمن
# =========================

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """
    لوحة تحكم الأدمن
    """
    kb = InlineKeyboardMarkup(row_width=2)

    kb.row(
        InlineKeyboardButton("⚙️ الإعدادات العامة", callback_data="admin_general_settings"),
        InlineKeyboardButton("💰 إعدادات الدفع", callback_data="admin_payment_settings")
    )

    kb.row(
        InlineKeyboardButton("💸 إعدادات السحب", callback_data="admin_withdraw_settings"),
        InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users_management")
    )

    kb.row(
        InlineKeyboardButton("📊 التقارير والإحصائيات", callback_data="admin_reports"),
        InlineKeyboardButton("🤝 إعدادات الاحالات", callback_data="admin_referral_settings")
    )

    kb.row(
        InlineKeyboardButton("⚡ نظام Ichancy", callback_data="admin_ichancy_settings"),
        InlineKeyboardButton("📋 المعاملات", callback_data="admin_transactions")
    )

    # زر إدارة الأدمن (للمشرف الرئيسي فقط)
    if can_manage_admins(ADMIN_ID):
        kb.add(InlineKeyboardButton("👑 إدارة الأدمن", callback_data="admin_manage_admins"))

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع للقائمة", callback_data="back"))

    return kb

def general_settings_keyboard() -> InlineKeyboardMarkup:
    """
    إعدادات عامة
    """
    kb = InlineKeyboardMarkup(row_width=2)

    # حالة Ichancy
    ichancy_status = "✅ مفعل" if get_setting('ichancy_enabled') == 'true' else "❌ معطل"
    ichancy_create_status = "✅ مفعل" if get_setting('ichancy_create_account_enabled') == 'true' else "❌ معطل"
    ichancy_deposit_status = "✅ مفعل" if get_setting('ichancy_deposit_enabled') == 'true' else "❌ معطل"
    ichancy_withdraw_status = "✅ مفعل" if get_setting('ichancy_withdraw_enabled') == 'true' else "❌ معطل"

    # حالة الشحن والسحب
    deposit_status = "✅ مفعل" if get_setting('deposit_enabled') == 'true' else "❌ معطل"
    withdraw_status = "✅ مفعل" if get_setting('withdraw_enabled') == 'true' else "❌ معطل"
    withdraw_btn_status = "👁️ مرئي" if get_setting('withdraw_button_visible') == 'true' else "👁️ مخفي"
    maintenance_status = "✅ مفعل" if get_setting('maintenance_mode') == 'true' else "❌ معطل"

    # قسم Ichancy
    kb.add(InlineKeyboardButton(f"⚡ Ichancy: {ichancy_status}", callback_data="admin_toggle_ichancy"))
    kb.row(
        InlineKeyboardButton(f"📝 إنشاء حساب: {ichancy_create_status}", callback_data="admin_toggle_ichancy_create"),
        InlineKeyboardButton(f"💰 الشحن: {ichancy_deposit_status}", callback_data="admin_toggle_ichancy_deposit")
    )
    kb.add(InlineKeyboardButton(f"💸 السحب: {ichancy_withdraw_status}", callback_data="admin_toggle_ichancy_withdraw"))

    # قسم الشحن والسحب
    kb.add(InlineKeyboardButton(f"💰 الشحن العام: {deposit_status}", callback_data="admin_toggle_deposit"))
    kb.row(
        InlineKeyboardButton(f"💸 السحب العام: {withdraw_status}", callback_data="admin_toggle_withdraw"),
        InlineKeyboardButton(f"👁️ زر السحب: {withdraw_btn_status}", callback_data="admin_toggle_withdraw_button")
    )
    kb.add(InlineKeyboardButton(f"🛠️ الصيانة: {maintenance_status}", callback_data="admin_toggle_maintenance"))

    # الرسائل
    kb.row(
        InlineKeyboardButton("✏️ رسالة الترحيب", callback_data="admin_edit_welcome_msg"),
        InlineKeyboardButton("✏️ رسالة الصيانة", callback_data="admin_edit_maintenance_msg")
    )

    kb.row(
        InlineKeyboardButton("📊 التقارير اليومية", callback_data="admin_daily_report"),
        InlineKeyboardButton("📁 نسخ احتياطي", callback_data="admin_backup_now")
    )

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def payment_settings_keyboard() -> InlineKeyboardMarkup:
    """
    إعدادات الدفع
    """
    kb = InlineKeyboardMarkup(row_width=2)

    # جلب حالة كل طريقة دفع
    syr_settings = get_payment_settings('syriatel_cash')
    sham_settings = get_payment_settings('sham_cash')
    sham_usd_settings = get_payment_settings('sham_cash_usd')

    syr_visible = "👁️" if syr_settings and syr_settings['is_visible'] else "👁️‍🗨️"
    syr_active = "✅" if syr_settings and syr_settings['is_active'] else "⏸️"

    sham_visible = "👁️" if sham_settings and sham_settings['is_visible'] else "👁️‍🗨️"
    sham_active = "✅" if sham_settings and sham_settings['is_active'] else "⏸️"

    sham_usd_visible = "👁️" if sham_usd_settings and sham_usd_settings['is_visible'] else "👁️‍🗨️"
    sham_usd_active = "✅" if sham_usd_settings and sham_usd_settings['is_active'] else "⏸️"

    kb.row(
        InlineKeyboardButton(f"📱 سيرياتيل كاش {syr_visible}{syr_active}", callback_data="admin_syriatel_settings"),
        InlineKeyboardButton(f"💰 شام كاش {sham_visible}{sham_active}", callback_data="admin_sham_settings")
    )

    kb.row(
        InlineKeyboardButton(f"💵 شام كاش دولار {sham_usd_visible}{sham_usd_active}", callback_data="admin_sham_usd_settings"),
        InlineKeyboardButton("💰 حدود المبالغ", callback_data="admin_payment_limits")
    )

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def withdraw_settings_keyboard() -> InlineKeyboardMarkup:
    """
    إعدادات السحب
    """
    kb = InlineKeyboardMarkup(row_width=2)

    withdraw_enabled = get_setting('withdraw_enabled') == 'true'
    withdraw_btn_visible = get_setting('withdraw_button_visible') == 'true'
    withdraw_percentage = get_setting('withdraw_percentage', '0')

    kb.row(
        InlineKeyboardButton(f"⚡ تفعيل/إيقاف: {'✅' if withdraw_enabled else '❌'}", 
                           callback_data="admin_toggle_withdraw"),
        InlineKeyboardButton(f"👁️ زر السحب: {'👁️' if withdraw_btn_visible else '👁️‍🗨️'}", 
                           callback_data="admin_toggle_withdraw_button")
    )

    kb.row(
        InlineKeyboardButton(f"📊 نسبة السحب: {withdraw_percentage}%", 
                           callback_data="admin_edit_withdraw_percentage"),
        InlineKeyboardButton("💰 حدود السحب", callback_data="admin_withdraw_limits")
    )

    kb.row(
        InlineKeyboardButton("📝 رسالة التوقف", callback_data="admin_edit_withdraw_msg"),
        InlineKeyboardButton("📊 إحصائيات السحب", callback_data="admin_withdraw_stats")
    )

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def users_management_keyboard() -> InlineKeyboardMarkup:
    """
    إدارة المستخدمين
    """
    kb = InlineKeyboardMarkup(row_width=2)

    kb.row(
        InlineKeyboardButton("👥 عدد المستخدمين", callback_data="admin_users_count"),
        InlineKeyboardButton("💰 إضافة رصيد", callback_data="admin_add_balance")
    )

    kb.row(
        InlineKeyboardButton("💸 سحب رصيد", callback_data="admin_subtract_balance"),
        InlineKeyboardButton("📊 رصيد المستخدمين", callback_data="admin_users_balance")
    )

    kb.row(
        InlineKeyboardButton("📨 رسالة لمستخدم", callback_data="admin_message_user"),
        InlineKeyboardButton("🖼️ صورة لمستخدم", callback_data="admin_photo_user")
    )

    kb.row(
        InlineKeyboardButton("📣 رسالة للجميع", callback_data="admin_broadcast"),
        InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user")
    )

    kb.row(
        InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="admin_unban_user"),
        InlineKeyboardButton("🗑️ حذف حساب", callback_data="admin_delete_user")
    )

    kb.row(
        InlineKeyboardButton("🏆 أعلى رصيد", callback_data="admin_top_balance"),
        InlineKeyboardButton("⭐ اللاعبين المميزين", callback_data="admin_top_deposit")
    )

    kb.row(
        InlineKeyboardButton("💸 سحب جميع الأرصدة", callback_data="admin_reset_all_balances"),
        InlineKeyboardButton("📜 جلب سجل لاعب", callback_data="admin_user_logs")
    )

    kb.add(InlineKeyboardButton("🎁 تعديل نسبة الإهداء", callback_data="admin_edit_gift_percentage"))

    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def referral_settings_keyboard() -> InlineKeyboardMarkup:
    """
    إعدادات الإحالات
    """
    kb = InlineKeyboardMarkup(row_width=2)

    settings = get_referral_settings()
    if settings:
        commission_rate = settings.get('commission_rate', 10)
        bonus_amount = settings.get('bonus_amount', 2000)
        min_active = settings.get('min_active_referrals', 5)
        min_charge = settings.get('min_charge_amount', 100000)
        next_dist = settings.get('next_distribution', 'غير محدد')
    else:
        commission_rate = 10
        bonus_amount = 2000
        min_active = 5
        min_charge = 100000
        next_dist = 'غير محدد'

    kb.row(
        InlineKeyboardButton(f"📊 النسبة: {commission_rate}%", 
                           callback_data="admin_edit_referral_rate"),
        InlineKeyboardButton(f"💰 المكافأة: {bonus_amount:,}", 
                           callback_data="admin_edit_referral_bonus")
    )

    kb.row(
        InlineKeyboardButton(f"👥 الحد الأدنى: {min_active}", 
                           callback_data="admin_edit_min_referrals"),
        InlineKeyboardButton(f"💸 حد الشحن: {min_charge:,}", 
                           callback_data="admin_edit_min_charge")
    )

    kb.row(
        InlineKeyboardButton(f"⏰ موعد التوزيع: {next_dist}", 
                           callback_data="admin_edit_distribution_time"),
        InlineKeyboardButton("📈 أعلى الاحالات", 
                           callback_data="admin_top_referrals")
    )

    kb.add(InlineKeyboardButton("💸 توزيع النسب", callback_data="admin_distribute_referrals"))
    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def ichancy_settings_keyboard() -> InlineKeyboardMarkup:
    """
    إعدادات Ichancy
    """
    kb = InlineKeyboardMarkup(row_width=2)

    ichancy_enabled = get_setting('ichancy_enabled') == 'true'
    create_enabled = get_setting('ichancy_create_account_enabled') == 'true'
    deposit_enabled = get_setting('ichancy_deposit_enabled') == 'true'
    withdraw_enabled = get_setting('ichancy_withdraw_enabled') == 'true'

    kb.row(
        InlineKeyboardButton(f"⚡ Ichancy: {'✅' if ichancy_enabled else '❌'}", 
                           callback_data="admin_toggle_ichancy"),
        InlineKeyboardButton(f"📝 إنشاء حساب: {'✅' if create_enabled else '❌'}", 
                           callback_data="admin_toggle_ichancy_create")
    )

    kb.row(
        InlineKeyboardButton(f"💰 الشحن: {'✅' if deposit_enabled else '❌'}", 
                           callback_data="admin_toggle_ichancy_deposit"),
        InlineKeyboardButton(f"💸 السحب: {'✅' if withdraw_enabled else '❌'}", 
                           callback_data="admin_toggle_ichancy_withdraw")
    )

    kb.add(InlineKeyboardButton("✏️ رسالة Ichancy", callback_data="admin_edit_ichancy_msg"))
    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def reports_keyboard() -> InlineKeyboardMarkup:
    """
    التقارير والإحصائيات
    """
    kb = InlineKeyboardMarkup(row_width=2)

    kb.row(
        InlineKeyboardButton("📅 تقرير اليوم", callback_data="report_today"),
        InlineKeyboardButton("📆 تقرير الأمس", callback_data="report_yesterday")
    )

    kb.row(
        InlineKeyboardButton("💰 تقرير الشحن", callback_data="report_deposit"),
        InlineKeyboardButton("💸 تقرير السحب", callback_data="report_withdraw")
    )

    kb.row(
        InlineKeyboardButton("📊 إحصائيات المستخدمين", callback_data="report_users"),
        InlineKeyboardButton("📈 أداء النظام", callback_data="report_system")
    )

    kb.row(
        InlineKeyboardButton("📱 إحصائيات الأكواد", callback_data="report_codes"),
        InlineKeyboardButton("🔄 تحديث البيانات", callback_data="report_refresh")
    )

    kb.add(InlineKeyboardButton("📥 تصدير البيانات", callback_data="report_export"))
    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def manage_admins_keyboard() -> InlineKeyboardMarkup:
    """
    إدارة الأدمن
    """
    kb = InlineKeyboardMarkup(row_width=2)

    kb.row(
        InlineKeyboardButton("➕ إضافة أدمن", callback_data="admin_add_admin"),
        InlineKeyboardButton("🗑️ حذف أدمن", callback_data="admin_remove_admin")
    )

    kb.add(InlineKeyboardButton("📋 عرض جميع الأدمن", callback_data="admin_list_admins"))
    kb.add(InlineKeyboardButton("⬅️ ↩️ رجوع", callback_data="admin_back_to_panel"))

    return kb

def deposit_report_keyboard() -> InlineKeyboardMarkup:
    """
    تقرير عمليات الشحن
    """
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("📱 سيرياتيل كاش", callback_data="report_deposit_syriatel"),
        InlineKeyboardButton("💰 شام كاش", callback_data="report_deposit_sham")
    )
    
    kb.row(
        InlineKeyboardButton("💵 شام كاش دولار", callback_data="report_deposit_sham_usd"),
        InlineKeyboardButton("📊 جميع الطرق", callback_data="report_deposit_all")
    )
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_reports"))
    
    return kb

# =========================
# أزرار الموافقة/الرفض
# =========================

def transaction_approval_buttons(transaction_id: int) -> InlineKeyboardMarkup:
    """
    أزرار الموافقة على المعاملة
    """
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ قبول", callback_data=f"approve_{transaction_id}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject_{transaction_id}")
    )
    return kb

# =========================
# أزرار تأكيد
# =========================

def confirmation_keyboard(confirm_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
    """
    لوحة تأكيد العملية
    """
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton("✅ نعم، تأكيد", callback_data=confirm_callback),
        InlineKeyboardButton("❌ إلغاء", callback_data=cancel_callback)
    )
    return kb