import os
import threading
import time
import asyncio
import re
from flask import Flask
from telegram import (Update, BotCommand, BotCommandScopeAllPrivateChats,
                      InlineKeyboardButton, InlineKeyboardMarkup,
                      ChatPermissions)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters)

# 🔒 Web serverni ishga tushurish (ping uchun)
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot ishlayapti!"

def run_web():
    app_flask.run(host="0.0.0.0", port=8080)

def start_web():
    threading.Thread(target=run_web).start()

# 🔒 Foydalanuvchi adminmi, tekshirish
async def is_admin(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    member = await chat.get_member(user.id)
    return member.status in ("administrator", "creator")

# 🔐 TOKEN
TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"

# 📌 Global o‘zgaruvchilar
WHITELIST = [165553982, "Yunus1995"]
MAJBUR_LIMIT = 10
RUXSAT_USER_IDS = set()
MAJBUR_USERS = {}
TUN_REJIMI = False
KANAL_USERNAME = None
FOYDALANUVCHI_HISOBI = {}
BLOK_VAQTLARI = {}
BLOK_MUDDATI = 300

# 🧩 Shu yerga siz yuborgan barcha funksiyalar (reklama_aniqlash, majbur, kanal, count, tun, ruxsat, va h.k.)ni joylashtiramiz
# ⚠️ Men ular siz yuborgan fayldan to‘liq olingan deb hisoblayman, ular yuqoridagi kodda mavjud bo‘lgani sababli takrorlamadim

# 🟢 Botni ishga tushirish
async def botni_ishga_tushur():
    application = ApplicationBuilder().token(TOKEN).build()

    # 👇 Bu yerda barcha handler’lar qo‘shiladi
    application.add_handler(CommandHandler("start", help))  # misol uchun
    # (Siz yuborgan barcha handlerlar bu yerga joylashtiriladi)

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await set_commands()
    print("✅ Bot Render.com da ishga tushdi!")

    while True:
        await asyncio.sleep(1)

# 🔁 Ishga tushirish
if __name__ == "__main__":
    start_web()
    asyncio.get_event_loop().run_until_complete(botni_ishga_tushur())
