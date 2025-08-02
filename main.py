import threading
from flask import Flask

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot ishlayapti!"

def run_web():
    app_flask.run(host="0.0.0.0", port=8080)

def start_web():
    threading.Thread(target=run_web).start()

from telegram import Update, BotCommand, BotCommandScopeAllPrivateChats
from telegram.ext import (CallbackQueryHandler, ApplicationBuilder,
                          CommandHandler, MessageHandler, filters,
                          ContextTypes, ChatMemberHandler)
import re
import os
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions


# ✅ So'kinish va uyatsiz so'zlarni aniqlash va o'chirish
UYAT_SOZLAR = [
     "am", "amlatta", "amyalaq", "amyalar", "amyaloq", "amxor", "am yaliman", "am yalayman", "am latta", "aminga", "aminga ske", "aminga sikay", "asshole", "bastard", "biyundiami", "bitch", "blyat", "buynami", "buyingdi omi",
    "buyingni ami", "buyundiomi", "dalbayob", "damn", "debil", "dick", "dolboyob", "durak", "eblan", "fuck", "fucker",
    "gandon", "haromi", "horomi", "hoy", "idinnaxxuy", "idin naxuy", "idin naxxuy", "isqirt", "jalap", "kal", "kot", "kotak", "ko't", "kotinga ske", "kotinga sikay", "kotinga", "ko'tinga", "kotingga", "kotvacha",
    "ko'tak", "lanati", "lax", "motherfucker", "mudak", "naxxuy", "og'zingaskay", "og'zinga skay", "ogzingaskay", "otti qotagi", "otni qotagi", "otti qo'tag'i",
    "ogzinga skay", "onagniomi", "onangniami", "pashol naxuy", "padarlanat", "lanati", "lanat", "pasholnaxxuy", "pidor", "poshol naxxuy", "posholnaxxuy", "poxxuy", "poxuy",
    "qanjik", "qanjiq", "qonjiq", "qotaq", "qotaqxor", "qo'taq", "qo'taqxo'r", "qotagim", "kotagim", "qo'tag'im", "qotag'im", "qo'tagim", "sik", "sikaman", "sikay", "sikalak",
    "sikish", "sikishish", "skay", "slut", "soska", "suka", "tashak", "tashaq", "toshoq", "toshok", "xaromi", "xoromi",
    "ам", "амлатта", "аминга", "амялак", "амялок", "амхўр", "амхур", "омин", "оминга", "ам ялиман", "ам ялайман", "искирт", "жалап", "далбаёб", "долбоёб", "гандон", "гондон", "нахуй", "иди нахуй", "идин наххуй", "идиннаххуй", "кот", "котак", "кутагим", "қўтағим",
    "кут", "кутак", "кутингга", "кўт", "кўтингга", "ланати", "нахуй", "наххуй", "огзинга скай", "огзингаскай", "онагниоми", "онагни оми",
    "онангниами", "онангни ами", "огзинга скей", "огзинга сикай", "отни кутаги", "пашол нахуй", "пашолнаххуй", "пидор", "пошол наххуй", "похуй", "поххуй", "пошолнаххуй", "секис", "сикай", "сикаман",
    "сикиш", "сикишиш", "соска", "сука", "ташак", "ташақ", "тошок", "тошоқ", "хароми", "ҳароми", "ҳороми", "қотақ", "ске", "ланат", "ланати", "падарланат",
    "қотақхор", "қўтақ", "кутак", "қўтақхўр", "қанжик", "қанжиқ", "қонжиқ", "ам", "амлатта", "амялақ", "амялар", "буйингди ами",
    "буйингди оми", "буйингни ами", "буйинди оми", "буйнами", "бийинди ами", "ский", "скай", "сикей", "сик", "кутагим", "скаман", "хуй", "xuy", "xuyna", "skey"
]

async def sokinish_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return
        text = update.message.text.lower()
        for soz in UYAT_SOZLAR:
            if soz in text:
                await update.message.delete()
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⚠️ {update.effective_user.first_name}, guruhda so'kinish taqiqlangan. Iltimos, odobli bo‘ling!"
                    )
                except:
                    pass
                break
    except Exception as e:
        print(f"So'kinish filtrda xatolik: {e}")




# 🔒 Foydalanuvchi adminmi, tekshirish
async def is_admin(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    member = await chat.get_member(user.id)
    return member.status in ("administrator", "creator")

TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"

WHITELIST = [165553982, "Yunus1995"]
TUN_REJIMI = False
KANAL_USERNAME = None
FOYDALANUVCHILAR = set()  # Bot foydalanuvchilari

async def kanal_tekshir(update: Update):
    global KANAL_USERNAME
    if not KANAL_USERNAME:
        return True
    try:
        user = update.message.from_user
        member = await update.get_bot().get_chat_member(KANAL_USERNAME, user.id)
        return member.status in ["member", "creator", "administrator"]
    except:
        return False

# ✅ Reklama tekshiruvi va kanalga a'zo bo'lish majburiyati
async def reklama_aniqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    user = update.message.from_user
    text = update.message.text
    chat_id = update.message.chat_id
    msg_id = update.message.message_id

    if user.id in WHITELIST or (user.username and user.username in WHITELIST):
        return

# 2. TUN REJIMI (lekin adminlar va guruh egalari uchun emas)
        if TUN_REJIMI:
            try:
                member = await context.bot.get_chat_member(chat_id, user.id)
                if member.status not in ("administrator", "creator"):
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    return
            except:
                # Xatolik bo‘lsa, xabarni o‘chir
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                return

    if not await kanal_tekshir(update):
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        keyboard = [[
            InlineKeyboardButton("✅ Men a’zo bo‘ldim", callback_data="kanal_azo")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {user.first_name}, siz {KANAL_USERNAME} kanalga a’zo emassiz!",
            reply_markup=reply_markup)
        return

    if re.search(r"(http|www\\.|t\\.me/|@|reklama|reklam)", text, re.IGNORECASE):
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {user.first_name}, guruhda reklama taqiqlangan.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]])
        )

# ✅ Guruhga kirgan yoki chiqqan foydalanuvchilar xabarini o‘chirish
async def welcome_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.delete()

# ✅ /id faqat private chatda
async def id_berish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return
    user = update.message.from_user
    await update.message.reply_text(
        f"🆔 {user.first_name}, sizning Telegram ID’ingiz: {user.id}",
        parse_mode="Markdown")

# ✅ /kanal
async def kanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    global KANAL_USERNAME
    if context.args:
        KANAL_USERNAME = context.args[0]
        await update.message.reply_text(
            f"📢 Kanalga a’zo bo‘lish majburiy: {KANAL_USERNAME}")

# ✅ /kanaloff
async def kanaloff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    global KANAL_USERNAME
    KANAL_USERNAME = None
    await update.message.reply_text("🚫 Kanalga a’zo bo‘lish talabi o‘chirildi.")

# ✅ /ruxsat
async def ruxsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    if update.message.reply_to_message is not None:
        user_id = update.message.reply_to_message.from_user.id
        await update.message.reply_text("✅ Ruxsat berildi.")

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    FOYDALANUVCHILAR.add(update.effective_user.id)
    keyboard = [[
        InlineKeyboardButton("➕ Guruhga qo‘shish",
                             url=f"https://t.me/{context.bot.username}?startgroup=start")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "<b>Salom👋</b>\n"
        "Men reklamalarni, ssilkalani guruhlarda <b>o‘chirib</b> <b>beraman</b>, profilingiz <b>ID</b> gizni aniqlab beraman, majburiy kanalga a'zo bo‘lishni tekshiraman va boshqa ko‘plab yordamlar beraman 👨🏻‍✈\n\n"
        "Bot komandalari <b>qo'llanmasi</b> 👉 /help\n\n"
        "Faqat Ishlashim uchun guruhingizga qo‘shib, <b>ADMIN</b> <b>berishingiz</b> <b>kerak</b> 🙂\n\n"
        "Murojaat uchun👉 @Devona0107",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# ✅ /users
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    await update.message.reply_text(f"📊 Botdan foydalangan foydalanuvchilar soni: {len(FOYDALANUVCHILAR)} ta")

# ✅ /kanal_azo tugmasi uchun callback
async def kanal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    if not KANAL_USERNAME:
        await query.edit_message_text("⚠️ Kanal sozlanmagan.")
        return
    try:
        member = await context.bot.get_chat_member(KANAL_USERNAME, user.id)
        if member.status in ["member", "administrator", "creator"]:
            await context.bot.restrict_chat_member(
                chat_id=query.message.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=True,
                                            can_send_media_messages=True,
                                            can_send_polls=True,
                                            can_send_other_messages=True,
                                            can_add_web_page_previews=True,
                                            can_invite_users=True))
            await query.edit_message_text("✅ A’zo bo‘lganingiz tasdiqlandi. Endi guruhda yozishingiz mumkin.")
        else:
            await query.edit_message_text("❌ Hali kanalga a’zo emassiz.")
    except:
        await query.edit_message_text("⚠️ Tekshirishda xatolik. Kanal username noto‘g‘ri bo‘lishi yoki bot kanalga a’zo bo‘lmasligi mumkin.")

# ✅ /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📌 <b>Buyruqlar ro‘yxati</b>\n\n"
        "🔹 <b>/id</b> - Акканунтингиз ID сини аниқлайди.\n"
        "🔹 <b>/tun</b> - Барча ёзилган хабарлар автоматик ўчирилади.\n"
        "🔹 <b>/tunoff</b> - Тун режими ўчирилади.\n"
        "🔹 <b>/ruxsat</b> - Ответ ёки @ орқали белгиланган одамга рухсат берилади.\n"
        "🔹 <b>/kanal @username</b> - Каналга азо бўлишга мажбурлайди.\n"
        "🔹 <b>/kanaloff</b> - Каналга мажбур азо бўлишни ўчиради.\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")

import asyncio

app = ApplicationBuilder().token(TOKEN).build()

async def reklama_va_soz_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        text = update.message.text
        chat_id = update.message.chat_id
        msg_id = update.message.message_id

        if not text or not user:
            return

        # 1. WHITELIST tekshiruv
        if user.id in WHITELIST or (user.username and user.username in WHITELIST):
            return

        # 2. TUN REJIMI
        if TUN_REJIMI:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            return

        # 3. KANALGA A’ZO TEKSHIRISH
        if not await kanal_tekshir(update):
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            keyboard = [[InlineKeyboardButton("✅ Men a’zo bo‘ldim", callback_data="kanal_azo")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, siz {KANAL_USERNAME} kanalga a’zo emassiz!",
                reply_markup=reply_markup)
            return

        # 4. REKLAMA so‘zlari
        if re.search(r"(http|www\.|t\.me/|@|reklama|reklam)", text, re.IGNORECASE):
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, guruhda reklama taqiqlangan.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]])
            )
            return

        # 5. SO‘KINISH SO‘ZLARI
        text_lower = text.lower()
        for soz in UYAT_SOZLAR:
            if soz in text_lower:
                await update.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ {user.first_name}, guruhda so‘kinish taqiqlangan. Iltimos, odobli bo‘ling!"
                )
                break

    except Exception as e:
        print(f"[Xatolik] reklama_va_soz_filtri: {e}")


app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("users", users))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("id", id_berish))
app.add_handler(CommandHandler("kanal", kanal))
app.add_handler(CommandHandler("kanaloff", kanaloff))
app.add_handler(CommandHandler("ruxsat", ruxsat))
app.add_handler(CommandHandler("tun", lambda u, c: tun(u, c)))
app.add_handler(CommandHandler("tunoff", lambda u, c: tunoff(u, c)))
app.add_handler(CallbackQueryHandler(kanal_callback, pattern="^kanal_azo$"))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_goodbye))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, welcome_goodbye))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reklama_va_soz_filtri))

async def tun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    TUN_REJIMI = True
    await update.message.reply_text("🌙 Tun rejimi yoqildi. Endi barcha xabarlar o‘chiriladi.")

async def tunoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    TUN_REJIMI = False
    await update.message.reply_text("🌤 Tun rejimi o‘chirildi.")

async def set_commands():
    await app.bot.set_my_commands(commands=[
        BotCommand("help", "Bot qo'llanmasi"),
        BotCommand("id", "Sizning ID’ingizni ko‘rsatadi"),
        BotCommand("tun", "Tun rejimini yoqish"),
        BotCommand("tunoff", "Tun rejimini o‘chirish"),
        BotCommand("kanal", "Majburiy kanalga a'zo bo'lish"),
        BotCommand("kanaloff", "Majburiy kanalga a'zo bo'lishni o'chirish"),
        BotCommand("ruxsat", "Odamga barcha ruxsatlar berish"),
    ], scope=BotCommandScopeAllPrivateChats())

async def botni_ishga_tushur():
    await set_commands()
    print("✅ Bot ishga tushdi...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    start_web()
    asyncio.get_event_loop().run_until_complete(botni_ishga_tushur())



# ✅ Reklama va so‘kinish filtrini birlashtirilgan holda tekshiruvchi handler
