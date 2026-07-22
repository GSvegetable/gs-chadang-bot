import threading
import logging
import requests
import httpx
import os
import time
import secrets
import hmac
import hashlib
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from config import BOT_TOKEN, BOSS_ID, PRICES, AI_API_KEY, AI_BASE_URL, AI_MODEL, OKPAY_BASE_URL, OKPAY_APP_ID, OKPAY_TOKEN
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

# ================= OkPay 签名算法 =================
def build_okpay_sign(params, token):
    filtered = {k: v for k, v in params.items() if k != 'sign' and v is not None and v != ''}
    sorted_keys = sorted(filtered.keys())
    base_string = "&".join([f"{k}={filtered[k]}" for k in sorted_keys])
    signature = hmac.new(token.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    return signature

# ================= 生成 OkPay 订单 =================
def create_okpay_order(amount, user_id):
    url = f"{OKPAY_BASE_URL}/shop/payLink"
    timestamp = int(time.time())
    nonce = secrets.token_hex(8)
    unique_id = f"{user_id}_{timestamp}"

    params = {
        "id": OKPAY_APP_ID,
        "amount": str(amount),
        "coin": "USDT",
        "unique_id": unique_id,
        "timestamp": str(timestamp),
        "nonce": nonce,
        "callback_url": f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'your-railway-domain.up.railway.app')}/okpay_callback"
    }
    
    sign = build_okpay_sign(params, OKPAY_TOKEN)
    params["sign"] = sign
    
    try:
        response = requests.post(url, data=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {"success": True, "pay_url": data["data"]["pay_url"], "order_id": data["data"]["order_id"]}
            else:
                return {"success": False, "msg": data.get("msg", "未知错误")}
        return {"success": False, "msg": f"请求失败，状态码：{response.status_code}"}
    except Exception as e:
        return {"success": False, "msg": str(e)}

@app.route('/okpay_callback', methods=['POST'])
def okpay_callback():
    try:
        body = request.get_json()
        received_sign = body.get("sign")
        calculated_sign = build_okpay_sign(body, OKPAY_TOKEN)
        if not hmac.compare_digest(calculated_sign, received_sign):
            return "bad sign", 400
        if body.get("status") == "success" and body.get("code") == 200:
            data = body.get("data", {})
            unique_id = data.get("unique_id")
            if unique_id:
                user_id = int(unique_id.split('_')[0])
                amount = float(data.get("amount", 0))
                if amount > 0:
                    add_balance(user_id, amount)
        return "ok", 200
    except Exception:
        return "error", 500

def get_reply_keyboard():
    return ReplyKeyboardMarkup([["充值"], ["官方名单"]], resize_keyboard=True)

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("主实名", callback_data="主实名")],
        [InlineKeyboardButton("证件照片", callback_data="证件照片")],
        [InlineKeyboardButton("🤖 AI 智能匹配", callback_data="ai_assist")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📂 请选择业务，或使用底部菜单。", reply_markup=get_main_keyboard())
    await update.message.reply_text("🟢 功能栏已开启", reply_markup=get_reply_keyboard())

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
        await query.edit_message_text("🤖 请发送查询描述。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 取消", callback_data="返回菜单")]]))
        return

    service_name = data
    if service_name not in PRICES:
        await query.edit_message_text("⚙️ 暂未开放。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")]]))
        return

    price = PRICES[service_name]
    balance = get_balance(user_id)

    if balance < price:
        await query.edit_message_text(f"❌ 余额不足。请点底部【充值】", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")]]))
        return

    deduct_balance(user_id, price)
    new_balance = get_balance(user_id)
    user = update.effective_user
    user_name = user.first_name or "未知"
    username = f"@{user.username}" if user.username else "无用户名"

    await context.bot.send_message(chat_id=BOSS_ID, text=f"新报单通知\n用户名字：{user_name}\n用户名：{username}\n用户ID：{user_id}\n选择业务：{service_name}\n余额：{new_balance} USDT")
    await query.edit_message_text(f"✅ 报单成功！", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")]]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "官方名单":
        await update.message.reply_text("机器人老板：枭雄·天眼查人 @xxtyc8\n公群链接：<a href=\"https://telegram.me/+cmzARoDq7WM0NTY1\">达利34 老牌查档</a>\n开发者：@gsyxyc", parse_mode='HTML', disable_web_page_preview=True)
        return

    if text == "充值":
        context.user_data['pending_charge'] = 'waiting_amount'
        await update.message.reply_text("💰 请输入金额（纯数字）：", reply_markup=ReplyKeyboardRemove())
        return

    if context.user_data.get('pending_charge') == 'waiting_amount':
        try:
            amount = int(text)
            if amount <= 0: raise ValueError
            await update.message.reply_text("⏳ 生成订单中...")
            result = create_okpay_order(amount, user_id)
            if result["success"]:
                await update.message.reply_text(f"✅ 支付链接已生成！", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 点击支付", url=result["pay_url"])]]))
            else:
                await update.message.reply_text(f"❌ 失败：{result['msg']}")
            context.user_data.pop('pending_charge', None)
            await update.message.reply_text("🟢 功能栏恢复", reply_markup=get_reply_keyboard())
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的整数。")
        return

    if context.user_data.get('ai_state') == 'awaiting_input':
        await update.message.reply_text("🧠 分析中...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {"model": AI_MODEL, "messages": [{"role": "system", "content": "你是一个匹配助手，从[主实名, 证件照片]中匹配，返回名称用逗号隔开。"}, {"role": "user", "content": text}]}
                response = await client.post(AI_BASE_URL, json=payload, headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"})
                if response.status_code == 200:
                    ai_result = response.json()['choices'][0]['message']['content'].strip()
                    valid_services = [i.strip() for i in ai_result.replace("，", ",").split(",") if i.strip() in PRICES]
                    if valid_services:
                        keyboard = [[InlineKeyboardButton(s, callback_data=s)] for s in valid_services]
                        keyboard.append([InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")])
                        await update.message.reply_text("🔍 为你找到：", reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        await update.message.reply_text("❌ 未匹配到。")
                else:
                    await update.message.reply_text("❌ AI 超时。")
        except Exception:
            await update.message.reply_text("❌ AI 请求失败。")
        context.user_data.pop('ai_state', None)
        return
