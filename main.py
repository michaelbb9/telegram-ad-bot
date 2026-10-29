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
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
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
HELP_CHANNEL_URL = "https://t.me/faqandaupport"
DELETE_DELAY_TIME = 540  # 9 minutes

PROXY_URL = None 

CHANNELS_FILE = "user_channels.json"
LINKING_STATE_FILE = "linking_states.json"

active_batch_sessions = {}
pending_batch_payloads = {}
paused_batches = {}
pending_single_links = {}

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

def parse_netscape_cookies(cookiefile):
    cookies_dict = {}
    if cookiefile and os.path.exists(cookiefile):
        try:
            with open(cookiefile, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        domain, flag, path, secure, expiration, name, value = parts[:7]
                        cookies_dict[name] = value
        except Exception as e:
            logger.error(f"Error parsing cookies: {e}")
    return cookies_dict

# --- NEW: ADVANCED IMAGE SCRAPER (MOBILE API TRICK) ---
def scrape_html_images(url, cookiefile=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    cookies_dict = parse_netscape_cookies(cookiefile)

    # TRICK 1: Try the Mobile Facebook API
    if "facebook.com" in url.lower():
        try:
            mobile_url = url.replace('www.facebook.com', 'm.facebook.com').replace('web.facebook.com', 'm.facebook.com')
            res = requests.get(mobile_url, headers=headers, cookies=cookies_dict, timeout=15, allow_redirects=True)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Mobile API often puts the image in og:image or a specific meta tag
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                return og_img['content']
                
            # Or look for the specific m.facebook image link
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and ('scontent' in src or 'fbcdn' in src):
                    return src
        except Exception as e:
            logger.error(f"Mobile FB Scrape error: {e}")

    # TRICK 2: Standard Scrape (for other sites)
    try:
        res = requests.get(url, headers=headers, cookies=cookies_dict, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            return og_img['content']
            
        tw_img = soup.find('meta', name='twitter:image')
        if tw_img and tw_img.get('content'):
            return tw_img['content']
            
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and ('scontent' in src or 'fbcdn' in src):
                return src
                
    except Exception as e:
        logger.error(f"Standard Scrape error: {e}")
        
    return None

# --- UNIVERSAL DOWNLOAD ENGINE ---
def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    url_lower = url.lower()
    
    http_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    cookiefile = None
    if "tiktok.com" in url_lower and os.path.exists("tiktok_cookies.txt"):
        cookiefile = "tiktok_cookies.txt"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        if os.path.exists("twitter_cookies.txt"):
            cookiefile = "twitter_cookies.txt"
    elif "facebook.com" in url_lower and os.path.exists("facebook_cookies.txt"):
        cookiefile = "facebook_cookies.txt"
    elif "naijafap.com" in url_lower and os.path.exists("naijafap_cookies.txt"):
        cookiefile = "naijafap_cookies.txt"
    elif os.path.exists("cookies.txt"):
        cookiefile = "cookies.txt"

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': http_headers,
        'proxy': PROXY_URL if PROXY_URL else None,
    }
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    # --- 1. AUDIO (MP3) ---
    if download_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': ffmpeg_path,
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base_name = os.path.splitext(ydl.prepare_filename(info))[0]
            mp3_path = f"{base_name}.mp3"
            if os.path.exists(mp3_path):
                size_mb = f"{os.path.getsize(mp3_path) / (1024 * 1024):.1f}MB"
                return [mp3_path], "Audio MP3", size_mb
        raise ValueError("FILE_NOT_FOUND")

    # --- 2. SUBTITLES ---
    elif download_type == 'subtitles':
        ydl_opts.update({
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'subtitlesformat': 'srt',
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base_name = os.path.splitext(ydl.prepare_filename(info))[0]
            srt_path = f"{base_name}.en.srt"
            if os.path.exists(srt_path):
                return [srt_path], "Subtitles (EN)", "Text File"
            else:
                srt_path = f"{base_name}.en.vtt"
                if os.path.exists(srt_path):
                    return [srt_path], "Subtitles (EN)", "Text File"
        raise ValueError("NO_SUBTITLES")

    # --- 3. IMAGES ---
    elif download_type == 'images':
        img_url = scrape_html_images(url, cookiefile)
        if img_url:
            try:
                img_data = requests.get(img_url, headers=http_headers, timeout=15).content
                ext = 'jpg'
                if '.png' in img_url: ext = 'png'
                elif '.webp' in img_url: ext = 'webp'
                
                img_path = os.path.join(output_dir, f"image_{int(time.time())}.{ext}")
                with open(img_path, 'wb') as handler:
                    handler.write(img_data)
                
                if os.path.getsize(img_path) > 1000:
                    size_mb = f"{os.path.getsize(img_path) / (1024 * 1024):.1f}MB"
                    return [img_path], "Image", size_mb
            except Exception as e:
                logger.error(f"Direct image download error: {e}")
        
        raise ValueError("NO_IMAGES")

    # --- 4. VIDEO ---
    else:
        tiers = [
            "bestvideo+bestaudio/best", 
            "best[height<=1080]", 
            "best[height<=720]", 
            "best[height<=480]", 
            "best"
        ]

        for fmt in tiers:
            try:
                ydl_opts.update({
                    'format': fmt,
                    'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'ffmpeg_location': ffmpeg_path,
                })

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
                        return [filename], resolution, size_str
            except Exception as e:
                logger.error(f"Video tier error ({fmt}): {e}")
                if "Unsupported URL" in str(e) or "Video unavailable" in str(e) or "403" in str(e) or "HTTP Error" in str(e):
                    raise e
                continue
                
        raise ValueError("FILE_TOO_LARGE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "🚀 **Welcome to the Ultimate Media Downloader Bot!** 🚀\n\n"
            "I am your all-in-one Swiss Army Knife for social media. Here is everything I can do:\n\n"
            "🎬 **Video Downloader:** Paste any link (TikTok, Insta, Twitter, FB) to get the video in the highest quality possible.\n\n"
            "🎵 **Audio / MP3 Extractor:** Turn any video into an MP3 audio file instantly.\n\n"
            "🖼️ **Image / Gallery Saver:** Download photos from Instagram posts, Facebook, or Pinterest.\n\n"
            "📝 **Subtitle Extractor:** Grab the subtitle text files (SRT) from videos.\n\n"
            "📦 **Massive Batch Downloader:** Paste up to 100+ links at once, or upload a `.txt` file.\n\n"
            "⚠️ **Rules & Limits:**\n"
            "• Telegram limits bots to 50MB per file. Anything bigger will automatically step down to a lower quality that fits.\n"
            "• You get 20 free batch downloads. After that, you must watch a quick 20-second sponsor timer to refill.\n\n"
            "👉 **Just paste a link to get started!**"
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
        notice_text = f"📦 **Batch Processing Started:** Found **{len(urls)} links**.\n\n⏳ *Processing...*"

    batch_notice = await bot.send_message(chat_id=chat_id, text=notice_text, reply_markup=stop_markup, parse_mode="Markdown")

    consecutive_fails = 0

    for index, url in enumerate(urls[start_index:], start=start_index + 1):
        if not active_batch_sessions.get(user_id, False):
            break

        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Skipped YouTube (maintenance).")
            continue

        if consecutive_fails >= 3:
            cooldown_msg = await bot.send_message(chat_id=chat_id, text=f"⏳ **Site Rate Limit Detected.** Pausing for 60 seconds...")
            await asyncio.sleep(60)
            try: await cooldown_msg.delete()
            except: pass
            consecutive_fails = 0

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except Exception:
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Connection error.")
            break

        if res_data.get("status") != "allowed":
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)

            paused_batches[user_id] = {"urls": urls, "next_index": index - 1, "target_destination_id": target_destination_id, "chat_id": chat_id}

            keyboard = [
                [InlineKeyboardButton("🔓 Open Link & Refill Batch Limit", url=bridge_link)],
                [InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton("💜 Check & Refill Balance", callback_data="verify_user")]
            ]
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ **Batch Limit Reached! (Stopped at link {index} of {len(urls)})**\n\nRefill to continue:",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
            break 

        status_msg = await bot.send_message(chat_id=chat_id, text=f"📥 [{index}/{len(urls)}] Downloading video...")

        try:
            file_paths, resolution, size_str = download_media_engine(url, 'video')
            
            if file_paths and os.path.exists(file_paths[0]):
                file_path = file_paths[0]
                with open(file_path, 'rb') as media_file:
                    sent_media = await bot.send_video(
                        chat_id=target_destination_id,
                        video=media_file,
                        caption=f"✨ **Batch Item {index}/{len(urls)}**\n📐 Quality: {resolution}\n📦 Size: {size_str}",
                        parse_mode="Markdown"
                    )
                
                if target_destination_id == chat_id:
                    warning_msg = await bot.send_message(chat_id=target_destination_id, text=f"⏳ Deletes in 9 minutes.")
                    asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                
                os.remove(file_path)
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
                consecutive_fails = 0 
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}/{len(urls)}] Failed.")
                fail_count += 1
                consecutive_fails += 1
        except Exception as e:
            consecutive_fails += 1
            try:
                if "FILE_TOO_LARGE" in str(e):
                    error_text = f"❌ [{index}/{len(urls)}] Failed: Video > 50MB."
                elif "403" in str(e) or "Unsupported URL" in str(e):
                    error_text = f"❌ [{index}/{len(urls)}] Failed: Site blocked bot or link private."
                else:
                    error_text = f"❌ [{index}/{len(urls)}] Download failed."
                
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=error_text)
            except Exception:
                pass
            fail_count += 1
        
        await asyncio.sleep(4) 

    if user_id in active_batch_sessions:
        del active_batch_sessions[user_id]

    try: await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except: pass

    if user_id not in paused_batches:
        dest_text = f"📢 **{success_count} videos forwarded!**" if target_destination_id != chat_id else f"📥 **{success_count} videos sent here.**"
        await bot.send_message(chat_id=chat_id, text=f"🏁 **Batch Finished!**\n✅ Success: {success_count}\n❌ Failed: {fail_count}\n\n{dest_text}", parse_mode="Markdown")


async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if active_batch_sessions.get(user_id, False):
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    if not extracted_urls:
        return

    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton("📥 Download in Chat", callback_data=f"dest_chat_{payload_key}")],
            [InlineKeyboardButton("📢 Forward to Private Channel", callback_data=f"dest_chan_{payload_key}")]
        ]
        await update.message.reply_text(f"📦 **Batch Detected ({len(extracted_urls)} links)**\nWhere to send these?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    url = extracted_urls[0]
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        await update.message.reply_text("❌ YouTube is paused.")
        return

    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url

    keyboard = [
        [InlineKeyboardButton("🎬 Video (MP4)", callback_data=f"fmt_vid_{payload_key}")],
        [InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"fmt_aud_{payload_key}")],
        [InlineKeyboardButton("🖼️ Images (Gallery)", callback_data=f"fmt_img_{payload_key}")],
        [InlineKeyboardButton("📝 Subtitles (SRT)", callback_data=f"fmt_sub_{payload_key}")]
    ]
    await update.message.reply_text(
        "👇 **What would you like to download?**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if active_batch_sessions.get(user_id, False):
        return

    if not document.file_name or not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please upload a valid `.txt` file.")
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
        await update.message.reply_text(f"📄 **File Detected ({len(extracted_urls)} links)**\nWhere to send these?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"File error: {e}")
        await update.message.reply_text("❌ Failed to read the file.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    tokens = load_tokens()
    await update.message.reply_text(f"📊 **STATS**\nTotal Users: {len(tokens)}", parse_mode="Markdown")


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("fmt_"):
        parts = data.split("_", 2)
        fmt_type = parts[1] 
        payload_key = parts[2]
        
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("❌ Session expired. Resend link.", show_alert=True)
            return
            
        await query.answer("Processing...")
        await query.message.delete()

        dl_type = 'video'
        if fmt_type == 'aud': dl_type = 'audio'
        elif fmt_type == 'img': dl_type = 'images'
        elif fmt_type == 'sub': dl_type = 'subtitles'

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": False}, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text="❌ Server connection error.")
            return

        if res_data.get("status") != "allowed":
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)
            keyboard = [
                [InlineKeyboardButton("🔓 Open Link & Refill", url=bridge_link)],
                [InlineKeyboardButton("📢 Join Public Channel", url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton("💜 Check Balance", callback_data="verify_user")]
            ]
            await context.bot.send_message(chat_id=chat_id, text="⚠️ **Limit Reached!** Refill to continue.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        status_msg = await context.bot.send_message(chat_id=chat_id, text=f"📥 **Fetching {dl_type}... Please wait.**")

        try:
            file_paths, resolution, size_str = download_media_engine(url, dl_type)
            
            if not file_paths:
                raise ValueError("FILE_NOT_FOUND")

            if dl_type == 'images':
                media_group = []
                for p in file_paths:
                    media_group.append(InputMediaPhoto(media=open(p, 'rb')))
                
                sent_media = await context.bot.send_media_group(chat_id=chat_id, media=media_group)
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ **{len(file_paths)} Images received. Auto-deletes in 9 minutes.**")
                
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [m.message_id for m in sent_media] + [warning_msg.message_id], DELETE_DELAY_TIME))
                for p in file_paths: os.remove(p)
                
            elif dl_type == 'audio':
                file_path = file_paths[0]
                with open(file_path, 'rb') as f:
                    sent_media = await context.bot.send_audio(chat_id=chat_id, audio=f, title="Extracted Audio", caption=f"🎵 **Audio Extracted**\n📦 Size: {size_str}", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text="⏳ **Auto-deletes in 9 minutes.**")
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_path)
                
            elif dl_type == 'subtitles':
                file_path = file_paths[0]
                with open(file_path, 'rb') as f:
                    sent_media = await context.bot.send_document(chat_id=chat_id, document=f, caption=f"📝 **Subtitles Extracted**", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text="⏳ **Auto-deletes in 9 minutes.**")
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_path)
                
            else:
                file_path = file_paths[0]
                with open(file_path, 'rb') as f:
                    sent_media = await context.bot.send_video(chat_id=chat_id, video=f, caption=f"✨ **Video Downloaded**\n📐 Quality: {resolution}\n📦 Size: {size_str}", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text="⏳ **Auto-deletes in 9 minutes.**")
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_path)

            await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)

        except Exception as e:
            logger.error(f"Single download error: {e}")
            error_msg = "❌ Failed to download. Link might be private, or site blocked the bot."
            if "FILE_TOO_LARGE" in str(e): 
                error_msg = "❌ File exceeds Telegram's 50MB limit (even at lowest quality)."
            elif "NO_SUBTITLES" in str(e): 
                error_msg = "❌ No English subtitles found for this video."
            elif "NO_IMAGES" in str(e): 
                error_msg = "❌ No images found at this link. Try 'Video' format instead."
            
            help_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Ask for Help", url=HELP_CHANNEL_URL)]])
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=error_msg, reply_markup=help_keyboard)
        return

    if data == "stop_batch":
        active_batch_sessions[user_id] = False
        await query.answer("🛑 Stopping...", show_alert=True)
        try: await query.edit_message_text("🛑 **Batch Stopped.**")
        except: pass
        return

    if data == "resume_batch":
        paused = paused_batches.pop(user_id, None)
        if not paused:
            await query.answer("❌ Resume session expired.", show_alert=True)
            return
        await query.answer("▶️ Resuming batch...", show_alert=False)
        await query.message.delete()
        asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], start_index=paused["next_index"]))
        return

    if data.startswith("dest_chat_") or data.startswith("dest_chan_"):
        parts = data.split("_", 2)
        action_type = parts[1]
        payload_key = parts[2]
        urls = pending_batch_payloads.pop(payload_key, None)
        
        if not urls:
            await query.answer("❌ Session expired.", show_alert=True)
            return

        if action_type == "chat":
            await query.answer("📥 Streaming to chat...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls))
        elif action_type == "chan":
            user_channels = load_user_channels()
            target_channel_id = user_channels.get(str(user_id))
            if not target_channel_id:
                await query.answer("❌ No private channel linked!", show_alert=True)
                await query.message.edit_text("📦 **Setup Required!**\n\n1. Make bot Admin in your channel.\n2. **Forward any message** from the channel here.", parse_mode="Markdown")
                return
            await query.answer("📢 Forwarding to channel...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, target_channel_id, urls))
        return

    if data == "verify_user":
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                await query.answer("❌ Join public channel first!", show_alert=True)
                return
        except Exception:
            await query.answer("⚠️ Join the channel first!", show_alert=True)
            return

        tokens = load_tokens()
        user_str = str(user_id)
        if user_str not in tokens: return
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
            keyboard = [[InlineKeyboardButton("▶️ Resume Batch", callback_data="resume_batch")]]
            await query.message.reply_text("✅ **Verified!** Your batch limit has been refilled.\nClick below to resume!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        if msg_start == 0:
            await query.message.reply_text("✅ **Refilled!** You can download again.")
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
            await query.message.reply_text(f"❌ Error: {e}")


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
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)