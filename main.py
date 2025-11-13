import json
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ---------------------------
# CONFIGURATION
# ---------------------------
BOT_TOKEN = "8511607485:AAGBBnV6TLxjJSiORmsXzTWFUrtD7RHgdG4"
ADMIN_IDS = [6898849211]  # Replace with your Telegram ID(s)
POST_INTERVAL = 1200  # 20 minutes in seconds

# ---------------------------
# DATA FILES
# ---------------------------
LINK_QUEUE_FILE = "link_queue.json"
ENGAGEMENT_FILE = "engagements.json"
LEADERBOARD_FILE = "leaderboard.json"

# ---------------------------
# LOAD / SAVE FUNCTIONS
# ---------------------------
def load_json(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

link_queue = load_json(LINK_QUEUE_FILE)
engagements = load_json(ENGAGEMENT_FILE)
leaderboard = load_json(LEADERBOARD_FILE)

# ---------------------------
# BOT COMMANDS
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = "Admin" if user_id in ADMIN_IDS else "User"
    await update.message.reply_text(f"👋 Welcome, {update.effective_user.first_name}!\nRole: {role}\nUse /help to see commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
Commands:
/start - Welcome
/help - This help message
/submit - Submit a new link (Users)
/task - Force posting queued links (Admins)
/stats - Show leaderboard
/viewqueue - View pending links (Admins)
"""
    await update.message.reply_text(msg)

# ---------------------------
# LINK SUBMISSION FLOW
# ---------------------------
async def submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        await update.message.reply_text("Admins can post directly. Use /task.")
        return
    # Ask category
    keyboard = [
        [InlineKeyboardButton("🪙 Promotional Link", callback_data="cat_promotional")],
        [InlineKeyboardButton("📁 Info File Link", callback_data="cat_infofile")],
        [InlineKeyboardButton("🌅 GM / Regular Post", callback_data="cat_regular")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose the category of your link:", reply_markup=reply_markup)

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    context.user_data['category'] = query.data.replace("cat_", "")
    await query.message.reply_text("Please send the link now:")

async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text
    context.user_data['link'] = link
    await update.message.reply_text("Please provide a short description for this link:")
    return

async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    description = update.message.text
    category = context.user_data.get('category')
    link = context.user_data.get('link')
    if not all([category, link, description]):
        await update.message.reply_text("Something went wrong, please try /submit again.")
        return

    # Queue the link
    timestamp = datetime.utcnow().isoformat()
    queue_item = {
        "user_id": user_id,
        "username": update.effective_user.username or update.effective_user.first_name,
        "category": category,
        "link": link,
        "description": description,
        "timestamp": timestamp
    }
    if 'queue' not in link_queue:
        link_queue['queue'] = []
    link_queue['queue'].append(queue_item)
    save_json(LINK_QUEUE_FILE, link_queue)

    await update.message.reply_text(f"✅ Your link has been queued for posting in the {category} category!")

# ---------------------------
# POSTING AND ENGAGEMENT
# ---------------------------
async def post_links_periodically(app):
    while True:
        await asyncio.sleep(POST_INTERVAL)
        await post_next_link(app)

async def post_next_link(app):
    if not link_queue.get('queue'):
        return
    link_item = link_queue['queue'].pop(0)
    save_json(LINK_QUEUE_FILE, link_queue)

    chat_id = "-1001234567890"  # Replace with your group/channel ID or dynamically map categories
    # Example: category -> chat
    category_chats = {
        "promotional": "-1003264303745",
        "infofile": "-1003264303745",
        "regular": "-1003264303745"
    }
    chat_id = category_chats.get(link_item['category'], chat_id)

    keyboard = [[InlineKeyboardButton("✅ Engage", callback_data="engage")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await app.bot.send_message(
        chat_id=chat_id,
        text=f"🚀 New {link_item['category']} post by @{link_item['username']}:\n\n{link_item['description']}\n{link_item['link']}",
        reply_markup=reply_markup
    )

async def engagement_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    timestamp = datetime.utcnow().isoformat()

    # Store engagement
    tx_id = f"TX#{len(engagements)+1:04}"
    engagements[tx_id] = {
        "user_id": user_id,
        "username": username,
        "timestamp": timestamp
    }
    save_json(ENGAGEMENT_FILE, engagements)

    # Update leaderboard
    leaderboard[user_id] = leaderboard.get(user_id, {"username": username, "points": 0})
    leaderboard[user_id]["points"] += 1
    save_json(LEADERBOARD_FILE, leaderboard)

    await query.message.reply_text(f"✅ Thanks {username}, your engagement is recorded!")

# ---------------------------
# STATS / LEADERBOARD
# ---------------------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not leaderboard:
        await update.message.reply_text("No engagements yet.")
        return
    report = "📊 Leaderboard (Most Engaging Users):\n"
    sorted_lb = sorted(leaderboard.values(), key=lambda x: x['points'], reverse=True)
    for i, item in enumerate(sorted_lb[:10], 1):
        report += f"{i}. @{item['username']} — {item['points']} points\n"
    await update.message.reply_text(report)

async def view_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin.")
        return
    if not link_queue.get('queue'):
        await update.message.reply_text("Queue is empty.")
        return
    report = "📋 Pending Link Queue:\n"
    for i, item in enumerate(link_queue['queue'], 1):
        report += f"{i}. @{item['username']} — {item['category']} — {item['link']}\n"
    await update.message.reply_text(report)

# ---------------------------
# MAIN SETUP
# ---------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Commands
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("submit", submit))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("viewqueue", view_queue))

# Callback Queries
app.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))
app.add_handler(CallbackQueryHandler(engagement_handler, pattern="^engage$"))

# Messages
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, link_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler))

# Run periodic posting in background
app.job_queue.run_repeating(lambda ctx: asyncio.create_task(post_next_link(app)), interval=POST_INTERVAL, first=10)

# Start bot
app.run_polling()
