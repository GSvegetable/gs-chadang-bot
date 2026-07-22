import os

# 🟢 机器人的身份（必须在 Railway 的 Variables 中填入）
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🟢 老板的 Telegram ID
BOSS_ID = 7857605443

# 🟢 业务价格
PRICES = {
    "主实名": 20,
    "证件照片": 30,
}

# 🟢 DeepSeek AI 密钥
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = "https://api.deepseek.com/chat/completions"
AI_MODEL = "deepseek-chat"

# 🟢 OkPay 支付网关配置（全部从环境变量读取）
OKPAY_BASE_URL = "https://api.okaypay.me"
OKPAY_APP_ID = os.getenv("OKPAY_APP_ID")
OKPAY_TOKEN = os.getenv("OKPAY_TOKEN")
