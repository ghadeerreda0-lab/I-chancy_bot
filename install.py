import subprocess
import sys

packages = [
    "pyTelegramBotAPI==4.15.2",
    "Flask==3.0.0", 
    "python-dotenv==1.0.1"
]

print("📦 تثبيت المكتبات...")
for pkg in packages:
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
print("✅ تم التثبيت!")