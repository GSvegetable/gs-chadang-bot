import os

# 必须从 Railway 的 Variables 环境变量中读取
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 老板的 Telegram ID
BOSS_ID = 7857605443

# 🟢 业务价格表（已改成「机主实名」和「证件照片」）
PRICES = {
    "机主实名": 20,
    "证件照片": 30,
}

# DeepSeek AI 密钥
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = "https://api.deepseek.com/chat/completions"
AI_MODEL = "deepseek-chat"

# OkPay 网关配置
OKPAY_BASE_URL = "https://api.okaypay.me"
OKPAY_APP_ID = os.getenv("OKPAY_APP_ID")
OKPAY_TOKEN = os.getenv("OKPAY_TOKEN")
