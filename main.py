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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
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
DELETE_DELAY_TIME = 540 

PROXY_URL = None 
CHANNELS_FILE = "user_channels.json"
LINKING_STATE_FILE = "linking_states.json"
LANG_FILE = "user_languages.json"
UPLOADS_FILE = "fan_uploads.json" 
UPLOAD_LIMITS_FILE = "upload_limits.json" # NEW: Tracks 5 uploads per day

active_batch_sessions = {}
pending_batch_payloads = {}
paused_batches = {}
pending_single_links = {}

LANGUAGES = {
    "en": {
        "welcome": "🚀 **Welcome to the Ultimate Media Downloader & Vault Bot!** 🚀\n\nI am your all-in-one Swiss Army Knife. Here is everything I can do:\n\n🎬 **Video Downloader:** Paste any link for HD videos.\n🎵 **Audio / MP3 Extractor:** Turn any video into an MP3.\n🖼️ **Image / Gallery Saver:** Download photos.\n📝 **Subtitle Extractor:** Grab SRT files.\n📦 **Massive Batch Downloader:** Paste up to 100+ links. Choose Video, Audio, or Images!\n💎 **Exclusive Vaults:** Unlock premium curated video bundles.\n📤 **Uploads:** Send us files/images directly (Max 5 per day)!\n\n⚠️ **Rules & Limits:**\n• Telegram limits bots to 50MB per file.\n• You get 20 free batch downloads. After that, watch a 20-second sponsor timer to refill.\n\n👉 **Just paste a link to get started!**",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **What would you like to download?**",
        "fetching": "📥 **Fetching {}... Please wait.**",
        "error_generic": "❌ Failed to download. Link might be private, or site blocked the bot.",
        "error_50mb": "❌ File exceeds Telegram's 50MB limit.", "error_no_img": "❌ No images found at this link.",
        "deletes_in_9": "⏳ **Auto-deletes in 9 minutes.**", "images_received": "⏳ **{} Images received. Auto-deletes in 9 minutes.**",
        "select_lang": "🌍 Please select your language:", "lang_set": "✅ Language set to English!",
        "batch_detected": "📦 **Batch Detected ({} links)**\nWhat format do you want?", "batch_dest": "📦 **Where to send these files?**",
        "btn_chat": "📥 Download in Chat", "btn_chan": "📢 Forward to Private Channel",
        "limit_reached": "⚠️ **Limit Reached!** Refill to continue.", "refill_btn": "🔓 Open Link & Refill",
        "join_btn": "📢 Join Public Channel", "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached! (Stopped at link {} of {})**\n\nRefill to continue:",
        "batch_start": "📦 **Batch Processing Started:** Downloading {} **{} files**.\n\n⏳ *Processing...*",
        "batch_done": "🏁 **Batch Finished!**\n✅ Success: {}\n❌ Failed: {}\n\n📥 **{} files sent here.**",
        "batch_done_chan": "🏁 **Batch Finished!**\n✅ Success: {}\n❌ Failed: {}\n\n📢 **{} files forwarded!**",
        "dl_video": "📥 Downloading video...", "dl_audio": "📥 Extracting audio...", "dl_image": "📥 Scraping images...", "dl_sub": "📥 Fetching subtitles...",
        "failed_50": "❌ Failed: File > 50MB.", "failed_blocked": "❌ Failed: Site blocked bot or link private.", "failed_generic": "❌ Download failed.",
        "menu_lang": "🌍 Language", "menu_stats": "📊 My Stats", "menu_help": "📢 FAQ / Help", "menu_join": "📢 Join Channel",
        "menu_uploads": "🍿 Fan Uploads", "menu_upload": "📤 Upload File",
        "admin_upload_prompt": "📂 **Fan Uploads Inbox**\n\nHere is what your fans have sent you recently:",
        "user_upload_prompt": "📤 **Upload File**\n\nSend me any video, image, or file. I will forward it directly to the Admin (anonymously if you wish!).\n\n⚠️ *Limit: 5 uploads per 24 hours.*",
        "upload_success_user": "✅ **File Received!**\nYour upload has been anonymously sent to the Admin.",
        "upload_limit_reached": "⚠️ **Upload Limit Reached!**\nYou can only send 5 files every 24 hours. Please try again tomorrow.",
        "no_uploads": "📭 No fan uploads yet. When users send files, they will appear here.",
        "stats_msg": "📊 **Your Stats:**\n\n• Normal Downloads Left: {}\n• Batch Downloads Left: {}\n\n*Stats reset every 24 hours.*"
    }
}

web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is alive and running!", 200

def load_json_file(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception: pass
    return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

def get_lang(user_id):
    langs = load_json_file(LANG_FILE)
    return langs.get(str(user_id), "en")

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", timeout=5)
        if response.status_code == 200: return response.json()
    except Exception as e: logger.error(f"Error loading tokens: {e}")
    return {}

def save_tokens(tokens):
    try: requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, timeout=5)
    except Exception as e: logger.error(f"Error saving tokens: {e}")

def load_user_channels(): return load_json_file(CHANNELS_FILE)
def save_user_channels(channels): save_json_file(CHANNELS_FILE, channels)
def load_linking_states(): return load_json_file(LINKING_STATE_FILE)
def save_linking_states(states): save_json_file(LINKING_STATE_FILE, states)

async def schedule_deletion(bot, chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try: await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception: pass

def scrape_html_images(url, cookiefile=None):
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9'}
    cookies = None
    if cookiefile and os.path.exists(cookiefile):
        try:
            import http.cookiejar
            cj = http.cookiejar.MozillaCookieJar(cookiefile)
            cj.load(ignore_discard=True, ignore_expires=True)
            cookies = {cookie.name: cookie.value for cookie in cj}
        except: pass
    try:
        res = requests.get(url, headers=headers, cookies=cookies, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(res.text, 'html.parser')
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'): return og_img['content']
        tw_img = soup.find('meta', name='twitter:image')
        if tw_img and tw_img.get('content'): return tw_img['content']
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and ('scontent' in src or 'fbcdn' in src): return src
    except Exception as e: logger.error(f"HTML Scrape error: {e}")
    return None

def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    url_lower = url.lower()
    http_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept-Language': 'en-US,en;q=0.9'}
    cookiefile = None
    if "tiktok.com" in url_lower and os.path.exists("tiktok_cookies.txt"): cookiefile = "tiktok_cookies.txt"
    elif "twitter.com" in url_lower or "x.com" in url_lower: cookiefile = "twitter_cookies.txt" if os.path.exists("twitter_cookies.txt") else None
    elif "facebook.com" in url_lower: cookiefile = "facebook_cookies.txt" if os.path.exists("facebook_cookies.txt") else None
    elif "naijafap.com" in url_lower: cookiefile = "naijafap_cookies.txt" if os.path.exists("naijafap_cookies.txt") else None
    elif os.path.exists("cookies.txt"): cookiefile = "cookies.txt"

    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if cookiefile: ydl_opts['cookiefile'] = cookiefile

    if download_type == 'audio':
        ydl_opts.update({'format': 'bestaudio/best', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'ffmpeg_location': ffmpeg_path})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            path = f"{base}.mp3"
            if os.path.exists(path): return [path], "Audio MP3", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("FILE_NOT_FOUND")
    elif download_type == 'subtitles':
        ydl_opts.update({'skip_download': True, 'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': ['en'], 'subtitlesformat': 'srt', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s')})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            for ext in ['.en.srt', '.en.vtt']:
                if os.path.exists(base+ext): return [base+ext], "Subtitles", "Text"
        raise ValueError("NO_SUBTITLES")
    elif download_type == 'images':
        img_url = scrape_html_images(url, cookiefile)
        if img_url:
            img_data = requests.get(img_url, headers=http_headers, timeout=15).content
            ext = '.png' if '.png' in img_url else '.webp' if '.webp' in img_url else '.jpg'
            path = os.path.join(output_dir, f"image_{int(time.time())}{ext}")
            with open(path, 'wb') as f: f.write(img_data)
            if os.path.getsize(path) > 1000: return [path], "Image", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("NO_IMAGES")
    else:
        for fmt in ["bestvideo+bestaudio/best", "best[height<=1080]", "best[height<=720]", "best[height<=480]", "best"]:
            try:
                ydl_opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path})
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"): path = os.path.splitext(path)[0]+".mp4"
                    if os.path.exists(path):
                        if os.path.getsize(path) > 50*1024*1024: os.remove(path); continue
                        return [path], f"{info.get('height', 'HD')}p", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
            except Exception as e:
                if "Unsupported URL" in str(e) or "403" in str(e): raise e
                continue
        raise ValueError("FILE_TOO_LARGE")

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES[lang_code]
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton(t["menu_upload"])]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(t["menu_uploads"])])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_lang(update.message.from_user.id)
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"), InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang_hi"), InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]
    ]
    await update.message.reply_text(LANGUAGES[lang]["select_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if not args:
        await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID), parse_mode="Markdown")
        return

    video_code = args[0]
    if video_code.startswith("vid"):
        clean_code = video_code.replace("vid", "")
        if "to" in clean_code:
            try:
                parts = clean_code.split("to")
                msg_start, msg_end = int(parts[0]), int(parts[1])
            except (ValueError, IndexError): return
        else:
            try:
                msg_start = int(clean_code)
                msg_end = msg_start
            except ValueError: return
    else: return

    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens = load_tokens()
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch Timer", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    caption_text = "👇 **CONTENT LOCKED** 👇\n\nWatch the ad to unlock your files."
    try:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID, caption=caption_text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text(text=caption_text, reply_markup=reply_markup, parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, download_type, start_index=0):
    if not urls: return
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    success_count = 0
    fail_count = 0
    active_batch_sessions[user_id] = True

    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Batch", callback_data="stop_batch")]])
    batch_notice = await bot.send_message(chat_id=chat_id, text=t["batch_start"].format(download_type.upper(), len(urls)), reply_markup=stop_markup, parse_mode="Markdown")

    consecutive_fails = 0

    for index, url in enumerate(urls[start_index:], start=start_index + 1):
        if not active_batch_sessions.get(user_id, False): break
        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Skipped YouTube.")
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
            paused_batches[user_id] = {"urls": urls, "next_index": index - 1, "target_destination_id": target_destination_id, "chat_id": chat_id, "dl_type": download_type}
            keyboard = [[InlineKeyboardButton(t["refill_btn"], url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
            await bot.send_message(chat_id=chat_id, text=t["limit_batch"].format(index, len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            break 

        status_text = t["dl_video"] if download_type == 'video' else t["dl_audio"] if download_type == 'audio' else t["dl_image"]
        status_msg = await bot.send_message(chat_id=chat_id, text=f"📥 [{index}/{len(urls)}] {status_text}")

        try:
            file_paths, resolution, size_str = download_media_engine(url, download_type)
            if file_paths and os.path.exists(file_paths[0]):
                file_path = file_paths[0]
                if download_type == 'audio':
                    with open(file_path, 'rb') as f: sent_media = await bot.send_audio(chat_id=target_destination_id, audio=f, caption=f"🎵 **Item {index}/{len(urls)}**\n📦 Size: {size_str}")
                elif download_type == 'images':
                    with open(file_path, 'rb') as f: sent_media = await bot.send_photo(chat_id=target_destination_id, photo=f, caption=f"🖼️ **Item {index}/{len(urls)}**\n📦 Size: {size_str}")
                else:
                    with open(file_path, 'rb') as f: sent_media = await bot.send_video(chat_id=target_destination_id, video=f, caption=f"✨ **Item {index}/{len(urls)}**\n📐 Quality: {resolution}\n📦 Size: {size_str}")
                
                if target_destination_id == chat_id:
                    warning_msg = await bot.send_message(chat_id=target_destination_id, text=t["deletes_in_9"])
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
                error_text = t["failed_50"] if "FILE_TOO_LARGE" in str(e) else t["failed_blocked"] if "403" in str(e) else t["failed_generic"]
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}/{len(urls)}] {error_text}")
            except Exception: pass
            fail_count += 1
        await asyncio.sleep(4) 

    if user_id in active_batch_sessions: del active_batch_sessions[user_id]
    try: await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except: pass

    if user_id not in paused_batches:
        dest_text = t["batch_done_chan"].format(success_count, fail_count, success_count) if target_destination_id != chat_id else t["batch_done"].format(success_count, fail_count, success_count)
        await bot.send_message(chat_id=chat_id, text=dest_text, parse_mode="Markdown")


async def handle_user_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if user_id == ADMIN_ID:
        try:
            await update.message.forward(chat_id=PRIVATE_CHANNEL_ID)
            await update.message.reply_text("✅ File saved to your vault channel!")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to save. Error: {e}")
    else:
        # --- NEW: Check 5 Uploads per day limit ---
        limits = load_json_file(UPLOAD_LIMITS_FILE)
        user_str = str(user_id)
        now = time.time()
        
        if user_str in limits and now - limits[user_str]["timestamp"] < 86400:
            if limits[user_str]["count"] >= 5:
                await update.message.reply_text(t["upload_limit_reached"])
                return
            limits[user_str]["count"] += 1
        else:
            limits[user_str] = {"count": 1, "timestamp": now}
        
        save_json_file(UPLOAD_LIMITS_FILE, limits)
        # ------------------------------------------

        try:
            uploads = load_json_file(UPLOADS_FILE)
            upload_id = str(int(time.time()))
            uploads[upload_id] = {"user_id": user_id, "msg_id": update.message.message_id}
            save_json_file(UPLOADS_FILE, uploads)

            await update.message.forward(chat_id=ADMIN_ID)
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 **New Anonymous Upload**\nFrom ID: {user_id}\n\n*(Saved to your 🍿 Fan Uploads folder)*")
            await update.message.reply_text(t["upload_success_user"])
        except Exception:
            await update.message.reply_text("❌ Failed to send file.")


async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if text == t["menu_stats"]:
        tokens = load_tokens()
        profile = tokens.get(str(user_id), {})
        d_left = profile.get("downloads_left", 4)
        b_left = profile.get("batch_downloads_left", 20)
        if user_id == ADMIN_ID: d_left, b_left = "∞", "∞"
        await update.message.reply_text(t["stats_msg"].format(d_left, b_left), parse_mode="Markdown")
        return

    if text == t["menu_join"]:
        await update.message.reply_text(f"📢 [Click here to join the channel]({PUBLIC_CHANNEL_URL})", parse_mode="Markdown", disable_web_page_preview=True)
        return

    if text == t["menu_help"]:
        await update.message.reply_text(f"💬 [Click here for FAQ / Support]({HELP_CHANNEL_URL})", parse_mode="Markdown", disable_web_page_preview=True)
        return
        
    if text == t["menu_lang"]:
        await language_command(update, context)
        return

    if text == t["menu_upload"]:
        prompt = t["admin_upload_prompt"] if user_id == ADMIN_ID else t["user_upload_prompt"]
        await update.message.reply_text(prompt, parse_mode="Markdown")
        return

    # --- ADMIN FAN UPLOADS FOLDER ---
    if text == t["menu_uploads"] and user_id == ADMIN_ID:
        uploads = load_json_file(UPLOADS_FILE)
        if not uploads:
            await update.message.reply_text(t["no_uploads"])
            return
            
        await update.message.reply_text(t["admin_upload_prompt"])
        # Show last 20 uploads to Admin
        for key, data in list(uploads.items())[-20:]:
            try:
                await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=data["user_id"], message_id=data["msg_id"])
            except Exception:
                pass
        return

    if active_batch_sessions.get(user_id, False): return
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
            await update.message.reply_text(f"✅ **Channel Linked!**\n📢 {f_chat.title}\n🆔 `{f_chat.id}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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
        await update.message.reply_text(f"✅ **Channel Linked!**\n📢 {f_chat.title}\n🆔 `{f_chat.id}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    if not extracted_urls: return

    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton(t["btn_video"], callback_data=f"batchtype_video_{payload_key}")],
            [InlineKeyboardButton(t["btn_image"], callback_data=f"batchtype_images_{payload_key}")],
            [InlineKeyboardButton(t["btn_audio"], callback_data=f"batchtype_audio_{payload_key}")]
        ]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    url = extracted_urls[0]
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        await update.message.reply_text("❌ YouTube is paused.")
        return

    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url

    keyboard = [
        [InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")],
        [InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],
        [InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")],
        [InlineKeyboardButton(t["btn_sub"], callback_data=f"fmt_sub_{payload_key}")]
    ]
    await update.message.reply_text(t["ask_format"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if not document.file_name or not document.file_name.endswith('.txt'):
        await handle_user_upload(update, context)
        return

    if active_batch_sessions.get(user_id, False): return

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        extracted_urls = re.findall(r'https?://[^\s]+', file_bytes.decode('utf-8', errors='ignore'))
        if not extracted_urls:
            await update.message.reply_text("❌ No links found inside.")
            return

        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton(t["btn_video"], callback_data=f"batchtype_video_{payload_key}")],
            [InlineKeyboardButton(t["btn_image"], callback_data=f"batchtype_images_{payload_key}")],
            [InlineKeyboardButton(t["btn_audio"], callback_data=f"batchtype_audio_{payload_key}")]
        ]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"File error: {e}")
        await update.message.reply_text("❌ Failed to read file.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    tokens = load_tokens()
    await update.message.reply_text(f"📊 **ADMIN STATS**\nTotal Users: {len(tokens)}", parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        langs = load_json_file(LANG_FILE)
        langs[str(user_id)] = new_lang
        save_json_file(LANG_FILE, langs)
        new_t = LANGUAGES[new_lang]
        await query.answer(new_t["lang_set"], show_alert=True)
        await query.message.reply_text(new_t["welcome"], reply_markup=get_main_keyboard(new_lang, user_id == ADMIN_ID), parse_mode="Markdown")
        await query.message.delete()
        return

    # --- FIXED: BATCH FORMAT SELECTION (maxsplit=3 prevents session expires) ---
    if data.startswith("batchtype_"):
        parts = data.split("_", 3) 
        dl_type = parts[1] 
        payload_key = parts[2] + "_" + parts[3]
        urls = pending_batch_payloads.pop(payload_key, None)
        if not urls:
            await query.answer("❌ Session expired.", show_alert=True)
            return
        
        await query.message.delete()
        keyboard = [
            [InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{dl_type}_{payload_key}")],
            [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{dl_type}_{payload_key}")]
        ]
        await context.bot.send_message(chat_id=chat_id, text=t["batch_dest"].format(len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("fmt_"):
        parts = data.split("_", 2)
        fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("❌ Session expired.", show_alert=True)
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
            await context.bot.send_message(chat_id=chat_id, text="❌ Server error.")
            return

        if res_data.get("status") != "allowed":
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)
            keyboard = [[InlineKeyboardButton(t["refill_btn"], url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
            await context.bot.send_message(chat_id=chat_id, text=t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        status_msg = await context.bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type))

        try:
            file_paths, resolution, size_str = download_media_engine(url, dl_type)
            if not file_paths: raise ValueError("FILE_NOT_FOUND")

            if dl_type == 'images':
                media_group = [InputMediaPhoto(media=open(p, 'rb')) for p in file_paths]
                sent_media = await context.bot.send_media_group(chat_id=chat_id, media=media_group)
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)))
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [m.message_id for m in sent_media] + [warning_msg.message_id], DELETE_DELAY_TIME))
                for p in file_paths: os.remove(p)
            elif dl_type == 'audio':
                with open(file_paths[0], 'rb') as f: sent_media = await context.bot.send_audio(chat_id=chat_id, audio=f, title="Extracted Audio", caption=f"🎵 **Audio**\n📦 Size: {size_str}", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["deletes_in_9"])
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_paths[0])
            elif dl_type == 'subtitles':
                with open(file_paths[0], 'rb') as f: sent_media = await context.bot.send_document(chat_id=chat_id, document=f, caption=f"📝 **Subtitles**", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["deletes_in_9"])
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_paths[0])
            else:
                with open(file_paths[0], 'rb') as f: sent_media = await context.bot.send_video(chat_id=chat_id, video=f, caption=f"✨ **Video**\n📐 Quality: {resolution}\n📦 Size: {size_str}", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["deletes_in_9"])
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_paths[0])

            await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception as e:
            logger.error(f"Single download error: {e}")
            error_msg = t["error_50mb"] if "FILE_TOO_LARGE" in str(e) else t["error_no_img"] if "NO_IMAGES" in str(e) else t["error_generic"]
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
            await query.answer("❌ Session expired.", show_alert=True)
            return
        await query.answer("▶️ Resuming...")
        await query.message.delete()
        asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
        return

    if data.startswith("dest_chat_") or data.startswith("dest_chan_"):
        parts = data.split("_", 3)
        action_type, dl_type, payload_key = parts[1], parts[2], parts[3]
        urls = pending_batch_payloads.pop(payload_key, None)
        if not urls:
            await query.answer("❌ Session expired.", show_alert=True)
            return

        if action_type == "chat":
            await query.answer("📥 Loading...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls, dl_type))
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
            await query.answer("📢 Loading...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, target_channel_id, urls, dl_type))
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

        msg_start, msg_end = token_data.get("msg_start", 0), token_data.get("msg_end", 0)
        del tokens[user_str]
        save_tokens(tokens)
        await query.answer("✅ Verified!")

        if user_id in paused_batches:
            keyboard = [[InlineKeyboardButton("▶️ Resume Batch", callback_data="resume_batch")]]
            await query.message.reply_text("✅ **Verified!** Refilled.\nClick below to resume!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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
            warn = await context.bot.send_message(chat_id=user_id, text=t["deletes_in_9"])
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
        app.add_handler(CommandHandler("language", language_command))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(MessageHandler(filters.VIDEO | filters.AUDIO | filters.PHOTO | filters.VOICE, handle_user_upload))
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