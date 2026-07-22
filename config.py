import os

# 🟢 从 Railway 环境变量读取 Token（安全做法）
BOT_TOKEN = os.getenv("BOT_TOKEN", "8781304324:AAFQmsif37BX7fEr2wix0bkBtPZjMnNT8Go")

# 🟢 老板（就是你）的 Telegram ID
BOSS_ID = 7857605443

# 🟢 老板提供的 USDT（TRC20）收款钱包地址
WALLET_ADDRESS = "TVy6chYwgvEy9QAnQvQnR4oEuxPyRx2YmT"

# 🟢 业务价格字典（键是业务名，值是对应的费用）
# 只有写了这两个价格的会真正扣费，其他的全都在代码里被设为“暂未开放”
PRICES = {
    "机主实名": 20,
    "证件照片": 30,
}
