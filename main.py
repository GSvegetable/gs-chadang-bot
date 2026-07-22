import threading
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import handlers
from config import BOT_TOKEN

def main():
    threading.Thread(target=handlers.run_flask, daemon=True).start()
    application = Application.builder().token(BOT_TOKEN).build()

    # 注册所有指令
    application.add_handler(CommandHandler("start", handlers.start))
    # 🟢 新加两行，让机器人能识别 /recharge 和 /ai
    application.add_handler(CommandHandler("recharge", handlers.recharge_command))
    application.add_handler(CommandHandler("ai", handlers.ai_command))

    application.add_handler(CallbackQueryHandler(handlers.button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    print("✅ 查档机器人（斜杠指令已激活）已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
