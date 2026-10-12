# language: Python, file: arak_bot.py, target: Any (Koyeb/Railway/VPS)
# *Arak rank bot — shout slogans, gain XP, climb ranks. 60s cooldown.*
import os
import sqlite3
import random
import time
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest

# ============ CONFIG ============
TOKEN = os.environ.get("TOKEN", "YOUR_BOT_TOKEN_HERE")
DB_PATH = "arak_bot.db"
# ================================

# ============ RANKS ============
RANKS = [
    ("شهروند اراکی",         0,     1,   5),
    ("سرباز اراکی",        100,     3,   8),
    ("گروهبان اراکی",      300,     5,  10),
    ("سروان اراکی",        700,     8,  14),
    ("ستوان اراکی",       1000,    11,  18),
    ("سرهنگ اراکی",       1500,    15,  25),
    ("سردار اراکی",       2500,    30,  80),
    ("فرمانده کل قوای اراک", 10000, 50, 120),
]

SLOGANS = [
    "جاوید اراک", "اراکی آزاد", "اراک مدرن", "اراک قدرتمند",
    "اراک بمولا", "حاجی ولی اراک", "اراک تا ابد", "اراک زنده باد",
    "اراک قلب ایرانه", "اراک قویه", "اراکی‌ام و افتخار می‌کنم",
    "اراک، شهر صنعت", "اراک همیشه پیروز", "اراک سرزمین مردان",
    "اراکی‌ها یکدل",
]

COOLDOWN = 60

# ============ DATABASE ============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            xp INTEGER DEFAULT 0,
            total_shouts INTEGER DEFAULT 0,
            last_shout REAL DEFAULT 0,
            joined_at REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_members (
            chat_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id, username=None, first_name=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute(
            "INSERT INTO users (user_id, username, first_name, joined_at) VALUES (?,?,?,?)",
            (user_id, username, first_name, time.time())
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    conn.close()
    return row

def update_user(user_id, xp_delta=0, shouts_delta=0, last_shout=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if last_shout is not None:
        c.execute(
            "UPDATE users SET xp = xp + ?, total_shouts = total_shouts + ?, last_shout = ? WHERE user_id = ?",
            (xp_delta, shouts_delta, last_shout, user_id)
        )
    else:
        c.execute(
            "UPDATE users SET xp = xp + ?, total_shouts = total_shouts + ? WHERE user_id = ?",
            (xp_delta, shouts_delta, user_id)
        )
    conn.commit()
    conn.close()

def get_rank(xp):
    idx = 0
    for i, (name, req, xmin, xmax) in enumerate(RANKS):
        if xp >= req:
            idx = i
    name, req, xmin, xmax = RANKS[idx]
    next_req = RANKS[idx + 1][1] if idx + 1 < len(RANKS) else None
    return idx, name, next_req

def top_users(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, xp, total_shouts FROM users ORDER BY xp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def register_chat_member(chat_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO chat_members (chat_id, user_id) VALUES (?,?)", (chat_id, user_id))
    conn.commit()
    conn.close()

def chat_rank(chat_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id, u.username, u.first_name, u.xp, u.total_shouts
        FROM users u JOIN chat_members m ON m.user_id = u.user_id
        WHERE m.chat_id = ? ORDER BY u.xp DESC LIMIT ?
    """, (chat_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

# ============ HELPERS ============
def progress_bar(current, total, length=10):
    if total <= 0:
        return "█" * length
    filled = int((current / total) * length)
    return "█" * filled + "░" * (length - filled)

def fmt_xp(n):
    return f"{n:,}"

# ============ COMMANDS ============
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    get_user(u.id, u.username, u.first_name)
    if update.effective_chat.type != "private":
        register_chat_member(update.effective_chat.id, u.id)
    text = (
        "🏙️ *به بات اراک خوش اومدی!*\n\n"
        "با شعار دادن، XP بگیر و رنکت رو ببر بالا.\n\n"
        "📢 *شعار بده:*\n"
        "• جاوید اراک\n"
        "• اراکی آزاد\n"
        "• اراک بمولا\n"
        "• حاجی ولی اراک\n\n"
        "⏱️ هر ۱ دقیقه یه بار.\n\n"
        "📋 /me /top /rank /slogans /chatrank"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def me_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    row = get_user(u.id, u.username, u.first_name)
    user_id, username, first_name, xp, shouts, last_shout, joined = row
    rank_idx, rank_name, next_req = get_rank(xp)
    next_rank_name = RANKS[rank_idx + 1][0] if rank_idx + 1 < len(RANKS) else None
    if next_req:
        cur = RANKS[rank_idx][1]
        prog = xp - cur
        needed = next_req - cur
        bar = progress_bar(prog, needed)
        prog_line = f"`{bar}`  {fmt_xp(prog)} / {fmt_xp(needed)}\n➡️ *{next_rank_name}*"
    else:
        prog_line = "🏆 *بالاترین رنک!*"
    delta = time.time() - (last_shout or 0)
    cd_line = f"⏱️ {int(COOLDOWN - delta)}s" if delta < COOLDOWN else "✅ آزاد"
    text = (
        f"👤 *{first_name}*\n\n"
        f"🎖️ *{rank_name}*\n"
        f"⭐ XP: *{fmt_xp(xp)}*\n"
        f"📢 شعارها: *{shouts}*\n\n"
        f"{prog_line}\n\n"
        f"{cd_line}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def shout_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 یه شعار اراکی بنویس.\nمثال: *جاوید اراک*",
        parse_mode="Markdown"
    )

async def slogans_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = "📜 *شعارها:*\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(SLOGANS, 1))
    await update.message.reply_text(text, parse_mode="Markdown")

async def rank_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = "🎖️ *رنک‌ها:*\n\n"
    for i, (name, req, xmin, xmax) in enumerate(RANKS):
        text += f"*{i+1}. {name}*\n   XP: {fmt_xp(req)}  |  هر شعار: {xmin}-{xmax}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def top_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = top_users(10)
    if not rows:
        await update.message.reply_text("هنوز کسی شعار نداده!")
        return
    text = "🏆 *۱۰ اراکی برتر:*\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, uname, fname, xp, shouts) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        _, rank_name, _ = get_rank(xp)
        text += f"{medal} *{fname or uname or uid}* — {rank_name}\n    ⭐ {fmt_xp(xp)}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def chatrank_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("فقط تو گروه.")
        return
    rows = chat_rank(update.effective_chat.id, 10)
    if not rows:
        await update.message.reply_text("هنوز کسی شعار نداده!")
        return
    text = "🏆 *برترین‌های گروه:*\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, uname, fname, xp, shouts) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        _, rank_name, _ = get_rank(xp)
        text += f"{medal} *{fname or uname or uid}* — {rank_name}\n    ⭐ {fmt_xp(xp)}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ============ SLOGAN ============
def is_arak_slogan(text):
    t = text.strip().lower().replace("ي", "ی").replace("ك", "ک")
    if "اراک" not in t and "اراکی" not in t:
        return False
    if len(t) > 80:
        return False
    return True

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    u = update.effective_user
    row = get_user(u.id, u.username, u.first_name)
    if update.effective_chat.type != "private":
        register_chat_member(update.effective_chat.id, u.id)
    if not is_arak_slogan(text):
        return
    user_id, username, first_name, xp, shouts, last_shout, joined = row
    now = time.time()
    if now - (last_shout or 0) < COOLDOWN:
        remaining = int(COOLDOWN - (now - (last_shout or 0)))
        await update.message.reply_text(f"⏱️ {first_name}، {remaining} ثانیه صبر کن.")
        return
    rank_idx, rank_name, _ = get_rank(xp)
    xmin, xmax = RANKS[rank_idx][2], RANKS[rank_idx][3]
    gain = random.randint(xmin, xmax)
    update_user(u.id, xp_delta=gain, shouts_delta=1, last_shout=now)
    new_xp = xp + gain
    new_idx, new_name, _ = get_rank(new_xp)
    msg = f"📢 {first_name}:\n*«{text}»*\n\n⭐ +{gain} XP\n🎖️ *{new_name}*\n📊 {fmt_xp(new_xp)} XP"
    if new_idx > rank_idx:
        msg += f"\n\n🎉 *ترفیع!* {rank_name} → *{new_name}*"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============ MAIN ============
def main():
    init_db()
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .get_updates_request(request)
        .build()
    )
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("me", me_cmd))
    app.add_handler(CommandHandler("shout", shout_cmd))
    app.add_handler(CommandHandler("slogans", slogans_cmd))
    app.add_handler(CommandHandler("rank", rank_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("chatrank", chatrank_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("[+] Arak bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
