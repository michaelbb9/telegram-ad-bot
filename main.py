import os
import json
import asyncio
import logging
import requests
from flask import Flask
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEB_BRIDGE_URL = os.getenv("WEB_BRIDGE_URL", "https://your-pythonanywhere-username.pythonanywhere.com")
PUBLIC_CHANNEL_URL = "@booksaufio"  # Public channel to verify membership
DETECTED_CHANNEL_ID = -1004347828512  # Private storage channel ID
TUTORIAL_MSG_ID = 6248570946  # Updated tutorial video message ID from private channel

DELETE_DELAY_TIME = 540  # 9 minutes in seconds

# --- FLASK APP FOR RENDER (KEEPS WEB SERVICE ALIVE) ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return "Bot is alive and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- TOKEN STORAGE HELPERS (SYNCED WITH PYTHONANYWHERE BACKEND) ---
def load_tokens():
    try:
        response = requests.get(f"{WEB_BRIDGE_URL}/get_tokens", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error loading tokens from bridge: {e}")
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BRIDGE_URL}/save_tokens", json=tokens, timeout=5)
    except Exception as e:
        logger.error(f"Error saving tokens to bridge: {e}")

# --- COMMAND: /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "Welcome! Please use a valid video link from our channel to get started."
        )
        return

    param = args[0]  # e.g., vid10to15
    try:
        start_str, end_str = param.replace("vid", "").split("to")
        msg_start = int(start_str)
        msg_end = int(end_str)
    except Exception:
        await update.message.reply_text("❌ Invalid link format.")
        return

    # Save initial token state
    tokens = load_tokens()
    tokens[str(user_id)] = {
        "msg_start": msg_start,
        "msg_end": msg_end,
        "verified": False
    }
    save_tokens(tokens)

    # Generate unique bridge page link for this user
    bridge_link = f"{WEB_BRIDGE_URL}/bridge?user_id={user_id}"

    keyboard = [
        [InlineKeyboardButton("🔒 Open Link & Watch Timer", url=bridge_link)],
        [InlineKeyboardButton("📢 Join Public Channel", url=f"https://t.me/{PUBLIC_CHANNEL_URL.lstrip('@')}")],
        [InlineKeyboardButton("💜 Check & Get Files", callback_data="verify_user")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Copy the tutorial video with caption & interactive buttons attached
    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=DETECTED_CHANNEL_ID,
            message_id=TUTORIAL_MSG_ID,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to copy tutorial video: {e}")
        await update.message.reply_text(
            "👇 **CONTENT LOCKED** 👇\n\nTo unlock and receive your video bundle, please complete the steps below:",
            reply_markup=reply_markup
        )

# --- COMMAND: /stats (Admin Dashboard) ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tokens = load_tokens()
    
    total_sessions = len(tokens)
    verified_sessions = sum(1 for data in tokens.values() if data.get("verified"))
    pending_sessions = total_sessions - verified_sessions

    await update.message.reply_text(
        f"📊 **Bot Live Statistics Summary**\n\n"
        f"• Total Active Sessions: `{total_sessions}`\n"
        f"• Verified Users Ready: `{verified_sessions}`\n"
        f"• Pending/Unverified: `{pending_sessions}`\n\n"
        f"🟢 **System Status:** Online & Operational"
    )

# --- BUTTON HANDLER (CHANNEL CHECK + VERIFICATION + FILE DELIVERY) ---
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "verify_user":
        # 1. MANDATORY PUBLIC CHANNEL CHECK
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_URL, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                await query.answer(
                    "❌ You must join our public channel first! Click '📢 Join Public Channel' below, join, and try again.",
                    show_alert=True
                )
                return
        except Exception as e:
            logger.error(f"Channel check error: {e}")
            await query.answer(
                "⚠️ Please make sure you have joined the public channel before proceeding!",
                show_alert=True
            )
            return

        # 2. SPONSOR TIMER VERIFICATION CHECK
        tokens = load_tokens()
        user_str = str(user_id)

        if user_str not in tokens:
            await query.answer("❌ Session expired or not started. Please click the video link again.", show_alert=True)
            return

        token_data = tokens[user_str]

        if not token_data.get("verified", False):
            await query.answer("❌ You haven't finished viewing the sponsor page yet! Stay on the sponsor page until the timer completes.", show_alert=True)
            return

        # 3. RELEASE CONTENT (IF BOTH CHECKS PASS)
        msg_start = token_data["msg_start"]
        msg_end = token_data["msg_end"]

        del tokens[user_str]
        save_tokens(tokens)

        await query.answer("✅ Verification Successful!", show_alert=False)
        await query.message.reply_text("✅ **Verification Successful!** Fetching your video bundle packet from the vault now...")

        forwarded_message_ids = []
        try:
            for target_msg_id in range(msg_start, msg_end + 1):
                forwarded_msg = await context.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=DETECTED_CHANNEL_ID,
                    message_id=target_msg_id
                )
                forwarded_message_ids.append(forwarded_msg.message_id)
                await asyncio.sleep(0.2)

            warning_msg = await context.bot.send_message(
                chat_id=user_id,
                text="⏳ **Safety Alert:** These videos will automatically delete in **9 minutes** for security reasons. Watch them now!"
            )
            forwarded_message_ids.append(warning_msg.message_id)

            # Schedule 9-minute auto-delete
            context.job_queue.run_once(auto_delete_task, when=DELETE_DELAY_TIME, data=forwarded_message_ids, chat_id=user_id)

        except Exception as e:
            await query.message.reply_text(f"❌ Error fetching file bundle: {e}")

# --- AUTO-DELETE TASK ---
async def auto_delete_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    message_ids = job.data
    chat_id = job.chat_id

    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to delete message {msg_id}: {e}")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🗑️ **Security Notice:** Your previous video bundle has been automatically deleted."
        )
    except Exception:
        pass

# --- MAIN ENTRY POINT ---
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("No TELEGRAM_TOKEN found in environment variables!")
        return

    # Start background Flask server for Render health checks
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Build and start Telegram bot
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(handle_buttons))

    logger.info("Bot is starting polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
