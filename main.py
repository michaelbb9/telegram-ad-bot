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
pending_song_search = {}  # In-memory song search mode - no file, instant, no rubbish search

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
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER! 🚀✨ FB, INSTA, TIKTOK, X, YOUTUBE! 🚀✨\n\n🔥 WHAT I CAN DO:\n🎬 VIDEOS HD No Watermark!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMAGES Scrape ALL!\n📝 SUBTITLES Auto!\n📦 BATCH 100+ Links!\n⚡ CACHE 1 Sec!\n💎 VAULT Forever!\n📤 FAN UPLOADS 5/day!\n\n👉 PASTE LINK TO START! 👇** 🚀\n\n🎬 Video, 🎵 Audio, 🖼️ Images, 📝 Subtitles\n📦 Batch Downloader (100+ links)\n⚡ Flash Drops\n💎 Exclusive Vaults\n📤 Fan Uploads (5/day)\n\n👉 Just paste ANY link: TikTok, Facebook, Instagram, Twitter/X, YouTube, Spotify to start! 🚀✨ All Media + Music Supported!\n\n🎵 Spotify: Paste track/playlist link → Get MP3 with tags!\n🎬 Quality: Choose 360p/720p/1080p!",
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
        # CLAUSE 12 FIX: Changed 30s to 20s and +4 to +1 optimum realistic reward
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
        # Separate cookies: tiktok_cookies.txt for TikTok, youtube_cookies.txt for YouTube/Spotify search
        if os.path.exists("tiktok_cookies.txt") and "tiktok.com" in url.lower():
            ydl_opts['cookiefile'] = "tiktok_cookies.txt"
        elif os.path.exists("youtube_cookies.txt") and ("youtube.com" in url.lower() or "youtu.be" in url.lower() or "ytsearch" in url.lower() or "ytmsearch" in url.lower()):
            ydl_opts['cookiefile'] = "youtube_cookies.txt"
        elif os.path.exists("youtube.com_cookies.txt"):
            ydl_opts['cookiefile'] = "youtube.com_cookies.txt"
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

def restore_cache_info():
    try:
        cache = load_json_file(CACHE_FILE)
        if len(cache)==0:
            logger.info("Cache empty after clear/restart - vault channel has 4 vids but index reset. Use /backup to restore from private channel")
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
    if mode == "adsgram":
        return "adsgram"
    elif mode == "adsterra":
        return "adsterra"
    day_epoch = int(time.time() // 86400)
    combined_hash = hash(f"{user_id}_{day_epoch}")
    return "adsgram" if combined_hash % 2 == 0 else "adsterra"

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Tokens: {e}")
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, timeout=5)
    except Exception as e:
        logger.error(f"Save tokens: {e}")

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

def download_media_engine(url: str, download_type: str, quality: str = "best"):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0'}
    cookiefile = None
    if "tiktok.com" in url.lower() and os.path.exists("tiktok_cookies.txt"):
        cookiefile = "tiktok_cookies.txt"
    elif os.path.exists("cookies.txt"):
        cookiefile = "cookies.txt"
    # Check for separate YouTube cookies first
    import os
    yt_cookie = None
    for cf in ["youtube_cookies.txt", "youtube.com_cookies.txt", "yt_cookies.txt"]:
        if os.path.exists(cf):
            yt_cookie = cf
            break
    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if yt_cookie:
        ydl_opts['cookiefile'] = yt_cookie
    elif cookiefile:
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
    elif download_type.startswith("video_"):
        # Quality selector: video_720, video_1080 etc - with cache support
        q = download_type.split("_")[1] if "_" in download_type else "best"
        fmt_map = {
            "360": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
            "480": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "best": "bestvideo+bestaudio/best"
        }
        fmt = fmt_map.get(q, "bestvideo+bestaudio/best")
        ydl_opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path})
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
                if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"):
                    path = os.path.splitext(path)[0]+".mp4"
                if os.path.exists(path):
                    if os.path.getsize(path) > 50*1024*1024:
                        os.remove(path)
                        raise ValueError("FILE_TOO_LARGE")
                    return [path], f"{info.get('height', 'HD')}p", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        except Exception as e:
            raise e
        raise ValueError("FILE_NOT_FOUND")
    elif dl_type.startswith("video_"):
        # Already handled above in quality branch - this else is for generic best
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

def is_spotify_url(url):
    return "open.spotify.com" in url.lower() or "spotify.com" in url.lower()

def get_spotify_metadata(url):
    # Improved: Try oEmbed + extract track name from URL
    track_name = ""
    artist_hint = ""
    try:
        import requests as req
        oembed_url = f"https://open.spotify.com/oembed?url={url}"
        r = req.get(oembed_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            title = data.get("title", "")  # e.g. "Oroma Baby" or "Rema - Oroma Baby"
            # oEmbed often returns track name only, clean it
            if title:
                return title.strip()
    except:
        pass
    # Fallback: try to get from Spotify page title via scraping
    try:
        import requests as req
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = req.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            # Look for <title>Rema - Oroma Baby - song and lyrics by Rema | Spotify</title>
            import re
            m = re.search(r'<title>(.*?)</title>', resp.text, re.I | re.S)
            if m:
                t = m.group(1).replace(" | Spotify", "").replace(" song and lyrics by", " - ").strip()
                # Clean: "Rema - Oroma Baby - song and lyrics by Rema" -> "Oroma Baby"
                if " - " in t:
                    parts = t.split(" - ")
                    # Take first meaningful
                    if len(parts) >= 2:
                        return parts[1].split(" - ")[0].strip() if "song" in parts[1].lower() else parts[0].strip()
                return t[:80]
    except:
        pass
    return "Spotify Track"

def extract_search_terms(spotify_url_or_name):
    # Clean search term for YouTube: remove extra symbols
    term = spotify_url_or_name
    term = term.replace("·", " ").replace("•", " ").strip()
    # If term is URL, get metadata first
    if "open.spotify.com" in term.lower():
        meta = get_spotify_metadata(term)
        if meta and meta != "Spotify Track":
            term = meta
    # Remove "Rema · Rave & Roses · Song · 2022" type junk
    if "·" in term or "Song ·" in term:
        # Take first part before ·
        term = term.split("·")[0].strip()
    return term


def download_spotify_engine(spotify_url_or_name: str):
    # V29 Improved: Multi-search fallback for Oroma Baby type tracks
    import requests as req
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    # Get clean search term
    if "open.spotify.com" in spotify_url_or_name.lower():
        base_term = extract_search_terms(spotify_url_or_name)
    else:
        base_term = spotify_url_or_name.strip()  # Direct song name like "oroma baby"
    
    # Try 3 search variants to avoid live/cover mismatch but still find track
    search_variants = [
        f"ytsearch1:{base_term}",
        f"ytsearch1:{base_term} official audio",
        f"ytsearch1:{base_term} Rema" if "rema" in base_term.lower() or "oroma" in base_term.lower() else f"ytsearch1:{base_term} lyrics",
    ]
    
    # Use youtube_cookies.txt for Spotify -> YouTube search (Oroma Baby fix)
    import os
    _yt_cookie = None
    for _cf in ["youtube_cookies.txt", "youtube.com_cookies.txt", "yt_cookies.txt", "cookies.txt"]:
        if os.path.exists(_cf):
            _yt_cookie = _cf
            break
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
        **({'cookiefile': _yt_cookie} if _yt_cookie else {}),
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'ffmpeg_location': ffmpeg_path,
        'noplaylist': True,
    }
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
    
    last_error = None
    for yt_search in search_variants:
        try:
            time.sleep(0.8)  # Rate limit
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_search, download=True)
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                if not info:
                    continue
                base_name = os.path.splitext(ydl.prepare_filename(info))[0]
                mp3_path = f"{base_name}.mp3"
                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 10000:
                    size = f"{os.path.getsize(mp3_path)/(1024*1024):.1f}MB"
                    yt_title = info.get('title', base_term)
                    # Success!
                    return [mp3_path], yt_title, size
        except Exception as e:
            last_error = e
            continue
    
    # If all 3 failed, try broader ytsearch5 and pick first non-live
    try:
        ydl_opts['noplaylist'] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            broad = f"ytsearch5:{base_term}"
            info = ydl.extract_info(broad, download=False)
            if 'entries' in info and info['entries']:
                for entry in info['entries']:
                    # Skip obvious live/cover if possible
                    t_lower = entry.get('title','').lower()
                    if 'live' in t_lower and 'official' not in t_lower:
                        continue
                    # Download this one
                    entry_id = entry.get('id')
                    if entry_id:
                        ydl2 = yt_dlp.YoutubeDL(ydl_opts)
                        info2 = ydl2.extract_info(f"https://www.youtube.com/watch?v={entry_id}", download=True)
                        base_name = os.path.splitext(ydl2.prepare_filename(info2))[0]
                        mp3_path = f"{base_name}.mp3"
                        if os.path.exists(mp3_path):
                            size = f"{os.path.getsize(mp3_path)/(1024*1024):.1f}MB"
                            return [mp3_path], entry.get('title', base_term), size
    except Exception as e:
        last_error = e
    
    raise ValueError(f"SPOTIFY_NOT_FOUND:{last_error}")


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
        keyboard.append([KeyboardButton("⚡ Create Flash Drop"), KeyboardButton("⚙️ Ad Toggle Panel")])
        keyboard.append([KeyboardButton("🎁 Set Reward (1/2/3/5)"), KeyboardButton("📦 Set Free DL (2/3/4/5)")])
        keyboard.append([KeyboardButton("🔍 Song Search")])
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
        req.get(f"{WEB_BASE_URL}/set_reward?value={val}", timeout=3)
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
        req.get(f"{WEB_BASE_URL}/set_free?value={val}", timeout=3)
    except:
        pass

def get_free_disk_mb():
    try:
        used = get_downloads_usage_mb()
        return max(0, 512 - used)
    except:
        return 512

def deduct_download_counter(user_id, is_batch=False):
    # FIX: Only call server once - no local double save - prevents -2 bug
    try:
        requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": is_batch}, timeout=3)
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
        tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": True, "verified": True, "expires": time.time() + 600}
        save_tokens(tokens)
        keyboard = [[InlineKeyboardButton("📺 Watch Ad (Adsgram)", callback_data=f"adsgram_complete_{msg_start}_{msg_end}")],[InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)]]
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")])
        await update.message.reply_text("📺 **Adsgram Sponsor**\nWatch to unlock!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")])
    # Forward tutorial video 108 for Adsterra bypass - ROBUST VERSION - CLAUSE 13 + 12 FIX
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
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="📺 **TUTORIAL: How to bypass Adsterra link (20s) - Optimum +1**\n\n"
                    "1️⃣ Click **Open Link & Watch Timer 20s**\n"
                    "2️⃣ Click **OPEN** on popup\n"
                    "3️⃣ Stay 20 seconds on ad page\n"
                    "4️⃣ Come back to bot\n"
                    "5️⃣ Click **Check Balance** → Get +1 download (realistic)!\n\n"
                    "⚠️ If tutorial video 108 missing from private channel -1004347828512, re-upload it!",
                    parse_mode="Markdown"
                )
                tutorial_sent = True
            except:
                pass

    await update.message.reply_text("👇 **CONTENT LOCKED 🔒 - Tutorial video above! Watch how to bypass!**" + ("" if tutorial_sent else "\n\n⚠️ Tutorial video 108 missing! Make bot admin in -1004347828512 and ensure message 108 exists!"), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except:
            res_data = {"status": "allowed"}
        tokens = load_tokens()
        d_left = tokens.get(str(user_id), {}).get("downloads_left", 4)
        if res_data.get("status") != "allowed" and d_left <= 0 and user_id != ADMIN_ID:
            assigned_network = get_global_ab_network(user_id)
            if assigned_network == "adsgram":
                tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": True, "verified": True, "expires": time.time() + 600}
                save_tokens(tokens)
                paused_batches[user_id] = {"urls": urls, "next_index": index-1, "target_destination_id": target_destination_id, "chat_id": chat_id, "dl_type": download_type}
                keyboard = [[InlineKeyboardButton("📺 Watch Ad", callback_data="adsgram_resume_batch")]]
                await bot.send_message(chat_id=chat_id, text=t["limit_batch"].format(index, len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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

async def handle_user_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_banned(user_id):
        return
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
        try:
            await update.message.forward(chat_id=ADMIN_ID)
        except:
            await context.bot.copy_message(chat_id=ADMIN_ID, from_chat_id=chat_id, message_id=update.message.message_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("✅ Sent to Admin!")
        return
    if user_id == ADMIN_ID and str(ADMIN_ID) in support_states and support_states[str(ADMIN_ID)].get("mode") == "admin_replying":
        target_user_id = support_states[str(ADMIN_ID)]["target_user_id"]
        ticket_id = support_states[str(ADMIN_ID)]["ticket_id"]
        del support_states[str(ADMIN_ID)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f"user_reply_ticket_{ticket_id}"), InlineKeyboardButton("🔒 Close", callback_data=f"support_close_{ticket_id}")]]
        try:
            await context.bot.copy_message(chat_id=target_user_id, from_chat_id=chat_id, message_id=update.message.message_id, reply_markup=InlineKeyboardMarkup(keyboard))
            await update.message.reply_text(f"✅ Media sent to {target_user_id}!", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
        return
    states = load_json_file(DRIP_STATE_FILE)
    user_state = states.get(str(user_id))
    if user_id == ADMIN_ID and user_state and isinstance(user_state, dict) and user_state.get("mode") == "collecting":
        user_state["items"].append({"chat_id": chat_id, "message_id": update.message.message_id})
        save_json_file(DRIP_STATE_FILE, states)
        await update.message.reply_text(f"📥 Item #{len(user_state['items'])} added")
        return
    if user_id == ADMIN_ID:
        try:
            await update.message.forward(chat_id=PRIVATE_CHANNEL_ID)
            await update.message.reply_text("✅ Saved to vault!")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    else:
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
        try:
            uploads = load_json_file(UPLOADS_FILE)
            uploads[str(int(time.time()))] = {"user_id": user_id, "msg_id": update.message.message_id}
            save_json_file(UPLOADS_FILE, uploads)
            await update.message.forward(chat_id=ADMIN_ID)
            await update.message.reply_text(t["upload_success_user"])
        except:
            await update.message.reply_text("❌ Failed")

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
            await update.message.reply_text(f"🐢 **Slow down!** You sent {FLOOD_LIMIT} links in last minute.\nWait {wait}s before next link.\n\n*Anti-spam for 750 users*", parse_mode="Markdown")
            return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    menu_texts = [t["menu_stats"], t["menu_lang"], t["menu_help"], t["menu_join"], t["menu_upload"], t["menu_uploads"], "🟢 Bot Status", "📢 Broadcast", "⚡ Create Flash Drop", "⚙️ Ad Toggle Panel"]
    if text in menu_texts:
        support_states = load_json_file(SUPPORT_STATES_FILE)
        if str(user_id) in support_states:
            del support_states[str(user_id)]
            save_json_file(SUPPORT_STATES_FILE, support_states)
    if text == "🔍 Song Search" or text.strip().lower() == "song search":
        # Enter song search mode - in-memory, no file, no rubbish auto-search
        pending_song_search[user_id] = time.time()
        # Clear old file states if any
        await update.message.reply_text(
            "🔍 **SONG SEARCH MODE**\n\n"
            "Type song name now (no link needed!):\n"
            "Examples:\n"
            "• `oroma baby`\n"
            "• `blinding lights`\n"
            "• `rema calm down`\n"
            "• `asake joha`\n\n"
            "Bot will search YouTube + Spotify and give MP3!\n\n"
            "Same limits: {} free → Ad → +{} (strict)".format(get_free_amount(), get_reward_amount()),
            parse_mode="Markdown"
        )
        return
    if text.startswith("📦 Set Free") and user_id == ADMIN_ID:
        current = get_free_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i} free", callback_data=f"set_free_{i}") for i in [2,3,4,5]]]
        await update.message.reply_text(f"📦 FREE DOWNLOADS PANEL\n\nCurrent free per day: {current}\n\nSelect new free limit:\n• 2 = Strict\n• 3 = Balanced\n• 4 = Default\n• 5 = Generous", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text.startswith("🎁 Set Reward") and user_id == ADMIN_ID:
        current = get_reward_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i}", callback_data=f"set_reward_{i}") for i in [1,2,3,5]]]
        await update.message.reply_text(f"🎁 REWARD PANEL (Clause 12 Fix)\n\nCurrent: +{current} download per 20s ad\n\nSelect new reward:\n• +1 = Most realistic (best for Adsgram)\n• +2 = Balanced\n• +3 = Generous\n• +5 = Max\n\nStrict limit: User will get EXACTLY this many!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == "⚙️ Ad Toggle Panel" and user_id == ADMIN_ID:
        config = load_json_file(CONFIG_FILE)
        mode = config.get("ad_mode", "auto").upper()
        keyboard = [[InlineKeyboardButton("🔄 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("📺 Adsgram", callback_data="set_ad_adsgram")],[InlineKeyboardButton("🌐 Adsterra", callback_data="set_ad_adsterra")]]
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
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
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

    if "Test Ad" in text or text.strip() == "🧪 Test Ad":
        bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
        keyboard = [
            [InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s (Ad) +1", url=bridge_link)],
            [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
            [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")]
        ]
        await update.message.reply_text(
            "🧪 **AD PLACEMENT TEST - FOR ADSGRAM REVIEWER (Clause 13 + 12 FIX)**\n\n"
            "📍 **WHERE AD IS PLACED:**\n"
            "1️⃣ User pastes ANY link: TikTok, FB, Insta, X, YouTube - ALL MEDIA!\n"
            "2️⃣ User downloads 4 videos FREE\n"
            "3️⃣ On 5th download, LIMIT REACHED wall shows\n"
            "4️⃣ **AD APPEARS HERE:** This message with 3 buttons below!\n"
            "5️⃣ Click Open Link & Watch Timer 20s -> Watch ad\n"
            "6️⃣ Click Check & Get Files -> Gets +1 download (realistic optimum!)\n\n"
            "🔗 **Ad Types:** Adsgram Rewarded + Adsterra Direct Link 20s\n"
            "⏰ **Timer:** 20 seconds\n"
            "🎁 **Reward:** +1 download (Clause 12 fix - realistic, not high)\n"
            "📍 **Also:** /testad command, batch limit\n\n"
            "👇 **TRY AD NOW - CLICK BELOW:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if "Ad Info" in text:
        await update.message.reply_text(
            "📢 **AD INFO - ALL MEDIA DOWNLOADER - Clause 13 + 12 Fix**\n\n"
            "Bot: @Michaelbbcvaultbot\n"
            "Bot ID: 8863904451\n"
            "PlatformID: 53875\n"
            "Block: bot-56953 (new)\n\n"
            "📍 **Exact Ad Placement:**\n"
            "• Screen: After 4 free downloads, 5th attempt\n"
            "• Supports: TikTok, FB, Insta, Twitter/X, YouTube - ALL MEDIA!\n"
            "• Message: Limit Reached! Watch 20s ad → +1 download\n"
            "• Buttons: Open Link 20s +1, Join Channel, Check & Get Files +1\n"
            "• Type: Rewarded Interstitial 20s\n"
            "• Reward: +1 download (realistic optimum - Clause 12 fix)\n"
            "• Test: Tap 🧪 Test Ad button or /testad\n\n"
            "✅ Fixes Clause 13: Clear placement + verifiable via /testad\n"
            "✅ Fixes Clause 12: Realistic reward +1 (not excessively high)",
            parse_mode="Markdown"
        )
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
            try:
                await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=data["user_id"], message_id=data["msg_id"])
            except:
                pass
        return
    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = []
    for u in extracted_urls:
        if "t.me/" in u and "start=" in u:
            continue
        filtered.append(u)
    extracted_urls = filtered
    if not extracted_urls:
        if "t.me/" in text and "start=" in text:
            await update.message.reply_text("👆 Please use the buttons above (Open Link & Watch → Check Balance) instead of pasting the link.", parse_mode="Markdown")
        return
    if user_id != ADMIN_ID:
        tokens = load_tokens()
        user_profile = tokens.get(str(user_id), {})
        d_left = user_profile.get("downloads_left", 4)
        if str(user_id) in tokens and not user_profile.get("verified", False) and d_left <= 0:
            is_single_link = len(extracted_urls)==1 and "t.me/" not in extracted_urls[0]
            if is_single_link:
                msg_start = msg_end = 0
                pending_single_links[f"retry_{user_id}"] = extracted_urls[0]
            else:
                msg_start = user_profile.get("msg_start", 0)
                msg_end = user_profile.get("msg_end", 0)
            assigned_network = get_global_ab_network(user_id)
            if assigned_network == "adsgram":
                keyboard = [[InlineKeyboardButton("📺 Watch Ad +1", callback_data="adsgram_complete_single" if msg_start == 0 else f"adsgram_complete_{msg_start}_{msg_end}")]]
                await update.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                return
            else:
                try:
                    tut = await context.bot.forward_message(chat_id=chat_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    await asyncio.sleep(0.2)
                except:
                    try:
                        tut = await context.bot.copy_message(chat_id=chat_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    except:
                        await context.bot.send_message(chat_id=chat_id, text="📺 TUTORIAL: Open Link & Watch 20s → Stay 20s → Come back → Check Balance = +1 download (realistic)! If video missing, re-upload message 108 to -1004347828512", parse_mode="Markdown")
                bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
                keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1 ⏰ 20s", url=bridge_link)], [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")]]
                await update.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                return
    if active_batch_sessions.get(user_id, False):
        return
    linking_states = load_linking_states()
    if linking_states.get(str(user_id)) == "waiting_for_channel":
        if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
            f_chat = update.message.forward_origin.chat
            user_channels = load_user_channels()
            user_channels[str(user_id)] = f_chat.id
            save_user_channels(user_channels)
            del linking_states[str(user_id)]
            save_linking_states(linking_states)
            await update.message.reply_text(f"✅ Linked {f_chat.title}", parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("❌ Forward from channel")
            return
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
    if is_spotify_url(url):
        # Spotify flow - same monetization as single downloads!
        # Check limits via existing check-download logic (handled earlier)
        status_preview = await update.message.reply_text("🎵 Checking Spotify link...")
        title = get_spotify_metadata(url)
        try:
            await status_preview.delete()
        except:
            pass
        payload_key = f"spotify_{user_id}_{int(time.time())}"
        pending_single_links[payload_key] = url  # Reuse for spotify
        keyboard = [[InlineKeyboardButton(f"🎵 Download: {title[:40]}", callback_data=f"fmt_spotify_{payload_key}")]]
        await update.message.reply_text(f"🎵 **{title}**\n⏱️ Spotify → YouTube Music\n\n👇 **Download as MP3 with tags?**\nSame limits: {get_free_amount()} free → Ad → +{get_reward_amount()}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if "youtube.com" in url.lower() and "music" not in url.lower():
        # Allow YouTube now for quality selector demo - previously paused
        pass
    status_preview = await update.message.reply_text("🔍 Checking link...")
    title, dur = fetch_url_metadata(url)
    try:
        await status_preview.delete()
    except:
        pass
    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    # Quality Selector - NEW!
    keyboard = [
        [InlineKeyboardButton("🎬 Best Quality (1080p)", callback_data=f"fmt_vid_best_{payload_key}")],
        [InlineKeyboardButton("🎬 720p HD", callback_data=f"fmt_vid_720_{payload_key}"), InlineKeyboardButton("🎬 480p", callback_data=f"fmt_vid_480_{payload_key}")],
        [InlineKeyboardButton("🎬 360p (Fast)", callback_data=f"fmt_vid_360_{payload_key}"), InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],
        [InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")]
    ]
    await update.message.reply_text(f"🎬 {title}\n⏱️ {dur}\n\n{t['ask_format']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    support_states = load_json_file(SUPPORT_STATES_FILE)
    user_id = update.message.from_user.id
    if is_banned(user_id):
        return
    if str(user_id) in support_states and support_states[str(user_id)].get("mode") == "user_writing":
        await handle_user_upload(update, context)
        return
    if user_id == ADMIN_ID and str(ADMIN_ID) in support_states and support_states[str(ADMIN_ID)].get("mode") == "admin_replying":
        await handle_user_upload(update, context)
        return
    document = update.message.document
    if not document.file_name or not document.file_name.endswith('.txt'):
        await handle_user_upload(update, context)
        return
    if active_batch_sessions.get(user_id, False):
        return
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
    if update.message.from_user.id != ADMIN_ID:
        return
    tokens = load_tokens()
    activity = load_json_file(ACTIVITY_FILE)
    config = load_json_file(CONFIG_FILE)
    now = time.time()
    total_users = len(tokens)
    active_24hr = sum(1 for d in activity.values() if now - d.get("last_active",0) < 86400)
    mode = config.get("ad_mode","auto").upper()
    adsgram_count = adsterra_count = 0
    for uid in tokens.keys():
        try:
            uid_int = int(str(uid).strip())
            net = get_global_ab_network(uid_int)
            if net == "adsgram":
                adsgram_count+=1
            else:
                adsterra_count+=1
        except:
            adsterra_count+=1
    sorted_users = sorted(activity.items(), key=lambda x: x[1].get("total_interactions",0), reverse=True)[:10]
    top_text = ""
    for idx,(uid,info) in enumerate(sorted_users,1):
        top_text+=f"{idx}. `{uid}` — {info.get('total_interactions',0)}\n"
    if not top_text:
        top_text="No activity yet"
    free_mb = get_free_disk_mb()
    used_mb = get_downloads_usage_mb()
    cache = load_json_file(CACHE_FILE)
    flood_data = load_json_file(FLOOD_FILE)
    banned = load_json_file(BANNED_FILE)
    total_hits = sum(v.get("hits",0) for v in cache.values() if isinstance(v, dict))
    host_free = shutil.disk_usage(".").free // (1024*1024) if os.path.exists(".") else 0
    txt = (f"📊 **ADVANCED ADMIN (via Button)**\n\n• Total: **{total_users}**\n• 24h Active: **{active_24hr}**\n• Ad Mode: **{mode}**\n\n📢 **Ad Split:**\n• Adsgram: **{adsgram_count}**\n• Adsterra: **{adsterra_count}**\n\n🖥️ **Render 512MB Real:**\n• Used: **{used_mb}MB**\n• Free: **{free_mb}MB / 512MB**\n• Host: **{host_free}MB** (ignore)\n• Active: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\n• Queue: **{download_queue.qsize()}**\n• Cache: **{len(cache)}** files\n• Hits: **{total_hits}** saved\n• Flood: **{len(flood_data)}**\n• Banned: **{len(banned)}**\n\n🎞️ **Video Vault:** `{VIDEO_VAULT_ID}`\n🏆 **Top 10:**\n{top_text}\n\n✅ Clause 12 Fixed: +1 realistic\n✅ Clause 13 Fixed: /testad verifiable")
    await update.message.reply_text(txt, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper()
    free_mb = get_free_disk_mb()
    cache = load_json_file(CACHE_FILE)
    await update.message.reply_text(f"🟢 **Status V24 Optimum**\nMode: **{mode}**\nFree: **{free_mb}MB**\nDL: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\nQueue: **{download_queue.qsize()}**\nCache: **{len(cache)}**\nVault: **{VIDEO_VAULT_ID}**\nReward: +1 realistic (Clause 12 fix)\nTest: /testad (Clause 13 fix)\nFlood: **ON**\nBackup: **6hr to {PRIVATE_CHANNEL_ID}**", parse_mode="Markdown")

async def toggle_ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID:
        return
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper()
    keyboard = [[InlineKeyboardButton("🔄 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("📺 Adsgram", callback_data="set_ad_adsgram")],[InlineKeyboardButton("🌐 Adsterra", callback_data="set_ad_adsterra")]]
    await update.message.reply_text(f"Ad Panel: {mode}\nReward: +1 optimum", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID:
        return
    args = context.args
    reply_msg = update.message.reply_to_message
    if not args and not reply_msg:
        await update.message.reply_text("Usage: /broadcast [msg] or reply with /broadcast", parse_mode="Markdown")
        return
    all_users = set()
    for d in [load_json_file(LANG_FILE), load_tokens()]:
        for uid in d.keys():
            try:
                all_users.add(int(uid))
            except:
                pass
    status_msg = await update.message.reply_text(f"🚀 Broadcasting to {len(all_users)}...", parse_mode="Markdown")
    success = fail = 0
    for uid in all_users:
        if uid == ADMIN_ID:
            continue
        if is_banned(uid):
            continue
        try:
            if reply_msg:
                await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=reply_msg.message_id)
            else:
                await context.bot.send_message(chat_id=uid, text=" ".join(args), parse_mode="Markdown")
            success+=1
            await asyncio.sleep(0.05)
        except:
            fail+=1
    await status_msg.edit_text(f"✅ Done\nSent: {success}\nFail: {fail}", parse_mode="Markdown")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        banned[target] = {"banned_at": time.time(), "reason": "spam"}
        save_json_file(BANNED_FILE, banned)
        await update.message.reply_text(f"🚫 Banned {target}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID:
        return
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
        else:
            await update.message.reply_text(f"Not banned")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"📦 Backing up to {PRIVATE_CHANNEL_ID}...")
    await backup_to_channel(context.bot)
    await update.message.reply_text("✅ Backup sent!")

async def cached_download_and_send(bot, chat_id, url, dl_type, t):
    cache = load_json_file(CACHE_FILE)
    base_ckey = get_canonical_key(url)
    # Quality-specific cache: video_720, video_360 etc get separate cache entries
    # Spotify gets its own key via url hash
    if dl_type.startswith("video_"):
        quality = dl_type.split("_")[1] if "_" in dl_type else "best"
        ckey = f"{base_ckey}_{quality}p"
    else:
        ckey = base_ckey

    if ckey in cache:
        try:
            cached = cache[ckey]
            file_id = cached.get("file_id")
            c_type = cached.get("type", "video")
            if file_id:
                if c_type == "video":
                    qual = cached.get("quality", dl_type)
                    sz = cached.get("size", "")
                    cached_note = " (360p cached)" if "360" in ckey else " (720p cached)" if "720" in ckey else " (1080p cached)" if "1080" in ckey else " (Best cached)"
                    sent = await bot.send_video(chat_id=chat_id, video=file_id, caption=f"Cached Instant {qual} {sz} {ckey}{cached_note}")
                elif c_type == "audio":
                    is_spotify = "spotify" in ckey or "url_" in ckey
                    note = "🎵 Spotify Cached" if is_spotify else "⚡ Cached"
                    sent = await bot.send_audio(chat_id=chat_id, audio=file_id, caption=f"{note} Instant `{ckey}`")
                elif c_type == "image":
                    sent = await bot.send_photo(chat_id=chat_id, photo=file_id, caption=f"⚡ **Cached Instant** `{ckey}`")
                else:
                    raise ValueError("bad cache")
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
        file_paths, res, size = download_media_engine(url, dl_type)
        if not file_paths:
            raise ValueError("FILE_NOT_FOUND")
        cache = load_json_file(CACHE_FILE)
        if dl_type == 'images':
            media_group = [InputMediaPhoto(media=open(p, 'rb')) for p in file_paths]
            sent_media = await bot.send_media_group(chat_id=chat_id, media=media_group)
            warn = await bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)))
            asyncio.create_task(schedule_deletion(bot, chat_id, [m.message_id for m in sent_media] + [warn.message_id], 540))
            try:
                vmsg = await bot.send_photo(chat_id=VIDEO_VAULT_ID, photo=sent_media[0].photo[-1].file_id, caption=ckey)
                cache[ckey] = {"file_id": sent_media[0].photo[-1].file_id, "vault_msg_id": vmsg.message_id, "type": "image", "timestamp": time.time(), "hits": 1, "size": size}
            except:
                cache[ckey] = {"file_id": sent_media[0].photo[-1].file_id, "type": "image", "timestamp": time.time(), "hits": 1, "size": size}
            for p in file_paths:
                os.remove(p)
        elif dl_type == 'audio':
            with open(file_paths[0], 'rb') as f:
                sent_media = await bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 Size {size} `{ckey}`", parse_mode="Markdown")
            warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent_media.audio.file_id, caption=ckey)
                cache[ckey] = {"file_id": sent_media.audio.file_id, "vault_msg_id": vmsg.message_id, "type": "audio", "timestamp": time.time(), "hits": 1, "size": size}
            except:
                cache[ckey] = {"file_id": sent_media.audio.file_id, "type": "audio", "timestamp": time.time(), "hits": 1, "size": size}
            os.remove(file_paths[0])
        else:
            with open(file_paths[0], 'rb') as f:
                sent_media = await bot.send_video(chat_id=chat_id, video=f, caption=f"✨ {res} Size {size} `{ckey}`", parse_mode="Markdown")
            warn = await bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_video(chat_id=VIDEO_VAULT_ID, video=sent_media.video.file_id, caption=ckey)
                cache[ckey] = {"file_id": sent_media.video.file_id, "vault_msg_id": vmsg.message_id, "type": "video", "timestamp": time.time(), "hits": 1, "size": size}
            except Exception as e:
                logger.error(f"Vault save fail: {e}")
                cache[ckey] = {"file_id": sent_media.video.file_id, "type": "video", "timestamp": time.time(), "hits": 1, "size": size}
            os.remove(file_paths[0])
        save_json_file(CACHE_FILE, cache)
        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        deduct_download_counter(chat_id, is_batch=False)
        return True
    except Exception as e:
        logger.error(f"DL {ckey}: {e}")
        err = t["error_50mb"] if "FILE_TOO_LARGE" in str(e) else t["error_generic"]
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=err)
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
    if data == "admin_skip_ad" and user_id == ADMIN_ID:
        tokens = load_tokens()
        if str(user_id) in tokens:
            del tokens[str(user_id)]
            save_tokens(tokens)
        await query.answer("✅ Skipped!", show_alert=True)
        try:
            await query.message.edit_text("✅ Bypassed")
        except:
            pass
        return
    if data.startswith("set_free_") and user_id == ADMIN_ID:
        val = int(data.replace("set_free_", ""))
        set_free_amount(val)
        await query.answer(f"✅ Free set to {val}!", show_alert=True)
        try:
            await query.message.edit_text(f"✅ Free Downloads Updated to {val}!\n\n• New users get {val} FREE per day\n• After {val}, ad wall shows\n• Synced to PythonAnywhere!", parse_mode="Markdown")
        except:
            pass
        return
    if data.startswith("set_reward_") and user_id == ADMIN_ID:
        val = int(data.replace("set_reward_", ""))
        set_reward_amount(val)
        await query.answer(f"✅ Reward set to +{val}!", show_alert=True)
        try:
            await query.message.edit_text(f"✅ Reward Updated to +{val}!\n\nStrict limit:\n• After ad, user gets exactly {val}\n• My Stats will show {val}\n• Batch will be {val*5}\n• Synced to PythonAnywhere!", parse_mode="Markdown")
        except:
            pass
        return
    if data.startswith("set_ad_") and user_id == ADMIN_ID:
        mode = data.replace("set_ad_", "")
        config = load_json_file(CONFIG_FILE)
        config["ad_mode"] = mode
        save_json_file(CONFIG_FILE, config)
        await query.answer(f"Updated to {mode.upper()}", show_alert=True)
        try:
            await query.message.edit_text(f"✅ Mode: {mode.upper()}", parse_mode="Markdown")
        except:
            pass
        return
    if data == "open_support":
        support_states = load_json_file(SUPPORT_STATES_FILE)
        ticket_id = str(int(time.time()))
        support_states[str(user_id)] = {"mode": "user_writing", "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer("Opened!")
        await query.message.reply_text("✍️ Send message/photo/video/voice/file below. Next message (including media) goes to Admin.", parse_mode="Markdown")
        return
    if data.startswith("support_reply_"):
        target_user_id = data.replace("support_reply_", "")
        ticket_id = str(int(time.time()))
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(ADMIN_ID)] = {"mode": "admin_replying", "target_user_id": int(target_user_id), "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer("Reply mode!")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✍️ Reply to {target_user_id}: Send text/photo/video/audio/voice/doc", parse_mode="Markdown")
        return
    if data.startswith("user_reply_ticket_"):
        ticket_id = data.replace("user_reply_ticket_", "")
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(user_id)] = {"mode": "user_writing", "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer("Reply mode!")
        await query.message.reply_text("✍️ Type follow-up (with media allowed) below", parse_mode="Markdown")
        return
    if data.startswith("support_close_"):
        await query.answer("Closed!", show_alert=True)
        try:
            await query.message.edit_text("🔒 Closed")
        except:
            pass
        return
    if data == "drop_cancel" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states:
            del states[str(user_id)]
            save_json_file(DRIP_STATE_FILE, states)
        await query.answer("Cancelled")
        try:
            await query.message.delete()
        except:
            pass
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
        try:
            await query.message.delete()
        except:
            pass
        bot_username = context.bot.username
        claim_url = f"https://t.me/{bot_username}?start=drip_{drop_id}"
        all_users = set()
        for d in [load_json_file(LANG_FILE), load_tokens()]:
            for uid in d.keys():
                try:
                    all_users.add(int(uid))
                except:
                    pass
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 Broadcasting {len(items_to_drop)} items to {len(all_users)}...", parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🎁 Claim Now", url=claim_url)]]
        broadcast_text = f"🚨 FLASH DROP!\nAuto-deletes in {mins_label}\nTap to claim:"
        success = 0
        for uid in all_users:
            if uid == ADMIN_ID or is_banned(uid):
                continue
            try:
                await context.bot.send_message(chat_id=uid, text=broadcast_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                success+=1
                await asyncio.sleep(0.05)
            except:
                pass
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
            try:
                await query.message.edit_text("⏳ Expired!")
            except:
                pass
            return
        if "claimed_users" not in drop:
            drop["claimed_users"]=[]
        if user_id in drop["claimed_users"]:
            await query.answer("Already claimed!", show_alert=True)
            try:
                await query.message.edit_text("❌ Already claimed!")
            except:
                pass
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
        except Exception as e:
            await context.bot.send_message(chat_id=user_id, text=f"❌ {e}")
        return
    if data == "age_no":
        await query.answer("Denied", show_alert=True)
        try:
            await query.message.edit_text("❌ Denied. Must be 18+")
        except:
            pass
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
        except:
            pass
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
        keyboard = [[InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{dl_type}_{payload_key}")],[InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{dl_type}_{payload_key}")]]
        await context.bot.send_message(chat_id=chat_id, text=t["batch_dest"].format(len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if data.startswith("do_search_"):
        # Step 2: User tapped SEARCH button - now do YouTube search (callback = reliable, avoids silent bug)
        payload_key = data.replace("do_search_", "")
        song_name = pending_single_links.get(payload_key, "")
        if not song_name:
            await query.answer("❌ Song expired, type again!", show_alert=True)
            return
        await query.answer(f"🔍 Searching {song_name}...")
        try:
            await query.edit_message_text(f"🔍 **Searching YouTube for: {song_name}**\nPlease wait... (using youtube_cookies.txt)")
        except:
            pass
        # Now create download button
        download_key = f"songdl_{user_id}_{int(time.time())}"
        pending_single_links[download_key] = song_name
        keyboard = [[InlineKeyboardButton(f"🎵 Download MP3: {song_name[:35]}", callback_data=f"fmt_spotify_{download_key}")]]
        try:
            await query.edit_message_text(
                f"✅ **Found: {song_name}**\n\n👇 **Tap to download MP3!**\n🎵 Searches: YouTube + YouTube Music\n💰 {get_free_amount()} FREE → Ad → +{get_reward_amount()}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except:
            await context.bot.send_message(chat_id=chat_id, text=f"✅ **Found: {song_name}** - Tap to download", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("fmt_"):
        # Spotify first
        if data.startswith("fmt_spotify_"):
            payload_key = data.replace("fmt_spotify_", "")
            url = pending_single_links.pop(payload_key, None)
            if not url:
                await query.answer("Expired", show_alert=True)
                return
            await query.answer("Searching YouTube for Spotify track... 2s anti-block delay")
            await query.message.delete()
            can_dl = await acquire_slot()
            if can_dl:
                try:
                    status = await context.bot.send_message(chat_id=chat_id, text=t["fetching"].format("Spotify MP3"), parse_mode="Markdown")
                    try:
                        file_paths, res, size = download_spotify_engine(url)
                        if file_paths and os.path.exists(file_paths[0]):
                            with open(file_paths[0], 'rb') as f:
                                sent = await context.bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 {res} | {size} | Spotify", parse_mode="Markdown")
                            warn = await context.bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins")
                            asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent.message_id, warn.message_id], 540))
                            ckey = get_canonical_key(url)
                            try:
                                vmsg = await context.bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent.audio.file_id, caption=ckey)
                                cache = load_json_file(CACHE_FILE)
                                cache[ckey] = {"file_id": sent.audio.file_id, "vault_msg_id": vmsg.message_id, "type": "audio", "timestamp": time.time(), "hits": 1, "size": size}
                                save_json_file(CACHE_FILE, cache)
                            except:
                                pass
                            os.remove(file_paths[0])
                            await context.bot.delete_message(chat_id=chat_id, message_id=status.message_id)
                            deduct_download_counter(chat_id, is_batch=False)
                        else:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=status.message_id, text=t["error_generic"])
                    except Exception as e:
                        logger.error(f"Spotify DL {url}: {e}")
                        try:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=status.message_id, text="❌ Spotify track not found on YouTube (live/cover mismatch protection). Try another Spotify link!")
                        except:
                            pass
                finally:
                    await release_slot()
            else:
                pos = download_queue.qsize()+1
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Queued #{pos} (Spotify)", parse_mode="Markdown")
            return
        
        # Quality selector: data like fmt_vid_720_key or fmt_vid_best_key
        if data.startswith("fmt_vid_"):
            # Extract quality and payload
            # Format: fmt_vid_720_payloadkey or fmt_vid_best_payloadkey
            rest = data.replace("fmt_vid_", "")
            # rest = "720_payloadkey"
            if "_" in rest:
                quality, payload_key = rest.split("_", 1)
            else:
                quality, payload_key = rest, ""
            url = pending_single_links.pop(payload_key, None)
            if not url:
                await query.answer("Expired - paste link again", show_alert=True)
                return
            await query.answer(f"Downloading {quality}p...")
            await query.message.delete()
            dl_type = f"video_{quality}"
            ckey = get_canonical_key(url)
            cache = load_json_file(CACHE_FILE)
            if ckey in cache:
                await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
                return
            can_dl = await acquire_slot()
            if can_dl:
                try:
                    await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
                finally:
                    await release_slot()
            else:
                pos = download_queue.qsize()+1
                await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, url, dl_type, t), 'kwargs': {}})
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Server Busy Queued #{pos} - {quality}p", parse_mode="Markdown")
            return
        
        # Original fmt handling for audio/image
        parts = data.split("_",2)
        fmt_type, payload_key = parts[1], parts[2]
        if False:  # placeholder
            pass
        else:
            # Continue to original logic
            url = pending_single_links.pop(payload_key, None)
            if not url:
                await query.answer("Expired", show_alert=True)
                return
            await query.answer("Checking vault & server load...")
            await query.message.delete()
            dl_type = 'video'
            if fmt_type == 'aud':
                dl_type='audio'
            elif fmt_type == 'img':
                dl_type='images'
            elif fmt_type == 'sub':
                dl_type='subtitles'
            ckey = get_canonical_key(url)
            cache = load_json_file(CACHE_FILE)
            if ckey in cache:
                await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
                return
            can_dl = await acquire_slot()
            if can_dl:
                try:
                    await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
                finally:
                    await release_slot()
            else:
                pos = download_queue.qsize()+1
                await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, url, dl_type, t), 'kwargs': {}})
                free_mb = get_free_disk_mb()
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Server Busy**\nActive: {active_downloads}/{MAX_CONCURRENT_SHORT}\nFree: {free_mb}MB\nQueue: #{pos}\nWill start auto!", parse_mode="Markdown")
            return
        # end

            url = pending_single_links.pop(payload_key, None)
            if not url:
                await query.answer("Expired", show_alert=True)
                return
            await query.answer("Searching YouTube for Spotify track...")
            await query.message.delete()
            # Use same monetization check already done before - download
            can_dl = await acquire_slot()
            if can_dl:
                try:
                    # Call spotify engine
                    status = await context.bot.send_message(chat_id=chat_id, text=t["fetching"].format("Spotify MP3") + f"\n`{url}`", parse_mode="Markdown")
                    try:
                        file_paths, res, size = download_spotify_engine(url)
                        if file_paths and os.path.exists(file_paths[0]):
                            with open(file_paths[0], 'rb') as f:
                                sent = await context.bot.send_audio(chat_id=chat_id, audio=f, caption=f"🎵 {res} Size {size} - Spotify via YouTube", parse_mode="Markdown")
                            warn = await context.bot.send_message(chat_id=chat_id, text="⏳ Auto-deletes in 9 mins\n🎵 ID3: Title from Spotify, Audio from YouTube")
                            asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent.message_id, warn.message_id], 540))
                            try:
                                vmsg = await context.bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent.audio.file_id, caption=f"spotify_{get_canonical_key(url)}")
                                cache = load_json_file(CACHE_FILE)
                                cache[get_canonical_key(url)] = {"file_id": sent.audio.file_id, "vault_msg_id": vmsg.message_id, "type": "audio", "timestamp": time.time(), "hits": 1, "size": size}
                                save_json_file(CACHE_FILE, cache)
                            except:
                                pass
                            os.remove(file_paths[0])
                            await context.bot.delete_message(chat_id=chat_id, message_id=status.message_id)
                            deduct_download_counter(chat_id, is_batch=False)
                        else:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=status.message_id, text=t["error_generic"])
                    except Exception as e:
                        logger.error(f"Spotify DL: {e}")
                        try:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=status.message_id, text=f"❌ Spotify track not found on YouTube. Try another link! (Mismatch protection)")
                        except:
                            pass
                finally:
                    await release_slot()
            else:
                pos = download_queue.qsize()+1
                await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, url, 'audio', t), 'kwargs': {}})
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Server Busy - Queued #{pos}", parse_mode="Markdown")
            return
        if fmt_type == "vidq":
            # Quality selector second step
            # payload_key contains url key and quality
            # Actually format: fmt_vidq_720_payload
            # Re-parse
            try:
                q_parts = payload_key.split("_",1)
                quality = q_parts[0]
                real_key = q_parts[1] if len(q_parts)>1 else ""
                url = pending_single_links.pop(real_key, None) if real_key else None
                if not url:
                    # Try direct
                    url = pending_single_links.get(payload_key)
                    quality = fmt_type
                # For simplicity, quality is in fmt_type? Let's handle
            except:
                pass
            # Fallback to original handling below
            pass

        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("Expired", show_alert=True)
            return
        await query.answer("Checking vault & server load...")
        await query.message.delete()
        dl_type = 'video'
        if fmt_type == 'aud':
            dl_type='audio'
        elif fmt_type == 'img':
            dl_type='images'
        elif fmt_type == 'sub':
            dl_type='subtitles'
        ckey = get_canonical_key(url)
        cache = load_json_file(CACHE_FILE)
        if ckey in cache:
            await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
            return
        can_dl = await acquire_slot()
        if can_dl:
            try:
                await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
            finally:
                await release_slot()
        else:
            pos = download_queue.qsize()+1
            await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, url, dl_type, t), 'kwargs': {}})
            free_mb = get_free_disk_mb()
            await context.bot.send_message(chat_id=chat_id, text=f"⏳ **Server Busy**\nActive: {active_downloads}/{MAX_CONCURRENT_SHORT}\nFree: {free_mb}MB\nQueue: #{pos}\nWill start auto!", parse_mode="Markdown")
        return
    if data.startswith("adsgram_complete_") or data == "adsgram_resume_batch":
        await query.answer("✅ Sponsor viewed! +1 added (realistic)!", show_alert=True)
        try:
            await query.message.delete()
        except:
            pass
        tokens = load_tokens()
        if str(user_id) in tokens:
            del tokens[str(user_id)]
            save_tokens(tokens)
        if data == "adsgram_resume_batch":
            paused = paused_batches.pop(user_id, None)
            if paused:
                asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
            return
        if data == "adsgram_complete_single":
            token_data = tokens.get(str(user_id), {})
            url = token_data.get("url")
            dl_type = token_data.get("dl_type","video")
            if not url:
                await query.message.reply_text("✅ Refilled +1! Send link again")
                return
            can_dl = await acquire_slot()
            if can_dl:
                try:
                    await cached_download_and_send(context.bot, chat_id, url, dl_type, t)
                finally:
                    await release_slot()
            else:
                await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, url, dl_type, t), 'kwargs': {}})
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Queued #{download_queue.qsize()}", parse_mode="Markdown")
            return
        parts = data.replace("adsgram_complete_","").split("_")
        try:
            msg_start, msg_end = int(parts[0]), int(parts[1])
        except:
            msg_start=msg_end=0
        if msg_start==0:
            await query.message.reply_text("✅ Refilled +1! You can download again (Clause 12 optimum)")
            return
        await query.message.reply_text("✅ Verified! Fetching bundle...")
        fwd_ids=[]
        try:
            for tid in range(msg_start, msg_end+1):
                try:
                    fwd = await context.bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
                    fwd_ids.append(fwd.message_id)
                    await asyncio.sleep(0.2)
                except:
                    continue
            if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end+1):
                try:
                    tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    fwd_ids.append(tut.message_id)
                except:
                    pass
            warn = await context.bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins")
            fwd_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, fwd_ids, 540))
        except Exception as e:
            await query.message.reply_text(f"❌ {e}")
        return
    if data == "stop_batch":
        active_batch_sessions[user_id]=False
        await query.answer("Stopping...", show_alert=True)
        try:
            await query.edit_message_text("🛑 Stopped")
        except:
            pass
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
        await query.message.reply_text("🔄 Forward message from new channel", parse_mode="Markdown")
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
            # Create new token with +1 for test ad demo (not 4!)
            reward = get_reward_amount()
            tokens[user_str] = {
                "user_id": int(user_id),
                "downloads_left": reward,
                "batch_downloads_left": reward * 5,
                "last_reset": time.time(),
                "msg_start": 0,
                "msg_end": 0,
                "clicked_ad": True,
                "verified": True,
                "expires": time.time() + 600
            }
            save_tokens(tokens)
            await query.answer("✅ Test Ad Verified! (Clause 13 Demo) +1 realistic", show_alert=True)
            await query.message.reply_text(
                "✅ **TEST AD VERIFIED! 🎉 (Clause 13 + 12 Demo) - Optimum +1**\n\n"
                "This is what user sees after watching 20s ad:\n"
                "• Ad placement found & verified! ✅\n"
                "• Reward: +1 download refilled (realistic optimum - Clause 12 fix)!\n"
                "• Real flow: Watch 20s ad → Click Check → Get +1 file\n\n"
                "📍 **For Adsgram Reviewer:** This proves ad placement exists and is verifiable via /testad button!\n"
                "🎁 Reward is realistic +1, not excessively high! Stats now shows 1!",
                parse_mode="Markdown"
            )
            return
        token_data = tokens[user_str]
        is_test_ad = token_data.get("msg_start", 0) == 0 and token_data.get("msg_end", 0) == 0
        if not is_test_ad and not token_data.get("verified",False):
            await query.answer("⏰ Finish 20s timer first! Watch ad via Open Link button!", show_alert=True)
            return
        msg_start, msg_end = token_data.get("msg_start",0), token_data.get("msg_end",0)
        # FIX: Don't delete token! Keep it and set to +1 optimum (was deleting and recreating as 4!)
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
            await query.message.reply_text("✅ Verified! Refilled +1 (realistic). Resume?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
        if msg_start==0:
            await query.message.reply_text("✅ Refilled +1! Download again (realistic optimum - Clause 12 fix)")
            return
        await query.message.reply_text("✅ Verified! Fetching bundle...")
        fwd_ids=[]
        try:
            for tid in range(msg_start, msg_end+1):
                try:
                    fwd = await context.bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
                    fwd_ids.append(fwd.message_id)
                    await asyncio.sleep(0.2)
                except Exception as inner_e:
                    logger.error(f"Forward {tid} fail: {inner_e}")
                    continue
            if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end+1):
                try:
                    tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    fwd_ids.append(tut.message_id)
                except Exception as tut_e:
                    logger.error(f"Tutorial forward fail: {tut_e}")
            warn = await context.bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins")
            fwd_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, fwd_ids, 540))
        except Exception as e:
            await query.message.reply_text(f"❌ {e} (Bundle {msg_start}-{msg_end} + Tutorial {TUTORIAL_MESSAGE_ID})")


async def test_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bridge_link = f"{BRIDGE_URL}?user={update.effective_user.id}&start_msg=0&end_msg=0"
    keyboard = [
        [InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s (Ad) +1", url=bridge_link)],
        [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")]
    ]
    await update.message.reply_text(
        "🧪 AD PLACEMENT TEST - FOR ADSGRAM REVIEWER (Clause 13 + 12)\n\n"
        "📍 WHERE AD IS PLACED:\n"
        "1️⃣ User pastes link\n"
        "2️⃣ User downloads 4 FREE\n"
        "3️⃣ On 5th download, LIMIT REACHED wall\n"
        "4️⃣ AD APPEARS HERE: This message with 3 buttons!\n"
        "5️⃣ User clicks Open Link & Watch Timer 20s -> Watches ad\n"
        "6️⃣ User clicks Check & Get Files -> Gets +1 download (realistic)\n\n"
        "Ad Types: Adsgram Rewarded + Adsterra Direct 20s\n"
        "Reward: +1 optimum realistic (Clause 12 fix)\n"
        "Commands: Any download after limit, /testad, batch limit\n\n"
        "TRY AD NOW:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def ad_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 AD PLACEMENT INFO FOR ADSGRAM (Clause 13 + 12)\n\n"
        "Bot: @Michaelbbcvaultbot\n"
        "Bot ID: 8863904451\n"
        "PlatformID: 53875\n"
        "Block: bot-56953\n\n"
        "📍 Exact Ad Placement:\n"
        "• Command: After 4 free downloads, 5th attempt\n"
        "• Message: Limit Reached! Watch 20s ad → +1 download\n"
        "• Buttons: Open Link 20s +1, Join Channel, Check & Get Files +1\n"
        "• Ad Type: Rewarded Interstitial 20s\n"
        "• Reward: +1 download (realistic optimum - fixes Clause 12)\n\n"
        "To test: Use /testad - shows ad placement instantly!\n"
        "Name field: Includes placement description for reviewer",
        parse_mode="Markdown"
    )

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
