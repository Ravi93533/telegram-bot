from telegram import Chat, Message, Update, BotCommand, BotCommandScopeAllPrivateChats, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters

import threading
import os
import re
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Flask

# --- New (Postgres) ---
import asyncio
import json
from typing import List, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None  # handled below with a log warning


# ---------------------- Linked channel helpers ----------------------
def _extract_forward_origin_chat(msg: Message):
    fo = getattr(msg, "forward_origin", None)
    if fo is not None:
        chat = getattr(fo, "chat", None) or getattr(fo, "from_chat", None)
        if chat is not None:
            return chat
    return getattr(msg, "forward_from_chat", None)


# ---- Linked channel cache helpers (added) ----
_GROUP_LINKED_ID_CACHE: dict[int, int | None] = {}

async def _get_linked_id(chat_id: int, bot) -> int | None:
    """Fetch linked_chat_id reliably using get_chat (cached)."""
    if chat_id in _GROUP_LINKED_ID_CACHE:
        return _GROUP_LINKED_ID_CACHE[chat_id]
    try:
        chat = await bot.get_chat(chat_id)
        linked_id = getattr(chat, "linked_chat_id", None)
        _GROUP_LINKED_ID_CACHE[chat_id] = linked_id
        return linked_id
    except Exception:
        _GROUP_LINKED_ID_CACHE[chat_id] = None
        return None

async def is_linked_channel_autoforward(msg: Message, bot) -> bool:
    """
    TRUE faqat guruhning bog'langan kanalidan avtomatik forward bo'lgan postlar uchun.
    - msg.is_automatic_forward True
    - get_chat(chat_id).linked_chat_id mavjud
    - va (sender_chat.id == linked_id) yoki (forward_origin chat.id == linked_id)
    - origin yashirilgan bo‘lsa ham fallback True (is_automatic_forward bo‘lsa)
    """
    try:
        if not getattr(msg, "is_automatic_forward", False):
            return False
        linked_id = await _get_linked_id(msg.chat_id, bot)
        if not linked_id:
            return False
        sc = getattr(msg, "sender_chat", None)
        if sc and getattr(sc, "id", None) == linked_id:
            return True
        fwd_chat = _extract_forward_origin_chat(msg)
        if fwd_chat and getattr(fwd_chat, "id", None) == linked_id:
            return True
        # Fallback: origin yashirilgan bo‘lishi mumkin
        return True
    except Exception:
        return False


# ---------------------- Small keep-alive web server ----------------------
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot ishlayapti!"

def run_web():
    app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))

def start_web():
    threading.Thread(target=run_web, daemon=True).start()


# ---------------------- Config ----------------------
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"

WHITELIST = {165553982, "Yunus1995"}
TUN_REJIMI = False
KANAL_USERNAME = None

MAJBUR_LIMIT = 0
FOYDALANUVCHI_HISOBI = defaultdict(int)
RUXSAT_USER_IDS = set()
BLOK_VAQTLARI = {}  # (chat_id, user_id) -> until_datetime (UTC)

FULL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)

BLOCK_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_invite_users=True,
)

UYATLI_SOZLAR = {"am", "ammisan", "ammislar", "ammislar?", "ammisizlar", "ammisizlar?", "amsan", "ammisan?", "amlar", "amlatta", "amyalaq", "amyalar", "amyaloq", "amxor", "am yaliman", "am yalayman", "am latta", "aminga",
"aminga ske", "aminga sikay", "buyingdi ami", "buyingdi omi", "buyingni ami", "buyindi omi", "buynami", "biyindi ami", "blya", "biyundiami", "blyat", "buynami", "buyingdi omi", "buyingni ami",
"buyundiomi", "dalbayob", "dalbayobmisan", "dalbayoblar", "dalbayobmisan?", "debil", "dolboyob", "durak", "fuck", "fakyou", "fuckyou", "foxisha", "foxishasan", "foxishamisan?", "foxishalar", "fohisha", "fohishasan", "fohishamisan?",
"fohishalar", "gandon", "g'ar", "gandonmisan", "gandonmisan?", "gandonlar", "haromi", "huy", "haromilar", "horomi", "horomilar", "idinnaxxuy", "idinaxxuy", "idin naxuy", "idin naxxuy", "isqirt", "isqirtsan", "isqirtlar", "jalap", "jalaplar",
"jalapsan", "jalapkot", "jalapkoz", "kot", "kotmislar", "kotmislar?", "kotmisizlar", "kutagim", "kotmisizlar?", "kotlar", "kotak", "kotmisan", "kotmisan?", "kotsan", "ko'tsan", "ko'tmisan", "ko't", "ko'tlar", "kotinga ske", "kotinga sikay", "kotingaske", "kotagim", "kotinga", "ko'tinga",
"kotingga", "kotvacha", "ko'tak", "lanati", "lanat", "lanatilar", "lanatisan", "mudak", "naxxuy", "og'zingaskay", "og'zinga skey", "ogzinga skey", "og'zinga skay", "ogzingaskay", "otti qotagi", "otni qotagi", "horomilar",
"huyimga", "huygami", "otti qo'tag'i", "ogzinga skay", "onagniomi", "onagni omi", "onangniami", "onagni ami", "pashol naxuy", "pasholnaxuy", "padarlanat", "padarlanatlar", "padarlanatsan", "pasholnaxxuy", "pidor",
"poshol naxxuy", "posholnaxxuy", "poxxuy", "poxuy", "qanjik", "qanjiq", "qanjiqsan", "qanjiqlar", "qonjiq", "qotaq", "qotaqlar", "qotaqsan", "qotaqmisan", "qotaqxor", "qo'taq", "qo'taqxo'r", "chochoq", "chochaq",
"qotagim", "qo'tag'im", "qotoqlar", "qo'toqlar", "qotag'im", "qotoglar", "qo'tog'lar", "qotagim", "skiy", "skay", "sikey", "sik", "skaman", "sikaman", "skasizmi", "sikasizmi", "sikay", "sikalak", "skishaman", "skishamiz",
"skishamizmi?", "sikishaman", "sikishamiz", "skey", "sikish", "sikishish", "skay", "soska", "suka", "sukalar", "tashak", "tashaklar", "tashaq", "tashaqlar", "toshoq", "toshoqlar", "toshok", "xuy", "xuramilar", "xuy",
"xuyna", "xaromi", "xoramilar", "xoromi", "xoromilar", "g'ar", "ам", "аммисан", "аммислар", "аммислар?", "аммисизлар", "аммисизлар?", "амсан", "аммисан?", "амлар", "амлатта", "амялақ", "амялар", "амялоқ", "амхор", "ам ялиман", "ам ялайман", "ам латта", "аминга",
"аминга ске", "аминга сикай", "буйингди ами", "буйингди оми", "буйингни ами", "буйинди оми", "буйнами", "бийинди ами", "бля", "биюндиами", "блят", "буйнами", "буйингди оми", "буйингни ами",
"буюндиоми", "далбаёб", "далбаёбмисан", "далбаёблар", "далбаёбмисан?", "дебил", "долбоёб", "дурак", "фуcк", "факёу", "фуcкёу", "фохиша", "фохишасан", "фохишамисан?", "фохишалар", "фоҳиша", "фоҳишасан", "фоҳишамисан?",
"фохишалар", "гандон", "гандонмисан", "гандонмисан?", "гандонлар", "ҳароми", "ҳуй", "ҳаромилар", "ҳороми", "ҳоромилар", "идиннаххуй", "идинаххуй", "идин нахуй", "идин наххуй", "исқирт", "исқиртсан", "исқиртлар", "жалап", "жалаплар",
"жалапсан", "жалапкот", "жалапкоз", "кот", "котмислар", "котмислар?", "котmisizlar", "kutagim", "kotlar", "kotak", "kotmisan", "kotmisan?", "kot", "ko't", "ko'tlar", "ko'tak", "ko't", "ko'tlar", "kotingga", "ko'tak", "kotingga", "kotvacha", "ko'tak",
"lanati", "lanat", "lanatilar", "lanatisan", "mudak", "naxxuy", "og'zingaskay", "og'zinga", "og'zinga skay", "onagniomi", "onagni", "onangniami", "onagni", "pasholnaxuy", "pasholnaxxuy", "pidor",
"posholnaxxuy", "poxuy", "qanjik", "qanjiq", "qanjiqsan", "qanjiqlar", "qotaq", "qotaqlar", "qotaqsan", "qotaqmisan", "qotaqxor", "qo'taq", "chochoq", "chochaq",
"qotagim", "qotoglar", "qo'tog'lar", "qotagim", "skiy", "skay", "sikey", "sik", "skaman", "sikaman", "skasizmi", "sikasizmi", "sikay", "sikalak", "skishaman", "skishamiz",
"sikishaman", "sikishamiz", "skey", "sikish", "sikishish", "skay", "soska", "suka", "sukalar", "tashak", "tashaklar", "toshoq", "toshoqlar", "toshok", "xuy", "xuy", "xuramilar", "xuy", "xuyna", "xaromi", "xoramilar", "xoromi", "xoromilar"}

async def dm_upsert_user(user):
    """Add/update a user to dm_users (Postgres if available, else JSON)."""
    global DB_POOL
    if user is None:
        return
    if DB_POOL:
        try:
            async with DB_POOL.acquire() as con:
                await con.execute(
                    """
                    INSERT INTO dm_users (user_id, username, first_name, last_name, is_bot, language_code, last_seen)
                    VALUES ($1,$2,$3,$4,$5,$6, now())
                    ON CONFLICT (user_id) DO UPDATE SET
                        username=EXCLUDED.username,
                        first_name=EXCLUDED.first_name,
                        last_name=EXCLUDED.last_name,
                        is_bot=EXCLUDED.is_bot,
                        language_code=EXCLUDED.language_code,
                        last_seen=now();
                    """,
                    user.id, user.username, user.first_name, user.last_name, user.is_bot, getattr(user, "language_code", None)
                )
        except Exception as e:
            log.warning(f"dm_upsert_user(DB) xatolik: {e}")
    else:
        add_chat_to_subs_fallback(user)

async def dm_all_ids() -> List[int]:
    global DB_POOL
    if DB_POOL:
        try:
            async with DB_POOL.acquire() as con:
                rows = await con.fetch("SELECT user_id FROM dm_users;")
            return [r["user_id"] for r in rows]
        except Exception as e:
            log.warning(f"dm_all_ids(DB) xatolik: {e}")
            return []
    else:
        return list(_load_ids(SUB_USERS_FILE))

async def dm_remove_user(user_id: int):
    global DB_POOL
    if DB_POOL:
        try:
            async with DB_POOL.acquire() as con:
                await con.execute("DELETE FROM dm_users WHERE user_id=$1;", user_id)
        except Exception as e:
            log.warning(f"dm_remove_user(DB) xatolik: {e}")
    else:
        remove_chat_from_subs_fallback(user_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_chat.type == 'private':
            await dm_upsert_user(update.effective_user)
    except Exception as e:
        log.warning(f"/start dm_upsert_user xatolik: {e}")
    kb = [[InlineKeyboardButton("➕ Guruhga qo‘shish", url=admin_add_link(context.bot.username))]]
    await update.effective_message.reply_text(
        "<b>САЛОМ👋</b>\n"
        "Мен барча рекламаларни, ссилкалани ва кирди чиқди хабарларни ҳамда ёрдамчи ботлардан келган рекламаларни гуруҳлардан <b>ўчириб</b> <b>тураман</b>\n\n"
        "Профилингиз <b>ID</b> гизни аниқлаб бераман\n\n"
        "Мажбурий гурухга одам қўштираман ва каналга аъзо бўлдираман (қўшмаса ёзолмайди) ➕\n\n"
        "18+ уятли сўзларни ўчираман ва бошқа кўплаб ёрдамлар бераман 👨🏻‍✈\n\n"
        "Ботнинг ўзи ҳам хечқандай реклама ёки ҳаволалар <b>ТАРҚАТМАЙДИ</b> ⛔\n\n"
        "Бот командалари <b>қўлланмаси</b> 👉 /help\n\n"
        "Фақат ишлашим учун гуруҳингизга қўшиб, <b>ADMIN</b> <b>беришингиз</b> <b>керак</b> 🙂\n\n"
        "Мурожаат ва саволлар бўлса 👉 @Devona0107 \n\n"
        "Сиздан фақатгина хомий каналимизга аъзолик 👉 <b>@SOAuz</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📌 <b>БОТ ҚЎЛЛАНМАЛАРИ</b>\n\n"
        "🔹 <b>/id</b> - Аккаунтингиз ID сини кўрсатади.\n\n"
        "📘<b>ЁРДАМЧИ БУЙРУҚЛАР</b>\n"
        "🔹 <b>/tun</b> — Тун режими(шу дақиқадан гурухга ёзилган хабарлар автоматик ўчирилиб турилади).\n"
        "🔹 <b>/tunoff</b> — Тун режимини ўчириш.\n"
        "🔹 <b>/ruxsat</b> — (Ответит) орқали имтиёз бериш.\n\n"
        "👥<b>ГУРУХГА МАЖБУР ОДАМ ҚЎШТИРИШ ВА КАНАЛГА МАЖБУР АЪЗО БЎЛДИРИШ</b>\n"
        "🔹 <b>/kanal @username</b> — Мажбурий кўрсатилган каналга аъзо қилдириш.\n"
        "🔹 <b>/kanaloff</b> — Мажбурий каналга аъзони ўчириш.\n"
        "🔹 <b>/majbur [3–25]</b> — Гурухда мажбурий одам қўшишни ёқиш.\n"
        "🔹 <b>/majburoff</b> — Мажбурий қўшишни ўчириш.\n\n"
        "📈<b>ОДАМ ҚЎШГАНЛАРНИ ХИСОБЛАШ</b>\n"
        "🔹 <b>/top</b> — TOP одам қўшганлар.\n"
        "🔹 <b>/cleangroup</b> — Одам қўшганлар хисобини 0 қилиш.\n"
        "🔹 <b>/count</b> — Ўзингиз нечта қўшдингиз.\n"
        "🔹 <b>/replycount</b> — (Ответит) қилинган одам қўшганлар сони.\n"
        "🔹 <b>/cleanuser</b> — (Ответит) қилинган одам қўшган хисобини 0 қилиш.\n"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

async def id_berish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    await update.effective_message.reply_text(f"🆔 {user.first_name}, sizning Telegram ID’ingiz: {user.id}")

async def tun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    TUN_REJIMI = True
    await update.effective_message.reply_text("🌙 Tun rejimi yoqildi. Oddiy foydalanuvchi xabarlari o‘chiriladi.")

async def tunoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TUN_REJIMI
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    TUN_REJIMI = False
    await update.effective_message.reply_text("🌞 Tun rejimi o‘chirildi.")

async def ruxsat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    if not update.effective_message.reply_to_message:
        return await update.effective_message.reply_text("Iltimos, foydalanuvchi xabariga reply qiling.")
    uid = update.effective_message.reply_to_message.from_user.id
    RUXSAT_USER_IDS.add(uid)
    await update.effective_message.reply_text(f"✅ <code>{uid}</code> foydalanuvchiga ruxsat berildi.", parse_mode="HTML")

async def kanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    global KANAL_USERNAME
    if context.args:
        KANAL_USERNAME = context.args[0]
        await update.effective_message.reply_text(f"📢 Majburiy kanal: {KANAL_USERNAME}")
    else:
        await update.effective_message.reply_text("Namuna: /kanal @username")

async def kanaloff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    global KANAL_USERNAME
    KANAL_USERNAME = None
    await update.effective_message.reply_text("🚫 Majburiy kanal talabi o‘chirildi.")

def majbur_klaviatura():
    rows = [[3, 5, 7, 10, 12], [15, 18, 20, 25, 30]]
    keyboard = [[InlineKeyboardButton(str(n), callback_data=f"set_limit:{n}") for n in row] for row in rows]
    keyboard.append([InlineKeyboardButton("❌ BEKOR QILISH ❌", callback_data="set_limit:cancel")])
    return InlineKeyboardMarkup(keyboard)

async def majbur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    global MAJBUR_LIMIT
    if context.args:
        try:
            val = int(context.args[0])
            if not (3 <= val <= 30):
                raise ValueError
            MAJBUR_LIMIT = val
            await update.effective_message.reply_text(f"✅ Majburiy odam qo‘shish limiti: <b>{MAJBUR_LIMIT}</b>", parse_mode="HTML")
        except ValueError:
            await update.effective_message.reply_text("❌ Noto‘g‘ri qiymat. Ruxsat etilgan oraliq: <b>3–30</b>. Masalan: <code>/majbur 10</code>", parse_mode="HTML")
    else:
        await update.effective_message.reply_text("👥 Guruhda majburiy odam qo‘shishni nechta qilib belgilay? 👇\nQo‘shish shart emas — /majburoff", reply_markup=majbur_klaviatura())

async def on_set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.callback_query.answer("Faqat adminlar!", show_alert=True)
    q = update.callback_query
    await q.answer()
    data = q.data.split(":", 1)[1]
    global MAJBUR_LIMIT
    if data == "cancel":
        return await q.edit_message_text("❌ Bekor qilindi.")
    try:
        val = int(data)
        if not (3 <= val <= 30):
            raise ValueError
        MAJBUR_LIMIT = val
        await q.edit_message_text(f"✅ Majburiy limit: <b>{MAJBUR_LIMIT}</b>", parse_mode="HTML")
    except Exception:
        await q.edit_message_text("❌ Noto‘g‘ri qiymat.")

async def majburoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    global MAJBUR_LIMIT
    MAJBUR_LIMIT = 0
    await update.effective_message.reply_text("🚫 Majburiy odam qo‘shish o‘chirildi.")

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    if not FOYDALANUVCHI_HISOBI:
        return await update.effective_message.reply_text("Hali hech kim odam qo‘shmagan.")
    items = sorted(FOYDALANUVCHI_HISOBI.items(), key=lambda x: x[1], reverse=True)[:100]
    lines = ["🏆 <b>Eng ko‘p odam qo‘shganlar</b> (TOP 100):"]
    for i, (uid, cnt) in enumerate(items, start=1):
        lines.append(f"{i}. <code>{uid}</code> — {cnt} ta")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")

async def cleangroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    FOYDALANUVCHI_HISOBI.clear()
    RUXSAT_USER_IDS.clear()
    await update.effective_message.reply_text("🗑 Barcha foydalanuvchilar hisobi va imtiyozlar 0 qilindi.")

async def replycount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("Iltimos, kimning hisobini ko‘rmoqchi bo‘lsangiz o‘sha xabarga reply qiling.")
    uid = msg.reply_to_message.from_user.id
    cnt = FOYDALANUVCHI_HISOBI.get(uid, 0)
    await msg.reply_text(f"👤 <code>{uid}</code> {cnt} ta odam qo‘shgan.", parse_mode="HTML")

async def cleanuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return await update.effective_message.reply_text("⛔ Faqat adminlar.")
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("Iltimos, kimni 0 qilmoqchi bo‘lsangiz o‘sha foydalanuvchi xabariga reply qiling.")
    uid = msg.reply_to_message.from_user.id
    FOYDALANUVCHI_HISOBI[uid] = 0
    RUXSAT_USER_IDS.discard(uid)
    await msg.reply_text(f"🗑 <code>{uid}</code> foydalanuvchi hisobi 0 qilindi.", parse_mode="HTML")

async def on_grant_priv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat = q.message.chat if q.message else None
    user = q.from_user
    if not (chat and user):
        return await q.answer()
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("administrator", "creator"):
            return await q.answer("Faqat adminlar imtiyoz bera oladi!", show_alert=True)
    except Exception:
        return await q.answer("Tekshirishda xatolik.", show_alert=True)
    await q.answer()
    try:
        target_id = int(q.data.split(":", 1)[1])
    except Exception:
        return await q.edit_message_text("❌ Noto‘g‘ri ma'lumot.")
    RUXSAT_USER_IDS.add(target_id)
    await q.edit_message_text(f"🎟 <code>{target_id}</code> foydalanuvchiga imtiyoz berildi.", parse_mode="HTML")


# ---------------------- Setup ----------------------
async def set_commands(app):
    await app.bot.set_my_commands(
        commands=[
            BotCommand("start", "Bot haqida ma'lumot"),
            BotCommand("help", "Bot qo'llanmasi"),
            BotCommand("id", "Sizning ID’ingiz"),
            BotCommand("top", "TOP 100 ro‘yxati"),
            BotCommand("majbur", "Majburiy odam limitini (3–30) o‘rnatish"),
            BotCommand("majburoff", "Majburiy qo‘shishni o‘chirish"),
        ],
        scope=BotCommandScopeAllPrivateChats()
    )

async def init_db(app=None):
    """Create asyncpg pool and ensure tables exist. Also migrate JSON -> DB once."""
    global DB_POOL
    db_url = _get_db_url()
    if not db_url:
        log.warning("DATABASE_URL topilmadi; DM ro'yxati JSON faylga yoziladi (ephemeral).")
        return
    if asyncpg is None:
        log.error("asyncpg o'rnatilmagan. requirements.txt ga 'asyncpg' qo'shing.")
        return

    # FAQAT BIRTA O‘ZGARISH — SSL REQUIRE QO‘SHILDI
    DB_POOL = await asyncpg.create_pool(dsn=db_url, ssl="require", min_size=1, max_size=5)

    async with DB_POOL.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS dm_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_bot BOOLEAN DEFAULT FALSE,
                language_code TEXT,
                last_seen TIMESTAMPTZ DEFAULT now()
            );
            """
        )

    # Migrate from JSON (best-effort, only if DB empty)
    try:
        if DB_POOL:
            async with DB_POOL.acquire() as con:
                count_row = await con.fetchval("SELECT COUNT(*) FROM dm_users;")
            if count_row == 0 and os.path.exists(SUB_USERS_FILE):
                s = _load_ids(SUB_USERS_FILE)
                if s:
                    async with DB_POOL.acquire() as con:
                        async with con.transaction():
                            for cid in s:
                                try:
                                    cid_int = int(cid)
                                except Exception:
                                    continue
                                await con.execute(
                                    "INSERT INTO dm_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING;", cid_int
                                )
                    log.info(f"Migratsiya: JSON dan Postgresga {len(s)} ta ID import qilindi.")
    except Exception as e:
        log.warning(f"Migratsiya vaqtida xato: {e}")
    await init_db(app)
    await set_commands(app)

def main():
    start_web()
    app = ApplicationBuilder().token(TOKEN).build()
    app.post_init = post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

