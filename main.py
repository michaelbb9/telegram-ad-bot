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

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()   
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

ADSGRAM_BLOCK_ID = os.getenv("ADSGRAM_BLOCK_ID", "")   
API_SECRET = os.getenv("API_SECRET", "change-me")        
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
        [InlineKeyboardButton("🎵 Open Hub & Watch Ad", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Check & Get +1", callback_data="adsgram_check")],
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return InlineKeyboardMarkup(rows)

async def deliver_bundle(bot, user_id, msg_start, msg_end):
    fwd_ids = []
    for tid in range(msg_start, msg_end + 1):
        try:
            fwd = await bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
            fwd_ids.append(fwd.message_id)
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Forward {tid} fail: {e}")
    if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end + 1):
        try:
            tut = await bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
            fwd_ids.append(tut.message_id)
        except Exception:
            pass
    warn = await bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins")
    fwd_ids.append(warn.message_id)
    asyncio.create_task(schedule_deletion(bot, user_id, fwd_ids, 540))

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
        [KeyboardButton(t["menu_upload"])],
        [KeyboardButton("🟢 Bot Status"), KeyboardButton("🎵 Open Music Hub")],
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
    arg_code = args[0]
    if arg_code.startswith("drip_"):
        drop_id = arg_code.replace("drip_", "")
        drip_data = load_json_file(DRIP_FILE)
        drop = drip_data.get(drop_id)
        if not drop:
            await update.message.reply_text("❌ Invalid flash drop.")
            return
        if time.time() > drop["expires_at"]:
            await update.message.reply_text("⏳ Expired!", parse_mode="Markdown")
            return
        if "claimed_users" in drop and user_id in drop["claimed_users"]:
            await update.message.reply_text("❌ Already claimed!", parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton("✅ Yes, 18+", callback_data=f"age_yes_{drop_id}"), InlineKeyboardButton("❌ No", callback_data="age_no")]]
        await update.message.reply_text("🔞 Age verification?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    video_code = arg_code
    if video_code.startswith("vid"):
        clean_code = video_code.replace("vid", "")
        if "to" in clean_code:
            try:
                parts = clean_code.split("to")
                msg_start, msg_end = int(parts[0]), int(parts[1])
            except:
                return
        else:
            try:
                msg_start = msg_end = int(clean_code)
            except:
                return
    else:
        return
    assigned_network = get_global_ab_network(user_id)
    tokens = load_tokens()
    if assigned_network == "adsgram":
        extra = [[InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")]] if user_id == ADMIN_ID else None
        kb = adsgram_keyboard(user_id, "wall", msg_start, msg_end, extra)
        if kb:
            await update.message.reply_text("📺 **Sponsor Hub**\nTap below to open the Mini App for music search and ad rewards.", reply_markup=kb, parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Ad server busy, try again in a moment.")
        return
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")])
    try:
        await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        await asyncio.sleep(0.2)
    except:
        pass
    await update.message.reply_text("👇 **CONTENT LOCKED 🔒**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
        if "youtube.com" in url.lower():
            continue
        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, headers=API_HEADERS, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except:
            res_data = {"status": "allowed"}
        tokens = load_tokens()
        d_left = tokens.get(str(user_id), {}).get("downloads_left", 4)
        if res_data.get("status") != "allowed" and d_left <= 0 and user_id != ADMIN_ID:
            assigned_network = get_global_ab_network(user_id)
            if assigned_network == "adsgram":
                paused_batches[user_id] = {"urls": urls, "next_index": index-1, "target_destination_id": target_destination_id, "chat_id": chat_id, "dl_type": download_type}
                kb = adsgram_keyboard(user_id, "wall", 0, 0)
                await bot.send_message(chat_id=chat_id, text=t["limit_batch"].format(index, len(urls)), reply_markup=kb, parse_mode="Markdown")
                break
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)
            paused_batches[user_id] = {"urls": urls, "next_index": index-1, "target_destination_id": target_destination_id, "chat_id": chat_id, "dl_type": download_type}
            keyboard = [[InlineKeyboardButton(t["refill_btn"], url=bridge_link)]]
            await bot.send_message(chat_id=chat_id, text=t["limit_batch"].format(index, len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            break
        status_msg = await bot.send_message(chat_id=chat_id, text=f"📥 [{index}/{len(urls)}] {t['dl_video']}")
        try:
            ckey = get_canonical_key(url)
            cache = load_json_file(CACHE_FILE)
            if ckey in cache:
                try:
                    cached = cache[ckey]
                    sent = await bot.send_video(chat_id=target_destination_id, video=cached["file_id"], caption=f"Item {index}/{len(urls)} ⚡ Cached")
                    if target_destination_id == chat_id:
                        warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                        asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent.message_id, warn.message_id], 540))
                    cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                    save_json_file(CACHE_FILE, cache)
                    await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                    success_count += 1
                    continue
                except:
                    pass
            file_paths, res, size = download_media_engine(url, download_type)
            if file_paths and os.path.exists(file_paths[0]):
                with open(file_paths[0], 'rb') as f:
                    sent = await bot.send_video(chat_id=target_destination_id, video=f, caption=f"Item {index}/{len(urls)} Size {size}")
                if target_destination_id == chat_id:
                    warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                    asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent.message_id, warn.message_id], 540))
                try:
                    vmsg = await bot.send_video(chat_id=VIDEO_VAULT_ID, video=sent.video.file_id, caption=ckey)
                    cache = load_json_file(CACHE_FILE)
                    cache[ckey] = {"file_id": sent.video.file_id, "vault_msg_id": vmsg.message_id, "type": "video", "timestamp": time.time(), "hits": 1}
                    save_json_file(CACHE_FILE, cache)
                except Exception as e:
                    logger.error(f"Vault save: {e}")
                    cache = load_json_file(CACHE_FILE)
                    cache[ckey] = {"file_id": sent.video.file_id, "type": "video", "timestamp": time.time(), "hits": 1}
                    save_json_file(CACHE_FILE, cache)
                os.remove(file_paths[0])
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}] Failed")
                fail_count += 1
        except Exception as e:
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}] {str(e)[:50]}")
            except:
                pass
            fail_count += 1
        await asyncio.sleep(3)
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
        await update.message.reply_text("🚫 Banned")
        return
    if "http" in text.lower():
        flood, wait = is_flood(user_id)
        if flood:
            await update.message.reply_text(f"🐢 **Slow down!** Wait {wait}s.", parse_mode="Markdown")
            return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])

    if text == "🎵 Open Music Hub":
        nonce = adsgram_start(user_id, "wall", 0, 0)
        url = f"{WEB_BASE_URL}/adsgram?n={nonce}&k=wall"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎵 Open Music Hub & Ads Mini App", web_app=WebAppInfo(url=url))]])
        await update.message.reply_text("🎵 **Music Hub & Rewards**\nTap below to open your Mini App to search music or view ads:", reply_markup=kb, parse_mode="Markdown")
        return

    if text == "🟢 Bot Status":
        await status_command(update, context)
        return
    if "Test Ad" in text or text.strip() == "🧪 Test Ad":
        await send_adsgram_test(update.message, user_id)
        return
    if "Ad Info" in text:
        await update.message.reply_text("📢 AD INFO: Adsgram Mini App Hub with Music Search!")
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = [u for u in extracted_urls if not ("t.me/" in u and "start=" in u)]
    if not filtered:
        return

    if user_id != ADMIN_ID:
        tokens = load_tokens()
        user_profile = tokens.get(str(user_id), {})
        d_left = user_profile.get("downloads_left", 4)
        if str(user_id) in tokens and d_left <= 0:
            kb = adsgram_keyboard(user_id, "wall", 0, 0)
            if kb:
                await update.message.reply_text(t["limit_reached"], reply_markup=kb, parse_mode="Markdown")
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

async def cached_download_and_send(bot, chat_id, url, dl_type, t):
    cache = load_json_file(CACHE_FILE)
    ckey = get_canonical_key(url)
    if ckey in cache:
        try:
            cached = cache[ckey]
            file_id = cached.get("file_id")
            if file_id:
                sent = await bot.send_video(chat_id=chat_id, video=file_id, caption=f"Cached Instant {ckey}")
                warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
                asyncio.create_task(schedule_deletion(bot, chat_id, [sent.message_id, warn.message_id], 540))
                cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                save_json_file(CACHE_FILE, cache)
                deduct_download_counter(chat_id, is_batch=False)
                return True
        except:
            pass
    status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type))
    try:
        file_paths, res, size = download_media_engine(url, dl_type)
        if not file_paths:
            raise ValueError("FILE_NOT_FOUND")
        cache = load_json_file(CACHE_FILE)
        if dl_type == 'audio':
            with open(file_paths[0], 'rb') as f:
                sent_media = await bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 Size {size}")
            os.remove(file_paths[0])
        else:
            with open(file_paths[0], 'rb') as f:
                sent_media = await bot.send_video(chat_id=chat_id, video=f, caption=f"✨ {res} Size {size}")
            os.remove(file_paths[0])
        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        deduct_download_counter(chat_id, is_batch=False)
        return True
    except Exception as e:
        logger.error(f"DL {ckey}: {e}")
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=t["error_generic"])
        except:
            pass
        return False

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    if is_banned(user_id):
        await query.answer("Banned", show_alert=True)
        return
    track_user_activity(user_id)
    data = query.data
    chat_id = query.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])

    if data == "adsgram_check":
        st = adsgram_status(user_id)
        if st.get("status") == "pending":
            await query.answer("📺 Watch the ad in the Hub Mini App first, then come back.", show_alert=True)
            return
        if st.get("status") != "done":
            await query.answer("Ad session expired. Open Hub again.", show_alert=True)
            return
        reward = st.get("reward", 1)
        try:
            await query.message.delete()
        except:
            pass
        await query.answer(f"✅ Refilled +{reward}!", show_alert=True)
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Refilled +{reward}! You can continue downloading.")
        return

    if data == "verify_user":
        tokens = load_tokens()
        reward = get_reward_amount()
        tokens[str(user_id)] = {"user_id": int(user_id), "downloads_left": reward, "verified": True}
        save_tokens(tokens)
        await query.answer("✅ Verified! +1 added", show_alert=True)
        return

async def send_adsgram_test(message, user_id):
    kb = adsgram_keyboard(user_id, "test", 0, 0)
    if not kb:
        await message.reply_text("⚠️ Ad server busy.")
        return
    await message.reply_text("🧪 Test Ad Hub & Music Player:", reply_markup=kb)

async def test_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_adsgram_test(update.message, update.effective_user.id)

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("testad", test_ad_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        await app.initialize()
        await app.start()
        asyncio.create_task(disk_cleaner_loop())
        asyncio.create_task(auto_backup_loop(app.bot))
        asyncio.create_task(queue_processor(app.bot))
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        print("Bot started with Hub Mini App Music Search!")
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
