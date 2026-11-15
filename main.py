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
try:
    import instaloader
except ImportError:
    instaloader = None
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== Carousel patch imports (STEP 1) =====
import sys
import subprocess
import concurrent.futures
from contextlib import ExitStack
# ===========================================

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
try:
    os.chmod(ffmpeg_path, 0o755)
except:
    pass

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ===== Deno on PATH (for yt-dlp YouTube support) =====
_DENO_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deno", "bin")
if os.path.isdir(_DENO_BIN):
    os.environ["PATH"] = _DENO_BIN + os.pathsep + os.environ.get("PATH", "")
    logger.info(f"Deno path added: {_DENO_BIN}, found={shutil.which('deno')}")
else:
    logger.warning("Deno folder .deno/bin not found: YouTube may fail")
# ======================================================

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

# ADDED arcade_backup.json HERE
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

# --- 100% COMPLETE 10-LANGUAGE DICTIONARY ---
LANGUAGES = {
    "en": {
        "welcome": "\U0001f680 **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER!**\n\n\U0001f525 WHAT I CAN DO:\n\U0001f3ac VIDEOS HD No Watermark!\n\U0001f3b5 AUDIO MP3 192kbps!\n\U0001f5bc\ufe0f IMAGES Scrape ALL!\n\U0001f4dd SUBTITLES Auto!\n\U0001f4e6 BATCH 100+ Links!\n\u26a1 CACHE 1 Sec!\n\U0001f48e VAULT Forever!\n\U0001f4e4 UPLOAD FILES!\n\U0001f517 FILE-TO-LINK: Create shareable links!\n\n\U0001f449 PASTE LINK TO START! \U0001f447",
        "btn_video": "\U0001f3ac Video (MP4)", "btn_audio": "\U0001f3b5 Audio (MP3)", "btn_image": "\U0001f5bc\ufe0f Images", "btn_sub": "\U0001f4dd Subtitles (SRT)",
        "ask_format": "\U0001f447 **AWESOME! What format you want? Pick below!**",
        "fetching": "\U0001f4e5 **Fetching your {}... Hang tight! \u23f3\u2728**",
        "error_generic": "\u274c Oops! Failed! \U0001f622 Link private/blocked. Try public link!",
        "error_50mb": "\u274c Too Big! \U0001f605 This video is over 300MB. Try a shorter one!", 
        "error_no_img": "\u274c No images found! \U0001f622 Try another link!",
        "images_received": "\u23f3 **{} Images received.**",
        "select_lang": "\U0001f30d Select your language! Choose below! \U0001f447", 
        "lang_set": "\u2705 Language set! Enjoy! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Batch Detected ({} links)**\nWhat format?",
        "batch_dest": "\U0001f4e6 **Where to send?**",
        "btn_chat": "\U0001f4e5 In Chat", "btn_chan": "\U0001f4e2 To Channel",
        "limit_reached": "\u26a0\ufe0f **Limit Reached!** You used 4 FREE! Watch 20s ad \u2192 Get +1 download!",
        "refill_btn": "\U0001f513 Open Link & Refill +1",
        "join_btn": "\U0001f4e2 Join Channel", "check_btn": "\U0001f49c Check Balance",
        "limit_batch": "\u26a0\ufe0f **Batch Limit Reached at {} of {}**\nWatch 20s ad \u2192 +1 download to continue.",
        "batch_start": "\U0001f4e6 **Batch Started:** {} **{} files**\n\u23f3 Processing...",
        "batch_done": "\U0001f3c1 **Done!** \u2705 {} \u274c {}\n\U0001f4e5 {} files here.",
        "batch_done_chan": "\U0001f3c1 **Done!** \u2705 {} \u274c {}\n\U0001f4e2 {} files forwarded!",
        "dl_video": "\U0001f4e5 Downloading video...", "dl_audio": "\U0001f4e5 Extracting audio...", "dl_image": "\U0001f4e5 Scraping images...", "dl_sub": "\U0001f4e5 Fetching subtitles...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Blocked/private", "failed_generic": "\u274c Failed",
        "menu_lang": "\U0001f30d Language", "menu_stats": "\U0001f4ca My Stats", "menu_help": "\U0001f4ac Support / FAQ", "menu_join": "\U0001f4e2 Join Channel",
        "menu_uploads": "\U0001f37f Fan Uploads", "menu_upload": "\U0001f4e4 Upload File",
        "admin_upload_prompt": "\U0001f4c2 **Fan Uploads Inbox**",
        "user_upload_prompt": "\U0001f4e4 **Upload File**\nSend video/image/file to Admin. Limit 5/24h.",
        "upload_success_user": "\u2705 Sent to Admin!",
        "upload_limit_reached": "\u26a0\ufe0f Upload limit 5/24h reached.",
        "no_uploads": "\U0001f4ed No uploads yet.",
        "stats_msg": "\U0001f4ca **Your Stats:**\n\u2022 Downloads Left: {}\n\u2022 Batch Left: {}",
        "change_channel_prompt": "\U0001f504 **Change Batch Channel**\n1. Make sure I am an admin in the new channel.\n2. Forward any message from that channel here.",
        "disk_config_prompt": "\U0001f4be **Disk Config**\nCurrent min free disk: **{}MB**\nTo change: `/setdisk <value>`",
        "mtproto_config_prompt": "\u26a1 **MTProto Config**\nCurrent max upload: **{}MB**\nTo change: `/setmtproto <value>`",
        "free_panel_prompt": "\U0001f4e6 FREE DOWNLOADS\nCurrent free per day: {}",
        "reward_panel_prompt": "\U0001f381 REWARD PANEL\nCurrent: +{} download per 20s ad",
        "ad_panel_prompt": "\u2699\ufe0f Ad Panel\nCurrent: {}",
        "password_saved": "\U0001f510 Password saved.",
        "password_too_long": "Password must be 64 chars or fewer.",
        "file_to_link_prompt": "\U0001f517 **File-to-Link**\nSend the file(s) you want to share.",
        "link_invalid_expired": "\u274c This link is invalid or expired.",
        "link_limit_reached": "\u26d4 This link reached its usage limit.",
        "link_password_protected": "\U0001f510 This link is password protected. Send the password.",
        "files_sent": "\u2705 Your files have been sent.",
        "file_added": "\U0001f4e5 Added file #{}. Send more, or tap Create Link.",
        "fl_cancelled": "File-to-Link cancelled",
        "fl_start_again": "Start File-to-Link again with /filetolink",
        "fl_choose_expiry": "Choose link expiry:",
        "fl_expiry_updated": "Expiry updated",
        "fl_choose_max_uses": "Choose max successful deliveries:",
        "fl_uses_updated": "Usage limit updated",
        "fl_set_password": "Send a password, or /clearpassword to remove.",
        "fl_link_created": "Link created",
        "fl_link_ready": "\U0001f517 Your link is ready:\n{}\nFiles: {}\nCost: 1 free daily download",
        "fl_daily_limit": "Daily free limit reached. Watch an ad to earn more.",
        "fl_ad_busy": "\u26a0\ufe0f Ad server busy.",
        "admin_skipped": "\u2705 Skipped!",
        "admin_bypassed": "\u2705 Bypassed",
        "free_set": "\u2705 Free set to {}!",
        "free_updated": "\u2705 Free Downloads updated to {}!",
        "reward_set": "\u2705 Reward set to +{}!",
        "reward_updated": "\u2705 Reward updated to +{}!",
        "mode_updated": "\u2705 Mode: {}",
        "support_opened": "\u270d\ufe0f Send message/photo/video/file below.",
        "admin_reply_mode": "\u270d\ufe0f Reply to {}:",
        "user_reply_mode": "\u270d\ufe0f Type follow-up below",
        "support_closed": "\U0001f512 Closed",
        "drop_cancelled": "\u274c Cancelled",
        "drop_no_items": "\u26a0\ufe0f No items!",
        "drop_timer_set": "{} set!",
        "drop_broadcasting": "\U0001f680 Broadcasting {} items to {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\nAuto-deletes in {}\nTap to claim:",
        "drop_done": "\u2705 Broadcast done to {}",
        "age_expired": "\u23f3 Expired!",
        "age_claimed": "\u274c Already claimed!",
        "age_verified": "Verified!",
        "age_denied": "\u274c Denied. Must be 18+",
        "lang_updated": "Updated!",
        "batch_expired": "Expired",
        "batch_loading": "Loading...",
        "batch_no_channel": "No channel linked!",
        "batch_setup_prompt": "\U0001f4e6 Setup: Make bot admin in channel and forward a message here",
        "batch_mode_activated": "Mode activated!",
        "batch_change_dest": "\U0001f504 **Change Destination Channel**\nMake bot admin in new channel, then forward a message here.",
        "join_channel_first_alert": "Join channel first! \U0001f4e2 Must join!",
        "join_channel_first": "Join channel first! \U0001f4e2",
        "watch_timer_first": "\u23f0 Open the link and watch the 20s timer first!",
        "test_ad_verified": "\u2705 Test Ad Verified! +1",
        "test_ad_verified_msg": "\u2705 **TEST AD VERIFIED!**\nReward: +1 download refilled!",
        "finish_timer_first": "\u23f0 Finish 20s timer first!",
        "verified_added": "Verified! +1 added",
        "resume_prompt": "\u2705 Verified! Refilled +1. Resume?",
        "refilled_download": "\u2705 Refilled +1! Download again.",
        "fetching_bundle": "\u2705 Verified! Fetching bundle...",
        "outdated_button": "This button is outdated. Send your link again.",
        "stopping": "Stopping...",
        "stopped": "\U0001f6d1 Stopped",
        "resuming": "Resuming...",
        "checking_vault": "Checking vault & server load...",
        "server_busy": "\u23f3 **Server Busy**\nActive: {}/{}\nFree: {}MB\nQueue: #{}\nWill start auto!",
        "simulated": "\U0001f6e0 Simulated! Now tap Check & Get +1",
        "server_unreachable": "\u274c Server unreachable",
        "monetag_failed_twice": "Complete two failed Monetag attempts first.",
        "monetag_fallback_prompt": "\U0001f310 Monetag failed twice. Continue with Adsterra:",
        "adsterra_ready": "Adsterra fallback ready",
        "finish_monetag": "\U0001f4fa Finish the Monetag ad in Mini App, then check again.",
        "monetag_failed_use_adsterra": "Monetag failed twice. Use Adsterra fallback below.",
        "ad_link_expired": "Ad link expired. Send your link again.",
        "ad_verified_added": "\u2705 Ad verified! +{} added",
        "test_ad_completed": "\u2705 TEST AD VERIFIED\nReward credited: +{} download.",
        "sponsor_viewed": "\u2705 Sponsor viewed! +{} added",
        "refilled_send_again": "\u2705 Refilled +{}! Send your link again.",
        "queued": "\u23f3 Queued #{}",
        "banned": "\U0001f6ab You are banned.",
        "no_links": "\u274c No links found.",
        "batch_count": "\U0001f4e6 Batch {} links",
        "restore_invalid_json": "\u274c Restore failed: **{}** is not valid JSON.",
        "restore_failed": "\u274c Restore failed: {}",
        "restore_success": "\u2705 **Restore Successful!**\nFile: **{}**\nRestored **{}** entries.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Send the new Welcome Message. Use `{bot_name}` for bot username.",
        "admin_welcome_updated": "\u2705 Welcome message updated!",
        "menu_edit_welcome": "\u270f\ufe0f Edit Welcome Msg",
        "cached_instant_video": "\u26a1 Cached Instant [{}] {} {}",
        "cached_instant_audio": "\u26a1 **Cached Instant** `{}`",
        "cached_instant_image": "\u26a1 **Cached Instant** `{}`",
        "auto_delete_9m": "\u23f3 Auto-deletes in 9 mins",
        "download_success": "\u2705 Download successful!"
    },
    "hi": {
        "welcome": "\U0001f680 **MICHAELBBC VAULT \u092e\u0947\u0902 \u0938\u094d\u0935\u093e\u0917\u0924 \u0939\u0948 - \u0911\u0932 \u092e\u0940\u0921\u093f\u092f\u093e \u0921\u093e\u0909\u0928\u0932\u094b\u0921\u0930!**\n\n\U0001f525 \u092e\u0948\u0902 \u0915\u094d\u092f\u093e \u0915\u0930 \u0938\u0915\u0924\u093e \u0939\u0942\u0901:\n\U0001f3ac \u0935\u0940\u0921\u093f\u092f\u094b HD \u0928\u094b \u0935\u0949\u091f\u0930\u092e\u093e\u0930\u094d\u0915!\n\U0001f3b5 \u0911\u0921\u093f\u092f\u094b MP3 192kbps!\n\U0001f5bc\ufe0f \u0907\u092e\u0947\u091c\u0947\u0938 \u0938\u094d\u0915\u094d\u0930\u0947\u092a ALL!\n\U0001f4dd \u0938\u092c\u091f\u093e\u0907\u091f\u0932\u094d\u0938 \u0911\u091f\u094b!\n\U0001f4e6 \u092c\u0948\u091a 100+ \u0932\u093f\u0902\u0915\u094d\u0938!\n\u26a1 \u0915\u0948\u0936 1 \u0938\u0947\u0915\u0902\u0921!\n\U0001f48e \u0935\u0949\u0932\u094d\u091f \u092b\u0949\u0930\u0947\u0935\u0930!\n\U0001f4e4 \u092b\u093e\u0907\u0932\u0947\u0902 \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902!\n\U0001f517 \u092b\u093e\u0907\u0932-\u091f\u0942-\u0932\u093f\u0902\u0915: \u0936\u0947\u092f\u0930 \u0932\u093f\u0902\u0915 \u092c\u0928\u093e\u090f\u0902!\n\n\U0001f449 \u0936\u0941\u0930\u0942 \u0915\u0930\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f \u0932\u093f\u0902\u0915 \u092a\u0947\u0938\u094d\u091f \u0915\u0930\u0947\u0902! \U0001f447",
        "btn_video": "\U0001f3ac \u0935\u0940\u0921\u093f\u092f\u094b (MP4)", "btn_audio": "\U0001f3b5 \u0911\u0921\u093f\u092f\u094b (MP3)", "btn_image": "\U0001f5bc\ufe0f \u0907\u092e\u0947\u091c\u0947\u0938", "btn_sub": "\U0001f4dd \u0938\u092c\u091f\u093e\u0907\u091f\u0932\u094d\u0938 (SRT)",
        "ask_format": "\U0001f447 **\u0936\u093e\u0928\u0926\u093e\u0930! \u0915\u094c\u0928 \u0938\u093e \u092b\u0949\u0930\u094d\u092e\u0947\u091f \u091a\u093e\u0939\u0924\u0947 \u0939\u0948\u0902? \u0928\u0940\u091a\u0947 \u091a\u0941\u0928\u0947\u0902!**",
        "fetching": "\U0001f4e5 **\u0906\u092a\u0915\u093e {} \u0932\u093e\u092f\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948... \u0930\u0941\u0915\u0947 \u0930\u0939\u0947\u0902! \u23f3\u2728**",
        "error_generic": "\u274c \u0913\u0939! \u0935\u093f\u092b\u0932! \U0001f622 \u0932\u093f\u0902\u0915 \u092a\u094d\u0930\u093e\u0907\u0935\u0947\u091f/\u092c\u094d\u0932\u0949\u0915 \u0939\u0948\u0964 \u092a\u092c\u094d\u0932\u093f\u0915 \u0932\u093f\u0902\u0915 \u0906\u091c\u093c\u092e\u093e\u090f\u0902!",
        "error_50mb": "\u274c \u092c\u0939\u0941\u0924 \u092c\u0921\u093c\u093e! \U0001f605 \u092f\u0939 \u0935\u0940\u0921\u093f\u092f\u094b 300MB \u0938\u0947 \u0905\u0927\u093f\u0915 \u0939\u0948\u0964 \u091b\u094b\u091f\u093e \u0935\u093e\u0932\u093e \u0906\u091c\u093c\u092e\u093e\u090f\u0902!", 
        "error_no_img": "\u274c \u0915\u094b\u0908 \u0907\u092e\u0947\u091c \u0928\u0939\u0940\u0902 \u092e\u093f\u0932\u0940! \U0001f622 \u0926\u0942\u0938\u0930\u093e \u0932\u093f\u0902\u0915 \u0906\u091c\u093c\u092e\u093e\u090f\u0902!",
        "images_received": "\u23f3 **{} \u0907\u092e\u0947\u091c\u0947\u0938 \u092a\u094d\u0930\u093e\u092a\u094d\u0924 \u0939\u0941\u0908\u0902\u0964**",
        "select_lang": "\U0001f30d \u0905\u092a\u0928\u0940 \u092d\u093e\u0937\u093e \u091a\u0941\u0928\u0947\u0902! \u0928\u0940\u091a\u0947 \u091a\u0941\u0928\u0947\u0902! \U0001f447", 
        "lang_set": "\u2705 \u092d\u093e\u0937\u093e \u0938\u0947\u091f \u0939\u094b \u0917\u0908! \u0906\u0928\u0902\u0926 \u0932\u0947\u0902! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **\u092c\u0948\u091a \u0921\u093f\u091f\u0947\u0915\u094d\u091f \u0939\u0941\u0906 ({} \u0932\u093f\u0902\u0915\u094d\u0938)**\n\u0915\u094c\u0928 \u0938\u093e \u092b\u0949\u0930\u094d\u092e\u0947\u091f?",
        "batch_dest": "\U0001f4e6 **\u0915\u0939\u093e\u0901 \u092d\u0947\u091c\u0947\u0902?**",
        "btn_chat": "\U0001f4e5 \u091a\u0948\u091f \u092e\u0947\u0902", "btn_chan": "\U0001f4e2 \u091a\u0948\u0928\u0932 \u092e\u0947\u0902",
        "limit_reached": "\u26a0\ufe0f **\u0932\u093f\u092e\u093f\u091f \u092a\u0942\u0930\u0940 \u0939\u094b \u0917\u0908!** \u0906\u092a\u0928\u0947 4 \u092b\u094d\u0930\u0940 \u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932 \u0915\u0930 \u0932\u093f\u090f! 20 \u0938\u0947\u0915\u0902\u0921 \u0915\u093e \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0926\u0947\u0916\u0947\u0902 \u2192 +1 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u092a\u093e\u090f\u0902!",
        "refill_btn": "\U0001f513 \u0932\u093f\u0902\u0915 \u0916\u094b\u0932\u0947\u0902 \u0914\u0930 +1 \u0930\u093f\u092b\u093f\u0932 \u0915\u0930\u0947\u0902",
        "join_btn": "\U0001f4e2 \u091a\u0948\u0928\u0932 \u091c\u0949\u0907\u0928 \u0915\u0930\u0947\u0902", "check_btn": "\U0001f49c \u092c\u0948\u0932\u0947\u0902\u0938 \u091a\u0947\u0915 \u0915\u0930\u0947\u0902",
        "limit_batch": "\u26a0\ufe0f **\u092c\u0948\u091a \u0932\u093f\u092e\u093f\u091f {} \u092e\u0947\u0902 \u0938\u0947 {} \u092a\u0930 \u092a\u0939\u0941\u0901\u091a \u0917\u0908**\n\u091c\u093e\u0930\u0940 \u0930\u0916\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f 20 \u0938\u0947\u0915\u0902\u0921 \u0915\u093e \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0926\u0947\u0916\u0947\u0902 \u2192 +1 \u0921\u093e\u0909\u0928\u0932\u094b\u0921\u0964",
        "batch_start": "\U0001f4e6 **\u092c\u0948\u091a \u0936\u0941\u0930\u0942:** {} **{} \u092b\u093e\u0907\u0932\u0947\u0902**\n\u23f3 \u092a\u094d\u0930\u094b\u0938\u0947\u0938\u093f\u0902\u0917...",
        "batch_done": "\U0001f3c1 **\u0939\u094b \u0917\u092f\u093e!** \u2705 {} \u274c {}\n\U0001f4e5 {} \u092b\u093e\u0907\u0932\u0947\u0902 \u092f\u0939\u093e\u0901 \u0939\u0948\u0902\u0964",
        "batch_done_chan": "\U0001f3c1 **\u0939\u094b \u0917\u092f\u093e!** \u2705 {} \u274c {}\n\U0001f4e2 {} \u092b\u093e\u0907\u0932\u0947\u0902 \u092b\u0949\u0930\u0935\u0930\u094d\u0921 \u0915\u0940 \u0917\u0908\u0902!",
        "dl_video": "\U0001f4e5 \u0935\u0940\u0921\u093f\u092f\u094b \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0939\u094b \u0930\u0939\u093e \u0939\u0948...", "dl_audio": "\U0001f4e5 \u0911\u0921\u093f\u092f\u094b \u0928\u093f\u0915\u093e\u0932\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948...", "dl_image": "\U0001f4e5 \u0907\u092e\u0947\u091c\u0947\u0938 \u0938\u094d\u0915\u094d\u0930\u0947\u092a \u0939\u094b \u0930\u0939\u0940 \u0939\u0948\u0902...", "dl_sub": "\U0001f4e5 \u0938\u092c\u091f\u093e\u0907\u091f\u0932\u094d\u0938 \u0932\u093e\u090f \u091c\u093e \u0930\u0939\u0947 \u0939\u0948\u0902...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c \u092c\u094d\u0932\u0949\u0915/\u092a\u094d\u0930\u093e\u0907\u0935\u0947\u091f", "failed_generic": "\u274c \u0935\u093f\u092b\u0932",
        "menu_lang": "\U0001f30d \u092d\u093e\u0937\u093e", "menu_stats": "\U0001f4ca \u092e\u0947\u0930\u0947 \u0906\u0902\u0915\u0921\u093c\u0947", "menu_help": "\U0001f4ac \u0938\u092a\u094b\u0930\u094d\u091f / FAQ", "menu_join": "\U0001f4e2 \u091a\u0948\u0928\u0932 \u091c\u0949\u0907\u0928 \u0915\u0930\u0947\u0902",
        "menu_uploads": "\U0001f37f \u092b\u0948\u0928 \u0905\u092a\u0932\u094b\u0921\u094d\u0938", "menu_upload": "\U0001f4e4 \u092b\u093e\u0907\u0932 \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902",
        "admin_upload_prompt": "\U0001f4c2 **\u092b\u0948\u0928 \u0905\u092a\u0932\u094b\u0921\u094d\u0938 \u0907\u0928\u092c\u0949\u0915\u094d\u0938**",
        "user_upload_prompt": "\U0001f4e4 **\u092b\u093e\u0907\u0932 \u0905\u092a\u0932\u094b\u0921 \u0915\u0930\u0947\u0902**\n\u090f\u0921\u092e\u093f\u0928 \u0915\u094b \u0935\u0940\u0921\u093f\u092f\u094b/\u0907\u092e\u0947\u091c/\u092b\u093e\u0907\u0932 \u092d\u0947\u091c\u0947\u0902\u0964 \u0932\u093f\u092e\u093f\u091f 5/24\u0918\u0902\u091f\u0947\u0964",
        "upload_success_user": "\u2705 \u090f\u0921\u092e\u093f\u0928 \u0915\u094b \u092d\u0947\u091c \u0926\u093f\u092f\u093e \u0917\u092f\u093e!",
        "upload_limit_reached": "\u26a0\ufe0f \u0905\u092a\u0932\u094b\u0921 \u0932\u093f\u092e\u093f\u091f 5/24\u0918\u0902\u091f\u0947 \u092a\u0942\u0930\u0940 \u0939\u094b \u0917\u0908\u0964",
        "no_uploads": "\U0001f4ed \u0905\u092d\u0940 \u0924\u0915 \u0915\u094b\u0908 \u0905\u092a\u0932\u094b\u0921 \u0928\u0939\u0940\u0902\u0964",
        "stats_msg": "\U0001f4ca **\u0906\u092a\u0915\u0947 \u0906\u0902\u0915\u0921\u093c\u0947:**\n\u2022 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u092c\u091a\u0947: {}\n\u2022 \u092c\u0948\u091a \u092c\u091a\u0947: {}",
        "change_channel_prompt": "\U0001f504 **\u092c\u0948\u091a \u091a\u0948\u0928\u0932 \u092c\u0926\u0932\u0947\u0902**\n1. \u0938\u0941\u0928\u093f\u0936\u094d\u091a\u093f\u0924 \u0915\u0930\u0947\u0902 \u0915\u093f \u092e\u0948\u0902 \u0928\u090f \u091a\u0948\u0928\u0932 \u092e\u0947\u0902 \u090f\u0921\u092e\u093f\u0928 \u0939\u0942\u0901\u0964\n2. \u0909\u0938 \u091a\u0948\u0928\u0932 \u0938\u0947 \u0915\u094b\u0908 \u092d\u0940 \u092e\u0948\u0938\u0947\u091c \u092f\u0939\u093e\u0901 \u092b\u0949\u0930\u0935\u0930\u094d\u0921 \u0915\u0930\u0947\u0902\u0964",
        "disk_config_prompt": "\U0001f4be **\u0921\u093f\u0938\u094d\u0915 \u0915\u0949\u0928\u094d\u092b\u093c\u093f\u0917\u0930\u0947\u0936\u0928**\n\u0935\u0930\u094d\u0924\u092e\u093e\u0928 \u0928\u094d\u092f\u0942\u0928\u0924\u092e \u092b\u094d\u0930\u0940 \u0921\u093f\u0938\u094d\u0915: **{}MB**\n\u092c\u0926\u0932\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f: `/setdisk <value>`",
        "mtproto_config_prompt": "\u26a1 **MTProto \u0915\u0949\u0928\u094d\u092b\u093c\u093f\u0917\u0930\u0947\u0936\u0928**\n\u0935\u0930\u094d\u0924\u092e\u093e\u0928 \u0905\u0927\u093f\u0915\u0924\u092e \u0905\u092a\u0932\u094b\u0921: **{}MB**\n\u092c\u0926\u0932\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f: `/setmtproto <value>`",
        "free_panel_prompt": "\U0001f4e6 \u092b\u094d\u0930\u0940 \u0921\u093e\u0909\u0928\u0932\u094b\u0921\u094d\u0938\n\u0935\u0930\u094d\u0924\u092e\u093e\u0928 \u092b\u094d\u0930\u0940 \u092a\u094d\u0930\u0924\u093f \u0926\u093f\u0928: {}",
        "reward_panel_prompt": "\U0001f381 \u0930\u093f\u0935\u0949\u0930\u094d\u0921 \u092a\u0948\u0928\u0932\n\u0935\u0930\u094d\u0924\u092e\u093e\u0928: +{} \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u092a\u094d\u0930\u0924\u093f 20 \u0938\u0947\u0915\u0902\u0921 \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928",
        "ad_panel_prompt": "\u2699\ufe0f \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u092a\u0948\u0928\u0932\n\u0935\u0930\u094d\u0924\u092e\u093e\u0928: {}",
        "password_saved": "\U0001f510 \u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0938\u0947\u0935 \u0939\u094b \u0917\u092f\u093e\u0964",
        "password_too_long": "\u092a\u093e\u0938\u0935\u0930\u094d\u0921 64 \u0905\u0915\u094d\u0937\u0930\u094b\u0902 \u0938\u0947 \u0915\u092e \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f\u0964",
        "file_to_link_prompt": "\U0001f517 **\u092b\u093e\u0907\u0932-\u091f\u0942-\u0932\u093f\u0902\u0915**\n\u0935\u0939 \u092b\u093e\u0907\u0932(\u0947\u0902) \u092d\u0947\u091c\u0947\u0902 \u091c\u093f\u0928\u094d\u0939\u0947\u0902 \u0906\u092a \u0936\u0947\u092f\u0930 \u0915\u0930\u0928\u093e \u091a\u093e\u0939\u0924\u0947 \u0939\u0948\u0902\u0964",
        "link_invalid_expired": "\u274c \u092f\u0939 \u0932\u093f\u0902\u0915 \u0905\u092e\u093e\u0928\u094d\u092f \u0939\u0948 \u092f\u093e \u0938\u092e\u093e\u092a\u094d\u0924 \u0939\u094b \u0917\u092f\u093e \u0939\u0948\u0964",
        "link_limit_reached": "\u26d4 \u0907\u0938 \u0932\u093f\u0902\u0915 \u0928\u0947 \u0905\u092a\u0928\u0940 \u0909\u092a\u092f\u094b\u0917 \u0938\u0940\u092e\u093e \u092a\u093e\u0930 \u0915\u0930 \u0932\u0940 \u0939\u0948\u0964",
        "link_password_protected": "\U0001f510 \u092f\u0939 \u0932\u093f\u0902\u0915 \u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u0938\u0947 \u0938\u0941\u0930\u0915\u094d\u0937\u093f\u0924 \u0939\u0948\u0964 \u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u092d\u0947\u091c\u0947\u0902\u0964",
        "files_sent": "\u2705 \u0906\u092a\u0915\u0940 \u092b\u093e\u0907\u0932\u0947\u0902 \u092d\u0947\u091c \u0926\u0940 \u0917\u0908 \u0939\u0948\u0902\u0964",
        "file_added": "\U0001f4e5 \u092b\u093e\u0907\u0932 #{} \u091c\u094b\u0921\u093c\u0940 \u0917\u0908\u0964 \u0914\u0930 \u092d\u0947\u091c\u0947\u0902, \u092f\u093e 'Create Link' \u091f\u0948\u092a \u0915\u0930\u0947\u0902\u0964",
        "fl_cancelled": "\u092b\u093e\u0907\u0932-\u091f\u0942-\u0932\u093f\u0902\u0915 \u0930\u0926\u094d\u0926 \u0915\u093f\u092f\u093e \u0917\u092f\u093e",
        "fl_start_again": "/filetolink \u0915\u0947 \u0938\u093e\u0925 \u092b\u093f\u0930 \u0938\u0947 \u0936\u0941\u0930\u0942 \u0915\u0930\u0947\u0902",
        "fl_choose_expiry": "\u0932\u093f\u0902\u0915 \u0938\u092e\u093e\u092a\u094d\u0924\u093f \u091a\u0941\u0928\u0947\u0902:",
        "fl_expiry_updated": "\u0938\u092e\u093e\u092a\u094d\u0924\u093f \u0905\u092a\u0921\u0947\u091f \u0939\u094b \u0917\u0908",
        "fl_choose_max_uses": "\u0905\u0927\u093f\u0915\u0924\u092e \u0938\u092b\u0932 \u0921\u093f\u0932\u0940\u0935\u0930\u0940 \u091a\u0941\u0928\u0947\u0902:",
        "fl_uses_updated": "\u0909\u092a\u092f\u094b\u0917 \u0938\u0940\u092e\u093e \u0905\u092a\u0921\u0947\u091f \u0939\u094b \u0917\u0908",
        "fl_set_password": "\u092a\u093e\u0938\u0935\u0930\u094d\u0921 \u092d\u0947\u091c\u0947\u0902, \u092f\u093e \u0939\u091f\u093e\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f /clearpassword \u092d\u0947\u091c\u0947\u0902\u0964",
        "fl_link_created": "\u0932\u093f\u0902\u0915 \u092c\u0928\u093e\u092f\u093e \u0917\u092f\u093e",
        "fl_link_ready": "\U0001f517 \u0906\u092a\u0915\u093e \u0932\u093f\u0902\u0915 \u0924\u0948\u092f\u093e\u0930 \u0939\u0948:\n{}\n\u092b\u093e\u0907\u0932\u0947\u0902: {}\n\u0932\u093e\u0917\u0924: 1 \u092b\u094d\u0930\u0940 \u0926\u0948\u0928\u093f\u0915 \u0921\u093e\u0909\u0928\u0932\u094b\u0921",
        "fl_daily_limit": "\u0926\u0948\u0928\u093f\u0915 \u092b\u094d\u0930\u0940 \u0932\u093f\u092e\u093f\u091f \u092a\u0942\u0930\u0940 \u0939\u094b \u0917\u0908\u0964 \u0905\u0927\u093f\u0915 \u0915\u092e\u093e\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0926\u0947\u0916\u0947\u0902\u0964",
        "fl_ad_busy": "\u26a0\ufe0f \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0938\u0930\u094d\u0935\u0930 \u0935\u094d\u092f\u0938\u094d\u0924 \u0939\u0948\u0964",
        "admin_skipped": "\u2705 \u091b\u094b\u0921\u093c \u0926\u093f\u092f\u093e \u0917\u092f\u093e!",
        "admin_bypassed": "\u2705 \u092c\u093e\u092f\u092a\u093e\u0938 \u0915\u093f\u092f\u093e \u0917\u092f\u093e",
        "free_set": "\u2705 \u092b\u094d\u0930\u0940 {} \u092a\u0930 \u0938\u0947\u091f \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "free_updated": "\u2705 \u092b\u094d\u0930\u0940 \u0921\u093e\u0909\u0928\u0932\u094b\u0921\u094d\u0938 {} \u092a\u0930 \u0905\u092a\u0921\u0947\u091f \u0915\u093f\u090f \u0917\u090f!",
        "reward_set": "\u2705 \u0930\u093f\u0935\u0949\u0930\u094d\u0921 +{} \u092a\u0930 \u0938\u0947\u091f \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "reward_updated": "\u2705 \u0930\u093f\u0935\u0949\u0930\u094d\u0921 +{} \u092a\u0930 \u0905\u092a\u0921\u0947\u091f \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "mode_updated": "\u2705 \u092e\u094b\u0921: {}",
        "support_opened": "\u270d\ufe0f \u0928\u0940\u091a\u0947 \u092e\u0948\u0938\u0947\u091c/\u092b\u094b\u091f\u094b/\u0935\u0940\u0921\u093f\u092f\u094b/\u092b\u093e\u0907\u0932 \u092d\u0947\u091c\u0947\u0902\u0964",
        "admin_reply_mode": "\u270d\ufe0f {} \u0915\u094b \u0930\u093f\u092a\u094d\u0932\u093e\u0908 \u0915\u0930\u0947\u0902:",
        "user_reply_mode": "\u270d\ufe0f \u0928\u0940\u091a\u0947 \u092b\u0949\u0932\u094b-\u0905\u092a \u091f\u093e\u0907\u092a \u0915\u0930\u0947\u0902",
        "support_closed": "\U0001f512 \u092c\u0902\u0926 \u0915\u093f\u092f\u093e \u0917\u092f\u093e",
        "drop_cancelled": "\u274c \u0930\u0926\u094d\u0926 \u0915\u093f\u092f\u093e \u0917\u092f\u093e",
        "drop_no_items": "\u26a0\ufe0f \u0915\u094b\u0908 \u0906\u0907\u091f\u092e \u0928\u0939\u0940\u0902!",
        "drop_timer_set": "{} \u0938\u0947\u091f \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "drop_broadcasting": "\U0001f680 {} \u0906\u0907\u091f\u092e {} \u0915\u094b \u092c\u094d\u0930\u0949\u0921\u0915\u093e\u0938\u094d\u091f \u0915\u093f\u092f\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948...",
        "drop_flash_text": "\U0001f6a8 \u092b\u094d\u0932\u0948\u0936 \u0921\u094d\u0930\u0949\u092a!\n{} \u092e\u0947\u0902 \u0911\u091f\u094b-\u0921\u093f\u0932\u0940\u091f \u0939\u094b\u0917\u093e\n\u0915\u094d\u0932\u0947\u092e \u0915\u0930\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f \u091f\u0948\u092a \u0915\u0930\u0947\u0902:",
        "drop_done": "\u2705 {} \u0915\u094b \u092c\u094d\u0930\u0949\u0921\u0915\u093e\u0938\u094d\u091f \u0939\u094b \u0917\u092f\u093e",
        "age_expired": "\u23f3 \u0938\u092e\u093e\u092a\u094d\u0924 \u0939\u094b \u0917\u092f\u093e!",
        "age_claimed": "\u274c \u092a\u0939\u0932\u0947 \u0939\u0940 \u0915\u094d\u0932\u0947\u092e \u0915\u093f\u092f\u093e \u091c\u093e \u091a\u0941\u0915\u093e \u0939\u0948!",
        "age_verified": "\u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924!",
        "age_denied": "\u274c \u0905\u0938\u094d\u0935\u0940\u0915\u0943\u0924\u0964 18+ \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f",
        "lang_updated": "\u0905\u092a\u0921\u0947\u091f \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "batch_expired": "\u0938\u092e\u093e\u092a\u094d\u0924 \u0939\u094b \u0917\u092f\u093e",
        "batch_loading": "\u0932\u094b\u0921 \u0939\u094b \u0930\u0939\u093e \u0939\u0948...",
        "batch_no_channel": "\u0915\u094b\u0908 \u091a\u0948\u0928\u0932 \u0932\u093f\u0902\u0915 \u0928\u0939\u0940\u0902 \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "batch_setup_prompt": "\U0001f4e6 \u0938\u0947\u091f\u0905\u092a: \u091a\u0948\u0928\u0932 \u092e\u0947\u0902 \u092c\u0949\u091f \u0915\u094b \u090f\u0921\u092e\u093f\u0928 \u092c\u0928\u093e\u090f\u0902 \u0914\u0930 \u092f\u0939\u093e\u0901 \u090f\u0915 \u092e\u0948\u0938\u0947\u091c \u092b\u0949\u0930\u0935\u0930\u094d\u0921 \u0915\u0930\u0947\u0902",
        "batch_mode_activated": "\u092e\u094b\u0921 \u0938\u0915\u094d\u0930\u093f\u092f \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "batch_change_dest": "\U0001f504 **\u0921\u0947\u0938\u094d\u091f\u093f\u0928\u0947\u0936\u0928 \u091a\u0948\u0928\u0932 \u092c\u0926\u0932\u0947\u0902**\n\u0928\u090f \u091a\u0948\u0928\u0932 \u092e\u0947\u0902 \u092c\u0949\u091f \u0915\u094b \u090f\u0921\u092e\u093f\u0928 \u092c\u0928\u093e\u090f\u0902, \u092b\u093f\u0930 \u092f\u0939\u093e\u0901 \u092e\u0948\u0938\u0947\u091c \u092b\u0949\u0930\u0935\u0930\u094d\u0921 \u0915\u0930\u0947\u0902\u0964",
        "join_channel_first_alert": "\u092a\u0939\u0932\u0947 \u091a\u0948\u0928\u0932 \u091c\u0949\u0907\u0928 \u0915\u0930\u0947\u0902! \U0001f4e2 \u091c\u0949\u0907\u0928 \u0915\u0930\u0928\u093e \u0906\u0935\u0936\u094d\u092f\u0915 \u0939\u0948!",
        "join_channel_first": "\u092a\u0939\u0932\u0947 \u091a\u0948\u0928\u0932 \u091c\u0949\u0907\u0928 \u0915\u0930\u0947\u0902! \U0001f4e2",
        "watch_timer_first": "\u23f0 \u092a\u0939\u0932\u0947 \u0932\u093f\u0902\u0915 \u0916\u094b\u0932\u0947\u0902 \u0914\u0930 20 \u0938\u0947\u0915\u0902\u0921 \u0915\u093e \u091f\u093e\u0907\u092e\u0930 \u0926\u0947\u0916\u0947\u0902!",
        "test_ad_verified": "\u2705 \u091f\u0947\u0938\u094d\u091f \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924! +1",
        "test_ad_verified_msg": "\u2705 **\u091f\u0947\u0938\u094d\u091f \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924!**\n\u0930\u093f\u0935\u0949\u0930\u094d\u0921: +1 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0930\u093f\u092b\u093f\u0932 \u0915\u093f\u092f\u093e \u0917\u092f\u093e!",
        "finish_timer_first": "\u23f0 \u092a\u0939\u0932\u0947 20 \u0938\u0947\u0915\u0902\u0921 \u0915\u093e \u091f\u093e\u0907\u092e\u0930 \u092a\u0942\u0930\u093e \u0915\u0930\u0947\u0902!",
        "verified_added": "\u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924! +1 \u091c\u094b\u0921\u093c\u093e \u0917\u092f\u093e",
        "resume_prompt": "\u2705 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924! +1 \u0930\u093f\u092b\u093f\u0932 \u0915\u093f\u092f\u093e \u0917\u092f\u093e\u0964 \u092b\u093f\u0930 \u0938\u0947 \u0936\u0941\u0930\u0942 \u0915\u0930\u0947\u0902?",
        "refilled_download": "\u2705 +1 \u0930\u093f\u092b\u093f\u0932 \u0915\u093f\u092f\u093e \u0917\u092f\u093e! \u092b\u093f\u0930 \u0938\u0947 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0915\u0930\u0947\u0902\u0964",
        "fetching_bundle": "\u2705 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924! \u092c\u0902\u0921\u0932 \u0932\u093e\u092f\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948...",
        "outdated_button": "\u092f\u0939 \u092c\u091f\u0928 \u092a\u0941\u0930\u093e\u0928\u093e \u0939\u0948\u0964 \u0905\u092a\u0928\u093e \u0932\u093f\u0902\u0915 \u092b\u093f\u0930 \u0938\u0947 \u092d\u0947\u091c\u0947\u0902\u0964",
        "stopping": "\u0930\u094b\u0915\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948...",
        "stopped": "\U0001f6d1 \u0930\u0941\u0915 \u0917\u092f\u093e",
        "resuming": "\u092b\u093f\u0930 \u0938\u0947 \u0936\u0941\u0930\u0942 \u0939\u094b \u0930\u0939\u093e \u0939\u0948...",
        "checking_vault": "\u0935\u0949\u0932\u094d\u091f \u0914\u0930 \u0938\u0930\u094d\u0935\u0930 \u0932\u094b\u0921 \u091a\u0947\u0915 \u0915\u093f\u092f\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948...",
        "server_busy": "\u23f3 **\u0938\u0930\u094d\u0935\u0930 \u0935\u094d\u092f\u0938\u094d\u0924 \u0939\u0948**\n\u0938\u0915\u094d\u0930\u093f\u092f: {}/{}\n\u092b\u094d\u0930\u0940: {}MB\n\u0915\u0924\u093e\u0930: #{}\n\u0911\u091f\u094b \u0936\u0941\u0930\u0942 \u0939\u094b\u0917\u093e!",
        "simulated": "\U0001f6e0 \u0938\u093f\u092e\u094d\u092f\u0941\u0932\u0947\u091f \u0915\u093f\u092f\u093e \u0917\u092f\u093e! \u0905\u092c \u091a\u0947\u0915 \u0915\u0930\u0947\u0902 \u0914\u0930 +1 \u092a\u094d\u0930\u093e\u092a\u094d\u0924 \u0915\u0930\u0947\u0902",
        "server_unreachable": "\u274c \u0938\u0930\u094d\u0935\u0930 \u092a\u0939\u0941\u0901\u091a \u0938\u0947 \u092c\u093e\u0939\u0930 \u0939\u0948",
        "monetag_failed_twice": "\u092a\u0939\u0932\u0947 \u0926\u094b \u0935\u093f\u092b\u0932 Monetag \u092a\u094d\u0930\u092f\u093e\u0938 \u092a\u0942\u0930\u0947 \u0915\u0930\u0947\u0902\u0964",
        "monetag_fallback_prompt": "\U0001f310 Monetag \u0926\u094b \u092c\u093e\u0930 \u0935\u093f\u092b\u0932 \u0930\u0939\u093e\u0964 Adsterra \u0915\u0947 \u0938\u093e\u0925 \u091c\u093e\u0930\u0940 \u0930\u0916\u0947\u0902:",
        "adsterra_ready": "Adsterra \u092b\u0949\u0932\u092c\u0948\u0915 \u0924\u0948\u092f\u093e\u0930 \u0939\u0948",
        "finish_monetag": "\U0001f4fa Mini App \u092e\u0947\u0902 Monetag \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u092a\u0942\u0930\u093e \u0915\u0930\u0947\u0902, \u092b\u093f\u0930 \u091a\u0947\u0915 \u0915\u0930\u0947\u0902\u0964",
        "monetag_failed_use_adsterra": "Monetag \u0926\u094b \u092c\u093e\u0930 \u0935\u093f\u092b\u0932 \u0930\u0939\u093e\u0964 \u0928\u0940\u091a\u0947 \u0926\u093f\u090f \u0917\u090f Adsterra \u092b\u0949\u0932\u092c\u0948\u0915 \u0915\u093e \u0909\u092a\u092f\u094b\u0917 \u0915\u0930\u0947\u0902\u0964",
        "ad_link_expired": "\u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0932\u093f\u0902\u0915 \u0938\u092e\u093e\u092a\u094d\u0924 \u0939\u094b \u0917\u092f\u093e \u0939\u0948\u0964 \u0905\u092a\u0928\u093e \u0932\u093f\u0902\u0915 \u092b\u093f\u0930 \u0938\u0947 \u092d\u0947\u091c\u0947\u0902\u0964",
        "ad_verified_added": "\u2705 \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924! +{} \u091c\u094b\u0921\u093c\u093e \u0917\u092f\u093e",
        "test_ad_completed": "\u2705 \u091f\u0947\u0938\u094d\u091f \u0935\u093f\u091c\u094d\u091e\u093e\u092a\u0928 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924\n\u0930\u093f\u0935\u0949\u0930\u094d\u0921 \u091c\u092e\u093e \u0915\u093f\u092f\u093e \u0917\u092f\u093e: +{} \u0921\u093e\u0909\u0928\u0932\u094b\u0921\u0964",
        "sponsor_viewed": "\u2705 \u0938\u094d\u092a\u0949\u0928\u094d\u0938\u0930 \u0926\u0947\u0916\u093e \u0917\u092f\u093e! +{} \u091c\u094b\u0921\u093c\u093e \u0917\u092f\u093e",
        "refilled_send_again": "\u2705 +{} \u0930\u093f\u092b\u093f\u0932 \u0915\u093f\u092f\u093e \u0917\u092f\u093e! \u0905\u092a\u0928\u093e \u0932\u093f\u0902\u0915 \u092b\u093f\u0930 \u0938\u0947 \u092d\u0947\u091c\u0947\u0902\u0964",
        "queued": "\u23f3 \u0915\u0924\u093e\u0930 #{}",
        "banned": "\U0001f6ab \u0906\u092a \u092c\u0948\u0928 \u0915\u0930 \u0926\u093f\u090f \u0917\u090f \u0939\u0948\u0902\u0964",
        "no_links": "\u274c \u0915\u094b\u0908 \u0932\u093f\u0902\u0915 \u0928\u0939\u0940\u0902 \u092e\u093f\u0932\u093e\u0964",
        "batch_count": "\U0001f4e6 \u092c\u0948\u091a {} \u0932\u093f\u0902\u0915\u094d\u0938",
        "restore_invalid_json": "\u274c \u0930\u093f\u0938\u094d\u091f\u094b\u0930 \u0935\u093f\u092b\u0932: **{}** \u092e\u093e\u0928\u094d\u092f JSON \u0928\u0939\u0940\u0902 \u0939\u0948\u0964",
        "restore_failed": "\u274c \u0930\u093f\u0938\u094d\u091f\u094b\u0930 \u0935\u093f\u092b\u0932: {}",
        "restore_success": "\u2705 **\u0930\u093f\u0938\u094d\u091f\u094b\u0930 \u0938\u092b\u0932!**\n\u092b\u093e\u0907\u0932: **{}**\n**{}** \u090f\u0902\u091f\u094d\u0930\u0940\u091c \u0930\u093f\u0938\u094d\u091f\u094b\u0930 \u0915\u0940 \u0917\u0908\u0902\u0964",
        "admin_edit_welcome_prompt": "\u270f\ufe0f \u0928\u092f\u093e \u0935\u0947\u0932\u0915\u092e \u092e\u0948\u0938\u0947\u091c \u092d\u0947\u091c\u0947\u0902\u0964 \u092c\u0949\u091f \u092f\u0942\u091c\u0930\u0928\u0947\u092e \u0915\u0947 \u0932\u093f\u090f `{bot_name}` \u0915\u093e \u0909\u092a\u092f\u094b\u0917 \u0915\u0930\u0947\u0902\u0964",
        "admin_welcome_updated": "\u2705 \u0935\u0947\u0932\u0915\u092e \u092e\u0948\u0938\u0947\u091c \u0905\u092a\u0921\u0947\u091f \u0939\u094b \u0917\u092f\u093e!",
        "menu_edit_welcome": "\u270f\ufe0f \u0935\u0947\u0932\u0915\u092e \u092e\u0948\u0938\u0947\u091c \u090f\u0921\u093f\u091f \u0915\u0930\u0947\u0902",
        "cached_instant_video": "\u26a1 \u0915\u0948\u0936 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0924\u093e\u0924\u094d\u0915\u093e\u0932\u093f\u0915 [{}] {} {}",
        "cached_instant_audio": "\u26a1 **\u0915\u0948\u0936 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0924\u093e\u0924\u094d\u0915\u093e\u0932\u093f\u0915** `{}`",
        "cached_instant_image": "\u26a1 **\u0915\u0948\u0936 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0924\u093e\u0924\u094d\u0915\u093e\u0932\u093f\u0915** `{}`",
        "auto_delete_9m": "\u23f3 9 \u092e\u093f\u0928\u091f \u092e\u0947\u0902 \u0911\u091f\u094b-\u0921\u093f\u0932\u0940\u091f",
        "download_success": "\u2705 \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0938\u092b\u0932!"
    },
    "es": {
        "welcome": "\U0001f680 **BIENVENIDO A MICHAELBBC VAULT - DESCARGADOR DE MEDIOS!**\n\n\U0001f525 QU\u00c9 PUEDO HACER:\n\U0001f3ac VIDEOS HD Sin Marca de Agua!\n\U0001f3b5 AUDIO MP3 192kbps!\n\U0001f5bc\ufe0f IM\u00c1GENES Scraping TOTAL!\n\U0001f4dd SUBT\u00cdTULOS Auto!\n\U0001f4e6 LOTES 100+ Enlaces!\n\u26a1 CACHE 1 Seg!\n\U0001f48e VAULT Para Siempre!\n\U0001f4e4 SUBIR ARCHIVOS!\n\U0001f517 ARCHIVO-A-ENLACE: Crea enlaces compartibles!\n\n\U0001f449 PEGA UN ENLACE PARA EMPEZAR! \U0001f447",
        "btn_video": "\U0001f3ac Video (MP4)", "btn_audio": "\U0001f3b5 Audio (MP3)", "btn_image": "\U0001f5bc\ufe0f Im\u00e1genes", "btn_sub": "\U0001f4dd Subt\u00edtulos (SRT)",
        "ask_format": "\U0001f447 **GENIAL! \u00bfQu\u00e9 formato quieres? Elige abajo!**",
        "fetching": "\U0001f4e5 **Obteniendo tu {}... Espera un momento! \u23f3\u2728**",
        "error_generic": "\u274c Ups! Fall\u00f3! \U0001f622 Enlace privado/bloqueado. Prueba un enlace p\u00fablico!",
        "error_50mb": "\u274c Demasiado grande! \U0001f605 Este video supera los 300MB. Prueba uno m\u00e1s corto!", 
        "error_no_img": "\u274c No se encontraron im\u00e1genes! \U0001f622 Prueba otro enlace!",
        "images_received": "\u23f3 **{} Im\u00e1genes recibidas.**",
        "select_lang": "\U0001f30d Selecciona tu idioma! Elige abajo! \U0001f447", 
        "lang_set": "\u2705 Idioma configurado! Disfruta! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Lote Detectado ({} enlaces)**\n\u00bfQu\u00e9 formato?",
        "batch_dest": "\U0001f4e6 **D\u00f3nde enviar?**",
        "btn_chat": "\U0001f4e5 En Chat", "btn_chan": "\U0001f4e2 Al Canal",
        "limit_reached": "\u26a0\ufe0f **L\u00edmite Alcanzado!** Usaste 4 GRATIS! Mira un anuncio de 20s \u2192 Obt\u00e9n +1 descarga!",
        "refill_btn": "\U0001f513 Abrir Enlace y Recargar +1",
        "join_btn": "\U0001f4e2 Unirse al Canal", "check_btn": "\U0001f49c Verificar Saldo",
        "limit_batch": "\u26a0\ufe0f **L\u00edmite de Lote Alcanzado en {} de {}**\nMira un anuncio de 20s \u2192 +1 descarga para continuar.",
        "batch_start": "\U0001f4e6 **Lote Iniciado:** {} **{} archivos**\n\u23f3 Procesando...",
        "batch_done": "\U0001f3c1 **Listo!** \u2705 {} \u274c {}\n\U0001f4e5 {} archivos aqu\u00ed.",
        "batch_done_chan": "\U0001f3c1 **Listo!** \u2705 {} \u274c {}\n\U0001f4e2 {} archivos reenviados!",
        "dl_video": "\U0001f4e5 Descargando video...", "dl_audio": "\U0001f4e5 Extrayendo audio...", "dl_image": "\U0001f4e5 Obteniendo im\u00e1genes...", "dl_sub": "\U0001f4e5 Obteniendo subt\u00edtulos...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Bloqueado/privado", "failed_generic": "\u274c Fall\u00f3",
        "menu_lang": "\U0001f30d Idioma", "menu_stats": "\U0001f4ca Mis Estad\u00edsticas", "menu_help": "\U0001f4ac Soporte / FAQ", "menu_join": "\U0001f4e2 Unirse al Canal",
        "menu_uploads": "\U0001f37f Subidas de Fans", "menu_upload": "\U0001f4e4 Subir Archivo",
        "admin_upload_prompt": "\U0001f4c2 **Bandeja de Subidas de Fans**",
        "user_upload_prompt": "\U0001f4e4 **Subir Archivo**\nEnv\u00eda video/imagen/archivo al Admin. L\u00edmite 5/24h.",
        "upload_success_user": "\u2705 Enviado al Admin!",
        "upload_limit_reached": "\u26a0\ufe0f L\u00edmite de subidas 5/24h alcanzado.",
        "no_uploads": "\U0001f4ed A\u00fan no hay subidas.",
        "stats_msg": "\U0001f4ca **Tus Estad\u00edsticas:**\n\u2022 Descargas Restantes: {}\n\u2022 Lotes Restantes: {}",
        "change_channel_prompt": "\U0001f504 **Cambiar Canal de Lotes**\n1. Aseg\u00farate de que soy admin en el nuevo canal.\n2. Reenv\u00eda cualquier mensaje de ese canal aqu\u00ed.",
        "disk_config_prompt": "\U0001f4be **Config de Disco**\nMin disco libre actual: **{}MB**\nPara cambiar: `/setdisk <valor>`",
        "mtproto_config_prompt": "\u26a1 **Config MTProto**\nMax subida actual: **{}MB**\nPara cambiar: `/setmtproto <valor>`",
        "free_panel_prompt": "\U0001f4e6 DESCARGAS GRATIS\nGratis actuales por d\u00eda: {}",
        "reward_panel_prompt": "\U0001f381 PANEL DE RECOMPENSAS\nActual: +{} descarga por anuncio de 20s",
        "ad_panel_prompt": "\u2699\ufe0f Panel de Anuncios\nActual: {}",
        "password_saved": "\U0001f510 Contrase\u00f1a guardada.",
        "password_too_long": "La contrase\u00f1a debe tener 64 caracteres o menos.",
        "file_to_link_prompt": "\U0001f517 **Archivo-a-Enlace**\nEnv\u00eda el/los archivo(s) que quieres compartir.",
        "link_invalid_expired": "\u274c Este enlace es inv\u00e1lido o expir\u00f3.",
        "link_limit_reached": "\u26d4 Este enlace alcanz\u00f3 su l\u00edmite de uso.",
        "link_password_protected": "\U0001f510 Este enlace est\u00e1 protegido con contrase\u00f1a. Env\u00eda la contrase\u00f1a.",
        "files_sent": "\u2705 Tus archivos han sido enviados.",
        "file_added": "\U0001f4e5 Archivo #{} a\u00f1adido. Env\u00eda m\u00e1s o toca Crear Enlace.",
        "fl_cancelled": "Archivo-a-Enlace cancelado",
        "fl_start_again": "Inicia Archivo-a-Enlace de nuevo con /filetolink",
        "fl_choose_expiry": "Elige la expiraci\u00f3n del enlace:",
        "fl_expiry_updated": "Expiraci\u00f3n actualizada",
        "fl_choose_max_uses": "Elige el m\u00e1ximo de entregas exitosas:",
        "fl_uses_updated": "L\u00edmite de uso actualizado",
        "fl_set_password": "Env\u00eda una contrase\u00f1a, o /clearpassword para eliminar.",
        "fl_link_created": "Enlace creado",
        "fl_link_ready": "\U0001f517 Tu enlace est\u00e1 listo:\n{}\nArchivos: {}\nCosto: 1 descarga diaria gratis",
        "fl_daily_limit": "L\u00edmite diario gratis alcanzado. Mira un anuncio para ganar m\u00e1s.",
        "fl_ad_busy": "\u26a0\ufe0f Servidor de anuncios ocupado.",
        "admin_skipped": "\u2705 Omitido!",
        "admin_bypassed": "\u2705 Omitido",
        "free_set": "\u2705 Gratis configurado a {}!",
        "free_updated": "\u2705 Descargas Gratis actualizadas a {}!",
        "reward_set": "\u2705 Recompensa configurada a +{}!",
        "reward_updated": "\u2705 Recompensa actualizada a +{}!",
        "mode_updated": "\u2705 Modo: {}",
        "support_opened": "\u270d\ufe0f Env\u00eda mensaje/foto/video/archivo abajo.",
        "admin_reply_mode": "\u270d\ufe0f Responder a {}:",
        "user_reply_mode": "\u270d\ufe0f Escribe el seguimiento abajo",
        "support_closed": "\U0001f512 Cerrado",
        "drop_cancelled": "\u274c Cancelado",
        "drop_no_items": "\u26a0\ufe0f Sin elementos!",
        "drop_timer_set": "{} configurado!",
        "drop_broadcasting": "\U0001f680 Transmitiendo {} elementos a {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\nAuto-elimina en {}\nToca para reclamar:",
        "drop_done": "\u2705 Transmisi\u00f3n hecha a {}",
        "age_expired": "\u23f3 Expirado!",
        "age_claimed": "\u274c Ya reclamado!",
        "age_verified": "Verificado!",
        "age_denied": "\u274c Denegado. Debe ser 18+",
        "lang_updated": "Actualizado!",
        "batch_expired": "Expirado",
        "batch_loading": "Cargando...",
        "batch_no_channel": "Ning\u00fan canal vinculado!",
        "batch_setup_prompt": "\U0001f4e6 Configuraci\u00f3n: Haz bot admin en el canal y reenv\u00eda un mensaje aqu\u00ed",
        "batch_mode_activated": "Modo activado!",
        "batch_change_dest": "\U0001f504 **Cambiar Canal de Destino**\nHaz bot admin en el nuevo canal, luego reenv\u00eda un mensaje aqu\u00ed.",
        "join_channel_first_alert": "\u00danete al canal primero! \U0001f4e2 Debes unirte!",
        "join_channel_first": "\u00danete al canal primero! \U0001f4e2",
        "watch_timer_first": "\u23f0 Abre el enlace y mira el temporizador de 20s primero!",
        "test_ad_verified": "\u2705 Anuncio de Prueba Verificado! +1",
        "test_ad_verified_msg": "\u2705 **ANUNCIO DE PRUEBA VERIFICADO!**\nRecompensa: +1 descarga recargada!",
        "finish_timer_first": "\u23f0 Termina el temporizador de 20s primero!",
        "verified_added": "Verificado! +1 a\u00f1adido",
        "resume_prompt": "\u2705 Verificado! Recargado +1. \u00bfReanudar?",
        "refilled_download": "\u2705 Recargado +1! Descarga de nuevo.",
        "fetching_bundle": "\u2705 Verificado! Obteniendo paquete...",
        "outdated_button": "Este bot\u00f3n est\u00e1 desactualizado. Env\u00eda tu enlace de nuevo.",
        "stopping": "Deteniendo...",
        "stopped": "\U0001f6d1 Detenido",
        "resuming": "Reanudando...",
        "checking_vault": "Verificando vault y carga del servidor...",
        "server_busy": "\u23f3 **Servidor Ocupado**\nActivos: {}/{}\nLibre: {}MB\nCola: #{}\nIniciar\u00e1 auto!",
        "simulated": "\U0001f6e0 Simulado! Ahora toca Verificar y Obtener +1",
        "server_unreachable": "\u274c Servidor inalcanzable",
        "monetag_failed_twice": "Completa dos intentos fallidos de Monetag primero.",
        "monetag_fallback_prompt": "\U0001f310 Monetag fall\u00f3 dos veces. Contin\u00faa con Adsterra:",
        "adsterra_ready": "Fallback de Adsterra listo",
        "finish_monetag": "\U0001f4fa Termina el anuncio de Monetag en Mini App, luego verifica.",
        "monetag_failed_use_adsterra": "Monetag fall\u00f3 dos veces. Usa el fallback de Adsterra abajo.",
        "ad_link_expired": "Enlace de anuncio expirado. Env\u00eda tu enlace de nuevo.",
        "ad_verified_added": "\u2705 Anuncio verificado! +{} a\u00f1adido",
        "test_ad_completed": "\u2705 ANUNCIO DE PRUEBA VERIFICADO\nRecompensa acreditada: +{} descarga.",
        "sponsor_viewed": "\u2705 Patrocinador visto! +{} a\u00f1adido",
        "refilled_send_again": "\u2705 Recargado +{}! Env\u00eda tu enlace de nuevo.",
        "queued": "\u23f3 En cola #{}",
        "banned": "\U0001f6ab Est\u00e1s prohibido.",
        "no_links": "\u274c No se encontraron enlaces.",
        "batch_count": "\U0001f4e6 Lote {} enlaces",
        "restore_invalid_json": "\u274c Restauraci\u00f3n fallida: **{}** no es JSON v\u00e1lido.",
        "restore_failed": "\u274c Restauraci\u00f3n fallida: {}",
        "restore_success": "\u2705 **Restauraci\u00f3n Exitosa!**\nArchivo: **{}**\nRestauradas **{}** entradas.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Env\u00eda el nuevo Mensaje de Bienvenida. Usa `{bot_name}` para el nombre de usuario.",
        "admin_welcome_updated": "\u2705 Mensaje de bienvenida actualizado!",
        "menu_edit_welcome": "\u270f\ufe0f Editar Mensaje de Bienvenida",
        "cached_instant_video": "\u26a1 Cach\u00e9 Instant\u00e1nea [{}] {} {}",
        "cached_instant_audio": "\u26a1 **Cach\u00e9 Instant\u00e1nea** `{}`",
        "cached_instant_image": "\u26a1 **Cach\u00e9 Instant\u00e1nea** `{}`",
        "auto_delete_9m": "\u23f3 Auto-elimina en 9 mins",
        "download_success": "\u2705 \u00a1Descarga exitosa!"
    },
    "ar": {
        "welcome": "\U0001f680 **\u0645\u0631\u062d\u0628\u0627\u064b \u0628\u0643 \u0641\u064a MICHAELBBC VAULT - \u0645\u062d\u0645\u0644 \u0627\u0644\u0648\u0633\u0627\u0626\u0637 \u0627\u0644\u0634\u0627\u0645\u0644!**\n\n\U0001f525 \u0645\u0627\u0630\u0627 \u064a\u0645\u0643\u0646\u0646\u064a \u0623\u0646 \u0623\u0641\u0639\u0644:\n\U0001f3ac \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a HD \u0628\u062f\u0648\u0646 \u0639\u0644\u0627\u0645\u0629 \u0645\u0627\u0626\u064a\u0629!\n\U0001f3b5 \u0635\u0648\u062a MP3 192kbps!\n\U0001f5bc\ufe0f \u0633\u062d\u0628 \u062c\u0645\u064a\u0639 \u0627\u0644\u0635\u0648\u0631!\n\U0001f4dd \u062a\u0631\u062c\u0645\u0627\u062a \u062a\u0644\u0642\u0627\u0626\u064a\u0629!\n\U0001f4e6 \u062f\u0641\u0639\u0627\u062a 100+ \u0631\u0627\u0628\u0637!\n\u26a1 \u0630\u0627\u0643\u0631\u0629 \u062a\u062e\u0632\u064a\u0646 \u0645\u0624\u0642\u062a 1 \u062b\u0627\u0646\u064a\u0629!\n\U0001f48e \u062e\u0632\u0646\u0629 \u0644\u0644\u0623\u0628\u062f!\n\U0001f4e4 \u0631\u0641\u0639 \u0627\u0644\u0645\u0644\u0641\u0627\u062a!\n\U0001f517 \u0645\u0644\u0641-\u0625\u0644\u0649-\u0631\u0627\u0628\u0637: \u0625\u0646\u0634\u0627\u0621 \u0631\u0648\u0627\u0628\u0637 \u0642\u0627\u0628\u0644\u0629 \u0644\u0644\u0645\u0634\u0627\u0631\u0643\u0629!\n\n\U0001f449 \u0627\u0644\u0635\u0642 \u0631\u0627\u0628\u0637\u0627\u064b \u0644\u0644\u0628\u062f\u0621! \U0001f447",
        "btn_video": "\U0001f3ac \u0641\u064a\u062f\u064a\u0648 (MP4)", "btn_audio": "\U0001f3b5 \u0635\u0648\u062a (MP3)", "btn_image": "\U0001f5bc\ufe0f \u0635\u0648\u0631", "btn_sub": "\U0001f4dd \u062a\u0631\u062c\u0645\u0627\u062a (SRT)",
        "ask_format": "\U0001f447 **\u0631\u0627\u0626\u0639! \u0645\u0627 \u0627\u0644\u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0630\u064a \u062a\u0631\u064a\u062f\u0647\u061f \u0627\u062e\u062a\u0631 \u0623\u062f\u0646\u0627\u0647!**",
        "fetching": "\U0001f4e5 **\u062c\u0627\u0631\u064a \u062c\u0644\u0628 {}... \u0627\u0646\u062a\u0638\u0631 \u0642\u0644\u064a\u0644\u0627\u064b! \u23f3\u2728**",
        "error_generic": "\u274c \u0639\u0630\u0631\u0627\u064b! \u0641\u0634\u0644! \U0001f622 \u0627\u0644\u0631\u0627\u0628\u0637 \u062e\u0627\u0635/\u0645\u062d\u0638\u0648\u0631. \u062c\u0631\u0628 \u0631\u0627\u0628\u0637\u0627\u064b \u0639\u0627\u0645\u0627\u064b!",
        "error_50mb": "\u274c \u0643\u0628\u064a\u0631 \u062c\u062f\u0627\u064b! \U0001f605 \u0647\u0630\u0627 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u064a\u062a\u062c\u0627\u0648\u0632 300 \u0645\u064a\u062c\u0627\u0628\u0627\u064a\u062a. \u062c\u0631\u0628 \u0641\u064a\u062f\u064a\u0648 \u0623\u0642\u0635\u0631!", 
        "error_no_img": "\u274c \u0644\u0645 \u064a\u062a\u0645 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u0635\u0648\u0631! \U0001f622 \u062c\u0631\u0628 \u0631\u0627\u0628\u0637\u0627\u064b \u0622\u062e\u0631!",
        "images_received": "\u23f3 **\u062a\u0645 \u0627\u0633\u062a\u0644\u0627\u0645 {} \u0635\u0648\u0631\u0629.**",
        "select_lang": "\U0001f30d \u0627\u062e\u062a\u0631 \u0644\u063a\u062a\u0643! \u0627\u062e\u062a\u0631 \u0623\u062f\u0646\u0627\u0647! \U0001f447", 
        "lang_set": "\u2705 \u062a\u0645 \u062a\u0639\u064a\u064a\u0646 \u0627\u0644\u0644\u063a\u0629! \u0627\u0633\u062a\u0645\u062a\u0639! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **\u062a\u0645 \u0627\u0643\u062a\u0634\u0627\u0641 \u062f\u0641\u0639\u0629 ({} \u0631\u0648\u0627\u0628\u0637)**\n\u0645\u0627 \u0627\u0644\u062a\u0646\u0633\u064a\u0642\u061f",
        "batch_dest": "\U0001f4e6 **\u0623\u064a\u0646 \u0646\u0631\u0633\u0644\u061f**",
        "btn_chat": "\U0001f4e5 \u0641\u064a \u0627\u0644\u062f\u0631\u062f\u0634\u0629", "btn_chan": "\U0001f4e2 \u0625\u0644\u0649 \u0627\u0644\u0642\u0646\u0627\u0629",
        "limit_reached": "\u26a0\ufe0f **\u062a\u0645 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u0644\u062d\u062f \u0627\u0644\u0623\u0642\u0635\u0649!** \u0627\u0633\u062a\u062e\u062f\u0645\u062a 4 \u0645\u062c\u0627\u0646\u0627\u064b! \u0634\u0627\u0647\u062f \u0625\u0639\u0644\u0627\u0646 20 \u062b\u0627\u0646\u064a\u0629 \u2192 \u0627\u062d\u0635\u0644 \u0639\u0644\u0649 +1 \u062a\u062d\u0645\u064a\u0644!",
        "refill_btn": "\U0001f513 \u0627\u0641\u062a\u062d \u0627\u0644\u0631\u0627\u0628\u0637 \u0648\u0623\u0639\u062f \u0627\u0644\u062a\u0639\u0628\u0626\u0629 +1",
        "join_btn": "\U0001f4e2 \u0627\u0646\u0636\u0645 \u0644\u0644\u0642\u0646\u0627\u0629", "check_btn": "\U0001f49c \u062a\u062d\u0642\u0642 \u0645\u0646 \u0627\u0644\u0631\u0635\u064a\u062f",
        "limit_batch": "\u26a0\ufe0f **\u062a\u0645 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u062d\u062f \u0627\u0644\u062f\u0641\u0639\u0629 \u0639\u0646\u062f {} \u0645\u0646 {}**\n\u0634\u0627\u0647\u062f \u0625\u0639\u0644\u0627\u0646 20 \u062b\u0627\u0646\u064a\u0629 \u2192 +1 \u062a\u062d\u0645\u064a\u0644 \u0644\u0644\u0645\u062a\u0627\u0628\u0639\u0629.",
        "batch_start": "\U0001f4e6 **\u0628\u062f\u0623\u062a \u0627\u0644\u062f\u0641\u0639\u0629:** {} **{} \u0645\u0644\u0641\u0627\u062a**\n\u23f3 \u062c\u0627\u0631\u064a \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629...",
        "batch_done": "\U0001f3c1 **\u062a\u0645!** \u2705 {} \u274c {}\n\U0001f4e5 {} \u0645\u0644\u0641\u0627\u062a \u0647\u0646\u0627.",
        "batch_done_chan": "\U0001f3c1 **\u062a\u0645!** \u2705 {} \u274c {}\n\U0001f4e2 \u062a\u0645 \u0625\u0639\u0627\u062f\u0629 \u062a\u0648\u062c\u064a\u0647 {} \u0645\u0644\u0641\u0627\u062a!",
        "dl_video": "\U0001f4e5 \u062c\u0627\u0631\u064a \u062a\u062d\u0645\u064a\u0644 \u0627\u0644\u0641\u064a\u062f\u064a\u0648...", "dl_audio": "\U0001f4e5 \u062c\u0627\u0631\u064a \u0627\u0633\u062a\u062e\u0631\u0627\u062c \u0627\u0644\u0635\u0648\u062a...", "dl_image": "\U0001f4e5 \u062c\u0627\u0631\u064a \u0633\u062d\u0628 \u0627\u0644\u0635\u0648\u0631...", "dl_sub": "\U0001f4e5 \u062c\u0627\u0631\u064a \u062c\u0644\u0628 \u0627\u0644\u062a\u0631\u062c\u0645\u0627\u062a...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c \u0645\u062d\u0638\u0648\u0631/\u062e\u0627\u0635", "failed_generic": "\u274c \u0641\u0634\u0644",
        "menu_lang": "\U0001f30d \u0627\u0644\u0644\u063a\u0629", "menu_stats": "\U0001f4ca \u0625\u062d\u0635\u0627\u0626\u064a\u0627\u062a\u064a", "menu_help": "\U0001f4ac \u0627\u0644\u062f\u0639\u0645 / \u0627\u0644\u0623\u0633\u0626\u0644\u0629 \u0627\u0644\u0634\u0627\u0626\u0639\u0629", "menu_join": "\U0001f4e2 \u0627\u0646\u0636\u0645 \u0644\u0644\u0642\u0646\u0627\u0629",
        "menu_uploads": "\U0001f37f \u0631\u0641\u0639 \u0627\u0644\u0645\u0639\u062c\u0628\u064a\u0646", "menu_upload": "\U0001f4e4 \u0631\u0641\u0639 \u0645\u0644\u0641",
        "admin_upload_prompt": "\U0001f4c2 **\u0635\u0646\u062f\u0648\u0642 \u0648\u0627\u0631\u062f \u0631\u0641\u0639 \u0627\u0644\u0645\u0639\u062c\u0628\u064a\u0646**",
        "user_upload_prompt": "\U0001f4e4 **\u0631\u0641\u0639 \u0645\u0644\u0641**\n\u0623\u0631\u0633\u0644 \u0641\u064a\u062f\u064a\u0648/\u0635\u0648\u0631\u0629/\u0645\u0644\u0641 \u0644\u0644\u0645\u0633\u0624\u0648\u0644. \u0627\u0644\u062d\u062f 5/24 \u0633\u0627\u0639\u0629.",
        "upload_success_user": "\u2705 \u062a\u0645 \u0627\u0644\u0625\u0631\u0633\u0627\u0644 \u0644\u0644\u0645\u0633\u0624\u0648\u0644!",
        "upload_limit_reached": "\u26a0\ufe0f \u062a\u0645 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u062d\u062f \u0627\u0644\u0631\u0641\u0639 5/24 \u0633\u0627\u0639\u0629.",
        "no_uploads": "\U0001f4ed \u0644\u0627 \u062a\u0648\u062c\u062f \u0639\u0645\u0644\u064a\u0627\u062a \u0631\u0641\u0639 \u0628\u0639\u062f.",
        "stats_msg": "\U0001f4ca **\u0625\u062d\u0635\u0627\u0626\u064a\u0627\u062a\u0643:**\n\u2022 \u0627\u0644\u062a\u062d\u0645\u064a\u0644\u0627\u062a \u0627\u0644\u0645\u062a\u0628\u0642\u064a\u0629: {}\n\u2022 \u0627\u0644\u062f\u0641\u0639\u0627\u062a \u0627\u0644\u0645\u062a\u0628\u0642\u064a\u0629: {}",
        "change_channel_prompt": "\U0001f504 **\u062a\u063a\u064a\u064a\u0631 \u0642\u0646\u0627\u0629 \u0627\u0644\u062f\u0641\u0639\u0627\u062a**\n1. \u062a\u0623\u0643\u062f \u0645\u0646 \u0623\u0646\u0646\u064a \u0645\u0633\u0624\u0648\u0644 \u0641\u064a \u0627\u0644\u0642\u0646\u0627\u0629 \u0627\u0644\u062c\u062f\u064a\u062f\u0629.\n2. \u0623\u0639\u062f \u062a\u0648\u062c\u064a\u0647 \u0623\u064a \u0631\u0633\u0627\u0644\u0629 \u0645\u0646 \u062a\u0644\u0643 \u0627\u0644\u0642\u0646\u0627\u0629 \u0625\u0644\u0649 \u0647\u0646\u0627.",
        "disk_config_prompt": "\U0001f4be **\u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u0642\u0631\u0635**\n\u0627\u0644\u062d\u062f \u0627\u0644\u0623\u062f\u0646\u0649 \u0627\u0644\u062d\u0627\u0644\u064a \u0644\u0644\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u062d\u0631\u0629: **{} \u0645\u064a\u062c\u0627\u0628\u0627\u064a\u062a**\n\u0644\u0644\u062a\u063a\u064a\u064a\u0631: `/setdisk <value>`",
        "mtproto_config_prompt": "\u26a1 **\u0625\u0639\u062f\u0627\u062f\u0627\u062a MTProto**\n\u0627\u0644\u062d\u062f \u0627\u0644\u0623\u0642\u0635\u0649 \u0627\u0644\u062d\u0627\u0644\u064a \u0644\u0644\u0631\u0641\u0639: **{} \u0645\u064a\u062c\u0627\u0628\u0627\u064a\u062a**\n\u0644\u0644\u062a\u063a\u064a\u064a\u0631: `/setmtproto <value>`",
        "free_panel_prompt": "\U0001f4e6 \u0627\u0644\u062a\u062d\u0645\u064a\u0644\u0627\u062a \u0627\u0644\u0645\u062c\u0627\u0646\u064a\u0629\n\u0627\u0644\u0645\u062c\u0627\u0646\u064a \u0627\u0644\u062d\u0627\u0644\u064a \u064a\u0648\u0645\u064a\u0627\u064b: {}",
        "reward_panel_prompt": "\U0001f381 \u0644\u0648\u062d\u0629 \u0627\u0644\u0645\u0643\u0627\u0641\u0622\u062a\n\u0627\u0644\u062d\u0627\u0644\u064a: +{} \u062a\u062d\u0645\u064a\u0644 \u0644\u0643\u0644 \u0625\u0639\u0644\u0627\u0646 20 \u062b\u0627\u0646\u064a\u0629",
        "ad_panel_prompt": "\u2699\ufe0f \u0644\u0648\u062d\u0629 \u0627\u0644\u0625\u0639\u0644\u0627\u0646\u0627\u062a\n\u0627\u0644\u062d\u0627\u0644\u064a: {}",
        "password_saved": "\U0001f510 \u062a\u0645 \u062d\u0641\u0638 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631.",
        "password_too_long": "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631 64 \u062d\u0631\u0641\u0627\u064b \u0623\u0648 \u0623\u0642\u0644.",
        "file_to_link_prompt": "\U0001f517 **\u0645\u0644\u0641-\u0625\u0644\u0649-\u0631\u0627\u0628\u0637**\n\u0623\u0631\u0633\u0644 \u0627\u0644\u0645\u0644\u0641(\u0627\u062a) \u0627\u0644\u062a\u064a \u062a\u0631\u064a\u062f \u0645\u0634\u0627\u0631\u0643\u062a\u0647\u0627.",
        "link_invalid_expired": "\u274c \u0647\u0630\u0627 \u0627\u0644\u0631\u0627\u0628\u0637 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d \u0623\u0648 \u0645\u0646\u062a\u0647\u064a \u0627\u0644\u0635\u0644\u0627\u062d\u064a\u0629.",
        "link_limit_reached": "\u26d4 \u0648\u0635\u0644 \u0647\u0630\u0627 \u0627\u0644\u0631\u0627\u0628\u0637 \u0625\u0644\u0649 \u062d\u062f \u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645.",
        "link_password_protected": "\U0001f510 \u0647\u0630\u0627 \u0627\u0644\u0631\u0627\u0628\u0637 \u0645\u062d\u0645\u064a \u0628\u0643\u0644\u0645\u0629 \u0645\u0631\u0648\u0631. \u0623\u0631\u0633\u0644 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631.",
        "files_sent": "\u2705 \u062a\u0645 \u0625\u0631\u0633\u0627\u0644 \u0645\u0644\u0641\u0627\u062a\u0643.",
        "file_added": "\U0001f4e5 \u062a\u0645\u062a \u0625\u0636\u0627\u0641\u0629 \u0627\u0644\u0645\u0644\u0641 #{}. \u0623\u0631\u0633\u0644 \u0627\u0644\u0645\u0632\u064a\u062f\u060c \u0623\u0648 \u0627\u0636\u063a\u0637 \u0639\u0644\u0649 \u0625\u0646\u0634\u0627\u0621 \u0631\u0627\u0628\u0637.",
        "fl_cancelled": "\u062a\u0645 \u0625\u0644\u063a\u0627\u0621 \u0645\u0644\u0641-\u0625\u0644\u0649-\u0631\u0627\u0628\u0637",
        "fl_start_again": "\u0627\u0628\u062f\u0623 \u0645\u0644\u0641-\u0625\u0644\u0649-\u0631\u0627\u0628\u0637 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649 \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 /filetolink",
        "fl_choose_expiry": "\u0627\u062e\u062a\u0631 \u0627\u0646\u062a\u0647\u0627\u0621 \u0635\u0644\u0627\u062d\u064a\u0629 \u0627\u0644\u0631\u0627\u0628\u0637:",
        "fl_expiry_updated": "\u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u0627\u0644\u0627\u0646\u062a\u0647\u0627\u0621",
        "fl_choose_max_uses": "\u0627\u062e\u062a\u0631 \u0627\u0644\u062d\u062f \u0627\u0644\u0623\u0642\u0635\u0649 \u0644\u0644\u062a\u0633\u0644\u064a\u0645\u0627\u062a \u0627\u0644\u0646\u0627\u062c\u062d\u0629:",
        "fl_uses_updated": "\u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u062d\u062f \u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645",
        "fl_set_password": "\u0623\u0631\u0633\u0644 \u0643\u0644\u0645\u0629 \u0645\u0631\u0648\u0631\u060c \u0623\u0648 /clearpassword \u0644\u0644\u0625\u0632\u0627\u0644\u0629.",
        "fl_link_created": "\u062a\u0645 \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u0631\u0627\u0628\u0637",
        "fl_link_ready": "\U0001f517 \u0631\u0627\u0628\u0637\u0643 \u062c\u0627\u0647\u0632:\n{}\n\u0627\u0644\u0645\u0644\u0641\u0627\u062a: {}\n\u0627\u0644\u062a\u0643\u0644\u0641\u0629: 1 \u062a\u062d\u0645\u064a\u0644 \u064a\u0648\u0645\u064a \u0645\u062c\u0627\u0646\u064a",
        "fl_daily_limit": "\u062a\u0645 \u0627\u0644\u0648\u0635\u0648\u0644 \u0644\u0644\u062d\u062f \u0627\u0644\u064a\u0648\u0645\u064a \u0627\u0644\u0645\u062c\u0627\u0646\u064a. \u0634\u0627\u0647\u062f \u0625\u0639\u0644\u0627\u0646\u0627\u064b \u0644\u0643\u0633\u0628 \u0627\u0644\u0645\u0632\u064a\u062f.",
        "fl_ad_busy": "\u26a0\ufe0f \u062e\u0627\u062f\u0645 \u0627\u0644\u0625\u0639\u0644\u0627\u0646\u0627\u062a \u0645\u0634\u063a\u0648\u0644.",
        "admin_skipped": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062e\u0637\u064a!",
        "admin_bypassed": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062c\u0627\u0648\u0632",
        "free_set": "\u2705 \u062a\u0645 \u062a\u0639\u064a\u064a\u0646 \u0627\u0644\u0645\u062c\u0627\u0646\u064a \u0625\u0644\u0649 {}!",
        "free_updated": "\u2705 \u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u0627\u0644\u062a\u062d\u0645\u064a\u0644\u0627\u062a \u0627\u0644\u0645\u062c\u0627\u0646\u064a\u0629 \u0625\u0644\u0649 {}!",
        "reward_set": "\u2705 \u062a\u0645 \u062a\u0639\u064a\u064a\u0646 \u0627\u0644\u0645\u0643\u0627\u0641\u0623\u0629 \u0625\u0644\u0649 +{}!",
        "reward_updated": "\u2705 \u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u0627\u0644\u0645\u0643\u0627\u0641\u0623\u0629 \u0625\u0644\u0649 +{}!",
        "mode_updated": "\u2705 \u0627\u0644\u0648\u0636\u0639: {}",
        "support_opened": "\u270d\ufe0f \u0623\u0631\u0633\u0644 \u0631\u0633\u0627\u0644\u0629/\u0635\u0648\u0631\u0629/\u0641\u064a\u062f\u064a\u0648/\u0645\u0644\u0641 \u0623\u062f\u0646\u0627\u0647.",
        "admin_reply_mode": "\u270d\ufe0f \u0627\u0644\u0631\u062f \u0639\u0644\u0649 {}:",
        "user_reply_mode": "\u270d\ufe0f \u0627\u0643\u062a\u0628 \u0627\u0644\u0645\u062a\u0627\u0628\u0639\u0629 \u0623\u062f\u0646\u0627\u0647",
        "support_closed": "\U0001f512 \u0645\u063a\u0644\u0642",
        "drop_cancelled": "\u274c \u0645\u0644\u063a\u064a",
        "drop_no_items": "\u26a0\ufe0f \u0644\u0627 \u062a\u0648\u062c\u062f \u0639\u0646\u0627\u0635\u0631!",
        "drop_timer_set": "\u062a\u0645 \u062a\u0639\u064a\u064a\u0646 {}!",
        "drop_broadcasting": "\U0001f680 \u062c\u0627\u0631\u064a \u0627\u0644\u0628\u062b {} \u0639\u0646\u0627\u0635\u0631 \u0625\u0644\u0649 {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\n\u062d\u0630\u0641 \u062a\u0644\u0642\u0627\u0626\u064a \u0641\u064a {}\n\u0627\u0636\u063a\u0637 \u0644\u0644\u0645\u0637\u0627\u0644\u0628\u0629:",
        "drop_done": "\u2705 \u062a\u0645 \u0627\u0644\u0628\u062b \u0625\u0644\u0649 {}",
        "age_expired": "\u23f3 \u0645\u0646\u062a\u0647\u064a \u0627\u0644\u0635\u0644\u0627\u062d\u064a\u0629!",
        "age_claimed": "\u274c \u062a\u0645\u062a \u0627\u0644\u0645\u0637\u0627\u0644\u0628\u0629 \u0628\u0647 \u0628\u0627\u0644\u0641\u0639\u0644!",
        "age_verified": "\u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642!",
        "age_denied": "\u274c \u0645\u0631\u0641\u0648\u0636. \u064a\u062c\u0628 \u0623\u0646 \u064a\u0643\u0648\u0646 18+",
        "lang_updated": "\u062a\u0645 \u0627\u0644\u062a\u062d\u062f\u064a\u062b!",
        "batch_expired": "\u0645\u0646\u062a\u0647\u064a \u0627\u0644\u0635\u0644\u0627\u062d\u064a\u0629",
        "batch_loading": "\u062c\u0627\u0631\u064a \u0627\u0644\u062a\u062d\u0645\u064a\u0644...",
        "batch_no_channel": "\u0644\u0627 \u062a\u0648\u062c\u062f \u0642\u0646\u0627\u0629 \u0645\u0631\u062a\u0628\u0637\u0629!",
        "batch_setup_prompt": "\U0001f4e6 \u0627\u0644\u0625\u0639\u062f\u0627\u062f: \u0627\u062c\u0639\u0644 \u0627\u0644\u0628\u0648\u062a \u0645\u0633\u0624\u0648\u0644\u0627\u064b \u0641\u064a \u0627\u0644\u0642\u0646\u0627\u0629 \u0648\u0623\u0639\u062f \u062a\u0648\u062c\u064a\u0647 \u0631\u0633\u0627\u0644\u0629 \u0625\u0644\u0649 \u0647\u0646\u0627",
        "batch_mode_activated": "\u062a\u0645 \u062a\u0641\u0639\u064a\u0644 \u0627\u0644\u0648\u0636\u0639!",
        "batch_change_dest": "\U0001f504 **\u062a\u063a\u064a\u064a\u0631 \u0642\u0646\u0627\u0629 \u0627\u0644\u0648\u062c\u0647\u0629**\n\u0627\u062c\u0639\u0644 \u0627\u0644\u0628\u0648\u062a \u0645\u0633\u0624\u0648\u0644\u0627\u064b \u0641\u064a \u0627\u0644\u0642\u0646\u0627\u0629 \u0627\u0644\u062c\u062f\u064a\u062f\u0629\u060c \u062b\u0645 \u0623\u0639\u062f \u062a\u0648\u062c\u064a\u0647 \u0631\u0633\u0627\u0644\u0629 \u0625\u0644\u0649 \u0647\u0646\u0627.",
        "join_channel_first_alert": "\u0627\u0646\u0636\u0645 \u0644\u0644\u0642\u0646\u0627\u0629 \u0623\u0648\u0644\u0627\u064b! \U0001f4e2 \u064a\u062c\u0628 \u0627\u0644\u0627\u0646\u0636\u0645\u0627\u0645!",
        "join_channel_first": "\u0627\u0646\u0636\u0645 \u0644\u0644\u0642\u0646\u0627\u0629 \u0623\u0648\u0644\u0627\u064b! \U0001f4e2",
        "watch_timer_first": "\u23f0 \u0627\u0641\u062a\u062d \u0627\u0644\u0631\u0627\u0628\u0637 \u0648\u0634\u0627\u0647\u062f \u0627\u0644\u0645\u0624\u0642\u062a \u0644\u0645\u062f\u0629 20 \u062b\u0627\u0646\u064a\u0629 \u0623\u0648\u0644\u0627\u064b!",
        "test_ad_verified": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0625\u0639\u0644\u0627\u0646 \u0627\u0644\u0627\u062e\u062a\u0628\u0627\u0631! +1",
        "test_ad_verified_msg": "\u2705 **\u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0625\u0639\u0644\u0627\u0646 \u0627\u0644\u0627\u062e\u062a\u0628\u0627\u0631!**\n\u0627\u0644\u0645\u0643\u0627\u0641\u0623\u0629: \u062a\u0645 \u0625\u0639\u0627\u062f\u0629 \u062a\u0639\u0628\u0626\u0629 +1 \u062a\u062d\u0645\u064a\u0644!",
        "finish_timer_first": "\u23f0 \u0623\u0646\u0647\u064d \u0645\u0624\u0642\u062a 20 \u062b\u0627\u0646\u064a\u0629 \u0623\u0648\u0644\u0627\u064b!",
        "verified_added": "\u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642! \u062a\u0645\u062a \u0625\u0636\u0627\u0641\u0629 +1",
        "resume_prompt": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642! \u062a\u0645\u062a \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0639\u0628\u0626\u0629 +1. \u0627\u0633\u062a\u0626\u0646\u0627\u0641\u061f",
        "refilled_download": "\u2705 \u062a\u0645\u062a \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0639\u0628\u0626\u0629 +1! \u062d\u0645\u0644 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649.",
        "fetching_bundle": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642! \u062c\u0627\u0631\u064a \u062c\u0644\u0628 \u0627\u0644\u062d\u0632\u0645\u0629...",
        "outdated_button": "\u0647\u0630\u0627 \u0627\u0644\u0632\u0631 \u0642\u062f\u064a\u0645. \u0623\u0631\u0633\u0644 \u0631\u0627\u0628\u0637\u0643 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649.",
        "stopping": "\u062c\u0627\u0631\u064a \u0627\u0644\u0625\u064a\u0642\u0627\u0641...",
        "stopped": "\U0001f6d1 \u062a\u0645 \u0627\u0644\u0625\u064a\u0642\u0627\u0641",
        "resuming": "\u062c\u0627\u0631\u064a \u0627\u0644\u0627\u0633\u062a\u0626\u0646\u0627\u0641...",
        "checking_vault": "\u062c\u0627\u0631\u064a \u0641\u062d\u0635 \u0627\u0644\u062e\u0632\u0646\u0629 \u0648\u062d\u0645\u0644 \u0627\u0644\u062e\u0627\u062f\u0645...",
        "server_busy": "\u23f3 **\u0627\u0644\u062e\u0627\u062f\u0645 \u0645\u0634\u063a\u0648\u0644**\n\u0646\u0634\u0637: {}/{}\n\u062d\u0631: {} \u0645\u064a\u062c\u0627\u0628\u0627\u064a\u062a\n\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0627\u0646\u062a\u0638\u0627\u0631: #{}\n\u0633\u064a\u0628\u062f\u0623 \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b!",
        "simulated": "\U0001f6e0 \u062a\u0645\u062a \u0627\u0644\u0645\u062d\u0627\u0643\u0627\u0629! \u0627\u0636\u063a\u0637 \u0627\u0644\u0622\u0646 \u0639\u0644\u0649 \u062a\u062d\u0642\u0642 \u0648\u0627\u062d\u0635\u0644 \u0639\u0644\u0649 +1",
        "server_unreachable": "\u274c \u0627\u0644\u062e\u0627\u062f\u0645 \u063a\u064a\u0631 \u0645\u062a\u0627\u062d",
        "monetag_failed_twice": "\u0623\u0643\u0645\u0644 \u0645\u062d\u0627\u0648\u0644\u062a\u064a\u0646 \u0641\u0627\u0634\u0644\u062a\u064a\u0646 \u0644\u0640 Monetag \u0623\u0648\u0644\u0627\u064b.",
        "monetag_fallback_prompt": "\U0001f310 \u0641\u0634\u0644 Monetag \u0645\u0631\u062a\u064a\u0646. \u062a\u0627\u0628\u0639 \u0645\u0639 Adsterra:",
        "adsterra_ready": "\u0628\u062f\u064a\u0644 Adsterra \u062c\u0627\u0647\u0632",
        "finish_monetag": "\U0001f4fa \u0623\u0646\u0647\u064d \u0625\u0639\u0644\u0627\u0646 Monetag \u0641\u064a \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0627\u0644\u0645\u0635\u063a\u0631\u060c \u062b\u0645 \u062a\u062d\u0642\u0642 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649.",
        "monetag_failed_use_adsterra": "\u0641\u0634\u0644 Monetag \u0645\u0631\u062a\u064a\u0646. \u0627\u0633\u062a\u062e\u062f\u0645 \u0628\u062f\u064a\u0644 Adsterra \u0623\u062f\u0646\u0627\u0647.",
        "ad_link_expired": "\u0627\u0646\u062a\u0647\u062a \u0635\u0644\u0627\u062d\u064a\u0629 \u0631\u0627\u0628\u0637 \u0627\u0644\u0625\u0639\u0644\u0627\u0646. \u0623\u0631\u0633\u0644 \u0631\u0627\u0628\u0637\u0643 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649.",
        "ad_verified_added": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0627\u0644\u0625\u0639\u0644\u0627\u0646! \u062a\u0645\u062a \u0625\u0636\u0627\u0641\u0629 +{}",
        "test_ad_completed": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0625\u0639\u0644\u0627\u0646 \u0627\u0644\u0627\u062e\u062a\u0628\u0627\u0631\n\u062a\u0645 \u0627\u0639\u062a\u0645\u0627\u062f \u0627\u0644\u0645\u0643\u0627\u0641\u0623\u0629: +{} \u062a\u062d\u0645\u064a\u0644.",
        "sponsor_viewed": "\u2705 \u062a\u0645\u062a \u0645\u0634\u0627\u0647\u062f\u0629 \u0627\u0644\u0631\u0627\u0639\u064a! \u062a\u0645\u062a \u0625\u0636\u0627\u0641\u0629 +{}",
        "refilled_send_again": "\u2705 \u062a\u0645\u062a \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0639\u0628\u0626\u0629 +{}! \u0623\u0631\u0633\u0644 \u0631\u0627\u0628\u0637\u0643 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649.",
        "queued": "\u23f3 \u0641\u064a \u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0627\u0646\u062a\u0638\u0627\u0631 #{}",
        "banned": "\U0001f6ab \u0623\u0646\u062a \u0645\u062d\u0638\u0648\u0631.",
        "no_links": "\u274c \u0644\u0645 \u064a\u062a\u0645 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u0631\u0648\u0627\u0628\u0637.",
        "batch_count": "\U0001f4e6 \u062f\u0641\u0639\u0629 {} \u0631\u0648\u0627\u0628\u0637",
        "restore_invalid_json": "\u274c \u0641\u0634\u0644 \u0627\u0644\u0627\u0633\u062a\u0639\u0627\u062f\u0629: **{}** \u0644\u064a\u0633 JSON \u0635\u0627\u0644\u062d\u0627\u064b.",
        "restore_failed": "\u274c \u0641\u0634\u0644 \u0627\u0644\u0627\u0633\u062a\u0639\u0627\u062f\u0629: {}",
        "restore_success": "\u2705 **\u0646\u062c\u0627\u062d \u0627\u0644\u0627\u0633\u062a\u0639\u0627\u062f\u0629!**\n\u0627\u0644\u0645\u0644\u0641: **{}**\n\u062a\u0645\u062a \u0627\u0633\u062a\u0639\u0627\u062f\u0629 **{}** \u0625\u062f\u062e\u0627\u0644\u0627\u062a.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f \u0623\u0631\u0633\u0644 \u0631\u0633\u0627\u0644\u0629 \u0627\u0644\u062a\u0631\u062d\u064a\u0628 \u0627\u0644\u062c\u062f\u064a\u062f\u0629. \u0627\u0633\u062a\u062e\u062f\u0645 `{bot_name}` \u0644\u0627\u0633\u0645 \u0645\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0628\u0648\u062a.",
        "admin_welcome_updated": "\u2705 \u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u0631\u0633\u0627\u0644\u0629 \u0627\u0644\u062a\u0631\u062d\u064a\u0628!",
        "menu_edit_welcome": "\u270f\ufe0f \u062a\u062d\u0631\u064a\u0631 \u0631\u0633\u0627\u0644\u0629 \u0627\u0644\u062a\u0631\u062d\u064a\u0628",
        "cached_instant_video": "\u26a1 \u0630\u0627\u0643\u0631\u0629 \u062a\u062e\u0632\u064a\u0646 \u0645\u0624\u0642\u062a \u0641\u0648\u0631\u064a\u0629 [{}] {} {}",
        "cached_instant_audio": "\u26a1 **\u0630\u0627\u0643\u0631\u0629 \u062a\u062e\u0632\u064a\u0646 \u0645\u0624\u0642\u062a \u0641\u0648\u0631\u064a\u0629** `{}`",
        "cached_instant_image": "\u26a1 **\u0630\u0627\u0643\u0631\u0629 \u062a\u062e\u0632\u064a\u0646 \u0645\u0624\u0642\u062a \u0641\u0648\u0631\u064a\u0629** `{}`",
        "auto_delete_9m": "\u23f3 \u062d\u0630\u0641 \u062a\u0644\u0642\u0627\u0626\u064a \u0641\u064a 9 \u062f\u0642\u0627\u0626\u0642",
        "download_success": "\u2705 \u062a\u0645 \u0627\u0644\u062a\u062d\u0645\u064a\u0644 \u0628\u0646\u062c\u0627\u062d!"
    },
    "ru": {
        "welcome": "\U0001f680 **\u0414\u041e\u0411\u0420\u041e \u041f\u041e\u0416\u0410\u041b\u041e\u0412\u0410\u0422\u042c \u0412 MICHAELBBC VAULT - \u0423\u041d\u0418\u0412\u0415\u0420\u0421\u0410\u041b\u042c\u041d\u042b\u0419 \u0417\u0410\u0413\u0420\u0423\u0417\u0427\u0418\u041a!**\n\n\U0001f525 \u0427\u0422\u041e \u042f \u0423\u041c\u0415\u042e:\n\U0001f3ac \u0412\u0418\u0414\u0415\u041e HD \u0411\u0435\u0437 \u0412\u043e\u0434\u044f\u043d\u044b\u0445 \u0417\u043d\u0430\u043a\u043e\u0432!\n\U0001f3b5 \u0410\u0423\u0414\u0418\u041e MP3 192kbps!\n\U0001f5bc\ufe0f \u0418\u0417\u041e\u0411\u0420\u0410\u0416\u0415\u041d\u0418\u042f \u0421\u043a\u0430\u0447\u0438\u0432\u0430\u043d\u0438\u0435 \u0412\u0421\u0415\u0425!\n\U0001f4dd \u0421\u0423\u0411\u0422\u0418\u0422\u0420\u042b \u0410\u0432\u0442\u043e!\n\U0001f4e6 \u041f\u0410\u041a\u0415\u0422\u042b 100+ \u0421\u0441\u044b\u043b\u043e\u043a!\n\u26a1 \u041a\u042d\u0428 1 \u0421\u0435\u043a!\n\U0001f48e \u0425\u0420\u0410\u041d\u0418\u041b\u0418\u0429\u0415 \u041d\u0430\u0432\u0441\u0435\u0433\u0434\u0430!\n\U0001f4e4 \u0417\u0410\u0413\u0420\u0423\u0417\u041a\u0410 \u0424\u0410\u0419\u041b\u041e\u0412!\n\U0001f517 \u0424\u0410\u0419\u041b-\u0412-\u0421\u0421\u042b\u041b\u041a\u0423: \u0421\u043e\u0437\u0434\u0430\u0432\u0430\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0438 \u0434\u043b\u044f \u043e\u0431\u043c\u0435\u043d\u0430!\n\n\U0001f449 \u0412\u0421\u0422\u0410\u0412\u042c\u0422\u0415 \u0421\u0421\u042b\u041b\u041a\u0423, \u0427\u0422\u041e\u0411\u042b \u041d\u0410\u0427\u0410\u0422\u042c! \U0001f447",
        "btn_video": "\U0001f3ac \u0412\u0438\u0434\u0435\u043e (MP4)", "btn_audio": "\U0001f3b5 \u0410\u0443\u0434\u0438\u043e (MP3)", "btn_image": "\U0001f5bc\ufe0f \u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f", "btn_sub": "\U0001f4dd \u0421\u0443\u0431\u0442\u0438\u0442\u0440\u044b (SRT)",
        "ask_format": "\U0001f447 **\u041e\u0422\u041b\u0418\u0427\u041d\u041e! \u041a\u0430\u043a\u043e\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u0432\u044b \u0445\u043e\u0442\u0438\u0442\u0435? \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043d\u0438\u0436\u0435!**",
        "fetching": "\U0001f4e5 **\u041f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u0435 \u0432\u0430\u0448\u0435\u0433\u043e {}... \u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435! \u23f3\u2728**",
        "error_generic": "\u274c \u041e\u0439! \u041e\u0448\u0438\u0431\u043a\u0430! \U0001f622 \u0421\u0441\u044b\u043b\u043a\u0430 \u043f\u0440\u0438\u0432\u0430\u0442\u043d\u0430\u044f/\u0437\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u0430. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u0443\u044e!",
        "error_50mb": "\u274c \u0421\u043b\u0438\u0448\u043a\u043e\u043c \u0431\u043e\u043b\u044c\u0448\u043e\u0439! \U0001f605 \u042d\u0442\u043e \u0432\u0438\u0434\u0435\u043e \u0431\u043e\u043b\u044c\u0448\u0435 300 \u041c\u0411. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043a\u043e\u0440\u043e\u0447\u0435!", 
        "error_no_img": "\u274c \u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b! \U0001f622 \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0434\u0440\u0443\u0433\u0443\u044e \u0441\u0441\u044b\u043b\u043a\u0443!",
        "images_received": "\u23f3 **\u041f\u043e\u043b\u0443\u0447\u0435\u043d\u043e {} \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0439.**",
        "select_lang": "\U0001f30d \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0432\u0430\u0448 \u044f\u0437\u044b\u043a! \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043d\u0438\u0436\u0435! \U0001f447", 
        "lang_set": "\u2705 \u042f\u0437\u044b\u043a \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d! \u041d\u0430\u0441\u043b\u0430\u0436\u0434\u0430\u0439\u0442\u0435\u0441\u044c! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d \u043f\u0430\u043a\u0435\u0442 ({} \u0441\u0441\u044b\u043b\u043e\u043a)**\n\u041a\u0430\u043a\u043e\u0439 \u0444\u043e\u0440\u043c\u0430\u0442?",
        "batch_dest": "\U0001f4e6 **\u041a\u0443\u0434\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c?**",
        "btn_chat": "\U0001f4e5 \u0412 \u0447\u0430\u0442", "btn_chan": "\U0001f4e2 \u0412 \u043a\u0430\u043d\u0430\u043b",
        "limit_reached": "\u26a0\ufe0f **\u041b\u0438\u043c\u0438\u0442 \u0434\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442!** \u0412\u044b \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043b\u0438 4 \u0411\u0415\u0421\u041f\u041b\u0410\u0422\u041d\u042b\u0425! \u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 20-\u0441\u0435\u043a \u0440\u0435\u043a\u043b\u0430\u043c\u0443 \u2192 \u041f\u043e\u043b\u0443\u0447\u0438\u0442\u0435 +1 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0443!",
        "refill_btn": "\U0001f513 \u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443 \u0438 \u043f\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u044c +1",
        "join_btn": "\U0001f4e2 \u041f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u044c\u0441\u044f \u043a \u043a\u0430\u043d\u0430\u043b\u0443", "check_btn": "\U0001f49c \u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0431\u0430\u043b\u0430\u043d\u0441",
        "limit_batch": "\u26a0\ufe0f **\u041b\u0438\u043c\u0438\u0442 \u043f\u0430\u043a\u0435\u0442\u0430 \u0434\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442 \u043d\u0430 {} \u0438\u0437 {}**\n\u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 20-\u0441\u0435\u043a \u0440\u0435\u043a\u043b\u0430\u043c\u0443 \u2192 +1 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0434\u043b\u044f \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u044f.",
        "batch_start": "\U0001f4e6 **\u041f\u0430\u043a\u0435\u0442 \u0437\u0430\u043f\u0443\u0449\u0435\u043d:** {} **{} \u0444\u0430\u0439\u043b\u043e\u0432**\n\u23f3 \u041e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430...",
        "batch_done": "\U0001f3c1 **\u0413\u043e\u0442\u043e\u0432\u043e!** \u2705 {} \u274c {}\n\U0001f4e5 {} \u0444\u0430\u0439\u043b\u043e\u0432 \u0437\u0434\u0435\u0441\u044c.",
        "batch_done_chan": "\U0001f3c1 **\u0413\u043e\u0442\u043e\u0432\u043e!** \u2705 {} \u274c {}\n\U0001f4e2 {} \u0444\u0430\u0439\u043b\u043e\u0432 \u043f\u0435\u0440\u0435\u0441\u043b\u0430\u043d\u043e!",
        "dl_video": "\U0001f4e5 \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0432\u0438\u0434\u0435\u043e...", "dl_audio": "\U0001f4e5 \u0418\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u0430\u0443\u0434\u0438\u043e...", "dl_image": "\U0001f4e5 \u0421\u043a\u0430\u0447\u0438\u0432\u0430\u043d\u0438\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0439...", "dl_sub": "\U0001f4e5 \u041f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u0435 \u0441\u0443\u0431\u0442\u0438\u0442\u0440\u043e\u0432...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c \u0417\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u043e/\u043f\u0440\u0438\u0432\u0430\u0442\u043d\u043e", "failed_generic": "\u274c \u041e\u0448\u0438\u0431\u043a\u0430",
        "menu_lang": "\U0001f30d \u042f\u0437\u044b\u043a", "menu_stats": "\U0001f4ca \u041c\u043e\u044f \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430", "menu_help": "\U0001f4ac \u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 / FAQ", "menu_join": "\U0001f4e2 \u041f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u044c\u0441\u044f \u043a \u043a\u0430\u043d\u0430\u043b\u0443",
        "menu_uploads": "\U0001f37f \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u0444\u0430\u043d\u0430\u0442\u043e\u0432", "menu_upload": "\U0001f4e4 \u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0444\u0430\u0439\u043b",
        "admin_upload_prompt": "\U0001f4c2 **\u0412\u0445\u043e\u0434\u044f\u0449\u0438\u0435 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u0444\u0430\u043d\u0430\u0442\u043e\u0432**",
        "user_upload_prompt": "\U0001f4e4 **\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0444\u0430\u0439\u043b**\n\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0432\u0438\u0434\u0435\u043e/\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435/\u0444\u0430\u0439\u043b \u0410\u0434\u043c\u0438\u043d\u0443. \u041b\u0438\u043c\u0438\u0442 5/24\u0447.",
        "upload_success_user": "\u2705 \u041e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e \u0410\u0434\u043c\u0438\u043d\u0443!",
        "upload_limit_reached": "\u26a0\ufe0f \u0414\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442 \u043b\u0438\u043c\u0438\u0442 \u0437\u0430\u0433\u0440\u0443\u0437\u043e\u043a 5/24\u0447.",
        "no_uploads": "\U0001f4ed \u0417\u0430\u0433\u0440\u0443\u0437\u043e\u043a \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.",
        "stats_msg": "\U0001f4ca **\u0412\u0430\u0448\u0430 \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430:**\n\u2022 \u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u043e\u043a: {}\n\u2022 \u041e\u0441\u0442\u0430\u043b\u043e\u0441\u044c \u043f\u0430\u043a\u0435\u0442\u043e\u0432: {}",
        "change_channel_prompt": "\U0001f504 **\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u043a\u0430\u043d\u0430\u043b \u0434\u043b\u044f \u043f\u0430\u043a\u0435\u0442\u043e\u0432**\n1. \u0423\u0431\u0435\u0434\u0438\u0442\u0435\u0441\u044c, \u0447\u0442\u043e \u044f \u0430\u0434\u043c\u0438\u043d \u0432 \u043d\u043e\u0432\u043e\u043c \u043a\u0430\u043d\u0430\u043b\u0435.\n2. \u041f\u0435\u0440\u0435\u0448\u043b\u0438\u0442\u0435 \u043b\u044e\u0431\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0438\u0437 \u044d\u0442\u043e\u0433\u043e \u043a\u0430\u043d\u0430\u043b\u0430 \u0441\u044e\u0434\u0430.",
        "disk_config_prompt": "\U0001f4be **\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 \u0434\u0438\u0441\u043a\u0430**\n\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u043c\u0438\u043d. \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0439 \u0434\u0438\u0441\u043a: **{} \u041c\u0411**\n\u0427\u0442\u043e\u0431\u044b \u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c: `/setdisk <\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435>`",
        "mtproto_config_prompt": "\u26a1 **\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 MTProto**\n\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u043c\u0430\u043a\u0441. \u0440\u0430\u0437\u043c\u0435\u0440 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438: **{} \u041c\u0411**\n\u0427\u0442\u043e\u0431\u044b \u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c: `/setmtproto <\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435>`",
        "free_panel_prompt": "\U0001f4e6 \u0411\u0415\u0421\u041f\u041b\u0410\u0422\u041d\u042b\u0415 \u0417\u0410\u0413\u0420\u0423\u0417\u041a\u0418\n\u0422\u0435\u043a\u0443\u0449\u0438\u0435 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u044b\u0435 \u0432 \u0434\u0435\u043d\u044c: {}",
        "reward_panel_prompt": "\U0001f381 \u041f\u0410\u041d\u0415\u041b\u042c \u041d\u0410\u0413\u0420\u0410\u0414\n\u0422\u0435\u043a\u0443\u0449\u0430\u044f: +{} \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0437\u0430 20-\u0441\u0435\u043a \u0440\u0435\u043a\u043b\u0430\u043c\u0443",
        "ad_panel_prompt": "\u2699\ufe0f \u041f\u0430\u043d\u0435\u043b\u044c \u0440\u0435\u043a\u043b\u0430\u043c\u044b\n\u0422\u0435\u043a\u0443\u0449\u0430\u044f: {}",
        "password_saved": "\U0001f510 \u041f\u0430\u0440\u043e\u043b\u044c \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d.",
        "password_too_long": "\u041f\u0430\u0440\u043e\u043b\u044c \u0434\u043e\u043b\u0436\u0435\u043d \u0431\u044b\u0442\u044c \u043d\u0435 \u0431\u043e\u043b\u0435\u0435 64 \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432.",
        "file_to_link_prompt": "\U0001f517 **\u0424\u0430\u0439\u043b-\u0432-\u0441\u0441\u044b\u043b\u043a\u0443**\n\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0444\u0430\u0439\u043b(\u044b), \u043a\u043e\u0442\u043e\u0440\u044b\u043c\u0438 \u0445\u043e\u0442\u0438\u0442\u0435 \u043f\u043e\u0434\u0435\u043b\u0438\u0442\u044c\u0441\u044f.",
        "link_invalid_expired": "\u274c \u042d\u0442\u0430 \u0441\u0441\u044b\u043b\u043a\u0430 \u043d\u0435\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u044c\u043d\u0430 \u0438\u043b\u0438 \u0438\u0441\u0442\u0435\u043a\u043b\u0430.",
        "link_limit_reached": "\u26d4 \u042d\u0442\u0430 \u0441\u0441\u044b\u043b\u043a\u0430 \u0434\u043e\u0441\u0442\u0438\u0433\u043b\u0430 \u043b\u0438\u043c\u0438\u0442\u0430 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u044f.",
        "link_password_protected": "\U0001f510 \u042d\u0442\u0430 \u0441\u0441\u044b\u043b\u043a\u0430 \u0437\u0430\u0449\u0438\u0449\u0435\u043d\u0430 \u043f\u0430\u0440\u043e\u043b\u0435\u043c. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c.",
        "files_sent": "\u2705 \u0412\u0430\u0448\u0438 \u0444\u0430\u0439\u043b\u044b \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u044b.",
        "file_added": "\U0001f4e5 \u0414\u043e\u0431\u0430\u0432\u043b\u0435\u043d \u0444\u0430\u0439\u043b #{}. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0435\u0449\u0435 \u0438\u043b\u0438 \u043d\u0430\u0436\u043c\u0438\u0442\u0435 \u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443.",
        "fl_cancelled": "\u0424\u0430\u0439\u043b-\u0432-\u0441\u0441\u044b\u043b\u043a\u0443 \u043e\u0442\u043c\u0435\u043d\u0435\u043d",
        "fl_start_again": "\u041d\u0430\u0447\u043d\u0438\u0442\u0435 \u0424\u0430\u0439\u043b-\u0432-\u0441\u0441\u044b\u043b\u043a\u0443 \u0437\u0430\u043d\u043e\u0432\u043e \u0441 /filetolink",
        "fl_choose_expiry": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0440\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0441\u0441\u044b\u043b\u043a\u0438:",
        "fl_expiry_updated": "\u0421\u0440\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d",
        "fl_choose_max_uses": "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043c\u0430\u043a\u0441. \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u0443\u0441\u043f\u0435\u0448\u043d\u044b\u0445 \u0434\u043e\u0441\u0442\u0430\u0432\u043e\u043a:",
        "fl_uses_updated": "\u041b\u0438\u043c\u0438\u0442 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u044f \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d",
        "fl_set_password": "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c \u0438\u043b\u0438 /clearpassword \u0434\u043b\u044f \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044f.",
        "fl_link_created": "\u0421\u0441\u044b\u043b\u043a\u0430 \u0441\u043e\u0437\u0434\u0430\u043d\u0430",
        "fl_link_ready": "\U0001f517 \u0412\u0430\u0448\u0430 \u0441\u0441\u044b\u043b\u043a\u0430 \u0433\u043e\u0442\u043e\u0432\u0430:\n{}\n\u0424\u0430\u0439\u043b\u043e\u0432: {}\n\u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c: 1 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u0430\u044f \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0432 \u0434\u0435\u043d\u044c",
        "fl_daily_limit": "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u044b\u0439 \u043b\u0438\u043c\u0438\u0442 \u0434\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442. \u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u0440\u0435\u043a\u043b\u0430\u043c\u0443, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c \u0431\u043e\u043b\u044c\u0448\u0435.",
        "fl_ad_busy": "\u26a0\ufe0f \u0420\u0435\u043a\u043b\u0430\u043c\u043d\u044b\u0439 \u0441\u0435\u0440\u0432\u0435\u0440 \u0437\u0430\u043d\u044f\u0442.",
        "admin_skipped": "\u2705 \u041f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e!",
        "admin_bypassed": "\u2705 \u041e\u0431\u043e\u0439\u0434\u0435\u043d\u043e",
        "free_set": "\u2705 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u043e \u043d\u0430 {}!",
        "free_updated": "\u2705 \u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u044b\u0435 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u044b \u0434\u043e {}!",
        "reward_set": "\u2705 \u041d\u0430\u0433\u0440\u0430\u0434\u0430 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0430 \u043d\u0430 +{}!",
        "reward_updated": "\u2705 \u041d\u0430\u0433\u0440\u0430\u0434\u0430 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0430 \u0434\u043e +{}!",
        "mode_updated": "\u2705 \u0420\u0435\u0436\u0438\u043c: {}",
        "support_opened": "\u270d\ufe0f \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435/\u0444\u043e\u0442\u043e/\u0432\u0438\u0434\u0435\u043e/\u0444\u0430\u0439\u043b \u043d\u0438\u0436\u0435.",
        "admin_reply_mode": "\u270d\ufe0f \u041e\u0442\u0432\u0435\u0442\u0438\u0442\u044c {}:",
        "user_reply_mode": "\u270d\ufe0f \u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u0435 \u043d\u0438\u0436\u0435",
        "support_closed": "\U0001f512 \u0417\u0430\u043a\u0440\u044b\u0442\u043e",
        "drop_cancelled": "\u274c \u041e\u0442\u043c\u0435\u043d\u0435\u043d\u043e",
        "drop_no_items": "\u26a0\ufe0f \u041d\u0435\u0442 \u044d\u043b\u0435\u043c\u0435\u043d\u0442\u043e\u0432!",
        "drop_timer_set": "{} \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u043e!",
        "drop_broadcasting": "\U0001f680 \u0422\u0440\u0430\u043d\u0441\u043b\u044f\u0446\u0438\u044f {} \u044d\u043b\u0435\u043c\u0435\u043d\u0442\u043e\u0432 \u0434\u043b\u044f {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\n\u0410\u0432\u0442\u043e\u0443\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0447\u0435\u0440\u0435\u0437 {}\n\u041d\u0430\u0436\u043c\u0438\u0442\u0435, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u0431\u0440\u0430\u0442\u044c:",
        "drop_done": "\u2705 \u0422\u0440\u0430\u043d\u0441\u043b\u044f\u0446\u0438\u044f \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0430 \u0434\u043b\u044f {}",
        "age_expired": "\u23f3 \u0418\u0441\u0442\u0435\u043a\u043b\u043e!",
        "age_claimed": "\u274c \u0423\u0436\u0435 \u0437\u0430\u0431\u0440\u0430\u043d\u043e!",
        "age_verified": "\u041f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e!",
        "age_denied": "\u274c \u041e\u0442\u043a\u0430\u0437\u0430\u043d\u043e. \u0414\u043e\u043b\u0436\u043d\u043e \u0431\u044b\u0442\u044c 18+",
        "lang_updated": "\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e!",
        "batch_expired": "\u0418\u0441\u0442\u0435\u043a\u043b\u043e",
        "batch_loading": "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...",
        "batch_no_channel": "\u041a\u0430\u043d\u0430\u043b \u043d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d!",
        "batch_setup_prompt": "\U0001f4e6 \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430: \u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u0431\u043e\u0442\u0430 \u0430\u0434\u043c\u0438\u043d\u043e\u043c \u0432 \u043a\u0430\u043d\u0430\u043b\u0435 \u0438 \u043f\u0435\u0440\u0435\u0448\u043b\u0438\u0442\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0441\u044e\u0434\u0430",
        "batch_mode_activated": "\u0420\u0435\u0436\u0438\u043c \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d!",
        "batch_change_dest": "\U0001f504 **\u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u043a\u0430\u043d\u0430\u043b \u043d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u044f**\n\u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u0431\u043e\u0442\u0430 \u0430\u0434\u043c\u0438\u043d\u043e\u043c \u0432 \u043d\u043e\u0432\u043e\u043c \u043a\u0430\u043d\u0430\u043b\u0435, \u0437\u0430\u0442\u0435\u043c \u043f\u0435\u0440\u0435\u0448\u043b\u0438\u0442\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0441\u044e\u0434\u0430.",
        "join_channel_first_alert": "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u0435\u0441\u044c \u043a \u043a\u0430\u043d\u0430\u043b\u0443! \U0001f4e2 \u041e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e!",
        "join_channel_first": "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u0435\u0441\u044c \u043a \u043a\u0430\u043d\u0430\u043b\u0443! \U0001f4e2",
        "watch_timer_first": "\u23f0 \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0438 \u043f\u043e\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 20-\u0441\u0435\u043a \u0442\u0430\u0439\u043c\u0435\u0440!",
        "test_ad_verified": "\u2705 \u0422\u0435\u0441\u0442\u043e\u0432\u0430\u044f \u0440\u0435\u043a\u043b\u0430\u043c\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u0430! +1",
        "test_ad_verified_msg": "\u2705 **\u0422\u0415\u0421\u0422\u041e\u0412\u0410\u042f \u0420\u0415\u041a\u041b\u0410\u041c\u0410 \u041f\u0420\u041e\u0412\u0415\u0420\u0415\u041d\u0410!**\n\u041d\u0430\u0433\u0440\u0430\u0434\u0430: +1 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0430!",
        "finish_timer_first": "\u23f0 \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u0435 20-\u0441\u0435\u043a \u0442\u0430\u0439\u043c\u0435\u0440!",
        "verified_added": "\u041f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e! +1 \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e",
        "resume_prompt": "\u2705 \u041f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e! \u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u043e +1. \u0412\u043e\u0437\u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c?",
        "refilled_download": "\u2705 \u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u043e +1! \u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u0435 \u0441\u043d\u043e\u0432\u0430.",
        "fetching_bundle": "\u2705 \u041f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e! \u041f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u0435 \u043f\u0430\u043a\u0435\u0442\u0430...",
        "outdated_button": "\u042d\u0442\u0430 \u043a\u043d\u043e\u043f\u043a\u0430 \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u0430. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0441\u043d\u043e\u0432\u0430.",
        "stopping": "\u041e\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430...",
        "stopped": "\U0001f6d1 \u041e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
        "resuming": "\u0412\u043e\u0437\u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435...",
        "checking_vault": "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0430 \u0438 \u043d\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u0441\u0435\u0440\u0432\u0435\u0440\u0430...",
        "server_busy": "\u23f3 **\u0421\u0435\u0440\u0432\u0435\u0440 \u0437\u0430\u043d\u044f\u0442**\n\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0445: {}/{}\n\u0421\u0432\u043e\u0431\u043e\u0434\u043d\u043e: {} \u041c\u0411\n\u041e\u0447\u0435\u0440\u0435\u0434\u044c: #{}\n\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438!",
        "simulated": "\U0001f6e0 \u0421\u0438\u043c\u0443\u043b\u0438\u0440\u043e\u0432\u0430\u043d\u043e! \u0422\u0435\u043f\u0435\u0440\u044c \u043d\u0430\u0436\u043c\u0438\u0442\u0435 \u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0438 \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c +1",
        "server_unreachable": "\u274c \u0421\u0435\u0440\u0432\u0435\u0440 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d",
        "monetag_failed_twice": "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u0435 \u0434\u0432\u0435 \u043d\u0435\u0443\u0434\u0430\u0447\u043d\u044b\u0435 \u043f\u043e\u043f\u044b\u0442\u043a\u0438 Monetag.",
        "monetag_fallback_prompt": "\U0001f310 Monetag \u043d\u0435 \u0441\u0440\u0430\u0431\u043e\u0442\u0430\u043b \u0434\u0432\u0430\u0436\u0434\u044b. \u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u0441 Adsterra:",
        "adsterra_ready": "\u0420\u0435\u0437\u0435\u0440\u0432\u043d\u044b\u0439 \u0432\u0430\u0440\u0438\u0430\u043d\u0442 Adsterra \u0433\u043e\u0442\u043e\u0432",
        "finish_monetag": "\U0001f4fa \u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u0435 \u0440\u0435\u043a\u043b\u0430\u043c\u0443 Monetag \u0432 Mini App, \u0437\u0430\u0442\u0435\u043c \u043f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0441\u043d\u043e\u0432\u0430.",
        "monetag_failed_use_adsterra": "Monetag \u043d\u0435 \u0441\u0440\u0430\u0431\u043e\u0442\u0430\u043b \u0434\u0432\u0430\u0436\u0434\u044b. \u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u0440\u0435\u0437\u0435\u0440\u0432\u043d\u044b\u0439 \u0432\u0430\u0440\u0438\u0430\u043d\u0442 Adsterra \u043d\u0438\u0436\u0435.",
        "ad_link_expired": "\u0421\u0440\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0440\u0435\u043a\u043b\u0430\u043c\u043d\u043e\u0439 \u0441\u0441\u044b\u043b\u043a\u0438 \u0438\u0441\u0442\u0435\u043a. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0441\u043d\u043e\u0432\u0430.",
        "ad_verified_added": "\u2705 \u0420\u0435\u043a\u043b\u0430\u043c\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u0430! +{} \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e",
        "test_ad_completed": "\u2705 \u0422\u0415\u0421\u0422\u041e\u0412\u0410\u042f \u0420\u0415\u041a\u041b\u0410\u041c\u0410 \u041f\u0420\u041e\u0412\u0415\u0420\u0415\u041d\u0410\n\u041d\u0430\u0433\u0440\u0430\u0434\u0430 \u043d\u0430\u0447\u0438\u0441\u043b\u0435\u043d\u0430: +{} \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430.",
        "sponsor_viewed": "\u2705 \u0421\u043f\u043e\u043d\u0441\u043e\u0440 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d! +{} \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e",
        "refilled_send_again": "\u2705 \u041f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u043e +{}! \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0441\u043d\u043e\u0432\u0430.",
        "queued": "\u23f3 \u0412 \u043e\u0447\u0435\u0440\u0435\u0434\u0438 #{}",
        "banned": "\U0001f6ab \u0412\u044b \u0437\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u044b.",
        "no_links": "\u274c \u0421\u0441\u044b\u043b\u043a\u0438 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b.",
        "batch_count": "\U0001f4e6 \u041f\u0430\u043a\u0435\u0442 {} \u0441\u0441\u044b\u043b\u043e\u043a",
        "restore_invalid_json": "\u274c \u041e\u0448\u0438\u0431\u043a\u0430 \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f: **{}** \u043d\u0435 \u044f\u0432\u043b\u044f\u0435\u0442\u0441\u044f \u0434\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u043c JSON.",
        "restore_failed": "\u274c \u041e\u0448\u0438\u0431\u043a\u0430 \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f: {}",
        "restore_success": "\u2705 **\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0441\u043f\u0435\u0448\u043d\u043e!**\n\u0424\u0430\u0439\u043b: **{}**\n\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u043e **{}** \u0437\u0430\u043f\u0438\u0441\u0435\u0439.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u043d\u043e\u0432\u043e\u0435 \u043f\u0440\u0438\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435. \u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 `{bot_name}` \u0434\u043b\u044f \u0438\u043c\u0435\u043d\u0438 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0431\u043e\u0442\u0430.",
        "admin_welcome_updated": "\u2705 \u041f\u0440\u0438\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e!",
        "menu_edit_welcome": "\u270f\ufe0f \u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u043f\u0440\u0438\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435",
        "cached_instant_video": "\u26a1 \u041c\u0433\u043d\u043e\u0432\u0435\u043d\u043d\u044b\u0439 \u043a\u044d\u0448 [{}] {} {}",
        "cached_instant_audio": "\u26a1 **\u041c\u0433\u043d\u043e\u0432\u0435\u043d\u043d\u044b\u0439 \u043a\u044d\u0448** `{}`",
        "cached_instant_image": "\u26a1 **\u041c\u0433\u043d\u043e\u0432\u0435\u043d\u043d\u044b\u0439 \u043a\u044d\u0448** `{}`",
        "auto_delete_9m": "\u23f3 \u0410\u0432\u0442\u043e\u0443\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0447\u0435\u0440\u0435\u0437 9 \u043c\u0438\u043d",
        "download_success": "\u2705 \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0443\u0441\u043f\u0435\u0448\u043d\u0430!"
    },
    "pt": {
        "welcome": "\U0001f680 **BEM-VINDO AO MICHAELBBC VAULT - BAIXADOR DE M\u00cdDIA COMPLETO!**\n\n\U0001f525 O QUE POSSO FAZER:\n\U0001f3ac V\u00cdDEOS HD Sem Marca D'\u00e1gua!\n\U0001f3b5 \u00c1UDIO MP3 192kbps!\n??\ufe0f IMAGENS Extra\u00e7\u00e3o TOTAL!\n\U0001f4dd LEGENDAS Auto!\n\U0001f4e6 LOTES 100+ Links!\n\u26a1 CACHE 1 Seg!\n\U0001f48e COFRE Para Sempre!\n\U0001f4e4 ENVIAR ARQUIVOS!\n\U0001f517 ARQUIVO-PARA-LINK: Crie links compartilh\u00e1veis!\n\n\U0001f449 COLE UM LINK PARA COME\u00c7AR! \U0001f447",
        "btn_video": "\U0001f3ac V\u00eddeo (MP4)", "btn_audio": "\U0001f3b5 \u00c1udio (MP3)", "btn_image": "\U0001f5bc\ufe0f Imagens", "btn_sub": "\U0001f4dd Legendas (SRT)",
        "ask_format": "\U0001f447 **INCR\u00cdVEL! Qual formato voc\u00ea quer? Escolha abaixo!**",
        "fetching": "\U0001f4e5 **Buscando seu {}... Aguarde! \u23f3\u2728**",
        "error_generic": "\u274c Ops! Falhou! \U0001f622 Link privado/bloqueado. Tente um link p\u00fablico!",
        "error_50mb": "\u274c Muito grande! \U0001f605 Este v\u00eddeo tem mais de 300MB. Tente um mais curto!", 
        "error_no_img": "\u274c Nenhuma imagem encontrada! \U0001f622 Tente outro link!",
        "images_received": "\u23f3 **{} Imagens recebidas.**",
        "select_lang": "\U0001f30d Selecione seu idioma! Escolha abaixo! \U0001f447", 
        "lang_set": "\u2705 Idioma definido! Aproveite! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Lote Detectado ({} links)**\nQual formato?",
        "batch_dest": "\U0001f4e6 **Para onde enviar?**",
        "btn_chat": "\U0001f4e5 No Chat", "btn_chan": "\U0001f4e2 Para o Canal",
        "limit_reached": "\u26a0\ufe0f **Limite Atingido!** Voc\u00ea usou 4 GR\u00c1TIS! Assista a um an\u00fancio de 20s \u2192 Ganhe +1 download!",
        "refill_btn": "\U0001f513 Abrir Link e Recarregar +1",
        "join_btn": "\U0001f4e2 Entrar no Canal", "check_btn": "\U0001f49c Verificar Saldo",
        "limit_batch": "\u26a0\ufe0f **Limite do Lote Atingido em {} de {}**\nAssista a um an\u00fancio de 20s \u2192 +1 download para continuar.",
        "batch_start": "\U0001f4e6 **Lote Iniciado:** {} **{} arquivos**\n\u23f3 Processando...",
        "batch_done": "\U0001f3c1 **Conclu\u00eddo!** \u2705 {} \u274c {}\n\U0001f4e5 {} arquivos aqui.",
        "batch_done_chan": "\U0001f3c1 **Conclu\u00eddo!** \u2705 {} \u274c {}\n\U0001f4e2 {} arquivos encaminhados!",
        "dl_video": "\U0001f4e5 Baixando v\u00eddeo...", "dl_audio": "\U0001f4e5 Extraindo \u00e1udio...", "dl_image": "\U0001f4e5 Extraindo imagens...", "dl_sub": "\U0001f4e5 Buscando legendas...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Bloqueado/privado", "failed_generic": "\u274c Falhou",
        "menu_lang": "\U0001f30d Idioma", "menu_stats": "\U0001f4ca Minhas Estat\u00edsticas", "menu_help": "\U0001f4ac Suporte / FAQ", "menu_join": "\U0001f4e2 Entrar no Canal",
        "menu_uploads": "\U0001f37f Envios de F\u00e3s", "menu_upload": "\U0001f4e4 Enviar Arquivo",
        "admin_upload_prompt": "\U0001f4c2 **Caixa de Entrada de Envios de F\u00e3s**",
        "user_upload_prompt": "\U0001f4e4 **Enviar Arquivo**\nEnvie v\u00eddeo/imagem/arquivo para o Admin. Limite 5/24h.",
        "upload_success_user": "\u2705 Enviado para o Admin!",
        "upload_limit_reached": "\u26a0\ufe0f Limite de envios 5/24h atingido.",
        "no_uploads": "\U0001f4ed Nenhum envio ainda.",
        "stats_msg": "\U0001f4ca **Suas Estat\u00edsticas:**\n\u2022 Downloads Restantes: {}\n\u2022 Lotes Restantes: {}",
        "change_channel_prompt": "\U0001f504 **Alterar Canal de Lotes**\n1. Certifique-se de que sou admin no novo canal.\n2. Encaminhe qualquer mensagem desse canal para c\u00e1.",
        "disk_config_prompt": "\U0001f4be **Config de Disco**\nM\u00ednimo de disco livre atual: **{}MB**\nPara alterar: `/setdisk <valor>`",
        "mtproto_config_prompt": "\u26a1 **Config MTProto**\nMax de upload atual: **{}MB**\nPara alterar: `/setmtproto <valor>`",
        "free_panel_prompt": "\U0001f4e6 DOWNLOADS GR\u00c1TIS\nGr\u00e1tis atuais por dia: {}",
        "reward_panel_prompt": "\U0001f381 PAINEL DE RECOMPENSAS\nAtual: +{} download por an\u00fancio de 20s",
        "ad_panel_prompt": "\u2699\ufe0f Painel de An\u00fancios\nAtual: {}",
        "password_saved": "\U0001f510 Senha salva.",
        "password_too_long": "A senha deve ter 64 caracteres ou menos.",
        "file_to_link_prompt": "\U0001f517 **Arquivo-para-Link**\nEnvie o(s) arquivo(s) que deseja compartilhar.",
        "link_invalid_expired": "\u274c Este link \u00e9 inv\u00e1lido ou expirou.",
        "link_limit_reached": "\u26d4 Este link atingiu seu limite de uso.",
        "link_password_protected": "\U0001f510 Este link est\u00e1 protegido por senha. Envie a senha.",
        "files_sent": "\u2705 Seus arquivos foram enviados.",
        "file_added": "\U0001f4e5 Arquivo #{} adicionado. Envie mais ou toque em Criar Link.",
        "fl_cancelled": "Arquivo-para-Link cancelado",
        "fl_start_again": "Inicie Arquivo-para-Link novamente com /filetolink",
        "fl_choose_expiry": "Escolha a expira\u00e7\u00e3o do link:",
        "fl_expiry_updated": "Expira\u00e7\u00e3o atualizada",
        "fl_choose_max_uses": "Escolha o m\u00e1ximo de entregas bem-sucedidas:",
        "fl_uses_updated": "Limite de uso atualizado",
        "fl_set_password": "Envie uma senha ou /clearpassword para remover.",
        "fl_link_created": "Link criado",
        "fl_link_ready": "\U0001f517 Seu link est\u00e1 pronto:\n{}\nArquivos: {}\nCusto: 1 download di\u00e1rio gr\u00e1tis",
        "fl_daily_limit": "Limite di\u00e1rio gr\u00e1tis atingido. Assista a um an\u00fancio para ganhar mais.",
        "fl_ad_busy": "\u26a0\ufe0f Servidor de an\u00fancios ocupado.",
        "admin_skipped": "\u2705 Ignorado!",
        "admin_bypassed": "\u2705 Ignorado",
        "free_set": "\u2705 Gr\u00e1tis definido para {}!",
        "free_updated": "\u2705 Downloads Gr\u00e1tis atualizados para {}!",
        "reward_set": "\u2705 Recompensa definida para +{}!",
        "reward_updated": "\u2705 Recompensa atualizada para +{}!",
        "mode_updated": "\u2705 Modo: {}",
        "support_opened": "\u270d\ufe0f Envie mensagem/foto/v\u00eddeo/arquivo abaixo.",
        "admin_reply_mode": "\u270d\ufe0f Responder a {}:",
        "user_reply_mode": "\u270d\ufe0f Digite o acompanhamento abaixo",
        "support_closed": "\U0001f512 Fechado",
        "drop_cancelled": "\u274c Cancelado",
        "drop_no_items": "\u26a0\ufe0f Sem itens!",
        "drop_timer_set": "{} definido!",
        "drop_broadcasting": "\U0001f680 Transmitindo {} itens para {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\nAuto-exclui em {}\nToque para reivindicar:",
        "drop_done": "\u2705 Transmiss\u00e3o feita para {}",
        "age_expired": "\u23f3 Expirado!",
        "age_claimed": "\u274c J\u00e1 reivindicado!",
        "age_verified": "Verificado!",
        "age_denied": "\u274c Negado. Deve ser 18+",
        "lang_updated": "Atualizado!",
        "batch_expired": "Expirado",
        "batch_loading": "Carregando...",
        "batch_no_channel": "Nenhum canal vinculado!",
        "batch_setup_prompt": "\U0001f4e6 Configura\u00e7\u00e3o: Torne o bot admin no canal e encaminhe uma mensagem aqui",
        "batch_mode_activated": "Modo ativado!",
        "batch_change_dest": "\U0001f504 **Alterar Canal de Destino**\nTorne o bot admin no novo canal, depois encaminhe uma mensagem aqui.",
        "join_channel_first_alert": "Entre no canal primeiro! \U0001f4e2 Deve entrar!",
        "join_channel_first": "Entre no canal primeiro! \U0001f4e2",
        "watch_timer_first": "\u23f0 Abra o link e assista ao temporizador de 20s primeiro!",
        "test_ad_verified": "\u2705 An\u00fancio de Teste Verificado! +1",
        "test_ad_verified_msg": "\u2705 **AN\u00daNCIO DE TESTE VERIFICADO!**\nRecompensa: +1 download recarregado!",
        "finish_timer_first": "\u23f0 Termine o temporizador de 20s primeiro!",
        "verified_added": "Verificado! +1 adicionado",
        "resume_prompt": "\u2705 Verificado! Recarregado +1. Retomar?",
        "refilled_download": "\u2705 Recarregado +1! Baixe novamente.",
        "fetching_bundle": "\u2705 Verificado! Buscando pacote...",
        "outdated_button": "Este bot\u00e3o est\u00e1 desatualizado. Envie seu link novamente.",
        "stopping": "Parando...",
        "stopped": "\U0001f6d1 Parado",
        "resuming": "Retomando...",
        "checking_vault": "Verificando cofre e carga do servidor...",
        "server_busy": "\u23f3 **Servidor Ocupado**\nAtivos: {}/{}\nLivre: {}MB\nFila: #{}\nIniciar\u00e1 auto!",
        "simulated": "\U0001f6e0 Simulado! Agora toque em Verificar e Obter +1",
        "server_unreachable": "\u274c Servidor inacess\u00edvel",
        "monetag_failed_twice": "Complete duas tentativas falhas de Monetag primeiro.",
        "monetag_fallback_prompt": "\U0001f310 Monetag falhou duas vezes. Continue com Adsterra:",
        "adsterra_ready": "Fallback de Adsterra pronto",
        "finish_monetag": "\U0001f4fa Termine o an\u00fancio Monetag no Mini App, depois verifique.",
        "monetag_failed_use_adsterra": "Monetag falhou duas vezes. Use o fallback de Adsterra abaixo.",
        "ad_link_expired": "Link de an\u00fancio expirado. Envie seu link novamente.",
        "ad_verified_added": "\u2705 An\u00fancio verificado! +{} adicionado",
        "test_ad_completed": "\u2705 AN\u00daNCIO DE TESTE VERIFICADO\nRecompensa creditada: +{} download.",
        "sponsor_viewed": "\u2705 Patrocinador visto! +{} adicionado",
        "refilled_send_again": "\u2705 Recarregado +{}! Envie seu link novamente.",
        "queued": "\u23f3 Na fila #{}",
        "banned": "\U0001f6ab Voc\u00ea est\u00e1 banido.",
        "no_links": "\u274c Nenhum link encontrado.",
        "batch_count": "\U0001f4e6 Lote {} links",
        "restore_invalid_json": "\u274c Falha na restaura\u00e7\u00e3o: **{}** n\u00e3o \u00e9 JSON v\u00e1lido.",
        "restore_failed": "\u274c Falha na restaura\u00e7\u00e3o: {}",
        "restore_success": "\u2705 **Restaura\u00e7\u00e3o Bem-sucedida!**\nArquivo: **{}**\nRestauradas **{}** entradas.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Envie a nova Mensagem de Boas-vindas. Use `{bot_name}` para o nome de usu\u00e1rio.",
        "admin_welcome_updated": "\u2705 Mensagem de boas-vindas atualizada!",
        "menu_edit_welcome": "\u270f\ufe0f Editar Mensagem de Boas-vindas",
        "cached_instant_video": "\u26a1 Cache Instant\u00e2neo [{}] {} {}",
        "cached_instant_audio": "\u26a1 **Cache Instant\u00e2neo** `{}`",
        "cached_instant_image": "\u26a1 **Cache Instant\u00e2neo** `{}`",
        "auto_delete_9m": "\u23f3 Auto-exclui em 9 mins",
        "download_success": "\u2705 Download bem-sucedido!"
    },
    "id": {
        "welcome": "\U0001f680 **SELAMAT DATANG DI MICHAELBBC VAULT - PENGUNDUH MEDIA LENGKAP!**\n\n\U0001f525 APA YANG BISA SAYA LAKUKAN:\n\U0001f3ac VIDEO HD Tanpa Watermark!\n\U0001f3b5 AUDIO MP3 192kbps!\n\U0001f5bc\ufe0f GAMBAR Ekstraksi SEMUA!\n\U0001f4dd SUBTITLE Otomatis!\n\U0001f4e6 BATCH 100+ Link!\n\u26a1 CACHE 1 Detik!\n\U0001f48e BRANKAS Selamanya!\n\U0001f4e4 UNGGAH FILE!\n\U0001f517 FILE-KE-LINK: Buat link yang bisa dibagikan!\n\n\U0001f449 TEMPEL LINK UNTUK MEMULAI! \U0001f447",
        "btn_video": "\U0001f3ac Video (MP4)", "btn_audio": "\U0001f3b5 Audio (MP3)", "btn_image": "\U0001f5bc\ufe0f Gambar", "btn_sub": "\U0001f4dd Subtitle (SRT)",
        "ask_format": "\U0001f447 **KEREN! Format apa yang Anda inginkan? Pilih di bawah!**",
        "fetching": "\U0001f4e5 **Mengambil {} Anda... Tunggu sebentar! \u23f3\u2728**",
        "error_generic": "\u274c Ups! Gagal! \U0001f622 Link pribadi/diblokir. Coba link publik!",
        "error_50mb": "\u274c Terlalu besar! \U0001f605 Video ini lebih dari 300MB. Coba yang lebih pendek!", 
        "error_no_img": "\u274c Tidak ada gambar ditemukan! \U0001f622 Coba link lain!",
        "images_received": "\u23f3 **{} Gambar diterima.**",
        "select_lang": "\U0001f30d Pilih bahasa Anda! Pilih di bawah! \U0001f447", 
        "lang_set": "\u2705 Bahasa diatur! Nikmati! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Batch Terdeteksi ({} link)**\nFormat apa?",
        "batch_dest": "\U0001f4e6 **Kirim ke mana?**",
        "btn_chat": "\U0001f4e5 Di Chat", "btn_chan": "\U0001f4e2 Ke Channel",
        "limit_reached": "\u26a0\ufe0f **Batas Tercapai!** Anda menggunakan 4 GRATIS! Tonton iklan 20d \u2192 Dapatkan +1 unduhan!",
        "refill_btn": "\U0001f513 Buka Link & Isi Ulang +1",
        "join_btn": "\U0001f4e2 Gabung Channel", "check_btn": "\U0001f49c Cek Saldo",
        "limit_batch": "\u26a0\ufe0f **Batas Batch Tercapai pada {} dari {}**\nTonton iklan 20d \u2192 +1 unduhan untuk melanjutkan.",
        "batch_start": "\U0001f4e6 **Batch Dimulai:** {} **{} file**\n\u23f3 Memproses...",
        "batch_done": "\U0001f3c1 **Selesai!** \u2705 {} \u274c {}\n\U0001f4e5 {} file di sini.",
        "batch_done_chan": "\U0001f3c1 **Selesai!** \u2705 {} \u274c {}\n\U0001f4e2 {} file diteruskan!",
        "dl_video": "\U0001f4e5 Mengunduh video...", "dl_audio": "\U0001f4e5 Mengekstrak audio...", "dl_image": "\U0001f4e5 Mengekstrak gambar...", "dl_sub": "\U0001f4e5 Mengambil subtitle...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Diblokir/pribadi", "failed_generic": "\u274c Gagal",
        "menu_lang": "\U0001f30d Bahasa", "menu_stats": "\U0001f4ca Statistik Saya", "menu_help": "\U0001f4ac Dukungan / FAQ", "menu_join": "\U0001f4e2 Gabung Channel",
        "menu_uploads": "\U0001f37f Unggahan Penggemar", "menu_upload": "\U0001f4e4 Unggah File",
        "admin_upload_prompt": "\U0001f4c2 **Kotak Masuk Unggahan Penggemar**",
        "user_upload_prompt": "\U0001f4e4 **Unggah File**\nKirim video/gambar/file ke Admin. Batas 5/24jam.",
        "upload_success_user": "\u2705 Terkirim ke Admin!",
        "upload_limit_reached": "\u26a0\ufe0f Batas unggahan 5/24jam tercapai.",
        "no_uploads": "\U0001f4ed Belum ada unggahan.",
        "stats_msg": "\U0001f4ca **Statistik Anda:**\n\u2022 Sisa Unduhan: {}\n\u2022 Sisa Batch: {}",
        "change_channel_prompt": "\U0001f504 **Ubah Channel Batch**\n1. Pastikan saya adalah admin di channel baru.\n2. Teruskan pesan apa pun dari channel tersebut ke sini.",
        "disk_config_prompt": "\U0001f4be **Konfigurasi Disk**\nMin disk bebas saat ini: **{}MB**\nUntuk mengubah: `/setdisk <nilai>`",
        "mtproto_config_prompt": "\u26a1 **Konfigurasi MTProto**\nMax unggah saat ini: **{}MB**\nUntuk mengubah: `/setmtproto <nilai>`",
        "free_panel_prompt": "\U0001f4e6 UNDUHAN GRATIS\nGratis saat ini per hari: {}",
        "reward_panel_prompt": "\U0001f381 PANEL HADIAH\nSaat ini: +{} unduhan per iklan 20d",
        "ad_panel_prompt": "\u2699\ufe0f Panel Iklan\nSaat ini: {}",
        "password_saved": "\U0001f510 Kata sandi disimpan.",
        "password_too_long": "Kata sandi harus 64 karakter atau kurang.",
        "file_to_link_prompt": "\U0001f517 **File-ke-Link**\nKirim file yang ingin Anda bagikan.",
        "link_invalid_expired": "\u274c Link ini tidak valid atau kedaluwarsa.",
        "link_limit_reached": "\u26d4 Link ini mencapai batas penggunaan.",
        "link_password_protected": "\U0001f510 Link ini dilindungi kata sandi. Kirim kata sandi.",
        "files_sent": "\u2705 File Anda telah dikirim.",
        "file_added": "\U0001f4e5 File #{} ditambahkan. Kirim lebih banyak, atau ketuk Buat Link.",
        "fl_cancelled": "File-ke-Link dibatalkan",
        "fl_start_again": "Mulai File-ke-Link lagi dengan /filetolink",
        "fl_choose_expiry": "Pilih kedaluwarsa link:",
        "fl_expiry_updated": "Kedaluwarsa diperbarui",
        "fl_choose_max_uses": "Pilih max pengiriman berhasil:",
        "fl_uses_updated": "Batas penggunaan diperbarui",
        "fl_set_password": "Kirim kata sandi, atau /clearpassword untuk menghapus.",
        "fl_link_created": "Link dibuat",
        "fl_link_ready": "\U0001f517 Link Anda siap:\n{}\nFile: {}\nBiaya: 1 unduhan harian gratis",
        "fl_daily_limit": "Batas harian gratis tercapai. Tonton iklan untuk mendapatkan lebih banyak.",
        "fl_ad_busy": "\u26a0\ufe0f Server iklan sibuk.",
        "admin_skipped": "\u2705 Dilewati!",
        "admin_bypassed": "\u2705 Dilewati",
        "free_set": "\u2705 Gratis diatur ke {}!",
        "free_updated": "\u2705 Unduhan Gratis diperbarui ke {}!",
        "reward_set": "\u2705 Hadiah diatur ke +{}!",
        "reward_updated": "\u2705 Hadiah diperbarui ke +{}!",
        "mode_updated": "\u2705 Mode: {}",
        "support_opened": "\u270d\ufe0f Kirim pesan/foto/video/file di bawah.",
        "admin_reply_mode": "\u270d\ufe0f Balas ke {}:",
        "user_reply_mode": "\u270d\ufe0f Ketik tindak lanjut di bawah",
        "support_closed": "\U0001f512 Ditutup",
        "drop_cancelled": "\u274c Dibatalkan",
        "drop_no_items": "\u26a0\ufe0f Tidak ada item!",
        "drop_timer_set": "{} diatur!",
        "drop_broadcasting": "\U0001f680 Menyiarakan {} item ke {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\nHapus otomatis dalam {}\nKetuk untuk klaim:",
        "drop_done": "\u2705 Siaran selesai ke {}",
        "age_expired": "\u23f3 Kedaluwarsa!",
        "age_claimed": "\u274c Sudah diklaim!",
        "age_verified": "Terverifikasi!",
        "age_denied": "\u274c Ditolak. Harus 18+",
        "lang_updated": "Diperbarui!",
        "batch_expired": "Kedaluwarsa",
        "batch_loading": "Memuat...",
        "batch_no_channel": "Tidak ada channel yang ditautkan!",
        "batch_setup_prompt": "\U0001f4e6 Pengaturan: Jadikan bot admin di channel dan teruskan pesan ke sini",
        "batch_mode_activated": "Mode diaktifkan!",
        "batch_change_dest": "\U0001f504 **Ubah Channel Tujuan**\nJadikan bot admin di channel baru, lalu teruskan pesan ke sini.",
        "join_channel_first_alert": "Gabung channel dulu! \U0001f4e2 Wajib gabung!",
        "join_channel_first": "Gabung channel dulu! \U0001f4e2",
        "watch_timer_first": "\u23f0 Buka link dan tonton timer 20d dulu!",
        "test_ad_verified": "\u2705 Iklan Uji Terverifikasi! +1",
        "test_ad_verified_msg": "\u2705 **IKLAN UJI TERVERIFIKASI!**\nHadiah: +1 unduhan diisi ulang!",
        "finish_timer_first": "\u23f0 Selesaikan timer 20d dulu!",
        "verified_added": "Terverifikasi! +1 ditambahkan",
        "resume_prompt": "\u2705 Terverifikasi! Diisi ulang +1. Lanjutkan?",
        "refilled_download": "\u2705 Diisi ulang +1! Unduh lagi.",
        "fetching_bundle": "\u2705 Terverifikasi! Mengambil paket...",
        "outdated_button": "Tombol ini kedaluwarsa. Kirim link Anda lagi.",
        "stopping": "Menghentikan...",
        "stopped": "\U0001f6d1 Berhenti",
        "resuming": "Melanjutkan...",
        "checking_vault": "Memeriksa brankas & beban server...",
        "server_busy": "\u23f3 **Server Sibuk**\nAktif: {}/{}\nBebas: {}MB\nAntrian: #{}\nAkan mulai otomatis!",
        "simulated": "\U0001f6e0 Disimulasikan! Sekarang ketuk Periksa & Dapatkan +1",
        "server_unreachable": "\u274c Server tidak dapat dijangkau",
        "monetag_failed_twice": "Selesaikan dua upaya Monetag yang gagal terlebih dahulu.",
        "monetag_fallback_prompt": "\U0001f310 Monetag gagal dua kali. Lanjutkan dengan Adsterra:",
        "adsterra_ready": "Fallback Adsterra siap",
        "finish_monetag": "\U0001f4fa Selesaikan iklan Monetag di Mini App, lalu periksa lagi.",
        "monetag_failed_use_adsterra": "Monetag gagal dua kali. Gunakan fallback Adsterra di bawah.",
        "ad_link_expired": "Link iklan kedaluwarsa. Kirim link Anda lagi.",
        "ad_verified_added": "\u2705 Iklan terverifikasi! +{} ditambahkan",
        "test_ad_completed": "\u2705 IKLAN UJI TERVERIFIKASI\nHadiah dikreditkan: +{} unduhan.",
        "sponsor_viewed": "\u2705 Sponsor dilihat! +{} ditambahkan",
        "refilled_send_again": "\u2705 Diisi ulang +{}! Kirim link Anda lagi.",
        "queued": "\u23f3 Dalam antrian #{}",
        "banned": "\U0001f6ab Anda dibanned.",
        "no_links": "\u274c Tidak ada link ditemukan.",
        "batch_count": "\U0001f4e6 Batch {} link",
        "restore_invalid_json": "\u274c Gagal memulihkan: **{}** bukan JSON yang valid.",
        "restore_failed": "\u274c Gagal memulihkan: {}",
        "restore_success": "\u2705 **Pemulihan Berhasil!**\nFile: **{}**\nDipulihkan **{}** entri.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Kirim Pesan Selamat Datang baru. Gunakan `{bot_name}` untuk username bot.",
        "admin_welcome_updated": "\u2705 Pesan selamat datang diperbarui!",
        "menu_edit_welcome": "\u270f\ufe0f Edit Pesan Selamat Datang",
        "cached_instant_video": "\u26a1 Cache Instan [{}] {} {}",
        "cached_instant_audio": "\u26a1 **Cache Instan** `{}`",
        "cached_instant_image": "\u26a1 **Cache Instan** `{}`",
        "auto_delete_9m": "\u23f3 Hapus otomatis dalam 9 menit",
        "download_success": "\u2705 Unduhan berhasil!"
    },
    "fr": {
        "welcome": "\U0001f680 **BIENVENUE SUR MICHAELBBC VAULT - T\u00c9L\u00c9CHARGEUR DE M\u00c9DIAS COMPLET!**\n\n\U0001f525 CE QUE JE PEUX FAIRE:\n\U0001f3ac VID\u00c9OS HD Sans Filigrane!\n\U0001f3b5 AUDIO MP3 192kbps!\n\U0001f5bc\ufe0f IMAGES Extraction TOTALE!\n\U0001f4dd SOUS-TITRES Auto!\n\U0001f4e6 LOTS 100+ Liens!\n\u26a1 CACHE 1 Sec!\n\U0001f48e COFFRE Pour Toujours!\n\U0001f4e4 T\u00c9L\u00c9VERSER DES FICHIERS!\n\U0001f517 FICHIER-VERS-LIEN: Cr\u00e9ez des liens partageables!\n\n\U0001f449 COLLEZ UN LIEN POUR COMMENCER! \U0001f447",
        "btn_video": "\U0001f3ac Vid\u00e9o (MP4)", "btn_audio": "\U0001f3b5 Audio (MP3)", "btn_image": "\U0001f5bc\ufe0f Images", "btn_sub": "\U0001f4dd Sous-titres (SRT)",
        "ask_format": "\U0001f447 **G\u00c9NIAL! Quel format voulez-vous? Choisissez ci-dessous!**",
        "fetching": "\U0001f4e5 **R\u00e9cup\u00e9ration de votre {}... Patientez! \u23f3\u2728**",
        "error_generic": "\u274c Oups! \u00c9chec! \U0001f622 Lien priv\u00e9/bloqu\u00e9. Essayez un lien public!",
        "error_50mb": "\u274c Trop grand! \U0001f605 Cette vid\u00e9o d\u00e9passe 300 Mo. Essayez une plus courte!", 
        "error_no_img": "\u274c Aucune image trouv\u00e9e! \U0001f622 Essayez un autre lien!",
        "images_received": "\u23f3 **{} Images re\u00e7ues.**",
        "select_lang": "\U0001f30d S\u00e9lectionnez votre langue! Choisissez ci-dessous! \U0001f447", 
        "lang_set": "\u2705 Langue d\u00e9finie! Profitez-en! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Lot D\u00e9tect\u00e9 ({} liens)**\nQuel format?",
        "batch_dest": "\U0001f4e6 **O\u00f9 envoyer?**",
        "btn_chat": "\U0001f4e5 Dans le Chat", "btn_chan": "\U0001f4e2 Vers le Canal",
        "limit_reached": "\u26a0\ufe0f **Limite Atteinte!** Vous avez utilis\u00e9 4 GRATUITS! Regardez une pub de 20s \u2192 Obtenez +1 t\u00e9l\u00e9chargement!",
        "refill_btn": "\U0001f513 Ouvrir le Lien et Recharger +1",
        "join_btn": "\U0001f4e2 Rejoindre le Canal", "check_btn": "\U0001f49c V\u00e9rifier le Solde",
        "limit_batch": "\u26a0\ufe0f **Limite du Lot Atteinte \u00e0 {} sur {}**\nRegardez une pub de 20s \u2192 +1 t\u00e9l\u00e9chargement pour continuer.",
        "batch_start": "\U0001f4e6 **Lot D\u00e9marr\u00e9:** {} **{} fichiers**\n\u23f3 Traitement...",
        "batch_done": "\U0001f3c1 **Termin\u00e9!** \u2705 {} \u274c {}\n\U0001f4e5 {} fichiers ici.",
        "batch_done_chan": "\U0001f3c1 **Termin\u00e9!** \u2705 {} \u274c {}\n\U0001f4e2 {} fichiers transf\u00e9r\u00e9s!",
        "dl_video": "\U0001f4e5 T\u00e9l\u00e9chargement de la vid\u00e9o...", "dl_audio": "\U0001f4e5 Extraction de l'audio...", "dl_image": "\U0001f4e5 Extraction des images...", "dl_sub": "\U0001f4e5 R\u00e9cup\u00e9ration des sous-titres...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Bloqu\u00e9/priv\u00e9", "failed_generic": "\u274c \u00c9chec",
        "menu_lang": "\U0001f30d Langue", "menu_stats": "\U0001f4ca Mes Statistiques", "menu_help": "\U0001f4ac Support / FAQ", "menu_join": "\U0001f4e2 Rejoindre le Canal",
        "menu_uploads": "\U0001f37f T\u00e9l\u00e9versements des Fans", "menu_upload": "\U0001f4e4 T\u00e9l\u00e9verser un Fichier",
        "admin_upload_prompt": "\U0001f4c2 **Bo\u00eete de R\u00e9ception des T\u00e9l\u00e9versements des Fans**",
        "user_upload_prompt": "\U0001f4e4 **T\u00e9l\u00e9verser un Fichier**\nEnvoyez vid\u00e9o/image/fichier \u00e0 l'Admin. Limite 5/24h.",
        "upload_success_user": "\u2705 Envoy\u00e9 \u00e0 l'Admin!",
        "upload_limit_reached": "\u26a0\ufe0f Limite de t\u00e9l\u00e9versement 5/24h atteinte.",
        "no_uploads": "\U0001f4ed Aucun t\u00e9l\u00e9versement pour le moment.",
        "stats_msg": "\U0001f4ca **Vos Statistiques:**\n\u2022 T\u00e9l\u00e9chargements Restants: {}\n\u2022 Lots Restants: {}",
        "change_channel_prompt": "\U0001f504 **Changer de Canal pour les Lots**\n1. Assurez-vous que je suis admin dans le nouveau canal.\n2. Transf\u00e9rez n'importe quel message de ce canal ici.",
        "disk_config_prompt": "\U0001f4be **Config du Disque**\nMin disque libre actuel: **{} Mo**\nPour changer: `/setdisk <valeur>`",
        "mtproto_config_prompt": "\u26a1 **Config MTProto**\nMax t\u00e9l\u00e9versement actuel: **{} Mo**\nPour changer: `/setmtproto <valeur>`",
        "free_panel_prompt": "\U0001f4e6 T\u00c9L\u00c9CHARGEMENTS GRATUITS\nGratuits actuels par jour: {}",
        "reward_panel_prompt": "\U0001f381 PANNEAU DE R\u00c9COMPENSES\nActuel: +{} t\u00e9l\u00e9chargement par pub de 20s",
        "ad_panel_prompt": "\u2699\ufe0f Panneau des Pubs\nActuel: {}",
        "password_saved": "\U0001f510 Mot de passe enregistr\u00e9.",
        "password_too_long": "Le mot de passe doit faire 64 caract\u00e8res ou moins.",
        "file_to_link_prompt": "\U0001f517 **Fichier-vers-Lien**\nEnvoyez le(s) fichier(s) que vous souhaitez partager.",
        "link_invalid_expired": "\u274c Ce lien est invalide ou a expir\u00e9.",
        "link_limit_reached": "\u26d4 Ce lien a atteint sa limite d'utilisation.",
        "link_password_protected": "\U0001f510 Ce lien est prot\u00e9g\u00e9 par mot de passe. Envoyez le mot de passe.",
        "files_sent": "\u2705 Vos fichiers ont \u00e9t\u00e9 envoy\u00e9s.",
        "file_added": "\U0001f4e5 Fichier #{} ajout\u00e9. Envoyez-en plus ou appuyez sur Cr\u00e9er un Lien.",
        "fl_cancelled": "Fichier-vers-Lien annul\u00e9",
        "fl_start_again": "Recommencez Fichier-vers-Lien avec /filetolink",
        "fl_choose_expiry": "Choisissez l'expiration du lien:",
        "fl_expiry_updated": "Expiration mise \u00e0 jour",
        "fl_choose_max_uses": "Choisissez le max de livraisons r\u00e9ussies:",
        "fl_uses_updated": "Limite d'utilisation mise \u00e0 jour",
        "fl_set_password": "Envoyez un mot de passe, ou /clearpassword pour supprimer.",
        "fl_link_created": "Lien cr\u00e9\u00e9",
        "fl_link_ready": "\U0001f517 Votre lien est pr\u00eat:\n{}\nFichiers: {}\nCo\u00fbt: 1 t\u00e9l\u00e9chargement quotidien gratuit",
        "fl_daily_limit": "Limite quotidienne gratuite atteinte. Regardez une pub pour en gagner plus.",
        "fl_ad_busy": "\u26a0\ufe0f Serveur de publicit\u00e9s occup\u00e9.",
        "admin_skipped": "\u2705 Ignor\u00e9!",
        "admin_bypassed": "\u2705 Contourn\u00e9",
        "free_set": "\u2705 Gratuit d\u00e9fini \u00e0 {}!",
        "free_updated": "\u2705 T\u00e9l\u00e9chargements Gratuits mis \u00e0 jour \u00e0 {}!",
        "reward_set": "\u2705 R\u00e9compense d\u00e9finie \u00e0 +{}!",
        "reward_updated": "\u2705 R\u00e9compense mise \u00e0 jour \u00e0 +{}!",
        "mode_updated": "\u2705 Mode: {}",
        "support_opened": "\u270d\ufe0f Envoyez message/photo/vid\u00e9o/fichier ci-dessous.",
        "admin_reply_mode": "\u270d\ufe0f R\u00e9pondre \u00e0 {}:",
        "user_reply_mode": "\u270d\ufe0f Tapez le suivi ci-dessous",
        "support_closed": "\U0001f512 Ferm\u00e9",
        "drop_cancelled": "\u274c Annul\u00e9",
        "drop_no_items": "\u26a0\ufe0f Aucun \u00e9l\u00e9ment!",
        "drop_timer_set": "{} d\u00e9fini!",
        "drop_broadcasting": "\U0001f680 Diffusion de {} \u00e9l\u00e9ments \u00e0 {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\nAuto-suppression dans {}\nAppuyez pour r\u00e9clamer:",
        "drop_done": "\u2705 Diffusion termin\u00e9e pour {}",
        "age_expired": "\u23f3 Expir\u00e9!",
        "age_claimed": "\u274c D\u00e9j\u00e0 r\u00e9clam\u00e9!",
        "age_verified": "V\u00e9rifi\u00e9!",
        "age_denied": "\u274c Refus\u00e9. Doit \u00eatre 18+",
        "lang_updated": "Mis \u00e0 jour!",
        "batch_expired": "Expir\u00e9",
        "batch_loading": "Chargement...",
        "batch_no_channel": "Aucun canal li\u00e9!",
        "batch_setup_prompt": "\U0001f4e6 Configuration: Rendez le bot admin dans le canal et transf\u00e9rez un message ici",
        "batch_mode_activated": "Mode activ\u00e9!",
        "batch_change_dest": "\U0001f504 **Changer de Canal de Destination**\nRendez le bot admin dans le nouveau canal, puis transf\u00e9rez un message ici.",
        "join_channel_first_alert": "Rejoignez le canal d'abord! \U0001f4e2 Obligatoire!",
        "join_channel_first": "Rejoignez le canal d'abord! \U0001f4e2",
        "watch_timer_first": "\u23f0 Ouvrez le lien et regardez le minuteur de 20s d'abord!",
        "test_ad_verified": "\u2705 Pub de Test V\u00e9rifi\u00e9e! +1",
        "test_ad_verified_msg": "\u2705 **PUB DE TEST V\u00c9RIFI\u00c9E!**\nR\u00e9compense: +1 t\u00e9l\u00e9chargement recharg\u00e9!",
        "finish_timer_first": "\u23f0 Terminez le minuteur de 20s d'abord!",
        "verified_added": "V\u00e9rifi\u00e9! +1 ajout\u00e9",
        "resume_prompt": "\u2705 V\u00e9rifi\u00e9! Recharg\u00e9 +1. Reprendre?",
        "refilled_download": "\u2705 Recharg\u00e9 +1! T\u00e9l\u00e9chargez \u00e0 nouveau.",
        "fetching_bundle": "\u2705 V\u00e9rifi\u00e9! R\u00e9cup\u00e9ration du paquet...",
        "outdated_button": "Ce bouton est obsol\u00e8te. Envoyez votre lien \u00e0 nouveau.",
        "stopping": "Arr\u00eat...",
        "stopped": "\U0001f6d1 Arr\u00eat\u00e9",
        "resuming": "Reprise...",
        "checking_vault": "V\u00e9rification du coffre et de la charge du serveur...",
        "server_busy": "\u23f3 **Serveur Occup\u00e9**\nActifs: {}/{}\nLibre: {} Mo\nFile d'attente: #{}\nD\u00e9marrage auto!",
        "simulated": "\U0001f6e0 Simul\u00e9! Appuyez maintenant sur V\u00e9rifier et Obtenir +1",
        "server_unreachable": "\u274c Serveur injoignable",
        "monetag_failed_twice": "Terminez d'abord deux tentatives Monetag \u00e9chou\u00e9es.",
        "monetag_fallback_prompt": "\U0001f310 Monetag a \u00e9chou\u00e9 deux fois. Continuez avec Adsterra:",
        "adsterra_ready": "Solution de repli Adsterra pr\u00eate",
        "finish_monetag": "\U0001f4fa Terminez la pub Monetag dans la Mini App, puis v\u00e9rifiez \u00e0 nouveau.",
        "monetag_failed_use_adsterra": "Monetag a \u00e9chou\u00e9 deux fois. Utilisez la solution de repli Adsterra ci-dessous.",
        "ad_link_expired": "Lien publicitaire expir\u00e9. Envoyez votre lien \u00e0 nouveau.",
        "ad_verified_added": "\u2705 Pub v\u00e9rifi\u00e9e! +{} ajout\u00e9",
        "test_ad_completed": "\u2705 PUB DE TEST V\u00c9RIFI\u00c9E\nR\u00e9compense cr\u00e9dit\u00e9e: +{} t\u00e9l\u00e9chargement.",
        "sponsor_viewed": "\u2705 Sponsor vu! +{} ajout\u00e9",
        "refilled_send_again": "\u2705 Recharg\u00e9 +{}! Envoyez votre lien \u00e0 nouveau.",
        "queued": "\u23f3 En file d'attente #{}",
        "banned": "\U0001f6ab Vous \u00eates banni.",
        "no_links": "\u274c Aucun lien trouv\u00e9.",
        "batch_count": "\U0001f4e6 Lot {} liens",
        "restore_invalid_json": "\u274c \u00c9chec de la restauration: **{}** n'est pas un JSON valide.",
        "restore_failed": "\u274c \u00c9chec de la restauration: {}",
        "restore_success": "\u2705 **Restauration R\u00e9ussie!**\nFichier: **{}**\nRestaur\u00e9es **{}** entr\u00e9es.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Envoyez le nouveau Message de Bienvenue. Utilisez `{bot_name}` pour le nom d'utilisateur.",
        "admin_welcome_updated": "\u2705 Message de bienvenue mis \u00e0 jour!",
        "menu_edit_welcome": "\u270f\ufe0f Modifier le Message de Bienvenue",
        "cached_instant_video": "\u26a1 Cache Instantan\u00e9 [{}] {} {}",
        "cached_instant_audio": "\u26a1 **Cache Instantan\u00e9** `{}`",
        "cached_instant_image": "\u26a1 **Cache Instantan\u00e9** `{}`",
        "auto_delete_9m": "\u23f3 Auto-suppression dans 9 mins",
        "download_success": "\u2705 T\u00e9l\u00e9chargement r\u00e9ussi !"
    },
    "tr": {
        "welcome": "\U0001f680 **MICHAELBBC VAULT'A HO\u015eGELD\u0130N\u0130Z - TAM MEDYA \u0130ND\u0130R\u0130C\u0130!**\n\n\U0001f525 NE YAPAB\u0130L\u0130R\u0130M:\n\U0001f3ac V\u0130DEOLAR HD Filigrans\u0131z!\n\U0001f3b5 SES MP3 192kbps!\n\U0001f5bc\ufe0f G\u00d6RSELLER Tam \u00c7ekim!\n\U0001f4dd ALTYAZILAR Oto!\n\U0001f4e6 TOPLU 100+ Ba\u011flant\u0131!\n\u26a1 \u00d6NBELLEK 1 Sn!\n\U0001f48e KASA Sonsuza Kadar!\n\U0001f4e4 DOSYA Y\u00dcKLE!\n\U0001f517 DOSYADAN-L\u0130NKE: Payla\u015f\u0131labilir ba\u011flant\u0131lar olu\u015fturun!\n\n\U0001f449 BA\u015eLAMAK \u0130\u00c7\u0130N BA\u011eLANTI YAPI\u015eTIRIN! \U0001f447",
        "btn_video": "\U0001f3ac Video (MP4)", "btn_audio": "\U0001f3b5 Ses (MP3)", "btn_image": "\U0001f5bc\ufe0f G\u00f6rseller", "btn_sub": "\U0001f4dd Altyaz\u0131lar (SRT)",
        "ask_format": "\U0001f447 **HAR\u0130KA! Hangi format\u0131 istiyorsunuz? A\u015fa\u011f\u0131dan se\u00e7in!**",
        "fetching": "\U0001f4e5 **{} getiriliyor... Bekleyin! \u23f3\u2728**",
        "error_generic": "\u274c Oops! Ba\u015far\u0131s\u0131z! \U0001f622 Ba\u011flant\u0131 \u00f6zel/engelli. Halka a\u00e7\u0131k bir ba\u011flant\u0131 deneyin!",
        "error_50mb": "\u274c \u00c7ok b\u00fcy\u00fck! \U0001f605 Bu video 300MB'\u0131 a\u015f\u0131yor. Daha k\u0131sa bir tane deneyin!", 
        "error_no_img": "\u274c G\u00f6rsel bulunamad\u0131! \U0001f622 Ba\u015fka bir ba\u011flant\u0131 deneyin!",
        "images_received": "\u23f3 **{} G\u00f6rsel al\u0131nd\u0131.**",
        "select_lang": "\U0001f30d Dilinizi se\u00e7in! A\u015fa\u011f\u0131dan se\u00e7in! \U0001f447", 
        "lang_set": "\u2705 Dil ayarland\u0131! Keyfini \u00e7\u0131kar\u0131n! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Toplu \u0130\u015flem Alg\u0131land\u0131 ({} ba\u011flant\u0131)**\nHangi format?",
        "batch_dest": "\U0001f4e6 **Nereye g\u00f6nderilsin?**",
        "btn_chat": "\U0001f4e5 Sohbette", "btn_chan": "\U0001f4e2 Kanala",
        "limit_reached": "\u26a0\ufe0f **Limit A\u015f\u0131ld\u0131!** 4 \u00dcCRETS\u0130Z kulland\u0131n\u0131z! 20 sn reklam izleyin \u2192 +1 indirme kazan\u0131n!",
        "refill_btn": "\U0001f513 Ba\u011flant\u0131y\u0131 A\u00e7 ve +1 Doldur",
        "join_btn": "\U0001f4e2 Kanala Kat\u0131l", "check_btn": "\U0001f49c Bakiyeyi Kontrol Et",
        "limit_batch": "\u26a0\ufe0f **Toplu \u0130\u015flem Limiti {}/{}'de A\u015f\u0131ld\u0131**\n20 sn reklam izleyin \u2192 devam etmek i\u00e7in +1 indirme.",
        "batch_start": "\U0001f4e6 **Toplu \u0130\u015flem Ba\u015flad\u0131:** {} **{} dosya**\n\u23f3 \u0130\u015fleniyor...",
        "batch_done": "\U0001f3c1 **Bitti!** \u2705 {} \u274c {}\n\U0001f4e5 Burada {} dosya var.",
        "batch_done_chan": "\U0001f3c1 **Bitti!** \u2705 {} \u274c {}\n\U0001f4e2 {} dosya iletildi!",
        "dl_video": "\U0001f4e5 Video indiriliyor...", "dl_audio": "\U0001f4e5 Ses \u00e7\u0131kar\u0131l\u0131yor...", "dl_image": "\U0001f4e5 G\u00f6rseller \u00e7ekiliyor...", "dl_sub": "\U0001f4e5 Altyaz\u0131lar getiriliyor...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Engelli/\u00f6zel", "failed_generic": "\u274c Ba\u015far\u0131s\u0131z",
        "menu_lang": "\U0001f30d Dil", "menu_stats": "\U0001f4ca \u0130statistiklerim", "menu_help": "\U0001f4ac Destek / SSS", "menu_join": "\U0001f4e2 Kanala Kat\u0131l",
        "menu_uploads": "\U0001f37f Hayran Y\u00fcklemeleri", "menu_upload": "\U0001f4e4 Dosya Y\u00fckle",
        "admin_upload_prompt": "\U0001f4c2 **Hayran Y\u00fcklemeleri Gelen Kutusu**",
        "user_upload_prompt": "\U0001f4e4 **Dosya Y\u00fckle**\nY\u00f6neticiye video/g\u00f6rsel/dosya g\u00f6nderin. Limit 5/24s.",
        "upload_success_user": "\u2705 Y\u00f6neticiye g\u00f6nderildi!",
        "upload_limit_reached": "\u26a0\ufe0f 5/24s y\u00fckleme limitine ula\u015f\u0131ld\u0131.",
        "no_uploads": "\U0001f4ed Hen\u00fcz y\u00fckleme yok.",
        "stats_msg": "\U0001f4ca **\u0130statistikleriniz:**\n\u2022 Kalan \u0130ndirme: {}\n\u2022 Kalan Toplu \u0130\u015flem: {}",
        "change_channel_prompt": "\U0001f504 **Toplu \u0130\u015flem Kanal\u0131n\u0131 De\u011fi\u015ftir**\n1. Yeni kanalda y\u00f6netici oldu\u011fumdan emin olun.\n2. O kanaldan herhangi bir mesaj\u0131 buraya iletin.",
        "disk_config_prompt": "\U0001f4be **Disk Yap\u0131land\u0131rmas\u0131**\nMevcut min bo\u015f disk: **{}MB**\nDe\u011fi\u015ftirmek i\u00e7in: `/setdisk <de\u011fer>`",
        "mtproto_config_prompt": "\u26a1 **MTProto Yap\u0131land\u0131rmas\u0131**\nMevcut max y\u00fckleme: **{}MB**\nDe\u011fi\u015ftirmek i\u00e7in: `/setmtproto <de\u011fer>`",
        "free_panel_prompt": "\U0001f4e6 \u00dcCRETS\u0130Z \u0130ND\u0130RMELER\nG\u00fcnl\u00fck mevcut \u00fccretsiz: {}",
        "reward_panel_prompt": "\U0001f381 \u00d6D\u00dcL PANEL\u0130\nMevcut: 20 sn reklam ba\u015f\u0131na +{} indirme",
        "ad_panel_prompt": "\u2699\ufe0f Reklam Paneli\nMevcut: {}",
        "password_saved": "\U0001f510 \u015eifre kaydedildi.",
        "password_too_long": "\u015eifre 64 karakter veya daha az olmal\u0131d\u0131r.",
        "file_to_link_prompt": "\U0001f517 **Dosyadan-Link**\nPayla\u015fmak istedi\u011finiz dosya(lar\u0131) g\u00f6nderin.",
        "link_invalid_expired": "\u274c Bu ba\u011flant\u0131 ge\u00e7ersiz veya s\u00fcresi dolmu\u015f.",
        "link_limit_reached": "\u26d4 Bu ba\u011flant\u0131 kullan\u0131m limitine ula\u015ft\u0131.",
        "link_password_protected": "\U0001f510 Bu ba\u011flant\u0131 \u015fifre korumal\u0131d\u0131r. \u015eifreyi g\u00f6nderin.",
        "files_sent": "\u2705 Dosyalar\u0131n\u0131z g\u00f6nderildi.",
        "file_added": "\U0001f4e5 Dosya #{} eklendi. Daha fazla g\u00f6nderin veya Ba\u011flant\u0131 Olu\u015ftur'a dokunun.",
        "fl_cancelled": "Dosyadan-Link iptal edildi",
        "fl_start_again": "/filetolink ile Dosyadan-Link'i yeniden ba\u015flat\u0131n",
        "fl_choose_expiry": "Ba\u011flant\u0131 sona erme s\u00fcresini se\u00e7in:",
        "fl_expiry_updated": "Sona erme g\u00fcncellendi",
        "fl_choose_max_uses": "Maksimum ba\u015far\u0131l\u0131 teslimat say\u0131s\u0131n\u0131 se\u00e7in:",
        "fl_uses_updated": "Kullan\u0131m limiti g\u00fcncellendi",
        "fl_set_password": "Bir \u015fifre g\u00f6nderin veya kald\u0131rmak i\u00e7in /clearpassword g\u00f6nderin.",
        "fl_link_created": "Ba\u011flant\u0131 olu\u015fturuldu",
        "fl_link_ready": "\U0001f517 Ba\u011flant\u0131n\u0131z haz\u0131r:\n{}\nDosyalar: {}\nMaliyet: 1 \u00fccretsiz g\u00fcnl\u00fck indirme",
        "fl_daily_limit": "G\u00fcnl\u00fck \u00fccretsiz limite ula\u015f\u0131ld\u0131. Daha fazlas\u0131n\u0131 kazanmak i\u00e7in reklam izleyin.",
        "fl_ad_busy": "\u26a0\ufe0f Reklam sunucusu me\u015fgul.",
        "admin_skipped": "\u2705 Atland\u0131!",
        "admin_bypassed": "\u2705 Atlat\u0131ld\u0131",
        "free_set": "\u2705 \u00dccretsiz {} olarak ayarland\u0131!",
        "free_updated": "\u2705 \u00dccretsiz \u0130ndirmeler {} olarak g\u00fcncellendi!",
        "reward_set": "\u2705 \u00d6d\u00fcl +{} olarak ayarland\u0131!",
        "reward_updated": "\u2705 \u00d6d\u00fcl +{} olarak g\u00fcncellendi!",
        "mode_updated": "\u2705 Mod: {}",
        "support_opened": "\u270d\ufe0f A\u015fa\u011f\u0131ya mesaj/foto\u011fraf/video/dosya g\u00f6nderin.",
        "admin_reply_mode": "\u270d\ufe0f {} ki\u015fisine yan\u0131t ver:",
        "user_reply_mode": "\u270d\ufe0f A\u015fa\u011f\u0131ya takip mesaj\u0131 yaz\u0131n",
        "support_closed": "\U0001f512 Kapat\u0131ld\u0131",
        "drop_cancelled": "\u274c \u0130ptal edildi",
        "drop_no_items": "\u26a0\ufe0f \u00d6\u011fe yok!",
        "drop_timer_set": "{} ayarland\u0131!",
        "drop_broadcasting": "\U0001f680 {} \u00f6\u011fe {} ki\u015fisine yay\u0131nlan\u0131yor...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\n{} i\u00e7inde otomatik silinir\nTalep etmek i\u00e7in dokunun:",
        "drop_done": "\u2705 {} ki\u015fisine yay\u0131n tamamland\u0131",
        "age_expired": "\u23f3 S\u00fcresi doldu!",
        "age_claimed": "\u274c Zaten talep edildi!",
        "age_verified": "Do\u011fruland\u0131!",
        "age_denied": "\u274c Reddedildi. 18+ olmal\u0131",
        "lang_updated": "G\u00fcncellendi!",
        "batch_expired": "S\u00fcresi doldu",
        "batch_loading": "Y\u00fckleniyor...",
        "batch_no_channel": "Ba\u011fl\u0131 kanal yok!",
        "batch_setup_prompt": "\U0001f4e6 Kurulum: Botu kanalda y\u00f6netici yap\u0131n ve buraya bir mesaj iletin",
        "batch_mode_activated": "Mod etkinle\u015ftirildi!",
        "batch_change_dest": "\U0001f504 **Hedef Kanal\u0131 De\u011fi\u015ftir**\nBotu yeni kanalda y\u00f6netici yap\u0131n, ard\u0131ndan buraya bir mesaj iletin.",
        "join_channel_first_alert": "\u00d6nce kanala kat\u0131l\u0131n! \U0001f4e2 Kat\u0131lmal\u0131s\u0131n\u0131z!",
        "join_channel_first": "\u00d6nce kanala kat\u0131l\u0131n! \U0001f4e2",
        "watch_timer_first": "\u23f0 \u00d6nce ba\u011flant\u0131y\u0131 a\u00e7\u0131n ve 20 sn'lik zamanlay\u0131c\u0131y\u0131 izleyin!",
        "test_ad_verified": "\u2705 Test Reklam\u0131 Do\u011fruland\u0131! +1",
        "test_ad_verified_msg": "\u2705 **TEST REKLAMI DO\u011eRULANDI!**\n\u00d6d\u00fcl: +1 indirme dolduruldu!",
        "finish_timer_first": "\u23f0 \u00d6nce 20 sn'lik zamanlay\u0131c\u0131y\u0131 tamamlay\u0131n!",
        "verified_added": "Do\u011fruland\u0131! +1 eklendi",
        "resume_prompt": "\u2705 Do\u011fruland\u0131! +1 dolduruldu. Devam edilsin mi?",
        "refilled_download": "\u2705 +1 dolduruldu! Tekrar indirin.",
        "fetching_bundle": "\u2705 Do\u011fruland\u0131! Paket getiriliyor...",
        "outdated_button": "Bu d\u00fc\u011fme g\u00fcncel de\u011fil. Ba\u011flant\u0131n\u0131z\u0131 tekrar g\u00f6nderin.",
        "stopping": "Durduruluyor...",
        "stopped": "\U0001f6d1 Durduruldu",
        "resuming": "Devam ediliyor...",
        "checking_vault": "Kasa ve sunucu y\u00fck\u00fc kontrol ediliyor...",
        "server_busy": "\u23f3 **Sunucu Me\u015fgul**\nAktif: {}/{}\nBo\u015f: {}MB\nKuyruk: #{}\nOtomatik ba\u015flayacak!",
        "simulated": "\U0001f6e0 Sim\u00fcle edildi! \u015eimdi Kontrol Et ve +1 Al'a dokunun",
        "server_unreachable": "\u274c Sunucuya ula\u015f\u0131lam\u0131yor",
        "monetag_failed_twice": "\u00d6nce iki ba\u015far\u0131s\u0131z Monetag denemesini tamamlay\u0131n.",
        "monetag_fallback_prompt": "\U0001f310 Monetag iki kez ba\u015far\u0131s\u0131z oldu. Adsterra ile devam edin:",
        "adsterra_ready": "Adsterra yedeklemesi haz\u0131r",
        "finish_monetag": "\U0001f4fa Mini Uygulama'da Monetag reklam\u0131n\u0131 tamamlay\u0131n, sonra tekrar kontrol edin.",
        "monetag_failed_use_adsterra": "Monetag iki kez ba\u015far\u0131s\u0131z oldu. A\u015fa\u011f\u0131daki Adsterra yedeklemesini kullan\u0131n.",
        "ad_link_expired": "Reklam ba\u011flant\u0131s\u0131n\u0131n s\u00fcresi doldu. Ba\u011flant\u0131n\u0131z\u0131 tekrar g\u00f6nderin.",
        "ad_verified_added": "\u2705 Reklam do\u011fruland\u0131! +{} eklendi",
        "test_ad_completed": "\u2705 TEST REKLAMI DO\u011eRULANDI\n\u00d6d\u00fcl yat\u0131r\u0131ld\u0131: +{} indirme.",
        "sponsor_viewed": "\u2705 Sponsor g\u00f6r\u00fcnt\u00fclendi! +{} eklendi",
        "refilled_send_again": "\u2705 +{} dolduruldu! Ba\u011flant\u0131n\u0131z\u0131 tekrar g\u00f6nderin.",
        "queued": "\u23f3 Kuyrukta #{}",
        "banned": "\U0001f6ab Yasakland\u0131n\u0131z.",
        "no_links": "\u274c Ba\u011flant\u0131 bulunamad\u0131.",
        "batch_count": "\U0001f4e6 Toplu {} ba\u011flant\u0131",
        "restore_invalid_json": "\u274c Geri y\u00fckleme ba\u015far\u0131s\u0131z: **{}** ge\u00e7erli bir JSON de\u011fil.",
        "restore_failed": "\u274c Geri y\u00fckleme ba\u015far\u0131s\u0131z: {}",
        "restore_success": "\u2705 **Geri Y\u00fckleme Ba\u015far\u0131l\u0131!**\nDosya: **{}**\n**{}** girdi geri y\u00fcklendi.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Yeni Kar\u015f\u0131lama Mesaj\u0131n\u0131 g\u00f6nderin. Bot kullan\u0131c\u0131 ad\u0131 i\u00e7in `{bot_name}` kullan\u0131n.",
        "admin_welcome_updated": "\u2705 Kar\u015f\u0131lama mesaj\u0131 g\u00fcncellendi!",
        "menu_edit_welcome": "\u270f\ufe0f Kar\u015f\u0131lama Mesaj\u0131n\u0131 D\u00fczenle",
        "cached_instant_video": "\u26a1 An\u0131nda \u00d6nbellek [{}] {} {}",
        "cached_instant_audio": "\u26a1 **An\u0131nda \u00d6nbellek** `{}`",
        "cached_instant_image": "\u26a1 **An\u0131nda \u00d6nbellek** `{}`",
        "auto_delete_9m": "\u23f3 9 dakikada otomatik silinir",
        "download_success": "\u2705 \u0130ndirme ba\u015far\u0131l\u0131!"
    },
    "de": {
        "welcome": "\U0001f680 **WILLKOMMEN IM MICHAELBBC VAULT - ALL-IN-ONE MEDIA DOWNLOADER!**\n\n\U0001f525 WAS ICH KANN:\n\U0001f3ac VIDEOS HD Ohne Wasserzeichen!\n\U0001f3b5 AUDIO MP3 192kbps!\n\U0001f5bc\ufe0f BILDER Komplett Extrahiert!\n\U0001f4dd UNTERTITEL Auto!\n\U0001f4e6 STAPEL 100+ Links!\n\u26a1 CACHE 1 Sek!\n\U0001f48e TRESOR F\u00fcr Immer!\n\U0001f4e4 DATEIEN HOCHLADEN!\n\U0001f517 DATEI-ZU-LINK: Erstelle teilbare Links!\n\n\U0001f449 F\u00dcGE EINEN LINK EIN, UM ZU STARTEN! \U0001f447",
        "btn_video": "\U0001f3ac Video (MP4)", "btn_audio": "\U0001f3b5 Audio (MP3)", "btn_image": "\U0001f5bc\ufe0f Bilder", "btn_sub": "\U0001f4dd Untertitel (SRT)",
        "ask_format": "\U0001f447 **TOLL! Welches Format m\u00f6chtest du? W\u00e4hle unten!**",
        "fetching": "\U0001f4e5 **Dein {} wird abgerufen... Warte kurz! \u23f3\u2728**",
        "error_generic": "\u274c Oops! Fehlgeschlagen! \U0001f622 Link privat/gesperrt. Versuche einen \u00f6ffentlichen Link!",
        "error_50mb": "\u274c Zu gro\u00df! \U0001f605 Dieses Video ist \u00fcber 300MB. Versuche ein k\u00fcrzeres!", 
        "error_no_img": "\u274c Keine Bilder gefunden! \U0001f622 Versuche einen anderen Link!",
        "images_received": "\u23f3 **{} Bilder erhalten.**",
        "select_lang": "\U0001f30d W\u00e4hle deine Sprache! W\u00e4hle unten! \U0001f447", 
        "lang_set": "\u2705 Sprache eingestellt! Viel Spa\u00df! \U0001f389\u2728",
        "batch_detected": "\U0001f4e6 **Stapel erkannt ({} Links)**\nWelches Format?",
        "batch_dest": "\U0001f4e6 **Wohin senden?**",
        "btn_chat": "\U0001f4e5 Im Chat", "btn_chan": "\U0001f4e2 An Kanal",
        "limit_reached": "\u26a0\ufe0f **Limit erreicht!** Du hast 4 KOSTENLOSE genutzt! Schau 20s Werbung \u2192 Erhalte +1 Download!",
        "refill_btn": "\U0001f513 Link \u00f6ffnen & +1 auff\u00fcllen",
        "join_btn": "\U0001f4e2 Kanal beitreten", "check_btn": "\U0001f49c Guthaben pr\u00fcfen",
        "limit_batch": "\u26a0\ufe0f **Stapel-Limit bei {} von {} erreicht**\nSchau 20s Werbung \u2192 +1 Download um fortzufahren.",
        "batch_start": "\U0001f4e6 **Stapel gestartet:** {} **{} Dateien**\n\u23f3 Wird verarbeitet...",
        "batch_done": "\U0001f3c1 **Fertig!** \u2705 {} \u274c {}\n\U0001f4e5 {} Dateien hier.",
        "batch_done_chan": "\U0001f3c1 **Fertig!** \u2705 {} \u274c {}\n\U0001f4e2 {} Dateien weitergeleitet!",
        "dl_video": "\U0001f4e5 Video wird heruntergeladen...", "dl_audio": "\U0001f4e5 Audio wird extrahiert...", "dl_image": "\U0001f4e5 Bilder werden extrahiert...", "dl_sub": "\U0001f4e5 Untertitel werden abgerufen...",
        "failed_50": "\u274c >300MB", "failed_blocked": "\u274c Gesperrt/privat", "failed_generic": "\u274c Fehlgeschlagen",
        "menu_lang": "\U0001f30d Sprache", "menu_stats": "\U0001f4ca Meine Statistiken", "menu_help": "\U0001f4ac Support / FAQ", "menu_join": "\U0001f4e2 Kanal beitreten",
        "menu_uploads": "\U0001f37f Fan-Uploads", "menu_upload": "\U0001f4e4 Datei hochladen",
        "admin_upload_prompt": "\U0001f4c2 **Fan-Uploads Posteingang**",
        "user_upload_prompt": "\U0001f4e4 **Datei hochladen**\nSende Video/Bild/Datei an Admin. Limit 5/24h.",
        "upload_success_user": "\u2705 An Admin gesendet!",
        "upload_limit_reached": "\u26a0\ufe0f Upload-Limit 5/24h erreicht.",
        "no_uploads": "\U0001f4ed Noch keine Uploads.",
        "stats_msg": "\U0001f4ca **Deine Statistiken:**\n\u2022 Verbleibende Downloads: {}\n\u2022 Verbleibende Stapel: {}",
        "change_channel_prompt": "\U0001f504 **Stapel-Kanal \u00e4ndern**\n1. Stelle sicher, dass ich im neuen Kanal Admin bin.\n2. Leite eine beliebige Nachricht aus diesem Kanal hierher weiter.",
        "disk_config_prompt": "\U0001f4be **Speicher-Konfiguration**\nAktueller min. freier Speicher: **{}MB**\nZum \u00c4ndern: `/setdisk <wert>`",
        "mtproto_config_prompt": "\u26a1 **MTProto-Konfiguration**\nAktueller max. Upload: **{}MB**\nZum \u00c4ndern: `/setmtproto <wert>`",
        "free_panel_prompt": "\U0001f4e6 KOSTENLOSE DOWNLOADS\nAktuell kostenlos pro Tag: {}",
        "reward_panel_prompt": "\U0001f381 BELOHNUNGS-PANEL\nAktuell: +{} Download pro 20s Werbung",
        "ad_panel_prompt": "\u2699\ufe0f Werbe-Panel\nAktuell: {}",
        "password_saved": "\U0001f510 Passwort gespeichert.",
        "password_too_long": "Passwort muss 64 Zeichen oder weniger sein.",
        "file_to_link_prompt": "\U0001f517 **Datei-zu-Link**\nSende die Datei(en), die du teilen m\u00f6chtest.",
        "link_invalid_expired": "\u274c Dieser Link ist ung\u00fcltig oder abgelaufen.",
        "link_limit_reached": "\u26d4 Dieser Link hat sein Nutzungslimit erreicht.",
        "link_password_protected": "\U0001f510 Dieser Link ist passwortgesch\u00fctzt. Sende das Passwort.",
        "files_sent": "\u2705 Deine Dateien wurden gesendet.",
        "file_added": "\U0001f4e5 Datei #{} hinzugef\u00fcgt. Sende mehr oder tippe auf Link erstellen.",
        "fl_cancelled": "Datei-zu-Link abgebrochen",
        "fl_start_again": "Starte Datei-zu-Link neu mit /filetolink",
        "fl_choose_expiry": "W\u00e4hle den Link-Ablauf:",
        "fl_expiry_updated": "Ablauf aktualisiert",
        "fl_choose_max_uses": "W\u00e4hle max. erfolgreiche Zustellungen:",
        "fl_uses_updated": "Nutzungslimit aktualisiert",
        "fl_set_password": "Sende ein Passwort oder /clearpassword zum Entfernen.",
        "fl_link_created": "Link erstellt",
        "fl_link_ready": "\U0001f517 Dein Link ist bereit:\n{}\nDateien: {}\nKosten: 1 kostenloser t\u00e4glicher Download",
        "fl_daily_limit": "T\u00e4gliches kostenloses Limit erreicht. Schau Werbung, um mehr zu verdienen.",
        "fl_ad_busy": "\u26a0\ufe0f Werbeserver besch\u00e4ftigt.",
        "admin_skipped": "\u2705 \u00dcbersprungen!",
        "admin_bypassed": "\u2705 Umgangen",
        "free_set": "\u2705 Kostenlos auf {} gesetzt!",
        "free_updated": "\u2705 Kostenlose Downloads auf {} aktualisiert!",
        "reward_set": "\u2705 Belohnung auf +{} gesetzt!",
        "reward_updated": "\u2705 Belohnung auf +{} aktualisiert!",
        "mode_updated": "\u2705 Modus: {}",
        "support_opened": "\u270d\ufe0f Sende Nachricht/Foto/Video/Datei unten.",
        "admin_reply_mode": "\u270d\ufe0f Antworte an {}:",
        "user_reply_mode": "\u270d\ufe0f Tippe die Fortsetzung unten",
        "support_closed": "\U0001f512 Geschlossen",
        "drop_cancelled": "\u274c Abgebrochen",
        "drop_no_items": "\u26a0\ufe0f Keine Elemente!",
        "drop_timer_set": "{} eingestellt!",
        "drop_broadcasting": "\U0001f6a1 Sende {} Elemente an {}...",
        "drop_flash_text": "\U0001f6a8 FLASH DROP!\nAutomatische L\u00f6schung in {}\nTippe zum Einl\u00f6sen:",
        "drop_done": "\u2705 Sendung abgeschlossen an {}",
        "age_expired": "\u23f3 Abgelaufen!",
        "age_claimed": "\u274c Bereits eingel\u00f6st!",
        "age_verified": "Verifiziert!",
        "age_denied": "\u274c Abgelehnt. Muss 18+ sein",
        "lang_updated": "Aktualisiert!",
        "batch_expired": "Abgelaufen",
        "batch_loading": "Wird geladen...",
        "batch_no_channel": "Kein Kanal verkn\u00fcpft!",
        "batch_setup_prompt": "\U0001f4e6 Einrichtung: Mache den Bot im Kanal zum Admin und leite eine Nachricht hierher weiter",
        "batch_mode_activated": "Modus aktiviert!",
        "batch_change_dest": "\U0001f504 **Zielkanal \u00e4ndern**\nMache den Bot im neuen Kanal zum Admin, dann leite eine Nachricht hierher weiter.",
        "join_channel_first_alert": "Tritt zuerst dem Kanal bei! \U0001f4e2 Muss beitreten!",
        "join_channel_first": "Tritt zuerst dem Kanal bei! \U0001f4e2",
        "watch_timer_first": "\u23f0 \u00d6ffne zuerst den Link und schaue den 20s Timer!",
        "test_ad_verified": "\u2705 Test-Werbung verifiziert! +1",
        "test_ad_verified_msg": "\u2705 **TEST-WERBUNG VERIFIZIERT!**\nBelohnung: +1 Download aufgef\u00fcllt!",
        "finish_timer_first": "\u23f0 Schlie\u00dfe zuerst den 20s Timer ab!",
        "verified_added": "Verifiziert! +1 hinzugef\u00fcgt",
        "resume_prompt": "\u2705 Verifiziert! +1 aufgef\u00fcllt. Fortsetzen?",
        "refilled_download": "\u2705 +1 aufgef\u00fcllt! Lade erneut herunter.",
        "fetching_bundle": "\u2705 Verifiziert! Paket wird abgerufen...",
        "outdated_button": "Diese Schaltfl\u00e4che ist veraltet. Sende deinen Link erneut.",
        "stopping": "Wird gestoppt...",
        "stopped": "\U0001f6d1 Gestoppt",
        "resuming": "Wird fortgesetzt...",
        "checking_vault": "Tresor und Serverlast werden \u00fcberpr\u00fcft...",
        "server_busy": "\u23f3 **Server besch\u00e4ftigt**\nAktiv: {}/{}\nFrei: {}MB\nWarteschlange: #{}\nStartet automatisch!",
        "simulated": "\U0001f6e0 Simuliert! Tippe jetzt auf Pr\u00fcfen & +1 erhalten",
        "server_unreachable": "\u274c Server nicht erreichbar",
        "monetag_failed_twice": "Schlie\u00dfe zuerst zwei fehlgeschlagene Monetag-Versuche ab.",
        "monetag_fallback_prompt": "\U0001f310 Monetag ist zweimal fehlgeschlagen. Mit Adsterra fortfahren:",
        "adsterra_ready": "Adsterra-Fallback bereit",
        "finish_monetag": "\U0001f4fa Schlie\u00dfe die Monetag-Werbung in der Mini-App ab, pr\u00fcfe dann erneut.",
        "monetag_failed_use_adsterra": "Monetag ist zweimal fehlgeschlagen. Nutze den Adsterra-Fallback unten.",
        "ad_link_expired": "Werbelink abgelaufen. Sende deinen Link erneut.",
        "ad_verified_added": "\u2705 Werbung verifiziert! +{} hinzugef\u00fcgt",
        "test_ad_completed": "\u2705 TEST-WERBUNG VERIFIZIERT\nBelohnung gutgeschrieben: +{} Download.",
        "sponsor_viewed": "\u2705 Sponsor angesehen! +{} hinzugef\u00fcgt",
        "refilled_send_again": "\u2705 +{} aufgef\u00fcllt! Sende deinen Link erneut.",
        "queued": "\u23f3 In Warteschlange #{}",
        "banned": "\U0001f6ab Du bist gesperrt.",
        "no_links": "\u274c Keine Links gefunden.",
        "batch_count": "\U0001f4e6 Stapel {} Links",
        "restore_invalid_json": "\u274c Wiederherstellung fehlgeschlagen: **{}** ist kein g\u00fcltiges JSON.",
        "restore_failed": "\u274c Wiederherstellung fehlgeschlagen: {}",
        "restore_success": "\u2705 **Wiederherstellung erfolgreich!**\nDatei: **{}**\n**{}** Eintr\u00e4ge wiederhergestellt.",
        "admin_edit_welcome_prompt": "\u270f\ufe0f Sende die neue Willkommensnachricht. Verwende `{bot_name}` f\u00fcr den Bot-Benutzernamen.",
        "admin_welcome_updated": "\u2705 Willkommensnachricht aktualisiert!",
        "menu_edit_welcome": "\u270f\ufe0f Willkommensnachricht bearbeiten",
        "cached_instant_video": "\u26a1 Sofortiger Cache [{}] {} {}",
        "cached_instant_audio": "\u26a1 **Sofortiger Cache** `{}`",
        "cached_instant_image": "\u26a1 **Sofortiger Cache** `{}`",
        "auto_delete_9m": "\u23f3 Automatische L\u00f6schung in 9 Min.",
        "download_success": "\u2705 Download erfolgreich!"
    }
}

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

YT_ID_RE = re.compile(
    r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/|embed/)|music\.youtube\.com/watch\?(?:[^#\s]*&)?v=)'
    r'([A-Za-z0-9_-]{11})')

def youtube_id_from_url(url):
    m = YT_ID_RE.search(url)
    return m.group(1) if m else None

async def get_canonical_key(url: str, chat_id=None, bot=None):
    original_url = url
    async def send_debug(text):
        if chat_id and bot and chat_id == ADMIN_ID:
            try: await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except: pass

    await send_debug(f"\U0001f50d <b>Processing Link:</b>\n<code>{url}</code>")
    yt_id = youtube_id_from_url(url)
    if yt_id:
        return f"youtube_{yt_id}"     # same key format yt-dlp produced, so old cache entries still match

    short_link_domains = ["vt.tiktok.com", "vm.tiktok.com", "youtu.be/", "t.co/", "instagr.am/", "fb.watch/"]
    is_short_link = any(domain in url.lower() for domain in short_link_domains)

    if is_short_link:
        await send_debug("\U0001f504 Resolving short link...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
            resolved_url = response.url
            if resolved_url != original_url and "google.com/sorry" not in resolved_url:
                url = resolved_url
                await send_debug(f"\u2705 Resolved to:\n<code>{url}</code>")
        except Exception as e:
            await send_debug(f"\u274c Redirect failed: {str(e)[:100]}")

    tiktok_match = re.search(r'/video/(\d{15,20})', url)
    if tiktok_match:
        vid_id = tiktok_match.group(1)
        await send_debug(f"\U0001f3af <b>TikTok Regex Match!</b>\nVideo ID: <code>{vid_id}</code>")
        return f"tiktok_{vid_id}"

    await send_debug("\U0001f916 Trying yt-dlp extraction...")
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                if 'entries' in info and info['entries']: info = info['entries'][0]
                extractor = info.get('extractor', 'generic').replace(':', '').replace(' ', '')
                vid_id = info.get('id', '')
                if vid_id:
                    await send_debug(f"\u2705 yt-dlp found ID: <code>{vid_id}</code>")
                    return f"{extractor}_{vid_id}"
    except Exception as e:
        await send_debug(f"\u26a0\ufe0f yt-dlp failed: {str(e)[:50]}")

    await send_debug("\U0001f3b2 Using URL hash fallback.")
    clean = url.split('?')[0].split('&')[0].lower().strip('/').replace('https://','').replace('http://','')
    h = hashlib.md5(clean.encode()).hexdigest()[:12]
    return f"url_{h}"

async def restore_arcade_backup(bot):
    """Downloads the latest arcade_backup.json from the private channel to the server disk."""
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
        
        # FETCH THE ARCADE BACKUP FROM PYTHONANYWHERE
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

        cap = f"\U0001f4e6 AUTO-BACKUP {ts}\nFree: {free_mb}MB | Active: {active_downloads} | Queue: {download_queue.qsize()} | Vault: {VIDEO_VAULT_ID}"
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
        [InlineKeyboardButton("\U0001f4fa Watch Monetag Ad +1", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("\U0001f4e2 Join Public Channel \U0001f49c", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("\u2705 Check & Get +1", callback_data="monetag_check")],
        [InlineKeyboardButton("\u21aa\ufe0f Use Adsterra fallback (after 2 failures)", callback_data="monetag_fallback")],
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
    warn = await bot.send_message(chat_id=user_id, text="\u23f3 Auto-deletes in 9 mins", reply_markup=kb)
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

def scrape_html_images(url, cookiefile=None):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        og = soup.find('meta', property='og:image')
        if og and og.get('content'): return og['content']
    except Exception as e: logger.error(f"Scrape: {e}")
    return None

def get_min_free_disk_mb():
    config = load_json_file(CONFIG_FILE)
    return config.get("min_free_disk_mb", MIN_FREE_DISK_MB)

def get_mtproto_max_mb():
    config = load_json_file(CONFIG_FILE)
    return config.get("mtproto_max_mb", MTPROTO_MAX_MB)

# ======================= BEGIN PASTE =================================
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MAX_CAROUSEL_ITEMS = 20

# Only these sites are treated as carousel sources, so a YouTube playlist
# can never turn into 100 downloads.
CAROUSEL_DOMAINS = (
    "instagram.com", "instagr.am", "tiktok.com", "twitter.com", "x.com",
    "facebook.com", "fb.watch", "threads.net", "threads.com", "pinterest.",
    "pin.it", "reddit.com", "tumblr.com", "bsky.app", "weibo.",
    "xiaohongshu.com", "xhslink.com",
)


def _collect_media(folder):
    files = []
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if os.path.splitext(name)[1].lower() in (PHOTO_EXT | VIDEO_EXT) and os.path.getsize(p) > 1000:
            files.append(p)
    return files



LAST_CAROUSEL_TRACE = []   # filled by download_carousel, read by the admin message


def _trace(msg):
    LAST_CAROUSEL_TRACE.append(msg)
    logger.warning(f"[carousel] {msg}")


def _fetch_media_url(url, dest_base, cap_bytes, default_ext):
    """Download one slide to dest_base + extension. Returns the file path."""
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext not in (PHOTO_EXT | VIDEO_EXT):
        ext = default_ext
    path = dest_base + ext
    with requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                      stream=True, timeout=25) as r:
        r.raise_for_status()
        size = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > cap_bytes:
                    f.close()
                    os.remove(path)
                    raise ValueError("file over size cap")
                f.write(chunk)
    return path


def _instaloader_worker(shortcode, folder, cap_bytes):
    kwargs = dict(quiet=True, sleep=False, max_connection_attempts=1,
                  request_timeout=20, download_comments=False,
                  download_geotags=False, save_metadata=False)
    try:
        loader = instaloader.Instaloader(fatal_status_codes=[429], **kwargs)
    except TypeError:                       # older Instaloader version
        loader = instaloader.Instaloader(**kwargs)
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    _trace(f"instaloader: post found, typename={post.typename}, items={post.mediacount}")

    items = []   # (url, default_extension) in post order
    if post.typename == "GraphSidecar":
        for node in post.get_sidecar_nodes():
            if node.is_video and node.video_url:
                items.append((node.video_url, ".mp4"))
            else:
                items.append((node.display_url, ".jpg"))
    else:
        if post.is_video and post.video_url:
            items.append((post.video_url, ".mp4"))
        else:
            items.append((post.url, ".jpg"))
    _trace(f"instaloader: {len(items)} slide URL(s) read")

    files = []
    for i, (u, ext) in enumerate(items[:MAX_CAROUSEL_ITEMS], start=1):
        try:
            files.append(_fetch_media_url(u, os.path.join(folder, f"{i:03d}"), cap_bytes, ext))
        except Exception as e:
            _trace(f"instaloader: slide {i} failed: {type(e).__name__}: {str(e)[:120]}")
    return files


def download_instagram_post(url, output_dir, cap_bytes, min_items=2):
    """Instaloader fallback with a hard 40s limit. Returns [] on any failure."""
    low = url.lower()
    if instaloader is None:
        _trace("instaloader: not installed")
        return []
    if "instagram.com" not in low and "instagr.am" not in low:
        return []
    match = re.search(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
    if not match:
        _trace("instaloader: no shortcode in link")
        return []
    folder = os.path.join(output_dir, f"insta_{uuid.uuid4().hex[:10]}")
    os.makedirs(folder, exist_ok=True)
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(_instaloader_worker, match.group(1), folder, cap_bytes)
        files = fut.result(timeout=40)
        _trace(f"instaloader: downloaded {len(files)} file(s)")
        if len(files) >= min_items:
            return files
    except concurrent.futures.TimeoutError:
        _trace("instaloader: TIMEOUT after 40s (Instagram throttling/blocking)")
    except Exception as exc:
        _trace(f"instaloader: FAILED {type(exc).__name__}: {str(exc)[:200]}")
    finally:
        ex.shutdown(wait=False)
    shutil.rmtree(folder, ignore_errors=True)
    return []


YT_POST_RE = re.compile(r'youtube\.com/post/([A-Za-z0-9_-]+)')


def _find_first(node, key):
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for v in node.values():
            r = _find_first(v, key)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _find_first(v, key)
            if r is not None:
                return r
    return None


def _collect_post_images(node, out):
    """Collect the largest URL of every image in a YouTube community post, in order."""
    if isinstance(node, dict):
        if "backstageImageRenderer" in node:
            thumbs = ((node["backstageImageRenderer"].get("image") or {}).get("thumbnails")) or []
            if thumbs and thumbs[-1].get("url"):
                out.append(thumbs[-1]["url"])
            return
        for v in node.values():
            _collect_post_images(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_post_images(v, out)


def download_youtube_post(url, output_dir, cap_bytes):
    """Download the images of a YouTube community post. No cookies. Returns [] on failure."""
    m = YT_POST_RE.search(url)
    if not m:
        return []
    post_url = f"https://www.youtube.com/post/{m.group(1)}"
    folder = os.path.join(output_dir, f"ytpost_{uuid.uuid4().hex[:10]}")
    os.makedirs(folder, exist_ok=True)
    try:
        r = requests.get(post_url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"}, cookies={"CONSENT": "YES+1"})
        _trace(f"yt-post: HTTP {r.status_code}, final={r.url[:60]}")
        if "google.com/sorry" in r.url or "consent.youtube.com" in r.url:
            _trace("yt-post: blocked by Google (sorry/consent page)")
            return []
        mm = re.search(r"ytInitialData\s*=\s*(\{.*?\});\s*</script>", r.text, re.DOTALL)
        if not mm:
            _trace("yt-post: ytInitialData not found in page")
            return []
        data = json.loads(mm.group(1))
        post = _find_first(data, "backstagePostRenderer") or data   # stay inside the main post
        urls = []
        _collect_post_images(post, urls)
        urls = list(dict.fromkeys(urls))[:MAX_CAROUSEL_ITEMS]        # drop duplicates, keep order
        _trace(f"yt-post: {len(urls)} image URL(s) found")
        files = []
        for i, u in enumerate(urls, start=1):
            big = re.sub(r"=s\d+", "=s2048", u, count=1)              # ask for a large version
            try:
                files.append(_fetch_media_url(big, os.path.join(folder, f"{i:03d}"), cap_bytes, ".jpg"))
            except Exception:
                try:
                    files.append(_fetch_media_url(u, os.path.join(folder, f"{i:03d}"), cap_bytes, ".jpg"))
                except Exception as e:
                    _trace(f"yt-post: image {i} failed: {type(e).__name__}")
        if files:
            _trace(f"RESULT: youtube post OK, {len(files)} image(s)")
            return files
    except Exception as e:
        _trace(f"yt-post: FAILED {type(e).__name__}: {str(e)[:150]}")
    shutil.rmtree(folder, ignore_errors=True)
    return []


def download_carousel(url, output_dir, cap_bytes, http_headers=None):
    """Return [paths] (post order) for a multi-item OR single-photo post, else [].
    No cookies. Every step writes one line to LAST_CAROUSEL_TRACE."""
    LAST_CAROUSEL_TRACE.clear()
    low = url.lower()
    if "youtube.com/post/" in low:
        _trace("start (youtube post)")
        return download_youtube_post(url, output_dir, cap_bytes)
    if not any(d in low for d in CAROUSEL_DOMAINS):
        return []
    _trace("start")

    folder = os.path.join(output_dir, f"car_{uuid.uuid4().hex[:10]}")
    os.makedirs(folder, exist_ok=True)
    files, ytdlp_failed, gallery_ran = [], False, False
    try:
        # ---- 1) yt-dlp ----
        try:
            base = {"quiet": True, "no_warnings": True, "noplaylist": False,
                    "playlistend": MAX_CAROUSEL_ITEMS, "ignoreerrors": True,
                    "socket_timeout": 15}
            if http_headers: base["http_headers"] = http_headers
            with yt_dlp.YoutubeDL(dict(base, skip_download=True)) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = [e for e in (info or {}).get("entries") or [] if e]
            _trace(f"yt-dlp: info={'none' if info is None else 'ok'}, entries={len(entries)}")
            vf = [f for f in (info or {}).get("formats") or [] if f.get("vcodec") not in (None, "none")]
            if info and not entries and vf:
                _trace("yt-dlp: single video, not a carousel")
                shutil.rmtree(folder, ignore_errors=True)
                return []
            if len(entries) >= 2:
                opts = dict(base)
                opts.update({
                    "outtmpl": os.path.join(folder, "%(autonumber)03d_%(id)s.%(ext)s"),
                    "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
                    "merge_output_format": "mp4",
                    "max_filesize": cap_bytes,
                })
                try:
                    import imageio_ffmpeg
                    opts["ffmpeg_location"] = imageio_ffmpeg.get_ffmpeg_exe()
                except Exception:
                    pass
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.extract_info(url, download=True)
            elif info is None:
                ytdlp_failed = True
        except Exception as e:
            _trace(f"yt-dlp: FAILED {type(e).__name__}: {str(e)[:150]}")
            ytdlp_failed = True

        files = sorted(_collect_media(folder))
        _trace(f"after yt-dlp: {len(files)} file(s)")

        # ---- 2) gallery-dl (45s limit, 1 retry): photo posts and slideshows ----
        if len(files) < 2 and (ytdlp_failed or not files):
            try:
                gallery_ran = True
                r = subprocess.run(
                    [sys.executable, "-m", "gallery_dl", "-D", folder, "--no-mtime",
                     "-R", "1", "--http-timeout", "15",
                     "--range", f"1-{MAX_CAROUSEL_ITEMS}", url],
                    capture_output=True, text=True, timeout=45)
                files = _collect_media(folder)
                files.sort(key=os.path.getmtime)
                err = (r.stderr or r.stdout or "").strip().replace("\n", " ")[-160:]
                _trace(f"gallery-dl: exit={r.returncode}, files={len(files)}, msg={err}")
            except subprocess.TimeoutExpired:
                _trace("gallery-dl: TIMEOUT after 45s")
                files = _collect_media(folder)
            except Exception as e:
                _trace(f"gallery-dl: FAILED {type(e).__name__}: {str(e)[:150]}")

        # ---- 3) Instaloader (Instagram only); a single photo is fine too ----
        if not files and ("instagram.com" in low or "instagr.am" in low):
            insta_files = download_instagram_post(url, output_dir, cap_bytes, min_items=1)
            if len(insta_files) >= 1:
                _trace(f"RESULT: OK via instaloader, {len(insta_files)} item(s)")
                return insta_files

        files = [p for p in files if os.path.getsize(p) <= cap_bytes][:MAX_CAROUSEL_ITEMS]
        # 2+ files is a carousel. Exactly 1 file is accepted only when it came from the
        # photo-post fallback (gallery-dl), so normal single videos are not touched.
        if len(files) >= 2 or (len(files) == 1 and gallery_ran):
            _trace(f"RESULT: OK, {len(files)} item(s)")
            return files
        _trace("RESULT: no carousel obtained -> old single-image code will run")
    except Exception as e:
        _trace(f"download_carousel crashed: {type(e).__name__}: {e}")
    shutil.rmtree(folder, ignore_errors=True)
    return []


# ---------------------------- sending ---------------------------------
def _media(kind, src, **kw):
    if kind == "video":
        return InputMediaVideo(media=src, supports_streaming=True, **kw)
    return InputMediaPhoto(media=src, **kw)


def _item_from_msg(m):
    mid = m.message_id
    if getattr(m, "photo", None): return {"kind": "photo", "file_id": m.photo[-1].file_id, "message_id": mid}
    if getattr(m, "video", None): return {"kind": "video", "file_id": m.video.file_id, "message_id": mid}
    if getattr(m, "document", None): return {"kind": "document", "file_id": m.document.file_id, "message_id": mid}
    return None


async def _send_items(bot, chat_id, items, caption=None):
    """items: [{'kind': photo|video|document, 'src': file handle OR file_id}].
    Albums of 10. Returns [{'kind','file_id','message_id'}]."""
    out = []
    albumable = [i for i in items if i["kind"] in ("photo", "video")]
    docs = [i for i in items if i["kind"] == "document"]
    first = True
    for s in range(0, len(albumable), 10):
        chunk = albumable[s:s + 10]
        cap = {"caption": caption, "parse_mode": "Markdown"} if (first and caption) else {}
        if len(chunk) == 1:
            it = chunk[0]
            if it["kind"] == "video":
                msgs = [await bot.send_video(chat_id=chat_id, video=it["src"], supports_streaming=True, **cap)]
            else:
                msgs = [await bot.send_photo(chat_id=chat_id, photo=it["src"], **cap)]
        else:
            media = [_media(it["kind"], it["src"], **(cap if j == 0 else {})) for j, it in enumerate(chunk)]
            msgs = list(await bot.send_media_group(chat_id=chat_id, media=media))
        out += [x for x in (_item_from_msg(m) for m in msgs) if x]
        first = False
        await asyncio.sleep(1)
    for it in docs:
        m = await bot.send_document(chat_id=chat_id, document=it["src"])
        x = _item_from_msg(m)
        if x: out.append(x)
    return out


async def send_carousel(bot, chat_id, file_paths, ckey, status_msg=None, send_video_file_fn=None):
    """Send downloaded files. Returns list of {'kind','file_id','message_id'}."""
    caption = f"\U0001f4f8 {len(file_paths)} items `{ckey}`"
    results, big_videos = [], []
    with ExitStack() as stack:
        items = []
        for p in file_paths:
            ext, size = os.path.splitext(p)[1].lower(), os.path.getsize(p)
            if ext in VIDEO_EXT and size <= BOT_API_LIMIT_BYTES:
                items.append({"kind": "video", "src": stack.enter_context(open(p, "rb"))})
            elif ext in VIDEO_EXT:
                big_videos.append(p)
            elif ext in PHOTO_EXT and size <= 10 * 1024 * 1024:
                items.append({"kind": "photo", "src": stack.enter_context(open(p, "rb"))})
            else:  # odd format or >10MB image -> as a file
                items.append({"kind": "document", "src": stack.enter_context(open(p, "rb"))})
        results += await _send_items(bot, chat_id, items, caption)
    for p in big_videos:
        if not send_video_file_fn:
            continue
        try:
            m = await send_video_file_fn(bot, chat_id, chat_id, p, f"\U0001f3ac `{ckey}`", "Markdown", status_msg)
            results.append({"kind": "video", "file_id": m.video.file_id, "message_id": m.message_id})
        except Exception as e:
            logger.error(f"carousel big video fail: {e}")
    return results


# ---------------------------- caching ---------------------------------
async def save_carousel_cache(bot, ckey, results, size):
    """Back up to the vault channel and store file_ids in the download cache."""
    vault_ids = []
    try:
        vault_items = [{"kind": r["kind"], "src": r["file_id"]} for r in results]
        sent = await _send_items(bot, VIDEO_VAULT_ID, vault_items, caption=None)
        vault_ids = [s["message_id"] for s in sent]
    except Exception as e:
        logger.error(f"carousel vault save: {e}")
    cache = load_json_file(CACHE_FILE)
    cache[ckey] = {
        "type": "carousel", "timestamp": time.time(), "hits": 0, "size": size,
        "items": [{"kind": r["kind"], "file_id": r["file_id"]} for r in results],
        "vault_msg_ids": vault_ids,
    }
    save_json_file(CACHE_FILE, cache)


async def send_cached_carousel(bot, chat_id, entry, ckey):
    """Instant resend from cache. Returns list of sent message ids.
    Falls back to copying from the vault channel if file_ids stop working."""
    caption = f"\u26a1 \U0001f4f8 {len(entry['items'])} items `{ckey}`"
    try:
        items = [{"kind": i["kind"], "src": i["file_id"]} for i in entry["items"]]
        sent = await _send_items(bot, chat_id, items, caption)
        return [s["message_id"] for s in sent]
    except Exception as e:
        logger.error(f"cached carousel file_id send failed {ckey}: {e}")
    ids = []
    for vid in entry.get("vault_msg_ids", []):
        m = await bot.copy_message(chat_id=chat_id, from_chat_id=VIDEO_VAULT_ID, message_id=vid)
        ids.append(m.message_id)
    if not ids:
        raise RuntimeError("CAROUSEL_CACHE_EMPTY")
    return ids
# ======================== END PASTE ==================================


def download_with_lux(url, output_dir, cap_bytes, cookiefile=None):
    """Run the optional Lux binary as a last-resort video downloader."""
    lux_bin = os.getenv(
        "LUX_BIN",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bin", "lux")
    )
    if not os.path.isfile(lux_bin) or not os.access(lux_bin, os.X_OK):
        lux_bin = shutil.which("lux")
    if not lux_bin:
        logger.info("Lux fallback skipped: binary is not installed.")
        return None

    folder = os.path.join(output_dir, f"lux_{uuid.uuid4().hex[:10]}")
    os.makedirs(folder, exist_ok=True)
    output_name = f"media_{uuid.uuid4().hex[:8]}"
    command = [lux_bin, "-retry", "2", "-n", "4", "-o", folder, "-O", output_name]
    if cookiefile and os.path.isfile(cookiefile):
        command.extend(["-c", cookiefile])
    command.append(url)

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        candidates = []
        for root, _, names in os.walk(folder):
            for name in names:
                path = os.path.join(root, name)
                if os.path.isfile(path) and os.path.getsize(path) > 1000:
                    candidates.append(path)
        candidates.sort(key=os.path.getmtime)
        candidates = [
            path for path in candidates
            if os.path.splitext(path)[1].lower() in VIDEO_EXT
            and os.path.getsize(path) <= cap_bytes
        ]
        if result.returncode == 0 and candidates:
            chosen = candidates[-1]
            # Keep only the chosen result; remove Lux side files.
            for path in candidates:
                if path != chosen:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            return chosen
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        logger.warning("Lux fallback did not produce a usable video: %s",
                       detail[-1][:200] if detail else f"exit={result.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning("Lux fallback timed out.")
    except Exception as exc:
        logger.warning(f"Lux fallback failed: {type(exc).__name__}: {str(exc)[:180]}")
    shutil.rmtree(folder, ignore_errors=True)
    return None


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

    # ===== EDIT A: carousel branch (no cookies passed here) =====
    if download_type in ('video', 'images'):
        car = download_carousel(url, output_dir, cap_bytes, http_headers)
        if car:
            total = sum(os.path.getsize(p) for p in car)
            return car, "carousel", f"{total/(1024*1024):.1f}MB"
    # ============================================================
    
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
        img_url = scrape_html_images(url, cookiefile)
        if img_url:
            data = requests.get(img_url, headers=http_headers, timeout=15).content
            path = os.path.join(output_dir, f"img_{int(time.time())}.jpg")
            with open(path, 'wb') as f: f.write(data)
            if os.path.getsize(path) > 1000: return [path], "original", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("NO_IMAGES")
    else:
        tiers = [
            ("1080p", "bv*[height<=1080]+ba/b[height<=1080]"),
            ("720p", "bv*[height<=720]+ba/b[height<=720]"),
            ("480p", "bv*[height<=480]+ba/b[height<=480]"),
            ("360p", "bv*[height<=360]+ba/b[height<=360]"),
            ("worst", "worst")
        ]
        too_big = False
        yt_blocked = False
        last_err = None
        best_quality = "unknown"
        
        for qual_name, fmt in tiers:
            try:
                opts = dict(ydl_opts)
                opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, f'%(id)s_{qual_name}.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path, 'max_filesize': cap_bytes})
                if qual_name != "worst":
                    # sort by the SHORT side so vertical videos (e.g. 720x1280) are not rejected
                    opts.update({'format': 'bv*+ba/b', 'format_sort': [f"res:{qual_name[:-1]}"]})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    try:
                        vf = [f for f in (info.get('formats') or []) if f.get('vcodec') not in (None, 'none') and f.get('height')]
                        sizes = sorted({f.get('height') for f in vf})
                        LAST_CAROUSEL_TRACE.append(f"{info.get('extractor')}: offered heights {sizes}, chosen {info.get('width')}x{info.get('height')} fmt={info.get('format_id')} tier={qual_name}")
                    except Exception:
                        pass
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"): path = os.path.splitext(path)[0]+".mp4"
                    if os.path.exists(path):
                        if os.path.getsize(path) > cap_bytes:
                            os.remove(path)
                            too_big = True
                            continue
                        w, h = info.get('width') or 0, info.get('height') or 0
                        actual_height = min(w, h) if (w and h) else max(w, h)
                        if actual_height >= 1080: best_quality = "1080p"
                        elif actual_height >= 720: best_quality = "720p"
                        elif actual_height >= 480: best_quality = "480p"
                        elif actual_height >= 360: best_quality = "360p"
                        else: best_quality = "worst"
                        return [path], best_quality, f"{os.path.getsize(path)/(1024*1024):.1f}MB"
                    last_err = RuntimeError("yt-dlp produced no output file")
            except Exception as e:
                last_err = e
                msg = str(e)
                if "not a bot" in msg or "Sign in to confirm" in msg or "HTTP Error 429" in msg:
                    yt_blocked = True
                    break
                if "Unsupported URL" in msg or "403" in msg:
                    break
                continue

        # Instagram-specific fallback for a single Reel/video after yt-dlp fails.
        if not too_big and ("instagram.com" in url.lower() or "instagr.am" in url.lower()):
            insta_files = download_instagram_post(url, output_dir, cap_bytes, min_items=1)
            insta_videos = [p for p in insta_files if os.path.splitext(p)[1].lower() in VIDEO_EXT]
            if insta_videos:
                chosen = insta_videos[0]
                return [chosen], "original", f"{os.path.getsize(chosen)/(1024*1024):.1f}MB"
            if insta_files:
                shutil.rmtree(os.path.dirname(insta_files[0]), ignore_errors=True)

        # Last-resort independent engine. It is only called after yt-dlp tiers fail.
        if not too_big and not yt_blocked:
            lux_path = download_with_lux(url, output_dir, cap_bytes, cookiefile)
            if lux_path:
                return [lux_path], "lux", f"{os.path.getsize(lux_path)/(1024*1024):.1f}MB"

        if yt_blocked:
            raise ValueError("SITE_BLOCKED")
        if too_big or last_err is None:
            raise ValueError("FILE_TOO_LARGE")
        raise last_err

def get_main_keyboard(lang_code, is_admin):
    t = LANGUAGES.get(lang_code, LANGUAGES["en"])
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])],
        [KeyboardButton(t["menu_upload"]), KeyboardButton("\U0001f517 File-to-Link")],
        [KeyboardButton("\U0001f7e2 Bot Status")],
        [KeyboardButton("\U0001f504 Change Batch Channel")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("/stats"), KeyboardButton("/toggleads")])
        keyboard.append([KeyboardButton("/testad"), KeyboardButton("/adinfo")])
        keyboard.append([KeyboardButton("/tokencheck"), KeyboardButton("/broadcast")])
        keyboard.append([KeyboardButton("/ban"), KeyboardButton("/unban")])
        keyboard.append([KeyboardButton("/backup"), KeyboardButton("/restore")])
        keyboard.append([KeyboardButton("\U0001f4be Disk Config"), KeyboardButton("\u26a1 MTProto Config")])
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("\u26a1 Create Flash Drop")])
        keyboard.append([KeyboardButton("\U0001f381 Set Reward (1/2/3/5)"), KeyboardButton("\U0001f4e6 Set Free DL (2/3/4/5)")])
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
        [InlineKeyboardButton("\U0001f1ec\U0001f1e7 English", callback_data="lang_en"), InlineKeyboardButton("\U0001f1ee\U0001f1f3 \u0939\u093f\u0902\u0926\u0940", callback_data="lang_hi")],
        [InlineKeyboardButton("\U0001f1ea\U0001f1f8 Espa\u00f1ol", callback_data="lang_es"), InlineKeyboardButton("\U0001f1f8\U0001f1e6 \u0627\u0644\u0639\u0631\u0628\u064a\u0629", callback_data="lang_ar")],
        [InlineKeyboardButton("\U0001f1f7\U0001f1fa \u0420\u0443\u0441\u0441\u043a\u0438\u0439", callback_data="lang_ru"), InlineKeyboardButton("\U0001f1e7\U0001f1f7 Portugu\u00eas", callback_data="lang_pt")],
        [InlineKeyboardButton("\U0001f1ee\U0001f1e9 Indonesia", callback_data="lang_id"), InlineKeyboardButton("\U0001f1eb\U0001f1f7 Fran\u00e7ais", callback_data="lang_fr")],
        [InlineKeyboardButton("\U0001f1f9\U0001f1f7 T\u00fcrk\u00e7e", callback_data="lang_tr"), InlineKeyboardButton("\U0001f1e9\U0001f1ea Deutsch", callback_data="lang_de")]
    ]
    await update.message.reply_text(t["select_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

def file_link_keyboard(state):
    settings = state.get("settings", {})
    expiry = settings.get("expiry", "never")
    expiry_label = {"3600":"1 hour", "86400":"1 day", "604800":"7 days", "2592000":"30 days", "never":"Never"}.get(str(expiry), "Never")
    max_clicks = int(settings.get("max_clicks", 0) or 0)
    kb = [[InlineKeyboardButton(f"\u23f3 Expiry: {expiry_label}", callback_data="fl_expiry")],
          [InlineKeyboardButton(f"\U0001f465 Max uses: {max_clicks if max_clicks else 'Unlimited'}", callback_data="fl_maxuses")],
          [InlineKeyboardButton("\U0001f510 Set password" if not settings.get("password") else "\U0001f510 Change/remove password", callback_data="fl_password")],
          [InlineKeyboardButton(f"\U0001f4ce Files: {len(state.get('items', []))}", callback_data="fl_refresh")],
          [InlineKeyboardButton("\u2705 Create Link", callback_data="fl_create"), InlineKeyboardButton("\u274c Cancel", callback_data="fl_cancel")]]
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
    except Exception: await update.effective_message.reply_text("\U0001f4e2 Join our required channel first: " + PUBLIC_CHANNEL_URL); return
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
        if not drop: await update.message.reply_text("\u274c Invalid flash drop."); return
        if time.time() > drop["expires_at"]: await update.message.reply_text(t["age_expired"], parse_mode="Markdown"); return
        if "claimed_users" in drop and user_id in drop["claimed_users"]: await update.message.reply_text(t["age_claimed"], parse_mode="Markdown"); return
        keyboard = [[InlineKeyboardButton("\u2705 Yes, 18+", callback_data=f"age_yes_{drop_id}"), InlineKeyboardButton("\u274c No", callback_data="age_no")]]
        await update.message.reply_text("\U0001f51e Age verification?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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
        extra = [[InlineKeyboardButton("\u274c Skip (Admin)", callback_data="admin_skip_ad")]] if user_id == ADMIN_ID else None
        kb = adsgram_keyboard(user_id, "wall", msg_start, msg_end, extra)
        if kb: await update.message.reply_text("\U0001f4fa **Sponsor**\nTap **Watch Ad**, finish the ad in the Mini App, then tap **Check & Get +1**.", reply_markup=kb, parse_mode="Markdown")
        else: await update.message.reply_text("\u26a0\ufe0f Ad server busy, try again in a moment.")
        return
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("\U0001f513 Open Link & Watch", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    if user_id == ADMIN_ID: keyboard.append([InlineKeyboardButton("\u274c Skip (Admin)", callback_data="admin_skip_ad")])
    try:
        tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        await asyncio.sleep(0.2)
    except Exception as e1:
        logger.error(f"Forward failed: {e1}")
        try: await context.bot.copy_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        except Exception as e2: logger.error(f"Copy failed: {e2}")
    await update.message.reply_text("\U0001f447 **CONTENT LOCKED \U0001f512**" + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, download_type, start_index=0):
    if not urls: return
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    success_count = fail_count = 0
    active_batch_sessions[user_id] = True
    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f6d1 Stop Batch", callback_data="stop_batch")]])
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
        status_msg = await bot.send_message(chat_id=chat_id, text=f"\U0001f4e5 [{index}/{len(urls)}] {t['dl_video']}")
        try:
            ckey = await get_canonical_key(url, chat_id, bot)
            cache = load_json_file(CACHE_FILE)
            
            if ckey in cache and "file_id" in cache[ckey] and "qualities" not in cache[ckey]:
                cache[ckey]["qualities"] = {"720p": {"file_id": cache[ckey]["file_id"], "vault_msg_id": cache[ckey].get("vault_msg_id"), "size": cache[ckey].get("size", "unknown")}}
                del cache[ckey]["file_id"]
                save_json_file(CACHE_FILE, cache)

            # ===== EDIT D1: batch carousel cache hit =====
            if ckey in cache and cache[ckey].get("type") == "carousel":
                try:
                    ids = await send_cached_carousel(bot, target_destination_id, cache[ckey], ckey)
                    if target_destination_id == chat_id:
                        asyncio.create_task(schedule_deletion(bot, chat_id, ids, 540))
                    cache[ckey]["hits"] = cache[ckey].get("hits", 0) + 1
                    save_json_file(CACHE_FILE, cache)
                    await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                    success_count += 1
                    continue
                except Exception as e: logger.error(f"Batch carousel cache fail {ckey}: {e}")
            # =============================================
            
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
                        sent = await bot.send_video(chat_id=target_destination_id, video=cached["file_id"], caption=f"Item {index}/{len(urls)} \u26a1 Cached {qual_tag}")
                        if target_destination_id == chat_id:
                            warn = await bot.send_message(chat_id=target_destination_id, text="\u23f3 Auto-deletes in 9 mins")
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

            # ===== EDIT D2: batch fresh carousel =====
            if file_paths and res == "carousel":
                try:
                    results = await send_carousel(bot, target_destination_id, file_paths, ckey, status_msg, send_video_file)
                    if results:
                        await save_carousel_cache(bot, ckey, results, size)
                        if target_destination_id == chat_id:
                            asyncio.create_task(schedule_deletion(bot, chat_id, [r["message_id"] for r in results], 540))
                finally:
                    shutil.rmtree(os.path.dirname(file_paths[0]), ignore_errors=True)
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
                await asyncio.sleep(3)
                continue
            # =========================================

            if file_paths and os.path.exists(file_paths[0]):
                qual_tag = f"[{res}]"
                sent = await send_video_file(bot, chat_id, target_destination_id, file_paths[0], f"Item {index}/{len(urls)} {qual_tag} Size {size}", None, status_msg)
                if target_destination_id == chat_id:
                    warn = await bot.send_message(chat_id=target_destination_id, text="\u23f3 Auto-deletes in 9 mins")
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
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"\u274c [{index}] {t['failed_generic']}")
                fail_count += 1
        except Exception as e:
            try: await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"\u274c [{index}] {str(e)[:50]}")
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
        keyboard = [[InlineKeyboardButton("\U0001f4ac Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("\U0001f512 Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"\U0001f4ac Ticket [{ticket_id}] From {user_id}\n\U0001f4ce Media below:", parse_mode="Markdown")
        try: await update.message.forward(chat_id=ADMIN_ID)
        except: await context.bot.copy_message(chat_id=ADMIN_ID, from_chat_id=chat_id, message_id=update.message.message_id)
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text(t["upload_success_user"], reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
        return
    if user_id == ADMIN_ID:
        drip_states = load_json_file(DRIP_STATE_FILE)
        drip_state = drip_states.get(str(user_id))
        if isinstance(drip_state, dict) and drip_state.get("mode") == "collecting":
            drip_state.setdefault("items", []).append({"chat_id": chat_id, "message_id": update.message.message_id})
            drip_states[str(user_id)] = drip_state
            save_json_file(DRIP_STATE_FILE, drip_states)
            await update.message.reply_text(
                f"\u26a1 Flash Drop item #{len(drip_state['items'])} added. Send more files or tap Finish & Broadcast Drop.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("\U0001f680 Finish & Broadcast Drop")], [KeyboardButton("\u274c Cancel / Exit")]],
                    resize_keyboard=True
                )
            )
            return
        try:
            await update.message.forward(chat_id=PRIVATE_CHANNEL_ID)
            context.user_data.pop("admin_vault_upload_mode", None)
            await update.message.reply_text("\u2705 Saved to vault!", reply_markup=get_main_keyboard(get_lang(user_id), True))
        except Exception as e:
            await update.message.reply_text(f"\u274c {e}", reply_markup=get_main_keyboard(get_lang(user_id), True))
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
            forwarded = await update.message.forward(chat_id=ADMIN_ID)
            uploads = load_json_file(UPLOADS_FILE)
            uploads[str(int(time.time() * 1000))] = {
                "user_id": user_id,
                "msg_id": forwarded.message_id,
                "storage_chat_id": ADMIN_ID
            }
            save_json_file(UPLOADS_FILE, uploads)
            await update.message.reply_text(t["upload_success_user"], reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))
        except Exception as e:
            logger.exception("Fan upload forwarding/storage failed: %s", e)
            await update.message.reply_text("\u274c Failed to send your upload. Please try again.", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))

async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.message.reply_text(t["banned"]); return
    if "http" in text.lower():
        flood, wait = is_flood(user_id)
        if flood: await update.message.reply_text(f"\U0001f422 **Slow down!** You sent {FLOOD_LIMIT} links in last minute.\nWait {wait}s before next link.", parse_mode="Markdown"); return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    
    if text == t.get("menu_edit_welcome", "\u270f\ufe0f Edit Welcome Msg") and user_id == ADMIN_ID:
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
        if f_chat is None: await update.message.reply_text("\u274c Please forward a message directly from your channel, not a copied message.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        try:
            bot_member = await context.bot.get_chat_member(chat_id=f_chat.id, user_id=context.bot.id)
            if getattr(bot_member, "status", None) not in ("administrator", "creator"): await update.message.reply_text("\u26a0\ufe0f I detected the channel, but I'm not an admin there yet. Add me as an administrator, then forward a channel message again.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        except Exception as exc:
            logger.warning(f"Could not verify bot admin status in channel {getattr(f_chat, 'id', 'unknown')}: {exc}")
            await update.message.reply_text("\u26a0\ufe0f I couldn't verify my admin access. Please check my admin status and forward another channel message.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        linking_states.pop(str(user_id), None)
        save_linking_states(linking_states)
        await update.message.reply_text(f"\u2705 Linked {getattr(f_chat, 'title', 'your channel')} successfully. You can now use batch downloads to that channel.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    fl_states = load_json_file(FILE_LINK_STATE_FILE)
    fl_state = fl_states.get(str(user_id))
    if fl_state and fl_state.get("mode") == "file_link_password":
        token = fl_state.get("token")
        links = load_json_file(FILE_LINKS_FILE)
        record = links.get(token)
        fl_states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, fl_states)
        if not record or (record.get("expires_at") and time.time() > record["expires_at"]): await update.message.reply_text(t["link_invalid_expired"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        if text.strip() != str(record.get("password", "")): await update.message.reply_text("\u274c Incorrect password.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        if record.get("max_clicks", 0) and record.get("clicks", 0) >= record["max_clicks"]: await update.message.reply_text(t["link_limit_reached"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        await send_file_link_payload(update, context, token, record)
        return
    menu_texts = [t["menu_stats"], t["menu_lang"], t["menu_help"], t["menu_join"], t["menu_upload"], t["menu_uploads"], "\U0001f517 File-to-Link", "\U0001f7e2 Bot Status", "\U0001f504 Change Batch Channel", "\U0001f4e2 Broadcast", "\u26a1 Create Flash Drop", "\u2699\ufe0f Ad Toggle Panel", t.get("menu_edit_welcome", "\u270f\ufe0f Edit Welcome Msg")]
    if text in menu_texts:
        if text != t["menu_upload"]:
            context.user_data.pop("admin_vault_upload_mode", None)
        support_states = load_json_file(SUPPORT_STATES_FILE)
        if str(user_id) in support_states: del support_states[str(user_id)]; save_json_file(SUPPORT_STATES_FILE, support_states)
    if text.strip() == "\U0001f517 File-to-Link": await file_to_link_command(update, context); return
    if text.strip() == "\U0001f504 Change Batch Channel":
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
    if text == "\U0001f4be Disk Config" and user_id == ADMIN_ID:
        current = get_min_free_disk_mb()
        await update.message.reply_text(t["disk_config_prompt"].format(current), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return
    if text == "\u26a1 MTProto Config" and user_id == ADMIN_ID:
        current = get_mtproto_max_mb()
        await update.message.reply_text(t["mtproto_config_prompt"].format(current), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return
    if text.startswith("\U0001f4e6 Set Free") and user_id == ADMIN_ID:
        current = get_free_amount()
        keyboard = [[InlineKeyboardButton(f"\u2705 {i} (Current)" if i==current else f"{i} free", callback_data=f"set_free_{i}") for i in [2,3,4,5]]]
        await update.message.reply_text(t["free_panel_prompt"].format(current), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text.startswith("\U0001f381 Set Reward") and user_id == ADMIN_ID:
        current = get_reward_amount()
        keyboard = [[InlineKeyboardButton(f"\u2705 {i} (Current)" if i==current else f"{i}", callback_data=f"set_reward_{i}") for i in [1,2,3,5]]]
        await update.message.reply_text(t["reward_panel_prompt"].format(current), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == "\u2699\ufe0f Ad Toggle Panel" and user_id == ADMIN_ID:
        config = load_json_file(CONFIG_FILE)
        mode = config.get("ad_mode", "auto").upper()
        keyboard = [[InlineKeyboardButton("\U0001f504 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("\U0001f4fa Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("\U0001f310 Adsterra", callback_data="set_ad_adsterra")]]
        await update.message.reply_text(t["ad_panel_prompt"].format(mode), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    
    if user_id == ADMIN_ID and str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "admin_replying":
        target_user_id = support_states[str(user_id)]["target_user_id"]
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("\U0001f4ac Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("\U0001f512 Close", callback_data=f"support_close_{ticket_id}")]]
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"\U0001f4ac **Admin Reply:**\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            await update.message.reply_text(f"\u2705 Sent to {target_user_id}!", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except Exception as e: await update.message.reply_text(f"\u274c {e}", reply_markup=get_main_keyboard(lang, True))
        return
    if str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "user_writing":
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("\U0001f4ac Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("\U0001f512 Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"\U0001f4ac Ticket [{ticket_id}] From {user_id}\n\n{text}", parse_mode="Markdown")
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("\u2705 Sent!", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == "\u26a1 Create Flash Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        states[str(user_id)] = {"mode": "collecting", "items": []}
        save_json_file(DRIP_STATE_FILE, states)
        kb = [[KeyboardButton("\U0001f680 Finish & Broadcast Drop")],[KeyboardButton("\u274c Cancel / Exit")]]
        await update.message.reply_text("\u26a1 Flash Drop Mode: Send files", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")
        return
    if text == "\U0001f7e2 Bot Status": await status_command(update, context); return
    if text.strip() in ("\U0001f9ea Test Ad", "\U0001f4e2 Ad Info"):
        if user_id != ADMIN_ID: await update.message.reply_text("\u2705 Menu updated.", reply_markup=get_main_keyboard(lang, False)); return
        if text.strip() == "\U0001f9ea Test Ad": await send_test_ad(update.message, user_id); return
    if text.strip() == "\U0001f4e2 Ad Info" and user_id == ADMIN_ID: await update.message.reply_text(build_ad_info_text(user_id), reply_markup=get_main_keyboard(lang, True)); return
    if text == "\U0001f4e2 Broadcast" and user_id == ADMIN_ID: await update.message.reply_text("\U0001f4e2 /broadcast [message] or reply with /broadcast", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True)); return
    if text == "\u274c Cancel / Exit" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states: del states[str(user_id)]; save_json_file(DRIP_STATE_FILE, states)
        await update.message.reply_text(t["drop_cancelled"], reply_markup=get_main_keyboard(lang, True), parse_mode="Markdown")
        return
    if text == "\U0001f680 Finish & Broadcast Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        user_state = states.get(str(user_id))
        if not user_state or not user_state.get("items"): await update.message.reply_text(t["drop_no_items"], reply_markup=get_main_keyboard(lang, True)); return
        user_state["mode"] = "waiting_for_timer"
        save_json_file(DRIP_STATE_FILE, states)
        keyboard = [[InlineKeyboardButton("30s", callback_data="drop_time_30"), InlineKeyboardButton("2m", callback_data="drop_time_120")],[InlineKeyboardButton("5m", callback_data="drop_time_300"), InlineKeyboardButton("10m", callback_data="drop_time_600")]]
        await update.message.reply_text(f"Select timer: {len(user_state['items'])} items", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    # Flash Drop collects actual media in handle_user_upload(), not menu/text messages.
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
        keyboard = [[InlineKeyboardButton("\U0001f4ac Open Support", callback_data="open_support")]]
        await update.message.reply_text(f"Support: [Help]({HELP_CHANNEL_URL})", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == t["menu_lang"]: await language_command(update, context); return
    if text == t["menu_upload"]:
        if user_id == ADMIN_ID:
            context.user_data["admin_vault_upload_mode"] = True
            prompt = "\U0001f4e4 **Admin File Upload**\\nSend the file(s) you want to save to the vault."
        else:
            prompt = t["user_upload_prompt"]
        await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == t["menu_uploads"] and user_id == ADMIN_ID:
        uploads = load_json_file(UPLOADS_FILE)
        if not uploads: await update.message.reply_text(t["no_uploads"], reply_markup=get_main_keyboard(lang, True)); return
        await update.message.reply_text(t["admin_upload_prompt"], reply_markup=get_main_keyboard(lang, True))
        shown = 0
        failed = 0
        for k, data in list(uploads.items())[-20:]:
            try:
                source_chat_id = data.get("storage_chat_id", data.get("user_id"))
                await context.bot.copy_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=source_chat_id,
                    message_id=data["msg_id"]
                )
                shown += 1
            except Exception as e:
                failed += 1
                logger.warning("Could not display fan upload %s: %s", k, e)
        await update.message.reply_text(
            f"\U0001f4ec Displayed {shown} fan upload(s)." + (f"\\n\u26a0\ufe0f {failed} older upload(s) could not be retrieved." if failed else ""),
            reply_markup=get_main_keyboard(lang, True)
        )
        return
    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = [u for u in extracted_urls if not ("t.me/" in u and "start=" in u)]
    extracted_urls = filtered
    if not extracted_urls:
        if "t.me/" in text and "start=" in text: await update.message.reply_text("\U0001f446 Please use the buttons above.", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
                else: await update.message.reply_text("\u26a0\ufe0f Ad server busy, try again in a moment.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
                return
            else:
                try:
                    tut = await context.bot.forward_message(chat_id=chat_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    await asyncio.sleep(0.2)
                except: pass
                bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
                keyboard = [[InlineKeyboardButton("\U0001f513 Open Link & Watch Timer \u23f0 20s +1", url=bridge_link)], [InlineKeyboardButton("\U0001f4e2 Join Public Channel \U0001f49c", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("\U0001f49c Check & Get Files \u2705 +1", callback_data="verify_user")]]
                await update.message.reply_text(t["limit_reached"] + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                return
    if active_batch_sessions.get(user_id, False): return
    if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
        f_chat = update.message.forward_origin.chat
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        await update.message.reply_text(f"\u2705 Linked {f_chat.title}", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"batchtype_video_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"batchtype_audio_{payload_key}")]]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    url = extracted_urls[0]
    status_preview = await update.message.reply_text("\U0001f50d Checking link...")
    title, dur = fetch_url_metadata(url)
    try: await status_preview.delete()
    except: pass
    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],[InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")]]
    await update.message.reply_text(f"\U0001f3ac {title}\n\u23f1\ufe0f {dur}\n\n{t['ask_format']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
        await update.message.reply_text(f"\U0001f504 Restoring <b>{document.file_name}</b>...", parse_mode="HTML")
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

    # Flash Drop takes priority over normal .txt batch-link parsing for admin uploads.
    drip_states = load_json_file(DRIP_STATE_FILE)
    drip_state = drip_states.get(str(user_id))
    if user_id == ADMIN_ID and isinstance(drip_state, dict) and drip_state.get("mode") == "collecting":
        await handle_user_upload(update, context)
        return

    # Files explicitly sent through the admin Upload File menu go to the vault,
    # including .txt documents; normal .txt batch lists remain supported otherwise.
    if user_id == ADMIN_ID and context.user_data.get("admin_vault_upload_mode"):
        await handle_user_upload(update, context)
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
        keyboard = [[InlineKeyboardButton("\U0001f3ac Video", callback_data=f"batchtype_video_{payload_key}")]]
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
    for idx,(uid,info) in enumerate(sorted_users,1): top_text+=f"{idx}. `{uid}` \u2014 {info.get('total_interactions',0)}\n"
    if not top_text: top_text="No activity yet"
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    used_mb = get_downloads_usage_mb()
    cache = load_json_file(CACHE_FILE)
    flood_data = load_json_file(FLOOD_FILE)
    banned = load_json_file(BANNED_FILE)
    total_hits = sum(v.get("hits",0) for v in cache.values() if isinstance(v, dict))
    host_free = shutil.disk_usage(".").free // (1024*1024) if os.path.exists(".") else 0
    txt = (f"\U0001f4ca **ADVANCED ADMIN**\n\n\u2022 Total: **{total_users}**\n\u2022 24h Active: **{active_24hr}**\n\u2022 Ad Mode: **{mode}**\n\n\U0001f4e2 **Ad Split:**\n\u2022 Monetag: **{adsgram_count}**\n\u2022 Adsterra: **{adsterra_count}**\n\n\U0001f5a5\ufe0f **Render:**\n\u2022 Used: **{used_mb}MB**\n\u2022 Free: **{free_mb}MB**\n\u2022 Host: **{host_free}MB**\n\u2022 Active: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\n\u2022 Queue: **{download_queue.qsize()}**\n\u2022 Cache: **{len(cache)}** files\n\u2022 Hits: **{total_hits}** saved\n\u2022 Flood: **{len(flood_data)}**\n\u2022 Banned: **{len(banned)}**\n\n\U0001f39e\ufe0f **Video Vault:** `{VIDEO_VAULT_ID}`\n\U0001f3c6 **Top 10:**\n{top_text}")
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    cache = load_json_file(CACHE_FILE)
    await update.message.reply_text(f"\U0001f7e2 **Status V38 Monetag**\nMode: **{mode}**\nFree: **{free_mb}MB**\nDL: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\nQueue: **{download_queue.qsize()}**\nCache: **{len(cache)}**\nVault: **{VIDEO_VAULT_ID}**\nReward: +1 realistic\nFlood: **ON**\nBackup: **6hr to {PRIVATE_CHANNEL_ID}**", parse_mode="Markdown", reply_markup=get_main_keyboard(get_lang(update.message.from_user.id), update.message.from_user.id == ADMIN_ID))

async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID: return
    file_list = "\n".join([f"   \u2022 <b>{f}</b>" for f in BACKUP_FILES])
    await update.message.reply_text(f"\U0001f504 <b>Restore Backup Files</b>\n\n1. Go to your private backup channel.\n2. <b>Long-press</b> a backup file, then tap all the others to select them.\n3. Hit <b>Forward</b> and send them all to this bot at once!\n\n<b>Files to restore:</b>\n{file_list}\n\nI will automatically detect and restore each file! \u26a1", parse_mode="HTML", reply_markup=get_main_keyboard("en", True))

async def toggle_ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    keyboard = [[InlineKeyboardButton("\U0001f504 Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("\U0001f4fa Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("\U0001f310 Adsterra", callback_data="set_ad_adsterra")]]
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
    status_msg = await update.message.reply_text(f"\U0001f680 Broadcasting to {len(all_users)}...", parse_mode="Markdown")
    success = fail = 0
    for uid in all_users:
        if uid == ADMIN_ID or is_banned(uid): continue
        try:
            if reply_msg: await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=reply_msg.message_id)
            else: await context.bot.send_message(chat_id=uid, text=" ".join(args), parse_mode="Markdown")
            success+=1
            await asyncio.sleep(0.05)
        except: fail+=1
    await status_msg.edit_text(f"\u2705 Done\nSent: {success}\nFail: {fail}", parse_mode="Markdown")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: /ban <user_id>", reply_markup=get_main_keyboard("en", True)); return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        banned[target] = {"banned_at": time.time(), "reason": "spam"}
        save_json_file(BANNED_FILE, banned)
        await update.message.reply_text(f"\U0001f6ab Banned {target}", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except Exception as e: await update.message.reply_text(f"\u274c {e}", reply_markup=get_main_keyboard("en", True))

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: /unban <user_id>", reply_markup=get_main_keyboard("en", True)); return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        if target in banned:
            del banned[target]
            save_json_file(BANNED_FILE, banned)
            await update.message.reply_text(f"\u2705 Unbanned {target}", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
        else: await update.message.reply_text(f"Not banned", reply_markup=get_main_keyboard("en", True))
    except Exception as e: await update.message.reply_text(f"\u274c {e}", reply_markup=get_main_keyboard("en", True))

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(f"\U0001f4e6 Backing up ALL files to {PRIVATE_CHANNEL_ID}...", reply_markup=get_main_keyboard("en", True))
    await backup_to_channel(context.bot)
    await update.message.reply_text("\u2705 Full Backup sent!", reply_markup=get_main_keyboard("en", True))

async def set_disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/setdisk <mb>`\nExample: `/setdisk 500`", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
    try:
        value = int(context.args[0])
        if value < 50: await update.message.reply_text("\u26a0\ufe0f Value must be at least 50MB.", reply_markup=get_main_keyboard("en", True)); return
        config = load_json_file(CONFIG_FILE)
        config["min_free_disk_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"\u2705 Minimum free disk space set to **{value}MB**", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except ValueError: await update.message.reply_text("\u274c Invalid number.", reply_markup=get_main_keyboard("en", True))

async def set_mtproto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/setmtproto <mb>`\nExample: `/setmtproto 1000`", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
    try:
        value = int(context.args[0])
        if value < 50: await update.message.reply_text("\u26a0\ufe0f Value must be at least 50MB.", reply_markup=get_main_keyboard("en", True)); return
        config = load_json_file(CONFIG_FILE)
        config["mtproto_max_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"\u2705 MTProto max upload size set to **{value}MB**", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except ValueError: await update.message.reply_text("\u274c Invalid number.", reply_markup=get_main_keyboard("en", True))

async def cached_download_and_send(bot, chat_id, user_id, url, dl_type, t):
    cache = load_json_file(CACHE_FILE)
    ckey = await get_canonical_key(url, chat_id, bot)
    
    if ckey in cache and "file_id" in cache[ckey] and "qualities" not in cache[ckey]:
        cache[ckey]["qualities"] = {"720p": {"file_id": cache[ckey]["file_id"], "vault_msg_id": cache[ckey].get("vault_msg_id"), "size": cache[ckey].get("size", "unknown")}}
        del cache[ckey]["file_id"]
        save_json_file(CACHE_FILE, cache)

    # ===== EDIT B: carousel cache hit (instant) =====
    if ckey in cache and cache[ckey].get("type") == "carousel" and dl_type in ("video", "images"):
        try:
            kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
            ids = await send_cached_carousel(bot, chat_id, cache[ckey], ckey)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, ids + [warn.message_id], 540))
            cache[ckey]["hits"] = cache[ckey].get("hits", 0) + 1
            save_json_file(CACHE_FILE, cache)
            deduct_download_counter(user_id, is_batch=False)
            return True
        except Exception as e:
            logger.error(f"Carousel cache hit failed {ckey}: {e}")  # falls through to re-download
    # =================================================

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
            try:
                cached = cached_qualities[best_cached_quality]
                file_id = cached.get("file_id")
                if file_id:
                    sz = cached.get("size", "")
                    qual_tag = f"[{best_cached_quality}]"
                    kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
                    if dl_type == 'video': 
                        sent = await bot.send_video(chat_id=chat_id, video=file_id, caption=t["cached_instant_video"].format(qual_tag, sz, ckey), reply_markup=kb)
                    elif dl_type == 'audio': 
                        sent = await bot.send_audio(chat_id=chat_id, audio=file_id, caption=t["cached_instant_audio"].format(ckey), reply_markup=kb)
                    else: 
                        sent = await bot.send_photo(chat_id=chat_id, photo=file_id, caption=t["cached_instant_image"].format(ckey), reply_markup=kb)
                    
                    warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                    asyncio.create_task(schedule_deletion(bot, chat_id, [sent.message_id, warn.message_id], 540))
                    cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                    save_json_file(CACHE_FILE, cache)
                    deduct_download_counter(user_id, is_batch=False)
                    return True
            except Exception as e:
                logger.error(f"Cache send fail {ckey} {best_cached_quality}: {e}")
                try:
                    vmid = cached.get("vault_msg_id")
                    if vmid:
                        kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
                        fwd = await bot.forward_message(chat_id=chat_id, from_chat_id=VIDEO_VAULT_ID, message_id=vmid)
                        warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"] + " (from vault)", reply_markup=kb)
                        asyncio.create_task(schedule_deletion(bot, chat_id, [fwd.message_id, warn.message_id], 540))
                        cache[ckey]["hits"] = cache[ckey].get("hits",0)+1
                        save_json_file(CACHE_FILE, cache)
                        deduct_download_counter(user_id, is_batch=False)
                        return True
                except Exception as e2:
                    logger.error(f"Vault fallback fail: {e2}")
                    if ckey in cache and "qualities" in cache[ckey] and best_cached_quality in cache[ckey]["qualities"]:
                        del cache[ckey]["qualities"][best_cached_quality]
                        save_json_file(CACHE_FILE, cache)

    status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type) + f"\n`{ckey}`", parse_mode="Markdown")
    try:
        free_mb = shutil.disk_usage(".").free // (1024*1024)
        min_free = get_min_free_disk_mb()
        effective_max_mb = mtproto_limit_mb()
        if free_mb < min_free + 150: effective_max_mb = min(effective_max_mb, 50)
            
        LAST_CAROUSEL_TRACE.clear()
        file_paths, res, size = await asyncio.wait_for(
            asyncio.to_thread(download_media_engine, url, dl_type, effective_max_mb), timeout=420)
        if user_id == ADMIN_ID and LAST_CAROUSEL_TRACE:
            try:
                await bot.send_message(chat_id=chat_id, text="\U0001f9ea Carousel trace:\n" + "\n".join(LAST_CAROUSEL_TRACE)[:3500])
            except Exception:
                pass
        if not file_paths: raise ValueError("FILE_NOT_FOUND")
        
        cache = load_json_file(CACHE_FILE)
        if ckey not in cache: cache[ckey] = {"type": dl_type, "timestamp": time.time(), "qualities": {}, "hits": 0}
            
        qual_tag = f"[{res}]"
        kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)

        # ===== EDIT C: fresh carousel download =====
        if res == "carousel":
            try:
                results = await send_carousel(bot, chat_id, file_paths, ckey, status_msg, send_video_file)
                if not results: raise ValueError("FILE_NOT_FOUND")
                await save_carousel_cache(bot, ckey, results, size)
                warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                asyncio.create_task(schedule_deletion(bot, chat_id, [r["message_id"] for r in results] + [warn.message_id], 540))
            finally:
                shutil.rmtree(os.path.dirname(file_paths[0]), ignore_errors=True)
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            deduct_download_counter(user_id, is_batch=False)
            await bot.send_message(chat_id=chat_id, text=t["download_success"], reply_markup=kb)
            return True
        # =============================================

        if dl_type == 'images':
            media_group = [InputMediaPhoto(media=open(p, 'rb')) for p in file_paths]
            sent_media = await bot.send_media_group(chat_id=chat_id, media=media_group)
            warn = await bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)), reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, [m.message_id for m in sent_media] + [warn.message_id], 540))
            try:
                vmsg = await bot.send_photo(chat_id=VIDEO_VAULT_ID, photo=sent_media[0].photo[-1].file_id, caption=ckey)
                cache[ckey]["qualities"]["original"] = {"file_id": sent_media[0].photo[-1].file_id, "vault_msg_id": vmsg.message_id, "size": size}
            except: cache[ckey]["qualities"]["original"] = {"file_id": sent_media[0].photo[-1].file_id, "size": size}
            for p in file_paths: os.remove(p)
        elif dl_type == 'audio':
            sent_media = await send_audio_file(bot, chat_id, file_paths[0], f"\U0001f3b5 Size {size} `{ckey}`", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent_media.audio.file_id, caption=ckey)
                cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "vault_msg_id": vmsg.message_id, "size": size}
            except: cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "size": size}
            os.remove(file_paths[0])
        else:
            sent_media = await send_video_file(bot, chat_id, chat_id, file_paths[0], f"\u2728 {qual_tag} Size {size} `{ckey}`", "Markdown", status_msg)
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
        if user_id == ADMIN_ID:
            trace_txt = ("\nTrace:\n" + "\n".join(LAST_CAROUSEL_TRACE)[:1200]) if LAST_CAROUSEL_TRACE else ""
            try:
                await bot.send_message(chat_id=chat_id, text=(
                    f"\U0001f9ea DL error: {type(e).__name__}: {str(e)[:500]}\n"
                    f"MTProto: ready={MTPROTO['ready'].is_set()} api_id={bool(API_ID)} api_hash={bool(API_HASH)}"
                    f"{trace_txt}"))
            except Exception: pass
        if "FILE_TOO_LARGE" in str(e): err = t["error_50mb"]
        elif "MTPROTO_OFF" in str(e): err = "\u26a0\ufe0f Big files need fast mode, which is offline right now."
        elif "MTPROTO_PEER" in str(e): err = "\u26a0\ufe0f Send /start to this bot once, then send the link again."
        elif "SITE_BLOCKED" in str(e): err = "\u26a0\ufe0f This site is blocking downloads from our server right now. Please try again later."
        elif isinstance(e, (asyncio.TimeoutError, TimeoutError)): err = "\u26a0\ufe0f This is taking too long, so I stopped. Please try again later."
        else: err = t["error_generic"]
        kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
        try: await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=err, reply_markup=kb)
        except: pass
        return False

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
                  [InlineKeyboardButton("Never", callback_data="fl_exp_never"), InlineKeyboardButton("\u2b05 Back", callback_data="fl_refresh")]]
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
                  [InlineKeyboardButton("\u2b05 Back", callback_data="fl_refresh")]]
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
                        reward_kb = [[InlineKeyboardButton("\U0001f513 Open Link & Watch Timer \u23f0 20s +1", url=bridge_link)], [InlineKeyboardButton("\U0001f4e2 Join Public Channel \U0001f49c", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("\U0001f49c Check & Get +1", callback_data="verify_user")]]
                        await query.message.reply_text(t["limit_reached"] + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup(reward_kb), parse_mode="Markdown")
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
        keyboard = [[InlineKeyboardButton("\U0001f381 Claim Now", url=claim_url)]]
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
            warn = await context.bot.send_message(chat_id=user_id, text=f"\u23f3 Auto-deletes in {drop.get('delete_label','9 Minutes')}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            sent_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, sent_ids, drop.get("delete_delay",540)))
        except Exception as e: await context.bot.send_message(chat_id=user_id, text=f"\u274c {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
        keyboard = [[InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{dl_type}_{payload_key}")], [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{dl_type}_{payload_key}")], [InlineKeyboardButton("\U0001f504 Change Channel", callback_data="change_channel")]]
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
        await query.message.reply_text(t["monetag_fallback_prompt"] + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f513 Open Adsterra Link", url=bridge_link)], [InlineKeyboardButton("\u2705 Check & Get +1", callback_data="verify_user")]]), parse_mode="Markdown")
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
            except Exception as e: await context.bot.send_message(chat_id=chat_id, text=f"\u274c {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
            keyboard = [[InlineKeyboardButton("\u25b6\ufe0f Resume Batch +1", callback_data="resume_batch")]]
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
            warn = await context.bot.send_message(chat_id=user_id, text="\u23f3 Auto-deletes in 9 mins", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            fwd_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, fwd_ids, 540))
        except Exception as e: await query.message.reply_text(f"\u274c {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))

ADSTERRA_USER_GUIDE = (
    "\n\n\u26a0\ufe0f **Adsterra not opening or visit not detected?**\n"
    "1. Temporarily disable Private DNS, ad blockers, and ad-filtering apps.\n"
    "2. Turn off VPN or proxy.\n"
    "3. Tap **Open Link** and choose **Open in browser** (not inside Telegram).\n"
    "4. Let the page load and keep it open for at least **20 seconds**.\n"
    "5. Return here and tap **Check & Get +1**.\n\n"
    "Detection depends on Adsterra and your browser/network; these steps do not guarantee a reward."
)

TEST_AD_TEXT = "\U0001f9ea AD PLACEMENT TEST\n\n1\ufe0f\u20e3 User sends link\n2\ufe0f\u20e3 User gets 4 FREE downloads\n3\ufe0f\u20e3 LIMIT REACHED screen appears\n4\ufe0f\u20e3 Tap Watch Ad\n5\ufe0f\u20e3 Tap Check & Get +1\n\n\U0001f447 TRY THE AD NOW:"

async def send_adsgram_test(message, user_id):
    extra = [[InlineKeyboardButton("\U0001f6e0 Admin: simulate ad finished", callback_data="admin_sim_ad")]] if user_id == ADMIN_ID else None
    kb = adsgram_keyboard(user_id, "test", 0, 0, extra)
    if not kb: await message.reply_text("\u26a0\ufe0f Ad server not reachable.", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)); return
    await message.reply_text(TEST_AD_TEXT, reply_markup=kb)

ADSTERRA_TEST_TEXT = "\U0001f9ea AD PLACEMENT TEST (Adsterra)\n\n1\ufe0f\u20e3 User sends link\n2\ufe0f\u20e3 LIMIT REACHED screen appears\n3\ufe0f\u20e3 Stay 20s on ad page\n4\ufe0f\u20e3 Tap Check & Get +1\n\n\U0001f447 TRY THE AD NOW:" + ADSTERRA_USER_GUIDE

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
    keyboard = [[InlineKeyboardButton("\U0001f513 Open Link & Watch Timer \u23f0 20s +1", url=bridge_link)], [InlineKeyboardButton("\U0001f4e2 Join Public Channel \U0001f49c", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("\U0001f49c Check & Get Files \u2705 +1", callback_data="verify_user")]]
    await message.reply_text(ADSTERRA_TEST_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))

async def send_test_ad(message, user_id):
    if get_global_ab_network(user_id) == "monetag": await send_adsgram_test(message, user_id)
    else: await send_adsterra_test(message, user_id)

def build_ad_info_text(user_id):
    mode = load_json_file(CONFIG_FILE).get("ad_mode", "auto")
    monetag = "\u2022 Monetag: LIMIT REACHED screen -> Watch Ad Mini App -> Check & Get +1\n"
    adsterra = "\u2022 Adsterra: LIMIT REACHED screen -> Open Link 20s -> Check & Get +1\n"
    if mode in ("monetag", "adsgram"): head, body = "Mode: MONETAG only", monetag
    elif mode == "adsterra": head, body = "Mode: ADSTERRA only", adsterra
    else:
        net = "Monetag" if get_global_ab_network(user_id) == "monetag" else "Adsterra"
        head, body = f"Mode: AUTO (you currently get {net})", monetag + adsterra
    return ("\U0001f4e2 AD INFO\n\nBot: @Michaelbbcvaultbot\n" + head + "\n\n\U0001f4cd Exact ad placement:\n" + body + "\n\u2022 Reward: +1 download per completed ad\n\n\U0001f9ea To test: tap \U0001f9ea Test Ad or send /testad")

async def test_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await send_test_ad(update.message, update.effective_user.id)

async def tokencheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    mine = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:8] if BOT_TOKEN else "none"
    try: s = requests.get(f"{WEB_BASE_URL}/monetag-selfcheck", timeout=15).json()
    except Exception as e: await update.message.reply_text(f"\u274c Could not reach server: {type(e).__name__}", reply_markup=get_main_keyboard("en", True)); return
    same = (s.get("fingerprint") == mine)
    lines = ["\U0001f510 TOKEN CHECK", f"Render bot: fingerprint {mine}", f"PythonAnywhere: fingerprint {s.get('fingerprint')}", f"PA token works: {s.get('telegram_ok')}"]
    lines.append("\u2705 MATCH" if same else "\u274c DIFFERENT")
    await update.message.reply_text("\n".join(lines), reply_markup=get_main_keyboard("en", True))

async def ad_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(build_ad_info_text(update.effective_user.id), reply_markup=get_main_keyboard("en", True))

EXTRAS_STATUS = "\u23f3 Extras not loaded yet"
import socket as _socket
INSTANCE_ID = f"{_socket.gethostname()[-6:]}-{uuid.uuid4().hex[:4]}"   # changes on every start: shows WHICH running copy answered
_CONFLICT_WARNED = [0.0]

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        clean_downloads_startup()
        app = Application.builder().token(BOT_TOKEN).build()
        # ---- load the extras add-on (Limits, Required Channels, quality picker, metadata, progress card) ----
        # Finds the file even if it was saved as "extras. Py", "extras.py.txt", "extras.txt", etc.
        # If it fails, the bot still runs and the admin gets a Telegram message with the exact reason.
        global EXTRAS_STATUS
        try:
            import glob, importlib.util, importlib.machinery, traceback
            _here = os.path.dirname(os.path.abspath(__file__))
            _cands = [os.path.join(_here, "extras.py")]
            _cands += sorted(p for p in glob.glob(os.path.join(_here, "*")) if os.path.basename(p).lower().replace(" ", "").startswith("extras") and os.path.isfile(p))
            _cands += [os.path.join(os.getcwd(), "extras.py")]
            _path = next((p for p in _cands if os.path.isfile(p)), None)
            if not _path:
                raise FileNotFoundError(f"no extras file found in {_here} (files: {', '.join(sorted(os.listdir(_here)))[:500]})")
            _loader = importlib.machinery.SourceFileLoader("extras", _path)
            _spec = importlib.util.spec_from_loader("extras", _loader)
            extras = importlib.util.module_from_spec(_spec)
            sys.modules["extras"] = extras
            _loader.exec_module(extras)
            extras.init(globals())
            extras.register(app)
            EXTRAS_STATUS = f"\u2705 Extras loaded from: {os.path.basename(_path)}"
        except Exception as _e:
            EXTRAS_STATUS = f"\u274c Extras NOT loaded: {type(_e).__name__}: {str(_e)[:700]}"
            logger.exception("extras failed to load")
        print(EXTRAS_STATUS, flush=True)

        async def extras_status_command(update, context):
            if update.effective_user.id != ADMIN_ID: return
            await update.message.reply_text(f"{EXTRAS_STATUS}\n\U0001f194 Copy: {INSTANCE_ID}", reply_markup=get_main_keyboard("en", True))
        app.add_handler(CommandHandler("extras", extras_status_command))
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
        _loop = asyncio.get_running_loop()
        def _poll_error(err):
            # "Conflict" = ANOTHER copy of this bot (same token) is running somewhere and stealing messages
            logger.error(f"polling error: {err}")
            if "Conflict" in type(err).__name__ or "terminated by other getUpdates" in str(err):
                if time.time() - _CONFLICT_WARNED[0] > 600:
                    _CONFLICT_WARNED[0] = time.time()
                    _loop.create_task(app.bot.send_message(chat_id=ADMIN_ID, text=(
                        f"\u26a0\ufe0f Another copy of this bot is running with the same token!\n"
                        f"This copy: {INSTANCE_ID}\n"
                        f"Messages are being split between the copies, so some users get the OLD bot "
                        f"(no quality picker, no metadata). Stop the other copy (old Render service, "
                        f"PythonAnywhere, your PC, or more than 1 worker).")))
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES, error_callback=_poll_error)
        try:   # tell the admin on every restart whether the extras loaded (also refreshes the admin keyboard)
            await app.bot.send_message(chat_id=ADMIN_ID, text=f"\U0001f916 Bot restarted\n{EXTRAS_STATUS}\n\U0001f194 Copy: {INSTANCE_ID}", reply_markup=get_main_keyboard("en", True))
        except Exception as e: logger.warning(f"startup notice failed: {e}")
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
    try: await status_msg.edit_text(f"\U0001f4e4 Uploading {os.path.getsize(path)/(1024*1024):.0f}MB in fast mode...")
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)  # must exist BEFORE pyrogram is imported (Python 3.14)
    try:
        from pyrogram import Client as PyroClient
    except Exception as e:
        print(f"MTProto worker skipped: pyrogram import failed: {type(e).__name__}: {e}")
        return
    try:
        from pyrogram import enums as pyro_enums
        MTPROTO["no_parse"] = pyro_enums.ParseMode.DISABLED
    except Exception:
        MTPROTO["no_parse"] = None
    import inspect
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