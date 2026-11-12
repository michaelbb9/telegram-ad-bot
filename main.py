# -*- coding: utf-8 -*-
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
from flask import Flask, request, jsonify
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
    FILE_LINKS_FILE, FILE_LINK_STATE_FILE, "arcade_backup.json"
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

# NEW: Carousel safety limits
MAX_CAROUSEL_IMAGES = 50
MAX_IMAGE_SIZE_MB = 20

# ============ LANGUAGE DICTIONARY (unchanged - too long to repeat) ============
# [The entire LANGUAGES dictionary remains exactly as you had it]
LANGUAGES = {
    # ... (all your existing language entries remain unchanged)
    "en": {
        "welcome": "🚀 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER!**\n\n🔥 WHAT I CAN DO:\n🎬 VIDEOS HD No Watermark!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMAGES Scrape ALL!\n📝 SUBTITLES Auto!\n📦 BATCH 100+ Links!\n⚡ CACHE 1 Sec!\n💎 VAULT Forever!\n📤 UPLOAD FILES!\n🔗 FILE-TO-LINK: Create shareable links!\n\n👉 PASTE LINK TO START! 👇",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **AWESOME! What format you want? Pick below!**",
        "fetching": "📥 **Fetching your {}... Hang tight! ⏳✨**",
        "error_generic": "❌ Oops! Failed! 😢 Link private/blocked. Try public link!",
        "error_50mb": "❌ Too Big! 😅 This video is over 300MB. Try a shorter one!", 
        "error_no_img": "❌ No images found! 😢 Try another link!",
        "images_received": "⏳ **{} Images received.**",
        "select_lang": "🌍 Select your language! Choose below! 👇", 
        "lang_set": "✅ Language set! Enjoy! 🎉✨",
        "batch_detected": "📦 **Batch Detected ({} links)**\nWhat format?",
        "batch_dest": "📦 **Where to send?**",
        "btn_chat": "📥 In Chat", "btn_chan": "📢 To Channel",
        "limit_reached": "⚠️ **Limit Reached!** You used 4 FREE! Watch 20s ad → Get +1 download!",
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
        "user_upload_prompt": "📤 **Upload File**\nSend video/image/file to Admin. Limit 5/24h.",
        "upload_success_user": "✅ Sent to Admin!",
        "upload_limit_reached": "⚠️ Upload limit 5/24h reached.",
        "no_uploads": "📭 No uploads yet.",
        "stats_msg": "📊 **Your Stats:**\n• Downloads Left: {}\n• Batch Left: {}",
        "change_channel_prompt": "🔄 **Change Batch Channel**\n1. Make sure I am an admin in the new channel.\n2. Forward any message from that channel here.",
        "disk_config_prompt": "💾 **Disk Config**\nCurrent min free disk: **{}MB**\nTo change: `/setdisk <value>`",
        "mtproto_config_prompt": "⚡ **MTProto Config**\nCurrent max upload: **{}MB**\nTo change: `/setmtproto <value>`",
        "free_panel_prompt": "📦 FREE DOWNLOADS\nCurrent free per day: {}",
        "reward_panel_prompt": "🎁 REWARD PANEL\nCurrent: +{} download per 20s ad",
        "ad_panel_prompt": "⚙️ Ad Panel\nCurrent: {}",
        "password_saved": "🔐 Password saved.",
        "password_too_long": "Password must be 64 chars or fewer.",
        "file_to_link_prompt": "🔗 **File-to-Link**\nSend the file(s) you want to share.",
        "link_invalid_expired": "❌ This link is invalid or expired.",
        "link_limit_reached": "⛔ This link reached its usage limit.",
        "link_password_protected": "🔐 This link is password protected. Send the password.",
        "files_sent": "✅ Your files have been sent.",
        "file_added": "📥 Added file #{}. Send more, or tap Create Link.",
        "fl_cancelled": "File-to-Link cancelled",
        "fl_start_again": "Start File-to-Link again with /filetolink",
        "fl_choose_expiry": "Choose link expiry:",
        "fl_expiry_updated": "Expiry updated",
        "fl_choose_max_uses": "Choose max successful deliveries:",
        "fl_uses_updated": "Usage limit updated",
        "fl_set_password": "Send a password, or /clearpassword to remove.",
        "fl_link_created": "Link created",
        "fl_link_ready": "🔗 Your link is ready:\n{}\nFiles: {}\nCost: 1 free daily download",
        "fl_daily_limit": "Daily free limit reached. Watch an ad to earn more.",
        "fl_ad_busy": "⚠️ Ad server busy.",
        "admin_skipped": "✅ Skipped!",
        "admin_bypassed": "✅ Bypassed",
        "free_set": "✅ Free set to {}!",
        "free_updated": "✅ Free Downloads updated to {}!",
        "reward_set": "✅ Reward set to +{}!",
        "reward_updated": "✅ Reward updated to +{}!",
        "mode_updated": "✅ Mode: {}",
        "support_opened": "✍️ Send message/photo/video/file below.",
        "admin_reply_mode": "✍️ Reply to {}:",
        "user_reply_mode": "✍️ Type follow-up below",
        "support_closed": "🔒 Closed",
        "drop_cancelled": "❌ Cancelled",
        "drop_no_items": "⚠️ No items!",
        "drop_timer_set": "{} set!",
        "drop_broadcasting": "🚀 Broadcasting {} items to {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nAuto-deletes in {}\nTap to claim:",
        "drop_done": "✅ Broadcast done to {}",
        "age_expired": "⏳ Expired!",
        "age_claimed": "❌ Already claimed!",
        "age_verified": "Verified!",
        "age_denied": "❌ Denied. Must be 18+",
        "lang_updated": "Updated!",
        "batch_expired": "Expired",
        "batch_loading": "Loading...",
        "batch_no_channel": "No channel linked!",
        "batch_setup_prompt": "📦 Setup: Make bot admin in channel and forward a message here",
        "batch_mode_activated": "Mode activated!",
        "batch_change_dest": "🔄 **Change Destination Channel**\nMake bot admin in new channel, then forward a message here.",
        "join_channel_first_alert": "Join channel first! 📢 Must join!",
        "join_channel_first": "Join channel first! 📢",
        "watch_timer_first": "⏰ Open the link and watch the 20s timer first!",
        "test_ad_verified": "✅ Test Ad Verified! +1",
        "test_ad_verified_msg": "✅ **TEST AD VERIFIED!**\nReward: +1 download refilled!",
        "finish_timer_first": "⏰ Finish 20s timer first!",
        "verified_added": "Verified! +1 added",
        "resume_prompt": "✅ Verified! Refilled +1. Resume?",
        "refilled_download": "✅ Refilled +1! Download again.",
        "fetching_bundle": "✅ Verified! Fetching bundle...",
        "outdated_button": "This button is outdated. Send your link again.",
        "stopping": "Stopping...",
        "stopped": "🛑 Stopped",
        "resuming": "Resuming...",
        "checking_vault": "Checking vault & server load...",
        "server_busy": "⏳ **Server Busy**\nActive: {}/{}\nFree: {}MB\nQueue: #{}\nWill start auto!",
        "simulated": "🛠 Simulated! Now tap Check & Get +1",
        "server_unreachable": "❌ Server unreachable",
        "monetag_failed_twice": "Complete two failed Monetag attempts first.",
        "monetag_fallback_prompt": "🌐 Monetag failed twice. Continue with Adsterra:",
        "adsterra_ready": "Adsterra fallback ready",
        "finish_monetag": "📺 Finish the Monetag ad in Mini App, then check again.",
        "monetag_failed_use_adsterra": "Monetag failed twice. Use Adsterra fallback below.",
        "ad_link_expired": "Ad link expired. Send your link again.",
        "ad_verified_added": "✅ Ad verified! +{} added",
        "test_ad_completed": "✅ TEST AD VERIFIED\nReward credited: +{} download.",
        "sponsor_viewed": "✅ Sponsor viewed! +{} added",
        "refilled_send_again": "✅ Refilled +{}! Send your link again.",
        "queued": "⏳ Queued #{}",
        "banned": "🚫 You are banned.",
        "no_links": "❌ No links found.",
        "batch_count": "📦 Batch {} links",
        "restore_invalid_json": "❌ Restore failed: **{}** is not valid JSON.",
        "restore_failed": "❌ Restore failed: {}",
        "restore_success": "✅ **Restore Successful!**\nFile: **{}**\nRestored **{}** entries.",
        "admin_edit_welcome_prompt": "✏️ Send the new Welcome Message. Use `{bot_name}` for bot username.",
        "admin_welcome_updated": "✅ Welcome message updated!",
        "menu_edit_welcome": "✏️ Edit Welcome Msg",
        "cached_instant_video": "⚡ Cached Instant [{}] {} {}",
        "cached_instant_audio": "⚡ **Cached Instant** `{}`",
        "cached_instant_image": "⚡ **Cached Instant** `{}`",
        "auto_delete_9m": "⏳ Auto-deletes in 9 mins",
        "download_success": "✅ Download successful!"
    },
    # ... (keep all other language entries exactly as they are in your original code)
}

# Copy all other languages from your original code here
# (hi, es, ar, ru, pt, id, fr, tr, de entries - unchanged)

web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot alive! V25 Cloud Sync", 200

@web_app.route('/api/receive-arcade-backup', methods=['POST'])
def receive_arcade_backup():
    data = request.get_json()
    if data.get('secret') != API_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    
    progress = data.get('progress')
    if progress:
        try:
            with open("arcade_backup.json", "w") as f:
                json.dump(progress, f)
            return jsonify({"ok": True}), 200
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": False, "error": "No data"}), 400

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

# ============ NEW: IMPROVED IMAGE EXTRACTION ENGINE ============

def extract_carousel_images_ytdlp(url, cookiefile=None):
    """
    Extract all images from a post using yt-dlp.
    Returns list of image URLs.
    """
    image_urls = []
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
        }
        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile
        if PROXY_URL:
            ydl_opts['proxy'] = PROXY_URL
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []
            
            # Handle playlists/entries (carousel posts often appear as entries)
            entries = info.get('entries', [])
            if entries:
                for entry in entries:
                    if not entry:
                        continue
                    # Check for thumbnails or image URL
                    thumbnails = entry.get('thumbnails', [])
                    for thumb in thumbnails:
                        thumb_url = thumb.get('url')
                        if thumb_url and _is_image_url(thumb_url):
                            image_urls.append(thumb_url)
                    
                    # Some extractors put image URL directly
                    entry_url = entry.get('url', '')
                    if entry_url and _is_image_url(entry_url) and entry_url not in image_urls:
                        image_urls.append(entry_url)
                    
                    # Check for formats that are images
                    formats = entry.get('formats', [])
                    for fmt in formats:
                        fmt_url = fmt.get('url', '')
                        ext = fmt.get('ext', '')
                        if fmt_url and ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                            if fmt_url not in image_urls:
                                image_urls.append(fmt_url)
            else:
                # Single entry - check thumbnails
                thumbnails = info.get('thumbnails', [])
                # Sort by resolution, prefer highest
                sorted_thumbs = sorted(
                    [t for t in thumbnails if t.get('url')],
                    key=lambda x: (x.get('width', 0) or 0) * (x.get('height', 0) or 0),
                    reverse=True
                )
                for thumb in sorted_thumbs:
                    thumb_url = thumb.get('url')
                    if thumb_url and _is_image_url(thumb_url):
                        image_urls.append(thumb_url)
                
                # Check formats for image extensions
                formats = info.get('formats', [])
                for fmt in formats:
                    fmt_url = fmt.get('url', '')
                    ext = fmt.get('ext', '')
                    if fmt_url and ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                        if fmt_url not in image_urls:
                            image_urls.append(fmt_url)
                
                # Direct URL check
                direct_url = info.get('url', '')
                if direct_url and _is_image_url(direct_url) and direct_url not in image_urls:
                    image_urls.append(direct_url)
    except Exception as e:
        logger.debug(f"yt-dlp image extraction failed: {e}")
    
    return image_urls

def extract_carousel_images_gallerydl(url):
    """
    Try to extract images using gallery-dl if available.
    """
    image_urls = []
    try:
        import subprocess
        result = subprocess.run(
            ['gallery-dl', '--dump-json', url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split('\n'):
                try:
                    data = json.loads(line)
                    # gallery-dl output format varies
                    if isinstance(data, list) and len(data) >= 3:
                        # Usually [type, url, metadata]
                        if data[0] == 3 and isinstance(data[1], str):  # Image type
                            img_url = data[1]
                            if _is_image_url(img_url) and img_url not in image_urls:
                                image_urls.append(img_url)
                    elif isinstance(data, dict):
                        img_url = data.get('url', '')
                        if img_url and _is_image_url(img_url) and img_url not in image_urls:
                            image_urls.append(img_url)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        logger.debug("gallery-dl not installed, skipping")
    except Exception as e:
        logger.debug(f"gallery-dl extraction failed: {e}")
    
    return image_urls

def extract_carousel_images_html(url, cookiefile=None):
    """
    HTML fallback: scrape all potential image URLs from page source.
    """
    image_urls = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    cookies = None
    if cookiefile and os.path.exists(cookiefile):
        cookies = _parse_netscape_cookies(cookiefile)
    
    try:
        res = requests.get(url, headers=headers, cookies=cookies, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. Open Graph images (usually the main one)
        for og in soup.find_all('meta', property='og:image'):
            content = og.get('content')
            if content and _is_image_url(content) and content not in image_urls:
                image_urls.append(content)
        
        # 2. Twitter card images
        for tw in soup.find_all('meta', attrs={'name': 'twitter:image'}):
            content = tw.get('content')
            if content and _is_image_url(content) and content not in image_urls:
                image_urls.append(content)
        
        # 3. JSON-LD structured data (often contains image arrays)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                _extract_images_from_jsonld(data, image_urls)
            except:
                pass
        
        # 4. Look for image URLs in inline scripts (Instagram, Twitter, etc.)
        script_text = res.text
        # Match common CDN image URL patterns
        cdn_patterns = [
            r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*',
            r'https?://[^\s"\'<>]*cdninstagram[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*',
            r'https?://[^\s"\'<>]*twimg[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*',
            r'https?://[^\s"\'<>]*fbcdn[^\s"\'<>]*\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*',
        ]
        for pattern in cdn_patterns:
            matches = re.findall(pattern, script_text)
            for match in matches:
                if match not in image_urls and _is_image_url(match):
                    image_urls.append(match)
        
        # 5. <img> tags with src
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            if src and _is_image_url(src) and src not in image_urls:
                # Skip tiny images (icons, tracking pixels)
                width = img.get('width', '')
                height = img.get('height', '')
                try:
                    if int(width) < 100 or int(height) < 100:
                        continue
                except:
                    pass
                image_urls.append(src)
        
        # 6. data-src (lazy loading)
        for img in soup.find_all('img', attrs={'data-src': True}):
            src = img.get('data-src', '')
            if src and _is_image_url(src) and src not in image_urls:
                image_urls.append(src)
        
    except Exception as e:
        logger.error(f"HTML image extraction failed: {e}")
    
    return image_urls

def _extract_images_from_jsonld(data, image_urls):
    """Recursively extract image URLs from JSON-LD structured data."""
    if isinstance(data, dict):
        # Check for image field
        img = data.get('image')
        if isinstance(img, str) and _is_image_url(img) and img not in image_urls:
            image_urls.append(img)
        elif isinstance(img, list):
            for i in img:
                if isinstance(i, str) and _is_image_url(i) and i not in image_urls:
                    image_urls.append(i)
                elif isinstance(i, dict):
                    url = i.get('url', '')
                    if url and _is_image_url(url) and url not in image_urls:
                        image_urls.append(url)
        # Recurse into nested objects
        for v in data.values():
            _extract_images_from_jsonld(v, image_urls)
    elif isinstance(data, list):
        for item in data:
            _extract_images_from_jsonld(item, image_urls)

def _is_image_url(url):
    """Check if a URL looks like an image (by extension or CDN pattern)."""
    if not url or not url.startswith('http'):
        return False
    url_lower = url.lower().split('?')[0]  # Remove query params
    # Direct extension check
    if url_lower.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
        return True
    # CDN patterns that serve images without extension
    cdn_hints = ['cdninstagram', 'twimg', 'fbcdn', 'pbs.twimg', 'instagram.f']
    if any(hint in url_lower for hint in cdn_hints):
        # Exclude video URLs
        if '.mp4' not in url_lower and 'video' not in url_lower:
            return True
    return False

def _parse_netscape_cookies(cookiefile):
    """Parse Netscape cookie file into requests-compatible dict."""
    cookies = {}
    try:
        with open(cookiefile, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    domain, flag, path, secure, expires, name, value = parts[:7]
                    cookies[name] = value
    except Exception as e:
        logger.error(f"Cookie parse failed: {e}")
    return cookies

def extract_all_carousel_images(url, cookiefile=None):
    """
    Main extraction pipeline: yt-dlp → gallery-dl → HTML fallback.
    Returns deduplicated list of image URLs.
    """
    all_urls = []
    seen_hashes = set()  # Use URL hash to dedupe (handles param variations)
    
    def add_urls(urls, source):
        added = 0
        for u in urls:
            # Normalize URL for dedup (strip query for comparison)
            normalized = u.split('?')[0].split('#')[0]
            url_hash = hashlib.md5(normalized.encode()).hexdigest()
            if url_hash not in seen_hashes:
                seen_hashes.add(url_hash)
                all_urls.append(u)
                added += 1
        if added:
            logger.info(f"Image extraction: {source} added {added} unique URLs")
        return added
    
    # Method 1: yt-dlp
    ytdlp_urls = extract_carousel_images_ytdlp(url, cookiefile)
    add_urls(ytdlp_urls, "yt-dlp")
    
    # Method 2: gallery-dl (if yt-dlp got nothing or few)
    if len(all_urls) < 2:
        gdl_urls = extract_carousel_images_gallerydl(url)
        add_urls(gdl_urls, "gallery-dl")
    
    # Method 3: HTML fallback (always run to catch anything missed)
    html_urls = extract_carousel_images_html(url, cookiefile)
    add_urls(html_urls, "HTML")
    
    # Filter out obvious non-content (tiny previews)
    filtered = []
    for u in all_urls:
        # Skip known thumbnail/preview patterns
        u_lower = u.lower()
        if any(skip in u_lower for skip in ['/s150x150/', '/s48x48/', 'profile_pic', '/avatar', 'emoji']):
            continue
        filtered.append(u)
    
    # Cap at max
    if len(filtered) > MAX_CAROUSEL_IMAGES:
        logger.info(f"Carousel has {len(filtered)} images, capping at {MAX_CAROUSEL_IMAGES}")
        filtered = filtered[:MAX_CAROUSEL_IMAGES]
    
    logger.info(f"Total unique carousel images extracted: {len(filtered)}")
    return filtered

# ============ END IMAGE EXTRACTION ENGINE ============

async def get_canonical_key(url: str, chat_id=None, bot=None):
    original_url = url
    async def send_debug(text):
        if chat_id and bot:
            try: await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except: pass

    await send_debug(f"🔍 <b>Processing Link:</b>\n<code>{url}</code>")
    short_link_domains = ["vt.tiktok.com", "vm.tiktok.com", "youtu.be/", "t.co/", "instagr.am/", "fb.watch/"]
    is_short_link = any(domain in url.lower() for domain in short_link_domains)

    if is_short_link:
        await send_debug("🔄 Resolving short link...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
            resolved_url = response.url
            if resolved_url != original_url:
                url = resolved_url
                await send_debug(f"✅ Resolved to:\n<code>{url}</code>")
        except Exception as e:
            await send_debug(f"❌ Redirect failed: {str(e)[:100]}")

    tiktok_match = re.search(r'/video/(\d{15,20})', url)
    if tiktok_match:
        vid_id = tiktok_match.group(1)
        await send_debug(f"🎯 <b>TikTok Regex Match!</b>\nVideo ID: <code>{vid_id}</code>")
        return f"tiktok_{vid_id}"

    await send_debug("🤖 Trying yt-dlp extraction...")
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                if 'entries' in info and info['entries']: info = info['entries'][0]
                extractor = info.get('extractor', 'generic').replace(':', '').replace(' ', '')
                vid_id = info.get('id', '')
                if vid_id:
                    await send_debug(f"✅ yt-dlp found ID: <code>{vid_id}</code>")
                    return f"{extractor}_{vid_id}"
    except Exception as e:
        await send_debug(f"⚠️ yt-dlp failed: {str(e)[:50]}")

    await send_debug("🎲 Using URL hash fallback.")
    clean = url.split('?')[0].split('&')[0].lower().strip('/').replace('https://','').replace('http://','')
    h = hashlib.md5(clean.encode()).hexdigest()[:12]
    return f"url_{h}"

async def restore_arcade_backup(bot):
    try:
        logger.info("Attempting to restore arcade_backup.json from Telegram channel...")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                for update in reversed(data.get("result", [])):
                    if "channel_post" in update and update["channel_post"].get("document"):
                        doc = update["channel_post"]["document"]
                        if doc.get("file_name") == "arcade_backup.json":
                            file_id = doc["file_id"]
                            file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                            r_file = requests.get(file_url, timeout=10)
                            if r_file.status_code == 200:
                                file_path = r_file.json()["result"]["file_path"]
                                download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                                r_download = requests.get(download_url, timeout=10)
                                if r_download.status_code == 200:
                                    with open("arcade_backup.json", "wb") as f:
                                        f.write(r_download.content)
                                    logger.info("Successfully restored arcade_backup.json from Telegram.")
                                    return
        logger.info("No arcade_backup.json found in recent updates.")
    except Exception as e:
        logger.error(f"Error restoring arcade backup: {e}")

async def backup_to_channel(bot):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M")
        free_mb = shutil.disk_usage(".").free // (1024*1024)
        
        try:
            logger.info("Fetching arcade backup from PythonAnywhere...")
            r = requests.get(f"{WEB_BASE_URL}/api/arcade/get-backup", headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    with open("arcade_backup.json", "w") as f:
                        json.dump(data["progress"], f)
                    logger.info("Successfully fetched arcade_backup.json from PythonAnywhere")
            else:
                logger.error(f"Failed to fetch arcade backup: HTTP {r.status_code}")
        except Exception as e:
            logger.error(f"Error fetching arcade backup: {e}")

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
            if not os.path.exists("downloads"): continue
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
                except: pass
            if deleted: logger.info(f"Cleaner deleted {deleted}")
        except Exception as e: logger.error(f"Cleaner: {e}")

def clean_downloads_startup():
    try:
        if os.path.exists("downloads"):
            for fname in os.listdir("downloads"):
                try: os.remove(os.path.join("downloads", fname))
                except: pass
    except: pass

def is_flood(user_id):
    if user_id == ADMIN_ID: return False, 0
    flood_data = load_json_file(FLOOD_FILE)
    now = time.time()
    uid = str(user_id)
    if uid not in flood_data: flood_data[uid] = []
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
    if user_str not in activity: activity[user_str] = {"total_interactions": 0, "last_active": now}
    activity[user_str]["total_interactions"] += 1
    activity[user_str]["last_active"] = now
    save_json_file(ACTIVITY_FILE, activity)

def get_lang(user_id):
    langs = load_json_file(LANG_FILE)
    return langs.get(str(user_id), "en")

def get_global_ab_network(user_id):
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode", "auto")
    if mode in ("monetag", "adsgram"): return "monetag"
    elif mode == "adsterra": return "adsterra"
    day_epoch = int(time.time() // 86400)
    return "monetag" if (int(user_id) + day_epoch) % 2 == 0 else "adsterra"

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", headers=API_HEADERS, timeout=5)
        if response.status_code == 200: return response.json()
    except Exception as e: logger.error(f"Tokens: {e}")
    return {}

def save_tokens(tokens):
    try: requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, headers=API_HEADERS, timeout=5)
    except Exception as e: logger.error(f"Save tokens: {e}")

def adsgram_start(user_id, kind="wall", msg_start=0, msg_end=0):
    try:
        r = requests.post(f"{WEB_BASE_URL}/monetag-start", json={"user_id": int(user_id), "kind": kind, "msg_start": int(msg_start), "msg_end": int(msg_end), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200: return r.json().get("nonce")
        logger.error(f"adsgram_start HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e: logger.error(f"adsgram_start: {e}")
    return None

def adsgram_status(user_id):
    try:
        r = requests.post(f"{WEB_BASE_URL}/monetag-status", json={"user_id": int(user_id), "secret": API_SECRET}, timeout=8)
        if r.status_code == 200: return r.json()
    except Exception as e: logger.error(f"adsgram_status: {e}")
    return {"status": "error"}

def adsgram_keyboard(user_id, kind="wall", msg_start=0, msg_end=0, extra_rows=None):
    nonce = adsgram_start(user_id, kind, msg_start, msg_end)
    if not nonce: return None
    url = f"{WEB_BASE_URL}/monetag?n={nonce}&k={kind}"
    rows = [
        [InlineKeyboardButton("📺 Watch Monetag Ad +1", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("✅ Check & Get +1", callback_data="monetag_check")],
        [InlineKeyboardButton("↪️ Use Adsterra fallback (after 2 failures)", callback_data="monetag_fallback")],
    ]
    if extra_rows: rows.extend(extra_rows)
    return InlineKeyboardMarkup(rows)

async def report_vault_delivery(user_id, msg_start, msg_end, delivered_message_ids):
    if not delivered_message_ids: return
    try:
        response = requests.post(f"{WEB_BASE_URL}/api/item-delivered", json={"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "delivered_message_ids": [int(x) for x in delivered_message_ids], "event_id": uuid.uuid4().hex}, headers=API_HEADERS, timeout=8)
        if response.status_code != 200: logger.warning("Vault analytics rejected delivery: %s %s", response.status_code, response.text[:200])
    except Exception as e: logger.warning("Vault analytics report failed: %s", e)

async def deliver_bundle(bot, user_id, msg_start, msg_end):
    fwd_ids = []
    for tid in range(msg_start, msg_end + 1):
        try:
            fwd = await bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
            fwd_ids.append(fwd.message_id)
            await asyncio.sleep(0.2)
        except Exception as e: logger.error(f"Forward {tid} fail: {e}")
    await report_vault_delivery(user_id, msg_start, msg_end, fwd_ids)
    if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end + 1):
        try:
            tut = await bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
            fwd_ids.append(tut.message_id)
        except Exception: pass
    kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
    warn = await bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins", reply_markup=kb)
    fwd_ids.append(warn.message_id)
    asyncio.create_task(schedule_deletion(bot, user_id, fwd_ids, 540))

def load_user_channels(): return load_json_file(CHANNELS_FILE)
def save_user_channels(c): save_json_file(CHANNELS_FILE, c)
def load_linking_states(): return load_json_file(LINKING_STATE_FILE)
def save_linking_states(s): save_json_file(LINKING_STATE_FILE, s)

async def schedule_deletion(bot, chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try: await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except: pass

def fetch_url_metadata(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info and info['entries']: info = info['entries'][0]
            title = info.get('title', 'Unknown')[:60]
            duration = info.get('duration', 0)
            mins, secs = divmod(duration, 60)
            dur = f"{mins}m {secs}s" if mins else f"{secs}s"
            return title, dur
    except: return "Media Link", "N/A"

def get_min_free_disk_mb():
    config = load_json_file(CONFIG_FILE)
    return config.get("min_free_disk_mb", MIN_FREE_DISK_MB)

def get_mtproto_max_mb():
    config = load_json_file(CONFIG_FILE)
    return config.get("mtproto_max_mb", MTPROTO_MAX_MB)

# ============ MODIFIED: download_media_engine with carousel support ============

def download_media_engine(url: str, download_type: str, max_mb=None):
    cap_mb = int(max_mb or get_mtproto_max_mb())
    cap_bytes = cap_mb * 1024 * 1024
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0'}
    cookiefile = None
    if "tiktok.com" in url.lower() and os.path.exists("tiktok_cookies.txt"): cookiefile = "tiktok_cookies.txt"
    elif os.path.exists("cookies.txt"): cookiefile = "cookies.txt"
    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if cookiefile: ydl_opts['cookiefile'] = cookiefile
    
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
                return [path], "audio", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("FILE_NOT_FOUND")
    
    elif download_type == 'images':
        # === NEW: Download ALL carousel images ===
        logger.info(f"Carousel image extraction starting for: {url}")
        
        # Step 1: Extract all image URLs
        image_urls = extract_all_carousel_images(url, cookiefile)
        
        if not image_urls:
            # Fallback to single OG image if nothing found
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')
                og = soup.find('meta', property='og:image')
                if og and og.get('content'):
                    image_urls = [og['content']]
            except:
                pass
        
        if not image_urls:
            raise ValueError("NO_IMAGES")
        
        logger.info(f"Downloading {len(image_urls)} images...")
        
        # Step 2: Download each image with validation
        downloaded_paths = []
        total_size = 0
        errors = 0
        
        # Parse cookies for authenticated requests
        cookies = None
        if cookiefile and os.path.exists(cookiefile):
            cookies = _parse_netscape_cookies(cookiefile)
        
        # Determine common extension for this carousel (for unique filenames)
        base_ts = int(time.time())
        
        for idx, img_url in enumerate(image_urls):
            if len(downloaded_paths) >= MAX_CAROUSEL_IMAGES:
                break
            try:
                # Check size before download using HEAD
                head_resp = requests.head(img_url, headers=http_headers, cookies=cookies, timeout=10, allow_redirects=True)
                content_length = int(head_resp.headers.get('content-length', 0))
                if content_length > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                    logger.warning(f"Skipping oversized image ({content_length // (1024*1024)}MB): {img_url[:80]}")
                    continue
                
                # Download with timeout
                img_resp = requests.get(img_url, headers=http_headers, cookies=cookies, timeout=20, allow_redirects=True)
                img_resp.raise_for_status()
                
                content_type = img_resp.headers.get('content-type', '').lower()
                data = img_resp.content
                
                # Validate: must be image content and non-trivial size
                if len(data) < 1000:
                    logger.warning(f"Skipping tiny image ({len(data)} bytes)")
                    continue
                
                # Determine extension from content-type or URL
                ext = _image_extension(content_type, img_url)
                if not ext:
                    logger.warning(f"Unknown content-type {content_type}, skipping")
                    continue
                
                # Check if adding this would exceed total cap
                if total_size + len(data) > cap_bytes:
                    logger.warning(f"Total size cap reached, stopping at {len(downloaded_paths)} images")
                    break
                
                # Unique filename per image
                filename = f"img_{base_ts}_{idx:03d}.{ext}"
                path = os.path.join(output_dir, filename)
                with open(path, 'wb') as f:
                    f.write(data)
                
                # Verify file is valid
                if os.path.getsize(path) < 1000:
                    os.remove(path)
                    continue
                
                downloaded_paths.append(path)
                total_size += len(data)
                await_sleep_ms = 50  # Small delay between downloads to be polite
                time.sleep(await_sleep_ms / 1000)
                
            except Exception as e:
                errors += 1
                logger.debug(f"Image {idx+1}/{len(image_urls)} failed: {e}")
                continue
        
        if not downloaded_paths:
            raise ValueError("NO_IMAGES")
        
        total_size_str = f"{total_size/(1024*1024):.1f}MB"
        logger.info(f"Downloaded {len(downloaded_paths)} images ({total_size_str}), {errors} skipped")
        
        return downloaded_paths, "original", total_size_str
    
    else:  # video
        tiers = [
            ("1080p", "bv*[height<=1080]+ba/b[height<=1080]"),
            ("720p", "bv*[height<=720]+ba/b[height<=720]"),
            ("480p", "bv*[height<=480]+ba/b[height<=480]"),
            ("360p", "bv*[height<=360]+ba/b[height<=360]"),
            ("worst", "worst")
        ]
        too_big = False
        last_err = None
        best_quality = "unknown"
        
        for qual_name, fmt in tiers:
            try:
                opts = dict(ydl_opts)
                opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, f'%(id)s_{qual_name}.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path, 'max_filesize': cap_bytes})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"): path = os.path.splitext(path)[0]+".mp4"
                    if os.path.exists(path):
                        if os.path.getsize(path) > cap_bytes:
                            os.remove(path)
                            too_big = True
                            continue
                        actual_height = info.get('height', 0)
                        if actual_height >= 1080: best_quality = "1080p"
                        elif actual_height >= 720: best_quality = "720p"
                        elif actual_height >= 480: best_quality = "480p"
                        elif actual_height >= 360: best_quality = "360p"
                        else: best_quality = "worst"
                        return [path], best_quality, f"{os.path.getsize(path)/(1024*1024):.1f}MB"
                    too_big = True
            except Exception as e:
                if "Unsupported URL" in str(e) or "403" in str(e): raise e
                last_err = e
                continue
        if too_big or last_err is None: raise ValueError("FILE_TOO_LARGE")
        raise last_err

def _image_extension(content_type, url):
    """Determine image extension from content-type or URL."""
    if 'jpeg' in content_type or 'jpg' in content_type:
        return 'jpg'
    if 'png' in content_type:
        return 'png'
    if 'webp' in content_type:
        return 'webp'
    if 'gif' in content_type:
        return 'gif'
    # Fallback to URL extension
    url_lower = url.lower().split('?')[0]
    for ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
        if url_lower.endswith(f'.{ext}'):
            return 'jpg' if ext == 'jpeg' else ext
    return None

# ============ END download_media_engine changes ============

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
        keyboard.append([KeyboardButton(t["menu_edit_welcome"])])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_downloads_usage_mb():
    try:
        if not os.path.exists("downloads"): return 0
        total = 0
        for fname in os.listdir("downloads"):
            fpath = os.path.join("downloads", fname)
            if os.path.isfile(fpath): total += os.path.getsize(fpath)
        return total // (1024*1024)
    except: return 0

def get_reward_amount():
    try: return int(load_json_file(CONFIG_FILE).get("reward_amount", 1))
    except: return 1
def set_reward_amount(val):
    cfg = load_json_file(CONFIG_FILE); cfg["reward_amount"] = int(val); save_json_file(CONFIG_FILE, cfg)
def get_free_amount():
    try: return int(load_json_file(CONFIG_FILE).get("free_amount", 4))
    except: return 4
def set_free_amount(val):
    cfg = load_json_file(CONFIG_FILE); cfg["free_amount"] = int(val); save_json_file(CONFIG_FILE, cfg)
def get_free_disk_mb():
    try: return max(0, 512 - get_downloads_usage_mb())
    except: return 512

def deduct_download_counter(user_id, is_batch=False):
    try: requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": is_batch}, headers=API_HEADERS, timeout=3)
    except: pass

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
    async with download_lock: active_downloads = max(0, active_downloads - 1)

async def queue_processor(bot):
    global active_downloads
    while True:
        try:
            job = await download_queue.get()
            while True:
                free_mb = shutil.disk_usage(".").free // (1024*1024)
                min_free = get_min_free_disk_mb()
                async with download_lock: can_run = active_downloads < MAX_CONCURRENT_SHORT and free_mb > min_free
                if can_run: break
                await asyncio.sleep(2)
            async with download_lock: active_downloads += 1
            try: await job['func'](*job['args'], **job['kwargs'])
            except Exception as e: logger.error(f"Queue job: {e}")
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
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang_hi")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"), InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"), InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇮🇩 Indonesia", callback_data="lang_id"), InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")]
    ]
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
    if not update.effective_message or not update.effective_user: return False
    uid = str(update.effective_user.id)
    states = load_json_file(FILE_LINK_STATE_FILE)
    state = states.get(uid)
    if not state or state.get("mode") != "collecting": return False
    try:
        copied = await context.bot.copy_message(chat_id=FILE_LINK_STORAGE_ID, from_chat_id=update.effective_message.chat_id, message_id=update.effective_message.message_id)
        state.setdefault("items", []).append({"message_id": copied.message_id})
        states[uid] = state
        save_json_file(FILE_LINK_STATE_FILE, states)
        t = LANGUAGES.get(get_lang(uid), LANGUAGES["en"])
        await update.effective_message.reply_text(t["file_added"].format(len(state['items'])), reply_markup=file_link_keyboard(state))
    except Exception as exc: logger.exception("File-to-Link storage copy failed")
    return True

async def file_to_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.effective_message.reply_text(t["banned"]); return
    states = load_json_file(FILE_LINK_STATE_FILE)
    state = {"mode": "collecting", "items": [], "created_at": time.time(), "settings": {"expiry": "never", "max_clicks": 0, "password": ""}}
    states[str(user_id)] = state
    save_json_file(FILE_LINK_STATE_FILE, states)
    await update.effective_message.reply_text(t["file_to_link_prompt"], reply_markup=file_link_keyboard(state), parse_mode="Markdown")

async def file_link_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    t = LANGUAGES.get(get_lang(update.effective_user.id), LANGUAGES["en"])
    links = load_json_file(FILE_LINKS_FILE)
    record = links.get(token)
    if not record or (record.get("expires_at") and time.time() > record["expires_at"]): await update.effective_message.reply_text(t["link_invalid_expired"]); return
    if record.get("max_clicks", 0) and record.get("clicks", 0) >= record["max_clicks"]: await update.effective_message.reply_text(t["link_limit_reached"]); return
    if record.get("password"):
        states = load_json_file(FILE_LINK_STATE_FILE)
        states[str(update.effective_user.id)] = {"mode": "file_link_password", "token": token}
        save_json_file(FILE_LINK_STATE_FILE, states)
        await update.effective_message.reply_text(t["link_password_protected"])
        return
    await send_file_link_payload(update, context, token, record)

async def send_file_link_payload(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str, record: dict) -> None:
    user_id = update.effective_user.id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    try:
        member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
        if member.status not in ("member", "administrator", "creator"): raise ValueError("not joined")
    except Exception: await update.effective_message.reply_text("📢 Join our required channel first: " + PUBLIC_CHANNEL_URL); return
    for item in record.get("items", []): await context.bot.copy_message(chat_id=user_id, from_chat_id=FILE_LINK_STORAGE_ID, message_id=item["message_id"])
    record["clicks"] = record.get("clicks", 0) + 1
    links = load_json_file(FILE_LINKS_FILE); links[token] = record; save_json_file(FILE_LINKS_FILE, links)
    await update.effective_message.reply_text(t["files_sent"])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.message.reply_text(t["banned"]); return
    track_user_activity(user_id)
    args = context.args
    lang = get_lang(user_id)
    
    if not args:
        config = load_json_file(CONFIG_FILE)
        welcome_msg = config.get("welcome_message", t["welcome"])
        try:
            bot_user = context.bot.username
            welcome_msg = welcome_msg.replace("{bot_name}", f"@{bot_user}")
        except: pass
        await update.message.reply_text(welcome_msg, reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID), parse_mode="Markdown")
        return
        
    arg_code = args[0]
    if arg_code.startswith("fl_"): await file_link_deep_link(update, context, arg_code[3:]); return
    if arg_code.startswith("drip_"):
        drop_id = arg_code.replace("drip_", "")
        drip_data = load_json_file(DRIP_FILE)
        drop = drip_data.get(drop_id)
        if not drop: await update.message.reply_text("❌ Invalid flash drop."); return
        if time.time() > drop["expires_at"]: await update.message.reply_text(t["age_expired"], parse_mode="Markdown"); return
        if "claimed_users" in drop and user_id in drop["claimed_users"]: await update.message.reply_text(t["age_claimed"], parse_mode="Markdown"); return
        keyboard = [[InlineKeyboardButton("✅ Yes, 18+", callback_data=f"age_yes_{drop_id}"), InlineKeyboardButton("❌ No", callback_data="age_no")]]
        await update.message.reply_text("🔞 Age verification?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    video_code = arg_code
    if video_code.startswith("vid"):
        clean_code = video_code.replace("vid", "")
        if "to" in clean_code:
            try: parts = clean_code.split("to"); msg_start, msg_end = int(parts[0]), int(parts[1])
            except: return
        else:
            try: msg_start = msg_end = int(clean_code)
            except: return
    else: return
    assigned_network = get_global_ab_network(user_id)
    tokens = load_tokens()
    if assigned_network == "monetag":
        extra = [[InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")]] if user_id == ADMIN_ID else None
        kb = adsgram_keyboard(user_id, "wall", msg_start, msg_end, extra)
        if kb: await update.message.reply_text("📺 **Sponsor**\nTap **Watch Ad**, finish the ad in the Mini App, then tap **Check & Get +1**.", reply_markup=kb, parse_mode="Markdown")
        else: await update.message.reply_text("⚠️ Ad server busy, try again in a moment.")
        return
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    if user_id == ADMIN_ID: keyboard.append([InlineKeyboardButton("❌ Skip (Admin)", callback_data="admin_skip_ad")])
    try:
        tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        await asyncio.sleep(0.2)
    except Exception as e1:
        logger.error(f"Forward failed: {e1}")
        try: await context.bot.copy_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        except Exception as e2: logger.error(f"Copy failed: {e2}")
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
            ckey = await get_canonical_key(url, chat_id, bot)
            cache = load_json_file(CACHE_FILE)
            
            if ckey in cache and "file_id" in cache[ckey] and "qualities" not in cache[ckey]:
                cache[ckey]["qualities"] = {"720p": {"file_id": cache[ckey]["file_id"], "vault_msg_id": cache[ckey].get("vault_msg_id"), "size": cache[ckey].get("size", "unknown")}}
                del cache[ckey]["file_id"]
                save_json_file(CACHE_FILE, cache)
            
            if ckey in cache and cache[ckey].get("type") == "video":
                qualities_order = ["1080p", "720p", "480p", "360p", "worst"]
                cached_qualities = cache[ckey].get("qualities", {})
                best_cached_quality = None
                for q in qualities_order:
                    if q in cached_qualities:
                        best_cached_quality = q
                        break
                if best_cached_quality:
                    try:
                        cached = cached_qualities[best_cached_quality]
                        qual_tag = f"[{best_cached_quality}]"
                        sent = await bot.send_video(chat_id=target_destination_id, video=cached["file_id"], caption=f"Item {index}/{len(urls)} ⚡ Cached {qual_tag}")
                        if target_destination_id == chat_id:
                            warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                            asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent.message_id, warn.message_id], 540))
                        cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                        save_json_file(CACHE_FILE, cache)
                        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                        success_count += 1
                        continue
                    except Exception as e: logger.error(f"Batch cache fail {ckey}: {e}")
            
            free_mb = shutil.disk_usage(".").free // (1024*1024)
            min_free = get_min_free_disk_mb()
            effective_max_mb = mtproto_limit_mb()
            if free_mb < min_free + 150: effective_max_mb = min(effective_max_mb, 50)
                
            file_paths, res, size = await asyncio.to_thread(download_media_engine, url, download_type, effective_max_mb)
            if file_paths and os.path.exists(file_paths[0]):
                qual_tag = f"[{res}]"
                sent = await send_video_file(bot, chat_id, target_destination_id, file_paths[0], f"Item {index}/{len(urls)} {qual_tag} Size {size}", None, status_msg)
                if target_destination_id == chat_id:
                    warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                    asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent.message_id, warn.message_id], 540))
                try:
                    vmsg = await bot.send_video(chat_id=VIDEO_VAULT_ID, video=sent.video.file_id, caption=f"{ckey} [{res}]")
                    cache = load_json_file(CACHE_FILE)
                    if ckey not in cache: cache[ckey] = {"type": "video", "timestamp": time.time(), "qualities": {}, "hits": 0}
                    cache[ckey]["qualities"][res] = {"file_id": sent.video.file_id, "vault_msg_id": vmsg.message_id, "size": size}
                    save_json_file(CACHE_FILE, cache)
                except Exception as e: logger.error(f"Vault save: {e}")
                os.remove(file_paths[0])
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}] {t['failed_generic']}")
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
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.message.reply_text(t["banned"]); return
    if await file_link_add_media(update, context): return
    chat_id = update.message.chat_id
    track_user_activity(user_id)
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
        await update.message.reply_text(t["upload_success_user"], reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
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
        except: await update.message.reply_text("❌ Failed", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))

async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.message.reply_text(t["banned"]); return
    if "http" in text.lower():
        flood, wait = is_flood(user_id)
        if flood: await update.message.reply_text(f"🐢 **Slow down!** You sent {FLOOD_LIMIT} links in last minute.\nWait {wait}s before next link.", parse_mode="Markdown"); return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    
    if text == t.get("menu_edit_welcome", "✏️ Edit Welcome Msg") and user_id == ADMIN_ID:
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(user_id)] = {"mode": "admin_edit_welcome"}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        try:
            bot_user = context.bot.username
            await update.message.reply_text(t["admin_edit_welcome_prompt"].format(bot_name=f"@{bot_user}"), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except:
            await update.message.reply_text(t["admin_edit_welcome_prompt"].format(bot_name="Bot"), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return

    support_states = load_json_file(SUPPORT_STATES_FILE)
    if str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "admin_edit_welcome":
        config = load_json_file(CONFIG_FILE)
        config["welcome_message"] = text
        save_json_file(CONFIG_FILE, config)
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await update.message.reply_text(t["admin_welcome_updated"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return

    linking_states = load_linking_states()
    if linking_states.get(str(user_id)) == "waiting_for_channel":
        forward_origin = getattr(update.message, "forward_origin", None)
        f_chat = None
        if forward_origin and getattr(forward_origin, "type", None) == "channel": f_chat = getattr(forward_origin, "chat", None)
        if f_chat is None: f_chat = getattr(update.message, "forward_from_chat", None)
        if f_chat is None: await update.message.reply_text("❌ Please forward a message directly from your channel, not a copied message.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        try:
            bot_member = await context.bot.get_chat_member(chat_id=f_chat.id, user_id=context.bot.id)
            if getattr(bot_member, "status", None) not in ("administrator", "creator"): await update.message.reply_text("⚠️ I detected the channel, but I'm not an admin there yet. Add me as an administrator, then forward a channel message again.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        except Exception as exc:
            logger.warning(f"Could not verify bot admin status in channel {getattr(f_chat, 'id', 'unknown')}: {exc}")
            await update.message.reply_text("⚠️ I couldn't verify my admin access. Please check my admin status and forward another channel message.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        linking_states.pop(str(user_id), None)
        save_linking_states(linking_states)
        await update.message.reply_text(f"✅ Linked {getattr(f_chat, 'title', 'your channel')} successfully. You can now use batch downloads to that channel.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    fl_states = load_json_file(FILE_LINK_STATE_FILE)
    fl_state = fl_states.get(str(user_id))
    if fl_state and fl_state.get("mode") == "file_link_password":
        token = fl_state.get("token")
        links = load_json_file(FILE_LINKS_FILE)
        record = links.get(token)
        fl_states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, fl_states)
        if not record or (record.get("expires_at") and time.time() > record["expires_at"]): await update.message.reply_text(t["link_invalid_expired"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        if text.strip() != str(record.get("password", "")): await update.message.reply_text("❌ Incorrect password.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        if record.get("max_clicks", 0) and record.get("clicks", 0) >= record["max_clicks"]: await update.message.reply_text(t["link_limit_reached"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        await send_file_link_payload(update, context, token, record)
        return
    menu_texts = [t["menu_stats"], t["menu_lang"], t["menu_help"], t["menu_join"], t["menu_upload"], t["menu_uploads"], "🔗 File-to-Link", "🟢 Bot Status", "🔄 Change Batch Channel", "📢 Broadcast", "⚡ Create Flash Drop", "⚙️ Ad Toggle Panel", t.get("menu_edit_welcome", "✏️ Edit Welcome Msg")]
    if text in menu_texts:
        support_states = load_json_file(SUPPORT_STATES_FILE)
        if str(user_id) in support_states: del support_states[str(user_id)]; save_json_file(SUPPORT_STATES_FILE, support_states)
    if text.strip() == "🔗 File-to-Link": await file_to_link_command(update, context); return
    if text.strip() == "🔄 Change Batch Channel":
        linking_states = load_linking_states()
        linking_states[str(user_id)] = "waiting_for_channel"
        save_linking_states(linking_states)
        await update.message.reply_text(t["change_channel_prompt"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    fl_states = load_json_file(FILE_LINK_STATE_FILE)
    fl_state = fl_states.get(str(user_id))
    if fl_state and fl_state.get("mode") == "file_link_set_password":
        if text.strip() == "/clearpassword": fl_state.setdefault("settings", {})["password"] = ""
        else:
            if len(text) > 64: await update.message.reply_text(t["password_too_long"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
            fl_state.setdefault("settings", {})["password"] = text.strip()
        fl_state["mode"] = "collecting"
        fl_states[str(user_id)] = fl_state; save_json_file(FILE_LINK_STATE_FILE, fl_states)
        await update.message.reply_text(t["password_saved"], reply_markup=file_link_keyboard(fl_state))
        return
    if text == "💾 Disk Config" and user_id == ADMIN_ID:
        current = get_min_free_disk_mb()
        await update.message.reply_text(t["disk_config_prompt"].format(current), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return
    if text == "⚡ MTProto Config" and user_id == ADMIN_ID:
        current = get_mtproto_max_mb()
        await update.message.reply_text(t["mtproto_config_prompt"].format(current), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return
    if text.startswith("📦 Set Free") and user_id == ADMIN_ID:
        current = get_free_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i} free", callback_data=f"set_free_{i}") for i in [2,3,4,5]]]
        await update.message.reply_text(t["free_panel_prompt"].format(current), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text.startswith("🎁 Set Reward") and user_id == ADMIN_ID:
        current = get_reward_amount()
        keyboard = [[InlineKeyboardButton(f"✅ {i} (Current)" if i==current else f"{i}", callback_data=f"set_reward_{i}") for i in [1,2,3,5]]]
        await update.message.reply_text(t["reward_panel_prompt"].format(current), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == "⚙️ Ad Toggle Panel" and user_id == ADMIN_ID:
        config = load_json_file(CONFIG_FILE)
        mode = config.get("ad_mode", "auto").upper()
        keyboard = [[InlineKeyboardButton("🔄 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("📺 Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("🌐 Adsterra", callback_data="set_ad_adsterra")]]
        await update.message.reply_text(t["ad_panel_prompt"].format(mode), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    
    if user_id == ADMIN_ID and str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "admin_replying":
        target_user_id = support_states[str(user_id)]["target_user_id"]
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("🔒 Close", callback_data=f"support_close_{ticket_id}")]]
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"💬 **Admin Reply:**\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            await update.message.reply_text(f"✅ Sent to {target_user_id}!", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except Exception as e: await update.message.reply_text(f"❌ {e}", reply_markup=get_main_keyboard(lang, True))
        return
    if str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "user_writing":
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("🔒 Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 Ticket [{ticket_id}] From {user_id}\n\n{text}", parse_mode="Markdown")
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("✅ Sent!", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == "⚡ Create Flash Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        states[str(user_id)] = {"mode": "collecting", "items": []}
        save_json_file(DRIP_STATE_FILE, states)
        kb = [[KeyboardButton("🚀 Finish & Broadcast Drop")],[KeyboardButton("❌ Cancel / Exit")]]
        await update.message.reply_text("⚡ Flash Drop Mode: Send files", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")
        return
    if text == "🟢 Bot Status": await status_command(update, context); return
    if text.strip() in ("🧪 Test Ad", "📢 Ad Info"):
        if user_id != ADMIN_ID: await update.message.reply_text("✅ Menu updated.", reply_markup=get_main_keyboard(lang, False)); return
        if text.strip() == "🧪 Test Ad": await send_test_ad(update.message, user_id); return
    if text.strip() == "📢 Ad Info" and user_id == ADMIN_ID: await update.message.reply_text(build_ad_info_text(user_id), reply_markup=get_main_keyboard(lang, True)); return
    if text == "📢 Broadcast" and user_id == ADMIN_ID: await update.message.reply_text("📢 /broadcast [message] or reply with /broadcast", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True)); return
    if text == "❌ Cancel / Exit" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states: del states[str(user_id)]; save_json_file(DRIP_STATE_FILE, states)
        await update.message.reply_text(t["drop_cancelled"], reply_markup=get_main_keyboard(lang, True), parse_mode="Markdown")
        return
    if text == "🚀 Finish & Broadcast Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        user_state = states.get(str(user_id))
        if not user_state or not user_state.get("items"): await update.message.reply_text(t["drop_no_items"], reply_markup=get_main_keyboard(lang, True)); return
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
        await update.message.reply_text(f"📥 Item #{len(user_state['items'])} added", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == t["menu_stats"]:
        if user_id == ADMIN_ID: await stats(update, context)
        else:
            tokens = load_tokens()
            profile = tokens.get(str(user_id), {})
            d_left = profile.get("downloads_left", get_free_amount())
            b_left = profile.get("batch_downloads_left", get_free_amount()*5)
            await update.message.reply_text(t["stats_msg"].format(d_left, b_left), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == t["menu_join"]: await update.message.reply_text(f"[Join]({PUBLIC_CHANNEL_URL})", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
    if text == t["menu_help"]:
        keyboard = [[InlineKeyboardButton("💬 Open Support", callback_data="open_support")]]
        await update.message.reply_text(f"Support: [Help]({HELP_CHANNEL_URL})", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == t["menu_lang"]: await language_command(update, context); return
    if text == t["menu_upload"]:
        prompt = t["admin_upload_prompt"] if user_id == ADMIN_ID else t["user_upload_prompt"]
        await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == t["menu_uploads"] and user_id == ADMIN_ID:
        uploads = load_json_file(UPLOADS_FILE)
        if not uploads: await update.message.reply_text(t["no_uploads"], reply_markup=get_main_keyboard(lang, True)); return
        await update.message.reply_text(t["admin_upload_prompt"], reply_markup=get_main_keyboard(lang, True))
        for k, data in list(uploads.items())[-20:]:
            try: await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=data["user_id"], message_id=data["msg_id"])
            except: pass
        return
    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = [u for u in extracted_urls if not ("t.me/" in u and "start=" in u)]
    extracted_urls = filtered
    if not extracted_urls:
        if "t.me/" in text and "start=" in text: await update.message.reply_text("👆 Please use the buttons above.", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
                if kb: await update.message.reply_text(t["limit_reached"], reply_markup=kb, parse_mode="Markdown")
                else: await update.message.reply_text("⚠️ Ad server busy, try again in a moment.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
        await update.message.reply_text(f"✅ Linked {f_chat.title}", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
    user_id = update.message.from_user.id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.message.reply_text(t["banned"]); return
    
    support_states = load_json_file(SUPPORT_STATES_FILE)
    if str(user_id) in support_states and support_states[str(user_id)].get("mode") == "user_writing": await handle_user_upload(update, context); return
    if user_id == ADMIN_ID and str(ADMIN_ID) in support_states and support_states[str(ADMIN_ID)].get("mode") == "admin_replying": await handle_user_upload(update, context); return
    if await file_link_add_media(update, context): return
        
    document = update.message.document
    if user_id == ADMIN_ID and document.file_name in BACKUP_FILES:
        await update.message.reply_text(f"🔄 Restoring <b>{document.file_name}</b>...", parse_mode="HTML")
        try:
            file = await context.bot.get_file(document.file_id)
            temp_path = f"temp_{document.file_name}"
            await file.download_to_drive(temp_path)
            with open(temp_path, 'r') as f: data = json.load(f)
            os.replace(temp_path, document.file_name)
            await update.message.reply_text(t["restore_success"].format(document.file_name, len(data) if isinstance(data, dict) else len(data)), parse_mode="HTML", reply_markup=get_main_keyboard(get_lang(user_id), True))
            return
        except json.JSONDecodeError:
            await update.message.reply_text(t["restore_invalid_json"].format(document.file_name), parse_mode="HTML", reply_markup=get_main_keyboard(get_lang(user_id), True))
            if os.path.exists(f"temp_{document.file_name}"): os.remove(f"temp_{document.file_name}")
            return
        except Exception as e:
            await update.message.reply_text(t["restore_failed"].format(str(e)), reply_markup=get_main_keyboard(get_lang(user_id), True))
            if os.path.exists(f"temp_{document.file_name}"): os.remove(f"temp_{document.file_name}")
            return

    if not document.file_name or not document.file_name.endswith('.txt'): await handle_user_upload(update, context); return
    if active_batch_sessions.get(user_id, False): return
    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        urls = re.findall(r'https?://[^\s]+', file_bytes.decode('utf-8', errors='ignore'))
        if not urls: await update.message.reply_text(t["no_links"], reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)); return
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = urls
        keyboard = [[InlineKeyboardButton("🎬 Video", callback_data=f"batchtype_video_{payload_key}")]]
        await update.message.reply_text(t["batch_count"].format(len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e: logger.error(f"File: {e}")

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
    for idx,(uid,info) in enumerate(sorted_users,1): top_text+=f"{idx}. `{uid}` — {info.get('total_interactions',0)}\n"
    if not top_text: top_text="No activity yet"
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    used_mb = get_downloads_usage_mb()
    cache = load_json_file(CACHE_FILE)
    flood_data = load_json_file(FLOOD_FILE)
    banned = load_json_file(BANNED_FILE)
    total_hits = sum(v.get("hits",0) for v in cache.values() if isinstance(v, dict))
    host_free = shutil.disk_usage(".").free // (1024*1024) if os.path.exists(".") else 0
    txt = (f"📊 **ADVANCED ADMIN**\n\n• Total: **{total_users}**\n• 24h Active: **{active_24hr}**\n• Ad Mode: **{mode}**\n\n📢 **Ad Split:**\n• Monetag: **{adsgram_count}**\n• Adsterra: **{adsterra_count}**\n\n🖥️ **Render:**\n• Used: **{used_mb}MB**\n• Free: **{free_mb}MB**\n• Host: **{host_free}MB**\n• Active: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\n• Queue: **{download_queue.qsize()}**\n• Cache: **{len(cache)}** files\n• Hits: **{total_hits}** saved\n• Flood: **{len(flood_data)}**\n• Banned: **{len(banned)}**\n\n🎞️ **Video Vault:** `{VIDEO_VAULT_ID}`\n🏆 **Top 10:**\n{top_text}")
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    cache = load_json_file(CACHE_FILE)
    await update.message.reply_text(f"🟢 **Status V38 Monetag**\nMode: **{mode}**\nFree: **{free_mb}MB**\nDL: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\nQueue: **{download_queue.qsize()}**\nCache: **{len(cache)}**\nVault: **{VIDEO_VAULT_ID}**\nReward: +1 realistic\nFlood: **ON**\nBackup: **6hr to {PRIVATE_CHANNEL_ID}**", parse_mode="Markdown", reply_markup=get_main_keyboard(get_lang(update.message.from_user.id), update.message.from_user.id == ADMIN_ID))

async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID: return
    file_list = "\n".join([f"   • <b>{f}</b>" for f in BACKUP_FILES])
    await update.message.reply_text(f"🔄 <b>Restore Backup Files</b>\n\n1. Go to your private backup channel.\n2. <b>Long-press</b> a backup file, then tap all the others to select them.\n3. Hit <b>Forward</b> and send them all to this bot at once!\n\n<b>Files to restore:</b>\n{file_list}\n\nI will automatically detect and restore each file! ⚡", parse_mode="HTML", reply_markup=get_main_keyboard("en", True))

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
    if not args and not reply_msg: await update.message.reply_text("Usage: /broadcast [msg] or reply with /broadcast", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
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
    if not context.args: await update.message.reply_text("Usage: /ban <user_id>", reply_markup=get_main_keyboard("en", True)); return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        banned[target] = {"banned_at": time.time(), "reason": "spam"}
        save_json_file(BANNED_FILE, banned)
        await update.message.reply_text(f"🚫 Banned {target}", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except Exception as e: await update.message.reply_text(f"❌ {e}", reply_markup=get_main_keyboard("en", True))

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: /unban <user_id>", reply_markup=get_main_keyboard("en", True)); return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        if target in banned:
            del banned[target]
            save_json_file(BANNED_FILE, banned)
            await update.message.reply_text(f"✅ Unbanned {target}", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
        else: await update.message.reply_text(f"Not banned", reply_markup=get_main_keyboard("en", True))
    except Exception as e: await update.message.reply_text(f"❌ {e}", reply_markup=get_main_keyboard("en", True))

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(f"📦 Backing up ALL files to {PRIVATE_CHANNEL_ID}...", reply_markup=get_main_keyboard("en", True))
    await backup_to_channel(context.bot)
    await update.message.reply_text("✅ Full Backup sent!", reply_markup=get_main_keyboard("en", True))

async def set_disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/setdisk <mb>`\nExample: `/setdisk 500`", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
    try:
        value = int(context.args[0])
        if value < 50: await update.message.reply_text("⚠️ Value must be at least 50MB.", reply_markup=get_main_keyboard("en", True)); return
        config = load_json_file(CONFIG_FILE)
        config["min_free_disk_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"✅ Minimum free disk space set to **{value}MB**", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except ValueError: await update.message.reply_text("❌ Invalid number.", reply_markup=get_main_keyboard("en", True))

async def set_mtproto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/setmtproto <mb>`\nExample: `/setmtproto 1000`", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
    try:
        value = int(context.args[0])
        if value < 50: await update.message.reply_text("⚠️ Value must be at least 50MB.", reply_markup=get_main_keyboard("en", True)); return
        config = load_json_file(CONFIG_FILE)
        config["mtproto_max_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"✅ MTProto max upload size set to **{value}MB**", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except ValueError: await update.message.reply_text("❌ Invalid number.", reply_markup=get_main_keyboard("en", True))

# ============ MODIFIED: cached_download_and_send with multi-image support ============

async def send_carousel_images_to_chat(bot, chat_id, file_paths, user_id, t, ckey=None):
    """
    Send downloaded carousel images to chat in groups of up to 10.
    Returns list of sent message objects.
    """
    sent_messages = []
    kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
    
    for i in range(0, len(file_paths), 10):
        group = file_paths[i:i+10]
        group_files = []
        try:
            for path in group:
                group_files.append(open(path, 'rb'))
            
            if len(group_files) == 1:
                # Single image
                msg = await bot.send_photo(chat_id=chat_id, photo=group_files[0], reply_markup=kb)
                sent_messages.append(msg)
            else:
                # Media group (2-10 images)
                media_group = [InputMediaPhoto(media=f) for f in group_files]
                msgs = await bot.send_media_group(chat_id=chat_id, media=media_group)
                sent_messages.extend(msgs)
        except Exception as e:
            logger.error(f"Failed to send carousel group: {e}")
        finally:
            # Always close file handles
            for f in group_files:
                try: f.close()
                except: pass
    
    return sent_messages

async def save_carousel_to_vault(bot, file_paths, ckey):
    """
    Save all carousel images to the private vault.
    Returns list of vault message IDs.
    """
    vault_msg_ids = []
    sent_file_ids = []
    
    for i in range(0, len(file_paths), 10):
        group = file_paths[i:i+10]
        group_files = []
        try:
            for path in group:
                group_files.append(open(path, 'rb'))
            
            if len(group_files) == 1:
                msg = await bot.send_photo(chat_id=VIDEO_VAULT_ID, photo=group_files[0], caption=ckey)
                vault_msg_ids.append(msg.message_id)
                sent_file_ids.append(msg.photo[-1].file_id)
            else:
                media_group = [InputMediaPhoto(media=f) for f in group_files]
                msgs = await bot.send_media_group(chat_id=VIDEO_VAULT_ID, media=media_group)
                for m in msgs:
                    vault_msg_ids.append(m.message_id)
                    sent_file_ids.append(m.photo[-1].file_id)
        except Exception as e:
            logger.error(f"Vault carousel save failed: {e}")
        finally:
            for f in group_files:
                try: f.close()
                except: pass
    
    return vault_msg_ids, sent_file_ids

async def replay_cached_images(bot, chat_id, user_id, cached, t):
    """
    Replay cached carousel images from file_ids array.
    Handles both new (file_ids list) and old (single file_id) formats.
    """
    file_ids = cached.get("file_ids", [])
    vault_msg_ids = cached.get("vault_msg_ids", [])
    size = cached.get("size", "")
    kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
    sent_count = 0
    
    # Backward compat: old single file_id
    if not file_ids and cached.get("file_id"):
        file_ids = [cached["file_id"]]
    
    for i in range(0, len(file_ids), 10):
        group = file_ids[i:i+10]
        try:
            if len(group) == 1:
                await bot.send_photo(chat_id=chat_id, photo=group[0], reply_markup=kb)
                sent_count += 1
            else:
                media_group = [InputMediaPhoto(media=fid) for fid in group]
                await bot.send_media_group(chat_id=chat_id, media=media_group)
                sent_count += len(group)
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Cached image replay fail, trying vault: {e}")
            # Fallback to vault
            if vault_msg_ids:
                for j in range(i, min(i + len(group), len(vault_msg_ids))):
                    try:
                        await bot.forward_message(chat_id=chat_id, from_chat_id=VIDEO_VAULT_ID, message_id=vault_msg_ids[j])
                        sent_count += 1
                        await asyncio.sleep(0.2)
                    except: pass
    
    # Send warning if any sent
    if sent_count > 0:
        warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
        return sent_count, warn.message_id
    
    return 0, None

async def cached_download_and_send(bot, chat_id, user_id, url, dl_type, t):
    cache = load_json_file(CACHE_FILE)
    ckey = await get_canonical_key(url, chat_id, bot)
    
    # Backward compat: migrate old single file_id format to qualities
    if ckey in cache and "file_id" in cache[ckey] and "qualities" not in cache[ckey]:
        cache[ckey]["qualities"] = {"720p": {"file_id": cache[ckey]["file_id"], "vault_msg_id": cache[ckey].get("vault_msg_id"), "size": cache[ckey].get("size", "unknown")}}
        del cache[ckey]["file_id"]
        save_json_file(CACHE_FILE, cache)
    
    if ckey in cache and cache[ckey].get("type") in ("video", "images", "audio"):
        cached_qualities = cache[ckey].get("qualities", {})
        if dl_type == 'video': qualities_order = ["1080p", "720p", "480p", "360p", "worst"]
        elif dl_type == 'audio': qualities_order = ["audio"]
        else: qualities_order = ["original"]
            
        best_cached_quality = None
        for q in qualities_order:
            if q in cached_qualities:
                best_cached_quality = q
                break
                
        if best_cached_quality:
            cached = cached_qualities[best_cached_quality]
            kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
            
            # ============ NEW: Handle carousel images from cache ============
            if dl_type == 'images' and cached.get("file_ids"):
                sent_count, warn_id = await replay_cached_images(bot, chat_id, user_id, cached, t)
                if sent_count > 0:
                    cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                    save_json_file(CACHE_FILE, cache)
                    deduct_download_counter(user_id, is_batch=False)
                    # Schedule deletion of warning
                    if warn_id:
                        asyncio.create_task(schedule_deletion(bot, chat_id, [warn_id], 540))
                    return True
            
            # ============ Legacy single file_id for images ============
            elif dl_type == 'images' and cached.get("file_id"):
                try:
                    sent = await bot.send_photo(chat_id=chat_id, photo=cached["file_id"], caption=t["cached_instant_image"].format(ckey), reply_markup=kb)
                    warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                    asyncio.create_task(schedule_deletion(bot, chat_id, [sent.message_id, warn.message_id], 540))
                    cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                    save_json_file(CACHE_FILE, cache)
                    deduct_download_counter(user_id, is_batch=False)
                    return True
                except Exception as e:
                    logger.error(f"Legacy cached image fail: {e}")
            
            # ============ Video / Audio cache (unchanged) ============
            elif dl_type in ('video', 'audio'):
                file_id = cached.get("file_id")
                if file_id:
                    try:
                        sz = cached.get("size", "")
                        qual_tag = f"[{best_cached_quality}]"
                        if dl_type == 'video': 
                            sent = await bot.send_video(chat_id=chat_id, video=file_id, caption=t["cached_instant_video"].format(qual_tag, sz, ckey), reply_markup=kb)
                        else: 
                            sent = await bot.send_audio(chat_id=chat_id, audio=file_id, caption=t["cached_instant_audio"].format(ckey), reply_markup=kb)
                        
                        warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                        asyncio.create_task(schedule_deletion(bot, chat_id, [sent.message_id, warn.message_id], 540))
                        cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                        save_json_file(CACHE_FILE, cache)
                        deduct_download_counter(user_id, is_batch=False)
                        return True
                    except Exception as e:
                        logger.error(f"Cache send fail {ckey} {best_cached_quality}: {e}")
                        # Try vault fallback
                        try:
                            vmid = cached.get("vault_msg_id")
                            if vmid:
                                fwd = await bot.forward_message(chat_id=chat_id, from_chat_id=VIDEO_VAULT_ID, message_id=vmid)
                                warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"] + " (from vault)", reply_markup=kb)
                                asyncio.create_task(schedule_deletion(bot, chat_id, [fwd.message_id, warn.message_id], 540))
                                cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                                save_json_file(CACHE_FILE, cache)
                                deduct_download_counter(user_id, is_batch=False)
                                return True
                        except Exception as e2:
                            logger.error(f"Vault fallback fail: {e2}")
                            # Remove bad cache entry
                            if ckey in cache and "qualities" in cache[ckey] and best_cached_quality in cache[ckey]["qualities"]:
                                del cache[ckey]["qualities"][best_cached_quality]
                                save_json_file(CACHE_FILE, cache)

    # No cache hit - download fresh
    status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type) + f"\n`{ckey}`", parse_mode="Markdown")
    try:
        free_mb = shutil.disk_usage(".").free // (1024*1024)
        min_free = get_min_free_disk_mb()
        effective_max_mb = get_mtproto_max_mb()
        if free_mb < min_free + 150: effective_max_mb = min(effective_max_mb, 50)
            
        file_paths, res, size = await asyncio.to_thread(download_media_engine, url, dl_type, effective_max_mb)
        if not file_paths: raise ValueError("FILE_NOT_FOUND")
        
        cache = load_json_file(CACHE_FILE)
        if ckey not in cache: cache[ckey] = {"type": dl_type, "timestamp": time.time(), "qualities": {}, "hits": 0}
            
        qual_tag = f"[{res}]"
        kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
        
        # ============ NEW: Multi-image carousel delivery ============
        if dl_type == 'images':
            # Send all images to chat (in groups of 10)
            sent_messages = await send_carousel_images_to_chat(bot, chat_id, file_paths, user_id, t)
            
            if not sent_messages:
                raise ValueError("SEND_FAILED")
            
            # Send warning
            warn = await bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)), reply_markup=kb)
            
            # Schedule deletion for ALL sent messages
            all_ids = [m.message_id for m in sent_messages] + [warn.message_id]
            asyncio.create_task(schedule_deletion(bot, chat_id, all_ids, 540))
            
            # Save ALL to vault + cache
            try:
                vault_msg_ids, file_ids = await save_carousel_to_vault(bot, file_paths, ckey)
                cache[ckey]["qualities"]["original"] = {
                    "file_ids": file_ids,
                    "vault_msg_ids": vault_msg_ids,
                    "size": size
                }
            except Exception as e:
                logger.error(f"Vault save all failed: {e}")
                # Still try to save file_ids we have
                try:
                    file_ids = [m.photo[-1].file_id for m in sent_messages]
                    cache[ckey]["qualities"]["original"] = {
                        "file_ids": file_ids,
                        "vault_msg_ids": [],
                        "size": size
                    }
                except: pass
            
            # Cleanup temp files
            for p in file_paths:
                try: os.remove(p)
                except: pass
            
        # ============ Audio (unchanged) ============
        elif dl_type == 'audio':
            sent_media = await send_audio_file(bot, chat_id, file_paths[0], f"🎵 Size {size} `{ckey}`", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent_media.audio.file_id, caption=ckey)
                cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "vault_msg_id": vmsg.message_id, "size": size}
            except: cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "size": size}
            os.remove(file_paths[0])
            
        # ============ Video (unchanged) ============
        else:
            sent_media = await send_video_file(bot, chat_id, chat_id, file_paths[0], f"✨ {qual_tag} Size {size} `{ckey}`", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_video(chat_id=VIDEO_VAULT_ID, video=sent_media.video.file_id, caption=f"{ckey} [{res}]")
                cache[ckey]["qualities"][res] = {"file_id": sent_media.video.file_id, "vault_msg_id": vmsg.message_id, "size": size}
            except Exception as e: 
                logger.error(f"Vault save fail: {e}")
                cache[ckey]["qualities"][res] = {"file_id": sent_media.video.file_id, "size": size}
            os.remove(file_paths[0])
            
        cache[ckey]["hits"] = cache[ckey].get("hits", 0) + 1
        save_json_file(CACHE_FILE, cache)
        await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        deduct_download_counter(user_id, is_batch=False)
        
        await bot.send_message(chat_id=chat_id, text=t["download_success"], reply_markup=kb)
        return True
    except Exception as e:
        logger.error(f"DL {ckey}: {e}")
        # Cleanup any downloaded files on error
        try:
            for f in os.listdir("downloads"):
                fp = os.path.join("downloads", f)
                if os.path.isfile(fp) and os.path.getmtime(fp) > time.time() - 60:
                    try: os.remove(fp)
                    except: pass
        except: pass
        if "FILE_TOO_LARGE" in str(e): err = t["error_50mb"]
        elif "MTPROTO_OFF" in str(e): err = "⚠️ Big files need fast mode, which is offline right now."
        elif "MTPROTO_PEER" in str(e): err = "⚠️ Send /start to this bot once, then send the link again."
        elif "NO_IMAGES" in str(e): err = t["error_no_img"]
        else: err = t["error_generic"]
        kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
        try: await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=err, reply_markup=kb)
        except: pass
        return False

# ============ END cached_download_and_send changes ============

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await query.answer(t["banned"], show_alert=True); return
    track_user_activity(user_id)
    data = query.data
    chat_id = query.message.chat_id
    lang = get_lang(user_id)
    
    if data.startswith("fl_"):
        states = load_json_file(FILE_LINK_STATE_FILE)
        state = states.get(str(user_id))
        if data == "fl_cancel":
            states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer(t["fl_cancelled"])
            try: await query.message.edit_text(t["fl_cancelled"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            except: pass
            return
        if data == "fl_refresh":
            await query.answer()
            if state: await query.message.edit_reply_markup(reply_markup=file_link_keyboard(state))
            return
        if not state: await query.answer(t["fl_start_again"], show_alert=True); return
        settings = state.setdefault("settings", {})
        if data == "fl_expiry":
            kb = [[InlineKeyboardButton("1 hour", callback_data="fl_exp_3600"), InlineKeyboardButton("1 day", callback_data="fl_exp_86400")],
                  [InlineKeyboardButton("7 days", callback_data="fl_exp_604800"), InlineKeyboardButton("30 days", callback_data="fl_exp_2592000")],
                  [InlineKeyboardButton("Never", callback_data="fl_exp_never"), InlineKeyboardButton("⬅ Back", callback_data="fl_refresh")]]
            await query.answer(); await query.message.reply_text(t["fl_choose_expiry"], reply_markup=InlineKeyboardMarkup(kb)); return
        if data.startswith("fl_exp_"):
            value = data[7:]
            settings["expiry"] = "never" if value == "never" else value
            states[str(user_id)] = state; save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer(t["fl_expiry_updated"])
            try: await query.message.edit_reply_markup(reply_markup=file_link_keyboard(state))
            except: pass
            return
        if data == "fl_maxuses":
            kb = [[InlineKeyboardButton(str(n), callback_data=f"fl_uses_{n}") for n in (1,5,10)],
                  [InlineKeyboardButton("25", callback_data="fl_uses_25"), InlineKeyboardButton("50", callback_data="fl_uses_50"), InlineKeyboardButton("Unlimited", callback_data="fl_uses_0")],
                  [InlineKeyboardButton("⬅ Back", callback_data="fl_refresh")]]
            await query.answer(); await query.message.reply_text(t["fl_choose_max_uses"], reply_markup=InlineKeyboardMarkup(kb)); return
        if data.startswith("fl_uses_"):
            settings["max_clicks"] = int(data.rsplit("_",1)[1])
            states[str(user_id)] = state; save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer(t["fl_uses_updated"])
            try: await query.message.edit_reply_markup(reply_markup=file_link_keyboard(state))
            except: pass
            return
        if data == "fl_password":
            state["mode"] = "file_link_set_password"
            states[str(user_id)] = state; save_json_file(FILE_LINK_STATE_FILE, states)
            await query.answer(); await query.message.reply_text(t["fl_set_password"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            return
        if data == "fl_create":
            items = state.get("items", [])
            if not items: await query.answer("Send at least one file first", show_alert=True); return
            if user_id != ADMIN_ID:
                tokens = load_tokens(); profile = tokens.get(str(user_id))
                if not isinstance(profile, dict): profile = {"user_id": int(user_id), "downloads_left": get_free_amount(), "batch_downloads_left": get_free_amount()*5, "last_reset": time.time()}
                try:
                    last_reset = float(profile.get("last_reset", 0) or 0)
                    if time.time() - last_reset >= 86400: profile["downloads_left"] = get_free_amount(); profile["batch_downloads_left"] = get_free_amount()*5; profile["last_reset"] = time.time()
                except: pass
                remaining = int(profile.get("downloads_left", get_free_amount()) or 0)
                if remaining <= 0:
                    await query.answer(t["fl_daily_limit"], show_alert=True)
                    assigned_network = get_global_ab_network(user_id)
                    if assigned_network == "monetag":
                        kb = adsgram_keyboard(user_id, "wall", 0, 0)
                        if kb: await query.message.reply_text(t["limit_reached"], reply_markup=kb, parse_mode="Markdown")
                        else: await query.message.reply_text(t["fl_ad_busy"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
                    else:
                        bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
                        reward_kb = [[InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1", url=bridge_link)], [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("💜 Check & Get +1", callback_data="verify_user")]]
                        await query.message.reply_text(t["limit_reached"], reply_markup=InlineKeyboardMarkup(reward_kb), parse_mode="Markdown")
                    return
                profile["downloads_left"] = remaining - 1
                tokens[str(user_id)] = profile; save_tokens(tokens)
            token = hashlib.sha256(f"{user_id}:{time.time_ns()}".encode()).hexdigest()[:12]
            expiry_setting = settings.get("expiry", "never")
            expires_at = None if expiry_setting == "never" else time.time() + int(expiry_setting)
            links = load_json_file(FILE_LINKS_FILE)
            links[token] = {"creator_id": user_id, "items": items, "created_at": time.time(), "expires_at": expires_at, "max_clicks": int(settings.get("max_clicks", 0) or 0), "clicks": 0, "password": settings.get("password", "")}
            save_json_file(FILE_LINKS_FILE, links)
            states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, states)
            me = await context.bot.get_me()
            link = f"https://t.me/{me.username}?start=fl_{token}"
            await query.answer(t["fl_link_created"])
            await query.message.reply_text(t["fl_link_ready"].format(link, len(items)), disable_web_page_preview=True, reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            try: await query.message.edit_reply_markup(reply_markup=None)
            except: pass
            return
        await query.answer(); return
    if data == "admin_skip_ad" and user_id == ADMIN_ID:
        tokens = load_tokens()
        if str(user_id) in tokens: del tokens[str(user_id)]; save_tokens(tokens)
        await query.answer(t["admin_skipped"], show_alert=True)
        try: await query.message.edit_text(t["admin_bypassed"], reply_markup=get_main_keyboard(lang, True))
        except: pass
        return
    if data.startswith("set_free_") and user_id == ADMIN_ID:
        val = int(data.replace("set_free_", "")); set_free_amount(val)
        await query.answer(t["free_set"].format(val), show_alert=True)
        try: await query.message.edit_text(t["free_updated"].format(val), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except: pass
        return
    if data.startswith("set_reward_") and user_id == ADMIN_ID:
        val = int(data.replace("set_reward_", "")); set_reward_amount(val)
        await query.answer(t["reward_set"].format(val), show_alert=True)
        try: await query.message.edit_text(t["reward_updated"].format(val), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except: pass
        return
    if data.startswith("set_ad_") and user_id == ADMIN_ID:
        mode = data.replace("set_ad_", "")
        if mode == "adsgram": mode = "monetag"
        config = load_json_file(CONFIG_FILE); config["ad_mode"] = mode; save_json_file(CONFIG_FILE, config)
        await query.answer(t["mode_updated"].format(mode.upper().replace('ADSGRAM', 'MONETAG')), show_alert=True)
        try: await query.message.edit_text(t["mode_updated"].format(mode.upper().replace('ADSGRAM','MONETAG')), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except: pass
        return
    if data == "open_support":
        support_states = load_json_file(SUPPORT_STATES_FILE)
        ticket_id = str(int(time.time()))
        support_states[str(user_id)] = {"mode": "user_writing", "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer(t["lang_updated"]); await query.message.reply_text(t["support_opened"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if data.startswith("support_reply_"):
        target_user_id = data.replace("support_reply_", "")
        ticket_id = str(int(time.time()))
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(ADMIN_ID)] = {"mode": "admin_replying", "target_user_id": int(target_user_id), "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer(t["admin_reply_mode"].split(":")[0]); await context.bot.send_message(chat_id=ADMIN_ID, text=t["admin_reply_mode"].format(target_user_id), parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
        return
    if data.startswith("user_reply_ticket_"):
        ticket_id = data.replace("user_reply_ticket_", "")
        support_states = load_json_file(SUPPORT_STATES_FILE)
        support_states[str(user_id)] = {"mode": "user_writing", "ticket_id": ticket_id}
        save_json_file(SUPPORT_STATES_FILE, support_states)
        await query.answer(t["user_reply_mode"].split(":")[0]); await query.message.reply_text(t["user_reply_mode"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if data.startswith("support_close_"):
        await query.answer(t["support_closed"], show_alert=True)
        try: await query.message.edit_text(t["support_closed"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        except: pass
        return
    if data == "drop_cancel" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states: del states[str(user_id)]; save_json_file(DRIP_STATE_FILE, states)
        await query.answer(t["drop_cancelled"])
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=chat_id, text=t["drop_cancelled"], reply_markup=get_main_keyboard(lang, True))
        return
    if data.startswith("drop_time_") and user_id == ADMIN_ID:
        seconds = int(data.replace("drop_time_", ""))
        mins_label = "30 Seconds" if seconds == 30 else f"{seconds//60} Minutes"
        states = load_json_file(DRIP_STATE_FILE)
        user_state = states.get(str(user_id))
        if not user_state or not user_state.get("items"): await query.answer(t["drop_no_items"], show_alert=True); return
        items_to_drop = user_state["items"]
        del states[str(user_id)]; save_json_file(DRIP_STATE_FILE, states)
        drop_id = str(int(time.time()))
        expires_at = time.time() + 480
        drop_data = load_json_file(DRIP_FILE)
        drop_data[drop_id] = {"items": items_to_drop, "expires_at": expires_at, "delete_delay": seconds, "delete_label": mins_label, "claimed_users": []}
        save_json_file(DRIP_FILE, drop_data)
        await query.answer(t["drop_timer_set"].format(mins_label))
        try: await query.message.delete()
        except: pass
        bot_username = context.bot.username
        claim_url = f"https://t.me/{bot_username}?start=drip_{drop_id}"
        all_users = set()
        for d in [load_json_file(LANG_FILE), load_tokens()]:
            for uid in d.keys():
                try: all_users.add(int(uid))
                except: pass
        await context.bot.send_message(chat_id=chat_id, text=t["drop_broadcasting"].format(len(items_to_drop), len(all_users)), parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🎁 Claim Now", url=claim_url)]]
        broadcast_text = t["drop_flash_text"].format(mins_label)
        success = 0
        for uid in all_users:
            if uid == ADMIN_ID or is_banned(uid): continue
            try:
                await context.bot.send_message(chat_id=uid, text=broadcast_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                success+=1; await asyncio.sleep(0.05)
            except: pass
        await context.bot.send_message(chat_id=chat_id, text=t["drop_done"].format(success), reply_markup=get_main_keyboard(lang, True), parse_mode="Markdown")
        return
    if data.startswith("age_yes_"):
        drop_id = data.replace("age_yes_", "")
        drip_data = load_json_file(DRIP_FILE)
        drop = drip_data.get(drop_id)
        if not drop: await query.answer(t["age_expired"], show_alert=True); return
        if time.time() > drop["expires_at"]:
            await query.answer(t["age_expired"], show_alert=True)
            try: await query.message.edit_text(t["age_expired"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            except: pass
            return
        if "claimed_users" not in drop: drop["claimed_users"]=[]
        if user_id in drop["claimed_users"]:
            await query.answer(t["age_claimed"], show_alert=True)
            try: await query.message.edit_text(t["age_claimed"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            except: pass
            return
        drop["claimed_users"].append(user_id)
        drip_data[drop_id]=drop; save_json_file(DRIP_FILE, drip_data)
        await query.answer(t["age_verified"])
        try:
            await query.message.delete()
            sent_ids=[]
            for item in drop["items"]:
                fwd = await context.bot.copy_message(chat_id=user_id, from_chat_id=item["chat_id"], message_id=item["message_id"])
                sent_ids.append(fwd.message_id); await asyncio.sleep(0.2)
            warn = await context.bot.send_message(chat_id=user_id, text=f"⏳ Auto-deletes in {drop.get('delete_label','9 Minutes')}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            sent_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, sent_ids, drop.get("delete_delay",540)))
        except Exception as e: await context.bot.send_message(chat_id=user_id, text=f"❌ {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if data == "age_no":
        await query.answer(t["age_denied"], show_alert=True)
        try: await query.message.edit_text(t["age_denied"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        except: pass
        return
    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        langs = load_json_file(LANG_FILE); langs[str(user_id)]=new_lang; save_json_file(LANG_FILE, langs)
        new_t = LANGUAGES.get(new_lang, LANGUAGES["en"])
        await query.answer(t["lang_updated"], show_alert=True)
        try:
            config = load_json_file(CONFIG_FILE)
            welcome_msg = config.get("welcome_message", new_t["welcome"])
            try:
                bot_user = context.bot.username
                welcome_msg = welcome_msg.replace("{bot_name}", f"@{bot_user}")
            except: pass
            await query.message.reply_text(welcome_msg, reply_markup=get_main_keyboard(new_lang, user_id==ADMIN_ID), parse_mode="Markdown")
            await query.message.delete()
        except: pass
        return
    if data.startswith("batchtype_"):
        parts = data.split("_",2); dl_type = parts[1]; payload_key = parts[2]
        urls = pending_batch_payloads.get(payload_key)
        if not urls: await query.answer(t["batch_expired"], show_alert=True); return
        await query.message.delete()
        keyboard = [[InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{dl_type}_{payload_key}")], [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{dl_type}_{payload_key}")], [InlineKeyboardButton("🔄 Change Channel", callback_data="change_channel")]]
        await context.bot.send_message(chat_id=chat_id, text=t["batch_dest"].format(len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if data.startswith("fmt_"):
        parts = data.split("_",2); fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url: await query.answer(t["batch_expired"], show_alert=True); return
        await query.answer(t["checking_vault"])
        await query.message.delete()
        dl_type = 'video'
        if fmt_type == 'aud': dl_type='audio'
        elif fmt_type == 'img': dl_type='images'
        elif fmt_type == 'sub': dl_type='subtitles'
        
        ckey = await get_canonical_key(url, chat_id, context.bot)
        cache = load_json_file(CACHE_FILE)
        if ckey in cache: 
            await cached_download_and_send(context.bot, chat_id, user_id, url, dl_type, t)
            return
        can_dl = await acquire_slot()
        if can_dl:
            try: await cached_download_and_send(context.bot, chat_id, user_id, url, dl_type, t)
            finally: await release_slot()
        else:
            pos = download_queue.qsize()+1
            await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, user_id, url, dl_type, t), 'kwargs': {}})
            free_mb = shutil.disk_usage(".").free // (1024*1024)
            await context.bot.send_message(chat_id=chat_id, text=t["server_busy"].format(active_downloads, MAX_CONCURRENT_SHORT, free_mb, pos), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if data == "admin_sim_ad" and user_id == ADMIN_ID:
        try:
            r = requests.get(f"{WEB_BASE_URL}/monetag-reward", params={"userid": user_id, "secret": API_SECRET}, timeout=8)
            ok = r.status_code == 200
        except Exception as e: logger.error(f"simulate ad: {e}"); ok = False
        await query.answer(t["simulated"] if ok else t["server_unreachable"], show_alert=True)
        return
    if data == "monetag_fallback":
        st = adsgram_status(user_id)
        if st.get("status") != "fallback_available": await query.answer(t["monetag_failed_twice"], show_alert=True); return
        bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
        tokens = load_tokens()
        tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
        save_tokens(tokens)
        await query.message.reply_text(t["monetag_fallback_prompt"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Open Adsterra Link", url=bridge_link)], [InlineKeyboardButton("✅ Check & Get +1", callback_data="verify_user")]]))
        await query.answer(t["adsterra_ready"], show_alert=True)
        return
    if data in ("monetag_check", "adsgram_check"):
        st = adsgram_status(user_id)
        if st.get("status") == "pending": await query.answer(t["finish_monetag"], show_alert=True); return
        if st.get("status") == "fallback_available": await query.answer(t["monetag_failed_use_adsterra"], show_alert=True); return
        if st.get("status") != "done": await query.answer(t["ad_link_expired"], show_alert=True); return
        reward = st.get("reward", 1)
        try: await query.message.delete()
        except: pass
        if st.get("kind") == "test":
            await query.answer(t["ad_verified_added"].format(reward), show_alert=True)
            await context.bot.send_message(chat_id=chat_id, text=t["test_ad_completed"].format(reward), reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            return
        await query.answer(t["sponsor_viewed"].format(reward), show_alert=True)
        paused = paused_batches.pop(user_id, None)
        if paused:
            asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
            return
        msg_start, msg_end = int(st.get("msg_start", 0)), int(st.get("msg_end", 0))
        if msg_start > 0:
            await context.bot.send_message(chat_id=chat_id, text=t["fetching_bundle"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            try: await deliver_bundle(context.bot, user_id, msg_start, msg_end)
            except Exception as e: await context.bot.send_message(chat_id=chat_id, text=f"❌ {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            return
        retry_url = pending_single_links.pop(f"retry_{user_id}", None)
        if retry_url:
            can_dl = await acquire_slot()
            if can_dl:
                try: await cached_download_and_send(context.bot, chat_id, user_id, retry_url, "video", t)
                finally: await release_slot()
            else:
                await download_queue.put({'func': cached_download_and_send, 'args': (context.bot, chat_id, user_id, retry_url, "video", t), 'kwargs': {}})
                await context.bot.send_message(chat_id=chat_id, text=t["queued"].format(download_queue.qsize()), reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            return
        await context.bot.send_message(chat_id=chat_id, text=t["refilled_send_again"].format(reward), reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if data.startswith("adsgram_complete_") or data in ("adsgram_resume_batch",): await query.answer(t["outdated_button"], show_alert=True); return
    if data == "stop_batch":
        active_batch_sessions[user_id]=False
        await query.answer(t["stopping"], show_alert=True)
        try: await query.edit_message_text(t["stopped"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        except: pass
        return
    if data == "resume_batch":
        paused = paused_batches.pop(user_id, None)
        if not paused: await query.answer(t["batch_expired"], show_alert=True); return
        await query.answer(t["resuming"])
        await query.message.delete()
        asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], paused["dl_type"], start_index=paused["next_index"]))
        return
    if data.startswith("dest_chat_") or data.startswith("dest_chan_"):
        parts = data.split("_",3); action_type, dl_type, payload_key = parts[1], parts[2], parts[3]
        urls = pending_batch_payloads.pop(payload_key, None)
        if not urls: await query.answer(t["batch_expired"], show_alert=True); return
        if action_type=="chat":
            await query.answer(t["batch_loading"])
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls, dl_type))
        else:
            user_channels = load_user_channels()
            target = user_channels.get(str(user_id))
            if not target:
                await query.answer(t["batch_no_channel"], show_alert=True)
                linking_states = load_linking_states()
                linking_states[str(user_id)]="waiting_for_channel"
                save_linking_states(linking_states)
                await query.message.edit_text(t["batch_setup_prompt"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
                return
            await query.answer(t["batch_loading"])
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, target, urls, dl_type))
        return
    if data == "change_channel":
        linking_states = load_linking_states()
        linking_states[str(user_id)]="waiting_for_channel"
        save_linking_states(linking_states)
        await query.answer(t["batch_mode_activated"])
        await query.message.reply_text(t["batch_change_dest"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if data == "verify_user":
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator","administrator","member"]: await query.answer(t["join_channel_first_alert"], show_alert=True); return
        except: await query.answer(t["join_channel_first"], show_alert=True); return
        tokens = load_tokens()
        user_str = str(user_id)
        if user_str not in tokens:
            if user_id != ADMIN_ID: await query.answer(t["watch_timer_first"], show_alert=True); return
            reward = get_reward_amount()
            tokens[user_str] = {"user_id": int(user_id), "downloads_left": reward, "batch_downloads_left": reward * 5, "last_reset": time.time(), "msg_start": 0, "msg_end": 0, "clicked_ad": True, "verified": True, "expires": time.time() + 600}
            save_tokens(tokens)
            await query.answer(t["test_ad_verified"], show_alert=True)
            await query.message.reply_text(t["test_ad_verified_msg"], parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            return
        token_data = tokens[user_str]
        if not token_data.get("verified", False): await query.answer(t["finish_timer_first"], show_alert=True); return
        msg_start, msg_end = token_data.get("msg_start",0), token_data.get("msg_end",0)
        reward = get_reward_amount()
        tokens[user_str]["downloads_left"] = reward
        tokens[user_str]["batch_downloads_left"] = reward * 5
        tokens[user_str]["verified"] = True
        tokens[user_str]["msg_start"] = 0
        tokens[user_str]["msg_end"] = 0
        save_tokens(tokens)
        await query.answer(t["verified_added"])
        if user_id in paused_batches:
            keyboard = [[InlineKeyboardButton("▶️ Resume Batch +1", callback_data="resume_batch")]]
            await query.message.reply_text(t["resume_prompt"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
        if msg_start==0: 
            await query.message.reply_text(t["refilled_download"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            return
        await query.message.reply_text(t["fetching_bundle"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        fwd_ids=[]
        try:
            for tid in range(msg_start, msg_end+1):
                try:
                    fwd = await context.bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=tid)
                    fwd_ids.append(fwd.message_id); await asyncio.sleep(0.2)
                except Exception as inner_e: logger.error(f"Forward {tid} fail: {inner_e}")
            await report_vault_delivery(user_id, msg_start, msg_end, fwd_ids)
            if TUTORIAL_MESSAGE_ID not in range(msg_start, msg_end+1):
                try:
                    tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    fwd_ids.append(tut.message_id)
                except Exception as tut_e: logger.error(f"Tutorial forward fail: {tut_e}")
            warn = await context.bot.send_message(chat_id=user_id, text="⏳ Auto-deletes in 9 mins", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            fwd_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, fwd_ids, 540))
        except Exception as e: await query.message.reply_text(f"❌ {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))

TEST_AD_TEXT = "🧪 AD PLACEMENT TEST\n\n1️⃣ User sends link\n2️⃣ User gets 4 FREE downloads\n3️⃣ LIMIT REACHED screen appears\n4️⃣ Tap Watch Ad\n5️⃣ Tap Check & Get +1\n\n👇 TRY THE AD NOW:"

async def send_adsgram_test(message, user_id):
    extra = [[InlineKeyboardButton("🛠 Admin: simulate ad finished", callback_data="admin_sim_ad")]] if user_id == ADMIN_ID else None
    kb = adsgram_keyboard(user_id, "test", 0, 0, extra)
    if not kb: await message.reply_text("⚠️ Ad server not reachable.", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)); return
    await message.reply_text(TEST_AD_TEXT, reply_markup=kb)

ADSTERRA_TEST_TEXT = "🧪 AD PLACEMENT TEST (Adsterra)\n\n1️⃣ User sends link\n2️⃣ LIMIT REACHED screen appears\n3️⃣ Stay 20s on ad page\n4️⃣ Tap Check & Get +1\n\n👇 TRY THE AD NOW:"

async def send_adsterra_test(message, user_id):
    tokens = load_tokens()
    uid = str(user_id)
    now = time.time()
    if uid in tokens and isinstance(tokens[uid], dict): tokens[uid].update({"msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": now + 600})
    else:
        free = get_free_amount()
        tokens[uid] = {"user_id": int(user_id), "downloads_left": free, "batch_downloads_left": free * 5, "last_reset": now, "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": now + 600}
    save_tokens(tokens)
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
    keyboard = [[InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1", url=bridge_link)], [InlineKeyboardButton("📢 Join Public Channel 💜", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")]]
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
    except Exception as e: await update.message.reply_text(f"❌ Could not reach server: {type(e).__name__}", reply_markup=get_main_keyboard("en", True)); return
    same = (s.get("fingerprint") == mine)
    lines = ["🔐 TOKEN CHECK", f"Render bot: fingerprint {mine}", f"PythonAnywhere: fingerprint {s.get('fingerprint')}", f"PA token works: {s.get('telegram_ok')}"]
    lines.append("✅ MATCH" if same else "❌ DIFFERENT")
    await update.message.reply_text("\n".join(lines), reply_markup=get_main_keyboard("en", True))

async def ad_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(build_ad_info_text(update.effective_user.id), reply_markup=get_main_keyboard("en", True))

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
        asyncio.create_task(restore_arcade_backup(app.bot)) 
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        print(f"Bot started! V25 Cloud Sync Vault={VIDEO_VAULT_ID} Backup={PRIVATE_CHANNEL_ID} Free {get_free_disk_mb()}MB")
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