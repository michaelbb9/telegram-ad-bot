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
import uuid
import types
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
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
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
FILE_LINKS_FILE = "file_links.json"
FILE_LINK_STATE_FILE = "file_link_states.json"
FILE_LINK_STORAGE_ID = -1003906423952

BACKUP_FILES = [
    CHANNELS_FILE, LANG_FILE, CONFIG_FILE, ACTIVITY_FILE, CACHE_FILE, 
    UPLOADS_FILE, UPLOAD_LIMITS_FILE, DRIP_FILE, FLOOD_FILE, BANNED_FILE,
    FILE_LINKS_FILE, FILE_LINK_STATE_FILE
]

active_batch_sessions = {}
pending_batch_payloads = {}
paused_batches = {}
pending_single_links = {}

MAX_CONCURRENT_SHORT = 3
MIN_FREE_DISK_MB = 150
MTPROTO_MAX_MB = 300
active_downloads = 0
download_lock = asyncio.Lock()
download_queue = asyncio.Queue()

FLOOD_LIMIT = 3
FLOOD_WINDOW = 60
FLOOD_COOLDOWN = 30

LANGUAGES = {
    "en": {
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨ FB, INSTA, TIKTOK, X, YOUTUBE! ✨\n\n🔥 WHAT I CAN DO:\n🎬 VIDEOS HD No Watermark!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMAGES Scrape ALL!\n📝 SUBTITLES Auto!\n📦 BATCH 100+ Links!\n⚡ CACHE 1 Sec!\n💎 VAULT Forever!\n📤 UPLOAD FILES!\n🔗 FILE-TO-LINK: Create shareable links! (1 free download credit/link)\n🌐 Other features: Check the web app!\n\n👉 PASTE LINK TO START! 👇** 🚀\n\n🎬 Video, 🎵 Audio, 🖼️ Images, 📝 Subtitles\n📦 Batch Downloader (100+ links)\n⚡ Flash Drops\n💎 Exclusive Vaults\n📤 Upload files\n🔗 File-to-Link: Create shareable file links (costs 1 free download)\n🌐 Other features: Check the web app\n\n👉 Just paste ANY link: TikTok, Facebook, Instagram, Twitter/X, YouTube to start! ✨ All Media Supported!",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **AWESOME! What format you want? Pick below! 🎯 Video=watch, Audio=music!**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳✨ Working magic! 🚀**",
        "error_generic": "❌ Oops! Failed! 😢 Link private/blocked. Try public link! 🔓💡",
        "error_50mb": "❌ Too Big! 😅 This video is over 300MB even at low quality. Try a shorter one! ✂️", "error_no_img": "❌ No images found! 😢 Try another link! 🖼️",
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
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Blocked/private", "failed_generic": "❌ Failed",
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

# --- NEW UNIVERSAL RESOLVER WITH TELEGRAM DEBUGGING ---
async def get_canonical_key(url: str, chat_id=None, bot=None):
    original_url = url
    
    # Helper to send debug messages to Telegram
    async def send_debug(text):
        if chat_id and bot:
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except:
                pass

    await send_debug(f"🔍 <b>Processing Link:</b>\n<code>{url}</code>")

    # 1. Resolve short links
    short_link_domains = ["vt.tiktok.com", "vm.tiktok.com", "youtu.be/", "t.co/", "instagr.am/", "fb.watch/"]
    is_short_link = any(domain in url.lower() for domain in short_link_domains)

    if is_short_link:
        await send_debug("🔄 Resolving short link...")
        try:
            # Mobile User-Agent often gets better redirects from TikTok
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
            resolved_url = response.url
            
            if resolved_url != original_url:
                url = resolved_url
                await send_debug(f"✅ Resolved to:\n<code>{url}</code>")
            else:
                await send_debug("⚠️ Link didn't redirect.")
        except Exception as e:
            await send_debug(f"❌ Redirect failed: {str(e)[:100]}")

    # 2. REGEX EXTRACTION (The "Different Approach")
    # This bypasses yt-dlp entirely for TikTok by looking for the ID in the URL path
    # TikTok IDs are usually 19 digits long in the path /video/1234567890123456789
    tiktok_match = re.search(r'/video/(\d{15,20})', url)
    if tiktok_match:
        vid_id = tiktok_match.group(1)
        await send_debug(f"🎯 <b>TikTok Regex Match!</b>\nVideo ID: <code>{vid_id}</code>")
        return f"tiktok_{vid_id}"

    # 3. Try yt-dlp for other platforms (YouTube, etc.)
    await send_debug("🤖 Trying yt-dlp extraction...")
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                extractor = info.get('extractor', 'generic').replace(':', '').replace(' ', '')
                vid_id = info.get('id', '')
                if vid_id:
                    await send_debug(f"✅ yt-dlp found ID: <code>{vid_id}</code>")
                    return f"{extractor}_{vid_id}"
    except Exception as e:
        await send_debug(f"⚠️ yt-dlp failed: {str(e)[:50]}")

    # 4. Fallback: Hash the resolved URL
    await send_debug("🎲 Using URL hash fallback.")
    clean = url.split('?')[0].split('&')[0].lower().strip('/').replace('https://','').replace('http://','')
    h = hashlib.md5(clean.encode()).hexdigest()[:12]
    return f"url_{h}"

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

def restore_cache_info():
    try:
        cache = load_json_file(CACHE_FILE)
        if len(cache)==0:
            logger.info("Cache empty after clear/restart")
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
    if mode in ("monetag", "adsgram"):
        return "monetag"
    elif mode == "adsterra":
        return "adsterra"
    day_epoch = int(time.time() // 86400)
    return "monetag" if (int(user_id) + day_epoch) % 2 == 0 else "adsterra"

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
        r = requests.post(f"{WEB_BASE_URL}/monetag-start",
                          json={"user_id": int(user_id), "kind": kind, "msg_start": int(msg_start),
                                "msg_end": int(msg_end), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200:
            return r.json().get("nonce")
        logger.error(f"adsgram_start HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"adsgram_start: {e}")
    return None

def adsgram_status(user_id):
    try:
        r = requests.post(f"{WEB_BASE_URL}/monetag-status", json={"user_id": int(user_id), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"adsgram_status: {e}")
    return {"status": "error"}

def adsgram_keyboard(user_id, kind="wall", msg_start=0, msg_end=0, extra_rows=None):
    nonce = adsgram_start(user_id, kind, msg_start, msg_end)
    if not nonce:
        return None
    url = f"{WEB_BASE_URL}/monetag?n={nonce}&k={kind}"
    rows = [
        [InlineKeyboardButton("📺 Watch Monetag Ad +1", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Check & Get +1", callback_data="monetag_check")],
        [InlineKeyboardButton("↪️ Use Adsterra fallback (after 2 failures)", callback_data="monetag_fallback")],
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return InlineKeyboardMarkup(rows)

async def report_vault_delivery(user_id, msg_start, msg_end, delivered_message_ids):
    if not delivered_message_ids:
        return
    try:
        response = requests.post(
            f"{WEB_BASE_URL}/api/item-delivered",
            json={
                "user_id": int(user_id),
                "msg_start": int(msg_start),
                "msg_end": int(msg_end),
                "delivered_message_ids": [int(x) for x in delivered_message_ids],
                "event_id": uuid.uuid4().hex,
            },
            headers=API_HEADERS,
            timeout=8,
        )
        if response.status_code != 200:
            logger.warning("Vault analytics rejected delivery: %s %s", response.status_code, response.text[:200])
    except Exception as e:
        logger.warning("Vault analytics report failed: %s", e)

async def deliver_bundle(bot, user_id, msg_start, msg_end):
    fwd_ids = []
    for tid in range(msg_start, msg_end + 1):
        try:
            fwd = await bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
            fwd_ids.append(fwd.message_id)
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Forward {tid} fail: {e}")
    await report_vault_delivery(user_id, msg_start, msg_end, fwd_ids)
    if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end + 1):
        try:
            tut = await bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
            fwd_ids.append(tut.message_id)
        except Exception:
            pass
    warn = await bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
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

def get_min_free_disk_mb():
    config = load_json_file(CONFIG_FILE)
    return config.get("min_free_disk_mb", MIN_FREE_DISK_MB)

def get_mtproto_max_mb():
    config = load_json_file(CONFIG_FILE)
    return config.get("mtproto_max_mb", MTPROTO_MAX_MB)

def download_media_engine(url: str, download_type: str, max_mb=None):
    cap_mb = int(max_mb or get_mtproto_max_mb())
    cap_bytes = cap_mb * 1024 * 1024
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
        ydl_opts.update({'format': 'bestaudio/best', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'ffmpeg_location': ffmpeg_path, 'max_filesize': cap_bytes})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            path = f"{base}.mp3"
            if os.path.exists(path):
                if os.path.getsize(path) > cap_bytes:
                    os.remove(path)
                    raise ValueError("FILE_TOO_LARGE")
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
        tiers = ["best", "bv*[height<=720]+ba/b[height<=720]", "bv*[height<=480]+ba/b[height<=480]", "bv*[height<=360]+ba/b[height<=360]", "worst"]
        too_big = False
        last_err = None
        for fmt in tiers:
            try:
                opts = dict(ydl_opts)
                opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path, 'max_filesize': cap_bytes})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"):
                        path = os.path.splitext(path)[0]+".mp4"
                    if os.path.exists(path):
                        if os.path.getsize(path) > cap_bytes:
                            os.remove(path)
                            too_big = True
                            continue
                        return [path], f"{info.get('height', 'HD')}p", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
                    too_big = True
            except Exception as e:
                if "Unsupported URL" in str(e) or "403" in str(e):
                    raise e
                last_err = e
                continue
        if too_big or last_err is None:
            raise ValueError("FILE_TOO_LARGE")
        raise last_err

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES.get(lang_code, LANGUAGES["en"])
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton(t["menu_upload"]), KeyboardButton("🔗 File-to-Link")],
        [KeyboardButton("🟢 Bot Status")],
        [KeyboardButton("🔄 Change Batch Channel")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("/stats"), KeyboardButton("/toggleads")])
        keyboard.append([KeyboardButton("/testad"), KeyboardButton("/adinfo")])
        keyboard.append([KeyboardButton("/tokencheck"), KeyboardButton("/broadcast")])
        keyboard.append([KeyboardButton("/ban"), KeyboardButton("/unban")])
        keyboard.append([KeyboardButton("/backup"), KeyboardButton("/restore")])
        keyboard.append([KeyboardButton("💾 Disk Config"), KeyboardButton("⚡ MTProto Config")])
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("⚡ Create Flash Drop")])
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
        free_mb = shutil.disk_usage(".").free // (1024*1024)
        min_free = get_min_free_disk_mb()
        if active_downloads < MAX_CONCURRENT_SHORT and free_mb > min_free:
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
                free_mb = shutil.disk_usage(".").free // (1024*1024)
                min_free = get_min_free_disk_mb()
                async with download_lock:
                    can_run = active_downloads < MAX_CONCURRENT_SHORT and free_mb > min_free
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

def file_link_keyboard(state):
    settings = state.get("settings", {})
    expiry = settings.get("expiry", "never")
    expiry_label = {"3600":"1 hour", "86400":"1 day", "604800":"7 days", "2592000":"30 days", "never":"Never"}.get(str(expiry), "Never")
    max_clicks = int(settings.get("max_clicks", 0) or 0)
    kb = [[InlineKeyboardButton(f"⏳ Expiry: {expiry_label}", callback_data="fl_expiry")],
          [InlineKeyboardButton(f"👥 Max uses: {max_clicks if max_clicks else 'Unlimited'}", callback_data="fl_maxuses")],
          [InlineKeyboardButton("🔐 Set password" if not settings.get("password") else "🔐 Change/remove password", callback_data="fl_password")],
          [InlineKeyboardButton(f"📎 Files: {len(state.get('items', []))}", callback_data="fl_refresh")],
          [InlineKeyboardButton("✅ Create Link", callback_data="fl_create"), InlineKeyboardButton("❌ Cancel", callback_data="fl_cancel")]]
    return InlineKeyboardMarkup(kb)

async def file_link_add_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_message or not update.effective_user:
        return False
    uid = str(update.effective_user.id)
    states = load_json_file(FILE_LINK_STATE_FILE)
    state = states.get(uid)
    if not state or state.get("mode") != "collecting":
        return False
    try:
        copied = await context.bot.copy_message(chat_id=FILE_LINK_STORAGE_ID, from_chat_id=update.effective_message.chat_id, message_id=update.effective_message.message_id)
        state.setdefault("items", []).append({"message_id": copied.message_id})
        states[uid] = state
        save_json_file(FILE_LINK_STATE_FILE, states)
        await update.effective_message.reply_text(f"📥 Added file #{len(state['items'])}. Send more, or tap Create Link.", reply_markup=file_link_keyboard(state))
    except Exception as exc:
        logger.exception("File-to-Link storage copy failed")
    return True

async def file_to_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text("🚫 You are banned.")
        return
    states = load_json_file(FILE_LINK_STATE_FILE)
    state = {"mode": "collecting", "items": [], "created_at": time.time(), "settings": {"expiry": "never", "max_clicks": 0, "password": ""}}
    states[str(user_id)] = state
    save_json_file(FILE_LINK_STATE_FILE, states)
    await update.effective_message.reply_text("🔗 **File-to-Link**\nSend the file(s) you want to share.", reply_markup=file_link_keyboard(state), parse_mode="Markdown")

async def file_link_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    links = load_json_file(FILE_LINKS_FILE)
    record = links.get(token)
    if not record or (record.get("expires_at") and time.time() > record["expires_at"]):
        await update.effective_message.reply_text("❌ This file link is invalid or has expired.")
        return
    if record.get("max_clicks", 0) and record.get("clicks", 0) >= record["max_clicks"]:
        await update.effective_message.reply_text("⛔ This link has reached its usage limit.")
        return
    if record.get("password"):
        states = load_json_file(FILE_LINK_STATE_FILE)
        states[str(update.effective_user.id)] = {"mode": "file_link_password", "token": token}
        save_json_file(FILE_LINK_STATE_FILE, states)
        await update.effective_message.reply_text("🔐 This link is password protected. Send the password to continue.")
        return
    await send_file_link_payload(update, context, token, record)

async def send_file_link_payload(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str, record: dict) -> None:
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
        if member.status not in ("member", "administrator", "creator"):
            raise ValueError("not joined")
    except Exception:
        await update.effective_message.reply_text("📢 Join our required channel first: " + PUBLIC_CHANNEL_URL)
        return
    for item in record.get("items", []):
        await context.bot.copy_message(chat_id=user_id, from_chat_id=FILE_LINK_STORAGE_ID, message_id=item["message_id"])
    record["clicks"] = record.get("clicks", 0) + 1
    links = load_json_file(FILE_LINKS_FILE)
    links[token] = record
    save_json_file(FILE_LINKS_FILE, links)
    await update.effective_message.reply_text("✅ Your files have been sent.")

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
    if arg_code.startswith("fl_"):
        await file_link_deep_link(update, context, arg_code[3:])
        return
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
    if assigned_network == "monetag":
        extra = [[InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")]] if user_id == ADMIN_ID else None
        kb = adsgram_keyboard(user_id, "wall", msg_start, msg_end, extra)
        if kb:
            await update.message.reply_text("📺 **Sponsor**\nTap **Watch Ad**, finish the ad in the Mini App, then tap **Check & Get +1**.", reply_markup=kb, parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Ad server busy, try again in a moment.")
        return
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")])
    tutorial_sent = False
    try:
        tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        tutorial_sent = True
        await asyncio.sleep(0.2)
    except Exception as e1:
        logger.error(f"Forward failed: {e1}")
        try:
            tut = await context.bot.copy_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
            tutorial_sent = True
        except Exception as e2:
            logger.error(f"Copy failed: {e2}")
    await update.message.reply_text("👇 **CONTENT LOCKED 🔒**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, download_type, start_index=0):
    if not urls: return
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    success_count = fail_count = 0
    active_batch_sessions[user_id] = True
    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Batch", callback_data="stop_batch")]])
    batch_notice = await bot.send_message(chat_id=chat_id, text=t["batch_start"].format(download_type.upper(), len(urls)), reply_markup=stop_markup, parse_mode="Markdown")
    for index, url in enumerate(urls[start_index:], start=start_index+1):
        if not active_batch_sessions.get(user_id, False): break
        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, headers=API_HEADERS, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except: res_data = {"status": "allowed"}
        tokens = load_tokens()
        d_left = tokens.get(str(user_id), {}).get("downloads_left", 4)
        if res_data.get("status") != "allowed" and d_left <= 0 and user_id != ADMIN_ID:
            assigned_network = get_global_ab_network(user_id)
            if assigned_network == "monetag":
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
            # UPDATED CALLER
            ckey = await get_canonical_key(url, chat_id, bot)
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
                except: pass
            file_paths, res, size = await asyncio.to_thread(download_media_engine, url, download_type, mtproto_limit_mb())
            if file_paths and os.path.exists(file_paths[0]):
                sent = await send_video_file(bot, chat_id, target_destination_id, file_paths[0], f"Item {index}/{len(urls)} Size {size}", None, status_msg)
                if target_destination_id == chat_id:
                    warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                    asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent.message_id, warn.message_id], 540))
                try:
                    vmsg = await bot.send_video(chat_id=VIDEO_VAULT_ID, video=sent.video.file_id, caption=ckey)
                    cache = load_json_file(CACHE_FILE)
                    cache[ckey] = {"file_id": sent.video.file_id, "vault_msg_id": vmsg.message_id, "type": "video", "timestamp": time.time(), "hits": 1}
                    save_json_file(CACHE_FILE, cache)
                except Exception as e: logger.error(f"Vault save: {e}")
                os.remove(file_paths[0])
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}] Failed")
                fail_count += 1
        except Exception as e:
            try: await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}] {str(e)[:50]}")
            except: pass
            fail_count += 1
        await asyncio.sleep(3)
    if user_id in active_batch_sessions: del active_batch_sessions[user_id]
    try: await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except: pass
    if user_id not in paused_batches:
        dest = t["batch_done_chan"].format(success_count, fail_count, success_count) if target_destination_id != chat_id else t["batch_done"].format(success_count, fail_count, success_count)
        await bot.send_message(chat_id=chat_id, text=dest, reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID), parse_mode="Markdown")

async def handle_user_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_banned(user_id): return
    if await file_link_add_media(update, context): return
    chat_id = update.message.chat_id
    track_user_activity(user_id)
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    support_states = load_json_file(SUPPORT_STATES_FILE)
    if str(user_id) in support_states and support_states[str(user_id)].get("mode") == "user_writing":
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("🔒 Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 Ticket [{ticket_id}] From {user_id}\n📎 Media below:", parse_mode="Markdown")
        try: await update.message.forward(chat_id=ADMIN_ID)
        except: await context.bot.copy_message(chat_id=ADMIN_ID, from_chat_id=chat_id, message_id=update.message.message_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("✅ Sent to Admin!")
        return
    if user_id == ADMIN_ID:
        try:
            await update.message.forward(chat_id=PRIVATE_CHANNEL_ID)
            await update.message.reply_text("✅ Saved to vault!", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
        except Exception as e: await update.message.reply_text(f"❌ {e}")
    else:
        limits = load_json_file(UPLOAD_LIMITS_FILE)
        user_str = str(user_id)
        now = time.time()
        if user_str in limits and now - limits[user_str]["timestamp"] < 86400:
            if limits[user_str]["count"] >= 5:
                await update.message.reply_text(t["upload_limit_reached"], reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
                return
            limits[user_str]["count"] += 1
        else: limits[user_str] = {"count": 1, "timestamp": now}
        save_json_file(UPLOAD_LIMITS_FILE, limits)
        try:
            uploads = load_json_file(UPLOADS_FILE)
            uploads[str(int(time.time()))] = {"user_id": user_id, "msg_id": update.message.message_id}
            save_json_file(UPLOADS_FILE, uploads)
            await update.message.forward(chat_id=ADMIN_ID)
            await update.message.reply_text(t["upload_success_user"], reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
        except: await update.message.reply_text("❌ Failed")

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
            await update.message.reply_text(f"🐢 **Slow down!** You sent {FLOOD_LIMIT} links in last minute.\nWait {wait}s before next link.", parse_mode="Markdown")
            return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    # Handle channel-linking forwards before URL parsing. Forwarded channel
    # posts may contain plain text or media, not URLs, so they must be handled
    # before the URL extraction path can return early.
    linking_states = load_linking_states()
    if linking_states.get(str(user_id)) == "waiting_for_channel":
        forward_origin = getattr(update.message, "forward_origin", None)
        f_chat = None
        if forward_origin and getattr(forward_origin, "type", None) == "channel":
            f_chat = getattr(forward_origin, "chat", None)
        # Compatibility with older Telegram / python-telegram-bot fields.
        if f_chat is None:
            f_chat = getattr(update.message, "forward_from_chat", None)
        if f_chat is None:
            await update.message.reply_text("❌ Please forward a message directly from your channel, not a copied message.")
            return
        try:
            bot_member = await context.bot.get_chat_member(chat_id=f_chat.id, user_id=context.bot.id)
            if getattr(bot_member, "status", None) not in ("administrator", "creator"):
                await update.message.reply_text("⚠️ I detected the channel, but I'm not an admin there yet. Add me as an administrator, then forward a channel message again.")
                return
        except Exception as exc:
            logger.warning(f"Could not verify bot admin status in channel {getattr(f_chat, 'id', 'unknown')}: {exc}")
            await update.message.reply_text("⚠️ I couldn't verify my admin access. Please check my admin status and forward another channel message.")
            return
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        linking_states.pop(str(user_id), None)
        save_linking_states(linking_states)
        await update.message.reply_text(f"✅ Linked {getattr(f_chat, 'title', 'your channel')} successfully. You can now use batch downloads to that channel.")
        return
    fl_states = load_json_file(FILE_LINK_STATE_FILE)
    fl_state = fl_states.get(str(user_id))
    if fl_state and fl_state.get("mode") == "file_link_password":
        token = fl_state.get("token")
        links = load_json_file(FILE_LINKS_FILE)
        record = links.get(token)
        fl_states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, fl_states)
        if not record or (record.get("expires_at") and time.time() > record["expires_at"]):
            await update.message.reply_text("❌ This file link is invalid or has expired."); return
        if text.strip() != str(record.get("password", "")):
            await update.message.reply_text("❌ Incorrect password."); return
        if record.get("max_clicks", 0) and record.get("clicks", 0) >= record["max_clicks"]:
            await update.message.reply_text("⛔ This link has reached its usage limit."); return
        await send_file_link_payload(update, context, token, record)
        return
    menu_texts = [t["menu_stats"], t["menu_lang"], t["menu_help"], t["menu_join"], t["menu_upload"], t["menu_uploads"], "🔗 File-to-Link", "🟢 Bot Status", "🔄 Change Batch Channel", "📢 Broadcast", "⚡ Create Flash Drop", "⚙️ Ad Toggle Panel"]
    if text in menu_texts:
        support_states = load_json_file(SUPPORT_STATES_FILE)
        if str(user_id) in support_states:
            del support_states[str(user_id)]
            save_json_file(SUPPORT_STATES_FILE, support_states)
    if text.strip() == "🔗 File-to-Link":
        await file_to_link_command(update, context)
        return
    if text.strip() == "🔄 Change Batch Channel":
        linking_states = load_linking_states()
        linking_states[str(user_id)] = "waiting_for_channel"
        save_linking_states(linking_states)
        await update.message.reply_text(
            "🔄 **Change Batch Download Channel**\n\n"
            "1. Make sure I am an administrator in the new channel.\n"
            "2. Forward any message directly from that channel here.\n"
            "Your new channel will replace the previously linked channel.",
            parse_mode="Markdown"
        )
        return
    fl_states = load_json_file(FILE_LINK_STATE_FILE)
    fl_state = fl_states.get(str(user_id))
    if fl_state and fl_state.get("mode") == "file_link_set_password":
        if text.strip() == "/clearpassword":
            fl_state.setdefault("settings", {})["password"] = ""
        else:
            if len(text) > 64:
                await update.message.reply_text("Password must be 64 characters or fewer."); return
            fl_state.setdefault("settings", {})["password"] = text.strip()
        fl_state["mode"] = "collecting"
        fl_states[str(user_id)] = fl_state; save_json_file(FILE_LINK_STATE_FILE, fl_states)
        await update.message.reply_text("🔐 Password setting saved.", reply_markup=file_link_keyboard(fl_state))
        return
    
    if text == "💾 Disk Config" and user_id == ADMIN_ID:
        current = get_min_free_disk_mb()
        await update.message.reply_text(f"💾 **Disk Configuration**\n\nCurrent min free disk: **{current}MB**\n\nTo change, type:\n`/setdisk <value>`\n\nExample: `/setdisk 500`", parse_mode="Markdown")
        return

    if text == "⚡ MTProto Config" and user_id == ADMIN_ID:
        current = get_mtproto_max_mb()
        await update.message.reply_text(f"⚡ **MTProto Configuration**\n\nCurrent max upload: **{current}MB**\n\nTo change, type:\n`/setmtproto <value>`\n\nExample: `/setmtproto 1000`", parse_mode="Markdown")
        return

    if text.startswith("📦 Set Free") and user_id == ADMIN_ID:
        current = get_free_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i} free", callback_data=f"set_free_{i}") for i in [2,3,4,5]]]
        await update.message.reply_text(f"📦 FREE DOWNLOADS PANEL\n\nCurrent free per day: {current}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text.startswith("🎁 Set Reward") and user_id == ADMIN_ID:
        current = get_reward_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i}", callback_data=f"set_reward_{i}") for i in [1,2,3,5]]]
        await update.message.reply_text(f"🎁 REWARD PANEL\n\nCurrent: +{current} download per 20s ad", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == "⚙️ Ad Toggle Panel" and user_id == ADMIN_ID:
        config = load_json_file(CONFIG_FILE)
        mode = config.get("ad_mode", "auto").upper()
        keyboard = [[InlineKeyboardButton("🔄 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("📺 Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("🌐 Adsterra", callback_data="set_ad_adsterra")]]
        await update.message.reply_text(f"⚙️ Ad Panel\nCurrent: {mode}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    support_states = load_json_file(SUPPORT_STATES_FILE)
    if user_id == ADMIN_ID and str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "admin_replying":
        target_user_id = support_states[str(user_id)]["target_user_id"]
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f"user_reply_ticket_{ticket_id}"), InlineKeyboardButton("🔒 Close", callback_data=f"support_close_{ticket_id}")]]
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"💬 **Admin Reply:**\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            await update.message.reply_text(f"✅ Sent to {target_user_id}!", parse_mode="Markdown")
        except Exception as e: await update.message.reply_text(f"❌ {e}")
        return
    if str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "user_writing":
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("🔒 Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 Ticket [{ticket_id}] From {user_id}\n\n{text}", parse_mode="Markdown")
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("✅ Sent!")
        return
    if text == "⚡ Create Flash Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        states[str(user_id)] = {"mode": "collecting", "items": []}
        save_json_file(DRIP_STATE_FILE, states)
        keyboard = [[KeyboardButton("🚀 Finish & Broadcast Drop")],[KeyboardButton("❌ Cancel / Exit")]]
        await update.message.reply_text("⚡ Flash Drop Mode: Send files", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode="Markdown")
        return
    if text == "🟢 Bot Status":
        await status_command(update, context)
        return

    if text.strip() in ("🧪 Test Ad", "📢 Ad Info"):
        if user_id != ADMIN_ID:
            await update.message.reply_text("✅ Menu updated.", reply_markup=get_main_keyboard(lang, False))
            return
        if text.strip() == "🧪 Test Ad":
            await send_test_ad(update.message, user_id)
            return

    if text.strip() == "📢 Ad Info" and user_id == ADMIN_ID:
        await update.message.reply_text(build_ad_info_text(user_id))
        return
    if text == "📢 Broadcast" and user_id == ADMIN_ID:
        await update.message.reply_text("📢 /broadcast [message] or reply with /broadcast", parse_mode="Markdown")
        return
    if text == "❌ Cancel / Exit" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states:
            del states[str(user_id)]
            save_json_file(DRIP_STATE_FILE, states)
        await update.message.reply_text("❌ Cancelled", reply_markup=get_main_keyboard(lang, True), parse_mode="Markdown")
        return
    if text == "🚀 Finish & Broadcast Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        user_state = states.get(str(user_id))
        if not user_state or not user_state.get("items"):
            await update.message.reply_text("⚠️ No items!")
            return
        user_state["mode"] = "waiting_for_timer"
        save_json_file(DRIP_STATE_FILE, states)
        keyboard = [[InlineKeyboardButton("30s", callback_data="drop_time_30"), InlineKeyboardButton("2m", callback_data="drop_time_120")],[InlineKeyboardButton("5m", callback_data="drop_time_300"), InlineKeyboardButton("10m", callback_data="drop_time_600")]]
        await update.message.reply_text(f"Select timer: {len(user_state['items'])} items", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    states = load_json_file(DRIP_STATE_FILE)
    user_state = states.get(str(user_id))
    if user_state and isinstance(user_state, dict) and user_state.get("mode") == "collecting":
        user_state["items"].append({"chat_id": chat_id, "message_id": update.message.message_id})
        save_json_file(DRIP_STATE_FILE, states)
        await update.message.reply_text(f"📥 Item #{len(user_state['items'])} added")
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
    if text == t["menu_uploads"] and user_id == ADMIN_ID:
        uploads = load_json_file(UPLOADS_FILE)
        if not uploads:
            await update.message.reply_text(t["no_uploads"])
            return
        await update.message.reply_text(t["admin_upload_prompt"])
        for k, data in list(uploads.items())[-20:]:
            try: await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=data["user_id"], message_id=data["msg_id"])
            except: pass
        return
    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = []
    for u in extracted_urls:
        if "t.me/" in u and "start=" in u: continue
        filtered.append(u)
    extracted_urls = filtered
    if not extracted_urls:
        if "t.me/" in text and "start=" in text:
            await update.message.reply_text("👆 Please use the buttons above.", parse_mode="Markdown")
        return
    if user_id != ADMIN_ID:
        tokens = load_tokens()
        user_profile = tokens.get(str(user_id), {})
        d_left = user_profile.get("downloads_left", 4)
        if str(user_id) in tokens and d_left <= 0:
            is_single_link = len(extracted_urls)==1 and "t.me/" not in extracted_urls[0]
            if is_single_link:
                msg_start = msg_end = 0
                pending_single_links[f"retry_{user_id}"] = extracted_urls[0]
            else:
                msg_start = user_profile.get("msg_start", 0)
                msg_end = user_profile.get("msg_end", 0)
            assigned_network = get_global_ab_network(user_id)
            if assigned_network == "monetag":
                kb = adsgram_keyboard(user_id, "wall", msg_start, msg_end)
                if kb:
                    await update.message.reply_text(t["limit_reached"], reply_markup=kb, parse_mode="Markdown")
                else:
                    await update.message.reply_text("⚠️ Ad server busy, try again in a moment.")
                return
            else:
                try:
                    tut = await context.bot.forward_message(chat_id=chat_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    await asyncio.sleep(0.2)
                except: pass
                bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
                keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1", url=bridge_link)], [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")]]
                await update.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                return
    if active_batch_sessions.get(user_id, False): return
    if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
        f_chat = update.message.forward_origin.chat
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        await update.message.reply_text(f"✅ Linked {f_chat.title}", parse_mode="Markdown")
        return
    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"batchtype_video_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"batchtype_audio_{payload_key}")]]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    url = extracted_urls[0]
    status_preview = await update.message.reply_text("🔍 Checking link...")
    title, dur = fetch_url_metadata(url)
    try: await status_preview.delete()
    except: pass
    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],[InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")]]
    await update.message.reply_text(f"🎬 {title}\n⏱️ {dur}\n\n{t['ask_format']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    support_states = load_json_file(SUPPORT_STATES_FILE)
    user_id = update.message.from_user.id
    if is_banned(user_id): return
    if str(user_id) in support_states and support_states[str(user_id)].get("mode") == "user_writing":
        await handle_user_upload(update, context)
        return
    if user_id == ADMIN_ID and str(ADMIN_ID) in support_states and support_states[str(ADMIN_ID)].get("mode") == "admin_replying":
        await handle_user_upload(update, context)
        return
    if await file_link_add_media(update, context): return
        
    document = update.message.document
    
    if user_id == ADMIN_ID and document.file_name in BACKUP_FILES:
        await update.message.reply_text(f"🔄 Restoring <b>{document.file_name}</b>...", parse_mode="HTML")
        try:
            file = await context.bot.get_file(document.file_id)
            temp_path = f"temp_{document.file_name}"
            await file.download_to_drive(temp_path)
            
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            os.replace(temp_path, document.file_name)
            
            await update.message.reply_text(
                f"✅ <b>Restore Successful!</b>\n\n"
                f"📄 File: <b>{document.file_name}</b>\n"
                f"📊 Restored <b>{len(data) if isinstance(data, dict) else len(data)}</b> entries.\n"
                f"Bot settings restored! ⚡",
                parse_mode="HTML"
            )
            return
        except json.JSONDecodeError:
            await update.message.reply_text(f"❌ Restore failed: <b>{document.file_name}</b> is not a valid JSON file.", parse_mode="HTML")
            if os.path.exists(f"temp_{document.file_name}"): os.remove(f"temp_{document.file_name}")
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Restore failed: {str(e)}")
            if os.path.exists(f"temp_{document.file_name}"): os.remove(f"temp_{document.file_name}")
            return

    if not document.file_name or not document.file_name.endswith('.txt'):
        await handle_user_upload(update, context)
        return
    if active_batch_sessions.get(user_id, False): return
    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        urls = re.findall(r'https?://[^\s]+', file_bytes.decode('utf-8', errors='ignore'))
        if not urls:
            await update.message.reply_text("❌ No links")
            return
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = urls
        keyboard = [[InlineKeyboardButton("🎬 Video", callback_data=f"batchtype_video_{payload_key}")]]
        await update.message.reply_text(f"📦 Batch {len(urls)}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"File: {e}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    tokens = load_tokens()
    activity = load_json_file(ACTIVITY_FILE)
    config = load_json_file(CONFIG_FILE)
    now = time.time()
    total_users = len(tokens)
    active_24hr = sum(1 for d in activity.values() if now - d.get("last_active",0) < 86400)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    adsgram_count = adsterra_count = 0
    for uid in tokens.keys():
        try:
            uid_int = int(str(uid).strip())
            net = get_global_ab_network(uid_int)
            if net == "monetag": adsgram_count+=1
            else: adsterra_count+=1
        except: adsterra_count+=1
    sorted_users = sorted(activity.items(), key=lambda x: x[1].get("total_interactions",0), reverse=True)[:10]
    top_text = ""
    for idx,(uid,info) in enumerate(sorted_users,1):
        top_text+=f"{idx}. `{uid}` — {info.get('total_interactions',0)}\n"
    if not top_text: top_text="No activity yet"
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    used_mb = get_downloads_usage_mb()
    cache = load_json_file(CACHE_FILE)
    flood_data = load_json_file(FLOOD_FILE)
    banned = load_json_file(BANNED_FILE)
    total_hits = sum(v.get("hits",0) for v in cache.values() if isinstance(v, dict))
    host_free = shutil.disk_usage(".").free // (1024*1024) if os.path.exists(".") else 0
    txt = (f"📊 **ADVANCED ADMIN**\n\n• Total: **{total_users}**\n• 24h Active: **{active_24hr}**\n• Ad Mode: **{mode}**\n\n📢 **Ad Split:**\n• Monetag: **{adsgram_count}**\n• Adsterra: **{adsterra_count}**\n\n🖥️ **Render:**\n• Used: **{used_mb}MB**\n• Free: **{free_mb}MB**\n• Host: **{host_free}MB**\n• Active: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\n• Queue: **{download_queue.qsize()}**\n• Cache: **{len(cache)}** files\n• Hits: **{total_hits}** saved\n• Flood: **{len(flood_data)}**\n• Banned: **{len(banned)}**\n\n🎞️ **Video Vault:** `{VIDEO_VAULT_ID}`\n🏆 **Top 10:**\n{top_text}")
    await update.message.reply_text(txt, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    cache = load_json_file(CACHE_FILE)
    await update.message.reply_text(f"🟢 **Status V38 Monetag**\nMode: **{mode}**\nFree: **{free_mb}MB**\nDL: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\nQueue: **{download_queue.qsize()}**\nCache: **{len(cache)}**\nVault: **{VIDEO_VAULT_ID}**\nReward: +1 realistic\nFlood: **ON**\nBackup: **6hr to {PRIVATE_CHANNEL_ID}**", parse_mode="Markdown")

async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID: return
    file_list = "\n".join([f"   • <b>{f}</b>" for f in BACKUP_FILES])
    await update.message.reply_text(
        f"🔄 <b>Restore Backup Files</b>\n\n"
        f"1. Go to your private backup channel.\n"
        f"2. <b>Long-press</b> a backup file, then tap all the others to select them.\n"
        f"3. Hit <b>Forward</b> and send them all to this bot at once!\n\n"
        f"<b>Files to restore:</b>\n{file_list}\n\n"
        f"I will automatically detect and restore each file! ⚡",
        parse_mode="HTML"
    )

async def toggle_ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    keyboard = [[InlineKeyboardButton("🔄 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("📺 Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("🌐 Adsterra", callback_data="set_ad_adsterra")]]
    await update.message.reply_text(f"Ad Panel: {mode}\nReward: +1 optimum", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    args = context.args
    reply_msg = update.message.reply_to_message
    if not args and not reply_msg:
        await update.message.reply_text("Usage: /broadcast [msg] or reply with /broadcast", parse_mode="Markdown")
        return
    all_users = set()
    for d in [load_json_file(LANG_FILE), load_tokens()]:
        for uid in d.keys():
            try: all_users.add(int(uid))
            except: pass
    status_msg = await update.message.reply_text(f"🚀 Broadcasting to {len(all_users)}...", parse_mode="Markdown")
    success = fail = 0
    for uid in all_users:
        if uid == ADMIN_ID or is_banned(uid): continue
        try:
            if reply_msg: await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=reply_msg.message_id)
            else: await context.bot.send_message(chat_id=uid, text=" ".join(args), parse_mode="Markdown")
            success+=1
            await asyncio.sleep(0.05)
        except: fail+=1
    await status_msg.edit_text(f"✅ Done\nSent: {success}\nFail: {fail}", parse_mode="Markdown")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        banned[target] = {"banned_at": time.time(), "reason": "spam"}
        save_json_file(BANNED_FILE, banned)
        await update.message.reply_text(f"🚫 Banned {target}", parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        if target in banned:
            del banned[target]
            save_json_file(BANNED_FILE, banned)
            await update.message.reply_text(f"✅ Unbanned {target}", parse_mode="Markdown")
        else: await update.message.reply_text(f"Not banned")
    except Exception as e: await update.message.reply_text(f"❌ {e}")

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(f"📦 Backing up ALL files to {PRIVATE_CHANNEL_ID}...")
    await backup_to_channel(context.bot)
    await update.message.reply_text("✅ Full Backup sent!")

async def set_disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: `/setdisk <mb>`\nExample: `/setdisk 500`", parse_mode="Markdown")
        return
    try:
        value = int(context.args[0])
        if value < 50:
            await update.message.reply_text("⚠️ Value must be at least 50MB.")
            return
        config = load_json_file(CONFIG_FILE)
        config["min_free_disk_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"✅ Minimum free disk space set to **{value}MB**", parse_mode="Markdown")
    except ValueError: await update.message.reply_text("❌ Invalid number.")

async def set_mtproto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: `/setmtproto <mb>`\nExample: `/setmtproto 1000`", parse_mode="Markdown")
        return
    try:
        value = int(context.args[0])
        if value < 50:
            await update.message.reply_text("⚠️ Value must be at least 50MB.")
            return
        config = load_json_file(CONFIG_FILE)
        config["mtproto_max_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"✅ MTProto max upload size set to **{value}MB**", parse_mode="Markdown")
    except ValueError: await update.message.reply_text("❌ Invalid number.")

async def cached_download_and_send(bot, chat_id, url, dl_type, t):
    cache = load_json_file(CACHE_FILE)
    # UPDATED CALLER
    ckey = await get_canonical_key(url, chat_id, bot)
    if ckey in cache:
        try:
            cached = cache[ckey]
            file_id = cached.get("file_id")
            c_type = cached.get("type", "video")
            if file_id:
                if c_type == "video":
                    qual = cached.get("quality", "HD")
                    sz = cached.get("size", "")
                    sent = await bot.send_video(chat_id=chat_id, video=file_id, caption=f"Cached Instant {qual} {sz} {ckey}")
                elif c_type == "audio":
                    sent = await bot.send_audio(chat_id=chat_id, audio=file_id, caption=f"⚡ **Cached Instant** `{ckey}`")
                elif c_type == "image":
                    sent = await bot.send_photo(chat_id=chat_id, photo=file_id, caption=f"⚡ **Cached Instant** `{ckey}`")
                else: raise ValueError("bad cache")
                warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
                asyncio.create_task(schedule_deletion(bot, chat_id, [sent.message_id, warn.message_id], 540))
                cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                save_json_file(CACHE_FILE, cache)
                deduct_download_counter(chat_id, is_batch=False)
                return True
        except Exception as e:
            logger.error(f"Cache send fail {ckey}: {e}")
            try:
                vmid = cache[ckey].get("vault_msg_id")
                if vmid:
                    fwd = await bot.forward_message(chat_id=chat_id, from_chat_id=VIDEO_VAULT_ID, message_id=vmid)
                    warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins (from vault)")
                    asyncio.create_task(schedule_deletion(bot, chat_id, [fwd.message_id, warn.message_id], 540))
                    cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                    save_json_file(CACHE_FILE, cache)
                    deduct_download_counter(chat_id, is_batch=False)
                    return True
            except Exception as e2:
                logger.error(f"Vault fallback fail: {e2}")
                if ckey in cache:
                    del cache[ckey]
                    save_json_file(CACHE_FILE, cache)
    status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type) + f"\n`{ckey}`", parse_mode="Markdown")
    try:
        file_paths, res, size = await asyncio.to_thread(download_media_engine, url, dl_type, mtproto_limit_mb())
        if not file_paths: raise ValueError("FILE_NOT_FOUND")
        cache = load_json_file(CACHE_FILE)
        if dl_type == 'images':
            media_group = [InputMediaPhoto(media=open(p, 'rb')) for p in file_paths]
            sent_media = await bot.send_media_group(chat_id=chat_id, media=media_group)
            warn = await bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)))
            asyncio.create_task(schedule_deletion(bot, chat_id, [m.message_id for m in sent_media] + [warn.message_id], 540))
            try:
                vmsg = await bot.send_photo(chat_id=VIDEO_VAULT_ID, photo=sent_media[0].photo[-1].file_id, caption=ckey)
                cache[ckey] = {"file_id": sent_media[0].photo[-1].file_id, "vault_msg_id": vmsg.message_id, "type": "image", "timestamp": time.time(), "hits": 1, "size": size}
            except: cache[ckey] = {"file_id": sent_media[0].photo[-1].file_id, "type": "image", "timestamp": time.time(), "hits": 1, "size": size}
            for p in file_paths: os.remove(p)
        elif dl_type == 'audio':
            sent_media = await send_audio_file(bot, chat_id, file_paths[0], f"🎵 Size {size} `{ckey}`", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent_media.audio.file_id, caption=ckey)
                cache[ckey] = {"file_id": sent_media.audio.file_id, "vault_msg_id": vmsg.message_id, "type": "audio", "timestamp": time.time(), "hits": 1, "size": size}
            except: cache[ckey] = {"file_id": sent_media.audio.file_id, "type": "audio", "timestamp": time.time(), "hits": 1, "size": size}
            os.remove(file_paths[0])
        else:
            sent_media = await send_video_file(bot, chat_id, chat_id, file_paths[0], f"✨ {res} Size {size} `{ckey}`", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_video(chat_id=VIDEO_VAULT_ID, video=sent_media.video.file_id, caption=ckey)
                cache[ckey] = {"file_id": sent_media.video.file_id, "vault_msg_id": vmsg.message_id, "type": "video", "timestamp": time.time(), "hits": 1, "size": size}
            except Exception as e: logger.error(f"Vault save fail: {e}")
            os.remove(file_paths[0])
        save_json_file(CACHE_FILE, cache)
        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        deduct_download_counter(chat_id, is_batch=False)
        return True
    except Exception as e:
        logger.error(f"DL {ckey}: {e}")
        if "FILE_TOO_LARGE" in str(e): err = t["error_50mb"]
        elif "MTPROTO_OFF" in str(e): err = "⚠️ Big files need fast mode, which is offline right now."
        elif "MTPROTO_PEER" in str(e): err = "⚠️ Send /start to this bot once, then send the link again."
        else: err = t["error_generic"]
        try: await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=err)
        except: pass
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
    if data.startswith("fl_"):
        states = load_json_file(FILE_LINK_STATE_FILE)
        state = states.get(str(user_id))
        if data == "fl_cancel":
            states.pop(str(user_id), None)
            save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer("File-to-Link cancelled")
            try: await query.message.edit_text("❌ File-to-Link cancelled")
            except: pass
            return
        if data == "fl_refresh":
            await query.answer()
            if state: await query.message.edit_reply_markup(reply_markup=file_link_keyboard(state))
            return
        if not state:
            await query.answer("Start File-to-Link again with /filetolink", show_alert=True)
            return
        settings = state.setdefault("settings", {})
        if data == "fl_expiry":
            kb = [[InlineKeyboardButton("1 hour", callback_data="fl_exp_3600"), InlineKeyboardButton("1 day", callback_data="fl_exp_86400")],
                  [InlineKeyboardButton("7 days", callback_data="fl_exp_604800"), InlineKeyboardButton("30 days", callback_data="fl_exp_2592000")],
                  [InlineKeyboardButton("Never", callback_data="fl_exp_never"), InlineKeyboardButton("⬅ Back", callback_data="fl_refresh")]]
            await query.answer()
            await query.message.reply_text("Choose link expiry:", reply_markup=InlineKeyboardMarkup(kb))
            return
        if data.startswith("fl_exp_"):
            value = data[7:]
            settings["expiry"] = "never" if value == "never" else value
            states[str(user_id)] = state; save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer("Expiry updated")
            try: await query.message.edit_reply_markup(reply_markup=file_link_keyboard(state))
            except: pass
            return
        if data == "fl_maxuses":
            kb = [[InlineKeyboardButton(str(n), callback_data=f"fl_uses_{n}") for n in (1,5,10)],
                  [InlineKeyboardButton("25", callback_data="fl_uses_25"), InlineKeyboardButton("50", callback_data="fl_uses_50"), InlineKeyboardButton("Unlimited", callback_data="fl_uses_0")],
                  [InlineKeyboardButton("⬅ Back", callback_data="fl_refresh")]]
            await query.answer(); await query.message.reply_text("Choose maximum successful deliveries:", reply_markup=InlineKeyboardMarkup(kb)); return
        if data.startswith("fl_uses_"):
            settings["max_clicks"] = int(data.rsplit("_",1)[1])
            states[str(user_id)] = state; save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer("Usage limit updated")
            try: await query.message.edit_reply_markup(reply_markup=file_link_keyboard(state))
            except: pass
            return
        if data == "fl_password":
            state["mode"] = "file_link_set_password"
            states[str(user_id)] = state; save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer()
            await query.message.reply_text("Send a password for the link, or send /clearpassword to remove it.")
            return
        if data == "fl_create":
            items = state.get("items", [])
            if not items:
                await query.answer("Send at least one file first", show_alert=True); return
            if user_id != ADMIN_ID:
                tokens = load_tokens(); profile = tokens.get(str(user_id))
                if not isinstance(profile, dict):
                    profile = {"user_id": int(user_id), "downloads_left": get_free_amount(), "batch_downloads_left": get_free_amount()*5, "last_reset": time.time()}
                try:
                    last_reset = float(profile.get("last_reset", 0) or 0)
                    if time.time() - last_reset >= 86400:
                        profile["downloads_left"] = get_free_amount(); profile["batch_downloads_left"] = get_free_amount()*5; profile["last_reset"] = time.time()
                except: pass
                remaining = int(profile.get("downloads_left", get_free_amount()) or 0)
                if remaining <= 0:
                    await query.answer("Daily free limit reached. Watch an ad to earn more downloads.", show_alert=True)
                    assigned_network = get_global_ab_network(user_id)
                    if assigned_network == "monetag":
                        kb = adsgram_keyboard(user_id, "wall", 0, 0)
                        if kb: await query.message.reply_text(t["limit_reached"], reply_markup=kb, parse_mode="Markdown")
                        else: await query.message.reply_text("⚠️ Ad server busy.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
                    else:
                        bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
                        reward_kb = [[InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1", url=bridge_link)],
                                     [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
                                     [InlineKeyboardButton("💜 Check & Get +1", callback_data="verify_user")]]
                        await query.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(reward_kb), parse_mode="Markdown")
                    return
                profile["downloads_left"] = remaining - 1
                tokens[str(user_id)] = profile; save_tokens(tokens)
            token = hashlib.sha256(f"{user_id}:{time.time_ns()}".encode()).hexdigest()[:12]
            expiry_setting = settings.get("expiry", "never")
            expires_at = None if expiry_setting == "never" else time.time() + int(expiry_setting)
            links = load_json_file(FILE_LINKS_FILE)
            links[token] = {"creator_id": user_id, "items": items, "created_at": time.time(), "expires_at": expires_at,
                           "max_clicks": int(settings.get("max_clicks", 0) or 0), "clicks": 0, "password": settings.get("password", "")}
            save_json_file(FILE_LINKS_FILE, links)
            states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, states)
            me = await context.bot.get_me()
            link = f"https://t.me/{me.username}?start=fl_{token}"
            await query.answer("Link created")
            await query.message.reply_text(f"🔗 Your File-to-Link is ready:\n{link}\n\nFiles: {len(items)}\nCost: 1 free daily download", disable_web_page_preview=True)
            try: await query.message.edit_reply_markup(reply_markup=None)
            except: pass
            return
        await query.answer()
        return
    if data == "admin_skip_ad" and user_id == ADMIN_ID:
        tokens = load_tokens()
        if str(user_id) in tokens:
            del tokens[str(user_id)]
            save_tokens(tokens)
        await query.answer("✅ Skipped!", show_alert=True)
        try: await query.message.edit_text("✅ Bypassed")
        except: pass
        return
    if data.startswith("set_free_") and user_id == ADMIN_ID:
        val = int(data.replace("set_free_", ""))
        set_free_amount(val)
        await query.answer(f"✅ Free set to {val}!", show_alert=True)
        try: await query.message.edit_text(f"✅ Free Downloads Updated to {val}!", parse_mode="Markdown")
        except: pass
        return
    if data.startswith("set_reward_") and user_id == ADMIN_ID:
        val = int(data.replace("set_reward_", ""))
        set_reward_amount(val)
        await query.answer(f"✅ Reward set to +{val}!", show_alert=True)
        try: await query.message.edit_text(f"✅ Reward Updated to +{val}!", parse_mode="Markdown")
        except: pass
        return
    if data.startswith("set_ad_") and user_id == ADMIN_ID:
        mode = data.replace("set_ad_", "")
        if mode == "adsgram": mode = "monetag"
        config = load_json_file(CONFIG_FILE)
        config["ad_mode"] = mode
        save_json_file(CONFIG_FILE, config)
        await query.answer(f"Updated to {mode.upper().replace('ADSGRAM', 'MONETAG')}", show_alert=True)
        try: await query.message.edit_text(f"✅ Mode: {mode.upper().replace('ADSGRAM','MONETAG')}", parse_mode="Markdown")
        except: pass
        return
    if data == "open_support":
        support_states = load_json_file(SUPPORT_STATES_FILE)
        ticket_id = str(int(time.time()))
        support_states[str(user_id)] = {"mode": "user_writing", "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer("Opened!")
        await query.message.reply_text("✍️ Send message/photo/video/voice/file below.", parse_mode="Markdown")
        return
    if data.startswith("support_reply_"):
        target_user_id = data.replace("support_reply_", "")
        ticket_id = str(int(time.time()))
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(ADMIN_ID)] = {"mode": "admin_replying", "target_user_id": int(target_user_id), "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer("Reply mode!")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✍️ Reply to {target_user_id}:", parse_mode="Markdown")
        return
    if data.startswith("user_reply_ticket_"):
        ticket_id = data.replace("user_reply_ticket_", "")
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(user_id)] = {"mode": "user_writing", "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer("Reply mode!")
        await query.message.reply_text("✍️ Type follow-up below", parse_mode="Markdown")
        return
    if data.startswith("support_close_"):
        await query.answer("Closed!", show_alert=True)
        try: await query.message.edit_text("🔒 Closed")
        except: pass
        return
    if data == "drop_cancel" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states:
            del states[str(user_id)]
            save_json_file(DRIP_STATE_FILE, states)
        await query.answer("Cancelled")
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=chat_id, text="❌ Cancelled", reply_markup=get_main_keyboard(lang, True))
        return
    if data.startswith("drop_time_") and user_id == ADMIN_ID:
        seconds = int(data.replace("drop_time_", ""))
        mins_label = "30 Seconds" if seconds == 30 else f"{seconds//60} Minutes"
        states = load_json_file(DRIP_STATE_FILE)
        user_state = states.get(str(user_id))
        if not user_state or not user_state.get("items"):
            await query.answer("No items!", show_alert=True)
            return
        items_to_drop = user_state["items"]
        del states[str(user_id)]
        save_json_file(DRIP_STATE_FILE, states)
        drop_id = str(int(time.time()))
        expires_at = time.time() + 480
        drop_data = load_json_file(DRIP_FILE)
        drop_data[drop_id] = {"items": items_to_drop, "expires_at": expires_at, "delete_delay": seconds, "delete_label": mins_label, "claimed_users": []}
        save_json_file(DRIP_FILE, drop_data)
        await query.answer(f"{mins_label} set!")
        try: await query.message.delete()
        except: pass
        bot_username = context.bot.username
        claim_url = f"https://t.me/{bot_username}?start=drip_{drop_id}"
        all_users = set()
        for d in [load_json_file(LANG_FILE), load_tokens()]:
            for uid in d.keys():
                try: all_users.add(int(uid))
                except: pass
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 Broadcasting {len(items_to_drop)} items to {len(all_users)}...", parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🎁 Claim Now", url=claim_url)]]
        broadcast_text = f"🚨 FLASH DROP!\nAuto-deletes in {mins_label}\nTap to claim:"
        success = 0
        for uid in all_users:
            if uid == ADMIN_ID or is_banned(uid): continue
            try:
                await context.bot.send_message(chat_id=uid, text=broadcast_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                success+=1
                await asyncio.sleep(0.05)
            except: pass
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Broadcast done to {success}", reply_markup=get_main_keyboard(lang, True), parse_mode="Markdown")
        return
    if data.startswith("age_yes_"):
        drop_id = data.replace("age_yes_", "")
        drip_data = load_json_file(DRIP_FILE)
        drop = drip_data.get(drop_id)
        if not drop:
            await query.answer("Expired!", show_alert=True)
            return
        if time.time() > drop["expires_at"]:
            await query.answer("Expired!", show_alert=True)
            try: await query.message.edit_text("⏳ Expired!")
            except: pass
            return
        if "claimed_users" not in drop: drop["claimed_users"]=[]
        if user_id in drop["claimed_users"]:
            await query.answer("Already claimed!", show_alert=True)
            try: await query.message.edit_text("❌ Already claimed!")
            except: pass
            return
        drop["claimed_users"].append(user_id)
        drip_data[drop_id]=drop
        save_json_file(DRIP_FILE, drip_data)
        await query.answer("Verified!")
        try:
            await query.message.delete()
            sent_ids=[]
            for item in drop["items"]:
                fwd = await context.bot.copy_message(chat_id=user_id, from_chat_id=item["chat_id"], message_id=item["message_id"])
                sent_ids.append(fwd.message_id)
                await asyncio.sleep(0.2)
            warn = await context.bot.send_message(chat_id=user_id, text=f"⏳ Auto-deletes in {drop.get('delete_label','9 Minutes')}")
            sent_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, sent_ids, drop.get("delete_delay",540)))
        except Exception as e: await context.bot.send_message(chat_id=user_id, text=f"❌ {e}")
        return
    if data == "age_no":
        await query.answer("Denied", show_alert=True)
        try: await query.message.edit_text("❌ Denied. Must be 18+")
        except: pass
        return
    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        langs = load_json_file(LANG_FILE)
        langs[str(user_id)]=new_lang
        save_json_file(LANG_FILE, langs)
        new_t = LANGUAGES.get(new_lang, LANGUAGES["en"])
        await query.answer("Updated!", show_alert=True)
        try:
            await query.message.reply_text(new_t["welcome"], reply_markup=get_main_keyboard(new_lang, user_id==ADMIN_ID), parse_mode="Markdown")
            await query.message.delete()
        except: pass
        return
    if data.startswith("batchtype_"):
        parts = data.split("_",2)
        dl_type = parts[1]
        payload_key = parts[2]
        urls = pending_batch_payloads.get(payload_key)
        if not urls:
            await query.answer("Expired", show_alert=True)
            return
        await query.message.delete()
        keyboard = [[InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{dl_type}_{payload_key}")], [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{dl_type}_{payload_key}")], [InlineKeyboardButton("🔄 Change Channel", callback_data="change_channel")]]
        await context.bot.send_message(chat_id=chat_id, text=t["batch_dest"].format(len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if data.startswith("fmt_"):
        parts = data.split("_",2)
        fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("Expired", show_alert=True)
            return
        await query.answer("Checking vault & server load...")
        await query.message.delete()
        dl_type = 'video'
        if fmt_type == 'aud': dl_type='audio'
        elif fmt_type == 'img': dl_type='images'
        elif fmt_type == 'sub': dl_type='subtitles'
        
        # UPDATED CALLER
        ckey = await get_canonical_key(url, chat_id, context.bot)
        cache = load_json_file(CACHE_FILE)
        if ckey in cache:
            await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
            return
        can_dl = await acquire_slot()
        if can_dl:
            try: await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
            finally: await release_slot()
        else:
            pos = download_queue.qsize()+1
            await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, url, dl_type, t), 'kwargs': {}})
            free_mb = shutil.disk_usage(".").free // (1024*1024)
            await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Server Busy**\nActive: {active_downloads}/{MAX_CONCURRENT_SHORT}\nFree: {free_mb}MB\nQueue: #{pos}\nWill start auto!", parse_mode="Markdown")
        return
    if data == "admin_sim_ad" and user_id == ADMIN_ID:
        try:
            r = requests.get(f"{WEB_BASE_URL}/monetag-reward", params={"userid": user_id, "secret": API_SECRET}, timeout=8)
            ok = r.status_code == 200
        except Exception as e:
            logger.error(f"simulate ad: {e}")
            ok = False
        await query.answer("🛠 Simulated! Now tap Check & Get +1" if ok else "❌ Server not reachable", show_alert=True)
        return
    if data == "monetag_fallback":
        st = adsgram_status(user_id)
        if st.get("status") != "fallback_available":
            await query.answer("Complete two failed Monetag attempts first.", show_alert=True)
            return
        bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
        tokens = load_tokens()
        tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
        save_tokens(tokens)
        await query.message.reply_text("🌐 Monetag failed twice. Continue with Adsterra:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Open Adsterra Link", url=bridge_link)],
                                               [InlineKeyboardButton("✅ Check & Get +1", callback_data="verify_user")]]))
        await query.answer("Adsterra fallback ready", show_alert=True)
        return
    if data in ("monetag_check", "adsgram_check"):
        st = adsgram_status(user_id)
        if st.get("status") == "pending":
            await query.answer("📺 Finish the Monetag ad in the Mini App, then come back and check again.", show_alert=True)
            return
        if st.get("status") == "fallback_available":
            await query.answer("Monetag failed twice. Use the Adsterra fallback button below.", show_alert=True)
            return
        if st.get("status") != "done":
            await query.answer("This ad link expired. Send your link again to get a new one.", show_alert=True)
            return
        reward = st.get("reward", 1)
        try: await query.message.delete()
        except: pass
        if st.get("kind") == "test":
            await query.answer(f"✅ Ad verified! +{reward} added", show_alert=True)
            await context.bot.send_message(chat_id=chat_id, text=f"✅ TEST AD VERIFIED\n\nThe ad was completed and the reward was credited: +{reward} download.")
            return
        await query.answer(f"✅ Sponsor viewed! +{reward} added", show_alert=True)
        paused = paused_batches.pop(user_id, None)
        if paused:
            asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
            return
        msg_start, msg_end = int(st.get("msg_start", 0)), int(st.get("msg_end", 0))
        if msg_start > 0:
            await context.bot.send_message(chat_id=chat_id, text="✅ Verified! Fetching bundle...")
            try: await deliver_bundle(context.bot, user_id, msg_start, msg_end)
            except Exception as e: await context.bot.send_message(chat_id=chat_id, text=f"❌ {e}")
            return
        retry_url = pending_single_links.pop(f"retry_{user_id}", None)
        if retry_url:
            can_dl = await acquire_slot()
            if can_dl:
                try: await cached_download_and_send(context.bot, chat_id, retry_url, "video", t)
                finally: await release_slot()
            else:
                await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, retry_url, "video", t), 'kwargs': {}})
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Queued #{download_queue.qsize()}")
            return
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Refilled +{reward}! Send your link again.")
        return
    if data.startswith("adsgram_complete_") or data in ("adsgram_resume_batch",):
        await query.answer("This button is outdated. Send your link again.", show_alert=True)
        return
    if data == "stop_batch":
        active_batch_sessions[user_id]=False
        await query.answer("Stopping...", show_alert=True)
        try: await query.edit_message_text("🛑 Stopped")
        except: pass
        return
    if data == "resume_batch":
        paused = paused_batches.pop(user_id, None)
        if not paused:
            await query.answer("Expired", show_alert=True)
            return
        await query.answer("Resuming...")
        await query.message.delete()
        asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
        return
    if data.startswith("dest_chat_") or data.startswith("dest_chan_"):
        parts = data.split("_",3)
        action_type, dl_type, payload_key = parts[1], parts[2], parts[3]
        urls = pending_batch_payloads.pop(payload_key, None)
        if not urls:
            await query.answer("Expired", show_alert=True)
            return
        if action_type=="chat":
            await query.answer("Loading...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls, dl_type))
        else:
            user_channels = load_user_channels()
            target = user_channels.get(str(user_id))
            if not target:
                await query.answer("No channel linked!", show_alert=True)
                linking_states = load_linking_states()
                linking_states[str(user_id)]="waiting_for_channel"
                save_linking_states(linking_states)
                await query.message.edit_text("📦 Setup: Make bot admin in channel and forward a message here", parse_mode="Markdown")
                return
            await query.answer("Loading...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, target, urls, dl_type))
        return
    if data == "change_channel":
        linking_states = load_linking_states()
        linking_states[str(user_id)]="waiting_for_channel"
        save_linking_states(linking_states)
        await query.answer("Mode activated!")
        await query.message.reply_text("🔄 **Change Batch Destination Channel**\nMake the bot an administrator in the new channel, then forward any message from that channel here.", parse_mode="Markdown")
        return
    if data == "verify_user":
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator","administrator","member"]:
                await query.answer("Join channel first! 📢 Must join!", show_alert=True)
                return
        except:
            await query.answer("Join channel first! 📢", show_alert=True)
            return
        tokens = load_tokens()
        user_str = str(user_id)
        if user_str not in tokens:
            if user_id != ADMIN_ID:
                await query.answer("⏰ Open the link and watch the 20s timer first!", show_alert=True)
                return
            reward = get_reward_amount()
            tokens[user_str] = {
                "user_id": int(user_id), "downloads_left": reward, "batch_downloads_left": reward * 5,
                "last_reset": time.time(), "msg_start": 0, "msg_end": 0, "clicked_ad": True, "verified": True, "expires": time.time() + 600
            }
            save_tokens(tokens)
            await query.answer("✅ Test Ad Verified! +1 realistic", show_alert=True)
            await query.message.reply_text("✅ **TEST AD VERIFIED!**\n\nReward: +1 download refilled!", parse_mode="Markdown")
            return
        token_data = tokens[user_str]
        if not token_data.get("verified", False):
            await query.answer("⏰ Finish 20s timer first!", show_alert=True)
            return
        msg_start, msg_end = token_data.get("msg_start",0), token_data.get("msg_end",0)
        reward = get_reward_amount()
        tokens[user_str]["downloads_left"] = reward
        tokens[user_str]["batch_downloads_left"] = reward * 5
        tokens[user_str]["verified"] = True
        tokens[user_str]["msg_start"] = 0
        tokens[user_str]["msg_end"] = 0
        save_tokens(tokens)
        await query.answer("Verified! +1 added")
        if user_id in paused_batches:
            keyboard = [[InlineKeyboardButton("▶️ Resume Batch +1", callback_data="resume_batch")]]
            await query.message.reply_text("✅ Verified! Refilled +1. Resume?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
        if msg_start==0:
            await query.message.reply_text("✅ Refilled +1! Download again.")
            return
        await query.message.reply_text("✅ Verified! Fetching bundle...")
        fwd_ids=[]
        try:
            for tid in range(msg_start, msg_end+1):
                try:
                    fwd = await context.bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
                    fwd_ids.append(fwd.message_id)
                    await asyncio.sleep(0.2)
                except Exception as inner_e: logger.error(f"Forward {tid} fail: {inner_e}")
            await report_vault_delivery(user_id, msg_start, msg_end, fwd_ids)
            if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end+1):
                try:
                    tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    fwd_ids.append(tut.message_id)
                except Exception as tut_e: logger.error(f"Tutorial forward fail: {tut_e}")
            warn = await context.bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins")
            fwd_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, fwd_ids, 540))
        except Exception as e: await query.message.reply_text(f"❌ {e}")

TEST_AD_TEXT = "🧪 AD PLACEMENT TEST\n\n1️⃣ User sends link\n2️⃣ User gets 4 FREE downloads\n3️⃣ LIMIT REACHED screen appears\n4️⃣ Tap Watch Ad\n5️⃣ Tap Check & Get +1\n\n👇 TRY THE AD NOW:"

async def send_adsgram_test(message, user_id):
    extra = [[InlineKeyboardButton("🛠 Admin: simulate ad finished", callback_data="admin_sim_ad")]] if user_id == ADMIN_ID else None
    kb = adsgram_keyboard(user_id, "test", 0, 0, extra)
    if not kb:
        await message.reply_text("⚠️ Ad server not reachable.")
        return
    await message.reply_text(TEST_AD_TEXT, reply_markup=kb)

ADSTERRA_TEST_TEXT = "🧪 AD PLACEMENT TEST (Adsterra)\n\n1️⃣ User sends link\n2️⃣ LIMIT REACHED screen appears\n3️⃣ Stay 20s on ad page\n4️⃣ Tap Check & Get +1\n\n👇 TRY THE AD NOW:"

async def send_adsterra_test(message, user_id):
    tokens = load_tokens()
    uid = str(user_id)
    now = time.time()
    if uid in tokens and isinstance(tokens[uid], dict):
        tokens[uid].update({"msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": now + 600})
    else:
        free = get_free_amount()
        tokens[uid] = {"user_id": int(user_id), "downloads_left": free, "batch_downloads_left": free * 5, "last_reset": now, "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": now + 600}
    save_tokens(tokens)
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
    keyboard = [
        [InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1", url=bridge_link)],
        [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")],
    ]
    await message.reply_text(ADSTERRA_TEST_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))

async def send_test_ad(message, user_id):
    if get_global_ab_network(user_id) == "monetag": await send_adsgram_test(message, user_id)
    else: await send_adsterra_test(message, user_id)

def build_ad_info_text(user_id):
    mode = load_json_file(CONFIG_FILE).get("ad_mode", "auto")
    monetag = "• Monetag: LIMIT REACHED screen -> Watch Ad Mini App -> Check & Get +1\n"
    adsterra = "• Adsterra: LIMIT REACHED screen -> Open Link 20s -> Check & Get +1\n"
    if mode in ("monetag", "adsgram"): head, body = "Mode: MONETAG only", monetag
    elif mode == "adsterra": head, body = "Mode: ADSTERRA only", adsterra
    else:
        net = "Monetag" if get_global_ab_network(user_id) == "monetag" else "Adsterra"
        head, body = f"Mode: AUTO (you currently get {net})", monetag + adsterra
    return ("📢 AD INFO\n\nBot: @Michaelbbcvaultbot\n" + head + "\n\n📍 Exact ad placement:\n" + body + "\n• Reward: +1 download per completed ad\n\n🧪 To test: tap 🧪 Test Ad or send /testad")

async def test_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await send_test_ad(update.message, update.effective_user.id)

async def tokencheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    mine = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:8] if BOT_TOKEN else "none"
    try: s = requests.get(f"{WEB_BASE_URL}/monetag-selfcheck", timeout=15).json()
    except Exception as e: await update.message.reply_text(f"❌ Could not reach server: {type(e).__name__}"); return
    same = (s.get("fingerprint") == mine)
    lines = ["🔐 TOKEN CHECK", f"Render bot: fingerprint {mine}", f"PythonAnywhere: fingerprint {s.get('fingerprint')}", f"PA token works: {s.get('telegram_ok')}"]
    lines.append("✅ MATCH" if same else "❌ DIFFERENT")
    await update.message.reply_text("\n".join(lines))

async def ad_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(build_ad_info_text(update.effective_user.id))

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        try:
            from telegram import BotCommand
            await app.bot.set_my_commands([BotCommand("start", "Start bot"), BotCommand("filetolink", "Create a File-to-Link"), BotCommand("language", "Choose language"), BotCommand("stats", "View download balance")])
        except Exception as e: logger.warning(f"Could not set bot menu commands: {e}")
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("filetolink", file_to_link_command))
        app.add_handler(CommandHandler("language", language_command))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("testad", test_ad_command))
        app.add_handler(CommandHandler("adinfo", ad_info_command))
        app.add_handler(CommandHandler("tokencheck", tokencheck_command))
        app.add_handler(CommandHandler("toggleads", toggle_ads_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("ban", ban_command))
        app.add_handler(CommandHandler("unban", unban_command))
        app.add_handler(CommandHandler("backup", backup_command))
        app.add_handler(CommandHandler("restore", restore_command))
        app.add_handler(CommandHandler("setdisk", set_disk_command))
        app.add_handler(CommandHandler("setmtproto", set_mtproto_command))
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

try:
    API_ID = int(os.getenv("API_ID", "0") or "0")
except ValueError: API_ID = 0
API_HASH = os.getenv("API_HASH", "").strip()
BOT_API_LIMIT_BYTES = 49 * 1024 * 1024
MTPROTO = {"client": None, "loop": None, "ready": threading.Event(), "no_parse": None}

def mtproto_limit_mb():
    max_mb = get_mtproto_max_mb()
    min_free = get_min_free_disk_mb()
    spare = (shutil.disk_usage(".").free // (1024*1024)) - min_free
    if not MTPROTO["ready"].is_set(): return 49
    return int(max(50, min(max_mb, spare // max(1, active_downloads))))

def probe_video(path):
    import subprocess
    info = {"duration": 0, "width": 0, "height": 0, "thumb": None}
    try:
        text = subprocess.run([ffmpeg_path, "-hide_banner", "-i", path], capture_output=True, text=True, timeout=60).stderr or ""
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if m: info["duration"] = int(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)))
        m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})[\s,\[]", text)
        if m: info["width"], info["height"] = int(m.group(1)), int(m.group(2))
        thumb = path + ".jpg"
        subprocess.run([ffmpeg_path, "-y", "-ss", "1", "-i", path, "-vframes", "1", "-vf", "scale=320:-2", thumb], capture_output=True, timeout=60)
        if os.path.exists(thumb) and os.path.getsize(thumb) > 0: info["thumb"] = thumb
    except Exception as e: logger.error(f"probe_video: {e}")
    return info

async def mtproto_upload(kind, chat_id, path, caption, **extra):
    if not MTPROTO["ready"].is_set(): raise RuntimeError("MTPROTO_OFF")
    client, loop = MTPROTO["client"], MTPROTO["loop"]
    kwargs = dict(chat_id=chat_id, caption=caption, **extra)
    if MTPROTO["no_parse"] is not None: kwargs["parse_mode"] = MTPROTO["no_parse"]
    async def _send():
        if kind == "audio": return await client.send_audio(audio=path, **kwargs)
        return await client.send_video(video=path, supports_streaming=True, **kwargs)
    fut = asyncio.run_coroutine_threadsafe(_send(), loop)
    try: return await asyncio.wait_for(asyncio.wrap_future(fut), timeout=1800)
    except Exception as e:
        if "PEER_ID_INVALID" in str(e).upper() or "PEER ID INVALID" in str(e).upper(): raise RuntimeError("MTPROTO_PEER")
        raise

async def _tell_uploading(status_msg, path):
    if status_msg is None: return
    try: await status_msg.edit_text(f"📤 Uploading {os.path.getsize(path)/(1024*1024):.0f}MB in fast mode...")
    except Exception: pass

async def send_video_file(bot, chat_id, target_id, path, caption, parse_mode, status_msg=None):
    if os.path.getsize(path) <= BOT_API_LIMIT_BYTES:
        with open(path, 'rb') as f: return await bot.send_video(chat_id=target_id, video=f, caption=caption, parse_mode=parse_mode)
    await _tell_uploading(status_msg, path)
    info = await asyncio.to_thread(probe_video, path)
    try:
        extra = {k: v for k, v in (("duration", info["duration"]), ("width", info["width"]), ("height", info["height"]), ("thumb", info["thumb"])) if v}
        msg = await mtproto_upload("video", chat_id, path, caption.replace("`", ""), **extra)
    finally:
        if info.get("thumb") and os.path.exists(info["thumb"]): os.remove(info["thumb"])
    media = msg.video or msg.document
    file_id, message_id = media.file_id, msg.id
    if target_id != chat_id:
        copied = await bot.copy_message(chat_id=target_id, from_chat_id=chat_id, message_id=message_id)
        try: await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception: pass
        message_id = copied.message_id
    return types.SimpleNamespace(message_id=message_id, video=types.SimpleNamespace(file_id=file_id))

async def send_audio_file(bot, chat_id, path, caption, parse_mode, status_msg=None):
    if os.path.getsize(path) <= BOT_API_LIMIT_BYTES:
        with open(path, 'rb') as f: return await bot.send_audio(chat_id=chat_id, audio=f, caption=caption, parse_mode=parse_mode)
    await _tell_uploading(status_msg, path)
    msg = await mtproto_upload("audio", chat_id, path, caption.replace("`", ""))
    media = msg.audio or msg.document
    return types.SimpleNamespace(message_id=msg.id, audio=types.SimpleNamespace(file_id=media.file_id))

def run_mtproto_worker():
    if not API_ID or not API_HASH:
        print("MTProto worker skipped: API_ID or API_HASH missing.")
        return
    try: from pyrogram import Client as PyroClient
    except ImportError:
        print("MTProto worker skipped: add pyrogram and tgcrypto.")
        return
    try:
        from pyrogram import enums as pyro_enums
        MTPROTO["no_parse"] = pyro_enums.ParseMode.DISABLED
    except Exception: MTPROTO["no_parse"] = None
    import inspect
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        client = PyroClient("mtproto_web_worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
        print("Starting MTProto Worker Thread...")
        started = client.start()
        if inspect.isawaitable(started): loop.run_until_complete(started)
        MTPROTO["client"], MTPROTO["loop"] = client, loop
        MTPROTO["ready"].set()
        print("MTProto worker is running.")
        loop.run_forever()
    except Exception as e:
        MTPROTO["ready"].clear()
        logger.error(f"MTProto worker stopped: {e}")

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    print("Starting bot thread...")
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if not getattr(web_app, '_mtproto_started', False):
    web_app._mtproto_started = True
    if API_ID and API_HASH: threading.Thread(target=run_mtproto_worker, daemon=True).start()
    else: print("MTProto worker not started.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)