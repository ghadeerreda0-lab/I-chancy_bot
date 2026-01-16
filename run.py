"""
run.py - تشغيل البوت
"""

import os
import sys

# إضافة المسار الحالي إلى Python Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot_main import main

if __name__ == "__main__":
    main()