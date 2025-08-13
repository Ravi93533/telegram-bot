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
from telegram.ext import (
    CallbackQueryHandler,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    filters,
)
import re
import os
import asyncio

# ===================== Global holat =====================
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

# ===================== Yordamchi funksiyalar =====================
ZERO_WIDTH = "".join([
    "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",  # zero-width
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # bidi
    "\u2060"  # word joiner
])

def strip_invisible_chars(s: str) -> str:
    if not s:
        return s
    return s.translate({ord(ch): None for ch in ZERO_WIDTH})

def has_embedded_tg_link(text: str) -> bool:
    """
    Telegram kanal/guruh havolalarini, hatto "so'z ichiga" biriktirilgan yoki
    bo'lib-bo'lib yozilgan ko'rinishlarini ham ushlaydi.
    Masalan: t.me/kanal, t . me/kanal, t[dot]me/kanal, telegram.me/joinchat, tg://join?,
             t•me/kanal, t_me/kanal, tme/kanal (nuqtasiz yozilgan) va hokazo.
    Shuningdek, @username (kanal/guruh niki) holati ham tekshiriladi.
    """
    if not text:
        return False

    raw = text
    s = strip_invisible_chars(raw).lower()

    # 1) Oddiy va obfuskatsiyalangan t.me/** patternlari
    #    t [noalpha]* .? [noalpha]* me [noalpha]*/ => t.me/
    tg_core = r"t\s*[^a-z0-9]*\.?\s*[^a-z0-9]*me\s*[/\\]"
    if re.search(tg_core, s, flags=re.IGNORECASE):
        return True

    # 2) telegram.me/** va telegram.dog/** variantlari (obfuskatsiya bilan)
    tg_telegram_me = r"tele\s*gram\s*[^a-z0-9]*\.?\s*[^a-z0-9]*me\s*[/\\]"
    tg_dog = r"tele\s*gram\s*[^a-z0-9]*\.?\s*[^a-z0-9]*dog\s*[/\\]"
    if re.search(tg_telegram_me, s, re.IGNORECASE) or re.search(tg_dog, s, re.IGNORECASE):
        return True

    # 3) joinchat / +invite formatlari
    if re.search(r"(join\s*chat|joinchat|\+[a-z0-9_\-]{10,})", s, re.IGNORECASE):
        return True

    # 4) tg://join? va shunga o'xshash
    if re.search(r"tg\s*[:][/][/]\s*join", s, re.IGNORECASE):
        return True

    # 5) "t dot me" ko'rinisi (t dot me / kanal)
    if re.search(r"t\s*(?:dot|\.)\s*me\s*[/\\]", s, re.IGNORECASE):
        return True

    # 6) "tme/kanal" (nuqtasiz, birga yozilgan) — juda agressiv emas, lekin tekshiramiz
    #    faqat "tme/" boshlanishiga yaqin joyda
    if re.search(r"\btme\s*[/\\]", s, re.IGNORECASE):
        return True

    # 7) @username — kanal/guruh niki. Email bilan adashmaslik uchun oddiy filtr.
    #    (oldida harf/rqam bo'lmasa, keyin kamida 4 ta belgi bo'lsa)
    if re.search(r"(^|[^a-z0-9_])@[a-z0-9_]{4,}", s, re.IGNORECASE):
        return True

    # 8) Har qanday to'g'ridan-to'g'ri http/https/www havolalar
    if re.search(r"(https?[:][/][/]|www\.)", s, re.IGNORECASE):
        return True

    return False

async def kanal_tekshir(update: Update):
    global KANAL_USERNAME
    if not KANAL_USERNAME:
        return True
    try:
        user = update.message.from_user
        member = await update.get_bot().get_chat_member(KANAL_USERNAME, user.id)
        return member.status in ["member", "creator", "administrator"]
    except Exception:
        return False

# ===================== Handlers =====================
async def reklama_va_soz_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.message
        if not msg:
            return

        user = msg.from_user
        text = msg.text or msg.caption or ""  # caption bilan ham ishlaydi
        chat_id = msg.chat_id
        msg_id = msg.message_id

        if not text or not user:
            return

        # 1. WHITELIST
        if user.id in WHITELIST or (user.username and user.username in WHITELIST):
            return

        # 2. TUN REJIMI
        if TUN_REJIMI:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            return

        # 3. KANALGA A'ZO TEKSHIRISH
        if not await kanal_tekshir(update):
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            keyboard = [[
                # Faqat tasdiqlash tugmasi. Kanal ssilkasi ochiq aytilmaydi.
                # Adminlar /kanal @username orqali o'rnatadi.
                # Foydalanuvchi a'zo bo'lib, tekshiruvni bosadi.
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            ]]
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Men a’zo bo‘ldim", callback_data="kanal_azo")]])
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, siz {KANAL_USERNAME} kanalga a’zo emassiz!",
                reply_markup=reply_markup)
            return

        # 4. HAR QANDAY TELEGRAM/URL/OBFUSKATSIYALANGAN HAVOLANI ANIQLASH
        if has_embedded_tg_link(text):
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {user.first_name}, guruhda reklama va havolalar taqiqlangan.",
            )
            return

        # 5. Qo'shimcha reklama so'zlari (ixtiyoriy)
        # if re.search(r"(reklama|reklam)", text, re.IGNORECASE):
        #     await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        #     await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {user.first_name}, guruhda reklama taqiqlangan.")
        #     return

    except Exception as e:
        print(f"[Xatolik] reklama_va_soz_filtri: {e}")

async def welcome_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

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
        await update.message.reply_text(f"📢 Kanalga a’zo bo‘lish majburiy: {KANAL_USERNAME}")

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
        # Bu yerda real "ruxsat" mantiqini amalga oshirish mumkin, hozircha faqat javob
        await update.message.reply_text("✅ Ruxsat berildi.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    FOYDALANUVCHILAR.add(update.effective_user.id)
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[
        InlineKeyboardButton(
            "➕ Guruhga qo‘shish",
            url=f"https://t.me/{context.bot.username}?startgroup=start"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "<b>Salom👋</b>\n"
        "Men reklamalarni, ssilkalani guruhlarda <b>o‘chirib</b> <b>beraman</b>, profilingiz <b>ID</b> gizni aniqlab beraman, majburiy kanalga a'zo bo‘lishni tekshiraman va boshqa ko‘plab yordamlar beraman 👨🏻‍✈\n\n"
        "Bot komandalari <b>qo'llanmasi</b> 👉 /help\n\n"
        "Faqat Ishlashim uchun guruhingizga qo‘shib, <b>ADMIN</b> <b>berishingiz</b> <b>kerak</b> 🙂\n\n"
        "Murojaat uchun👉 @Devona0107",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    await update.message.reply_text(f"📊 Botdan foydalangan foydalanuvchilar soni: {len(FOYDALANUVCHILAR)} ta")

async def kanal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_invite_users=True
                ),
            )
            await query.edit_message_text("✅ A’zo bo‘lganingiz tasdiqlandi. Endi guruhda yozishingiz mumkin.")
        else:
            await query.edit_message_text("❌ Hali kanalga a’zo emassiz.")
    except Exception:
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

# ===================== App & Handlers ro'yxati =====================
app = ApplicationBuilder().token(TOKEN).build()

# Komandalar
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("users", users))
app.add_handler(CommandHandler("help", help))
app.add_handler(CommandHandler("id", id_berish))
app.add_handler(CommandHandler("kanal", kanal))
app.add_handler(CommandHandler("kanaloff", kanaloff))
app.add_handler(CommandHandler("ruxsat", ruxsat))

# Tun rejimi komandasi
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

app.add_handler(CommandHandler("tun", tun))
app.add_handler(CommandHandler("tunoff", tunoff))

# Callback
app.add_handler(CallbackQueryHandler(kanal_callback, pattern="^kanal_azo$"))

# Status xabarlarini o'chirish
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_goodbye))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, welcome_goodbye))

# Matn va CAPTION (foto/video/dokument osti yozuvlari) filtri
# TEXT
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reklama_va_soz_filtri))
# CAPTION bilan keladigan media turlari
app.add_handler(MessageHandler((filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.DOCUMENT) & filters.Caption, reklama_va_soz_filtri))

# ===================== Ishga tushirish =====================
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
