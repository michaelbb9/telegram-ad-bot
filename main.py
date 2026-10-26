import time
import json
import os
import asyncio
import threading
import requests
import logging
import yt_dlp
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# .strip() automatically removes any accidental spaces or hidden enter keys (\n) from Render's environment variables
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8863904451:AAG-QT2pLfR1myUkCyziVCteRiGW5t08udc").strip()
ADMIN_ID = 6248570946  # Your secure personal Telegram ID
DETECTED_CHANNEL_ID = -1004347828512
PRIVATE_CHANNEL_ID = -1004347828512  # Vault/Tutorial channel
TUTORIAL_MESSAGE_ID = 108             # Your working tutorial video message ID
WEB_BASE_URL = "https://michaelbbc.pythonanywhere.com"
BRIDGE_URL = f"{WEB_BASE_URL}/bridge"
PUBLIC_CHANNEL_URL = "https://t.me/booksaufio"
PUBLIC_CHANNEL_USERNAME = "@booksaufio"  # Used for API channel membership checks
DELETE_DELAY_TIME = 540  # 9 minutes

# --- TINY WEB SERVER FOR RENDER ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is alive and running!", 200
# ----------------------------------

# TOKEN SYNC WITH PYTHONANYWHERE BRIDGE BACKEND
def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error loading tokens from bridge: {e}")
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, timeout=5)
    except Exception as e:
        logger.error(f"Error saving tokens to bridge: {e}")

# --- YT-DLP DOWNLOAD HELPER (With Cookies & Quality Extraction) ---
def download_video_ytdlp(url: str):
    """Downloads video using yt-dlp, returning filepath, resolution, and file size."""
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    ydl_opts = {
        'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'max_filesize': 50 * 1024 * 1024,  # 50MB limit for Telegram bots
        'noplaylist': True,
        'quiet': True,
    }
    
    # Automatically attach cookies.txt if available for authenticated platform scraping
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # Extract quality/resolution and file size metrics
        height = info.get('height', 'Unknown')
        resolution = f"{height}p" if isinstance(height, int) else "HD/SD"
        
        try:
            file_size_bytes = os.path.getsize(filename)
            size_str = f"{file_size_bytes / (1024 * 1024):.1f}MB"
        except Exception:
            size_str = "Unknown size"
            
        return filename, resolution, size_str

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "👋 **Welcome to the Media Downloader & Vault Bot!**\n\n"
            "📥 **What I can do:**\n"
            "I allow you to download media files directly from supported platforms and unlock exclusive content vaults!\n\n"
            "🌐 **Supported Platforms for Downloading:**\n"
            "• **TikTok** (Videos & Slides)\n"
            "• **YouTube** (Videos & Shorts)\n"
            "• **X (Twitter)** (Public, Sensitive, & Authenticated Posts)\n"
            "• **Instagram** (Reels & Posts)\n"
            "• **Facebook** (Videos & Reels)\n\n"
            "🎁 **Allowance & Refills:**\n"
            "You get **4 free downloads every day**. When you run out, you can instantly refill your balance by completing a quick 20-second bridge page timer!"
        )
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

    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"

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
        logger.error(f"Copy message error: {e}")
        await update.message.reply_text(
            text=caption_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# --- MEDIA LINK LISTENER HANDLER ---
async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    
    supported_domains = ["youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com", "facebook.com", "fb.watch", "instagram.com"]
    if not any(domain in text.lower() for domain in supported_domains):
        return

    words = text.split()
    url = next((word for word in words if any(d in word.lower() for d in supported_domains)), None)
    
    if not url:
        return

    # Check download allowance with PythonAnywhere backend (Admin bypass active)
    try:
        response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id}, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
        else:
            await update.message.reply_text("❌ Server connection error. Please try again later.")
            return
    except Exception as e:
        logger.error(f"Error checking download limit: {e}")
        await update.message.reply_text("❌ Error connecting to authorization server.")
        return

    if res_data.get("status") == "allowed":
        remaining = res_data.get("left", 0)
        display_left = "∞ (Admin)" if remaining > 500 else str(remaining)
        status_msg = await update.message.reply_text(f"📥 **Downloading video...** ({display_left} free downloads remaining for today)")
        
        try:
            file_path, resolution, size_str = download_video_ytdlp(url)
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as video_file:
                    sent_video = await context.bot.send_video(
                        chat_id=user_id,
                        video=video_file,
                        caption=(
                            "✨ **Download Successful!**\n"
                            f"📐 **Quality:** {resolution}\n"
                            f"📦 **Size:** {size_str}"
                        ),
                        parse_mode="Markdown"
                    )
                
                warning_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text="⏳ **Safety Alert:** This downloaded video will automatically delete in **9 minutes** for security reasons. Watch or save it now!"
                )
                
                # Schedule auto-delete for both the video and the warning notification
                messages_to_delete = [sent_video.message_id, warning_msg.message_id]
                context.job_queue.run_once(auto_delete_task, when=DELETE_DELAY_TIME, data=messages_to_delete, chat_id=user_id)

                os.remove(file_path)
                await context.bot.delete_message(chat_id=user_id, message_id=status_msg.message_id)
            else:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg.message_id,
                    text="❌ Failed to download video. File path not found."
                )
        except Exception as e:
            logger.error(f"Download error details: {e}", exc_info=True)
            error_msg = str(e) if str(e) else type(e).__name__
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg.message_id,
                    text=f"❌ Download error: {error_msg}"
                )
            except Exception:
                pass
    else:
        # Limit reached -> Provide bridge link to refill 4 downloads
        bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
        
        tokens = load_tokens()
        tokens[str(user_id)] = {
            "user_id": int(user_id),
            "msg_start": 0,
            "msg_end": 0,
            "clicked_ad": False,
            "verified": False,
            "expires": time.time() + 600
        }
        save_tokens(tokens)

        keyboard = [
            [InlineKeyboardButton("🔓 Open Link & Refill 4 Downloads", url=bridge_link)],
            [InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)],
            [InlineKeyboardButton("💜 Check & Refill Balance", callback_data="verify_user")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text=(
                "⚠️ **Daily Download Limit Reached!**\n\n"
                "You have used your 4 free downloads for today.\n\n"
                "🔓 **Want 4 more downloads immediately?**\n"
                "1️⃣ Click **Open Link & Refill 4 Downloads**, then click **Open Sponsor Page**.\n"
                "2️⃣ Stay on the sponsor page for 20 seconds, close it, and come back to click **Check & Refill Balance**!"
            ),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
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
        # 1. MANDATORY PUBLIC CHANNEL JOIN CHECK
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                await query.answer(
                    "❌ You must join our public channel first! Click '📢 Join Public Channel' above, join, and try again.",
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
            await query.answer("❌ Session expired or not started. Please try again.", show_alert=True)
            return

        token_data = tokens[user_str]

        if not token_data.get("verified", False):
            await query.answer("❌ You haven't finished viewing the sponsor page yet! Stay on the sponsor page until the timer completes.", show_alert=True)
            return

        msg_start = token_data.get("msg_start", 0)
        msg_end = token_data.get("msg_end", 0)

        del tokens[user_str]
        save_tokens(tokens)

        await query.answer("✅ Verification Successful!", show_alert=False)

        # CASE A: Media Downloader Refill (msg_start == 0)
        if msg_start == 0:
            await query.message.reply_text("✅ **Verification Successful!** Your 4 free downloads have been refilled for today. Send your video link now!")
            return

        # CASE B: Vault Bundle Delivery (msg_start > 0)
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

def run_telegram_bot():
    """Runs the Telegram bot in a dedicated event loop thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_bot():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        await asyncio.Event().wait()

    loop.run_until_complete(start_bot())

if __name__ == "__main__":
    print("Starting Telegram bot background thread...")
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    print("Testing Flask web server on main thread...")
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
