"""
خدمات الأدمن المتقدمة - سرعة فائقة
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import time

from telebot.types import Message, CallbackQuery
from core.database import db
from core.cache import cache
from core.security import input_validator
from core.logger import get_logger, performance_logger
from services.user_service import UserService
from services.system_service import SystemService
from services.payment_service import PaymentService
from services.ichancy_service import IchancyService
from services.referral_service import ReferralService
from services.gift_service import GiftService
from models.admin import AdminModel
from keyboards.admin_keyboards import *

logger = get_logger(__name__)


class AdminService:
    """خدمات الأدمن المتقدمة"""
    
    def __init__(self):
        self.user_service = UserService()
        self.system_service = SystemService()
        self.payment_service = PaymentService()
        self.ichancy_service = IchancyService()
        self.referral_service = ReferralService()
        self.gift_service = GiftService()
    
    @performance_logger
    def handle_admin_callback(self, call: CallbackQuery):
        """معالجة كال باكات الأدمن"""
        try:
            user_id = call.from_user.id
            data = call.data
            
            if data == "admin_general_settings":
                self._show_general_settings(call)
            elif data == "admin_payment_settings":
                self._show_payment_settings(call)
            elif data == "admin_withdraw_settings":
                self._show_withdraw_settings(call)
            elif data == "admin_users_management":
                self._show_users_management(call)
            elif data == "admin_reports":
                self._show_reports(call)
            elif data == "admin_referral_settings":
                self._show_referral_settings(call)
            elif data == "admin_ichancy_settings":
                self._show_ichancy_settings(call)
            elif data == "admin_transactions":
                self._show_transactions(call)
            elif data == "admin_manage_admins":
                self._show_manage_admins(call)
            elif data.startswith("admin_toggle_"):
                self._toggle_setting(call)
            elif data.startswith("admin_edit_"):
                self._edit_setting(call)
            elif data.startswith("admin_"):
                self._handle_admin_action(call)
            
        except Exception as e:
            logger.error(f"خطأ في handle_admin_callback: {e}")
    
    @performance_logger
    def handle_admin_message(self, message: Message, step: str, temp_data: dict):
        """معالجة رسائل الأدمن"""
        try:
            user_id = message.from_user.id
            text = message.text.strip()
            
            from handlers.sessions import set_session, clear_session
            
            if step == "admin_add_admin":
                self._add_admin(message, text)
            elif step == "admin_remove_admin":
                self._remove_admin(message, text)
            elif step == "admin_edit_referral_rate":
                self._edit_referral_rate(message, text)
            elif step == "admin_top_referrals_count":
                self._show_top_referrals(message, text)
            elif step == "admin_top_balance_count":
                self._show_top_balance(message, text)
            elif step.startswith("admin_"):
                self._handle_admin_message_action(message, step, text, temp_data)
            
        except Exception as e:
            logger.error(f"خطأ في handle_admin_message: {e}")
    
    # ===== دوال العرض =====
    
    def _show_general_settings(self, call: CallbackQuery):
        """عرض الإعدادات العامة"""
        kb = get_general_settings_keyboard()
        
        msg = "⚙️ **الإعدادات العامة**\n\nإدارة جميع إعدادات النظام:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_payment_settings(self, call: CallbackQuery):
        """عرض إعدادات الدفع"""
        kb = get_payment_settings_keyboard()
        
        msg = "💰 **إعدادات الدفع**\n\nإدارة جميع طرق الدفع:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_withdraw_settings(self, call: CallbackQuery):
        """عرض إعدادات السحب"""
        kb = get_withdraw_settings_keyboard()
        
        msg = "💸 **إعدادات السحب**\n\nإدارة جميع إعدادات نظام السحب:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_users_management(self, call: CallbackQuery):
        """عرض إدارة المستخدمين"""
        kb = get_users_management_keyboard()
        
        msg = "👥 **إدارة المستخدمين**\n\nاختر الإجراء المطلوب:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_reports(self, call: CallbackQuery):
        """عرض التقارير"""
        kb = get_reports_keyboard()
        
        msg = "📊 **التقارير والإحصائيات**\n\nاختر نوع التقرير:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_referral_settings(self, call: CallbackQuery):
        """عرض إعدادات الإحالات"""
        kb = get_referral_settings_keyboard()
        
        msg = "🤝 **إعدادات الإحالات**\n\nإدارة نظام الإحالات والمكافآت:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_ichancy_settings(self, call: CallbackQuery):
        """عرض إعدادات Ichancy"""
        kb = get_ichancy_settings_keyboard()
        
        msg = "⚡ **إعدادات نظام Ichancy**\n\nإدارة نظام Ichancy بالكامل:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_transactions(self, call: CallbackQuery):
        """عرض المعاملات"""
        from keyboards.user_keyboards import get_main_menu
        
        msg = "📋 **المعاملات المعلقة**\n\n"
        
        pending = self.payment_service.get_pending_transactions()
        if not pending:
            msg += "✅ لا توجد معاملات معلقة"
        else:
            msg += f"⏳ **هناك {len(pending)} معاملة معلقة:**\n\n"
            
            for tx in pending[:5]:  # عرض أول 5 فقط
                msg += f"🆔 #{tx.id}\n"
                msg += f"👤 المستخدم: `{tx.user_id}`\n"
                msg += f"💰 المبلغ: {tx.amount:,} ليرة\n"
                msg += f"📝 النوع: {tx.type}\n"
                msg += f"📅 التاريخ: {tx.created_at[:16]}\n"
                msg += "─" * 20 + "\n"
        
        kb = get_main_menu(call.from_user.id)
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_manage_admins(self, call: CallbackQuery):
        """عرض إدارة الأدمن"""
        user_id = call.from_user.id
        
        if not self.user_service.can_manage_admins(user_id):
            call.bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
            return
        
        kb = get_manage_admins_keyboard()
        
        msg = "👑 **إدارة الأدمن**\n\nإضافة وحذف الأدمن الثانويين:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="Markdown"
        )
        call.bot.answer_callback_query(call.id)
    
    # ===== دوال التبديل =====
    
    def _toggle_setting(self, call: CallbackQuery):
        """تبديل إعداد"""
        user_id = call.from_user.id
        data = call.data
        
        setting_map = {
            "admin_toggle_ichancy": "ichancy_enabled",
            "admin_toggle_ichancy_create": "ichancy_create_account_enabled",
            "admin_toggle_ichancy_deposit": "ichancy_deposit_enabled",
            "admin_toggle_ichancy_withdraw": "ichancy_withdraw_enabled",
            "admin_toggle_deposit": "deposit_enabled",
            "admin_toggle_withdraw": "withdraw_enabled",
            "admin_toggle_withdraw_button": "withdraw_button_visible",
            "admin_toggle_maintenance": "maintenance_mode"
        }
        
        if data in setting_map:
            result = self.system_service.toggle_setting(setting_map[data], user_id)
            call.bot.answer_callback_query(call.id, result['message'])
            
            # تحديث الواجهة
            try:
                if "ichancy" in data:
                    kb = get_ichancy_settings_keyboard()
                    call.bot.edit_message_reply_markup(
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=kb
                    )
                elif "withdraw" in data:
                    kb = get_withdraw_settings_keyboard()
                    call.bot.edit_message_reply_markup(
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=kb
                    )
                else:
                    kb = get_general_settings_keyboard()
                    call.bot.edit_message_reply_markup(
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=kb
                    )
            except:
                pass
    
    # ===== دوال التعديل =====
    
    def _edit_setting(self, call: CallbackQuery):
        """تعديل إعداد"""
        user_id = call.from_user.id
        data = call.data
        
        from handlers.sessions import set_session
        
        if data == "admin_edit_withdraw_percentage":
            set_session(user_id, "admin_edit_withdraw_percentage")
            
            msg = "📊 **تعديل نسبة السحب**\n\n"
            msg += "أدخل نسبة السحب (0-100):\n"
            msg += "0 يعني بدون نسبة خصم\n"
            msg += "مثال: 10 ← نسبة 10%"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_edit_gift_percentage":
            set_session(user_id, "admin_edit_gift_percentage")
            
            msg = "🎁 **تعديل نسبة الإهداء**\n\n"
            msg += "أدخل نسبة الإهداء (0-100):\n"
            msg += "0 يعني بدون نسبة خصم\n"
            msg += "مثال: 5 ← نسبة 5% على المبلغ المُهدى"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_edit_referral_rate":
            set_session(user_id, "admin_edit_referral_rate")
            
            msg = "📊 **تعديل نسبة الإحالات**\n\n"
            msg += "أدخل نسبة العمولة (0-100):\n"
            msg += "0 يعني بدون عمولة\n"
            msg += "مثال: 10 ← نسبة 10% من الشحن"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_top_referrals":
            set_session(user_id, "admin_top_referrals_count")
            
            msg = "📈 **أعلى الإحالات**\n\n"
            msg += "أدخل عدد الإحالات المطلوب عرضهم (مثال: 15):"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_top_balance":
            set_session(user_id, "admin_top_balance_count")
            
            msg = "🏆 **أعلى رصيد مستخدمين**\n\n"
            msg += "أدخل عدد المستخدمين المطلوب عرضهم (مثال: 20):"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_add_balance":
            set_session(user_id, "admin_add_balance_user")
            
            msg = "💰 **إضافة رصيد لمستخدم**\n\n"
            msg += "أدخل ID المستخدم:"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_subtract_balance":
            set_session(user_id, "admin_subtract_balance_user")
            
            msg = "💸 **سحب رصيد من مستخدم**\n\n"
            msg += "أدخل ID المستخدم:"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_add_admin":
            if not self.user_service.can_manage_admins(user_id):
                call.bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return
            
            set_session(user_id, "admin_add_admin")
            
            msg = "➕ **إضافة أدمن جديد**\n\n"
            msg += "أدخل ID المستخدم المراد ترقيته لأدمن:"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
            
        elif data == "admin_remove_admin":
            if not self.user_service.can_manage_admins(user_id):
                call.bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول")
                return
            
            set_session(user_id, "admin_remove_admin")
            
            msg = "🗑️ **حذف أدمن**\n\n"
            msg += "أدخل ID الأدمن المراد حذفه:"
            
            call.bot.send_message(user_id, msg, parse_mode="Markdown")
            call.bot.answer_callback_query(call.id)
    
    # ===== دوال الإجراءات =====
    
    def _add_admin(self, message: Message, text: str):
        """إضافة أدمن"""
        user_id = message.from_user.id
        
        if not self.user_service.can_manage_admins(user_id):
            message.bot.reply_to(message, "❌ ليس لديك صلاحية إضافة أدمن")
            return
        
        target_id = input_validator.validate_user_id(text)
        if not target_id:
            message.bot.reply_to(message, "❌ ID غير صحيح")
            return
        
        if target_id == user_id:
            message.bot.reply_to(message, "❌ لا يمكن إضافة نفسك")
            return
        
        if AdminModel.is_admin(target_id):
            message.bot.reply_to(message, "❌ المستخدم أدمن بالفعل")
            return
        
        if AdminModel.add_admin(target_id, user_id, 'limited'):
            message.bot.reply_to(message, f"✅ تم إضافة المستخدم {target_id} كأدمن")
        else:
            message.bot.reply_to(message, "❌ خطأ في إضافة الأدمن")
        
        from handlers.sessions import clear_session
        clear_session(user_id)
    
    def _remove_admin(self, message: Message, text: str):
        """حذف أدمن"""
        user_id = message.from_user.id
        
        if not self.user_service.can_manage_admins(user_id):
            message.bot.reply_to(message, "❌ ليس لديك صلاحية حذف أدمن")
            return
        
        target_id = input_validator.validate_user_id(text)
        if not target_id:
            message.bot.reply_to(message, "❌ ID غير صحيح")
            return
        
        if target_id == user_id:
            message.bot.reply_to(message, "❌ لا يمكن حذف نفسك")
            return
        
        from core.config import ADMIN_ID
        if target_id == ADMIN_ID:
            message.bot.reply_to(message, "❌ لا يمكن حذف المشرف الرئيسي")
            return
        
        if AdminModel.remove_admin(target_id):
            message.bot.reply_to(message, f"✅ تم حذف المستخدم {target_id} من قائمة الأدمن")
        else:
            message.bot.reply_to(message, "❌ خطأ في حذف الأدمن")
        
        from handlers.sessions import clear_session
        clear_session(user_id)
    
    def _edit_referral_rate(self, message: Message, text: str):
        """تعديل نسبة الإحالات"""
        user_id = message.from_user.id
        
        rate = input_validator.validate_amount(text, min_val=0, max_val=100)
        if rate is None:
            message.bot.reply_to(message, "❌ النسبة غير صحيحة (0-100)")
            return
        
        if self.referral_service.update_settings(commission_rate=rate):
            message.bot.reply_to(message, f"✅ تم تعديل نسبة الإحالات إلى {rate}%")
        else:
            message.bot.reply_to(message, "❌ خطأ في تعديل النسبة")
        
        from handlers.sessions import clear_session
        clear_session(user_id)
    
    def _show_top_referrals(self, message: Message, text: str):
        """عرض أعلى الإحالات"""
        user_id = message.from_user.id
        
        limit = input_validator.validate_amount(text, min_val=1, max_val=50)
        if not limit:
            message.bot.reply_to(message, "❌ العدد غير صحيح (1-50)")
            return
        
        referrals = self.referral_service.get_top_referrers(limit)
        
        if not referrals:
            message.bot.reply_to(message, "❌ لا توجد إحالات")
        else:
            msg = f"📈 **أعلى {len(referrals)} إحالة**\n\n"
            
            for i, ref in enumerate(referrals, 1):
                msg += f"{i}. `{ref['referrer_id']}`\n"
                msg += f"   👥 الإجمالي: {ref['total_refs']} إحالة\n"
                msg += f"   ✅ النشطة: {ref['active_refs']} إحالة\n"
                msg += f"   💰 العمولة: {ref['total_commission'] or 0:,} ليرة\n\n"
            
            message.bot.reply_to(message, msg, parse_mode="Markdown")
        
        from handlers.sessions import clear_session
        clear_session(user_id)
    
    def _show_top_balance(self, message: Message, text: str):
        """عرض أعلى الرصيد"""
        user_id = message.from_user.id
        
        limit = input_validator.validate_amount(text, min_val=1, max_val=100)
        if not limit:
            message.bot.reply_to(message, "❌ العدد غير صحيح (1-100)")
            return
        
        users = self.user_service.get_top_users_by_balance(limit)
        
        msg = f"🏆 **أعلى {len(users)} رصيد مستخدمين**\n\n"
        
        for i, user in enumerate(users, 1):
            msg += f"{i}. `{user.user_id}`\n"
            msg += f"   💰 الرصيد: {user.balance:,} ليرة\n"
            msg += f"   📅 الانضمام: {user.created_at[:10]}\n"
            msg += f"   🕒 آخر نشاط: {user.last_active[:16] if user.last_active else 'غير معروف'}\n\n"
        
        message.bot.reply_to(message, msg, parse_mode="Markdown")
        
        from handlers.sessions import clear_session
        clear_session(user_id)
    
    def _handle_admin_action(self, call: CallbackQuery):
        """معالجة إجراءات الأدمن الأخرى"""
        data = call.data
        
        if data == "admin_users_count":
            self._show_users_count(call)
        elif data == "admin_distribute_referrals":
            self._distribute_referrals(call)
        elif data == "admin_reset_all_balances":
            self._reset_all_balances(call)
        elif data == "admin_list_admins":
            self._list_admins(call)
        elif data == "report_today":
            self._show_today_report(call)
        elif data == "report_deposit":
            self._show_deposit_report(call)
        elif data == "report_withdraw":
            self._show_withdraw_report(call)
    
    def _show_users_count(self, call: CallbackQuery):
        """عرض عدد المستخدمين"""
        users = self.user_service.get_all_users(limit=5)
        total = self.user_service.get_system_stats()['total_users']
        
        msg = f"👥 **إحصائيات المستخدمين**\n\n"
        msg += f"📊 **إجمالي المستخدمين:** {total:,}\n"
        
        # جلب من services
        banned = 0
        for user in users:
            if user.is_banned:
                banned += 1
        
        msg += f"🚫 **المحظورين:** {banned}\n"
        msg += f"✅ **النشطين:** {total - banned}\n\n"
        msg += f"📈 **آخر 5 مستخدمين جدد:**\n"
        
        for user in users[:5]:
            msg += f"• `{user.user_id}` - {user.balance:,} ليرة - {user.created_at[:10]}\n"
        
        call.bot.send_message(call.from_user.id, msg, parse_mode="Markdown")
        call.bot.answer_callback_query(call.id, f"✅ العدد: {total}")
    
    def _distribute_referrals(self, call: CallbackQuery):
        """توزيع عمولات الإحالات"""
        result = self.referral_service.distribute_commissions()
        call.bot.answer_callback_query(call.id, result['message'])
    
    def _reset_all_balances(self, call: CallbackQuery):
        """تصفير جميع الأرصدة"""
        kb = get_confirmation_keyboard(
            "confirm_reset_balances",
            "admin_back_to_panel",
            "✅ نعم، تصفير جميع الأرصدة",
            "❌ إلغاء"
        )
        
        msg = "⚠️ **تصفير جميع الأرصدة**\n\n"
        msg += "هل أنت متأكد أنك تريد تصفير أرصدة جميع المستخدمين؟\n"
        msg += "هذا الإجراء لا يمكن التراجع عنه!"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
        call.bot.answer_callback_query(call.id)
    
    def _list_admins(self, call: CallbackQuery):
        """عرض قائمة الأدمن"""
        admins = AdminModel.get_all()
        
        if not admins:
            call.bot.answer_callback_query(call.id, "❌ لا توجد أدمن ثانويين")
            return
        
        msg = "👑 **قائمة الأدمن الثانويين:**\n\n"
        
        for admin in admins:
            msg += f"👤 **المستخدم:** `{admin.user_id}`\n"
            msg += f"📅 أصبح أدمن: {admin.added_at[:10]}\n"
            msg += f"➕ تمت الإضافة بواسطة: `{admin.added_by}`\n"
            msg += f"🔑 الصلاحيات: {admin.permissions}\n"
            msg += "─" * 20 + "\n"
        
        msg += f"\n📊 **المجموع:** {len(admins)} أدمن ثانوي"
        
        call.bot.send_message(call.from_user.id, msg, parse_mode="Markdown")
        call.bot.answer_callback_query(call.id, f"✅ عدد الأدمن: {len(admins)}")
    
    def _show_today_report(self, call: CallbackQuery):
        """عرض تقرير اليوم"""
        report = self.payment_service.get_daily_report()
        
        msg = f"📊 **تقرير اليوم - {report['date']}**\n\n"
        msg += f"👥 **المالية:**\n"
        msg += f"• 💳 إجمالي الإيداع: {report['total_deposit']:,} ليرة\n"
        msg += f"• 💸 إجمالي السحب: {report['total_withdraw']:,} ليرة\n"
        msg += f"• 📈 صافي التدفق: {report['total_deposit'] - report['total_withdraw']:,} ليرة\n"
        msg += f"• 📋 عدد العمليات: {report['deposit_count'] + report['withdraw_count']}\n"
        msg += f"• ⏳ المعلقة: {report['pending_count']}\n\n"
        msg += f"🕒 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        call.bot.send_message(call.from_user.id, msg, parse_mode="Markdown")
        call.bot.answer_callback_query(call.id, "✅ تم إرسال التقرير")
    
    def _show_deposit_report(self, call: CallbackQuery):
        """عرض تقرير الشحن"""
        from keyboards.admin_keyboards import get_reports_keyboard
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(
            InlineKeyboardButton("📱 سيرياتيل كاش", callback_data="report_deposit_syriatel"),
            InlineKeyboardButton("💰 شام كاش", callback_data="report_deposit_sham")
        )
        kb.row(
            InlineKeyboardButton("💵 شام دولار", callback_data="report_deposit_sham_usd"),
            InlineKeyboardButton("📊 جميع الطرق", callback_data="report_deposit_all")
        )
        kb.add(InlineKeyboardButton("⬅ ↩️ رجوع", callback_data="admin_reports"))
        
        msg = "💰 **تقرير عمليات الشحن**\n\nاختر طريقة الدفع:"
        
        call.bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
        call.bot.answer_callback_query(call.id)
    
    def _show_withdraw_report(self, call: CallbackQuery):
        """عرض تقرير السحب"""
        report = self.payment_service.get_daily_report()
        
        msg = f"💸 **تقرير السحب - {report['date']}**\n\n"
        msg += f"💰 **إجمالي المبلغ:** {report['total_withdraw']:,} ليرة\n"
        msg += f"📋 **عدد العمليات:** {report['withdraw_count']}\n"
        
        # جلب المعاملات المعلقة للسحب
        pending_withdrawals = self.payment_service.get_pending_transactions('withdraw')
        
        if pending_withdrawals:
            msg += f"\n⏳ **المعلقة ({len(pending_withdrawals)}):**\n"
            for tx in pending_withdrawals[:5]:
                msg += f"• #{tx.id} - {tx.user_id} - {tx.amount:,} ليرة\n"
        
        call.bot.send_message(call.from_user.id, msg, parse_mode="Markdown")
        call.bot.answer_callback_query(call.id, "✅ تم إرسال التقرير")
    
    def _handle_admin_message_action(self, message: Message, step: str, text: str, temp_data: dict):
        """معالجة رسائل الأدمن الأخرى"""
        # يمكن إضافة المزيد من الإجراءات هنا
        pass