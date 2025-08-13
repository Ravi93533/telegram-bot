import threading
from flask import Flask
import os
import re
import asyncio
from typing import List

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
)

# ---------------- Web keepalive (Render/Replit) ----------------
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return 'Bot ishlayapti!'

def run_web():
    app_flask.run(host='0.0.0.0', port=8080)

def start_web():
    threading.Thread(target=run_web, daemon=True).start()

# ---------------- Config ----------------
TOKEN = os.getenv("TOKEN") or "YOUR_TOKEN_HERE"
WHITELIST = set()  # {user_id, 'username'}

KANAL_USERNAME = None
TUN_REJIMI = False

# ---------------- Helpers ----------------
ZERO_WIDTH = "".join([
    "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2060"
])

def strip_invisible_chars(s: str) -> str:
    if not s:
        return s
    return s.translate({ord(ch): None for ch in ZERO_WIDTH})

TG_PATTERNS = [
    r"t\s*[^a-z0-9]*\.?\s*[^a-z0-9]*me\s*[/\\]",     # t.me or t . me
    r"tele\s*gram\s*[^a-z0-9]*\.?\s*[^a-z0-9]*me\s*[/\\]",  # telegram.me
    r"tele\s*gram\s*[^a-z0-9]*\.?\s*[^a-z0-9]*dog\s*[/\\]", # telegram.dog
    r"t\s*(?:dot|\.)\s*me\s*[/\\]",                  # t dot me
    r"\btme\s*[/\\]",                                # tme/
    r"(join\s*chat|joinchat|\+[a-z0-9_\-]{10,})",    # joinchat/+invite
    r"tg\s*[:][/][/]\s*join",                        # tg://join
    r"(^|[^a-z0-9_])@[a-z0-9_]{4,}",                # @username
    r"(https?[:][/][/]|www\.)"                       # any url
]

TG_REGEXES = [re.compile(p, re.IGNORECASE) for p in TG_PATTERNS]

def text_has_tg_link(text: str) -> bool:
    if not text:
        return False
    raw = text
    s = strip_invisible_chars(raw).lower()
    for rgx in TG_REGEXES:
        if rgx.search(s):
            return True
    # Uppercase channel-like names
    if re.search(r"\b[A-Z_]{5,}\b", raw):
        return True
    return False

def extract_entities_urls(msg) -> List[str]:
    urls = []
    try:
        for e in (msg.entities or []):
            t = getattr(e, "type", None)
            if t == "url" and msg.text:
                urls.append(msg.text[e.offset:e.offset+e.length])
            elif t == "text_link":
                urls.append(getattr(e, "url", ""))
            elif t == "mention" and msg.text:
                urls.append(msg.text[e.offset:e.offset+e.length])
        for e in (msg.caption_entities or []):
            t = getattr(e, "type", None)
            if t == "url" and msg.caption:
                urls.append(msg.caption[e.offset:e.offset+e.length])
            elif t == "text_link":
                urls.append(getattr(e, "url", ""))
            elif t == "mention" and msg.caption:
                urls.append(msg.caption[e.offset:e.offset+e.length])
    except Exception:
        pass
    return urls

def is_promo_url(u: str) -> bool:
    if not u: 
        return False
    u = u.lower()
    return ("t.me" in u) or ("telegram.me" in u) or ("tg://" in u) or ("joinchat" in u)

def group_add_btn(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Guruhga qo‘shish", url=f"https://t.me/{bot_username}?startgroup=start")
    ]])

# ---------------- Core Filter ----------------
async def reklama_va_soz_filtri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # commandsni o'tkazamiz
    if msg.entities:
        for e in msg.entities:
            if getattr(e, "type", "") == "bot_command":
                return

    user = msg.from_user
    chat_id = msg.chat_id
    mid = msg.message_id

    # Whitelist
    if user and (user.id in WHITELIST or (user.username and user.username in WHITELIST)):
        return

    # Night mode
    if TUN_REJIMI:
        try: await context.bot.delete_message(chat_id, mid)
        except: pass
        return

    # Channel membership (optional)
    if KANAL_USERNAME:
        try:
            member = await context.bot.get_chat_member(KANAL_USERNAME, user.id)
            if member.status not in ("member", "administrator", "creator"):
                try: await context.bot.delete_message(chat_id, mid)
                except: pass
                await context.bot.send_message(chat_id, f"⚠️ {user.first_name}, {KANAL_USERNAME} kanalga a’zo bo‘ling.", reply_markup=group_add_btn(context.bot.username))
                return
        except Exception:
            pass

    # 1) Forwarded from channel/group
    if msg.forward_from_chat and msg.forward_from_chat.type in ("channel", "supergroup", "group"):
        try: await context.bot.delete_message(chat_id, mid)
        except: pass
        await context.bot.send_message(chat_id, f"⚠️ {user.first_name}, forward qilingan postlar taqiqlangan.", reply_markup=group_add_btn(context.bot.username))
        return

    # 2) Entities (exact detection)
    urls = extract_entities_urls(msg)
    if any(is_promo_url(u) for u in urls):
        try: await context.bot.delete_message(chat_id, mid)
        except: pass
        await context.bot.send_message(chat_id, f"⚠️ {user.first_name}, havolalar taqiqlangan.", reply_markup=group_add_btn(context.bot.username))
        return

    # 3) Text/caption regex fallback
    full_text = (msg.text or "") + "\n" + (msg.caption or "")
    if text_has_tg_link(full_text):
        try: await context.bot.delete_message(chat_id, mid)
        except: pass
        await context.bot.send_message(chat_id, f"⚠️ {user.first_name}, reklama/havola taqiqlangan.", reply_markup=group_add_btn(context.bot.username))
        return

# ---------------- Commands ----------------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Buyruqlar:\n"
        "/help – yordam\n",
        reply_markup=group_add_btn(context.bot.username)
    )

# ---------------- App ----------------
app = ApplicationBuilder().token(TOKEN).build()

# Catch ALL messages first (except service updates; those we'll handle separately if needed)
app.add_handler(MessageHandler(filters.ALL, reklama_va_soz_filtri))
app.add_handler(CommandHandler("help", help_cmd))

async def main():
    await app.bot.set_my_commands([BotCommand("help", "Bot qo'llanmasi")])
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print("✅ Bot ishga tushdi...")
    while True:
        await asyncio.sleep(2)

if __name__ == "__main__":
    start_web()
    asyncio.get_event_loop().run_until_complete(main())
