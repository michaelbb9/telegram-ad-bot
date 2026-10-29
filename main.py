import time
import json
import os
import asyncio
import threading
import requests
import logging
import re
import imageio_ffmpeg
import yt_dlp
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- FIX FFMPEG EXECUTION PERMISSIONS FOR RENDER ---
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
try:
    os.chmod(ffmpeg_path, 0o755)  # Grants execution rights to the ffmpeg binary
except Exception as e:
    logging.error(f"Could not set ffmpeg permissions: {e}")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# .strip() automatically removes any accidental spaces or hidden enter keys (\n) from Render's environment variables
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8863904451:AAFYl9yyjTvKTaliLR5iqTsvZr2tytFi3bk").strip()
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

# --- NATIVE AUTO-DELETE BACKGROUND TASK ---
async def schedule_deletion(bot, chat_id, message_ids, delay):
    """Waits for the specified delay and deletes messages securely."""
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

# --- YT-DLP DOWNLOAD HELPER (Dynamic Quality Fallback System) ---
def download_video_ytdlp(url: str):
    """
    Tries downloading in highest possible quality first. 
    Steps down to 720p, then 480p if too big. Raises error if 480p still exceeds 50MB.
    """
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    tiers = [
        ("best", "Highest Quality (4K/1080p)"),
        ("best[height<=720]", "720p HD"),
        ("best[height<=480]", "480p")
    ]
    
    for fmt, tier_desc in tiers:
        try:
            ydl_opts = {
                'format': fmt,
                'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                'max_filesize': 50 * 1024 * 1024,  # Strict 50MB limit cap for Telegram bots
                'noplaylist': True,
                'quiet': True,
                'merge_output_format': 'mp4',
                'ffmpeg_location': ffmpeg_path,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            }
            
            domain_lower = url.lower()
            if any(d in domain_lower for d in ["twitter.com", "x.com", "youtube.com", "youtu.be"]):
                if os.path.exists("cookies.txt"):
                    ydl_opts['cookiefile'] = "cookies.txt"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                file_size_bytes = os.path.getsize(filename)
                if file_size_bytes > 50 * 1024 * 1024:
                    os.remove(filename)
                    continue
                
                height = info.get('height', 'Unknown')
                resolution = f"{height}p" if isinstance(height, int) else "HD/SD"
                size_str = f"{file_size_bytes / (1024 * 1024):.1f}MB"
                    
                return filename, resolution, size_str
        except Exception:
            continue
            
    raise ValueError("FILE_TOO_LARGE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "👋 **Welcome to the Media Downloader & Vault Bot!**\n\n"
            "📥 **What I can do:**\n"
            "I allow you to download media files from **several different websites**, process **batch multi-link text/files**, AND unlock exclusive content vaults!\n\n"
            "💬 **How to Download:**\n"
            "• **Single Link:** Paste any link directly into chat.\n"
            "• **Batch Links:** Paste jumbled text containing multiple links OR upload a `.txt` file packed with links to download them all at once!\n\n"
            "🌐 **Supported Sites & Platforms:**\n"
            "• **Multiple Websites** (TikTok, vt.tiktok.com short links, X/Twitter, Instagram, Facebook, and thousands of other video & media sites!)\n"
            "• ❌ ~~YouTube~~ *(Temporarily paused / Maintenance)*\n\n"
            "⚡ **Dynamic Quality & Size Notice:**\n"
            "• Automatically grabs the **highest possible quality** (up to 4K/1080p), stepping down to 720p/480p if needed.\n"
            "• If a video exceeds **50MB** even at 480p, it will notify you that Telegram won't allow it.\n\n"
            "📦 **Exclusive Content Vaults:**\n"
            "• Tap vault links to unlock premium curated video bundles and media packs from our private channels.\n\n"
            "🎁 **Allowance & Refills:**\n"
            "• You get **4 free downloads every day**.\n"
            "• When you run out, instantly refill your balance by completing a quick 20-second bridge page timer!"
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

# --- CORE BATCH DOWNLOAD PROCESSOR ---
async def process_url_batch(bot, user_id, chat_id, urls):
    """Processes a list of extracted URLs sequentially with allowance checks and security timers."""
    if not urls:
        return

    success_count = 0
    fail_count = 0

    batch_notice = await bot.send_message(
        chat_id=chat_id,
        text=f"📦 **Batch Processing Started:** Found **{len(urls)} links**. Processing downloads sequentially..."
    )

    for index, url in enumerate(urls, start=1):
        domain_lower = url.lower()
        if "youtube.com" in domain_lower or "youtu.be" in domain_lower:
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Skipped YouTube link (under maintenance).")
            continue

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id}, timeout=5)
            if response.status_code == 200:
                res_data = response.json()
            else:
                await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Server error checking allowance.")
                break
        except Exception:
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Connection error to server.")
            break

        if res_data.get("status") != "allowed":
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

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ **Daily Download Limit Reached at link {index} of {len(urls)}!**\n\n"
                    "You have used your 4 free downloads. Refill your balance to continue batch downloading!"
                ),
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            break

        status_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"📥 [{index}/{len(urls)}] Downloading media..."
        )

        try:
            file_path, resolution, size_str = download_video_ytdlp(url)
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as media_file:
                    sent_media = await bot.send_video(
                        chat_id=chat_id,
                        video=media_file,
                        caption=(
                            f"✨ **Batch Item {index}/{len(urls)} Successful!**\n"
                            f"📐 **Quality:** {resolution}\n"
                            f"📦 **Size:** {size_str}"
                        ),
                        parse_mode="Markdown"
                    )
                
                warning_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ [{index}/{len(urls)}] Safety Alert: This file will automatically delete in **9 minutes**."
                )
                
                messages_to_delete = [sent_media.message_id, warning_msg.message_id]
                asyncio.create_task(schedule_deletion(bot, chat_id, messages_to_delete, DELETE_DELAY_TIME))

                os.remove(file_path)
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}/{len(urls)}] Failed: File path not found.")
                fail_count += 1
        except Exception as e:
            logger.error(f"Batch download error for {url}: {e}", exc_info=True)
            if "FILE_TOO_LARGE" in str(e):
                err_text = f"❌ [{index}/{len(urls)}] File too large (exceeds 50MB even at 480p)."
            else:
                err_text = f"❌ [{index}/{len(urls)}] Error: {type(e).__name__}"
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=err_text)
            except Exception:
                pass
            fail_count += 1

        await asyncio.sleep(1.5)

    try:
        await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except Exception:
        pass

    await bot.send_message(
        chat_id=chat_id,
        text=f"🏁 **Batch Processing Complete!**\n✅ Successful: {success_count}\n❌ Failed/Skipped: {fail_count}"
    )

# --- UNIVERSAL MEDIA LINK & BATCH TEXT LISTENER HANDLER ---
async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    
    if not extracted_urls:
        return

    if len(extracted_urls) == 1:
        url = extracted_urls[0]
        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            await update.message.reply_text("❌ **YouTube downloads are temporarily paused for maintenance.** Please share links from other supported websites instead!")
            return

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
            status_msg = await update.message.reply_text(f"📥 **Downloading media...** ({display_left} free downloads remaining for today)")
            
            try:
                file_path, resolution, size_str = download_video_ytdlp(url)
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'rb') as media_file:
                        sent_media = await context.bot.send_video(
                            chat_id=chat_id,
                            video=media_file,
                            caption=(
                                "✨ **Download Successful!**\n"
                                f"📐 **Quality:** {resolution}\n"
                                f"📦 **Size:** {size_str}"
                            ),
                            parse_mode="Markdown"
                        )
                    
                    warning_msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text="⏳ **Safety Alert:** This downloaded file will automatically delete in **9 minutes** for security reasons. Watch or save it now!"
                    )
                    
                    messages_to_delete = [sent_media.message_id, warning_msg.message_id]
                    asyncio.create_task(schedule_deletion(context.bot, chat_id, messages_to_delete, DELETE_DELAY_TIME))

                    os.remove(file_path)
                    await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                else:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Failed to download media. File path not found.")
            except Exception as e:
                logger.error(f"Download error details: {e}", exc_info=True)
                if "FILE_TOO_LARGE" in str(e):
                    error_msg = "❌ The file is too large and Telegram won't allow it (exceeds the 50MB bot limit even at 480p)."
                else:
                    error_msg = str(e) if str(e) else type(e).__name__
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ Download error: {error_msg}")
                except Exception:
                    pass
        else:
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
    else:
        asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, extracted_urls))

# --- .TXT FILE UPLOAD BATCH HANDLER ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if not document.file_name or not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please upload a valid `.txt` file containing your links.")
        return

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        file_text = file_bytes.decode('utf-8', errors='ignore')

        extracted_urls = re.findall(r'https?://[^\s]+', file_text)
        if not extracted_urls:
            await update.message.reply_text("❌ No valid HTTP/HTTPS links found inside the uploaded `.txt` file.")
            return

        asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, extracted_urls))
    except Exception as e:
        logger.error(f"Error processing .txt file: {e}")
        await update.message.reply_text("❌ Failed to read the uploaded text file.")

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

        if msg_start == 0:
            await query.message.reply_text("✅ **Verification Successful!** Your 4 free downloads have been refilled for today. Send your video link now!")
            return

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

            asyncio.create_task(schedule_deletion(context.bot, user_id, forwarded_message_ids, DELETE_DELAY_TIME))

        except Exception as e:
            await query.message.reply_text(f"❌ Error fetching file bundle: {e}")

def run_telegram_bot():
    """Runs the Telegram bot in a dedicated event loop thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_bot():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        
        await asyncio.Event().wait()

    loop.run_until_complete(start_bot())

# --- MODULE-LEVEL STARTUP (CRITICAL FOR GUNICORN ON RENDER) ---
if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    print("Starting Telegram bot background thread...")
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

if __name__ == "__main__":
    print("Testing Flask web server on main thread...")
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
