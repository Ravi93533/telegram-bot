
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

from telegram import Update, BotCommand, BotCommandScopeAllPrivateChats, ChatPermissions
from telegram.ext import (CallbackQueryHandler, ApplicationBuilder,
                          CommandHandler, MessageHandler, filters,
                          ContextTypes, ChatMemberHandler)
import re
import os
import time
import logging
import asyncio

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ------------------ ADMIN ANIQLASH YORDAMCHI FUNKSIYALAR ------------------

async def is_admin(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not (chat and user):
        return False
    try:
        member = await chat.get_member(user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logging.warning(f"is_admin tekshiruvda xatolik: {e}")
        return False

async def is_privileged_message(msg, bot) -> bool:
    """
    Guruhdagi PRIVILEGED (creator/administrator) yozuvchilarga TRUE qaytaradi.
    Anonymous admin holati ham qo'llab-quvvatlanadi.
    """
    try:
        chat = msg.chat
        user = msg.from_user
        # 1) Anonymous admin (sender_chat == group chat)
        if getattr(msg, "sender_chat", None) and msg.sender_chat.id == chat.id:
            # Guruh nomi bilan yozilgan xabar — bu odatda anonym admin
            return True

        # 2) Oddiy admin/creator
        if user:
            member = await bot.get_chat_member(chat.id, user.id)
            if member.status in ("administrator", "creator"):
                return True
    except Exception as e:
        logging.warning(f"is_privileged_message xatolik: {e}")
    return False

TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"

# Statik WHITELIST saqlab qolamiz, lekin endi ADMINLAR DYNAMIC RUXSAT bilan avtomatik o‘tadi
WHITELIST = [165553982, "Yunus1995"]
TUN_REJIMI = False
KANAL_USERNAME = None
FOYDALANUVCHILAR = set()  # Bot foydalanuvchilari

async def kanal_tekshir(update: Update, bot) -> bool:
    global KANAL_USERNAME
    if not KANAL_USERNAME:
        return True
    try:
        user = update.effective_user
        member = await bot.get_chat_member(KANAL_USERNAME, user.id)
        return member.status in ["member", "creator", "administrator"]
    except Exception as e:
        logging.warning(f"kanal_tekshir xatolik: {e}")
        return False

# ✅ Reklama tekshiruvi va kanalga a'zo bo'lish majburiyati
async def reklama_aniqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ushbu funksiya hozirda ishlatilmayapti; asosiy logika quyi handlerda
    return

# So‘kinish so‘zlari ro‘yxati (o‘sha fayldan saqlab qoldik)
uyatli_sozlar = {"am", "qotaq", "kot", "tashak"}
# Kengaytirilgan ro‘yxat (o‘sha fayl bo‘yicha)
uyatli_sozlar = {"am", "amlar", "amlatta", "amyalaq", "amyalar", "amyaloq", "amxor", "am yaliman", "am yalayman", "am latta", "aminga", "aminga ske", "aminga sikay", 
    "asshole", "bastard", "biyundiami", "bitch", "blyat", "buynami", "buyingdi omi", "buyingni ami", "buyundiomi", "dalbayob", "damn", "debil", 
    "dick", "dolboyob", "durak", "eblan", "fuck", "fakyou", "fuckyou", "foxisha", "fohisha", "fucker", "gandon", "gandonlar", "haromi", "haromilar", "horomi", "hoy", "idinnaxxuy", "idin naxuy", "idin naxxuy", 
    "isqirt", "jalap", "kal", "kot", "kotlar", "kotak", "ko't", "ko'tlar", "kotinga ske", "kotinga sikay", "kotinga", "ko'tinga", "kotingga", "kotvacha", "ko'tak", 
    "lanati", "lax", "motherfucker", "mudak", "naxxuy", "og'zingaskay", "og'zinga skay", "ogzingaskay", "otti qotagi", "otni qotagi", "horomilar", 
    "otti qo'tag'i", "ogzinga skay", "onagniomi", "onangniami", "pashol naxuy", "padarlanat", "lanat", "pasholnaxxuy", "pidor", 
    "poshol naxxuy", "posholnaxxuy", "poxxuy", "poxuy", "qanjik", "qanjiq", "qonjiq", "qotaq", "qotaqxor", "qo'taq", "qo'taqxo'r", 
    "qotagim", "kotagim", "qo'tag'im", "qotoqlar", "qo'toqlar", "qotag'im", "qotoglar", "qo'tog'lar", "qo'tagim", "sik", "sikaman", "sikay", "sikalak", "sikish", "sikishish", "skay", 
    "slut", "soska", "suka", "tashak", "tashaq", "toshoq", "toshok", "xaromi", "xoramilar", "xoromi", "xoromilar", "ам", "амлар", "амлатта", "аминга", "амялак", "амялок", "амхўр", "амхур", "омин", "оминга", "ам ялиман", "ам ялайман", "искирт", "жалап", 
    "далбаёб", "долбоёб", "гандон", "гондон", "нахуй", "иди нахуй", "идин наххуй", "идиннаххуй", "кот", "котак", "кутагим", "қўтағим",
    "кут", "кутак", "кутлар", "кутингга", "кўт", "кўтлар", "кўтингга", "ланати", "нахуй", "наххуй", "огзинга скай", "огзингаскай", "онагниоми", "онагни оми",
    "онангниами", "онангни ами", "огзинга скей", "огзинга сикай", "отни кутаги", "пашол нахуй", "пашолнаххуй", "пидор", "пошол наххуй", 
    "похуй", "поххуй", "пошолнаххуй", "секис", "сикай", "сикаман", "сикиш", "сикишиш", "соска", "сука", "ташак", "ташақ", "тошок", 
    "тошоқ", "хароми", "ҳароми", "ҳороми", "қотақ", "ске", "ланат", "ланати", "падарланат", "қотақхор", "қўтақ", "ташақлар", "қўтоқлар", "кутак", "қўтақхўр", 
    "қанжик", "қанжиқ", "қонжиқ", "am", "amlatta", "amyalaq", "amyalar", "buÿingdi ami", "buyingdi omi", "buyingni ami", "buyindi omi", 
    "buynami", "biyindi ami", "skiy", "skay", "sikey", "sik", "kutagim", "skaman", "xuy", "xuramilar", "xuy", "xuyna", "skey"}

def matndan_sozlar_olish(matn):
    return re.findall(r"\b\w+\b", (matn or "").lower())

# ------------------ ASOSIY FILTR HANDLER ------------------
async def reklama_va_soz_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.message
        if not msg:
            return
        user = msg.from_user
        chat_id = msg.chat_id
        msg_id = msg.message_id

        text = msg.text or msg.caption or ""
        entities = msg.entities or msg.caption_entities or []

        logging.info(f"🔍 Keldi: user={getattr(user, 'id', None)}, text={text}")
        logging.info(f"📎 Forward? => from_chat={getattr(msg, 'forward_from_chat', None)}, sender_name={getattr(msg, 'forward_sender_name', None)}, sender_chat={getattr(msg, 'sender_chat', None)}")
        logging.info(f"🔗 Entities: {entities}")

        # 0) PRIVILEGED (creator/administrator/anonymous admin) va WHITELIST uchun FULL BYPASS
        privileged = await is_privileged_message(msg, context.bot)
        whitelisted = (user and (user.id in WHITELIST or (user.username and user.username in WHITELIST)))
        if privileged or whitelisted:
            logging.info("✅ Admin/Owner yoki WHITELIST — filtr bypass")
            return

        # 1) FORWARD xabarlar — taqiqlanadi
        if getattr(msg, "forward_from_chat", None) or getattr(msg, "forward_sender_name", None):
            logging.info("⛔ Forward xabar aniqlandi — o‘chirilmoqda")
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, forward qilingan xabar yuborish taqiqlangan!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]
                ])
            )
            return

        # 2) TUN REJIMI
        if TUN_REJIMI:
            logging.info("🌙 Tun rejimi: xabar o‘chirilmoqda (oddiy foydalanuvchi)")
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            return

        # 3) Kanalga a’zolik tekshiruvi (faqat oddiy foydalanuvchiga)
        if not await kanal_tekshir(update, context.bot):
            logging.info("📢 Kanalga a’zolik yo‘q — xabar o‘chirilmoqda")
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            keyboard = [[InlineKeyboardButton("✅ Men a’zo bo‘ldim", callback_data="kanal_azo")]]
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, siz {KANAL_USERNAME} kanalga a’zo emassiz!",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # 4) Yashirin ssilkalar va textdagi ssilkalar
        for ent in entities:
            if ent.type in ["text_link", "url", "mention"]:
                url = getattr(ent, "url", "") or ""
                if url and ("t.me" in url or "telegram.me" in url):
                    logging.info("🔗 Yashirin ssilka aniqlandi — o‘chirilmoqda")
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ {user.first_name}, yashirin ssilka yuborish taqiqlangan!",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]
                        ])
                    )
                    return

        if any(x in text for x in ["t.me", "telegram.me", "@", "www.", "https://youtu.be"]):
            logging.info("🔗 Matnda reklama ssilka — o‘chirilmoqda")
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, reklama yuborish taqiqlangan!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]
                ])
            )
            return

        # 5) Ochiq reklama so‘zlari
        if text and re.search(r"(http|www\.|t\.me/|@|reklama|reklam)", text, re.IGNORECASE):
            logging.info("🔗 Ochiq reklama topildi — o‘chirilmoqda")
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, reklama yuborish taqiqlangan!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]
                ])
            )
            return

        # 6) So‘kinish
        sozlar = matndan_sozlar_olish(text)
        if any(soz in uyatli_sozlar for soz in sozlar):
            logging.info("🤬 So‘kinish so‘zi topildi — o‘chirilmoqda")
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, guruhda so‘kinish taqiqlangan!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{context.bot.username}?startgroup=start")]
                ])
            )
            return

    except Exception as e:
        logging.error(f"[Xatolik] Filtrda: {e}")

# ------------------ QOLGAN KOMANDALAR (original strukturani saqlab) ------------------

async def welcome_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.delete()

async def id_berish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return
    user = update.message.from_user
    await update.message.reply_text(
        f"🆔 {user.first_name}, sizning Telegram ID’ingiz: {user.id}",
        parse_mode="Markdown")

async def kanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    global KANAL_USERNAME
    if context.args:
        KANAL_USERNAME = context.args[0]
        await update.message.reply_text(
            f"📢 Kanalga a’zo bo‘lish majburiy: {KANAL_USERNAME}")

async def kanaloff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    global KANAL_USERNAME
    KANAL_USERNAME = None
    await update.message.reply_text("🚫 Kanalga a’zo bo‘lish talabi o‘chirildi.")

async def ruxsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    if update.message.reply_to_message is not None:
        user_id = update.message.reply_to_message.from_user.id
        await update.message.reply_text("✅ Ruxsat berildi.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    FOYDALANUVCHILAR.add(update.effective_user.id)
    keyboard = [[
        InlineKeyboardButton("➕ Guruhga qo‘shish",
                             url=f"https://t.me/{context.bot.username}?startgroup=start")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "<b>Salom👋</b>\n"
        "Men reklamalarni, ssilkalani va kirdi chiqdi xabarlarni guruhlardan <b>o‘chirib</b> <b>beraman</b>, profilingiz <b>ID</b> gizni aniqlab beraman, majburiy kanalga a'zo bo‘ldiraman, 18+ uyatli so'zlarni o'chiraman va boshqa ko‘plab yordamlar beraman 👨🏻‍✈\n\n"
        "Bot komandalari <b>qo'llanmasi</b> 👉 /help\n\n"
        "Faqat Ishlashim uchun guruhingizga qo‘shib, <b>ADMIN</b> <b>berishingiz</b> <b>kerak</b> 🙂\n\n"
        "Murojaat uchun👉 @Devona0107",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    await update.message.reply_text(f"📊 Botdan foydalangan foydalanuvchilar soni: {len(FOYDALANUVCHILAR)} ta")

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
    except Exception as e:
        await query.edit_message_text("⚠️ Tekshirishda xatolik. Kanal username noto‘g‘ri bo‘lishi yoki bot kanalga a’zo bo‘lmasligi mumkin.")

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

# ------------------ APP va HANDLERLAR ------------------

app = ApplicationBuilder().token(TOKEN).build()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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

media_filters = (
    filters.TEXT |
    filters.PHOTO |
    filters.VIDEO |
    filters.Document.ALL |
    filters.ANIMATION |
    filters.VOICE |
    filters.VIDEO_NOTE
)
app.add_handler(MessageHandler(media_filters & (~filters.COMMAND), reklama_va_soz_filtri))

async def tun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
    TUN_REJIMI = True
    await update.message.reply_text("🌙 Tun rejimi yoqildi. Endi barcha xabarlar o‘chiriladi (admin/creator bundan mustasno).")

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
