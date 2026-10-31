import time
import json
import os
import asyncio
import threading
import requests
import logging
import re
import shutil
import hashlib
import imageio_ffmpeg
import yt_dlp
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
try:
    os.chmod(ffmpeg_path, 0o755)
except:
    pass

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8863904451:AAFYl9yyjTvKTaliLR5iqTsvZr2tytFi3bk").strip()
ADMIN_ID = 6248570946
DETECTED_CHANNEL_ID = -1004347828512
PRIVATE_CHANNEL_ID = -1004347828512
VIDEO_VAULT_ID = -1004324594855
WEB_BASE_URL = "https://michaelbbc.pythonanywhere.com"
PUBLIC_CHANNEL_URL = "https://t.me/booksaufio"
PUBLIC_CHANNEL_USERNAME = "@booksaufio"
HELP_CHANNEL_URL = "https://t.me/faqandaupport"

ADSGRAM_BLOCK_ID = "bot-56842"
PROXY_URL = None 

CHANNELS_FILE = "user_channels.json"
LINKING_STATE_FILE = "linking_states.json"
LANG_FILE = "user_languages.json"
UPLOADS_FILE = "fan_uploads.json" 
UPLOAD_LIMITS_FILE = "upload_limits.json"
DRIP_FILE = "active_drip.json"
DRIP_STATE_FILE = "drip_states.json"
SUPPORT_STATES_FILE = "support_states.json"
CONFIG_FILE = "bot_config.json"
ACTIVITY_FILE = "user_activity.json"
CACHE_FILE = "download_cache.json"
FLOOD_FILE = "flood_control.json"
BANNED_FILE = "banned_users.json"

active_batch_sessions = {}
pending_batch_payloads = {}
paused_batches = {}
pending_single_links = {}

MAX_CONCURRENT_SHORT = 3
MIN_FREE_DISK_MB = 150
active_downloads = 0
download_lock = asyncio.Lock()
download_queue = asyncio.Queue()

FLOOD_LIMIT = 3
FLOOD_WINDOW = 60
FLOOD_COOLDOWN = 30

LANGUAGES = {
    "en": {
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨\n\n👉 PASTE LINK TO START! 👇**",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images",
        "ask_format": "👇 **AWESOME! What format you want? Pick below! 🎯**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳✨**",
        "error_generic": "❌ Oops! Failed! Try public link.",
        "error_50mb": "❌ Too Big! >50MB limit.", 
        "images_received": "⏳ **{} Images received.**",
        "select_lang": "🌍 Select your language! 👇", "lang_set": "✅ Language set!",
        "batch_detected": "📦 **Batch Detected ({} links)**\nWhat format?",
        "batch_dest": "📦 **Where to send?**",
        "btn_chat": "📥 In Chat", "btn_chan": "📢 To Channel",
        "limit_reached": "⚠️ **Limit Reached! Watch Adsgram ad → Get +1 download!**",
        "refill_btn": "📺 Watch Adsgram Ad (+1)",
        "join_btn": "📢 Join Channel", "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached at {} of {}**\nWatch Adsgram ad to continue.",
        "batch_start": "📦 **Batch Started:** {} **{} files**\n⏳ Processing...",
        "batch_done": "🏁 **Done!** ✅ {} ❌ {}\n📥 {} files here.",
        "batch_done_chan": "🏁 **Done!** ✅ {} ❌ {}\n📢 {} files forwarded!",
        "dl_video": "📥 Downloading video...", "dl_audio": "📥 Extracting audio...", "dl_image": "📥 Scraping images...",
        "menu_lang": "🌍 Language", "menu_stats": "📊 My Stats", "menu_help": "💬 Support / FAQ", "menu_join": "📢 Join Channel",
        "menu_uploads": "🍿 Fan Uploads", "menu_upload": "📤 Upload File",
        "admin_upload_prompt": "📂 **Fan Uploads Inbox**",
        "user_upload_prompt": "📤 **Upload File**\nSend media to Admin (anon). Limit 5/24h.",
        "upload_success_user": "✅ Sent to Admin!",
        "upload_limit_reached": "⚠️ Upload limit 5/24h reached.",
        "no_uploads": "📭 No uploads yet.",
        "stats_msg": "📊 **Your Stats:**\n• Downloads Left: {}\n• Batch Left: {}"
    }
}

web_app = Flask(__name__)
@web_app.route('/')
def health_check():
    return "Bot alive! Adsgram Native V24 Fixed", 200

def load_json_file(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Save {filename}: {e}")

def get_canonical_key(url: str):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("no info")
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            extractor = info.get('extractor', 'generic').replace(':', '').replace(' ', '')
            vid_id = info.get('id', '')
            if vid_id:
                return f"{extractor}_{vid_id}"
    except:
        pass
    clean = url.split('?')[0].split('&')[0].lower().strip('/').replace('https://','').replace('http://','')
    return f"url_{hashlib.md5(clean.encode()).hexdigest()[:12]}"

BACKUP_FILES = [CHANNELS_FILE, LANG_FILE, CONFIG_FILE, ACTIVITY_FILE, CACHE_FILE, UPLOADS_FILE, UPLOAD_LIMITS_FILE, DRIP_FILE, FLOOD_FILE, BANNED_FILE]

async def backup_to_channel(bot):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M")
        free_mb = shutil.disk_usage(".").free // (1024*1024)
        cap = f"📦 AUTO-BACKUP {ts}\nFree: {free_mb}MB | Vault: {VIDEO_VAULT_ID}"
        first = True
        for fname in BACKUP_FILES:
            if os.path.exists(fname):
                try:
                    with open(fname, 'rb') as f:
                        await bot.send_document(chat_id=PRIVATE_CHANNEL_ID, document=f, filename=fname, caption=cap if first else None)
                        first = False
                except:
                    pass
    except:
        pass

async def auto_backup_loop(bot):
    while True:
        await asyncio.sleep(6 * 3600)
        await backup_to_channel(bot)

async def disk_cleaner_loop():
    while True:
        await asyncio.sleep(5 * 60)
        try:
            if os.path.exists("downloads"):
                now = time.time()
                for fname in os.listdir("downloads"):
                    fpath = os.path.join("downloads", fname)
                    if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 3 * 60:
                        os.remove(fpath)
        except:
            pass

def clean_downloads_startup():
    try:
        if os.path.exists("downloads"):
            for fname in os.listdir("downloads"):
                try:
                    os.remove(os.path.join("downloads", fname))
                except:
                    pass
    except:
        pass

def is_flood(user_id):
    if user_id == ADMIN_ID:
        return False, 0
    flood_data = load_json_file(FLOOD_FILE)
    now = time.time()
    uid = str(user_id)
    if uid not in flood_data:
        flood_data[uid] = []
    flood_data[uid] = [t for t in flood_data[uid] if now - t < FLOOD_WINDOW]
    if len(flood_data[uid]) >= FLOOD_LIMIT:
        wait = int(FLOOD_COOLDOWN - (now - min(flood_data[uid])))
        return True, max(wait, 5)
    flood_data[uid].append(now)
    save_json_file(FLOOD_FILE, flood_data)
    return False, 0

def is_banned(user_id):
    return str(user_id) in load_json_file(BANNED_FILE)

def track_user_activity(user_id):
    activity = load_json_file(ACTIVITY_FILE)
    user_str = str(user_id)
    now = time.time()
    if user_str not in activity:
        activity[user_str] = {"total_interactions": 0, "last_active": now}
    activity[user_str]["total_interactions"] += 1
    activity[user_str]["last_active"] = now
    save_json_file(ACTIVITY_FILE, activity)

def get_lang(user_id):
    return load_json_file(LANG_FILE).get(str(user_id), "en")

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, timeout=5)
    except:
        pass

def load_user_channels():
    return load_json_file(CHANNELS_FILE)
def save_user_channels(c):
    save_json_file(CHANNELS_FILE, c)
def load_linking_states():
    return load_json_file(LINKING_STATE_FILE)
def save_linking_states(s):
    save_json_file(LINKING_STATE_FILE, s)

async def schedule_deletion(bot, chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass

def fetch_url_metadata(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            title = info.get('title', 'Unknown')[:60]
            duration = info.get('duration', 0)
            mins, secs = divmod(duration, 60)
            return title, f"{mins}m {secs}s" if mins else f"{secs}s"
    except:
        return "Media Link", "N/A"

def scrape_html_images(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        og = BeautifulSoup(res.text, 'html.parser').find('meta', property='og:image')
        if og and og.get('content'):
            return og['content']
    except:
        pass
    return None

def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0'}
    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if download_type == 'audio':
        ydl_opts.update({'format': 'bestaudio/best', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'ffmpeg_location': ffmpeg_path})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = f"{os.path.splitext(ydl.prepare_filename(info))[0]}.mp3"
            if os.path.exists(path):
                return [path], "MP3", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("FILE_NOT_FOUND")
    elif download_type == 'images':
        img_url = scrape_html_images(url)
        if img_url:
            data = requests.get(img_url, headers=http_headers, timeout=15).content
            path = os.path.join(output_dir, f"img_{int(time.time())}.jpg")
            with open(path, 'wb') as f:
                f.write(data)
            return [path], "Image", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("NO_IMAGES")
    else:
        for fmt in ["best", "bestvideo+bestaudio/best"]:
            try:
                ydl_opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path})
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"):
                        path = os.path.splitext(path)[0]+".mp4"
                    if os.path.exists(path):
                        if os.path.getsize(path) > 50*1024*1024:
                            os.remove(path)
                            continue
                        return [path], f"{info.get('height', 'HD')}p", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
            except:
                continue
        raise ValueError("FILE_TOO_LARGE")

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES.get(lang_code, LANGUAGES["en"])
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton(t["menu_upload"])],
        [KeyboardButton("🟢 Bot Status"), KeyboardButton("🧪 Test Adsgram Ad")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("📢 Broadcast")])
        keyboard.append([KeyboardButton("⚡ Create Flash Drop")])
        keyboard.append([KeyboardButton("🎁 Set Reward (1/2/3/5)"), KeyboardButton("📦 Set Free DL (2/3/4/5)")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_downloads_usage_mb():
    try:
        if not os.path.exists("downloads"):
            return 0
        return sum(os.path.getsize(os.path.join("downloads", f)) for f in os.listdir("downloads") if os.path.isfile(os.path.join("downloads", f))) // (1024*1024)
    except:
        return 0

def get_reward_amount():
    try:
        return int(load_json_file(CONFIG_FILE).get("reward_amount", 1))
    except:
        return 1

def set_reward_amount(val):
    cfg = load_json_file(CONFIG_FILE)
    cfg["reward_amount"] = int(val)
    save_json_file(CONFIG_FILE, cfg)

def get_free_amount():
    try:
        return int(load_json_file(CONFIG_FILE).get("free_amount", 4))
    except:
        return 4

def set_free_amount(val):
    cfg = load_json_file(CONFIG_FILE)
    cfg["free_amount"] = int(val)
    save_json_file(CONFIG_FILE, cfg)

def get_free_disk_mb():
    return max(0, 512 - get_downloads_usage_mb())

def deduct_download_counter(user_id, is_batch=False):
    try:
        requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": is_batch}, timeout=3)
    except:
        pass

async def acquire_slot():
    global active_downloads
    async with download_lock:
        if active_downloads < MAX_CONCURRENT_SHORT and get_free_disk_mb() > MIN_FREE_DISK_MB:
            active_downloads += 1
            return True
        return False

async def release_slot():
    global active_downloads
    async with download_lock:
        active_downloads = max(0, active_downloads - 1)

async def queue_processor(bot):
    global active_downloads
    while True:
        try:
            job = await download_queue.get()
            while True:
                async with download_lock:
                    if active_downloads < MAX_CONCURRENT_SHORT and get_free_disk_mb() > MIN_FREE_DISK_MB:
                        break
                await asyncio.sleep(2)
            async with download_lock:
                active_downloads += 1
            try:
                await job['func'](*job['args'], **job['kwargs'])
            except:
                pass
            finally:
                await release_slot()
                download_queue.task_done()
        except:
            await asyncio.sleep(1)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    lang = get_lang(update.message.from_user.id)
    keyboard = [[InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]]
    await update.message.reply_text(LANGUAGES.get(lang, LANGUAGES["en"])["select_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID), parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, download_type, start_index=0):
    if not urls:
        return
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    success_count = fail_count = 0
    active_batch_sessions[user_id] = True
    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Batch", callback_data="stop_batch")]])
    batch_notice = await bot.send_message(chat_id=chat_id, text=t["batch_start"].format(download_type.upper(), len(urls)), reply_markup=stop_markup, parse_mode="Markdown")
    
    for index, url in enumerate(urls[start_index:], start=start_index+1):
        if not active_batch_sessions.get(user_id, False):
            break
        try:
            res_data = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, timeout=5).json()
        except:
            res_data = {"status": "allowed"}
        
        tokens = load_tokens()
        d_left = tokens.get(str(user_id), {}).get("downloads_left", get_free_amount())
        if res_data.get("status") != "allowed" and d_left <= 0 and user_id != ADMIN_ID:
            paused_batches[user_id] = {"urls": urls, "next_index": index-1, "target_destination_id": target_destination_id, "chat_id": chat_id, "dl_type": download_type}
            
            adsgram_url = f"https://api.adsgram.ai/advbot?blockId={ADSGRAM_BLOCK_ID}"
            reward = get_reward_amount()
            keyboard = [
                [InlineKeyboardButton(f"📺 Watch Adsgram Ad (+{reward})", web_app={"url": adsgram_url})],
                [InlineKeyboardButton("✅ Check Reward Balance", callback_data="adsgram_verify_batch")]
            ]
            await bot.send_message(chat_id=chat_id, text=t["limit_batch"].format(index, len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            break
        
        status_msg = await bot.send_message(chat_id=chat_id, text=f"📥 [{index}/{len(urls)}] {t['dl_video']}")
        try:
            file_paths, res, size = download_media_engine(url, download_type)
            if file_paths and os.path.exists(file_paths[0]):
                with open(file_paths[0], 'rb') as f:
                    await bot.send_video(chat_id=target_destination_id, video=f, caption=f"Item {index}/{len(urls)} Size {size}")
                os.remove(file_paths[0])
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
            else:
                fail_count += 1
        except:
            fail_count += 1
        await asyncio.sleep(2)
    
    if user_id in active_batch_sessions:
        del active_batch_sessions[user_id]
    try:
        await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except:
        pass
    if user_id not in paused_batches:
        dest = t["batch_done_chan"].format(success_count, fail_count, success_count) if target_destination_id != chat_id else t["batch_done"].format(success_count, fail_count, success_count)
        await bot.send_message(chat_id=chat_id, text=dest, parse_mode="Markdown")

async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    if is_banned(user_id):
        return
    if "http" in text.lower():
        flood, wait = is_flood(user_id)
        if flood:
            await update.message.reply_text(f"🐢 Slow down! Wait {wait}s.")
            return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])

    # RESTORED BUTTON HANDLERS
    if text == t["menu_stats"]:
        if user_id == ADMIN_ID:
            tokens = load_tokens()
            await update.message.reply_text(f"📊 **Admin Stats**\nTotal Users Tracked: {len(tokens)}", parse_mode="Markdown")
        else:
            tokens = load_tokens()
            profile = tokens.get(str(user_id), {})
            d_left = profile.get("downloads_left", get_free_amount())
            b_left = profile.get("batch_downloads_left", get_free_amount()*5)
            await update.message.reply_text(t["stats_msg"].format(d_left, b_left), parse_mode="Markdown")
        return

    if text == t["menu_lang"]:
        await language_command(update, context)
        return

    if text == t["menu_join"]:
        await update.message.reply_text(f"📢 [Join Channel]({PUBLIC_CHANNEL_URL})", parse_mode="Markdown")
        return

    if text == t["menu_help"]:
        keyboard = [[InlineKeyboardButton("💬 Open Support", callback_data="open_support")]]
        await update.message.reply_text(f"💬 [Support Chat]({HELP_CHANNEL_URL})", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if text == t["menu_upload"]:
        await update.message.reply_text(t["user_upload_prompt"], parse_mode="Markdown")
        return

    if text.startswith("📦 Set Free") and user_id == ADMIN_ID:
        current = get_free_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i}", callback_data=f"set_free_{i}") for i in [2,3,4,5]]]
        await update.message.reply_text(f"📦 **FREE DOWNLOADS PANEL**\nCurrent: {current}\nSelect new free limit:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if text.startswith("🎁 Set Reward") and user_id == ADMIN_ID:
        current = get_reward_amount()
        keyboard = [[InlineKeyboardButton(f"✅ +{i} (Current)" if i==current else f"+{i}", callback_data=f"set_reward_{i}") for i in [1,2,3,5]]]
        await update.message.reply_text(f"🎁 **REWARD PANEL**\nCurrent: +{current}\nSelect new ad reward value:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if text == "🟢 Bot Status":
        await update.message.reply_text(f"🟢 **Status: Adsgram Native Mode**\nFree Limit: {get_free_amount()}\nReward Value: +{get_reward_amount()}\nFree Disk: {get_free_disk_mb()}MB", parse_mode="Markdown")
        return

    if "Test Adsgram Ad" in text or text.strip() == "🧪 Test Adsgram Ad":
        adsgram_url = f"https://api.adsgram.ai/advbot?blockId={ADSGRAM_BLOCK_ID}"
        reward = get_reward_amount()
        keyboard = [
            [InlineKeyboardButton("📺 Watch Adsgram Rewarded Ad", web_app={"url": adsgram_url})],
            [InlineKeyboardButton(f"✅ Verify & Refill +{reward} Download", callback_data="adsgram_verify_test")]
        ]
        await update.message.reply_text(
            "🧪 **ADSGRAM AD PLACEMENT TEST (Clause 13 Compliance)**\n\n"
            "This button opens the native Adsgram WebApp directly inside Telegram without external redirects.\n\n"
            "👉 **Tap the button below to test the native ad unit:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    extracted_urls = [u for u in re.findall(r'https?://[^\s]+', text) if "t.me/" not in u or "start=" not in u]
    if not extracted_urls:
        return

    if user_id != ADMIN_ID:
        tokens = load_tokens()
        user_profile = tokens.get(str(user_id), {})
        d_left = user_profile.get("downloads_left", get_free_amount())
        if str(user_id) in tokens and not user_profile.get("verified", False) and d_left <= 0:
            adsgram_url = f"https://api.adsgram.ai/advbot?blockId={ADSGRAM_BLOCK_ID}"
            reward = get_reward_amount()
            keyboard = [
                [InlineKeyboardButton(f"📺 Watch Adsgram Ad (+{reward} Download)", web_app={"url": adsgram_url})],
                [InlineKeyboardButton("📢 Join Channel", url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton("✅ Check Balance & Refill", callback_data="adsgram_verify_single")]
            ]
            await update.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"batchtype_video_{payload_key}")]]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    url = extracted_urls[0]
    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")], [InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")]]
    await update.message.reply_text(t["ask_format"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def cached_download_and_send(bot, chat_id, url, dl_type, t):
    status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type))
    try:
        file_paths, res, size = download_media_engine(url, dl_type)
        with open(file_paths[0], 'rb') as f:
            await bot.send_video(chat_id=chat_id, video=f, caption=f"✨ {res} Size {size}")
        os.remove(file_paths[0])
        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        deduct_download_counter(chat_id, is_batch=False)
        return True
    except Exception as e:
        await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=t["error_generic"])
        return False

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])

    if data == "open_support":
        await query.answer("Support opened")
        await query.message.reply_text(f"💬 You can reach out via our support channel: {HELP_CHANNEL_URL}", parse_mode="Markdown")
        return

    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        langs = load_json_file(LANG_FILE)
        langs[str(user_id)] = new_lang
        save_json_file(LANG_FILE, langs)
        await query.answer("Language updated!", show_alert=True)
        try:
            await query.message.edit_text(t["lang_set"])
        except:
            pass
        return

    if data.startswith("set_free_") and user_id == ADMIN_ID:
        val = int(data.replace("set_free_", ""))
        set_free_amount(val)
        await query.answer(f"✅ Free limit set to {val}!", show_alert=True)
        try:
            await query.message.edit_text(f"✅ **Free Downloads Updated to {val}!**", parse_mode="Markdown")
        except:
            pass
        return

    if data.startswith("set_reward_") and user_id == ADMIN_ID:
        val = int(data.replace("set_reward_", ""))
        set_reward_amount(val)
        await query.answer(f"✅ Reward set to +{val}!", show_alert=True)
        try:
            await query.message.edit_text(f"✅ **Reward Updated to +{val} downloads per ad!**", parse_mode="Markdown")
        except:
            pass
        return

    if data.startswith("adsgram_verify_") or data == "adsgram_verify_batch" or data == "adsgram_verify_test":
        tokens = load_tokens()
        reward = get_reward_amount()
        tokens[str(user_id)] = {
            "user_id": int(user_id),
            "downloads_left": reward,
            "batch_downloads_left": reward * 5,
            "verified": True,
            "expires": time.time() + 600
        }
        save_tokens(tokens)
        await query.answer(f"✅ Adsgram Reward Verified! +{reward} Download Added.", show_alert=True)
        try:
            await query.message.edit_text(f"✅ **Adsgram Reward Verified Successfully!**\n\nYour download limit has been refilled by +{reward}.", parse_mode="Markdown")
        except:
            pass
        if user_id in paused_batches:
            paused = paused_batches.pop(user_id)
            asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
        return

    if data.startswith("fmt_"):
        parts = data.split("_", 2)
        fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("Expired", show_alert=True)
            return
        await query.answer("Processing...")
        await query.message.delete()
        dl_type = 'audio' if fmt_type == 'aud' else 'video'
        await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
        return

    if data.startswith("batchtype_"):
        parts = data.split("_", 2)
        dl_type, payload_key = parts[1], parts[2]
        urls = pending_batch_payloads.pop(payload_key, None)
        if not urls:
            await query.answer("Expired", show_alert=True)
            return
        await query.message.delete()
        asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls, dl_type))
        return

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("language", language_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        await app.initialize()
        await app.start()
        asyncio.create_task(disk_cleaner_loop())
        asyncio.create_task(auto_backup_loop(app.bot))
        asyncio.create_task(queue_processor(app.bot))
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        print("Bot started with Full Button Support & Native Adsgram WebApp Integration!")
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
