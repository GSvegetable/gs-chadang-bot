import threading
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# 引入拆分出去的 handlers 模块
import handlers
from config import BOT_TOKEN

def main():
    # 1. 启动 Flask 保活网页（在 handlers.py 里）
    threading.Thread(target=handlers.run_flask, daemon=True).start()

    # 2. 启动 Telegram 机器人
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    print("✅ 查档机器人（精简拆分版）已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
