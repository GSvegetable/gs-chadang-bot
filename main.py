import threading
import logging
import requests
import httpx
import os
import re
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, BOSS_ID, WALLET_ADDRESS, PRICES, AI_API_KEY, AI_BASE_URL, AI_MODEL
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

# ================= 生成简化版菜单 =================
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("主实名", callback_data="主实名")],
        [InlineKeyboardButton("证件照片", callback_data="证件照片")],
        [InlineKeyboardButton("🤖 AI 智能匹配", callback_data="ai_assist")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= 链上核验 TXID =================
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
            if float(value / 10**6) >= float(expected_amount):
                return True
        return False
    except Exception:
        return False

# ================= 机器人核心逻辑 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 请选择业务：",
        reply_markup=get_main_keyboard()
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # 1. 返回菜单 / 取消充值
    if data == "返回菜单":
        await query.edit_message_text("📂 请选择业务：", reply_markup=get_main_keyboard())
        return

    # 2. 充值说明
    if data == "充值说明":
        await query.edit_message_text(
            f"💰 充值说明\n\n"
            f"1. 请向老板钱包地址转账 U (TRC20)：\n`{WALLET_ADDRESS}`\n\n"
            f"2. 转账后，请在聊天框输入：`/charge 金额`\n"
            f"   例如：`/charge 50`\n\n"
            f"3. 接着按提示发送交易哈希（TXID）即可自动完成充值。",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")]])
        )
        return

    # 3. AI 智能匹配入口
    if data == "ai_assist":
        context.user_data['ai_state'] = 'awaiting_input'
        await query.edit_message_text(
            "🤖 请发送您想查询的描述（例如：我想查一个人，还有他爸爸之前开过的公司）\n\nAI 会自动为您匹配并扣费报单。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 取消并返回", callback_data="返回菜单")]])
        )
        return

    # 4. 处理常规业务按钮（主实名、证件照片）
    service_name = data
    if service_name not in PRICES:
        await query.edit_message_text("⚙️ 业务暂未开放。", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回菜单", callback_data="返回菜单")]]))
        return

    price = PRICES[service_name]
    balance = get_balance(user_id)

    if balance < price:
        await query.edit_message_text(
            f"❌ 余额不足。\n当前余额：{balance} USDT\n业务费用：{price} USDT",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 点击查看充值方式", callback_data="充值说明")]])
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

# ================= 充值流程 =================
async def charge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("❌ 格式错误。请使用：`/charge 金额` （如：`/charge 20`）")
        return
    try:
        amount = int(args[0])
        if amount <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ 金额必须为大于 0 的整数。")
        return

    context.user_data['pending_recharge'] = amount
    await update.message.reply_text(f"📤 您的充值金额为 {amount} USDT。\n请将转账后生成的【交易哈希（TXID）】复制并发送给我。")

# ================= 处理普通文字消息 + AI 匹配 =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # 优先处理充值 TXID 状态
    if 'pending_recharge' in context.user_data:
        txid = text.strip()
        amount = context.user_data['pending_recharge']
        await update.message.reply_text("⏳ 正在链上核验您的交易，请稍候...")

        if verify_txid(txid, amount):
            add_balance(user_id, amount)
            del context.user_data['pending_recharge']
            await update.message.reply_text(f"✅ 充值成功！余额已增加 {amount} USDT。\n当前余额：{get_balance(user_id)} USDT")
            return
        else:
            del context.user_data['pending_recharge']
            await update.message.reply_text(f"❌ 核验失败。可能是 TXID 填写错误或金额不匹配，请核对后重新充值。")
            return

    # 处理 AI 状态
    if context.user_data.get('ai_state') == 'awaiting_input':
        await update.message.reply_text("🧠 正在分析您的需求，请稍候...")
        # 调用 DeepSeek API
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个业务匹配助手。用户会发送一段描述需求的文字，你需要从以下业务列表中选择最匹配的一项，并严格只返回该业务名称，不要包含任何多余的文字、标点符号或表情。如果完全不匹配，请返回“无匹配”。业务列表：[主实名, 证件照片]"},
                        {"role": "user", "content": text}
                    ]
                }
                response = await client.post(
                    AI_BASE_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    ai_result = response.json()['choices'][0]['message']['content'].strip()
                    print(f"AI 返回结果: {ai_result}")
                    
                    # 匹配逻辑
                    if ai_result in PRICES:
                        service_name = ai_result
                        price = PRICES[service_name]
                        balance = get_balance(user_id)

                        if balance < price:
                            await update.message.reply_text(
                                f"❌ 已为您匹配到业务【{service_name}】，但余额不足。\n当前余额：{balance} USDT\n业务费用：{price} USDT",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 充值", callback_data="充值说明")]])
                            )
                        else:
                            deduct_balance(user_id, price)
                            new_balance = get_balance(user_id)
                            user = update.effective_user
                            user_name = user.first_name or "未知"
                            username = f"@{user.username}" if user.username else "无用户名"

                            notify_msg = (
                                f"新报单通知（AI匹配）\n"
                                f"用户名字：{user_name}\n"
                                f"用户名：{username}\n"
                                f"用户ID：{user_id}\n"
                                f"选择业务：{service_name}\n"
                                f"当前余额：扣除后剩余 {new_balance} USDT"
                            )
                            await context.bot.send_message(chat_id=BOSS_ID, text=notify_msg)

                            await update.message.reply_text(
                                f"✅ AI 匹配报单成功！\n\n业务：{service_name}\n扣除金额：{price} USDT\n剩余余额：{new_balance} USDT\n\n📨 报单已发送给老板。",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回菜单", callback_data="返回菜单")]])
                            )
                    else:
                        await update.message.reply_text(
                            f"❌ AI 未能匹配到精准业务。\n{ai_result}",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回菜单", callback_data="返回菜单")]])
                        )
                else:
                    await update.message.reply_text("❌ AI 接口请求失败，请稍后重试。")
        except Exception as e:
            await update.message.reply_text(f"❌ 网络或 API 出错：{str(e)}")
        
        # 不论成功失败，清除 AI 状态防止干扰下次输入
        context.user_data.pop('ai_state', None)
        return

    # 如果用户胡乱发送文字，且没有触发任何状态
    await update.message.reply_text("❓ 请发送 /start 开始使用，或发送 /charge 进行充值。")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("charge", charge_command))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ 查档机器人（AI 极简版）已上线！")
    application.run_polling()

if __name__ == "__main__":
    main()
