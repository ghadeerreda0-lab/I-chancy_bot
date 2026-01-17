"""
معالجات الرسائل النصية - سرعة فائقة
"""

import time
from datetime import datetime
from telebot import TeleBot
from telebot.types import Message

from core.config import TOKEN
from core.cache import cache
from core.security import rate_limiter, input_validator
from core.logger import get_logger, performance_logger
from services.user_service import UserService
from services.system_service import SystemService
from services.payment_service import PaymentService
from services.ichancy_service import IchancyService
from services.referral_service import ReferralService
from services.gift_service import GiftService
from services.admin_service import AdminService
from keyboards.user_keyboards import get_main_menu
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


@bot.message_handler(func=lambda message: True)
@performance_logger
def handle_all_messages(message: Message):
    """معالجة جميع الرسائل النصية"""
    try:
        user_id = message.from_user.id
        
        # التحقق من الصيانة
        if system_service.is_maintenance_mode() and not user_service.is_admin(user_id):
            maintenance_msg = system_service.get_maintenance_message()
            bot.reply_to(message, maintenance_msg)
            return
        
        # Rate limiting
        allowed, remaining = rate_limiter.is_allowed(user_id)
        if not allowed:
            bot.reply_to(message, f"⏳ كثير طلبات! حاول بعد {remaining} ثانية")
            return
        
        # التحقق من الحظر
        user = user_service.get_or_create_user(user_id)
        if user and user.is_banned:
            bot.reply_to(message, "🚫 حسابك محظور ولا يمكنك استخدام البوت.")
            return
        
        # جلب الجلسة الحالية
        session = get_session(user_id)
        if not session:
            # لا توجد جلسة، عرض القائمة الرئيسية
            welcome_msg = system_service.get_welcome_message(user.balance if user else 0)
            bot.send_message(
                message.chat.id,
                welcome_msg,
                reply_markup=get_main_menu(user_id),
                parse_mode="Markdown"
            )
            return
        
        step = session.get("step")
        temp_data = session.get("temp_data", {})
        
        # توجيه الرسالة حسب الخطوة
        if step.startswith("awaiting_"):
            handle_awaiting_steps(message, step, temp_data, user_id)
        elif step.startswith("admin_"):
            handle_admin_steps(message, step, temp_data, user_id)
        else:
            # خطوة غير معروفة، عرض القائمة الرئيسية
            clear_session(user_id)
            welcome_msg = system_service.get_welcome_message(user.balance if user else 0)
            bot.send_message(
                message.chat.id,
                welcome_msg,
                reply_markup=get_main_menu(user_id),
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"خطأ في handle_all_messages: {e}")
        try:
            bot.reply_to(message, "❌ حدث خطأ، حاول مرة أخرى")
        except:
            pass


def handle_awaiting_steps(message: Message, step: str, temp_data: dict, user_id: int):
    """معالجة خطوات انتظار الإدخال"""
    try:
        text = message.text.strip()
        
        # ===== إدخال مبلغ الإهداء =====
        if step == "awaiting_gift_amount":
            amount = input_validator.validate_amount(text, min_val=1)
            if not amount:
                bot.reply_to(message, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
                return
            
            user_balance = user_service.get_user_balance(user_id)
            if amount > user_balance:
                bot.reply_to(message, f"❌ رصيدك غير كافي. رصيدك الحالي: {user_balance:,} ليرة")
                clear_session(user_id)
                return
            
            # حفظ المبلغ والانتقال للخطوة التالية
            set_session(user_id, "awaiting_gift_receiver", {
                **temp_data,
                "amount": amount
            })
            
            bot.reply_to(message, f"🎁 **إهداء رصيد**\n\n💰 المبلغ: {amount:,} ليرة\n\nأدخل ID المستخدم المراد إهداؤه:")
        
        # ===== إدخال مستلم الإهداء =====
        elif step == "awaiting_gift_receiver":
            receiver_id = input_validator.validate_user_id(text)
            if not receiver_id:
                bot.reply_to(message, "❌ ID غير صحيح، أدخل رقم صحيح فقط")
                return
            
            amount = temp_data.get("amount", 0)
            
            if receiver_id == user_id:
                bot.reply_to(message, "❌ لا يمكن إهداء نفسك")
                clear_session(user_id)
                return
            
            # إرسال الهدية
            result = gift_service.send_gift(user_id, receiver_id, amount)
            
            bot.reply_to(message, result['message'])
            clear_session(user_id)
        
        # ===== إدخال كود الهدية =====
        elif step == "awaiting_gift_code":
            code = text.upper().strip()
            
            result = gift_service.use_gift_code(code, user_id)
            
            bot.reply_to(message, result['message'])
            clear_session(user_id)
        
        # ===== إدخال مبلغ الشحن =====
        elif step.startswith("awaiting_") and step.endswith("_amount"):
            # استخراج طريقة الدفع من اسم الخطوة
            payment_method = step.replace("awaiting_", "").replace("_amount", "")
            
            # التحقق من صحة المبلغ
            if payment_method == 'sham_cash_usd':
                # للدولار، يمكن قبول أرقام عشرية
                try:
                    amount = float(text)
                    if amount <= 0:
                        raise ValueError
                except:
                    bot.reply_to(message, "❌ المبلغ غير صحيح، أدخل رقم صحيح أو عشري")
                    return
            else:
                amount = input_validator.validate_amount(text, min_val=1)
                if not amount:
                    bot.reply_to(message, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
                    return
            
            # التحقق من حدود الدفع
            validation = payment_service.validate_payment_amount(payment_method, int(amount))
            if not validation['valid']:
                bot.reply_to(message, validation['message'])
                return
            
            # حفظ المبلغ والانتقال للخطوة التالية
            set_session(user_id, f"awaiting_{payment_method}_txid", {
                **temp_data,
                "amount": amount,
                "payment_method": payment_method
            })
            
            # رسالة التأكيد
            msg = f"💰 **تفاصيل التحويل**\n\n"
            
            if payment_method == 'sham_cash_usd':
                exchange_rate = system_service.get_exchange_rate()
                final_amount = int(amount * exchange_rate)
                msg += f"💵 المبلغ: {amount:,} دولار\n"
                msg += f"💱 سعر الصرف: 1$ = {exchange_rate:,} ليرة\n"
                msg += f"📊 القيمة: {final_amount:,} ليرة سورية\n\n"
            else:
                msg += f"💰 المبلغ: {amount:,} ليرة سورية\n\n"
            
            msg += f"🔑 الآن أدخل رقم العملية (Transaction ID) لإكمال الطلب:"
            
            bot.reply_to(message, msg, parse_mode="Markdown")
        
        # ===== إدخال رقم العملية للشحن =====
        elif step.startswith("awaiting_") and step.endswith("_txid"):
            payment_method = step.replace("awaiting_", "").replace("_txid", "")
            transaction_id = text.strip()
            amount = temp_data.get("amount", 0)
            
            if not transaction_id:
                bot.reply_to(message, "❌ رقم العملية فارغ")
                return
            
            # إنشاء طلب الشحن
            result = payment_service.create_deposit_request(
                user_id, 
                int(amount), 
                payment_method, 
                transaction_id
            )
            
            bot.reply_to(message, result['message'])
            clear_session(user_id)
        
        # ===== إدخال مبلغ السحب =====
        elif step == "awaiting_withdraw_amount":
            amount = input_validator.validate_amount(text, min_val=1)
            if not amount:
                bot.reply_to(message, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
                return
            
            user_balance = user_service.get_user_balance(user_id)
            if amount > user_balance:
                bot.reply_to(message, f"❌ رصيدك غير كافي. رصيدك الحالي: {user_balance:,} ليرة")
                clear_session(user_id)
                return
            
            # تطبيق نسبة السحب
            withdraw_percentage = system_service.get_setting('withdraw_percentage', '0')
            net_amount = amount
            deduction = 0
            
            if withdraw_percentage != '0':
                percentage = int(withdraw_percentage)
                deduction = int(amount * percentage / 100)
                net_amount = amount - deduction
            
            # حفظ البيانات
            set_session(user_id, "awaiting_withdraw_details", {
                "amount": amount,
                "net_amount": net_amount,
                "deduction": deduction
            })
            
            msg = f"💸 **تفاصيل السحب**\n\n"
            msg += f"💰 المبلغ المطلوب: {amount:,} ليرة\n"
            
            if deduction > 0:
                msg += f"📊 نسبة السحب: {withdraw_percentage}%\n"
                msg += f"💸 المبلغ المخصوم: {deduction:,} ليرة\n"
                msg += f"🎯 المبلغ الذي ستستلمه: {net_amount:,} ليرة\n\n"
            
            msg += f"💳 رصيدك الحالي: {user_balance:,} ليرة\n\n"
            msg += "📝 أدخل رقم الحساب أو التفاصيل المطلوبة:"
            
            bot.reply_to(message, msg, parse_mode="Markdown")
        
        # ===== إدخال تفاصيل السحب =====
        elif step == "awaiting_withdraw_details":
            account_details = text.strip()
            if not account_details:
                bot.reply_to(message, "❌ التفاصيل فارغة")
                return
            
            amount = temp_data.get("amount", 0)
            
            # إنشاء طلب السحب
            result = payment_service.create_withdraw_request(
                user_id, 
                amount, 
                account_details
            )
            
            bot.reply_to(message, result['message'])
            clear_session(user_id)
        
        # ===== إدخال مبلغ شحن Ichancy =====
        elif step == "awaiting_ichancy_deposit_amount":
            amount = input_validator.validate_amount(text, min_val=1)
            if not amount:
                bot.reply_to(message, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
                return
            
            # شحن في Ichancy
            result = ichancy_service.deposit_to_ichancy(user_id, amount)
            
            bot.reply_to(message, result['message'])
            clear_session(user_id)
        
        # ===== إدخال مبلغ سحب Ichancy =====
        elif step == "awaiting_ichancy_withdraw_amount":
            amount = input_validator.validate_amount(text, min_val=1)
            if not amount:
                bot.reply_to(message, "❌ المبلغ غير صحيح، أدخل رقم صحيح فقط")
                return
            
            # سحب من Ichancy
            result = ichancy_service.withdraw_from_ichancy(user_id, amount)
            
            bot.reply_to(message, result['message'])
            clear_session(user_id)
        
        else:
            # خطوة غير معروفة
            clear_session(user_id)
            bot.reply_to(message, "❌ جلسة منتهية، ابدأ من جديد")
    
    except Exception as e:
        logger.error(f"خطأ في handle_awaiting_steps: {e}")
        bot.reply_to(message, "❌ حدث خطأ، حاول مرة أخرى")
        clear_session(user_id)


def handle_admin_steps(message: Message, step: str, temp_data: dict, user_id: int):
    """معالجة خطوات الأدمن"""
    try:
        if not user_service.is_admin(user_id):
            clear_session(user_id)
            return
        
        text = message.text.strip()
        
        # ===== إضافة رصيد لمستخدم =====
        if step == "admin_add_balance_user":
            target_id = input_validator.validate_user_id(text)
            if not target_id:
                bot.reply_to(message, "❌ ID غير صحيح")
                return
            
            target_user = user_service.get_or_create_user(target_id)
            if not target_user:
                bot.reply_to(message, "❌ المستخدم غير موجود")
                clear_session(user_id)
                return
            
            set_session(user_id, "admin_add_balance_amount", {
                "target_id": target_id
            })
            
            msg = f"👤 **المستخدم:** `{target_id}`\n"
            msg += f"💳 **الرصيد الحالي:** {target_user.balance:,} ليرة\n\n"
            msg += f"💰 أدخل المبلغ المراد إضافته:"
            
            bot.reply_to(message, msg, parse_mode="Markdown")
        
        elif step == "admin_add_balance_amount":
            amount = input_validator.validate_amount(text, min_val=1)
            if not amount:
                bot.reply_to(message, "❌ المبلغ غير صحيح")
                return
            
            target_id = temp_data.get("target_id")
            
            result = user_service.update_balance(target_id, amount, 'add')
            
            if result['success']:
                msg = f"✅ **تم إضافة الرصيد بنجاح**\n\n"
                msg += f"👤 المستخدم: `{target_id}`\n"
                msg += f"💰 المبلغ: {amount:,} ليرة\n"
                msg += f"💳 الرصيد السابق: {result['old_balance']:,} ليرة\n"
                msg += f"💳 الرصيد الجديد: {result['new_balance']:,} ليرة"
            else:
                msg = result['message']
            
            bot.reply_to(message, msg, parse_mode="Markdown")
            clear_session(user_id)
        
        # ===== سحب رصيد من مستخدم =====
        elif step == "admin_subtract_balance_user":
            target_id = input_validator.validate_user_id(text)
            if not target_id:
                bot.reply_to(message, "❌ ID غير صحيح")
                return
            
            target_user = user_service.get_or_create_user(target_id)
            if not target_user:
                bot.reply_to(message, "❌ المستخدم غير موجود")
                clear_session(user_id)
                return
            
            set_session(user_id, "admin_subtract_balance_amount", {
                "target_id": target_id
            })
            
            msg = f"👤 **المستخدم:** `{target_id}`\n"
            msg += f"💳 **الرصيد الحالي:** {target_user.balance:,} ليرة\n\n"
            msg += f"💰 أدخل المبلغ المراد سحبه:"
            
            bot.reply_to(message, msg, parse_mode="Markdown")
        
        elif step == "admin_subtract_balance_amount":
            amount = input_validator.validate_amount(text, min_val=1)
            if not amount:
                bot.reply_to(message, "❌ المبلغ غير صحيح")
                return
            
            target_id = temp_data.get("target_id")
            
            result = user_service.update_balance(target_id, amount, 'subtract')
            
            if result['success']:
                msg = f"✅ **تم سحب الرصيد بنجاح**\n\n"
                msg += f"👤 المستخدم: `{target_id}`\n"
                msg += f"💰 المبلغ: {amount:,} ليرة\n"
                msg += f"💳 الرصيد السابق: {result['old_balance']:,} ليرة\n"
                msg += f"💳 الرصيد الجديد: {result['new_balance']:,} ليرة"
            else:
                msg = result['message']
            
            bot.reply_to(message, msg, parse_mode="Markdown")
            clear_session(user_id)
        
        # ===== تعديل نسبة الإهداء =====
        elif step == "admin_edit_gift_percentage":
            percentage = input_validator.validate_amount(text, min_val=0, max_val=100)
            if percentage is None:
                bot.reply_to(message, "❌ النسبة غير صحيحة (0-100)")
                return
            
            system_service.set_setting('gift_percentage', str(percentage), user_id, "تعديل نسبة الإهداء")
            
            msg = f"✅ **تم تعديل نسبة الإهداء**\n\n"
            msg += f"📊 النسبة الجديدة: {percentage}%\n\n"
            
            if percentage == 0:
                msg += f"*بدون خصم*"
            else:
                msg += f"*سيتم خصم {percentage}% من المبلغ المُهدى*"
            
            bot.reply_to(message, msg, parse_mode="Markdown")
            clear_session(user_id)
        
        # ===== تعديل نسبة السحب =====
        elif step == "admin_edit_withdraw_percentage":
            percentage = input_validator.validate_amount(text, min_val=0, max_val=100)
            if percentage is None:
                bot.reply_to(message, "❌ النسبة غير صحيحة (0-100)")
                return
            
            system_service.set_setting('withdraw_percentage', str(percentage), user_id, "تعديل نسبة السحب")
            
            msg = f"✅ **تم تعديل نسبة السحب**\n\n"
            msg += f"📊 النسبة الجديدة: {percentage}%\n\n"
            
            if percentage == 0:
                msg += f"*بدون خصم*"
            else:
                msg += f"*سيتم خصم {percentage}% من المبلغ المسحوب*"
            
            bot.reply_to(message, msg, parse_mode="Markdown")
            clear_session(user_id)
        
        # ===== بث رسالة للجميع =====
        elif step == "awaiting_broadcast_message":
            message_text = text
            
            # تأكيد البث
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("✅ نعم، أرسل للجميع", callback_data=f"confirm_broadcast:{message_text[:50]}"),
                InlineKeyboardButton("❌ إلغاء", callback_data="admin_back_to_panel")
            )
            
            msg = f"📣 **تأكيد البث**\n\n"
            msg += f"📝 الرسالة:\n{message_text[:500]}\n\n"
            msg += f"⚠️ سيتم إرسال هذه الرسالة لجميع المستخدمين. هل أنت متأكد؟"
            
            bot.reply_to(message, msg, reply_markup=kb, parse_mode="Markdown")
            clear_session(user_id)
        
        else:
            # توجيه إلى service الأدمن
            admin_service.handle_admin_message(message, step, temp_data)
    
    except Exception as e:
        logger.error(f"خطأ في handle_admin_steps: {e}")
        bot.reply_to(message, "❌ حدث خطأ")
        clear_session(user_id)


# إعداد معالجات الرسائل
def setup_messages():
    """إعداد معالجات الرسائل"""
    logger.info("✅ تم تحميل معالجات الرسائل")