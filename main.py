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


# ---- Linked channel cache helpers ----
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
    TRUE only for automatic forwards from a linked channel into the group.
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
        return True  # fallback
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

# So'kinish lug'ati (ASL RO‘YXAT TO‘LIQ SAQLANDI — siz yuborgan matn 1:1)
UYATLI_SOZLAR = {
    "am", "ammisan", "ammislar", "ammislar?", "ammisizlar", "ammisizlar?", "amsan", "ammisan?", "amlar",
    "amlatta", "amyalaq", "amyalar", "amyaloq", "amxor", "am yaliman", "am yalayman", "am latta", "aminga",
    "aminga ske", "aminga sikay", "buyingdi ami", "buyingdi omi", "buyingni ami", "buyindi omi", "buynami",
    "biyindi ami", "blya", "biyundiami", "blyat", "dalbayob", "dalbayobmisan", "dalbayoblar", "dalbayobmisan?",
    "debil", "dolboyob", "durak", "fuck", "fakyou", "fuckyou", "foxisha", "foxishasan", "foxishamisan?",
    "foxishalar", "fohisha", "fohishasan", "fohishamisan?", "fohishalar", "gandon", "g'ar", "gandonmisan",
    "gandonmisan?", "gandonlar", "haromi", "huy", "haromilar", "horomi", "horomilar", "idinnaxxuy", "idinaxxuy",
    "idin naxuy", "idin naxxuy", "isqirt", "isqirtsan", "isqirtlar", "jalap", "jalaplar", "jalapsan",
    "jalapkot", "jalapkoz", "kot", "kotmislar", "kotmislar?", "kotmisizlar", "kutagim", "kotlar", "kotak",
    "kotmisan", "kotmisan?", "kotsan", "ko'tsan", "ko'tmisan", "ko't", "ko'tlar", "kotingga", "ko'tak", "kotvacha",
    "lanati", "lanat", "lanatilar", "lanatisan", "mudak", "naxxuy", "og'zingaskay", "og'zinga skey",
    "ogzinga skey", "og'zinga skay", "ogzingaskay", "otti qotagi", "otni qotagi", "onagniomi", "onagni omi",
    "onangniami", "onagni ami", "pashol naxuy", "pasholnaxuy", "padarlanat", "padarlanatlar", "padarlanatsan",
    "pasholnaxxuy", "pidor", "poshol naxxuy", "posholnaxxuy", "poxxuy", "poxuy", "qanjik", "qanjiq",
    "qanjiqsan", "qanjiqlar", "qonjiq", "qotaq", "qotaqlar", "qotaqsan", "qotaqmisan", "qotaqxor", "qo'taq",
    "qo'taqxo'r", "chochoq", "chochaq", "qotagim", "qo'tag'im", "qotoqlar", "qo'toqlar", "qotoglar", "qo'tog'lar"
}

# Game/inline reklama kalit so'zlar/domenlar
SUSPECT_KEYWORDS = {"open game", "play", "game"}
SUSPECT_DOMAINS = {"t.me", "play", "gamee"}


# ---------------------- DB init & broadcast helpers ----------------------
def _get_db_url() -> Optional[str]:
    return os.getenv("DATABASE_URL")

async def init_db(app=None):
    global DB_POOL
    db_url = _get_db_url()
    if not db_url:
        return
    if asyncpg is None:
        return
    # === FAQAT SHU JOYGA SSL QO‘SHILDI ===
    DB_POOL = await asyncpg.create_pool(dsn=db_url, ssl="require", min_size=1, max_size=5)

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

async def post_init(app):
    await init_db(app)
    await set_commands(app)

def main():
    start_web()
    app = ApplicationBuilder().token(TOKEN).build()
    app.post_init = post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
