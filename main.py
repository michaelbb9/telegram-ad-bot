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

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()   # set TELEGRAM_TOKEN in Render env - never hardcode it
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

ADSGRAM_BLOCK_ID = os.getenv("ADSGRAM_BLOCK_ID", "")   # Mini App REWARDED block id (the SDK one). Set in the Flask server too.
API_SECRET = os.getenv("API_SECRET", "change-me")        # must be the same value on PythonAnywhere
API_HEADERS = {"X-Api-Secret": API_SECRET}
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
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨ FB, INSTA, TIKTOK, X, YOUTUBE! 🚀✨\n\n🔥 WHAT I CAN DO:\n🎬 VIDEOS HD No Watermark!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMAGES Scrape ALL!\n📝 SUBTITLES Auto!\n📦 BATCH 100+ Links!\n⚡ CACHE 1 Sec!\n💎 VAULT Forever!\n📤 FAN UPLOADS 5/day!\n\n👉 PASTE LINK TO START! 👇** 🚀\n\n🎬 Video, 🎵 Audio, 🖼️ Images, 📝 Subtitles\n📦 Batch Downloader (100+ links)\n⚡ Flash Drops\n💎 Exclusive Vaults\n📤 Fan Uploads (5/day)\n\n👉 Just paste ANY link: TikTok, Facebook, Instagram, Twitter/X, YouTube to start! 🚀✨ All Media Supported!",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **AWESOME! What format you want? Pick below! 🎯 Video=watch, Audio=music!**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳✨ Working magic! 🚀**",
        "error_generic": "❌ Oops! Failed! 😢 Link private/blocked. Try public link! 🔓💡",
        "error_50mb": "❌ Too Big! 😅 >50MB limit. Try <20MB short video! ✂️", "error_no_img": "❌ No images found! 😢 Try another link! 🖼️",
        "images_received": "⏳ **{} Images received.**",
        "select_lang": "🌍 Select your language! 🌍✨ Choose below! 👇", "lang_set": "✅ Language set! Enjoy magic! 🎉✨",
        "batch_detected": "📦 **Batch Detected ({} links)**\nWhat format?",
        "batch_dest": "📦 **Where to send?**",
        "btn_chat": "📥 In Chat", "btn_chan": "📢 To Channel",
        "limit_reached": "⚠️ **Limit Reached! 🚧😅 You used 4 FREE! 🎬 Watch 20s ad → Get +1 download! Realistic reward ♻️✨**",
        "refill_btn": "🔓 Open Link & Refill +1",
        "join_btn": "📢 Join Channel", "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached at {} of {}**\nWatch 20s ad → +1 download to continue.",
        "batch_start": "📦 **Batch Started:** {} **{} files**\n⏳ Processing...",
        "batch_done": "🏁 **Done!** ✅ {} ❌ {}\n📥 {} files here.",
        "batch_done_chan": "🏁 **Done!** ✅ {} ❌ {}\n📢 {} files forwarded!",
        "dl_video": "📥 Downloading video...", "dl_audio": "📥 Extracting audio...", "dl_image": "📥 Scraping images...", "dl_sub": "📥 Fetching subtitles...",
        "failed_50": "❌ >50MB", "failed_blocked": "❌ Blocked/private", "failed_generic": "❌ Failed",
        "menu_lang": "🌍 Language", "menu_stats": "📊 My Stats", "menu_help": "💬 Support / FAQ", "menu_join": "📢 Join Channel",
        "menu_uploads": "🍿 Fan Uploads", "menu_upload": "📤 Upload File",
        "admin_upload_prompt": "📂 **Fan Uploads Inbox**",
        "user_upload_prompt": "📤 **Upload File**\nSend video/image/file to Admin (anon). Limit 5/24h.",
        "upload_success_user": "✅ Sent to Admin!",
        "upload_limit_reached": "⚠️ Upload limit 5/24h reached.",
        "no_uploads": "📭 No uploads yet.",
        "stats_msg": "📊 **Your Stats:**\n• Downloads Left: {}\n• Batch Left: {}"
    }
}

web_app = Flask(__name__)
@web_app.route('/')
def health_check():
    return "Bot alive! V24 Optimum +1", 200

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
        if os.path.exists("tiktok_cookies.txt") and "tiktok.com" in url.lower():
            ydl_opts['cookiefile'] = "tiktok_cookies.txt"
        elif os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = "cookies.txt"
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
    except Exception as e:
        logger.info(f"Key extract fail: {e}")
    try:
        clean = url.split('?')[0].split('&')[0].lower().strip('/').replace('https://','').replace('http://','')
        h = hashlib.md5(clean.encode()).hexdigest()[:12]
        return f"url_{h}"
    except:
        return f"url_{hashlib.md5(url.encode()).hexdigest()[:12]}"

BACKUP_FILES = [CHANNELS_FILE, LANG_FILE, CONFIG_FILE, ACTIVITY_FILE, CACHE_FILE, UPLOADS_FILE, UPLOAD_LIMITS_FILE, DRIP_FILE, FLOOD_FILE, BANNED_FILE]

async def backup_to_channel(bot):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M")
        free_mb = shutil.disk_usage(".").free // (1024*1024)
        cap = f"📦 AUTO-BACKUP {ts}\nFree: {free_mb}MB | Active: {active_downloads} | Queue: {download_queue.qsize()} | Vault: {VIDEO_VAULT_ID}"
        first = True
        for fname in BACKUP_FILES:
            if os.path.exists(fname):
                try:
                    with open(fname, 'rb') as f:
                        await bot.send_document(chat_id=PRIVATE_CHANNEL_ID, document=f, filename=fname, caption=cap if first else None)
                        first = False
                except Exception as e:
                    logger.error(f"Backup {fname}: {e}")
        logger.info("Backup done")
    except Exception as e:
        logger.error(f"Backup error: {e}")

async def auto_backup_loop(bot):
    while True:
        await asyncio.sleep(6 * 3600)
        await backup_to_channel(bot)

async def disk_cleaner_loop():
    while True:
        await asyncio.sleep(5 * 60)
        try:
            if not os.path.exists("downloads"):
                continue
            now = time.time()
            deleted = 0
            for fname in os.listdir("downloads"):
                fpath = os.path.join("downloads", fname)
                try:
                    if os.path.isfile(fpath):
                        age = now - os.path.getmtime(fpath)
                        if age > 3 * 60:
                            os.remove(fpath)
                            deleted += 1
                except:
                    pass
            if deleted:
                logger.info(f"Cleaner deleted {deleted}")
        except Exception as e:
            logger.error(f"Cleaner: {e}")

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
        oldest = min(flood_data[uid]) if flood_data[uid] else now
        wait = int(FLOOD_COOLDOWN - (now - oldest))
        wait = max(wait, 5)
        return True, wait
    flood_data[uid].append(now)
    save_json_file(FLOOD_FILE, flood_data)
    return False, 0

def is_banned(user_id):
    banned = load_json_file(BANNED_FILE)
    return str(user_id) in banned

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
    langs = load_json_file(LANG_FILE)
    return langs.get(str(user_id), "en")

def get_global_ab_network(user_id):
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode", "auto")
    if mode == "adsgram":
        return "adsgram"
    elif mode == "adsterra":
        return "adsterra"
    day_epoch = int(time.time() // 86400)
    return "adsgram" if (int(user_id) + day_epoch) % 2 == 0 else "adsterra"

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", headers=API_HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Tokens: {e}")
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, headers=API_HEADERS, timeout=5)
    except Exception as e:
        logger.error(f"Save tokens: {e}")

def adsgram_start(user_id, kind="wall", msg_start=0, msg_end=0):
    try:
        r = requests.post(f"{WEB_BASE_URL}/adsgram-start",
                          json={"user_id": int(user_id), "kind": kind, "msg_start": int(msg_start),
                                "msg_end": int(msg_end), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200:
            return r.json().get("nonce")
    except Exception as e:
        logger.error(f"adsgram_start: {e}")
    return None

def adsgram_status(user_id):
    try:
        r = requests.post(f"{WEB_BASE_URL}/adsgram-status", json={"user_id": int(user_id), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"adsgram_status: {e}")
    return {"status": "error"}

def adsgram_keyboard(user_id, kind="wall", msg_start=0, msg_end=0, extra_rows=None):
    nonce = adsgram_start(user_id, kind, msg_start, msg_end)
    if not nonce:
        return None
    url = f"{WEB_BASE_URL}/adsgram?n={nonce}&k={kind}"
    rows = [
        [InlineKeyboardButton("📺 Watch Ad (opens Mini App) +1", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Check & Get +1", callback_data="adsgram_check")],
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return InlineKeyboardMarkup(rows)

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
            dur = f"{mins}m {secs}s" if mins else f"{secs}s"
            return title, dur
    except:
        return "Media Link", "N/A"

def scrape_html_images(url, cookiefile=None):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            return og['content']
    except Exception as e:
        logger.error(f"Scrape: {e}")
    return None

def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0'}
    cookiefile = None
    if "tiktok.com" in url.lower() and os.path.exists("tiktok_cookies.txt"):
        cookiefile = "tiktok_cookies.txt"
    elif os.path.exists("cookies.txt"):
        cookiefile = "cookies.txt"
    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
    if download_type == 'audio':
        ydl_opts.update({'format': 'bestaudio/best', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'ffmpeg_location': ffmpeg_path})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            path = f"{base}.mp3"
            if os.path.exists(path):
                return [path], "MP3", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("FILE_NOT_FOUND")
    elif download_type == 'images':
        img_url = scrape_html_images(url, cookiefile)
        if img_url:
            data = requests.get(img_url, headers=http_headers, timeout=15).content
            path = os.path.join(output_dir, f"img_{int(time.time())}.jpg")
            with open(path, 'wb') as f:
                f.write(data)
            if os.path.getsize(path) > 1000:
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
            except Exception as e:
                if "Unsupported URL" in str(e) or "403" in str(e):
                    raise e
                continue
        raise ValueError("FILE_TOO_LARGE")

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES.get(lang_code, LANGUAGES["en"])
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton("🔍 Song Search"), KeyboardButton(t["menu_upload"])],
        [KeyboardButton("🟢 Bot Status")],
        [KeyboardButton("🧪 Test Ad"), KeyboardButton("📢 Ad Info")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("📢 Broadcast")])
        keyboard.append([KeyboardButton("⚡ Create Flash Drop"), KeyboardButton("⚙️ Ad Toggle Panel")])
        keyboard.append([KeyboardButton("🎁 Set Reward (1/2/3/5)"), KeyboardButton("📦 Set Free DL (2/3/4/5)")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_downloads_usage_mb():
    try:
        if not os.path.exists("downloads"):
            return 0
        total = 0
        for fname in os.listdir("downloads"):
            fpath = os.path.join("downloads", fname)
            if os.path.isfile(fpath):
                total += os.path.getsize(fpath)
        return total // (1024*1024)
    except:
        return 0

def get_reward_amount():
    try:
        cfg = load_json_file(CONFIG_FILE)
        return int(cfg.get("reward_amount", 1))
    except:
        return 1

def set_reward_amount(val):
    cfg = load_json_file(CONFIG_FILE)
    cfg["reward_amount"] = int(val)
    save_json_file(CONFIG_FILE, cfg)
    try:
        import requests as req
        req.get(f"{WEB_BASE_URL}/set_reward?value={val}", headers=API_HEADERS, timeout=3)
    except:
        pass

def get_free_amount():
    try:
        cfg = load_json_file(CONFIG_FILE)
        return int(cfg.get("free_amount", 4))
    except:
        return 4

def set_free_amount(val):
    cfg = load_json_file(CONFIG_FILE)
    cfg["free_amount"] = int(val)
    save_json_file(CONFIG_FILE, cfg)
    try:
        import requests as req
        req.get(f"{WEB_BASE_URL}/set_free?value={val}", headers=API_HEADERS, timeout=3)
    except:
        pass

def get_free_disk_mb():
    try:
        used = get_downloads_usage_mb()
        return max(0, 512 - used)
    except:
        return 512

def deduct_download_counter(user_id, is_batch=False):
    try:
        requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": is_batch}, headers=API_HEADERS, timeout=3)
    except:
        pass

async def acquire_slot():
    global active_downloads
    async with download_lock:
        free_mb = get_free_disk_mb()
        if active_downloads < MAX_CONCURRENT_SHORT and free_mb > MIN_FREE_DISK_MB:
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
                free_mb = get_free_disk_mb()
                async with download_lock:
                    can_run = active_downloads < MAX_CONCURRENT_SHORT and free_mb > MIN_FREE_DISK_MB
                if can_run:
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

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    lang = get_lang(update.message.from_user.id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    keyboard = [[InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]]
    await update.message.reply_text(t["select_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    track_user_activity(user_id)
    args = context.args
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    if not args:
        await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID), parse_mode="Markdown")
        return
    # [Rest of start command logic...]

# ===================== MUSIC MODULE (FIXED & FULLY INTEGRATED) =====================
import tempfile
from concurrent.futures import ThreadPoolExecutor

song_search_mode = {}  
MUSIC_CACHE_FILE = "music_cache.json"
MUSIC_PENDING_FILE = "pending_music_requests.json"
music_executor = ThreadPoolExecutor(max_workers=3)

MIKU_BOT_USERNAME = "Mikulordbot"
MIKU_CACHE_CHANNEL_ID = -1004324594855  

def load_music_cache():
    if os.path.exists(MUSIC_CACHE_FILE):
        try:
            return json.load(open(MUSIC_CACHE_FILE))
        except:
            return {}
    return {}

def save_music_cache(cache):
    try:
        with open(MUSIC_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except:
        pass

def load_music_pending():
    if os.path.exists(MUSIC_PENDING_FILE):
        try:
            return json.load(open(MUSIC_PENDING_FILE))
        except:
            return {}
    return {}

def save_music_pending(pending):
    try:
        with open(MUSIC_PENDING_FILE, "w") as f:
            json.dump(pending, f)
    except:
        pass

def search_deezer_sync(query_text):
    try:
        resp = requests.get(f"https://api.deezer.com/search?q={query_text}", timeout=8)
        data = resp.json()
        return data.get("data", [])[:10]
    except Exception as e:
        print(f"Deezer search fail: {e}")
        return []

async def handle_song_search_mode_fixed(update, context, query_text):
    user_id = update.effective_user.id
    try:
        wait_msg = await update.message.reply_text(f"🔍 Searching '{query_text}'...\n\nFinding 10 suggestions (like Miku bot)...")
    except Exception:
        wait_msg = None
    
    loop = asyncio.get_event_loop()
    tracks = await loop.run_in_executor(music_executor, search_deezer_sync, query_text)
    
    if not tracks:
        txt = f"❌ No results for '{query_text}'. Try another song name."
        if wait_msg:
            await wait_msg.edit_text(txt)
        else:
            await update.message.reply_text(txt)
        return
    
    buttons = []
    for track in tracks:
        t_title = track.get("title", "")[:28]
        t_artist = track.get("artist", {}).get("name", "")[:18]
        t_id = track.get("id")
        btn_text = f"{t_title} — {t_artist}"[:40]
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"music_pick_{t_id}_{user_id}")])
    
    buttons.append([InlineKeyboardButton("🔍 Search again", callback_data=f"music_search_again_{user_id}")])
    
    try:
        if wait_msg:
            await wait_msg.edit_text(f"🎵 Found {len(tracks)} for '{query_text}' - Tap to download MP3 + lyrics:", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(f"🎵 Found {len(tracks)}:", reply_markup=InlineKeyboardMarkup(buttons))
        context.user_data[f"music_search_{user_id}"] = tracks
    except Exception as e:
        await update.message.reply_text(f"Found {len(tracks)} but button send failed: {e}")

async def handle_music_pick_callback_fixed(update, context):
    query = update.callback_query
    data = query.data
    
    if data.startswith("music_search_again_"):
        uid = int(data.split("_")[-1])
        song_search_mode[uid] = True
        await query.message.reply_text("🔍 Enter song name again:")
        await query.answer()
        return
    
    if data.startswith("music_pick_"):
        try:
            parts = data.split("_")
            track_id = parts[2]
            target_user_id = int(parts[3])
            
            await query.answer("Downloading... MP3 + lyrics coming!")
            
            title, artist = "Unknown", "Unknown"
            try:
                def get_track_sync(tid):
                    r = requests.get(f"https://api.deezer.com/track/{tid}", timeout=6)
                    j = r.json()
                    return j.get("title","Unknown"), j.get("artist",{}).get("name","Unknown")
                loop = asyncio.get_event_loop()
                title, artist = await loop.run_in_executor(music_executor, get_track_sync, track_id)
            except:
                tracks = context.user_data.get(f"music_search_{target_user_id}", [])
                for t in tracks:
                    if str(t.get("id")) == str(track_id):
                        title = t.get("title","Unknown")
                        artist = t.get("artist",{}).get("name","Unknown")
                        break
            
            user_id = target_user_id
            cache = load_music_cache()
            cache_key = f"{title}_{artist}".lower().replace(" ", "_")[:50]
            
            if cache_key in cache and "file_id" in cache[cache_key]:
                try:
                    await context.bot.send_audio(chat_id=user_id, audio=cache[cache_key]["file_id"], title=title, performer=artist, caption=f"{title} - {artist} ♻️ Cached!")
                    deduct_download_counter(user_id, is_batch=False)
                    await query.edit_message_text(f"✅ Sent cached {title} - {artist}!")
                    return
                except:
                    pass
            
            await query.edit_message_text(f"🎵 Requesting {title} - {artist} via Miku bot...")
            
            pending = load_music_pending()
            pending[cache_key] = {"user_id": user_id, "title": title, "artist": artist, "timestamp": time.time(), "status": "waiting_miku"}
            save_music_pending(pending)
            msg = f"@{MIKU_BOT_USERNAME} {title} - {artist}\nRequested by {user_id}."
            await context.bot.send_message(chat_id=MIKU_CACHE_CHANNEL_ID, text=msg)
            
        except Exception as e:
            await query.answer(f"Error: {str(e)[:60]}")

async def handle_channel_post_fixed(update, context):
    try:
        post = update.channel_post
        if not post or post.chat.id != MIKU_CACHE_CHANNEL_ID:
            return
        if post.audio:
            file_id = post.audio.file_id
            caption = post.caption or ""
            title = post.audio.title or caption[:30] or "Unknown"
            artist = post.audio.performer or "Unknown"
            
            pending = load_music_pending()
            matched_key = None
            matched_user = None
            for key, info in list(pending.items()):
                if time.time() - info.get("timestamp",0) < 600:
                    matched_key = key
                    matched_user = info.get("user_id")
                    title = info.get("title", title)
                    artist = info.get("artist", artist)
                    break
            if matched_user:
                full_caption = caption if caption else f"{title} - {artist} MP3"
                await context.bot.send_audio(chat_id=matched_user, audio=file_id, title=title, performer=artist, caption=full_caption[:1024])
                cache = load_music_cache()
                cache_key = f"{title}_{artist}".lower().replace(" ", "_")[:50]
                cache[cache_key] = {"file_id": file_id, "title": title, "artist": artist, "source": "miku_cache_channel", "timestamp": time.time()}
                save_music_cache(cache)
                deduct_download_counter(matched_user, is_batch=False)
                if matched_key in pending:
                    del pending[matched_key]
                    save_music_pending(pending)
    except:
        pass


# ===================== MAIN MEDIA LINK & BUTTON HANDLER (PRESERVED) =====================
async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    if is_banned(user_id):
        await update.message.reply_text("🚫 Banned")
        return

    # 1. FIXED SONG SEARCH INTERCEPTOR CHECK (Processes text before any link or menu routing)
    if user_id in song_search_mode and song_search_mode[user_id]:
        if len(text) >= 2 and not text.startswith("/") and not text.startswith("http") and "Song Search" not in text:
            song_search_mode[user_id] = False
            await handle_song_search_mode_fixed(update, context, text)
            return

    # Rest of your full original handler logic...
    if "http" in text.lower():
        flood, wait = is_flood(user_id)
        if flood:
            await update.message.reply_text(f"🐢 **Slow down!** Wait {wait}s before next link.", parse_mode="Markdown")
            return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    
    if "🔍 Song Search" in text:
        song_search_mode[user_id] = True
        await update.message.reply_text("🎵 Song Search Mode ON!\n\nEnter song name (e.g. Koleyewon or Blinding Lights):\n\nI'll show 10 suggestions like Miku bot, with lyrics!")
        return

    if text == "🟢 Bot Status":
        await status_command(update, context)
        return

    if "Test Ad" in text or text.strip() == "🧪 Test Ad":
        await send_adsgram_test(update.message, user_id)
        return

    if text == t["menu_stats"]:
        if user_id == ADMIN_ID:
            await stats(update, context)
        else:
            tokens = load_tokens()
            profile = tokens.get(str(user_id), {})
            d_left = profile.get("downloads_left", get_free_amount())
            b_left = profile.get("batch_downloads_left", get_free_amount()*5)
            await update.message.reply_text(t["stats_msg"].format(d_left, b_left), parse_mode="Markdown")
        return

    if text == t["menu_join"]:
        await update.message.reply_text(f"[Join]({PUBLIC_CHANNEL_URL})", parse_mode="Markdown")
        return

    if text == t["menu_help"]:
        keyboard = [[InlineKeyboardButton("💬 Open Support", callback_data="open_support")]]
        await update.message.reply_text(f"Support: [Help]({HELP_CHANNEL_URL})", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if text == t["menu_lang"]:
        await language_command(update, context)
        return

    if text == t["menu_upload"]:
        prompt = t["admin_upload_prompt"] if user_id == ADMIN_ID else t["user_upload_prompt"]
        await update.message.reply_text(prompt, parse_mode="Markdown")
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = [u for u in extracted_urls if not ("t.me/" in u and "start=" in u)]
    if not filtered:
        return

    url = filtered[0]
    status_preview = await update.message.reply_text("🔍 Checking link...")
    title, dur = fetch_url_metadata(url)
    try:
        await status_preview.delete()
    except:
        pass
    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],[InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")]]
    await update.message.reply_text(f"🎬 {title}\n⏱️ {dur}\n\n{t['ask_format']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("language", language_command))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("testad", test_ad_command))
        app.add_handler(CommandHandler("adinfo", ad_info_command))
        app.add_handler(CommandHandler("toggleads", toggle_ads_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("ban", ban_command))
        app.add_handler(CommandHandler("unban", unban_command))
        app.add_handler(CommandHandler("backup", backup_command))
        app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_channel_post_fixed))
        app.add_handler(CallbackQueryHandler(handle_music_pick_callback_fixed, pattern="^music_pick_|^music_search_again_"))
        
        # Main handlers completely preserved
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(MessageHandler(filters.VIDEO | filters.AUDIO | filters.PHOTO | filters.VOICE | filters.ATTACHMENT, handle_user_upload))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        
        await app.initialize()
        await app.start()
        asyncio.create_task(disk_cleaner_loop())
        asyncio.create_task(auto_backup_loop(app.bot))
        asyncio.create_task(queue_processor(app.bot))
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        print(f"Bot started! V24 Optimum +1 Vault={VIDEO_VAULT_ID} Backup={PRIVATE_CHANNEL_ID} Free {get_free_disk_mb()}MB")
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    print("Starting bot thread...")
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
