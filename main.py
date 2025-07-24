import os
import threading
from flask import Flask
from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TOKEN") or "123456789:YOUR-BOT-TOKEN-HERE"

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot ishlayapti!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

def start_web():
    thread = threading.Thread(target=run_web)
    thread.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Men Render.com da ishlayapman!")

async def main():
    app_builder = ApplicationBuilder().token(TOKEN).build()
    app_builder.add_handler(CommandHandler("start", start))
    app_builder.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
    await app_builder.initialize()
    await app_builder.start()
    await app_builder.updater.start_polling()
    await app_builder.updater.idle()

if __name__ == "__main__":
    start_web()
    import asyncio
    asyncio.run(main())
