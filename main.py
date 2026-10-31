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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
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
TUTORIAL_MESSAGE_ID = 108
WEB_BASE_URL = "https://michaelbbc.pythonanywhere.com"
BRIDGE_URL = f"{WEB_BASE_URL}/bridge"
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
REWARD_FILE = "reward_config.json"

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
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨ FB, INSTA, TIKTOK, X, YOUTUBE! 🚀✨\n\n🔥 WHAT I CAN DO:\n🎬 VIDEOS HD No Watermark!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMAGES Scrape ALL!\n📝 SUBTITLES Auto!\n📦 BATCH 100+ Links!\n⚡ CACHE 1 Sec!\n💎 VAULT Forever!\n📤 FAN UPLOADS 5/day!\n\n👉 PASTE LINK TO START! 👇**",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **AWESOME! What format you want? Pick below!**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳**",
        "error_generic": "❌ Oops! Failed! 😢 Link private/blocked.",
        "error_50mb": "❌ Too Big! 😅 >50MB limit.", "error_no_img": "❌ No images found!",
        "images_received": "⏳ **{} Images received.**",
        "select_lang": "🌍 Select your language! 👇", "lang_set": "✅ Language set!",
        "batch_detected": "📦 **Batch Detected ({} links)**",
        "batch_dest": "📦 **Where to send?**",
        "btn_chat": "📥 In Chat", "btn_chan": "📢 To Channel",
        "limit_reached": "⚠️ **Limit Reached! You used 4 FREE! 🎬 Watch Ad → Get +1 download!**",
        "refill_btn": "🔓 Open Link & Refill +1",
        "join_btn": "📢 Join Channel", "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached at {} of {}**",
        "batch_start": "📦 **Batch Started:** {} **{} files**",
        "batch_done": "🏁 **Done!** ✅ {} ❌ {}\n📥 {} files here.",
        "batch_done_chan": "🏁 **Done!** ✅ {} ❌ {}\n📢 {} files forwarded!",
        "dl_video": "📥 Downloading video...", "dl_audio": "📥 Extracting audio...", "dl_image": "📥 Scraping images...", "dl_sub": "📥 Fetching subtitles...",
        "failed_50": "❌ >50MB", "failed_blocked": "❌ Blocked", "failed_generic": "❌ Failed",
        "menu_lang": "🌍 Language", "menu_stats": "📊 My Stats", "menu_help": "💬 Support", "menu_join": "📢 Join Channel",
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
    return "Bot alive! V28 Operational", 200

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
    h = hashlib.md5(clean.encode()).hexdigest()[:12]
    return f"url_{h}"

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES.get(lang_code, LANGUAGES["en"])
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton(t["menu_upload"])],
        [KeyboardButton("🟢 Bot Status")],
        [KeyboardButton("🧪 Test Ad"), KeyboardButton("📢 Ad Info")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("📢 Broadcast")])
        keyboard.append([KeyboardButton("⚙️ Ad Toggle Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_downloads_usage_mb():
    try:
        if not os.path.exists("downloads"):
            return 0
        total = sum(os.path.getsize(os.path.join("downloads", f)) for f in os.listdir("downloads") if os.path.isfile(os.path.join("downloads", f)))
        return total // (1024*1024)
    except:
        return 0

def get_reward_amount():
    cfg = load_json_file(CONFIG_FILE)
    return int(cfg.get("reward_amount", 1))

def get_free_amount():
    cfg = load_json_file(CONFIG_FILE)
    return int(cfg.get("free_amount", 4))

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
                if active_downloads < MAX_CONCURRENT_SHORT and get_free_disk_mb() > MIN_FREE_DISK_MB:
                    break
                await asyncio.sleep(2)
            async with download_lock:
                active_downloads += 1
            try:
                await job['func'](*job['args'], **job['kwargs'])
            except Exception as e:
                logger.error(f"Queue job: {e}")
            finally:
                await release_slot()
                download_queue.task_done()
        except Exception as e:
            logger.error(f"Queue proc: {e}")
            await asyncio.sleep(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_banned(user_id):
        return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID), parse_mode="Markdown")

async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    if is_banned(user_id):
        return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])

    if "Test Ad" in text or text.strip() == "🧪 Test Ad":
        adsgram_webapp_url = f"https://api.adsgram.ai/advbot?blockId={ADSGRAM_BLOCK_ID}"
        keyboard = [
            [InlineKeyboardButton("📺 Watch Ad (Adsgram)", web_app=WebAppInfo(url=adsgram_webapp_url))],
            [InlineKeyboardButton("📢 Join Channel", url=PUBLIC_CHANNEL_URL)],
            [InlineKeyboardButton("💜 Check Balance & Unlock ✅", callback_data="verify_user")]
        ]
        await update.message.reply_text(
            "🧪 **ADSGRAM REVIEWER TEST PLACEMENT**\n\n"
            "Click the button below to launch the official Adsgram Mini App ad drawer:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    if not extracted_urls:
        return

    if user_id != ADMIN_ID:
        tokens = load_tokens()
        user_profile = tokens.get(str(user_id), {})
        d_left = user_profile.get("downloads_left", 4)
        if str(user_id) in tokens and not user_profile.get("verified", False) and d_left <= 0:
            adsgram_webapp_url = f"https://api.adsgram.ai/advbot?blockId={ADSGRAM_BLOCK_ID}"
            keyboard = [[InlineKeyboardButton("📺 Watch Ad (Adsgram)", web_app=WebAppInfo(url=adsgram_webapp_url))]]
            await update.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

    url = extracted_urls[0]
    await update.message.reply_text("📥 Processing download link...")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    if data == "verify_user":
        tokens = load_tokens()
        reward = get_reward_amount()
        tokens[str(user_id)] = {"user_id": int(user_id), "downloads_left": reward, "verified": True}
        save_tokens(tokens)
        await query.answer("✅ Verified! +1 download added.", show_alert=True)
        try:
            await query.message.edit_text("✅ **Ad Verified!** Your download limit has been refilled.")
        except:
            pass

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("testad", lambda u, c: u.message.reply_text("Tap below:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📺 Watch Ad", web_app=WebAppInfo(url=f"https://api.adsgram.ai/advbot?blockId={ADSGRAM_BLOCK_ID}"))]]))))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        await app.initialize()
        await app.start()
        asyncio.create_task(queue_processor(app.bot))
        await app.updater.start_polling(drop_pending_updates=True)
        print("Bot polling started successfully!")
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
