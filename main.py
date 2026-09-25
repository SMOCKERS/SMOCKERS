import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 SMOCKERS ON BOS!\nBot Cupang Medan udah aktif!\n\nKetik /menu buat liat stok"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 MENU SMOCKERS:\n- Cupang Halfmoon\n- Cupang Plakat\n- Cupang Avatar\n\nChat admin: @username lu"
    )

token = os.getenv("BOT_TOKEN")
app = ApplicationBuilder().token(token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
print("Bot jalan...")
app.run_polling()
