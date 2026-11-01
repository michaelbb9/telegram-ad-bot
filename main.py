import time
song_search_mode_global = {}
last_song_search_time = {}
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
from flask import Flask, request, jsonify, render_template_string
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

MUSIC_VAULT_CHANNEL_ID = -1004324594855

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
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨**\n\n🔑 **YouTube Login Required:** Send your `cookies.txt` file first using the **🔑 Set Cookies** button to enable YouTube & Music downloads!",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **What format you want? Pick below!**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳**",
        "error_generic": "❌ Oops! Failed! 😢 Link private/blocked. Make sure `cookies.txt` is uploaded!",
        "error_50mb": "❌ Too Big! 😅 >50MB limit.", "error_no_img": "❌ No images found!",
        "images_received": "⏳ **{} Images received.**",
        "select_lang": "🌍 Select your language! 👇", "lang_set": "✅ Language set!",
        "batch_detected": "📦 **Batch Detected ({} links)**",
        "batch_dest": "📦 **Where to send?**",
        "btn_chat": "📥 In Chat", "btn_chan": "📢 To Channel",
        "limit_reached": "⚠️ **Limit Reached! Watch 20s ad → Get +1 download!**",
        "refill_btn": "🔓 Open Link & Refill +1",
        "join_btn": "📢 Join Channel", "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached at {} of {}**",
        "batch_start": "📦 **Batch Started:** {} **{} files**",
        "batch_done": "🏁 **Done!** ✅ {} ❌ {}",
        "batch_done_chan": "🏁 **Done!** ✅ {} ❌ {}",
        "dl_video": "📥 Downloading video...", "dl_audio": "📥 Extracting audio...", "dl_image": "📥 Scraping images...", "dl_sub": "📥 Fetching subtitles...",
        "menu_lang": "🌍 Language", "menu_stats": "📊 My Stats", "menu_help": "💬 Support", "menu_join": "📢 Join Channel",
        "menu_uploads": "🍿 Fan Uploads", "menu_upload": "📤 Upload File",
        "admin_upload_prompt": "📂 **Inbox**",
        "user_upload_prompt": "📤 **Upload File**",
        "upload_success_user": "✅ Sent to Admin!",
        "upload_limit_reached": "⚠️ Limit reached.",
        "no_uploads": "📭 No uploads.",
        "stats_msg": "📊 **Your Stats:**\n• Downloads Left: {}"
    }
}

web_app = Flask(__name__)
@web_app.route('/')
def health_check():
    return "Bot alive! V35 YouTube Login Required Engine WORKING", 200

@web_app.route('/adsgram')
def adsgram_page():
    nonce = request.args.get('n','')
    kind = request.args.get('k','wall')
    html = '''
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<script src="https://sad.adsgram.ai/js/sad.min.js"></script>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
</head><body style="background:#111;color:#fff;font-family:Arial;text-align:center;padding:20px">
<h3>📺 Loading Ad...</h3><div id="status">Initializing...</div>
<script>
const tg = window.Telegram.WebApp; tg.ready(); tg.expand();
const nonce = "NONCE_PLACEHOLDER";
const kind = "KIND_PLACEHOLDER";
const AdController = window.Adsgram.init({ blockId: "BLOCK_ID_PLACEHOLDER" });
AdController.show().then((result) => {
  fetch('/adsgram-done', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nonce: nonce, kind: kind, secret: "SECRET_PLACEHOLDER"})})
  .then(r=>r.json()).then(d=>{
    document.getElementById('status').innerText = "✅ Verified! Go back to bot and tap Check";
    setTimeout(()=>{ tg.close(); }, 2000);
  });
}).catch((result) => {
  document.getElementById('status').innerText = "Ad not completed";
});
</script></body></html>
    '''.replace("NONCE_PLACEHOLDER", nonce).replace("KIND_PLACEHOLDER", kind).replace("BLOCK_ID_PLACEHOLDER", ADSGRAM_BLOCK_ID).replace("SECRET_PLACEHOLDER", API_SECRET)
    return html

@web_app.route('/adsgram-start', methods=['POST'])
def adsgram_start_api():
    try:
        data = request.json
        if data.get('secret') != API_SECRET:
            return jsonify({"error":"bad secret"}), 403
        import uuid
        nonce = str(uuid.uuid4())[:8]
        return jsonify({"nonce": nonce})
    except Exception as e:
        return jsonify({"nonce": str(int(time.time()))[-6:]})

@web_app.route('/adsgram-done', methods=['POST'])
def adsgram_done():
    try:
        data = request.json
        r = requests.post(f"{WEB_BASE_URL}/adsgram-done", json=data, headers=API_HEADERS, timeout=8)
        return jsonify(r.json() if r.status_code==200 else {"reward":1,"status":"done"})
    except Exception as e:
        return jsonify({"reward":1,"status":"done"})

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
        if os.path.exists("cookies.txt"):
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
        cap = f"📦 AUTO-BACKUP {ts}\nFree: {free_mb}MB"
        first = True
        for fname in BACKUP_FILES:
            if os.path.exists(fname):
                try:
                    with open(fname, 'rb') as f:
                        await bot.send_document(chat_id=PRIVATE_CHANNEL_ID, document=f, filename=fname, caption=cap if first else None)
                        first = False
                except Exception as e:
                    logger.error(f"Backup {fname}: {e}")
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
            for fname in os.listdir("downloads"):
                fpath = os.path.join("downloads", fname)
                try:
                    if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > 3 * 60:
                        os.remove(fpath)
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
    for c in ["cookies.txt", "tiktok_cookies.txt"]:
        if os.path.exists(c):
            try:
                os.remove(c)
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
        wait = max(int(FLOOD_COOLDOWN - (now - oldest)), 5)
        return True, wait
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
    except:
        pass
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, headers=API_HEADERS, timeout=5)
    except:
        pass

def adsgram_start(user_id, kind="wall", msg_start=0, msg_end=0):
    try:
        r = requests.post(f"{WEB_BASE_URL}/adsgram-start", json={"user_id": int(user_id), "kind": kind, "msg_start": int(msg_start), "msg_end": int(msg_end), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200:
            return r.json().get("nonce")
    except:
        pass
    return None

def adsgram_status(user_id):
    try:
        r = requests.post(f"{WEB_BASE_URL}/adsgram-status", json={"user_id": int(user_id), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200:
            return r.json()
    except:
        pass
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

async def deliver_bundle(bot, user_id, msg_start, msg_end):
    fwd_ids = []
    for tid in range(msg_start, msg_end + 1):
        try:
            fwd = await bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
            fwd_ids.append(fwd.message_id)
            await asyncio.sleep(0.2)
        except:
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
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = "cookies.txt"
        else:
            raise ValueError("YOUTUBE_LOGIN_REQUIRED")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            title = info.get('title', 'Unknown')[:60]
            duration = info.get('duration', 0)
            mins, secs = divmod(duration, 60)
            return title, f"{mins}m {secs}s" if mins else f"{secs}s"
    except Exception as e:
        if "YOUTUBE_LOGIN_REQUIRED" in str(e):
            raise e
        return "Media Link", "N/A"

def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0'}
    
    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    
    # REQUIRE YOUTUBE LOGIN COOKIES
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = "cookies.txt"
        else:
            raise ValueError("YOUTUBE_LOGIN_REQUIRED")

    try:
        if download_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best', 
                'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 
                'ffmpeg_location': ffmpeg_path
            })
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                base = os.path.splitext(ydl.prepare_filename(info))[0]
                path = f"{base}.mp3"
                if os.path.exists(path):
                    return [path], "MP3", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
            raise ValueError("FILE_NOT_FOUND")
        elif download_type == 'images':
            res = requests.get(url, headers=http_headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            og = soup.find('meta', property='og:image')
            if og and og.get('content'):
                data = requests.get(og['content'], headers=http_headers, timeout=15).content
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
                except Exception as e:
                    if "YOUTUBE_LOGIN_REQUIRED" in str(e):
                        raise e
                    continue
            raise ValueError("FILE_TOO_LARGE")
    finally:
        # Zero-retention cleanup: Immediately delete cookies after job completes
        for tmp_cookie in ["cookies.txt", "tiktok_cookies.txt"]:
            if os.path.exists(tmp_cookie):
                try:
                    os.remove(tmp_cookie)
                except:
                    pass

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES.get(lang_code, LANGUAGES["en"])
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton("🔍 Song Search"), KeyboardButton(t["menu_upload"])],
        [KeyboardButton("🟢 Bot Status V35"), KeyboardButton("🔑 Set Cookies")],
        [KeyboardButton("🧪 Test Ad"), KeyboardButton("📢 Ad Info")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("📢 Broadcast")])
        keyboard.append([KeyboardButton("⚡ Create Flash Drop"), KeyboardButton("⚙️ Ad Toggle Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_free_disk_mb():
    try:
        used = 0
        if os.path.exists("downloads"):
            for f in os.listdir("downloads"):
                fp = os.path.join("downloads", f)
                if os.path.isfile(fp):
                    used += os.path.getsize(fp)
        return max(0, 512 - (used // (1024*1024)))
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
                    can_run = active_downloads < MAX_CONCURRENT_SHORT and get_free_disk_mb() > MIN_FREE_DISK_MB
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
    if is_banned(user_id):
        return
    track_user_activity(user_id)
    
    if "🔑 Set Cookies" in text:
        await update.message.reply_text("🔑 **YouTube Login Required**\n\nTo download YouTube videos or search songs, upload your browser session file named `cookies.txt` directly to this chat.\n\n🔒 **Zero Retention:** It will be automatically deleted after your download completes!")
        return

    if "🔍 Song Search" in text:
        if not os.path.exists("cookies.txt"):
            await update.message.reply_text("❌ **YouTube Login Required!**\n\nPlease upload your `cookies.txt` file first using the **🔑 Set Cookies** button before searching or downloading music.")
            return
        song_search_mode_global[user_id] = True
        await update.message.reply_text("🎵 Song Search Mode ON! Enter song name:")
        return

    if song_search_mode_global.get(user_id) and "http" not in text.lower():
        song_search_mode_global.pop(user_id, None)
        if not os.path.exists("cookies.txt"):
            await update.message.reply_text("❌ **YouTube Login Required!** Please upload `cookies.txt` first.")
            return
        query_text = text.strip()[:100]
        wait_msg = await update.message.reply_text(f"🔍 Searching Deezer for '{query_text}'...")
        try:
            r = requests.get(f"https://api.deezer.com/search?q={query_text}", timeout=8)
            tracks = [{"title": i.get("title"), "artist": i.get("artist", {}).get("name"), "id": str(i.get("id"))} for i in r.json().get("data", [])[:10]]
            if not tracks:
                await wait_msg.edit_text("❌ No songs found.")
                return
            context.bot_data[f"music_search_{user_id}"] = tracks
            buttons = [[InlineKeyboardButton(f"{tr['title']} — {tr['artist']}"[:40], callback_data=f"music_pick_{tr['id']}_{user_id}")] for tr in tracks]
            await wait_msg.edit_text(f"🎵 Found {len(tracks)} tracks — Tap to download MP3:", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await wait_msg.edit_text(f"❌ Error: {e}")
        return

    extracted_urls = [u for u in re.findall(r'https?://[^\s]+', text) if "t.me/" not in u]
    if not extracted_urls:
        return

    url = extracted_urls[0]
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        if not os.path.exists("cookies.txt"):
            await update.message.reply_text("❌ **YouTube Login Required!**\n\nPlease upload your `cookies.txt` file first using the **🔑 Set Cookies** button to unlock YouTube downloads.")
            return

    status_preview = await update.message.reply_text("🔍 Checking link...")
    try:
        title, dur = fetch_url_metadata(url)
    except Exception as e:
        if "YOUTUBE_LOGIN_REQUIRED" in str(e):
            await status_preview.edit_text("❌ **YouTube Login Required!** Upload `cookies.txt` first.")
            return
        title, dur = "Media Link", "N/A"
    try:
        await status_preview.delete()
    except:
        pass

    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    keyboard = [[InlineKeyboardButton("🎬 Video (MP4)", callback_data=f"fmt_vid_{payload_key}")],[InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"fmt_aud_{payload_key}")]]
    await update.message.reply_text(f"🎬 {title}\n⏱️ {dur}\n\nChoose format:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_user_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    doc = update.message.document
    if doc and doc.file_name and "cookie" in doc.file_name.lower():
        try:
            f = await context.bot.get_file(doc.file_id)
            await f.download_to_drive("cookies.txt")
            await update.message.reply_text("🔑 **Cookies uploaded successfully!**\n\nYouTube login session active. It will be automatically deleted right after your download finishes.")
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {e}")
            return
    if user_id == ADMIN_ID:
        try:
            await update.message.forward(chat_id=PRIVATE_CHANNEL_ID)
            await update.message.reply_text("✅ Saved to vault!")
        except:
            pass

async def cached_download_and_send(bot, chat_id, url, dl_type, t):
    if ("youtube.com" in url.lower() or "youtu.be" in url.lower()) and not os.path.exists("cookies.txt"):
        await bot.send_message(chat_id=chat_id, text="❌ **YouTube Login Required!** Please upload `cookies.txt` first.")
        return False

    status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type))
    try:
        file_paths, res, size = download_media_engine(url, dl_type)
        if dl_type == 'audio':
            with open(file_paths[0], 'rb') as f:
                sent = await bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 Size {size}")
        else:
            with open(file_paths[0], 'rb') as f:
                sent = await bot.send_video(chat_id=chat_id, video=f, caption=f"✨ {res} Size {size}")
        os.remove(file_paths[0])
        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        deduct_download_counter(chat_id, is_batch=False)
        return True
    except Exception as e:
        if "YOUTUBE_LOGIN_REQUIRED" in str(e):
            await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ **YouTube Login Required!** Upload `cookies.txt` first.")
        else:
            await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=t["error_generic"])
        return False
    finally:
        for tmp_cookie in ["cookies.txt", "tiktok_cookies.txt"]:
            if os.path.exists(tmp_cookie):
                try:
                    os.remove(tmp_cookie)
                except:
                    pass

async def handle_music_pick_v35(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data.startswith("music_pick_"):
        if not os.path.exists("cookies.txt"):
            await query.answer("YouTube Login Required! Upload cookies.txt first.", show_alert=True)
            return
        parts = data.split("_")
        uid = int(parts[-1])
        track_id = parts[2]
        await query.answer("Downloading MP3...")
        await query.edit_message_text("🎵 Downloading high quality MP3 via login session...")
        
        tracks = context.bot_data.get(f"music_search_{uid}", [])
        title, artist = next(((tr.get("title"), tr.get("artist")) for tr in tracks if str(tr.get("id")) == str(track_id)), ("Unknown", "Unknown"))
        
        def music_download_sync(tt, aa):
            try:
                import tempfile, shutil
                from ytmusicapi import YTMusic
                res = YTMusic().search(f"{tt} {aa}", filter="songs", limit=1)
                if not res or not res[0].get('videoId'):
                    return None, None
                youtube_url = f"https://www.youtube.com/watch?v={res[0]['videoId']}"
                
                td = tempfile.mkdtemp()
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(td, '%(id)s.%(ext)s'),
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                    'ffmpeg_location': ffmpeg_path,
                    'quiet': True,
                    'no_warnings': True
                }
                if os.path.exists("cookies.txt"):
                    ydl_opts['cookiefile'] = "cookies.txt"

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    path = f"{os.path.splitext(ydl.prepare_filename(info))[0]}.mp3"
                    if os.path.exists(path):
                        return path, td
                shutil.rmtree(td, ignore_errors=True)
            except:
                pass
            return None, None

        loop = asyncio.get_event_loop()
        from concurrent.futures import ThreadPoolExecutor
        fp, td = await loop.run_in_executor(ThreadPoolExecutor(max_workers=2), music_download_sync, title, artist)

        if fp and os.path.exists(fp):
            with open(fp, 'rb') as af:
                await context.bot.send_audio(chat_id=uid, audio=af, title=title, performer=artist, caption=f"{title} - {artist} 🎵 MP3")
            shutil.rmtree(td, ignore_errors=True)
            await query.edit_message_text(f"✅ Sent {title} - {artist}!")
            deduct_download_counter(uid, is_batch=False)
        else:
            await query.edit_message_text("❌ Download failed. Ensure valid cookies.txt is loaded.")
        
        for tmp_cookie in ["cookies.txt", "tiktok_cookies.txt"]:
            if os.path.exists(tmp_cookie):
                try:
                    os.remove(tmp_cookie)
                except:
                    pass

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    if is_banned(user_id):
        return
    data = query.data
    chat_id = query.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    
    if data.startswith("fmt_"):
        parts = data.split("_",2)
        fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("Expired", show_alert=True)
            return
        await query.answer("Processing...")
        await query.message.delete()
        dl_type = 'audio' if fmt_type == 'aud' else 'video'
        await cached_download_and_send(context.bot, chat_id, url, dl_type, t)

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(handle_music_pick_v35, pattern="^music_pick_"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_user_upload))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        
        await app.initialize()
        await app.start()
        asyncio.create_task(disk_cleaner_loop())
        asyncio.create_task(auto_backup_loop(app.bot))
        asyncio.create_task(queue_processor(app.bot))
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        print("Bot started! V35 YouTube Login Required Engine WORKING")
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
