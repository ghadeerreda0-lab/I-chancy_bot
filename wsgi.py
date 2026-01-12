# ملف wsgi.py بسيط لتشغيل البوت
import os
import sys
import threading
from app import keep_alive, bot

# تشغيل Flask في thread منفصل
flask_thread = threading.Thread(target=keep_alive, daemon=True)
flask_thread.start()

# تشغيل البوت
if __name__ == "__main__":
    print("🚀 بدء تشغيل IChancy Bot...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)