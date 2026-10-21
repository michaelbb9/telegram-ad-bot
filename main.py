import time
import json
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8863904451:AAE1DbPBkeB1SXyCLIzDNbxTfEZIYd_sjWI"
ADMIN_ID = 6248570946  # Your secure personal Telegram ID
DETECTED_CHANNEL_ID = -1004347828512
PRIVATE_CHANNEL_ID = -1004347828512  # Vault/Tutorial channel
TUTORIAL_MESSAGE_ID = 78             # Message ID for your tutorial video
WEB_BRIDGE_URL = "https://michaelbbc.pythonanywhere.com/bridge"
PUBLIC_CHANNEL_URL = "https://t.me/booksaufio"
DELETE_DELAY_TIME = 540  # 9 minutes
REQUIRED_WAIT_SECONDS = 20

TOKEN_FILE = "/home/Michaelbbc/mysite/tokens.json"

def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return {}
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_tokens(tokens):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(tokens, f)
    except Exception as e:
        print(f"Error saving tokens: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text("👋 Welcome! Please click a video link from the main channel.")
        return

    video_code = args[0]
    if video_code.startswith("vid"):
        clean_code = video_code.replace("vid", "")
        if "to" in clean_code:
            try:
                parts = clean_code.split("to")
                msg_start, msg_end = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Invalid bundle format.")
                return
        else:
            try:
                msg_start = int(clean_code)
                msg_end = msg_start
            except ValueError:
                await update.message.reply_text("❌ Invalid video number.")
                return
    else:
        await update.message.reply_text("❌ Unknown link parameter layout.")
        return

    bridge_link = f"{WEB_BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"

    # Register session in your tokens.json file
    tokens = load_tokens()
    tokens[str(user_id)] = {
        "user_id": int(user_id),
        "msg_start": int(msg_start),
        "msg_end": int(msg_end),
        "clicked_ad": False,
        "verified": False,
        "expires": time.time() + 600
    }
    save_tokens(tokens)

    keyboard = [
        [InlineKeyboardButton("🔓 Open Link & Watch Timer", url=bridge_link)],
        [InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("💜 Check & Get Files", callback_data="verify_user")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption_text = (
        "👇 **CONTENT LOCKED** 👇\n\n"
        "⚠️ **Browser Tip:** *For the smoothest experience and accurate timer tracking, please tap the three dots (⋮) and select **'Open in browser' (Chrome/Safari)** instead of using Telegram's built-in view!*\n\n"
        "To unlock and receive your video bundle:\n"
        "1️⃣ Click **Open Link & Watch Timer**, then click the **Open Sponsor Page** button.\n"
        "2️⃣ Stay on the sponsor page for the full countdown, close the window, and come back here to click **Check & Get Files**!\n\n"
        "👇 *Watch the short tutorial video above if you're stuck!*"
    )

    # Send tutorial video from your private vault with your buttons attached
    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=PRIVATE_CHANNEL_ID,
            message_id=TUTORIAL_MESSAGE_ID,
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        # Fallback text message if copy fails
        await update.message.reply_text(
            text=caption_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Secure Admin /stats command handler"""
    user_id = update.message.from_user.id
    
    # Strictly lock down to your admin ID
    if user_id != ADMIN_ID:
        return

    tokens = load_tokens()
    total_sessions = len(tokens)
    clicked_ad = sum(1 for data in tokens.values() if data.get("clicked_ad", False))
    completed_timer = sum(1 for data in tokens.values() if data.get("verified", False))
    pending_users = total_sessions - completed_timer

    report = (
        "📊 **ADMIN LIVE STATS** 📊\n\n"
        f"👥 **Total Bot Sessions:** {total_sessions}\n"
        f"🖱️ **Clicked Ad:** {clicked_ad}\n"
        f"✅ **Completed Verification:** {completed_timer}\n"
        f"⏳ **Currently Pending:** {pending_users}\n"
    )

    await update.message.reply_text(report, parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "verify_user":
        tokens = load_tokens()
        user_str = str(user_id)

        if user_str not in tokens:
            await query.answer("❌ Session expired or not started. Please click the video link again.", show_alert=True)
            return

        token_data = tokens[user_str]

        if not token_data.get("verified", False):
            await query.answer("❌ You haven't finished viewing the sponsor page yet! Stay on the sponsor page until the timer completes.", show_alert=True)
            return

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

            context.job_queue.run_once(auto_delete_task, when=DELETE_DELAY_TIME, data=forwarded_message_ids, chat_id=user_id)

        except Exception as e:
            await query.message.reply_text(f"❌ Error fetching file bundle: {e}")

async def auto_delete_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    for msg_id in job.data:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

def main() -> None:
    print("Bot is starting up with your secure session architecture and tutorial video...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers registered here
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    
    app.run_polling()

if __name__ == "__main__":
    main()
