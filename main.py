import asyncio
import os
import re
import time
import threading
from flask import Flask
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, BotCommandScopeAllPrivateChats
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot ishlayapti!"

def run_web():
    app_flask.run(host="0.0.0.0", port=8080)

def start_web():
    threading.Thread(target=run_web).start()

TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
WHITELIST = []
TUN_REJIMI = False
KANAL_USERNAME = None
FOYDALANUVCHILAR = set()

UYAT_SOZLAR = [
    "am", "amlatta", "amyalaq", "amyalar", "amyaloq", "amxor", "am yaliman", "am yalayman", "am latta", "aminga", "aminga ske", "aminga sikay", 
    "asshole", "bastard", "biyundiami", "bitch", "blyat", "buynami", "buyingdi omi", "buyingni ami", "buyundiomi", "dalbayob", "damn", "debil", 
    "dick", "dolboyob", "durak", "eblan", "fuck", "fucker", "gandon", "haromi", "horomi", "hoy", "idinnaxxuy", "idin naxuy", "idin naxxuy", 
    "isqirt", "jalap", "kal", "kot", "kotak", "ko't", "kotinga ske", "kotinga sikay", "kotinga", "ko'tinga", "kotingga", "kotvacha", "ko'tak", 
    "lanati", "lax", "motherfucker", "mudak", "naxxuy", "og'zingaskay", "og'zinga skay", "ogzingaskay", "otti qotagi", "otni qotagi", 
    "otti qo'tag'i", "ogzinga skay", "onagniomi", "onangniami", "pashol naxuy", "padarlanat", "lanat", "pasholnaxxuy", "pidor", 
    "poshol naxxuy", "posholnaxxuy", "poxxuy", "poxuy", "qanjik", "qanjiq", "qonjiq", "qotaq", "qotaqxor", "qo'taq", "qo'taqxo'r", 
    "qotagim", "kotagim", "qo'tag'im", "qotag'im", "qo'tagim", "sik", "sikaman", "sikay", "sikalak", "sikish", "sikishish", "skay", 
    "slut", "soska", "suka", "tashak", "tashaq", "toshoq", "toshok", "xaromi", "xoromi",
    "ам", "амлатта", "аминга", "амялак", "амялок", "амхўр", "амхур", "омин", "оминга", "ам ялиман", "ам ялайман", "искирт", "жалап", 
    "далбаёб", "долбоёб", "гандон", "гондон", "нахуй", "иди нахуй", "идин наххуй", "идиннаххуй", "кот", "котак", "кутагим", "қўтағим",
    "кут", "кутак", "кутингга", "кўт", "кўтингга", "ланати", "нахуй", "наххуй", "огзинга скай", "огзингаскай", "онагниоми", "онагни оми",
    "онангниами", "онангни ами", "огзинга скей", "огзинга сикай", "отни кутаги", "пашол нахуй", "пашолнаххуй", "пидор", "пошол наххуй", 
    "похуй", "поххуй", "пошолнаххуй", "секис", "сикай", "сикаман", "сикиш", "сикишиш", "соска", "сука", "ташак", "ташақ", "тошок", 
    "тошоқ", "хароми", "ҳароми", "ҳороми", "қотақ", "ске", "ланат", "ланати", "падарланат", "қотақхор", "қўтақ", "кутак", "қўтақхўр", 
    "қанжик", "қанжиқ", "қонжиқ", "ам", "амлатта", "амялақ", "амялар", "буйингди ами", "буйингди оми", "буйингни ами", "буйинди оми", 
    "буйнами", "бийинди ами", "ский", "скай", "сикей", "сик", "кутагим", "скаман", "хуй", "xuy", "xuyna", "skey"
]

# ✅ Kanalga obuna bo‘lganmi
async def kanal_tekshir(update: Update):
    if not KANAL_USERNAME:
        return True
    try:
        user = update.message.from_user
        member = await update.get_bot().get_chat_member(KANAL_USERNAME, user.id)
        return member.status in ["member", "creator", "administrator"]
    except:
        return False

# ✅ Reklama va so‘kinish filtri — to‘liq so‘zlar bilan
async def reklama_va_soz_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        text = update.message.text
        chat_id = update.message.chat_id
        msg_id = update.message.message_id

        if not text or not user:
            return

        if user.id in WHITELIST or (user.username and user.username in WHITELIST):
            return

        if TUN_REJIMI:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            return

        if not await kanal_tekshir(update):
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            keyboard = [[InlineKeyboardButton("✅ Men a’zo bo‘ldim", callback_data="kanal_azo")]]
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, siz kanalga a’zo emassiz!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        if re.search(r"(http|www\.|t\.me/|@|reklama|reklam)", text, re.IGNORECASE):
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            return

        sozlar = re.findall(r"\w+", text.lower())
        print("📥 Original text:", text)
        print("🔎 Ajratilgan so‘zlar:", sozlar)
        for soz in sozlar:
            if soz in UYAT_SOZLAR:
                print("❌ Bloklanadigan so‘z:", soz)
                await update.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ {user.first_name}, guruhda so‘kinish taqiqlangan!"
                )
                break
    except Exception as e:
        print(f"[Xatolik] reklama_va_soz_filtri: {e}")

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    FOYDALANUVCHILAR.add(update.effective_user.id)
    await update.message.reply_text("✅ Bot ishga tushdi. So‘kinish va reklama filtr ishlamoqda.")

# ✅ /tun
async def tun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    TUN_REJIMI = True
    await update.message.reply_text("🌙 Tun rejimi yoqildi.")

# ✅ /tunoff
async def tunoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    TUN_REJIMI = False
    await update.message.reply_text("🌤 Tun rejimi o‘chirildi.")

# ✅ Komandalarni ro‘yxatga qo‘shish
async def set_commands():
    await app.bot.set_my_commands(commands=[
        BotCommand("start", "Botni ishga tushurish"),
        BotCommand("tun", "Tun rejimini yoqish"),
        BotCommand("tunoff", "Tun rejimini o‘chirish"),
    ], scope=BotCommandScopeAllPrivateChats())

# ✅ Botni ishga tushirish
async def botni_ishga_tushur():
    await set_commands()
    print("✅ Bot ishga tushdi...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(1)

# ✅ ApplicationBuilder
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("tun", tun))
app.add_handler(CommandHandler("tunoff", tunoff))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reklama_va_soz_filtri))

# ✅ Flask + polling ishga tushirish
if __name__ == "__main__":
    start_web()
    asyncio.get_event_loop().run_until_complete(botni_ishga_tushur())
