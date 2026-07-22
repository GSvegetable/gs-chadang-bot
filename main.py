import threading
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import handlers
from config import BOT_TOKEN

def main():
    threading.Thread(target=handlers.run_flask, daemon=True).start()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    print("✅ 查档机器人已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
