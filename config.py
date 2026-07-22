import os

# 🟢 机器人的身份
BOT_TOKEN = os.getenv("BOT_TOKEN", "8781304324:AAFQmsif37BX7fEr2wix0bkBtPZjMnNT8Go")

# 🟢 老板的 Telegram ID
BOSS_ID = 7857605443

# 🟢 老板的 USDT 收款地址
WALLET_ADDRESS = "TVy6chYwgvEy9QAnQvQnR4oEuxPyRx2YmT"

# 🟢 业务价格（两个核心业务）
PRICES = {
    "主实名": 20,
    "证件照片": 30,
}

# 🟢 DeepSeek AI 密钥
AI_API_KEY = "sk-4583c7674eaf43ebba51c7ce817a6eb1"
AI_BASE_URL = "https://api.deepseek.com/chat/completions"
AI_MODEL = "deepseek-chat"

# 🟢 双支付网关配置
# ⚠️ 重点：请把 `请求地址` 替换成平台提供的真实接口网址（例如：https://api.okpay.com/api/order）
PAY_GATEWAYS = {
    "okpay": {
        "enable": True,  # 设为 True 开启，False 关闭
        "app_id": "37315",
        "secret": "6Rk5bPqx5pRdqn7chPZXY4dFKvyhAvIn",
        "api_url": "https://这里填okpay的订单创建接口"
    },
    "fulilai": {
        "enable": True,  # 设为 True 开启，False 关闭
        "app_id": "5247784160",
        "secret": "4b9fc4a2b0564a3b93487cb1547724ea",
        "api_url": "https://这里填福利来的订单创建接口"
    }
}
