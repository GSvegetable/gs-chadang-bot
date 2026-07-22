import os

# 🟢 Railway 环境变量读取
BOT_TOKEN = os.getenv("BOT_TOKEN", "8781304324:AAFQmsif37BX7fEr2wix0bkBtPZjMnNT8Go")

# 🟢 老板（就是你）的 Telegram ID
BOSS_ID = 7857605443

# 🟢 老板的 USDT (TRC20) 收款地址
WALLET_ADDRESS = "TVy6chYwgvEy9QAnQvQnR4oEuxPyRx2YmT"

# 🟢 业务价格字典（只保留两个业务）
PRICES = {
    "主实名": 20,
    "证件照片": 30,
}

# 🟢 DeepSeek AI 配置
AI_API_KEY = "sk-4583c7674eaf43ebba51c7ce817a6eb1"
AI_BASE_URL = "https://api.deepseek.com/chat/completions"
AI_MODEL = "deepseek-chat"
