import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 SMOCKERS ON BOS!\nBot Cupang Medan aktif!\nKetik /menu")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 MENU:\n- Halfmoon\n- Plakat\n- Avatar")

async def balas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Lu: {update.message.text}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, balas))
app.run_polling()
