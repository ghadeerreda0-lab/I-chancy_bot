import os
import asyncio
import logging
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "IChancy Bot Running!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# إعدادات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    TOKEN = os.getenv("8312113931:AAFKlUxshhvrZ9IiMn9Wj4FelfcISj31S9w", "")
    ADMIN_ID = int(os.getenv("8146077656", "0"))
    SYR_CASH_NUMBER = os.getenv("SYR_CASH_NUMBER", "0990000000")
    SCH_CASH_NUMBER = os.getenv("SCH_CASH_NUMBER", "0940000000")
    CHANNEL_SYR_CASH = int(os.getenv("CHANNEL_SYR_CASH", "-1003597919374"))
    CHANNEL_SCH_CASH = int(os.getenv("CHANNEL_SCH_CASH", "-1003464319533"))
    CHANNEL_ADMIN_LOGS = int(os.getenv("CHANNEL_ADMIN_LOGS", "-1003577468648"))
    CHANNEL_WITHDRAW = int(os.getenv("CHANNEL_WITHDRAW", "-1003443113179"))
    CHANNEL_SUPPORT = int(os.getenv("CHANNEL_SUPPORT", "-1003514396473"))

config = Config()

if not config.TOKEN:
    print("❌ أضف BOT_TOKEN في Render Dashboard!")
    exit(1)

bot = AsyncTeleBot(config.TOKEN, parse_mode="HTML")

# القائمة الرئيسية
def main_menu(user_id: int):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("⚡ Ichancy", callback_data="ichancy"))
    kb.add(
        InlineKeyboardButton("📥 شحن رصيد", callback_data="charge"),
        InlineKeyboardButton("📤 سحب رصيد", callback_data="withdraw")
    )
    kb.add(InlineKeyboardButton("💰 نظام الاحالات", callback_data="referrals"))
    kb.add(
        InlineKeyboardButton("🎁 اهداء رصيد", callback_data="gift"),
        InlineKeyboardButton("🎁 كود هدية", callback_data="gift_code")
    )
    kb.add(
        InlineKeyboardButton("✉️ تواصل مع الدعم", callback_data="support"),
        InlineKeyboardButton("✉️ تواصل معنا", callback_data="contact")
    )
    kb.add(
        InlineKeyboardButton("🔁 السجل", callback_data="logs"),
        InlineKeyboardButton("☁️ الشروحات", callback_data="tutorials")
    )
    kb.add(InlineKeyboardButton("🔁 سجل الرهانات", callback_data="bets"))
    kb.add(InlineKeyboardButton("🆕 🃏 الجاكبوت", callback_data="jackpot"))
    kb.add(
        InlineKeyboardButton("↗️ Vp لتشغيل كامل اقسام الموقع", callback_data="vp"),
        InlineKeyboardButton("↗️ ichancy apk", callback_data="apk")
    )
    kb.add(InlineKeyboardButton("📌 الشروط والأحكام", callback_data="rules"))
    
    if user_id == config.ADMIN_ID:
        kb.add(InlineKeyboardButton("🎛 لوحة التحكم", callback_data="admin_panel"))
    
    return kb

# معالجة /start
@bot.message_handler(commands=["start"])
async def start_command(message):
    try:
        welcome = f"""
👋 أهلاً بك <b>{message.from_user.first_name}</b> في <b>IChancy</b>!

⚡ <b>منصة التعاملات المالية الآمنة</b>
        
💰 <b>رصيدك الحالي:</b> <code>50,000 ليرة سورية</code>
🎫 <b>كود الإحالة:</b> <code>ICH{message.from_user.id}123</code>
        """
        
        await bot.send_message(
            message.chat.id,
            welcome,
            reply_markup=main_menu(message.from_user.id),
            parse_mode="HTML"
        )
        
        logger.info(f"✅ بدء جلسة: {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"خطأ في start: {e}")

# معالجة الأزرار
@bot.callback_query_handler(func=lambda call: True)
async def callback_handler(call):
    try:
        if call.data == "support":
            await bot.send_message(call.message.chat.id, "✍️ اكتب رسالتك للدعم:")
            await bot.answer_callback_query(call.id)
        
        elif call.data == "charge":
            await bot.send_message(call.message.chat.id, "📥 اختر طريقة الدفع:")
            await bot.answer_callback_query(call.id)
        
        elif call.data == "withdraw":
            await bot.send_message(call.message.chat.id, "📤 اختر طريقة السحب:")
            await bot.answer_callback_query(call.id)
        
        else:
            await bot.answer_callback_query(call.id, "🛠️ قيد التطوير!", show_alert=True)
            
    except Exception as e:
        logger.error(f"خطأ في callback: {e}")

# التشغيل الرئيسي
async def main():
    keep_alive()
    print("🚀 بدء تشغيل IChancy Bot...")
    await bot.polling(none_stop=True)

if __name__ == "__main__":
    asyncio.run(main())