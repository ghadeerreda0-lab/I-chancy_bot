"""
كيبوردات المستخدمين - سرعة فائقة
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.user_service import UserService
from services.system_service import SystemService

user_service = UserService()
system_service = SystemService()


def get_main_menu(user_id: int) -> InlineKeyboardMarkup:
    """القائمة الرئيسية للمستخدم"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    # زر Ichancy (أول زر)
    if system_service.is_ichancy_enabled():
        from services.ichancy_service import IchancyService
        ichancy_service = IchancyService()
        ichancy_account = ichancy_service.get_account_info(user_id)
        
        if ichancy_account:
            kb.add(InlineKeyboardButton("⚡ Ichancy - معلومات الحساب", callback_data="ichancy_menu"))
        else:
            kb.add(InlineKeyboardButton("⚡ Ichancy - إنشاء حساب", callback_data="ichancy_menu"))
    
    # زر شحن رصيد
    if system_service.is_deposit_enabled():
        kb.add(InlineKeyboardButton("💰 شحن رصيد", callback_data="deposit_menu"))
    
    # زر سحب رصيد
    if system_service.is_withdraw_enabled() and system_service.is_withdraw_button_visible():
        kb.add(InlineKeyboardButton("📤 سحب رصيد", callback_data="withdraw_menu"))
    
    # نظام الاحالات
    kb.row(
        InlineKeyboardButton("🤝 نظام الاحالات", callback_data="referral_menu"),
        InlineKeyboardButton("🎁 اهداء رصيد", callback_data="gift_send")
    )
    
    # خدمات إضافية
    kb.row(
        InlineKeyboardButton("🎁 كود هدية", callback_data="gift_code"),
        InlineKeyboardButton("📜 السجل", callback_data="gift_logs")
    )
    
    # الدعم والمساعدة
    kb.row(
        InlineKeyboardButton("✉️ تواصل مع الدعم", url="https://t.me/username"),
        InlineKeyboardButton("📞 تواصل معنا", callback_data="contact_us")
    )
    
    # الشروط والأحكام
    kb.add(InlineKeyboardButton("📌 الشروط والأحكام", callback_data="terms"))
    
    # زر لوحة التحكم للأدمن
    if user_service.is_admin(user_id):
        kb.add(InlineKeyboardButton("🎛 لوحة التحكم", callback_data="admin_panel"))
    
    return kb


def get_ichancy_menu(has_account: bool = False) -> InlineKeyboardMarkup:
    """قائمة Ichancy"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    if has_account:
        kb.row(
            InlineKeyboardButton("💰 شحن في Ichancy", callback_data="ichancy_deposit"),
            InlineKeyboardButton("💸 سحب من Ichancy", callback_data="ichancy_withdraw")
        )
    else:
        if system_service.can_create_ichancy_account():
            kb.add(InlineKeyboardButton("📝 إنشاء حساب Ichancy", callback_data="ichancy_create"))
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb


def get_deposit_menu() -> InlineKeyboardMarkup:
    """قائمة طرق الشحن"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    from services.payment_service import PaymentService
    payment_service = PaymentService()
    
    # طرق الدفع المفعلة والمرئية
    payment_methods = [
        ('syriatel_cash', '📱 سيرياتيل كاش'),
        ('sham_cash', '💰 شام كاش'),
        ('sham_cash_usd', '💵 شام كاش دولار')
    ]
    
    buttons = []
    for method_id, method_name in payment_methods:
        settings = payment_service.get_payment_settings(method_id)
        if settings and settings['is_visible'] and settings['is_active']:
            buttons.append(InlineKeyboardButton(method_name, callback_data=f"pay_{method_id}"))
    
    # ترتيب الأزرار
    if len(buttons) >= 2:
        kb.row(buttons[0], buttons[1])
        if len(buttons) > 2:
            kb.add(buttons[2])
    elif buttons:
        kb.add(buttons[0])
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb


def get_referral_menu() -> InlineKeyboardMarkup:
    """قائمة الإحالات"""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    return kb


def get_gift_menu() -> InlineKeyboardMarkup:
    """قائمة الهدايا"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("🎁 إهداء رصيد", callback_data="gift_send"),
        InlineKeyboardButton("🎟️ كود هدية", callback_data="gift_code")
    )
    
    kb.add(InlineKeyboardButton("📜 سجل الهدايا", callback_data="gift_logs"))
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb


def get_logs_menu() -> InlineKeyboardMarkup:
    """قائمة السجلات"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("💳 عمليات الشحن", callback_data="user_deposit_logs"),
        InlineKeyboardButton("💸 عمليات السحب", callback_data="user_withdraw_logs")
    )
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb


def get_contact_menu() -> InlineKeyboardMarkup:
    """قائمة التواصل"""
    kb = InlineKeyboardMarkup()
    
    kb.add(InlineKeyboardButton("📞 تواصل عبر تليجرام", url="https://t.me/username"))
    kb.add(InlineKeyboardButton("📧 البريد الإلكتروني", url="mailto:support@example.com"))
    kb.add(InlineKeyboardButton("🌐 الموقع الإلكتروني", url="https://example.com"))
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb


def get_terms_menu() -> InlineKeyboardMarkup:
    """قائمة الشروط"""
    kb = InlineKeyboardMarkup()
    
    kb.add(InlineKeyboardButton("📖 قراءة الشروط", url="https://example.com/terms"))
    kb.add(InlineKeyboardButton("✅ أوافق على الشروط", callback_data="accept_terms"))
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb


def get_yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """كيبورد نعم/لا"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    kb.row(
        InlineKeyboardButton("✅ نعم", callback_data=yes_callback),
        InlineKeyboardButton("❌ لا", callback_data=no_callback)
    )
    
    return kb


def get_numeric_keyboard(prefix: str, rows: int = 3, cols: int = 3) -> InlineKeyboardMarkup:
    """كيبورد رقمي"""
    kb = InlineKeyboardMarkup(row_width=cols)
    
    numbers = []
    for i in range(1, rows * cols + 1):
        numbers.append(InlineKeyboardButton(str(i), callback_data=f"{prefix}_{i}"))
    
    # ترتيب الأرقام في صفوف
    for i in range(0, len(numbers), cols):
        kb.row(*numbers[i:i + cols])
    
    kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="back"))
    
    return kb