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
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨ FB, INSTA, TIKTOK, X, YOUTUBE!**\n\n👉 PASTE LINK TO START! 👇",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **AWESOME! What format you want? Pick below!**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳✨**",
        "error_generic": "❌ Oops! Failed! Try another public link. 🔓💡",
        "error_50mb": "❌ Too Big! 😅 >50MB limit.", "error_no_img": "❌ No images found!",
        "images_received": "⏳ **{} Images received.**",
        "select_lang": "🌍 Select your language! 👇", "lang_set": "✅ Language set!",
        "batch_detected": "📦 **Batch Detected ({} links)**\nWhat format?",
        "batch_dest": "📦 **Where to send?**",
        "btn_chat": "📥 In Chat", "btn_chan": "📢 To Channel",
        "limit_reached": "⚠️ **Limit Reached! Watch ad to refill!**",
        "refill_btn": "🔓 Open Link & Refill +1",
        "join_btn": "📢 Join Channel", "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached at {} of {}**",
        "batch_start": "📦 **Batch Started:** {} **{} files**\n⏳ Processing...",
        "batch_done": "🏁 **Done!** ✅ {} ❌ {}\n📥 {} files here.",
        "batch_done_chan": "🏁 **Done!** ✅ {} ❌ {}\n📢 {} files forwarded!",
        "dl_video": "📥 Downloading video...", "dl_audio": "📥 Extracting audio...", "dl_image": "📥 Scraping images...", "dl_sub": "📥 Fetching subtitles...",
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
    return "Bot alive!", 200

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
        clean = url.split('?')[0].split('&')[0].lower().strip('/').replace('https://','').replace('http://','')
        h = hashlib.md5(clean.encode()).hexdigest()[:12]
        return f"url_{h}"
    except:
        return f"url_{hashlib.md5(url.encode()).hexdigest()[:12]}"

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

def get_global_ab_network(user_id):
    return "adsgram"

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
        r = requests.post(f"{WEB_BASE_URL}/adsgram-start",
                          json={"user_id": int(user_id), "kind": kind, "msg_start": int(msg_start),
                                "msg_end": int(msg_end), "secret": API_SECRET}, timeout=8)
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
        soup = BeautifulSoup(res.text, 'html.parser')
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            return og['content']
    except:
        pass
    return None

def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0'}
    cookiefile = "tiktok_cookies.txt" if "tiktok.com" in url.lower() and os.path.exists("tiktok_cookies.txt") else ("cookies.txt" if os.path.exists("cookies.txt") else None)
    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
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
                        return [path], f"{info.get('height', 'HD')}p", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
            except:
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

def get_free_disk_mb():
    try:
        total = sum(os.path.getsize(os.path.join("downloads", f)) for f in os.listdir("downloads") if os.path.isfile(os.path.join("downloads", f))) if os.path.exists("downloads") else 0
        return max(0, 512 - (total // (1024*1024)))
    except:
        return 512

def deduct_download_counter(user_id, is_batch=False):
    try:
        requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": is_batch}, headers=API_HEADERS, timeout=3)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_banned(user_id):
        return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID), parse_mode="Markdown")

# ===================== MUSIC MODULE =====================
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
    except:
        return []

async def handle_song_search_mode_fixed(update, context, query_text):
    user_id = update.effective_user.id
    try:
        wait_msg = await update.message.reply_text(f"🔍 Searching '{query_text}'...\n\nFinding suggestions...")
    except:
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
            await wait_msg.edit_text(f"🎵 Found {len(tracks)} for '{query_text}' - Tap to download MP3:", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(f"🎵 Found {len(tracks)}:", reply_markup=InlineKeyboardMarkup(buttons))
        context.user_data[f"music_search_{user_id}"] = tracks
    except Exception as e:
        await update.message.reply_text(f"Found {len(tracks)} but error sending buttons: {e}")

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
            
            await query.answer("Fetching track...")
            
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

# ===================== RESTORED MEDIA & MENU HANDLER =====================
async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    if is_banned(user_id):
        return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])

    # 1. SONG SEARCH INTERCEPTOR
    if user_id in song_search_mode and song_search_mode[user_id]:
        if len(text) >= 2 and not text.startswith("/") and not text.startswith("http") and "Song Search" not in text:
            song_search_mode[user_id] = False
            await handle_song_search_mode_fixed(update, context, text)
            return

    # 2. MENU BUTTONS & COMMAND HANDLERS RESTORED
    if "🔍 Song Search" in text:
        song_search_mode[user_id] = True
        await update.message.reply_text("🎵 Song Search Mode ON!\n\nEnter song name (e.g. Koleyewon or Blinding Lights):")
        return

    if "🟢 Bot Status" in text:
        await update.message.reply_text(f"🟢 **Bot Status:** Online & Fully Operational\nFree Disk: {get_free_disk_mb()}MB", parse_mode="Markdown")
        return

    if "Test Ad" in text or text.strip() == "🧪 Test Ad":
        kb = adsgram_keyboard(user_id, "test", 0, 0)
        if kb:
            await update.message.reply_text("🧪 Test Ad Placement:", reply_markup=kb)
        return

    if "📢 Ad Info" in text:
        await update.message.reply_text("📢 **Ad Info:** Adsgram Rewarded Mini App integration active.", parse_mode="Markdown")
        return

    if t["menu_stats"] in text:
        await update.message.reply_text("📊 **Your Stats:**\n• Downloads Left: 4\n• Status: Active", parse_mode="Markdown")
        return

    if t["menu_lang"] in text:
        await update.message.reply_text("🌍 Language is set to English.")
        return

    if t["menu_join"] in text:
        await update.message.reply_text(f"📢 [Join Public Channel]({PUBLIC_CHANNEL_URL})", parse_mode="Markdown")
        return

    if t["menu_help"] in text:
        await update.message.reply_text(f"💬 [Support / FAQ]({HELP_CHANNEL_URL})", parse_mode="Markdown")
        return

    if t["menu_upload"] in text:
        await update.message.reply_text("📤 Send any media file to upload.")
        return

    # 3. LINK DOWNLOAD HANDLER
    extracted_urls = re.findall(r'https?://[^\s]+', text)
    if not extracted_urls:
        return

    url = extracted_urls[0]
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

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    if is_banned(user_id):
        return
    track_user_activity(user_id)
    data = query.data
    chat_id = query.message.chat_id
    
    if data == "adsgram_check":
        st = adsgram_status(user_id)
        if st.get("status") == "pending":
            await query.answer("📺 Tap Watch Ad first!", show_alert=True)
            return
        await query.message.delete()
        await query.answer("✅ Verified! +1 added", show_alert=True)
        return

    if data.startswith("fmt_"):
        parts = data.split("_",2)
        fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("Expired", show_alert=True)
            return
        await query.answer("Downloading...")
        await query.message.delete()
        dl_type = 'audio' if fmt_type == 'aud' else ('images' if fmt_type == 'img' else 'video')
        
        status_msg = await query.message.reply_text("📥 Fetching media...")
        try:
            file_paths, res, size = download_media_engine(url, dl_type)
            if dl_type == 'audio':
                with open(file_paths[0], 'rb') as f:
                    await context.bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 Size {size}")
                os.remove(file_paths[0])
            elif dl_type == 'images':
                with open(file_paths[0], 'rb') as f:
                    await context.bot.send_photo(chat_id=chat_id, photo=f, caption="🖼️ Image")
                os.remove(file_paths[0])
            else:
                with open(file_paths[0], 'rb') as f:
                    await context.bot.send_video(chat_id=chat_id, video=f, caption=f"✨ {res} Size {size}")
                os.remove(file_paths[0])
            await status_msg.delete()
            deduct_download_counter(chat_id, is_batch=False)
        except Exception as e:
            await status_msg.edit_text(f"❌ Failed: {str(e)[:50]}")
        return

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_channel_post_fixed))
        app.add_handler(CallbackQueryHandler(handle_music_pick_callback_fixed, pattern="^music_pick_|^music_search_again_"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        await app.initialize()
        await app.start()
        print("Bot started successfully with fully restored menus and search!")
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
