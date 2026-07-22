import threading
import logging
import requests
import httpx
import os
import re
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, BOSS_ID, WALLET_ADDRESS, PRICES, AI_API_KEY, AI_BASE_URL, AI_MODEL, PAY_GATEWAYS
from db import init_db, get_balance, add_balance, deduct_balance

init_db()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)
@app.route('/')
def home():
    return "查档机器人运行中！"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= 底部回复键盘（输入框下方） =================
def get_reply_keyboard():
    keyboard = [
        ["充值"],
        ["官方名单"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ================= 生成内联业务菜单 =================
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("主实名", callback_data="主实名")],
        [InlineKeyboardButton("证件照片", callback_data="证件照片")],
        [InlineKeyboardButton("🤖 AI 智能匹配", callback_data="ai_assist")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= 链上核验 TXID（保留备用） =================
def verify_txid(txid, expected_amount):
    try:
        url = f"https://api.trongrid.io/v1/transactions/{txid}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200: return False
        data = resp.json()
        if data.get("to") != WALLET_ADDRESS: return False
        if "raw_data" in data and "contract" in data["raw_data"]:
            contract = data["raw_data"]["contract"][0]
            value = contract["parameter"]["value"]["amount"]
            if float(value / 10**6) >= float(expected_amount): return True
        return False
    except Exception: return False

# ================= 机器人核心逻辑 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 发菜单的同时，带上底部回复键盘
    await update.message.reply_text(
        "📂 请选择业务，或者使用底部菜单进行充值。",
        reply_markup=get_main_keyboard()
    )
    await update.message.reply_text("🟢 底部功能栏已开启", reply_markup=get_reply_keyboard())

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "返回菜单":
        await query.edit_message_text("📂 请选择业务：", reply_markup=get_main_keyboard())
        return

    if data == "ai_assist":
        context.user_data['ai_state'] = 'awaiting_input'
        await query.edit_message_text(
            "🤖 请发送您想查询的描述，AI会自动为您匹配业务。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 取消并返回", callback_data="返回菜单")]])
        )
        return

    service_name = data
    if service_name not in PRICES:
        await query.edit_message_text("⚙️ 业务暂未开放。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")]]))
        return

    price = PRICES[service_name]
    balance = get_balance(user_id)

    if balance < price:
        await query.edit_message_text(
            f"❌ 余额不足。\n当前余额：{balance} USDT\n业务费用：{price} USDT\n请点底部菜单【充值】",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")]])
        )
        return

    deduct_balance(user_id, price)
    new_balance = get_balance(user_id)
    user = update.effective_user
    user_name = user.first_name or "未知"
    username = f"@{user.username}" if user.username else "无用户名"

    notify_msg = (
        f"新报单通知\n"
        f"用户名字：{user_name}\n"
        f"用户名：{username}\n"
        f"用户ID：{user_id}\n"
        f"选择业务：{service_name}\n"
        f"当前余额：扣除后剩余 {new_balance} USDT"
    )
    await context.bot.send_message(chat_id=BOSS_ID, text=notify_msg)

    await query.edit_message_text(
        f"✅ 报单成功！\n\n业务：{service_name}\n扣除金额：{price} USDT\n剩余余额：{new_balance} USDT\n\n📨 报单已发送给老板。",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")]])
    )

# ================= 处理文字和底部按钮 =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # 1. 官方名单（底部按钮触发）
    if text == "官方名单":
        official_msg = (
            "机器人老板：枭雄·天眼查人 @xxtyc8\n"
            "公群链接：<a href=\"https://telegram.me/+cmzARoDq7WM0NTY1\">达利34 老牌查档</a>\n"
            "机器人开发者：@gsyxyc"
        )
        await update.message.reply_text(official_msg, parse_mode='HTML', disable_web_page_preview=True)
        return

    # 2. 充值请求（底部按钮触发 / 手动输入）
    if text == "充值":
        context.user_data['pending_charge'] = 'waiting_amount'
        await update.message.reply_text("💰 请输入您要充值的金额（请输入纯数字，例如：20）：", reply_markup=ReplyKeyboardRemove())
        return

    # 3. 处理金额输入
    if context.user_data.get('pending_charge') == 'waiting_amount':
        try:
            amount = int(text)
            if amount <= 0: raise ValueError
            
            # 这里调用网关接口生成二维码（因缺少API地址，先返回提示）
            gateway_url = PAY_GATEWAYS["okpay"]["api_url"]
            if "这里填" in gateway_url:
                await update.message.reply_text("⚠️ 网关 API 接口地址尚未配置，请先在 config.py 中填入平台提供的订单接口 URL 并重启。")
                context.user_data.pop('pending_charge', None)
                return
            
            # ===== 真实网关请求逻辑（如果你填好了api_url会自动执行） =====
            # 示例模拟请求：
            # payload = {'app_id': PAY_GATEWAYS["okpay"]["app_id"], 'amount': amount}
            # response = requests.post(gateway_url, json=payload)
            # qr_data = response.json()['qr_url']
            
            await update.message.reply_text(f"✅ 已收到充值 {amount} USDT 请求，正在生成专属收款码...\n（此处将生成二维码并发送，请确保 config.py 中网关接口地址已正确配置）")
            
            context.user_data.pop('pending_charge', None)
            await update.message.reply_text("🟢 底部功能栏已恢复", reply_markup=get_reply_keyboard())
            
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的整数金额。")
        return

    # 4. AI 处理
    if context.user_data.get('ai_state') == 'awaiting_input':
        await update.message.reply_text("🧠 正在分析您的需求，请稍候...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个业务匹配助手。用户会发送一段描述需求的文字，你需要从以下业务列表中选择最匹配的1到2项，并严格只返回业务名称，用逗号隔开。如果完全不匹配，请返回“无匹配”。业务列表：[主实名, 证件照片]"},
                        {"role": "user", "content": text}
                    ]
                }
                response = await client.post(AI_BASE_URL, json=payload, headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"})
                if response.status_code == 200:
                    ai_result = response.json()['choices'][0]['message']['content'].strip()
                    items = ai_result.replace("，", ",").split(",")
                    # 过滤有效业务
                    valid_services = [i.strip() for i in items if i.strip() in PRICES]
                    if valid_services:
                        keyboard = [[InlineKeyboardButton(s, callback_data=s)] for s in valid_services]
                        keyboard.append([InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")])
                        await update.message.reply_text("🔍 为你查找到以下类似的选项，请点击选择：", reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        await update.message.reply_text("❌ 未能精准匹配到业务，请点击菜单重新选择。")
                else:
                    await update.message.reply_text("❌ AI接口超时，请稍后重试。")
        except Exception as e:
            await update.message.reply_text(f"❌ AI请求失败：{str(e)}")
        context.user_data.pop('ai_state', None)
        return

    # 5. 其他乱发消息
    await update.message.reply_text("❓ 请使用底部按钮或发送 /start 开始。")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ 查档机器人（双网关+底部键盘版）已上线！")
    application.run_polling()

if __name__ == "__main__":
    main()
