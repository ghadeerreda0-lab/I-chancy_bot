"""
كيبوردات الأدمن - سرعة فائقة
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.user_service import UserService
from services.system_service import SystemService

user_service = UserService()
system_service = SystemService()


def get_admin_panel(user_id: int) -> InlineKeyboardMarkup:
    """لوحة تحكم الأدمن"""
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
    if user_service.can_manage_admins(user_id):
        kb.add(InlineKeyboardButton("👑 إدارة الأدمن", callback_data="admin_manage_admins"))
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع للقائمة", callback_data="back"))
    
    return kb


def get_general_settings_keyboard() -> InlineKeyboardMarkup:
    """إعدادات عامة"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    # حالة Ichancy
    ichancy_status = "✅ مفعل" if system_service.get_setting('ichancy_enabled') == 'true' else "❌ معطل"
    ichancy_create_status = "✅ مفعل" if system_service.get_setting('ichancy_create_account_enabled') == 'true' else "❌ معطل"
    ichancy_deposit_status = "✅ مفعل" if system_service.get_setting('ichancy_deposit_enabled') == 'true' else "❌ معطل"
    ichancy_withdraw_status = "✅ مفعل" if system_service.get_setting('ichancy_withdraw_enabled') == 'true' else "❌ معطل"
    
    # حالة الشحن والسحب
    deposit_status = "✅ مفعل" if system_service.is_deposit_enabled() else "❌ معطل"
    withdraw_status = "✅ مفعل" if system_service.is_withdraw_enabled() else "❌ معطل"
    withdraw_btn_status = "👁️ مرئي" if system_service.is_withdraw_button_visible() else "👁️ مخفي"
    maintenance_status = "✅ مفعل" if system_service.is_maintenance_mode() else "❌ معطل"
    
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
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_payment_settings_keyboard() -> InlineKeyboardMarkup:
    """إعدادات الدفع"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    from services.payment_service import PaymentService
    payment_service = PaymentService()
    
    # جلب حالة كل طريقة دفع
    syr_settings = payment_service.get_payment_settings('syriatel_cash')
    sham_settings = payment_service.get_payment_settings('sham_cash')
    sham_usd_settings = payment_service.get_payment_settings('sham_cash_usd')
    
    syr_visible = "👁️" if syr_settings and syr_settings['is_visible'] else "👁️‍🗨️"
    syr_active = "✅" if syr_settings and syr_settings['is_active'] else "⏸️"
    
    sham_visible = "👁️" if sham_settings and sham_settings['is_visible'] else "👁️‍🗨️"
    sham_active = "✅" if sham_settings and sham_settings['is_active'] else "⏸️"
    
    sham_usd_visible = "👁️" if sham_usd_settings and sham_usd_settings['is_visible'] else "👁️‍🗨️"
    sham_usd_active = "✅" if sham_usd_settings and sham_usd_settings['is_active'] else "⏸️"
    
    kb.row(
        InlineKeyboardButton(f"📱 سيرياتيل {syr_visible}{syr_active}", callback_data="admin_syriatel_settings"),
        InlineKeyboardButton(f"💰 شام كاش {sham_visible}{sham_active}", callback_data="admin_sham_settings")
    )
    
    kb.row(
        InlineKeyboardButton(f"💵 شام دولار {sham_usd_visible}{sham_usd_active}", callback_data="admin_sham_usd_settings"),
        InlineKeyboardButton("💰 حدود المبالغ", callback_data="admin_payment_limits")
    )
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_withdraw_settings_keyboard() -> InlineKeyboardMarkup:
    """إعدادات السحب"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    withdraw_enabled = system_service.is_withdraw_enabled()
    withdraw_btn_visible = system_service.is_withdraw_button_visible()
    withdraw_percentage = system_service.get_setting('withdraw_percentage', '0')
    
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
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_users_management_keyboard() -> InlineKeyboardMarkup:
    """إدارة المستخدمين"""
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
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_referral_settings_keyboard() -> InlineKeyboardMarkup:
    """إعدادات الإحالات"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    from services.referral_service import ReferralService
    referral_service = ReferralService()
    
    settings = referral_service.get_settings()
    if settings:
        commission_rate = settings.commission_rate
        bonus_amount = settings.bonus_amount
        min_active = settings.min_active_referrals
        min_charge = settings.min_charge_amount
        next_dist = settings.next_distribution or 'غير محدد'
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
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_ichancy_settings_keyboard() -> InlineKeyboardMarkup:
    """إعدادات Ichancy"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    ichancy_enabled = system_service.is_ichancy_enabled()
    create_enabled = system_service.can_create_ichancy_account()
    deposit_enabled = system_service.get_setting('ichancy_deposit_enabled') == 'true'
    withdraw_enabled = system_service.get_setting('ichancy_withdraw_enabled') == 'true'
    
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
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_reports_keyboard() -> InlineKeyboardMarkup:
    """التقارير والإحصائيات"""
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
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_manage_admins_keyboard() -> InlineKeyboardMarkup:
    """إدارة الأدمن"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("➕ إضافة أدمن", callback_data="admin_add_admin"),
        InlineKeyboardButton("🗑️ حذف أدمن", callback_data="admin_remove_admin")
    )
    
    kb.add(InlineKeyboardButton("📋 عرض جميع الأدمن", callback_data="admin_list_admins"))
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_back_to_panel"))
    
    return kb


def get_transaction_approval_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    """كيبورد الموافقة على المعاملة"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("✅ قبول", callback_data=f"approve_{transaction_id}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject_{transaction_id}")
    )
    
    return kb


def get_confirmation_keyboard(yes_callback: str, no_callback: str, 
                             yes_text: str = "✅ نعم", no_text: str = "❌ لا") -> InlineKeyboardMarkup:
    """كيبورد تأكيد"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton(yes_text, callback_data=yes_callback),
        InlineKeyboardButton(no_text, callback_data=no_callback)
    )
    
    return kb