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
    os.chmod(ffmpeg_path, 0o755)
except Exception as e:
    logging.error(f"Could not set ffmpeg permissions: {e}")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8863904451:AAFYl9yyjTvKTaliLR5iqTsvZr2tytFi3bk").strip()
ADMIN_ID = 6248570946
DETECTED_CHANNEL_ID = -1004347828512
PRIVATE_CHANNEL_ID = -1004347828512
TUTORIAL_MESSAGE_ID = 108
WEB_BASE_URL = "https://michaelbbc.pythonanywhere.com"
BRIDGE_URL = f"{WEB_BASE_URL}/bridge"
PUBLIC_CHANNEL_URL = "https://t.me/booksaufio"
PUBLIC_CHANNEL_USERNAME = "@booksaufio"
DELETE_DELAY_TIME = 540  # 9 minutes

CHANNELS_FILE = "user_channels.json"
LINKING_STATE_FILE = "linking_states.json"

active_batch_sessions = {}
pending_batch_payloads = {}
paused_batches = {}

web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is alive and running!", 200

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, timeout=5)
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")

def load_user_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_user_channels(channels):
    try:
        with open(CHANNELS_FILE, "w") as f:
            json.dump(channels, f)
    except Exception as e:
        logger.error(f"Error saving user channels: {e}")

def load_linking_states():
    if os.path.exists(LINKING_STATE_FILE):
        try:
            with open(LINKING_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_linking_states(states):
    try:
        with open(LINKING_STATE_FILE, "w") as f:
            json.dump(states, f)
    except Exception as e:
        logger.error(f"Error saving linking states: {e}")

async def schedule_deletion(bot, chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

def download_video_ytdlp(url: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    tiers = ["best", "best[height<=720]", "best[height<=480]"]
    
    for fmt in tiers:
        try:
            ydl_opts = {
                'format': fmt,
                'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                'max_filesize': 50 * 1024 * 1024,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4',
                'ffmpeg_location': ffmpeg_path,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            }
            
            # Check for cookies.txt
            if os.path.exists("cookies.txt"):
                ydl_opts['cookiefile'] = "cookies.txt"
            
            # 1. Extract info first to check size before downloading
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize and filesize > 50 * 1024 * 1024:
                    continue 
            
            # 2. Download if it passed the size check
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    if os.path.exists(base + ".mp4"):
                        filename = base + ".mp4"
                        
                if os.path.exists(filename):
                    file_size_bytes = os.path.getsize(filename)
                    if file_size_bytes > 50 * 1024 * 1024:
                        os.remove(filename)
                        continue 
                    
                    height = info.get('height', 'Unknown')
                    resolution = f"{height}p" if isinstance(height, int) else "HD/SD"
                    size_str = f"{file_size_bytes / (1024 * 1024):.1f}MB"
                    return filename, resolution, size_str
                    
        except Exception as e:
            logger.error(f"yt-dlp tier error for {url}: {e}")
            # Raise error to show the exact reason it failed
            if "Unsupported URL" in str(e) or "Video unavailable" in str(e) or "403" in str(e) or "Forbidden" in str(e) or "HTTP Error" in str(e):
                raise e
            continue
            
    raise ValueError("FILE_TOO_LARGE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "👋 **Welcome to the Media Downloader & Vault Bot!**\n\n"
            "📥 **What I can do:**\n"
            "I download media from websites, process **batch links**, AND unlock exclusive content vaults!\n\n"
            "💬 **How to Download:**\n"
            "• **Single Link:** Paste any link directly.\n"
            "• **Batch Links:** Paste multiple links or upload a `.txt` file.\n\n"
            "⚡ **Limit Notice:** Telegram limits bots to 50MB. Files larger than 50MB will be skipped.\n\n"
            "🎁 **Allowance:**\n"
            "• You get 4 free bundle downloads daily.\n"
            "• Batch downloads are limited to 20 per session. Refill by completing a quick sponsor timer!"
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
                return
        else:
            try:
                msg_start = int(clean_code)
                msg_end = msg_start
            except ValueError:
                return
    else:
        return

    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens = load_tokens()
    tokens[str(user_id)] = {
        "user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end),
        "clicked_ad": False, "verified": False, "expires": time.time() + 600
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
        "To unlock your video bundle:\n"
        "1️⃣ Click **Open Link & Watch Timer**, then click the Sponsor Page.\n"
        "2️⃣ Stay on the page for the countdown, close it, and click **Check & Get Files**!"
    )
    try:
        await context.bot.copy_message(
            chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID,
            caption=caption_text, parse_mode="Markdown", reply_markup=reply_markup
        )
    except Exception:
        await update.message.reply_text(text=caption_text, reply_markup=reply_markup, parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, start_index=0):
    if not urls:
        return

    success_count = 0
    fail_count = 0
    active_batch_sessions[user_id] = True

    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Batch Processing", callback_data="stop_batch")]])
    
    if start_index > 0:
        notice_text = f"▶️ **Resuming Batch...** Starting from link {start_index + 1} of {len(urls)}."
    else:
        notice_text = (
            f"📦 **Batch Processing Started:** Found **{len(urls)} links**.\n\n"
            "⚠️ **Notice:** Telegram limits bots to 50MB. Videos larger than this will be skipped.\n\n"
            "⏳ *Processing...*"
        )

    batch_notice = await bot.send_message(
        chat_id=chat_id,
        text=notice_text,
        reply_markup=stop_markup,
        parse_mode="Markdown"
    )

    for index, url in enumerate(urls[start_index:], start=start_index + 1):
        if not active_batch_sessions.get(user_id, False):
            break

        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Skipped YouTube (maintenance).")
            continue

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, timeout=5)
            if response.status_code == 200:
                res_data = response.json()
            else:
                await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Server error.")
                break
        except Exception:
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Connection error.")
            break

        if res_data.get("status") != "allowed":
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {
                "user_id": int(user_id), "msg_start": 0, "msg_end": 0,
                "clicked_ad": False, "verified": False, "expires": time.time() + 600
            }
            save_tokens(tokens)

            paused_batches[user_id] = {
                "urls": urls,
                "next_index": index - 1,
                "target_destination_id": target_destination_id,
                "chat_id": chat_id
            }

            keyboard = [
                [InlineKeyboardButton("🔓 Open Link & Refill Batch Limit", url=bridge_link)],
                [InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton("💜 Check & Refill Balance", callback_data="verify_user")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ **Batch Limit Reached! (Stopped at link {index} of {len(urls)})**\n\n"
                    "You have hit your limit. You must refill to continue batch downloading.\n\n"
                    "1️⃣ Click **Open Link & Refill Batch Limit** below.\n"
                    "2️⃣ Watch the sponsor timer.\n"
                    "3️⃣ Return here and click **Check & Refill Balance** to resume!"
                ),
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            break 

        status_msg = await bot.send_message(chat_id=chat_id, text=f"📥 [{index}/{len(urls)}] Downloading video...")

        try:
            file_path, resolution, size_str = download_video_ytdlp(url)
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as media_file:
                    sent_media = await bot.send_video(
                        chat_id=target_destination_id,
                        video=media_file,
                        caption=f"✨ **Batch Item {index}/{len(urls)}**\n📐 Quality: {resolution}\n📦 Size: {size_str}",
                        parse_mode="Markdown"
                    )
                
                if target_destination_id == chat_id:
                    warning_msg = await bot.send_message(
                        chat_id=target_destination_id,
                        text=f"⏳ [{index}/{len(urls)}] Safety Alert: This file will automatically delete in **9 minutes**."
                    )
                    asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                
                os.remove(file_path)
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}/{len(urls)}] Failed: File path not found.")
                fail_count += 1
        except Exception as e:
            logger.error(f"Batch item error: {e}")
            try:
                # --- NEW: Show exact HTTP error if possible ---
                if "FILE_TOO_LARGE" in str(e):
                    error_text = f"❌ [{index}/{len(urls)}] Failed: Video is larger than 50MB."
                elif "403" in str(e):
                    error_text = f"❌ [{index}/{len(urls)}] Failed: HTTP 403 Forbidden (Site blocked bot)."
                elif "404" in str(e):
                    error_text = f"❌ [{index}/{len(urls)}] Failed: HTTP 404 Not Found."
                elif "Unsupported URL" in str(e) or "Video unavailable" in str(e):
                    error_text = f"❌ [{index}/{len(urls)}] Failed: Site restricted download."
                else:
                    # Show a snippet of the actual error
                    short_err = str(e).split(";")[0][:40] 
                    error_text = f"❌ [{index}/{len(urls)}] Failed: {short_err}..."
                
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=error_text)
            except Exception:
                pass
            fail_count += 1
        
        await asyncio.sleep(4) 

    if user_id in active_batch_sessions:
        del active_batch_sessions[user_id]

    try:
        await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except Exception:
        pass

    if user_id not in paused_batches:
        if target_destination_id != chat_id:
            dest_text = f"📢 **{success_count} videos forwarded to your private channel!**"
        else:
            dest_text = f"📥 **{success_count} videos sent to this chat.**"

        await bot.send_message(
            chat_id=chat_id,
            text=f"🏁 **Batch Finished!**\n✅ Success: {success_count}\n❌ Failed/Skipped: {fail_count}\n\n{dest_text}",
            parse_mode="Markdown"
        )

async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    linking_states = load_linking_states()
    if linking_states.get(str(user_id)) == "waiting_for_channel":
        if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
            f_chat = update.message.forward_origin.chat
            user_channels = load_user_channels()
            user_channels[str(user_id)] = f_chat.id
            save_user_channels(user_channels)
            del linking_states[str(user_id)]
            save_linking_states(linking_states)
            keyboard = [[InlineKeyboardButton("🔄 Change Linked Channel", callback_data="change_channel")]]
            await update.message.reply_text(
                f"✅ **Channel Linked!**\n📢 {f_chat.title}\n🆔 `{f_chat.id}`",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
            return
        else:
            await update.message.reply_text("❌ Forward a message from your channel to link it.")
            return

    if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
        f_chat = update.message.forward_origin.chat
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        keyboard = [[InlineKeyboardButton("🔄 Change Linked Channel", callback_data="change_channel")]]
        await update.message.reply_text(
            f"✅ **Channel Linked!**\n📢 {f_chat.title}\n🆔 `{f_chat.id}`",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    if not extracted_urls:
        return

    if len(extracted_urls) == 1:
        url = extracted_urls[0]
        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            await update.message.reply_text("❌ YouTube is paused.")
            return

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": False}, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except Exception:
            await update.message.reply_text("❌ Error connecting to server.")
            return

        if res_data.get("status") == "allowed":
            remaining = res_data.get("left", 0)
            status_msg = await update.message.reply_text(f"📥 **Downloading...** ({remaining} free downloads left)")
            try:
                file_path, resolution, size_str = download_video_ytdlp(url)
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'rb') as media_file:
                        sent_media = await context.bot.send_video(
                            chat_id=chat_id, video=media_file,
                            caption=f"✨ **Download Successful!**\n📐 Quality: {resolution}\n📦 Size: {size_str}",
                            parse_mode="Markdown"
                        )
                    warning_msg = await context.bot.send_message(chat_id=chat_id, text="⏳ **Auto-deletes in 9 minutes.**")
                    asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                    os.remove(file_path)
                    await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            except Exception as e:
                if "FILE_TOO_LARGE" in str(e):
                    error_msg = "❌ Video is larger than 50MB."
                elif "403" in str(e):
                    error_msg = "❌ HTTP 403 Forbidden (Site blocked bot)."
                elif "404" in str(e):
                    error_msg = "❌ HTTP 404 Not Found."
                else:
                    error_msg = "❌ Site restricted download."
                await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=error_msg)
        else:
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)
            keyboard = [
                [InlineKeyboardButton("🔓 Open Link & Refill", url=bridge_link)],
                [InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton("💜 Check Balance", callback_data="verify_user")]
            ]
            await update.message.reply_text("⚠️ **Limit Reached!** Refill to continue.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                keyboard = [[InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)]]
                await update.message.reply_text(
                    "⚠️ **Channel Required!**\n\nYou must join our public channel before using the Batch Downloader.\n\n1. Join the channel below.\n2. Send your links again.",
                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                )
                return
        except Exception:
            await update.message.reply_text("⚠️ Please join the public channel to use batch downloads.")
            return

        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton("📥 Download in Chat", callback_data=f"dest_chat_{payload_key}")],
            [InlineKeyboardButton("📢 Forward to Private Channel", callback_data=f"dest_chan_{payload_key}")]
        ]
        await update.message.reply_text(
            f"📦 **Batch Detected ({len(extracted_urls)} links)**\n\nWhere would you like to send these?",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if not document.file_name or not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please upload a valid `.txt` file.")
        return

    try:
        member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
        if member.status not in ["creator", "administrator", "member"]:
            keyboard = [[InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)]]
            await update.message.reply_text(
                "⚠️ **Channel Required!**\n\nYou must join our public channel before using the Batch Downloader.",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
            return
    except Exception:
        await update.message.reply_text("⚠️ Please join the public channel to use batch downloads.")
        return

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        file_text = file_bytes.decode('utf-8', errors='ignore')
        extracted_urls = re.findall(r'https?://[^\s]+', file_text)
        
        if not extracted_urls:
            await update.message.reply_text("❌ No links found inside the file.")
            return

        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton("📥 Download in Chat", callback_data=f"dest_chat_{payload_key}")],
            [InlineKeyboardButton("📢 Forward to Private Channel", callback_data=f"dest_chan_{payload_key}")]
        ]
        await update.message.reply_text(
            f"📄 **File Detected ({len(extracted_urls)} links)**\n\nWhere would you like to send these?",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"File error: {e}")
        await update.message.reply_text("❌ Failed to read the file.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID:
        return
    tokens = load_tokens()
    total = len(tokens)
    clicked = sum(1 for d in tokens.values() if d.get("clicked_ad", False))
    verified = sum(1 for d in tokens.values() if d.get("verified", False))
    await update.message.reply_text(f"📊 **STATS**\nTotal: {total}\nClicked Ad: {clicked}\nVerified: {verified}\nPending: {total-verified}", parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "stop_batch":
        active_batch_sessions[user_id] = False
        await query.answer("🛑 Stopping...", show_alert=True)
        try:
            await query.edit_message_text("🛑 **Batch Stopped.**")
        except Exception:
            pass
        return

    if data == "resume_batch":
        paused = paused_batches.pop(user_id, None)
        if not paused:
            await query.answer("❌ Resume session expired.", show_alert=True)
            return
        
        await query.answer("▶️ Resuming batch...", show_alert=False)
        await query.message.delete()
        asyncio.create_task(process_url_batch(
            context.bot, user_id, paused["chat_id"], paused["target_destination_id"], 
            paused["urls"], start_index=paused["next_index"]
        ))
        return

    if data.startswith("dest_chat_") or data.startswith("dest_chan_"):
        parts = data.split("_", 2)
        action_type = parts[1]
        payload_key = parts[2]
        urls = pending_batch_payloads.pop(payload_key, None)
        
        if not urls:
            await query.answer("❌ Session expired. Resend links.", show_alert=True)
            return

        chat_id = query.message.chat_id
        if action_type == "chat":
            await query.answer("📥 Streaming to chat...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls))
        elif action_type == "chan":
            user_channels = load_user_channels()
            target_channel_id = user_channels.get(str(user_id))
            if not target_channel_id:
                await query.answer("❌ No private channel linked!", show_alert=True)
                linking_states = load_linking_states()
                linking_states[str(user_id)] = "waiting_for_channel"
                save_linking_states(linking_states)
                await query.message.edit_text("📦 **Setup Required!**\n\n1. Make bot Admin in your channel.\n2. **Forward any message** from the channel here.", parse_mode="Markdown")
                return
            await query.answer("📢 Forwarding to channel...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, target_channel_id, urls))
        return

    if data == "change_channel":
        linking_states = load_linking_states()
        linking_states[str(user_id)] = "waiting_for_channel"
        save_linking_states(linking_states)
        await query.answer("🔄 Mode activated!")
        await query.message.reply_text("🔄 **Change Channel**\n\nForward a message from your new channel here.", parse_mode="Markdown")
        return

    if data == "verify_user":
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                await query.answer("❌ Join our public channel first!", show_alert=True)
                return
        except Exception:
            await query.answer("⚠️ Join the channel before proceeding!", show_alert=True)
            return

        tokens = load_tokens()
        user_str = str(user_id)
        if user_str not in tokens:
            await query.answer("❌ Session expired. Try again.", show_alert=True)
            return
        
        token_data = tokens[user_str]
        if not token_data.get("verified", False):
            await query.answer("❌ Finish the timer first!", show_alert=True)
            return

        msg_start = token_data.get("msg_start", 0)
        msg_end = token_data.get("msg_end", 0)
        del tokens[user_str]
        save_tokens(tokens)
        await query.answer("✅ Verified!")

        if user_id in paused_batches:
            keyboard = [[InlineKeyboardButton("▶️ Resume Batch from where I stopped", callback_data="resume_batch")]]
            await query.message.reply_text(
                "✅ **Verification Successful!** Your batch limit has been refilled.\n\n"
                "Click the button below to continue downloading your remaining links!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return

        if msg_start == 0:
            await query.message.reply_text("✅ **Refilled!** You can download again now.")
            return

        await query.message.reply_text("✅ **Verified!** Fetching bundle...")
        forwarded_ids = []
        try:
            for target_msg_id in range(msg_start, msg_end + 1):
                fwd = await context.bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=target_msg_id)
                forwarded_ids.append(fwd.message_id)
                asyncio.sleep(0.2)
            warn = await context.bot.send_message(chat_id=user_id, text="⏳ **Auto-deletes in 9 minutes.**")
            forwarded_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, forwarded_ids, DELETE_DELAY_TIME))
        except Exception as e:
            await query.message.reply_text(f"❌ Error fetching bundle: {e}")

def run_telegram_bot():
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

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    print("Starting Telegram bot thread...")
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    print("Testing Flask server...")
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)