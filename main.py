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
        "welcome": "ðŸš€ **WELCOME TO MICHAELBBC VAULT - ALL MEDIA DOWNLOADER!**\n\nðŸ”¥ WHAT I CAN DO:\nðŸŽ¬ VIDEOS HD No Watermark!\nðŸŽµ AUDIO MP3 192kbps!\nðŸ–¼ï¸ IMAGES Scrape ALL!\nðŸ“ SUBTITLES Auto!\nðŸ“¦ BATCH 100+ Links!\nâš¡ CACHE 1 Sec!\nðŸ’Ž VAULT Forever!\nðŸ“¤ UPLOAD FILES!\nðŸ”— FILE-TO-LINK: Create shareable links!\n\nðŸ‘‰ PASTE LINK TO START! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ Video (MP4)", "btn_audio": "ðŸŽµ Audio (MP3)", "btn_image": "ðŸ–¼ï¸ Images", "btn_sub": "ðŸ“ Subtitles (SRT)",
        "ask_format": "ðŸ‘‡ **AWESOME! What format you want? Pick below!**",
        "fetching": "ðŸ“¥ **Fetching your {}... Hang tight! â³âœ¨**",
        "error_generic": "âŒ Oops! Failed! ðŸ˜¢ Link private/blocked. Try public link!",
        "error_50mb": "âŒ Too Big! ðŸ˜… This video is over 300MB. Try a shorter one!", 
        "error_no_img": "âŒ No images found! ðŸ˜¢ Try another link!",
        "images_received": "â³ **{} Images received.**",
        "select_lang": "ðŸŒ Select your language! Choose below! ðŸ‘‡", 
        "lang_set": "âœ… Language set! Enjoy! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Batch Detected ({} links)**\nWhat format?",
        "batch_dest": "ðŸ“¦ **Where to send?**",
        "btn_chat": "ðŸ“¥ In Chat", "btn_chan": "ðŸ“¢ To Channel",
        "limit_reached": "âš ï¸ **Limit Reached!** You used 4 FREE! Watch 20s ad â†’ Get +1 download!",
        "refill_btn": "ðŸ”“ Open Link & Refill +1",
        "join_btn": "ðŸ“¢ Join Channel", "check_btn": "ðŸ’œ Check Balance",
        "limit_batch": "âš ï¸ **Batch Limit Reached at {} of {}**\nWatch 20s ad â†’ +1 download to continue.",
        "batch_start": "ðŸ“¦ **Batch Started:** {} **{} files**\nâ³ Processing...",
        "batch_done": "ðŸ **Done!** âœ… {} âŒ {}\nðŸ“¥ {} files here.",
        "batch_done_chan": "ðŸ **Done!** âœ… {} âŒ {}\nðŸ“¢ {} files forwarded!",
        "dl_video": "ðŸ“¥ Downloading video...", "dl_audio": "ðŸ“¥ Extracting audio...", "dl_image": "ðŸ“¥ Scraping images...", "dl_sub": "ðŸ“¥ Fetching subtitles...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Blocked/private", "failed_generic": "âŒ Failed",
        "menu_lang": "ðŸŒ Language", "menu_stats": "ðŸ“Š My Stats", "menu_help": "ðŸ’¬ Support / FAQ", "menu_join": "ðŸ“¢ Join Channel",
        "menu_uploads": "ðŸ¿ Fan Uploads", "menu_upload": "ðŸ“¤ Upload File",
        "admin_upload_prompt": "ðŸ“‚ **Fan Uploads Inbox**",
        "user_upload_prompt": "ðŸ“¤ **Upload File**\nSend video/image/file to Admin. Limit 5/24h.",
        "upload_success_user": "âœ… Sent to Admin!",
        "upload_limit_reached": "âš ï¸ Upload limit 5/24h reached.",
        "no_uploads": "ðŸ“­ No uploads yet.",
        "stats_msg": "ðŸ“Š **Your Stats:**\nâ€¢ Downloads Left: {}\nâ€¢ Batch Left: {}",
        "change_channel_prompt": "ðŸ”„ **Change Batch Channel**\n1. Make sure I am an admin in the new channel.\n2. Forward any message from that channel here.",
        "disk_config_prompt": "ðŸ’¾ **Disk Config**\nCurrent min free disk: **{}MB**\nTo change: `/setdisk <value>`",
        "mtproto_config_prompt": "âš¡ **MTProto Config**\nCurrent max upload: **{}MB**\nTo change: `/setmtproto <value>`",
        "free_panel_prompt": "ðŸ“¦ FREE DOWNLOADS\nCurrent free per day: {}",
        "reward_panel_prompt": "ðŸŽ REWARD PANEL\nCurrent: +{} download per 20s ad",
        "ad_panel_prompt": "âš™ï¸ Ad Panel\nCurrent: {}",
        "password_saved": "ðŸ” Password saved.",
        "password_too_long": "Password must be 64 chars or fewer.",
        "file_to_link_prompt": "ðŸ”— **File-to-Link**\nSend the file(s) you want to share.",
        "link_invalid_expired": "âŒ This link is invalid or expired.",
        "link_limit_reached": "â›” This link reached its usage limit.",
        "link_password_protected": "ðŸ” This link is password protected. Send the password.",
        "files_sent": "âœ… Your files have been sent.",
        "file_added": "ðŸ“¥ Added file #{}. Send more, or tap Create Link.",
        "fl_cancelled": "File-to-Link cancelled",
        "fl_start_again": "Start File-to-Link again with /filetolink",
        "fl_choose_expiry": "Choose link expiry:",
        "fl_expiry_updated": "Expiry updated",
        "fl_choose_max_uses": "Choose max successful deliveries:",
        "fl_uses_updated": "Usage limit updated",
        "fl_set_password": "Send a password, or /clearpassword to remove.",
        "fl_link_created": "Link created",
        "fl_link_ready": "ðŸ”— Your link is ready:\n{}\nFiles: {}\nCost: 1 free daily download",
        "fl_daily_limit": "Daily free limit reached. Watch an ad to earn more.",
        "fl_ad_busy": "âš ï¸ Ad server busy.",
        "admin_skipped": "âœ… Skipped!",
        "admin_bypassed": "âœ… Bypassed",
        "free_set": "âœ… Free set to {}!",
        "free_updated": "âœ… Free Downloads updated to {}!",
        "reward_set": "âœ… Reward set to +{}!",
        "reward_updated": "âœ… Reward updated to +{}!",
        "mode_updated": "âœ… Mode: {}",
        "support_opened": "âœï¸ Send message/photo/video/file below.",
        "admin_reply_mode": "âœï¸ Reply to {}:",
        "user_reply_mode": "âœï¸ Type follow-up below",
        "support_closed": "ðŸ”’ Closed",
        "drop_cancelled": "âŒ Cancelled",
        "drop_no_items": "âš ï¸ No items!",
        "drop_timer_set": "{} set!",
        "drop_broadcasting": "ðŸš€ Broadcasting {} items to {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nAuto-deletes in {}\nTap to claim:",
        "drop_done": "âœ… Broadcast done to {}",
        "age_expired": "â³ Expired!",
        "age_claimed": "âŒ Already claimed!",
        "age_verified": "Verified!",
        "age_denied": "âŒ Denied. Must be 18+",
        "lang_updated": "Updated!",
        "batch_expired": "Expired",
        "batch_loading": "Loading...",
        "batch_no_channel": "No channel linked!",
        "batch_setup_prompt": "ðŸ“¦ Setup: Make bot admin in channel and forward a message here",
        "batch_mode_activated": "Mode activated!",
        "batch_change_dest": "ðŸ”„ **Change Destination Channel**\nMake bot admin in new channel, then forward a message here.",
        "join_channel_first_alert": "Join channel first! ðŸ“¢ Must join!",
        "join_channel_first": "Join channel first! ðŸ“¢",
        "watch_timer_first": "â° Open the link and watch the 20s timer first!",
        "test_ad_verified": "âœ… Test Ad Verified! +1",
        "test_ad_verified_msg": "âœ… **TEST AD VERIFIED!**\nReward: +1 download refilled!",
        "finish_timer_first": "â° Finish 20s timer first!",
        "verified_added": "Verified! +1 added",
        "resume_prompt": "âœ… Verified! Refilled +1. Resume?",
        "refilled_download": "âœ… Refilled +1! Download again.",
        "fetching_bundle": "âœ… Verified! Fetching bundle...",
        "outdated_button": "This button is outdated. Send your link again.",
        "stopping": "Stopping...",
        "stopped": "ðŸ›‘ Stopped",
        "resuming": "Resuming...",
        "checking_vault": "Checking vault & server load...",
        "server_busy": "â³ **Server Busy**\nActive: {}/{}\nFree: {}MB\nQueue: #{}\nWill start auto!",
        "simulated": "ðŸ›  Simulated! Now tap Check & Get +1",
        "server_unreachable": "âŒ Server unreachable",
        "monetag_failed_twice": "Complete two failed Monetag attempts first.",
        "monetag_fallback_prompt": "ðŸŒ Monetag failed twice. Continue with Adsterra:",
        "adsterra_ready": "Adsterra fallback ready",
        "finish_monetag": "ðŸ“º Finish the Monetag ad in Mini App, then check again.",
        "monetag_failed_use_adsterra": "Monetag failed twice. Use Adsterra fallback below.",
        "ad_link_expired": "Ad link expired. Send your link again.",
        "ad_verified_added": "âœ… Ad verified! +{} added",
        "test_ad_completed": "âœ… TEST AD VERIFIED\nReward credited: +{} download.",
        "sponsor_viewed": "âœ… Sponsor viewed! +{} added",
        "refilled_send_again": "âœ… Refilled +{}! Send your link again.",
        "queued": "â³ Queued #{}",
        "banned": "ðŸš« You are banned.",
        "no_links": "âŒ No links found.",
        "batch_count": "ðŸ“¦ Batch {} links",
        "restore_invalid_json": "âŒ Restore failed: **{}** is not valid JSON.",
        "restore_failed": "âŒ Restore failed: {}",
        "restore_success": "âœ… **Restore Successful!**\nFile: **{}**\nRestored **{}** entries.",
        "admin_edit_welcome_prompt": "âœï¸ Send the new Welcome Message. Use `{bot_name}` for bot username.",
        "admin_welcome_updated": "âœ… Welcome message updated!",
        "menu_edit_welcome": "âœï¸ Edit Welcome Msg",
        "cached_instant_video": "âš¡ Cached Instant [{}] {} {}",
        "cached_instant_audio": "âš¡ **Cached Instant** `{}`",
        "cached_instant_image": "âš¡ **Cached Instant** `{}`",
        "auto_delete_9m": "â³ Auto-deletes in 9 mins",
        "download_success": "âœ… Download successful!"
    },
    "hi": {
        "welcome": "ðŸš€ **MICHAELBBC VAULT à¤®à¥‡à¤‚ à¤¸à¥à¤µà¤¾à¤—à¤¤ à¤¹à¥ˆ - à¤‘à¤² à¤®à¥€à¤¡à¤¿à¤¯à¤¾ à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡à¤°!**\n\nðŸ”¥ à¤®à¥ˆà¤‚ à¤•à¥à¤¯à¤¾ à¤•à¤° à¤¸à¤•à¤¤à¤¾ à¤¹à¥‚à¤:\nðŸŽ¬ à¤µà¥€à¤¡à¤¿à¤¯à¥‹ HD à¤¨à¥‹ à¤µà¥‰à¤Ÿà¤°à¤®à¤¾à¤°à¥à¤•!\nðŸŽµ à¤‘à¤¡à¤¿à¤¯à¥‹ MP3 192kbps!\nðŸ–¼ï¸ à¤‡à¤®à¥‡à¤œà¥‡à¤¸ à¤¸à¥à¤•à¥à¤°à¥‡à¤ª ALL!\nðŸ“ à¤¸à¤¬à¤Ÿà¤¾à¤‡à¤Ÿà¤²à¥à¤¸ à¤‘à¤Ÿà¥‹!\nðŸ“¦ à¤¬à¥ˆà¤š 100+ à¤²à¤¿à¤‚à¤•à¥à¤¸!\nâš¡ à¤•à¥ˆà¤¶ 1 à¤¸à¥‡à¤•à¤‚à¤¡!\nðŸ’Ž à¤µà¥‰à¤²à¥à¤Ÿ à¤«à¥‰à¤°à¥‡à¤µà¤°!\nðŸ“¤ à¤«à¤¾à¤‡à¤²à¥‡à¤‚ à¤…à¤ªà¤²à¥‹à¤¡ à¤•à¤°à¥‡à¤‚!\nðŸ”— à¤«à¤¾à¤‡à¤²-à¤Ÿà¥‚-à¤²à¤¿à¤‚à¤•: à¤¶à¥‡à¤¯à¤° à¤²à¤¿à¤‚à¤• à¤¬à¤¨à¤¾à¤à¤‚!\n\nðŸ‘‰ à¤¶à¥à¤°à¥‚ à¤•à¤°à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ à¤²à¤¿à¤‚à¤• à¤ªà¥‡à¤¸à¥à¤Ÿ à¤•à¤°à¥‡à¤‚! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ à¤µà¥€à¤¡à¤¿à¤¯à¥‹ (MP4)", "btn_audio": "ðŸŽµ à¤‘à¤¡à¤¿à¤¯à¥‹ (MP3)", "btn_image": "ðŸ–¼ï¸ à¤‡à¤®à¥‡à¤œà¥‡à¤¸", "btn_sub": "ðŸ“ à¤¸à¤¬à¤Ÿà¤¾à¤‡à¤Ÿà¤²à¥à¤¸ (SRT)",
        "ask_format": "ðŸ‘‡ **à¤¶à¤¾à¤¨à¤¦à¤¾à¤°! à¤•à¥Œà¤¨ à¤¸à¤¾ à¤«à¥‰à¤°à¥à¤®à¥‡à¤Ÿ à¤šà¤¾à¤¹à¤¤à¥‡ à¤¹à¥ˆà¤‚? à¤¨à¥€à¤šà¥‡ à¤šà¥à¤¨à¥‡à¤‚!**",
        "fetching": "ðŸ“¥ **à¤†à¤ªà¤•à¤¾ {} à¤²à¤¾à¤¯à¤¾ à¤œà¤¾ à¤°à¤¹à¤¾ à¤¹à¥ˆ... à¤°à¥à¤•à¥‡ à¤°à¤¹à¥‡à¤‚! â³âœ¨**",
        "error_generic": "âŒ à¤“à¤¹! à¤µà¤¿à¤«à¤²! ðŸ˜¢ à¤²à¤¿à¤‚à¤• à¤ªà¥à¤°à¤¾à¤‡à¤µà¥‡à¤Ÿ/à¤¬à¥à¤²à¥‰à¤• à¤¹à¥ˆà¥¤ à¤ªà¤¬à¥à¤²à¤¿à¤• à¤²à¤¿à¤‚à¤• à¤†à¤œà¤¼à¤®à¤¾à¤à¤‚!",
        "error_50mb": "âŒ à¤¬à¤¹à¥à¤¤ à¤¬à¤¡à¤¼à¤¾! ðŸ˜… à¤¯à¤¹ à¤µà¥€à¤¡à¤¿à¤¯à¥‹ 300MB à¤¸à¥‡ à¤…à¤§à¤¿à¤• à¤¹à¥ˆà¥¤ à¤›à¥‹à¤Ÿà¤¾ à¤µà¤¾à¤²à¤¾ à¤†à¤œà¤¼à¤®à¤¾à¤à¤‚!", 
        "error_no_img": "âŒ à¤•à¥‹à¤ˆ à¤‡à¤®à¥‡à¤œ à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¥€! ðŸ˜¢ à¤¦à¥‚à¤¸à¤°à¤¾ à¤²à¤¿à¤‚à¤• à¤†à¤œà¤¼à¤®à¤¾à¤à¤‚!",
        "images_received": "â³ **{} à¤‡à¤®à¥‡à¤œà¥‡à¤¸ à¤ªà¥à¤°à¤¾à¤ªà¥à¤¤ à¤¹à¥à¤ˆà¤‚à¥¤**",
        "select_lang": "ðŸŒ à¤…à¤ªà¤¨à¥€ à¤­à¤¾à¤·à¤¾ à¤šà¥à¤¨à¥‡à¤‚! à¤¨à¥€à¤šà¥‡ à¤šà¥à¤¨à¥‡à¤‚! ðŸ‘‡", 
        "lang_set": "âœ… à¤­à¤¾à¤·à¤¾ à¤¸à¥‡à¤Ÿ à¤¹à¥‹ à¤—à¤ˆ! à¤†à¤¨à¤‚à¤¦ à¤²à¥‡à¤‚! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **à¤¬à¥ˆà¤š à¤¡à¤¿à¤Ÿà¥‡à¤•à¥à¤Ÿ à¤¹à¥à¤† ({} à¤²à¤¿à¤‚à¤•à¥à¤¸)**\nà¤•à¥Œà¤¨ à¤¸à¤¾ à¤«à¥‰à¤°à¥à¤®à¥‡à¤Ÿ?",
        "batch_dest": "ðŸ“¦ **à¤•à¤¹à¤¾à¤ à¤­à¥‡à¤œà¥‡à¤‚?**",
        "btn_chat": "ðŸ“¥ à¤šà¥ˆà¤Ÿ à¤®à¥‡à¤‚", "btn_chan": "ðŸ“¢ à¤šà¥ˆà¤¨à¤² à¤®à¥‡à¤‚",
        "limit_reached": "âš ï¸ **à¤²à¤¿à¤®à¤¿à¤Ÿ à¤ªà¥‚à¤°à¥€ à¤¹à¥‹ à¤—à¤ˆ!** à¤†à¤ªà¤¨à¥‡ 4 à¤«à¥à¤°à¥€ à¤‡à¤¸à¥à¤¤à¥‡à¤®à¤¾à¤² à¤•à¤° à¤²à¤¿à¤! 20 à¤¸à¥‡à¤•à¤‚à¤¡ à¤•à¤¾ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¦à¥‡à¤–à¥‡à¤‚ â†’ +1 à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤ªà¤¾à¤à¤‚!",
        "refill_btn": "ðŸ”“ à¤²à¤¿à¤‚à¤• à¤–à¥‹à¤²à¥‡à¤‚ à¤”à¤° +1 à¤°à¤¿à¤«à¤¿à¤² à¤•à¤°à¥‡à¤‚",
        "join_btn": "ðŸ“¢ à¤šà¥ˆà¤¨à¤² à¤œà¥‰à¤‡à¤¨ à¤•à¤°à¥‡à¤‚", "check_btn": "ðŸ’œ à¤¬à¥ˆà¤²à¥‡à¤‚à¤¸ à¤šà¥‡à¤• à¤•à¤°à¥‡à¤‚",
        "limit_batch": "âš ï¸ **à¤¬à¥ˆà¤š à¤²à¤¿à¤®à¤¿à¤Ÿ {} à¤®à¥‡à¤‚ à¤¸à¥‡ {} à¤ªà¤° à¤ªà¤¹à¥à¤à¤š à¤—à¤ˆ**\nà¤œà¤¾à¤°à¥€ à¤°à¤–à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ 20 à¤¸à¥‡à¤•à¤‚à¤¡ à¤•à¤¾ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¦à¥‡à¤–à¥‡à¤‚ â†’ +1 à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡à¥¤",
        "batch_start": "ðŸ“¦ **à¤¬à¥ˆà¤š à¤¶à¥à¤°à¥‚:** {} **{} à¤«à¤¾à¤‡à¤²à¥‡à¤‚**\nâ³ à¤ªà¥à¤°à¥‹à¤¸à¥‡à¤¸à¤¿à¤‚à¤—...",
        "batch_done": "ðŸ **à¤¹à¥‹ à¤—à¤¯à¤¾!** âœ… {} âŒ {}\nðŸ“¥ {} à¤«à¤¾à¤‡à¤²à¥‡à¤‚ à¤¯à¤¹à¤¾à¤ à¤¹à¥ˆà¤‚à¥¤",
        "batch_done_chan": "ðŸ **à¤¹à¥‹ à¤—à¤¯à¤¾!** âœ… {} âŒ {}\nðŸ“¢ {} à¤«à¤¾à¤‡à¤²à¥‡à¤‚ à¤«à¥‰à¤°à¤µà¤°à¥à¤¡ à¤•à¥€ à¤—à¤ˆà¤‚!",
        "dl_video": "ðŸ“¥ à¤µà¥€à¤¡à¤¿à¤¯à¥‹ à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤¹à¥‹ à¤°à¤¹à¤¾ à¤¹à¥ˆ...", "dl_audio": "ðŸ“¥ à¤‘à¤¡à¤¿à¤¯à¥‹ à¤¨à¤¿à¤•à¤¾à¤²à¤¾ à¤œà¤¾ à¤°à¤¹à¤¾ à¤¹à¥ˆ...", "dl_image": "ðŸ“¥ à¤‡à¤®à¥‡à¤œà¥‡à¤¸ à¤¸à¥à¤•à¥à¤°à¥‡à¤ª à¤¹à¥‹ à¤°à¤¹à¥€ à¤¹à¥ˆà¤‚...", "dl_sub": "ðŸ“¥ à¤¸à¤¬à¤Ÿà¤¾à¤‡à¤Ÿà¤²à¥à¤¸ à¤²à¤¾à¤ à¤œà¤¾ à¤°à¤¹à¥‡ à¤¹à¥ˆà¤‚...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ à¤¬à¥à¤²à¥‰à¤•/à¤ªà¥à¤°à¤¾à¤‡à¤µà¥‡à¤Ÿ", "failed_generic": "âŒ à¤µà¤¿à¤«à¤²",
        "menu_lang": "ðŸŒ à¤­à¤¾à¤·à¤¾", "menu_stats": "ðŸ“Š à¤®à¥‡à¤°à¥‡ à¤†à¤‚à¤•à¤¡à¤¼à¥‡", "menu_help": "ðŸ’¬ à¤¸à¤ªà¥‹à¤°à¥à¤Ÿ / FAQ", "menu_join": "ðŸ“¢ à¤šà¥ˆà¤¨à¤² à¤œà¥‰à¤‡à¤¨ à¤•à¤°à¥‡à¤‚",
        "menu_uploads": "ðŸ¿ à¤«à¥ˆà¤¨ à¤…à¤ªà¤²à¥‹à¤¡à¥à¤¸", "menu_upload": "ðŸ“¤ à¤«à¤¾à¤‡à¤² à¤…à¤ªà¤²à¥‹à¤¡ à¤•à¤°à¥‡à¤‚",
        "admin_upload_prompt": "ðŸ“‚ **à¤«à¥ˆà¤¨ à¤…à¤ªà¤²à¥‹à¤¡à¥à¤¸ à¤‡à¤¨à¤¬à¥‰à¤•à¥à¤¸**",
        "user_upload_prompt": "ðŸ“¤ **à¤«à¤¾à¤‡à¤² à¤…à¤ªà¤²à¥‹à¤¡ à¤•à¤°à¥‡à¤‚**\nà¤à¤¡à¤®à¤¿à¤¨ à¤•à¥‹ à¤µà¥€à¤¡à¤¿à¤¯à¥‹/à¤‡à¤®à¥‡à¤œ/à¤«à¤¾à¤‡à¤² à¤­à¥‡à¤œà¥‡à¤‚à¥¤ à¤²à¤¿à¤®à¤¿à¤Ÿ 5/24à¤˜à¤‚à¤Ÿà¥‡à¥¤",
        "upload_success_user": "âœ… à¤à¤¡à¤®à¤¿à¤¨ à¤•à¥‹ à¤­à¥‡à¤œ à¤¦à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "upload_limit_reached": "âš ï¸ à¤…à¤ªà¤²à¥‹à¤¡ à¤²à¤¿à¤®à¤¿à¤Ÿ 5/24à¤˜à¤‚à¤Ÿà¥‡ à¤ªà¥‚à¤°à¥€ à¤¹à¥‹ à¤—à¤ˆà¥¤",
        "no_uploads": "ðŸ“­ à¤…à¤­à¥€ à¤¤à¤• à¤•à¥‹à¤ˆ à¤…à¤ªà¤²à¥‹à¤¡ à¤¨à¤¹à¥€à¤‚à¥¤",
        "stats_msg": "ðŸ“Š **à¤†à¤ªà¤•à¥‡ à¤†à¤‚à¤•à¤¡à¤¼à¥‡:**\nâ€¢ à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤¬à¤šà¥‡: {}\nâ€¢ à¤¬à¥ˆà¤š à¤¬à¤šà¥‡: {}",
        "change_channel_prompt": "ðŸ”„ **à¤¬à¥ˆà¤š à¤šà¥ˆà¤¨à¤² à¤¬à¤¦à¤²à¥‡à¤‚**\n1. à¤¸à¥à¤¨à¤¿à¤¶à¥à¤šà¤¿à¤¤ à¤•à¤°à¥‡à¤‚ à¤•à¤¿ à¤®à¥ˆà¤‚ à¤¨à¤ à¤šà¥ˆà¤¨à¤² à¤®à¥‡à¤‚ à¤à¤¡à¤®à¤¿à¤¨ à¤¹à¥‚à¤à¥¤\n2. à¤‰à¤¸ à¤šà¥ˆà¤¨à¤² à¤¸à¥‡ à¤•à¥‹à¤ˆ à¤­à¥€ à¤®à¥ˆà¤¸à¥‡à¤œ à¤¯à¤¹à¤¾à¤ à¤«à¥‰à¤°à¤µà¤°à¥à¤¡ à¤•à¤°à¥‡à¤‚à¥¤",
        "disk_config_prompt": "ðŸ’¾ **à¤¡à¤¿à¤¸à¥à¤• à¤•à¥‰à¤¨à¥à¤«à¤¼à¤¿à¤—à¤°à¥‡à¤¶à¤¨**\nà¤µà¤°à¥à¤¤à¤®à¤¾à¤¨ à¤¨à¥à¤¯à¥‚à¤¨à¤¤à¤® à¤«à¥à¤°à¥€ à¤¡à¤¿à¤¸à¥à¤•: **{}MB**\nà¤¬à¤¦à¤²à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤: `/setdisk <value>`",
        "mtproto_config_prompt": "âš¡ **MTProto à¤•à¥‰à¤¨à¥à¤«à¤¼à¤¿à¤—à¤°à¥‡à¤¶à¤¨**\nà¤µà¤°à¥à¤¤à¤®à¤¾à¤¨ à¤…à¤§à¤¿à¤•à¤¤à¤® à¤…à¤ªà¤²à¥‹à¤¡: **{}MB**\nà¤¬à¤¦à¤²à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤: `/setmtproto <value>`",
        "free_panel_prompt": "ðŸ“¦ à¤«à¥à¤°à¥€ à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡à¥à¤¸\nà¤µà¤°à¥à¤¤à¤®à¤¾à¤¨ à¤«à¥à¤°à¥€ à¤ªà¥à¤°à¤¤à¤¿ à¤¦à¤¿à¤¨: {}",
        "reward_panel_prompt": "ðŸŽ à¤°à¤¿à¤µà¥‰à¤°à¥à¤¡ à¤ªà¥ˆà¤¨à¤²\nà¤µà¤°à¥à¤¤à¤®à¤¾à¤¨: +{} à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤ªà¥à¤°à¤¤à¤¿ 20 à¤¸à¥‡à¤•à¤‚à¤¡ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨",
        "ad_panel_prompt": "âš™ï¸ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤ªà¥ˆà¤¨à¤²\nà¤µà¤°à¥à¤¤à¤®à¤¾à¤¨: {}",
        "password_saved": "ðŸ” à¤ªà¤¾à¤¸à¤µà¤°à¥à¤¡ à¤¸à¥‡à¤µ à¤¹à¥‹ à¤—à¤¯à¤¾à¥¤",
        "password_too_long": "à¤ªà¤¾à¤¸à¤µà¤°à¥à¤¡ 64 à¤…à¤•à¥à¤·à¤°à¥‹à¤‚ à¤¸à¥‡ à¤•à¤® à¤¹à¥‹à¤¨à¤¾ à¤šà¤¾à¤¹à¤¿à¤à¥¤",
        "file_to_link_prompt": "ðŸ”— **à¤«à¤¾à¤‡à¤²-à¤Ÿà¥‚-à¤²à¤¿à¤‚à¤•**\nà¤µà¤¹ à¤«à¤¾à¤‡à¤²(à¥‡à¤‚) à¤­à¥‡à¤œà¥‡à¤‚ à¤œà¤¿à¤¨à¥à¤¹à¥‡à¤‚ à¤†à¤ª à¤¶à¥‡à¤¯à¤° à¤•à¤°à¤¨à¤¾ à¤šà¤¾à¤¹à¤¤à¥‡ à¤¹à¥ˆà¤‚à¥¤",
        "link_invalid_expired": "âŒ à¤¯à¤¹ à¤²à¤¿à¤‚à¤• à¤…à¤®à¤¾à¤¨à¥à¤¯ à¤¹à¥ˆ à¤¯à¤¾ à¤¸à¤®à¤¾à¤ªà¥à¤¤ à¤¹à¥‹ à¤—à¤¯à¤¾ à¤¹à¥ˆà¥¤",
        "link_limit_reached": "â›” à¤‡à¤¸ à¤²à¤¿à¤‚à¤• à¤¨à¥‡ à¤…à¤ªà¤¨à¥€ à¤‰à¤ªà¤¯à¥‹à¤— à¤¸à¥€à¤®à¤¾ à¤ªà¤¾à¤° à¤•à¤° à¤²à¥€ à¤¹à¥ˆà¥¤",
        "link_password_protected": "ðŸ” à¤¯à¤¹ à¤²à¤¿à¤‚à¤• à¤ªà¤¾à¤¸à¤µà¤°à¥à¤¡ à¤¸à¥‡ à¤¸à¥à¤°à¤•à¥à¤·à¤¿à¤¤ à¤¹à¥ˆà¥¤ à¤ªà¤¾à¤¸à¤µà¤°à¥à¤¡ à¤­à¥‡à¤œà¥‡à¤‚à¥¤",
        "files_sent": "âœ… à¤†à¤ªà¤•à¥€ à¤«à¤¾à¤‡à¤²à¥‡à¤‚ à¤­à¥‡à¤œ à¤¦à¥€ à¤—à¤ˆ à¤¹à¥ˆà¤‚à¥¤",
        "file_added": "ðŸ“¥ à¤«à¤¾à¤‡à¤² #{} à¤œà¥‹à¤¡à¤¼à¥€ à¤—à¤ˆà¥¤ à¤”à¤° à¤­à¥‡à¤œà¥‡à¤‚, à¤¯à¤¾ 'Create Link' à¤Ÿà¥ˆà¤ª à¤•à¤°à¥‡à¤‚à¥¤",
        "fl_cancelled": "à¤«à¤¾à¤‡à¤²-à¤Ÿà¥‚-à¤²à¤¿à¤‚à¤• à¤°à¤¦à¥à¤¦ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾",
        "fl_start_again": "/filetolink à¤•à¥‡ à¤¸à¤¾à¤¥ à¤«à¤¿à¤° à¤¸à¥‡ à¤¶à¥à¤°à¥‚ à¤•à¤°à¥‡à¤‚",
        "fl_choose_expiry": "à¤²à¤¿à¤‚à¤• à¤¸à¤®à¤¾à¤ªà¥à¤¤à¤¿ à¤šà¥à¤¨à¥‡à¤‚:",
        "fl_expiry_updated": "à¤¸à¤®à¤¾à¤ªà¥à¤¤à¤¿ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤¹à¥‹ à¤—à¤ˆ",
        "fl_choose_max_uses": "à¤…à¤§à¤¿à¤•à¤¤à¤® à¤¸à¤«à¤² à¤¡à¤¿à¤²à¥€à¤µà¤°à¥€ à¤šà¥à¤¨à¥‡à¤‚:",
        "fl_uses_updated": "à¤‰à¤ªà¤¯à¥‹à¤— à¤¸à¥€à¤®à¤¾ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤¹à¥‹ à¤—à¤ˆ",
        "fl_set_password": "à¤ªà¤¾à¤¸à¤µà¤°à¥à¤¡ à¤­à¥‡à¤œà¥‡à¤‚, à¤¯à¤¾ à¤¹à¤Ÿà¤¾à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ /clearpassword à¤­à¥‡à¤œà¥‡à¤‚à¥¤",
        "fl_link_created": "à¤²à¤¿à¤‚à¤• à¤¬à¤¨à¤¾à¤¯à¤¾ à¤—à¤¯à¤¾",
        "fl_link_ready": "ðŸ”— à¤†à¤ªà¤•à¤¾ à¤²à¤¿à¤‚à¤• à¤¤à¥ˆà¤¯à¤¾à¤° à¤¹à¥ˆ:\n{}\nà¤«à¤¾à¤‡à¤²à¥‡à¤‚: {}\nà¤²à¤¾à¤—à¤¤: 1 à¤«à¥à¤°à¥€ à¤¦à¥ˆà¤¨à¤¿à¤• à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡",
        "fl_daily_limit": "à¤¦à¥ˆà¤¨à¤¿à¤• à¤«à¥à¤°à¥€ à¤²à¤¿à¤®à¤¿à¤Ÿ à¤ªà¥‚à¤°à¥€ à¤¹à¥‹ à¤—à¤ˆà¥¤ à¤…à¤§à¤¿à¤• à¤•à¤®à¤¾à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¦à¥‡à¤–à¥‡à¤‚à¥¤",
        "fl_ad_busy": "âš ï¸ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¸à¤°à¥à¤µà¤° à¤µà¥à¤¯à¤¸à¥à¤¤ à¤¹à¥ˆà¥¤",
        "admin_skipped": "âœ… à¤›à¥‹à¤¡à¤¼ à¤¦à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "admin_bypassed": "âœ… à¤¬à¤¾à¤¯à¤ªà¤¾à¤¸ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾",
        "free_set": "âœ… à¤«à¥à¤°à¥€ {} à¤ªà¤° à¤¸à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "free_updated": "âœ… à¤«à¥à¤°à¥€ à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡à¥à¤¸ {} à¤ªà¤° à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¤¿à¤ à¤—à¤!",
        "reward_set": "âœ… à¤°à¤¿à¤µà¥‰à¤°à¥à¤¡ +{} à¤ªà¤° à¤¸à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "reward_updated": "âœ… à¤°à¤¿à¤µà¥‰à¤°à¥à¤¡ +{} à¤ªà¤° à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "mode_updated": "âœ… à¤®à¥‹à¤¡: {}",
        "support_opened": "âœï¸ à¤¨à¥€à¤šà¥‡ à¤®à¥ˆà¤¸à¥‡à¤œ/à¤«à¥‹à¤Ÿà¥‹/à¤µà¥€à¤¡à¤¿à¤¯à¥‹/à¤«à¤¾à¤‡à¤² à¤­à¥‡à¤œà¥‡à¤‚à¥¤",
        "admin_reply_mode": "âœï¸ {} à¤•à¥‹ à¤°à¤¿à¤ªà¥à¤²à¤¾à¤ˆ à¤•à¤°à¥‡à¤‚:",
        "user_reply_mode": "âœï¸ à¤¨à¥€à¤šà¥‡ à¤«à¥‰à¤²à¥‹-à¤…à¤ª à¤Ÿà¤¾à¤‡à¤ª à¤•à¤°à¥‡à¤‚",
        "support_closed": "ðŸ”’ à¤¬à¤‚à¤¦ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾",
        "drop_cancelled": "âŒ à¤°à¤¦à¥à¤¦ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾",
        "drop_no_items": "âš ï¸ à¤•à¥‹à¤ˆ à¤†à¤‡à¤Ÿà¤® à¤¨à¤¹à¥€à¤‚!",
        "drop_timer_set": "{} à¤¸à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "drop_broadcasting": "ðŸš€ {} à¤†à¤‡à¤Ÿà¤® {} à¤•à¥‹ à¤¬à¥à¤°à¥‰à¤¡à¤•à¤¾à¤¸à¥à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤œà¤¾ à¤°à¤¹à¤¾ à¤¹à¥ˆ...",
        "drop_flash_text": "ðŸš¨ à¤«à¥à¤²à¥ˆà¤¶ à¤¡à¥à¤°à¥‰à¤ª!\n{} à¤®à¥‡à¤‚ à¤‘à¤Ÿà¥‹-à¤¡à¤¿à¤²à¥€à¤Ÿ à¤¹à¥‹à¤—à¤¾\nà¤•à¥à¤²à¥‡à¤® à¤•à¤°à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤ à¤Ÿà¥ˆà¤ª à¤•à¤°à¥‡à¤‚:",
        "drop_done": "âœ… {} à¤•à¥‹ à¤¬à¥à¤°à¥‰à¤¡à¤•à¤¾à¤¸à¥à¤Ÿ à¤¹à¥‹ à¤—à¤¯à¤¾",
        "age_expired": "â³ à¤¸à¤®à¤¾à¤ªà¥à¤¤ à¤¹à¥‹ à¤—à¤¯à¤¾!",
        "age_claimed": "âŒ à¤ªà¤¹à¤²à¥‡ à¤¹à¥€ à¤•à¥à¤²à¥‡à¤® à¤•à¤¿à¤¯à¤¾ à¤œà¤¾ à¤šà¥à¤•à¤¾ à¤¹à¥ˆ!",
        "age_verified": "à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤!",
        "age_denied": "âŒ à¤…à¤¸à¥à¤µà¥€à¤•à¥ƒà¤¤à¥¤ 18+ à¤¹à¥‹à¤¨à¤¾ à¤šà¤¾à¤¹à¤¿à¤",
        "lang_updated": "à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "batch_expired": "à¤¸à¤®à¤¾à¤ªà¥à¤¤ à¤¹à¥‹ à¤—à¤¯à¤¾",
        "batch_loading": "à¤²à¥‹à¤¡ à¤¹à¥‹ à¤°à¤¹à¤¾ à¤¹à¥ˆ...",
        "batch_no_channel": "à¤•à¥‹à¤ˆ à¤šà¥ˆà¤¨à¤² à¤²à¤¿à¤‚à¤• à¤¨à¤¹à¥€à¤‚ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "batch_setup_prompt": "ðŸ“¦ à¤¸à¥‡à¤Ÿà¤…à¤ª: à¤šà¥ˆà¤¨à¤² à¤®à¥‡à¤‚ à¤¬à¥‰à¤Ÿ à¤•à¥‹ à¤à¤¡à¤®à¤¿à¤¨ à¤¬à¤¨à¤¾à¤à¤‚ à¤”à¤° à¤¯à¤¹à¤¾à¤ à¤à¤• à¤®à¥ˆà¤¸à¥‡à¤œ à¤«à¥‰à¤°à¤µà¤°à¥à¤¡ à¤•à¤°à¥‡à¤‚",
        "batch_mode_activated": "à¤®à¥‹à¤¡ à¤¸à¤•à¥à¤°à¤¿à¤¯ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "batch_change_dest": "ðŸ”„ **à¤¡à¥‡à¤¸à¥à¤Ÿà¤¿à¤¨à¥‡à¤¶à¤¨ à¤šà¥ˆà¤¨à¤² à¤¬à¤¦à¤²à¥‡à¤‚**\nà¤¨à¤ à¤šà¥ˆà¤¨à¤² à¤®à¥‡à¤‚ à¤¬à¥‰à¤Ÿ à¤•à¥‹ à¤à¤¡à¤®à¤¿à¤¨ à¤¬à¤¨à¤¾à¤à¤‚, à¤«à¤¿à¤° à¤¯à¤¹à¤¾à¤ à¤®à¥ˆà¤¸à¥‡à¤œ à¤«à¥‰à¤°à¤µà¤°à¥à¤¡ à¤•à¤°à¥‡à¤‚à¥¤",
        "join_channel_first_alert": "à¤ªà¤¹à¤²à¥‡ à¤šà¥ˆà¤¨à¤² à¤œà¥‰à¤‡à¤¨ à¤•à¤°à¥‡à¤‚! ðŸ“¢ à¤œà¥‰à¤‡à¤¨ à¤•à¤°à¤¨à¤¾ à¤†à¤µà¤¶à¥à¤¯à¤• à¤¹à¥ˆ!",
        "join_channel_first": "à¤ªà¤¹à¤²à¥‡ à¤šà¥ˆà¤¨à¤² à¤œà¥‰à¤‡à¤¨ à¤•à¤°à¥‡à¤‚! ðŸ“¢",
        "watch_timer_first": "â° à¤ªà¤¹à¤²à¥‡ à¤²à¤¿à¤‚à¤• à¤–à¥‹à¤²à¥‡à¤‚ à¤”à¤° 20 à¤¸à¥‡à¤•à¤‚à¤¡ à¤•à¤¾ à¤Ÿà¤¾à¤‡à¤®à¤° à¤¦à¥‡à¤–à¥‡à¤‚!",
        "test_ad_verified": "âœ… à¤Ÿà¥‡à¤¸à¥à¤Ÿ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤! +1",
        "test_ad_verified_msg": "âœ… **à¤Ÿà¥‡à¤¸à¥à¤Ÿ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤!**\nà¤°à¤¿à¤µà¥‰à¤°à¥à¤¡: +1 à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤°à¤¿à¤«à¤¿à¤² à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾!",
        "finish_timer_first": "â° à¤ªà¤¹à¤²à¥‡ 20 à¤¸à¥‡à¤•à¤‚à¤¡ à¤•à¤¾ à¤Ÿà¤¾à¤‡à¤®à¤° à¤ªà¥‚à¤°à¤¾ à¤•à¤°à¥‡à¤‚!",
        "verified_added": "à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤! +1 à¤œà¥‹à¤¡à¤¼à¤¾ à¤—à¤¯à¤¾",
        "resume_prompt": "âœ… à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤! +1 à¤°à¤¿à¤«à¤¿à¤² à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾à¥¤ à¤«à¤¿à¤° à¤¸à¥‡ à¤¶à¥à¤°à¥‚ à¤•à¤°à¥‡à¤‚?",
        "refilled_download": "âœ… +1 à¤°à¤¿à¤«à¤¿à¤² à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾! à¤«à¤¿à¤° à¤¸à¥‡ à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤•à¤°à¥‡à¤‚à¥¤",
        "fetching_bundle": "âœ… à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤! à¤¬à¤‚à¤¡à¤² à¤²à¤¾à¤¯à¤¾ à¤œà¤¾ à¤°à¤¹à¤¾ à¤¹à¥ˆ...",
        "outdated_button": "à¤¯à¤¹ à¤¬à¤Ÿà¤¨ à¤ªà¥à¤°à¤¾à¤¨à¤¾ à¤¹à¥ˆà¥¤ à¤…à¤ªà¤¨à¤¾ à¤²à¤¿à¤‚à¤• à¤«à¤¿à¤° à¤¸à¥‡ à¤­à¥‡à¤œà¥‡à¤‚à¥¤",
        "stopping": "à¤°à¥‹à¤•à¤¾ à¤œà¤¾ à¤°à¤¹à¤¾ à¤¹à¥ˆ...",
        "stopped": "ðŸ›‘ à¤°à¥à¤• à¤—à¤¯à¤¾",
        "resuming": "à¤«à¤¿à¤° à¤¸à¥‡ à¤¶à¥à¤°à¥‚ à¤¹à¥‹ à¤°à¤¹à¤¾ à¤¹à¥ˆ...",
        "checking_vault": "à¤µà¥‰à¤²à¥à¤Ÿ à¤”à¤° à¤¸à¤°à¥à¤µà¤° à¤²à¥‹à¤¡ à¤šà¥‡à¤• à¤•à¤¿à¤¯à¤¾ à¤œà¤¾ à¤°à¤¹à¤¾ à¤¹à¥ˆ...",
        "server_busy": "â³ **à¤¸à¤°à¥à¤µà¤° à¤µà¥à¤¯à¤¸à¥à¤¤ à¤¹à¥ˆ**\nà¤¸à¤•à¥à¤°à¤¿à¤¯: {}/{}\nà¤«à¥à¤°à¥€: {}MB\nà¤•à¤¤à¤¾à¤°: #{}\nà¤‘à¤Ÿà¥‹ à¤¶à¥à¤°à¥‚ à¤¹à¥‹à¤—à¤¾!",
        "simulated": "ðŸ›  à¤¸à¤¿à¤®à¥à¤¯à¥à¤²à¥‡à¤Ÿ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾! à¤…à¤¬ à¤šà¥‡à¤• à¤•à¤°à¥‡à¤‚ à¤”à¤° +1 à¤ªà¥à¤°à¤¾à¤ªà¥à¤¤ à¤•à¤°à¥‡à¤‚",
        "server_unreachable": "âŒ à¤¸à¤°à¥à¤µà¤° à¤ªà¤¹à¥à¤à¤š à¤¸à¥‡ à¤¬à¤¾à¤¹à¤° à¤¹à¥ˆ",
        "monetag_failed_twice": "à¤ªà¤¹à¤²à¥‡ à¤¦à¥‹ à¤µà¤¿à¤«à¤² Monetag à¤ªà¥à¤°à¤¯à¤¾à¤¸ à¤ªà¥‚à¤°à¥‡ à¤•à¤°à¥‡à¤‚à¥¤",
        "monetag_fallback_prompt": "ðŸŒ Monetag à¤¦à¥‹ à¤¬à¤¾à¤° à¤µà¤¿à¤«à¤² à¤°à¤¹à¤¾à¥¤ Adsterra à¤•à¥‡ à¤¸à¤¾à¤¥ à¤œà¤¾à¤°à¥€ à¤°à¤–à¥‡à¤‚:",
        "adsterra_ready": "Adsterra à¤«à¥‰à¤²à¤¬à¥ˆà¤• à¤¤à¥ˆà¤¯à¤¾à¤° à¤¹à¥ˆ",
        "finish_monetag": "ðŸ“º Mini App à¤®à¥‡à¤‚ Monetag à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤ªà¥‚à¤°à¤¾ à¤•à¤°à¥‡à¤‚, à¤«à¤¿à¤° à¤šà¥‡à¤• à¤•à¤°à¥‡à¤‚à¥¤",
        "monetag_failed_use_adsterra": "Monetag à¤¦à¥‹ à¤¬à¤¾à¤° à¤µà¤¿à¤«à¤² à¤°à¤¹à¤¾à¥¤ à¤¨à¥€à¤šà¥‡ à¤¦à¤¿à¤ à¤—à¤ Adsterra à¤«à¥‰à¤²à¤¬à¥ˆà¤• à¤•à¤¾ à¤‰à¤ªà¤¯à¥‹à¤— à¤•à¤°à¥‡à¤‚à¥¤",
        "ad_link_expired": "à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤²à¤¿à¤‚à¤• à¤¸à¤®à¤¾à¤ªà¥à¤¤ à¤¹à¥‹ à¤—à¤¯à¤¾ à¤¹à¥ˆà¥¤ à¤…à¤ªà¤¨à¤¾ à¤²à¤¿à¤‚à¤• à¤«à¤¿à¤° à¤¸à¥‡ à¤­à¥‡à¤œà¥‡à¤‚à¥¤",
        "ad_verified_added": "âœ… à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤! +{} à¤œà¥‹à¤¡à¤¼à¤¾ à¤—à¤¯à¤¾",
        "test_ad_completed": "âœ… à¤Ÿà¥‡à¤¸à¥à¤Ÿ à¤µà¤¿à¤œà¥à¤žà¤¾à¤ªà¤¨ à¤¸à¤¤à¥à¤¯à¤¾à¤ªà¤¿à¤¤\nà¤°à¤¿à¤µà¥‰à¤°à¥à¤¡ à¤œà¤®à¤¾ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾: +{} à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡à¥¤",
        "sponsor_viewed": "âœ… à¤¸à¥à¤ªà¥‰à¤¨à¥à¤¸à¤° à¤¦à¥‡à¤–à¤¾ à¤—à¤¯à¤¾! +{} à¤œà¥‹à¤¡à¤¼à¤¾ à¤—à¤¯à¤¾",
        "refilled_send_again": "âœ… +{} à¤°à¤¿à¤«à¤¿à¤² à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾! à¤…à¤ªà¤¨à¤¾ à¤²à¤¿à¤‚à¤• à¤«à¤¿à¤° à¤¸à¥‡ à¤­à¥‡à¤œà¥‡à¤‚à¥¤",
        "queued": "â³ à¤•à¤¤à¤¾à¤° #{}",
        "banned": "ðŸš« à¤†à¤ª à¤¬à¥ˆà¤¨ à¤•à¤° à¤¦à¤¿à¤ à¤—à¤ à¤¹à¥ˆà¤‚à¥¤",
        "no_links": "âŒ à¤•à¥‹à¤ˆ à¤²à¤¿à¤‚à¤• à¤¨à¤¹à¥€à¤‚ à¤®à¤¿à¤²à¤¾à¥¤",
        "batch_count": "ðŸ“¦ à¤¬à¥ˆà¤š {} à¤²à¤¿à¤‚à¤•à¥à¤¸",
        "restore_invalid_json": "âŒ à¤°à¤¿à¤¸à¥à¤Ÿà¥‹à¤° à¤µà¤¿à¤«à¤²: **{}** à¤®à¤¾à¤¨à¥à¤¯ JSON à¤¨à¤¹à¥€à¤‚ à¤¹à¥ˆà¥¤",
        "restore_failed": "âŒ à¤°à¤¿à¤¸à¥à¤Ÿà¥‹à¤° à¤µà¤¿à¤«à¤²: {}",
        "restore_success": "âœ… **à¤°à¤¿à¤¸à¥à¤Ÿà¥‹à¤° à¤¸à¤«à¤²!**\nà¤«à¤¾à¤‡à¤²: **{}**\n**{}** à¤à¤‚à¤Ÿà¥à¤°à¥€à¤œ à¤°à¤¿à¤¸à¥à¤Ÿà¥‹à¤° à¤•à¥€ à¤—à¤ˆà¤‚à¥¤",
        "admin_edit_welcome_prompt": "âœï¸ à¤¨à¤¯à¤¾ à¤µà¥‡à¤²à¤•à¤® à¤®à¥ˆà¤¸à¥‡à¤œ à¤­à¥‡à¤œà¥‡à¤‚à¥¤ à¤¬à¥‰à¤Ÿ à¤¯à¥‚à¤œà¤°à¤¨à¥‡à¤® à¤•à¥‡ à¤²à¤¿à¤ `{bot_name}` à¤•à¤¾ à¤‰à¤ªà¤¯à¥‹à¤— à¤•à¤°à¥‡à¤‚à¥¤",
        "admin_welcome_updated": "âœ… à¤µà¥‡à¤²à¤•à¤® à¤®à¥ˆà¤¸à¥‡à¤œ à¤…à¤ªà¤¡à¥‡à¤Ÿ à¤¹à¥‹ à¤—à¤¯à¤¾!",
        "menu_edit_welcome": "âœï¸ à¤µà¥‡à¤²à¤•à¤® à¤®à¥ˆà¤¸à¥‡à¤œ à¤à¤¡à¤¿à¤Ÿ à¤•à¤°à¥‡à¤‚",
        "cached_instant_video": "âš¡ à¤•à¥ˆà¤¶ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾ à¤¤à¤¾à¤¤à¥à¤•à¤¾à¤²à¤¿à¤• [{}] {} {}",
        "cached_instant_audio": "âš¡ **à¤•à¥ˆà¤¶ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾ à¤¤à¤¾à¤¤à¥à¤•à¤¾à¤²à¤¿à¤•** `{}`",
        "cached_instant_image": "âš¡ **à¤•à¥ˆà¤¶ à¤•à¤¿à¤¯à¤¾ à¤—à¤¯à¤¾ à¤¤à¤¾à¤¤à¥à¤•à¤¾à¤²à¤¿à¤•** `{}`",
        "auto_delete_9m": "â³ 9 à¤®à¤¿à¤¨à¤Ÿ à¤®à¥‡à¤‚ à¤‘à¤Ÿà¥‹-à¤¡à¤¿à¤²à¥€à¤Ÿ",
        "download_success": "âœ… à¤¡à¤¾à¤‰à¤¨à¤²à¥‹à¤¡ à¤¸à¤«à¤²!"
    },
    "es": {
        "welcome": "ðŸš€ **BIENVENIDO A MICHAELBBC VAULT - DESCARGADOR DE MEDIOS!**\n\nðŸ”¥ QUÃ‰ PUEDO HACER:\nðŸŽ¬ VIDEOS HD Sin Marca de Agua!\nðŸŽµ AUDIO MP3 192kbps!\nðŸ–¼ï¸ IMÃGENES Scraping TOTAL!\nðŸ“ SUBTÃTULOS Auto!\nðŸ“¦ LOTES 100+ Enlaces!\nâš¡ CACHE 1 Seg!\nðŸ’Ž VAULT Para Siempre!\nðŸ“¤ SUBIR ARCHIVOS!\nðŸ”— ARCHIVO-A-ENLACE: Crea enlaces compartibles!\n\nðŸ‘‰ PEGA UN ENLACE PARA EMPEZAR! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ Video (MP4)", "btn_audio": "ðŸŽµ Audio (MP3)", "btn_image": "ðŸ–¼ï¸ ImÃ¡genes", "btn_sub": "ðŸ“ SubtÃ­tulos (SRT)",
        "ask_format": "ðŸ‘‡ **GENIAL! Â¿QuÃ© formato quieres? Elige abajo!**",
        "fetching": "ðŸ“¥ **Obteniendo tu {}... Espera un momento! â³âœ¨**",
        "error_generic": "âŒ Ups! FallÃ³! ðŸ˜¢ Enlace privado/bloqueado. Prueba un enlace pÃºblico!",
        "error_50mb": "âŒ Demasiado grande! ðŸ˜… Este video supera los 300MB. Prueba uno mÃ¡s corto!", 
        "error_no_img": "âŒ No se encontraron imÃ¡genes! ðŸ˜¢ Prueba otro enlace!",
        "images_received": "â³ **{} ImÃ¡genes recibidas.**",
        "select_lang": "ðŸŒ Selecciona tu idioma! Elige abajo! ðŸ‘‡", 
        "lang_set": "âœ… Idioma configurado! Disfruta! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Lote Detectado ({} enlaces)**\nÂ¿QuÃ© formato?",
        "batch_dest": "ðŸ“¦ **DÃ³nde enviar?**",
        "btn_chat": "ðŸ“¥ En Chat", "btn_chan": "ðŸ“¢ Al Canal",
        "limit_reached": "âš ï¸ **LÃ­mite Alcanzado!** Usaste 4 GRATIS! Mira un anuncio de 20s â†’ ObtÃ©n +1 descarga!",
        "refill_btn": "ðŸ”“ Abrir Enlace y Recargar +1",
        "join_btn": "ðŸ“¢ Unirse al Canal", "check_btn": "ðŸ’œ Verificar Saldo",
        "limit_batch": "âš ï¸ **LÃ­mite de Lote Alcanzado en {} de {}**\nMira un anuncio de 20s â†’ +1 descarga para continuar.",
        "batch_start": "ðŸ“¦ **Lote Iniciado:** {} **{} archivos**\nâ³ Procesando...",
        "batch_done": "ðŸ **Listo!** âœ… {} âŒ {}\nðŸ“¥ {} archivos aquÃ­.",
        "batch_done_chan": "ðŸ **Listo!** âœ… {} âŒ {}\nðŸ“¢ {} archivos reenviados!",
        "dl_video": "ðŸ“¥ Descargando video...", "dl_audio": "ðŸ“¥ Extrayendo audio...", "dl_image": "ðŸ“¥ Obteniendo imÃ¡genes...", "dl_sub": "ðŸ“¥ Obteniendo subtÃ­tulos...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Bloqueado/privado", "failed_generic": "âŒ FallÃ³",
        "menu_lang": "ðŸŒ Idioma", "menu_stats": "ðŸ“Š Mis EstadÃ­sticas", "menu_help": "ðŸ’¬ Soporte / FAQ", "menu_join": "ðŸ“¢ Unirse al Canal",
        "menu_uploads": "ðŸ¿ Subidas de Fans", "menu_upload": "ðŸ“¤ Subir Archivo",
        "admin_upload_prompt": "ðŸ“‚ **Bandeja de Subidas de Fans**",
        "user_upload_prompt": "ðŸ“¤ **Subir Archivo**\nEnvÃ­a video/imagen/archivo al Admin. LÃ­mite 5/24h.",
        "upload_success_user": "âœ… Enviado al Admin!",
        "upload_limit_reached": "âš ï¸ LÃ­mite de subidas 5/24h alcanzado.",
        "no_uploads": "ðŸ“­ AÃºn no hay subidas.",
        "stats_msg": "ðŸ“Š **Tus EstadÃ­sticas:**\nâ€¢ Descargas Restantes: {}\nâ€¢ Lotes Restantes: {}",
        "change_channel_prompt": "ðŸ”„ **Cambiar Canal de Lotes**\n1. AsegÃºrate de que soy admin en el nuevo canal.\n2. ReenvÃ­a cualquier mensaje de ese canal aquÃ­.",
        "disk_config_prompt": "ðŸ’¾ **Config de Disco**\nMin disco libre actual: **{}MB**\nPara cambiar: `/setdisk <valor>`",
        "mtproto_config_prompt": "âš¡ **Config MTProto**\nMax subida actual: **{}MB**\nPara cambiar: `/setmtproto <valor>`",
        "free_panel_prompt": "ðŸ“¦ DESCARGAS GRATIS\nGratis actuales por dÃ­a: {}",
        "reward_panel_prompt": "ðŸŽ PANEL DE RECOMPENSAS\nActual: +{} descarga por anuncio de 20s",
        "ad_panel_prompt": "âš™ï¸ Panel de Anuncios\nActual: {}",
        "password_saved": "ðŸ” ContraseÃ±a guardada.",
        "password_too_long": "La contraseÃ±a debe tener 64 caracteres o menos.",
        "file_to_link_prompt": "ðŸ”— **Archivo-a-Enlace**\nEnvÃ­a el/los archivo(s) que quieres compartir.",
        "link_invalid_expired": "âŒ Este enlace es invÃ¡lido o expirÃ³.",
        "link_limit_reached": "â›” Este enlace alcanzÃ³ su lÃ­mite de uso.",
        "link_password_protected": "ðŸ” Este enlace estÃ¡ protegido con contraseÃ±a. EnvÃ­a la contraseÃ±a.",
        "files_sent": "âœ… Tus archivos han sido enviados.",
        "file_added": "ðŸ“¥ Archivo #{} aÃ±adido. EnvÃ­a mÃ¡s o toca Crear Enlace.",
        "fl_cancelled": "Archivo-a-Enlace cancelado",
        "fl_start_again": "Inicia Archivo-a-Enlace de nuevo con /filetolink",
        "fl_choose_expiry": "Elige la expiraciÃ³n del enlace:",
        "fl_expiry_updated": "ExpiraciÃ³n actualizada",
        "fl_choose_max_uses": "Elige el mÃ¡ximo de entregas exitosas:",
        "fl_uses_updated": "LÃ­mite de uso actualizado",
        "fl_set_password": "EnvÃ­a una contraseÃ±a, o /clearpassword para eliminar.",
        "fl_link_created": "Enlace creado",
        "fl_link_ready": "ðŸ”— Tu enlace estÃ¡ listo:\n{}\nArchivos: {}\nCosto: 1 descarga diaria gratis",
        "fl_daily_limit": "LÃ­mite diario gratis alcanzado. Mira un anuncio para ganar mÃ¡s.",
        "fl_ad_busy": "âš ï¸ Servidor de anuncios ocupado.",
        "admin_skipped": "âœ… Omitido!",
        "admin_bypassed": "âœ… Omitido",
        "free_set": "âœ… Gratis configurado a {}!",
        "free_updated": "âœ… Descargas Gratis actualizadas a {}!",
        "reward_set": "âœ… Recompensa configurada a +{}!",
        "reward_updated": "âœ… Recompensa actualizada a +{}!",
        "mode_updated": "âœ… Modo: {}",
        "support_opened": "âœï¸ EnvÃ­a mensaje/foto/video/archivo abajo.",
        "admin_reply_mode": "âœï¸ Responder a {}:",
        "user_reply_mode": "âœï¸ Escribe el seguimiento abajo",
        "support_closed": "ðŸ”’ Cerrado",
        "drop_cancelled": "âŒ Cancelado",
        "drop_no_items": "âš ï¸ Sin elementos!",
        "drop_timer_set": "{} configurado!",
        "drop_broadcasting": "ðŸš€ Transmitiendo {} elementos a {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nAuto-elimina en {}\nToca para reclamar:",
        "drop_done": "âœ… TransmisiÃ³n hecha a {}",
        "age_expired": "â³ Expirado!",
        "age_claimed": "âŒ Ya reclamado!",
        "age_verified": "Verificado!",
        "age_denied": "âŒ Denegado. Debe ser 18+",
        "lang_updated": "Actualizado!",
        "batch_expired": "Expirado",
        "batch_loading": "Cargando...",
        "batch_no_channel": "NingÃºn canal vinculado!",
        "batch_setup_prompt": "ðŸ“¦ ConfiguraciÃ³n: Haz bot admin en el canal y reenvÃ­a un mensaje aquÃ­",
        "batch_mode_activated": "Modo activado!",
        "batch_change_dest": "ðŸ”„ **Cambiar Canal de Destino**\nHaz bot admin en el nuevo canal, luego reenvÃ­a un mensaje aquÃ­.",
        "join_channel_first_alert": "Ãšnete al canal primero! ðŸ“¢ Debes unirte!",
        "join_channel_first": "Ãšnete al canal primero! ðŸ“¢",
        "watch_timer_first": "â° Abre el enlace y mira el temporizador de 20s primero!",
        "test_ad_verified": "âœ… Anuncio de Prueba Verificado! +1",
        "test_ad_verified_msg": "âœ… **ANUNCIO DE PRUEBA VERIFICADO!**\nRecompensa: +1 descarga recargada!",
        "finish_timer_first": "â° Termina el temporizador de 20s primero!",
        "verified_added": "Verificado! +1 aÃ±adido",
        "resume_prompt": "âœ… Verificado! Recargado +1. Â¿Reanudar?",
        "refilled_download": "âœ… Recargado +1! Descarga de nuevo.",
        "fetching_bundle": "âœ… Verificado! Obteniendo paquete...",
        "outdated_button": "Este botÃ³n estÃ¡ desactualizado. EnvÃ­a tu enlace de nuevo.",
        "stopping": "Deteniendo...",
        "stopped": "ðŸ›‘ Detenido",
        "resuming": "Reanudando...",
        "checking_vault": "Verificando vault y carga del servidor...",
        "server_busy": "â³ **Servidor Ocupado**\nActivos: {}/{}\nLibre: {}MB\nCola: #{}\nIniciarÃ¡ auto!",
        "simulated": "ðŸ›  Simulado! Ahora toca Verificar y Obtener +1",
        "server_unreachable": "âŒ Servidor inalcanzable",
        "monetag_failed_twice": "Completa dos intentos fallidos de Monetag primero.",
        "monetag_fallback_prompt": "ðŸŒ Monetag fallÃ³ dos veces. ContinÃºa con Adsterra:",
        "adsterra_ready": "Fallback de Adsterra listo",
        "finish_monetag": "ðŸ“º Termina el anuncio de Monetag en Mini App, luego verifica.",
        "monetag_failed_use_adsterra": "Monetag fallÃ³ dos veces. Usa el fallback de Adsterra abajo.",
        "ad_link_expired": "Enlace de anuncio expirado. EnvÃ­a tu enlace de nuevo.",
        "ad_verified_added": "âœ… Anuncio verificado! +{} aÃ±adido",
        "test_ad_completed": "âœ… ANUNCIO DE PRUEBA VERIFICADO\nRecompensa acreditada: +{} descarga.",
        "sponsor_viewed": "âœ… Patrocinador visto! +{} aÃ±adido",
        "refilled_send_again": "âœ… Recargado +{}! EnvÃ­a tu enlace de nuevo.",
        "queued": "â³ En cola #{}",
        "banned": "ðŸš« EstÃ¡s prohibido.",
        "no_links": "âŒ No se encontraron enlaces.",
        "batch_count": "ðŸ“¦ Lote {} enlaces",
        "restore_invalid_json": "âŒ RestauraciÃ³n fallida: **{}** no es JSON vÃ¡lido.",
        "restore_failed": "âŒ RestauraciÃ³n fallida: {}",
        "restore_success": "âœ… **RestauraciÃ³n Exitosa!**\nArchivo: **{}**\nRestauradas **{}** entradas.",
        "admin_edit_welcome_prompt": "âœï¸ EnvÃ­a el nuevo Mensaje de Bienvenida. Usa `{bot_name}` para el nombre de usuario.",
        "admin_welcome_updated": "âœ… Mensaje de bienvenida actualizado!",
        "menu_edit_welcome": "âœï¸ Editar Mensaje de Bienvenida",
        "cached_instant_video": "âš¡ CachÃ© InstantÃ¡nea [{}] {} {}",
        "cached_instant_audio": "âš¡ **CachÃ© InstantÃ¡nea** `{}`",
        "cached_instant_image": "âš¡ **CachÃ© InstantÃ¡nea** `{}`",
        "auto_delete_9m": "â³ Auto-elimina en 9 mins",
        "download_success": "âœ… Â¡Descarga exitosa!"
    },
    "ar": {
        "welcome": "ðŸš€ **Ù…Ø±Ø­Ø¨Ø§Ù‹ Ø¨Ùƒ ÙÙŠ MICHAELBBC VAULT - Ù…Ø­Ù…Ù„ Ø§Ù„ÙˆØ³Ø§Ø¦Ø· Ø§Ù„Ø´Ø§Ù…Ù„!**\n\nðŸ”¥ Ù…Ø§Ø°Ø§ ÙŠÙ…ÙƒÙ†Ù†ÙŠ Ø£Ù† Ø£ÙØ¹Ù„:\nðŸŽ¬ ÙÙŠØ¯ÙŠÙˆÙ‡Ø§Øª HD Ø¨Ø¯ÙˆÙ† Ø¹Ù„Ø§Ù…Ø© Ù…Ø§Ø¦ÙŠØ©!\nðŸŽµ ØµÙˆØª MP3 192kbps!\nðŸ–¼ï¸ Ø³Ø­Ø¨ Ø¬Ù…ÙŠØ¹ Ø§Ù„ØµÙˆØ±!\nðŸ“ ØªØ±Ø¬Ù…Ø§Øª ØªÙ„Ù‚Ø§Ø¦ÙŠØ©!\nðŸ“¦ Ø¯ÙØ¹Ø§Øª 100+ Ø±Ø§Ø¨Ø·!\nâš¡ Ø°Ø§ÙƒØ±Ø© ØªØ®Ø²ÙŠÙ† Ù…Ø¤Ù‚Øª 1 Ø«Ø§Ù†ÙŠØ©!\nðŸ’Ž Ø®Ø²Ù†Ø© Ù„Ù„Ø£Ø¨Ø¯!\nðŸ“¤ Ø±ÙØ¹ Ø§Ù„Ù…Ù„ÙØ§Øª!\nðŸ”— Ù…Ù„Ù-Ø¥Ù„Ù‰-Ø±Ø§Ø¨Ø·: Ø¥Ù†Ø´Ø§Ø¡ Ø±ÙˆØ§Ø¨Ø· Ù‚Ø§Ø¨Ù„Ø© Ù„Ù„Ù…Ø´Ø§Ø±ÙƒØ©!\n\nðŸ‘‰ Ø§Ù„ØµÙ‚ Ø±Ø§Ø¨Ø·Ø§Ù‹ Ù„Ù„Ø¨Ø¯Ø¡! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ ÙÙŠØ¯ÙŠÙˆ (MP4)", "btn_audio": "ðŸŽµ ØµÙˆØª (MP3)", "btn_image": "ðŸ–¼ï¸ ØµÙˆØ±", "btn_sub": "ðŸ“ ØªØ±Ø¬Ù…Ø§Øª (SRT)",
        "ask_format": "ðŸ‘‡ **Ø±Ø§Ø¦Ø¹! Ù…Ø§ Ø§Ù„ØªÙ†Ø³ÙŠÙ‚ Ø§Ù„Ø°ÙŠ ØªØ±ÙŠØ¯Ù‡ØŸ Ø§Ø®ØªØ± Ø£Ø¯Ù†Ø§Ù‡!**",
        "fetching": "ðŸ“¥ **Ø¬Ø§Ø±ÙŠ Ø¬Ù„Ø¨ {}... Ø§Ù†ØªØ¸Ø± Ù‚Ù„ÙŠÙ„Ø§Ù‹! â³âœ¨**",
        "error_generic": "âŒ Ø¹Ø°Ø±Ø§Ù‹! ÙØ´Ù„! ðŸ˜¢ Ø§Ù„Ø±Ø§Ø¨Ø· Ø®Ø§Øµ/Ù…Ø­Ø¸ÙˆØ±. Ø¬Ø±Ø¨ Ø±Ø§Ø¨Ø·Ø§Ù‹ Ø¹Ø§Ù…Ø§Ù‹!",
        "error_50mb": "âŒ ÙƒØ¨ÙŠØ± Ø¬Ø¯Ø§Ù‹! ðŸ˜… Ù‡Ø°Ø§ Ø§Ù„ÙÙŠØ¯ÙŠÙˆ ÙŠØªØ¬Ø§ÙˆØ² 300 Ù…ÙŠØ¬Ø§Ø¨Ø§ÙŠØª. Ø¬Ø±Ø¨ ÙÙŠØ¯ÙŠÙˆ Ø£Ù‚ØµØ±!", 
        "error_no_img": "âŒ Ù„Ù… ÙŠØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ ØµÙˆØ±! ðŸ˜¢ Ø¬Ø±Ø¨ Ø±Ø§Ø¨Ø·Ø§Ù‹ Ø¢Ø®Ø±!",
        "images_received": "â³ **ØªÙ… Ø§Ø³ØªÙ„Ø§Ù… {} ØµÙˆØ±Ø©.**",
        "select_lang": "ðŸŒ Ø§Ø®ØªØ± Ù„ØºØªÙƒ! Ø§Ø®ØªØ± Ø£Ø¯Ù†Ø§Ù‡! ðŸ‘‡", 
        "lang_set": "âœ… ØªÙ… ØªØ¹ÙŠÙŠÙ† Ø§Ù„Ù„ØºØ©! Ø§Ø³ØªÙ…ØªØ¹! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **ØªÙ… Ø§ÙƒØªØ´Ø§Ù Ø¯ÙØ¹Ø© ({} Ø±ÙˆØ§Ø¨Ø·)**\nÙ…Ø§ Ø§Ù„ØªÙ†Ø³ÙŠÙ‚ØŸ",
        "batch_dest": "ðŸ“¦ **Ø£ÙŠÙ† Ù†Ø±Ø³Ù„ØŸ**",
        "btn_chat": "ðŸ“¥ ÙÙŠ Ø§Ù„Ø¯Ø±Ø¯Ø´Ø©", "btn_chan": "ðŸ“¢ Ø¥Ù„Ù‰ Ø§Ù„Ù‚Ù†Ø§Ø©",
        "limit_reached": "âš ï¸ **ØªÙ… Ø§Ù„ÙˆØµÙˆÙ„ Ù„Ù„Ø­Ø¯ Ø§Ù„Ø£Ù‚ØµÙ‰!** Ø§Ø³ØªØ®Ø¯Ù…Øª 4 Ù…Ø¬Ø§Ù†Ø§Ù‹! Ø´Ø§Ù‡Ø¯ Ø¥Ø¹Ù„Ø§Ù† 20 Ø«Ø§Ù†ÙŠØ© â†’ Ø§Ø­ØµÙ„ Ø¹Ù„Ù‰ +1 ØªØ­Ù…ÙŠÙ„!",
        "refill_btn": "ðŸ”“ Ø§ÙØªØ­ Ø§Ù„Ø±Ø§Ø¨Ø· ÙˆØ£Ø¹Ø¯ Ø§Ù„ØªØ¹Ø¨Ø¦Ø© +1",
        "join_btn": "ðŸ“¢ Ø§Ù†Ø¶Ù… Ù„Ù„Ù‚Ù†Ø§Ø©", "check_btn": "ðŸ’œ ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„Ø±ØµÙŠØ¯",
        "limit_batch": "âš ï¸ **ØªÙ… Ø§Ù„ÙˆØµÙˆÙ„ Ù„Ø­Ø¯ Ø§Ù„Ø¯ÙØ¹Ø© Ø¹Ù†Ø¯ {} Ù…Ù† {}**\nØ´Ø§Ù‡Ø¯ Ø¥Ø¹Ù„Ø§Ù† 20 Ø«Ø§Ù†ÙŠØ© â†’ +1 ØªØ­Ù…ÙŠÙ„ Ù„Ù„Ù…ØªØ§Ø¨Ø¹Ø©.",
        "batch_start": "ðŸ“¦ **Ø¨Ø¯Ø£Øª Ø§Ù„Ø¯ÙØ¹Ø©:** {} **{} Ù…Ù„ÙØ§Øª**\nâ³ Ø¬Ø§Ø±ÙŠ Ø§Ù„Ù…Ø¹Ø§Ù„Ø¬Ø©...",
        "batch_done": "ðŸ **ØªÙ…!** âœ… {} âŒ {}\nðŸ“¥ {} Ù…Ù„ÙØ§Øª Ù‡Ù†Ø§.",
        "batch_done_chan": "ðŸ **ØªÙ…!** âœ… {} âŒ {}\nðŸ“¢ ØªÙ… Ø¥Ø¹Ø§Ø¯Ø© ØªÙˆØ¬ÙŠÙ‡ {} Ù…Ù„ÙØ§Øª!",
        "dl_video": "ðŸ“¥ Ø¬Ø§Ø±ÙŠ ØªØ­Ù…ÙŠÙ„ Ø§Ù„ÙÙŠØ¯ÙŠÙˆ...", "dl_audio": "ðŸ“¥ Ø¬Ø§Ø±ÙŠ Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„ØµÙˆØª...", "dl_image": "ðŸ“¥ Ø¬Ø§Ø±ÙŠ Ø³Ø­Ø¨ Ø§Ù„ØµÙˆØ±...", "dl_sub": "ðŸ“¥ Ø¬Ø§Ø±ÙŠ Ø¬Ù„Ø¨ Ø§Ù„ØªØ±Ø¬Ù…Ø§Øª...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Ù…Ø­Ø¸ÙˆØ±/Ø®Ø§Øµ", "failed_generic": "âŒ ÙØ´Ù„",
        "menu_lang": "ðŸŒ Ø§Ù„Ù„ØºØ©", "menu_stats": "ðŸ“Š Ø¥Ø­ØµØ§Ø¦ÙŠØ§ØªÙŠ", "menu_help": "ðŸ’¬ Ø§Ù„Ø¯Ø¹Ù… / Ø§Ù„Ø£Ø³Ø¦Ù„Ø© Ø§Ù„Ø´Ø§Ø¦Ø¹Ø©", "menu_join": "ðŸ“¢ Ø§Ù†Ø¶Ù… Ù„Ù„Ù‚Ù†Ø§Ø©",
        "menu_uploads": "ðŸ¿ Ø±ÙØ¹ Ø§Ù„Ù…Ø¹Ø¬Ø¨ÙŠÙ†", "menu_upload": "ðŸ“¤ Ø±ÙØ¹ Ù…Ù„Ù",
        "admin_upload_prompt": "ðŸ“‚ **ØµÙ†Ø¯ÙˆÙ‚ ÙˆØ§Ø±Ø¯ Ø±ÙØ¹ Ø§Ù„Ù…Ø¹Ø¬Ø¨ÙŠÙ†**",
        "user_upload_prompt": "ðŸ“¤ **Ø±ÙØ¹ Ù…Ù„Ù**\nØ£Ø±Ø³Ù„ ÙÙŠØ¯ÙŠÙˆ/ØµÙˆØ±Ø©/Ù…Ù„Ù Ù„Ù„Ù…Ø³Ø¤ÙˆÙ„. Ø§Ù„Ø­Ø¯ 5/24 Ø³Ø§Ø¹Ø©.",
        "upload_success_user": "âœ… ØªÙ… Ø§Ù„Ø¥Ø±Ø³Ø§Ù„ Ù„Ù„Ù…Ø³Ø¤ÙˆÙ„!",
        "upload_limit_reached": "âš ï¸ ØªÙ… Ø§Ù„ÙˆØµÙˆÙ„ Ù„Ø­Ø¯ Ø§Ù„Ø±ÙØ¹ 5/24 Ø³Ø§Ø¹Ø©.",
        "no_uploads": "ðŸ“­ Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¹Ù…Ù„ÙŠØ§Øª Ø±ÙØ¹ Ø¨Ø¹Ø¯.",
        "stats_msg": "ðŸ“Š **Ø¥Ø­ØµØ§Ø¦ÙŠØ§ØªÙƒ:**\nâ€¢ Ø§Ù„ØªØ­Ù…ÙŠÙ„Ø§Øª Ø§Ù„Ù…ØªØ¨Ù‚ÙŠØ©: {}\nâ€¢ Ø§Ù„Ø¯ÙØ¹Ø§Øª Ø§Ù„Ù…ØªØ¨Ù‚ÙŠØ©: {}",
        "change_channel_prompt": "ðŸ”„ **ØªØºÙŠÙŠØ± Ù‚Ù†Ø§Ø© Ø§Ù„Ø¯ÙØ¹Ø§Øª**\n1. ØªØ£ÙƒØ¯ Ù…Ù† Ø£Ù†Ù†ÙŠ Ù…Ø³Ø¤ÙˆÙ„ ÙÙŠ Ø§Ù„Ù‚Ù†Ø§Ø© Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø©.\n2. Ø£Ø¹Ø¯ ØªÙˆØ¬ÙŠÙ‡ Ø£ÙŠ Ø±Ø³Ø§Ù„Ø© Ù…Ù† ØªÙ„Ùƒ Ø§Ù„Ù‚Ù†Ø§Ø© Ø¥Ù„Ù‰ Ù‡Ù†Ø§.",
        "disk_config_prompt": "ðŸ’¾ **Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª Ø§Ù„Ù‚Ø±Øµ**\nØ§Ù„Ø­Ø¯ Ø§Ù„Ø£Ø¯Ù†Ù‰ Ø§Ù„Ø­Ø§Ù„ÙŠ Ù„Ù„Ù…Ø³Ø§Ø­Ø© Ø§Ù„Ø­Ø±Ø©: **{} Ù…ÙŠØ¬Ø§Ø¨Ø§ÙŠØª**\nÙ„Ù„ØªØºÙŠÙŠØ±: `/setdisk <value>`",
        "mtproto_config_prompt": "âš¡ **Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª MTProto**\nØ§Ù„Ø­Ø¯ Ø§Ù„Ø£Ù‚ØµÙ‰ Ø§Ù„Ø­Ø§Ù„ÙŠ Ù„Ù„Ø±ÙØ¹: **{} Ù…ÙŠØ¬Ø§Ø¨Ø§ÙŠØª**\nÙ„Ù„ØªØºÙŠÙŠØ±: `/setmtproto <value>`",
        "free_panel_prompt": "ðŸ“¦ Ø§Ù„ØªØ­Ù…ÙŠÙ„Ø§Øª Ø§Ù„Ù…Ø¬Ø§Ù†ÙŠØ©\nØ§Ù„Ù…Ø¬Ø§Ù†ÙŠ Ø§Ù„Ø­Ø§Ù„ÙŠ ÙŠÙˆÙ…ÙŠØ§Ù‹: {}",
        "reward_panel_prompt": "ðŸŽ Ù„ÙˆØ­Ø© Ø§Ù„Ù…ÙƒØ§ÙØ¢Øª\nØ§Ù„Ø­Ø§Ù„ÙŠ: +{} ØªØ­Ù…ÙŠÙ„ Ù„ÙƒÙ„ Ø¥Ø¹Ù„Ø§Ù† 20 Ø«Ø§Ù†ÙŠØ©",
        "ad_panel_prompt": "âš™ï¸ Ù„ÙˆØ­Ø© Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†Ø§Øª\nØ§Ù„Ø­Ø§Ù„ÙŠ: {}",
        "password_saved": "ðŸ” ØªÙ… Ø­ÙØ¸ ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±.",
        "password_too_long": "ÙŠØ¬Ø¨ Ø£Ù† ØªÙƒÙˆÙ† ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ± 64 Ø­Ø±ÙØ§Ù‹ Ø£Ùˆ Ø£Ù‚Ù„.",
        "file_to_link_prompt": "ðŸ”— **Ù…Ù„Ù-Ø¥Ù„Ù‰-Ø±Ø§Ø¨Ø·**\nØ£Ø±Ø³Ù„ Ø§Ù„Ù…Ù„Ù(Ø§Øª) Ø§Ù„ØªÙŠ ØªØ±ÙŠØ¯ Ù…Ø´Ø§Ø±ÙƒØªÙ‡Ø§.",
        "link_invalid_expired": "âŒ Ù‡Ø°Ø§ Ø§Ù„Ø±Ø§Ø¨Ø· ØºÙŠØ± ØµØ§Ù„Ø­ Ø£Ùˆ Ù…Ù†ØªÙ‡ÙŠ Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ©.",
        "link_limit_reached": "â›” ÙˆØµÙ„ Ù‡Ø°Ø§ Ø§Ù„Ø±Ø§Ø¨Ø· Ø¥Ù„Ù‰ Ø­Ø¯ Ø§Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù….",
        "link_password_protected": "ðŸ” Ù‡Ø°Ø§ Ø§Ù„Ø±Ø§Ø¨Ø· Ù…Ø­Ù…ÙŠ Ø¨ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ±. Ø£Ø±Ø³Ù„ ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±.",
        "files_sent": "âœ… ØªÙ… Ø¥Ø±Ø³Ø§Ù„ Ù…Ù„ÙØ§ØªÙƒ.",
        "file_added": "ðŸ“¥ ØªÙ…Øª Ø¥Ø¶Ø§ÙØ© Ø§Ù„Ù…Ù„Ù #{}. Ø£Ø±Ø³Ù„ Ø§Ù„Ù…Ø²ÙŠØ¯ØŒ Ø£Ùˆ Ø§Ø¶ØºØ· Ø¹Ù„Ù‰ Ø¥Ù†Ø´Ø§Ø¡ Ø±Ø§Ø¨Ø·.",
        "fl_cancelled": "ØªÙ… Ø¥Ù„ØºØ§Ø¡ Ù…Ù„Ù-Ø¥Ù„Ù‰-Ø±Ø§Ø¨Ø·",
        "fl_start_again": "Ø§Ø¨Ø¯Ø£ Ù…Ù„Ù-Ø¥Ù„Ù‰-Ø±Ø§Ø¨Ø· Ù…Ø±Ø© Ø£Ø®Ø±Ù‰ Ø¨Ø§Ø³ØªØ®Ø¯Ø§Ù… /filetolink",
        "fl_choose_expiry": "Ø§Ø®ØªØ± Ø§Ù†ØªÙ‡Ø§Ø¡ ØµÙ„Ø§Ø­ÙŠØ© Ø§Ù„Ø±Ø§Ø¨Ø·:",
        "fl_expiry_updated": "ØªÙ… ØªØ­Ø¯ÙŠØ« Ø§Ù„Ø§Ù†ØªÙ‡Ø§Ø¡",
        "fl_choose_max_uses": "Ø§Ø®ØªØ± Ø§Ù„Ø­Ø¯ Ø§Ù„Ø£Ù‚ØµÙ‰ Ù„Ù„ØªØ³Ù„ÙŠÙ…Ø§Øª Ø§Ù„Ù†Ø§Ø¬Ø­Ø©:",
        "fl_uses_updated": "ØªÙ… ØªØ­Ø¯ÙŠØ« Ø­Ø¯ Ø§Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù…",
        "fl_set_password": "Ø£Ø±Ø³Ù„ ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ±ØŒ Ø£Ùˆ /clearpassword Ù„Ù„Ø¥Ø²Ø§Ù„Ø©.",
        "fl_link_created": "ØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ø±Ø§Ø¨Ø·",
        "fl_link_ready": "ðŸ”— Ø±Ø§Ø¨Ø·Ùƒ Ø¬Ø§Ù‡Ø²:\n{}\nØ§Ù„Ù…Ù„ÙØ§Øª: {}\nØ§Ù„ØªÙƒÙ„ÙØ©: 1 ØªØ­Ù…ÙŠÙ„ ÙŠÙˆÙ…ÙŠ Ù…Ø¬Ø§Ù†ÙŠ",
        "fl_daily_limit": "ØªÙ… Ø§Ù„ÙˆØµÙˆÙ„ Ù„Ù„Ø­Ø¯ Ø§Ù„ÙŠÙˆÙ…ÙŠ Ø§Ù„Ù…Ø¬Ø§Ù†ÙŠ. Ø´Ø§Ù‡Ø¯ Ø¥Ø¹Ù„Ø§Ù†Ø§Ù‹ Ù„ÙƒØ³Ø¨ Ø§Ù„Ù…Ø²ÙŠØ¯.",
        "fl_ad_busy": "âš ï¸ Ø®Ø§Ø¯Ù… Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†Ø§Øª Ù…Ø´ØºÙˆÙ„.",
        "admin_skipped": "âœ… ØªÙ… Ø§Ù„ØªØ®Ø·ÙŠ!",
        "admin_bypassed": "âœ… ØªÙ… Ø§Ù„ØªØ¬Ø§ÙˆØ²",
        "free_set": "âœ… ØªÙ… ØªØ¹ÙŠÙŠÙ† Ø§Ù„Ù…Ø¬Ø§Ù†ÙŠ Ø¥Ù„Ù‰ {}!",
        "free_updated": "âœ… ØªÙ… ØªØ­Ø¯ÙŠØ« Ø§Ù„ØªØ­Ù…ÙŠÙ„Ø§Øª Ø§Ù„Ù…Ø¬Ø§Ù†ÙŠØ© Ø¥Ù„Ù‰ {}!",
        "reward_set": "âœ… ØªÙ… ØªØ¹ÙŠÙŠÙ† Ø§Ù„Ù…ÙƒØ§ÙØ£Ø© Ø¥Ù„Ù‰ +{}!",
        "reward_updated": "âœ… ØªÙ… ØªØ­Ø¯ÙŠØ« Ø§Ù„Ù…ÙƒØ§ÙØ£Ø© Ø¥Ù„Ù‰ +{}!",
        "mode_updated": "âœ… Ø§Ù„ÙˆØ¶Ø¹: {}",
        "support_opened": "âœï¸ Ø£Ø±Ø³Ù„ Ø±Ø³Ø§Ù„Ø©/ØµÙˆØ±Ø©/ÙÙŠØ¯ÙŠÙˆ/Ù…Ù„Ù Ø£Ø¯Ù†Ø§Ù‡.",
        "admin_reply_mode": "âœï¸ Ø§Ù„Ø±Ø¯ Ø¹Ù„Ù‰ {}:",
        "user_reply_mode": "âœï¸ Ø§ÙƒØªØ¨ Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø© Ø£Ø¯Ù†Ø§Ù‡",
        "support_closed": "ðŸ”’ Ù…ØºÙ„Ù‚",
        "drop_cancelled": "âŒ Ù…Ù„ØºÙŠ",
        "drop_no_items": "âš ï¸ Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¹Ù†Ø§ØµØ±!",
        "drop_timer_set": "ØªÙ… ØªØ¹ÙŠÙŠÙ† {}!",
        "drop_broadcasting": "ðŸš€ Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø¨Ø« {} Ø¹Ù†Ø§ØµØ± Ø¥Ù„Ù‰ {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nØ­Ø°Ù ØªÙ„Ù‚Ø§Ø¦ÙŠ ÙÙŠ {}\nØ§Ø¶ØºØ· Ù„Ù„Ù…Ø·Ø§Ù„Ø¨Ø©:",
        "drop_done": "âœ… ØªÙ… Ø§Ù„Ø¨Ø« Ø¥Ù„Ù‰ {}",
        "age_expired": "â³ Ù…Ù†ØªÙ‡ÙŠ Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ©!",
        "age_claimed": "âŒ ØªÙ…Øª Ø§Ù„Ù…Ø·Ø§Ù„Ø¨Ø© Ø¨Ù‡ Ø¨Ø§Ù„ÙØ¹Ù„!",
        "age_verified": "ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚!",
        "age_denied": "âŒ Ù…Ø±ÙÙˆØ¶. ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† 18+",
        "lang_updated": "ØªÙ… Ø§Ù„ØªØ­Ø¯ÙŠØ«!",
        "batch_expired": "Ù…Ù†ØªÙ‡ÙŠ Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ©",
        "batch_loading": "Ø¬Ø§Ø±ÙŠ Ø§Ù„ØªØ­Ù…ÙŠÙ„...",
        "batch_no_channel": "Ù„Ø§ ØªÙˆØ¬Ø¯ Ù‚Ù†Ø§Ø© Ù…Ø±ØªØ¨Ø·Ø©!",
        "batch_setup_prompt": "ðŸ“¦ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯: Ø§Ø¬Ø¹Ù„ Ø§Ù„Ø¨ÙˆØª Ù…Ø³Ø¤ÙˆÙ„Ø§Ù‹ ÙÙŠ Ø§Ù„Ù‚Ù†Ø§Ø© ÙˆØ£Ø¹Ø¯ ØªÙˆØ¬ÙŠÙ‡ Ø±Ø³Ø§Ù„Ø© Ø¥Ù„Ù‰ Ù‡Ù†Ø§",
        "batch_mode_activated": "ØªÙ… ØªÙØ¹ÙŠÙ„ Ø§Ù„ÙˆØ¶Ø¹!",
        "batch_change_dest": "ðŸ”„ **ØªØºÙŠÙŠØ± Ù‚Ù†Ø§Ø© Ø§Ù„ÙˆØ¬Ù‡Ø©**\nØ§Ø¬Ø¹Ù„ Ø§Ù„Ø¨ÙˆØª Ù…Ø³Ø¤ÙˆÙ„Ø§Ù‹ ÙÙŠ Ø§Ù„Ù‚Ù†Ø§Ø© Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø©ØŒ Ø«Ù… Ø£Ø¹Ø¯ ØªÙˆØ¬ÙŠÙ‡ Ø±Ø³Ø§Ù„Ø© Ø¥Ù„Ù‰ Ù‡Ù†Ø§.",
        "join_channel_first_alert": "Ø§Ù†Ø¶Ù… Ù„Ù„Ù‚Ù†Ø§Ø© Ø£ÙˆÙ„Ø§Ù‹! ðŸ“¢ ÙŠØ¬Ø¨ Ø§Ù„Ø§Ù†Ø¶Ù…Ø§Ù…!",
        "join_channel_first": "Ø§Ù†Ø¶Ù… Ù„Ù„Ù‚Ù†Ø§Ø© Ø£ÙˆÙ„Ø§Ù‹! ðŸ“¢",
        "watch_timer_first": "â° Ø§ÙØªØ­ Ø§Ù„Ø±Ø§Ø¨Ø· ÙˆØ´Ø§Ù‡Ø¯ Ø§Ù„Ù…Ø¤Ù‚Øª Ù„Ù…Ø¯Ø© 20 Ø«Ø§Ù†ÙŠØ© Ø£ÙˆÙ„Ø§Ù‹!",
        "test_ad_verified": "âœ… ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø¥Ø¹Ù„Ø§Ù† Ø§Ù„Ø§Ø®ØªØ¨Ø§Ø±! +1",
        "test_ad_verified_msg": "âœ… **ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø¥Ø¹Ù„Ø§Ù† Ø§Ù„Ø§Ø®ØªØ¨Ø§Ø±!**\nØ§Ù„Ù…ÙƒØ§ÙØ£Ø©: ØªÙ… Ø¥Ø¹Ø§Ø¯Ø© ØªØ¹Ø¨Ø¦Ø© +1 ØªØ­Ù…ÙŠÙ„!",
        "finish_timer_first": "â° Ø£Ù†Ù‡Ù Ù…Ø¤Ù‚Øª 20 Ø«Ø§Ù†ÙŠØ© Ø£ÙˆÙ„Ø§Ù‹!",
        "verified_added": "ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚! ØªÙ…Øª Ø¥Ø¶Ø§ÙØ© +1",
        "resume_prompt": "âœ… ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚! ØªÙ…Øª Ø¥Ø¹Ø§Ø¯Ø© Ø§Ù„ØªØ¹Ø¨Ø¦Ø© +1. Ø§Ø³ØªØ¦Ù†Ø§ÙØŸ",
        "refilled_download": "âœ… ØªÙ…Øª Ø¥Ø¹Ø§Ø¯Ø© Ø§Ù„ØªØ¹Ø¨Ø¦Ø© +1! Ø­Ù…Ù„ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.",
        "fetching_bundle": "âœ… ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚! Ø¬Ø§Ø±ÙŠ Ø¬Ù„Ø¨ Ø§Ù„Ø­Ø²Ù…Ø©...",
        "outdated_button": "Ù‡Ø°Ø§ Ø§Ù„Ø²Ø± Ù‚Ø¯ÙŠÙ…. Ø£Ø±Ø³Ù„ Ø±Ø§Ø¨Ø·Ùƒ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.",
        "stopping": "Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø¥ÙŠÙ‚Ø§Ù...",
        "stopped": "ðŸ›‘ ØªÙ… Ø§Ù„Ø¥ÙŠÙ‚Ø§Ù",
        "resuming": "Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø§Ø³ØªØ¦Ù†Ø§Ù...",
        "checking_vault": "Ø¬Ø§Ø±ÙŠ ÙØ­Øµ Ø§Ù„Ø®Ø²Ù†Ø© ÙˆØ­Ù…Ù„ Ø§Ù„Ø®Ø§Ø¯Ù…...",
        "server_busy": "â³ **Ø§Ù„Ø®Ø§Ø¯Ù… Ù…Ø´ØºÙˆÙ„**\nÙ†Ø´Ø·: {}/{}\nØ­Ø±: {} Ù…ÙŠØ¬Ø§Ø¨Ø§ÙŠØª\nÙ‚Ø§Ø¦Ù…Ø© Ø§Ù„Ø§Ù†ØªØ¸Ø§Ø±: #{}\nØ³ÙŠØ¨Ø¯Ø£ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹!",
        "simulated": "ðŸ›  ØªÙ…Øª Ø§Ù„Ù…Ø­Ø§ÙƒØ§Ø©! Ø§Ø¶ØºØ· Ø§Ù„Ø¢Ù† Ø¹Ù„Ù‰ ØªØ­Ù‚Ù‚ ÙˆØ§Ø­ØµÙ„ Ø¹Ù„Ù‰ +1",
        "server_unreachable": "âŒ Ø§Ù„Ø®Ø§Ø¯Ù… ØºÙŠØ± Ù…ØªØ§Ø­",
        "monetag_failed_twice": "Ø£ÙƒÙ…Ù„ Ù…Ø­Ø§ÙˆÙ„ØªÙŠÙ† ÙØ§Ø´Ù„ØªÙŠÙ† Ù„Ù€ Monetag Ø£ÙˆÙ„Ø§Ù‹.",
        "monetag_fallback_prompt": "ðŸŒ ÙØ´Ù„ Monetag Ù…Ø±ØªÙŠÙ†. ØªØ§Ø¨Ø¹ Ù…Ø¹ Adsterra:",
        "adsterra_ready": "Ø¨Ø¯ÙŠÙ„ Adsterra Ø¬Ø§Ù‡Ø²",
        "finish_monetag": "ðŸ“º Ø£Ù†Ù‡Ù Ø¥Ø¹Ù„Ø§Ù† Monetag ÙÙŠ Ø§Ù„ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„Ù…ØµØºØ±ØŒ Ø«Ù… ØªØ­Ù‚Ù‚ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.",
        "monetag_failed_use_adsterra": "ÙØ´Ù„ Monetag Ù…Ø±ØªÙŠÙ†. Ø§Ø³ØªØ®Ø¯Ù… Ø¨Ø¯ÙŠÙ„ Adsterra Ø£Ø¯Ù†Ø§Ù‡.",
        "ad_link_expired": "Ø§Ù†ØªÙ‡Øª ØµÙ„Ø§Ø­ÙŠØ© Ø±Ø§Ø¨Ø· Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†. Ø£Ø±Ø³Ù„ Ø±Ø§Ø¨Ø·Ùƒ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.",
        "ad_verified_added": "âœ… ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†! ØªÙ…Øª Ø¥Ø¶Ø§ÙØ© +{}",
        "test_ad_completed": "âœ… ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø¥Ø¹Ù„Ø§Ù† Ø§Ù„Ø§Ø®ØªØ¨Ø§Ø±\nØªÙ… Ø§Ø¹ØªÙ…Ø§Ø¯ Ø§Ù„Ù…ÙƒØ§ÙØ£Ø©: +{} ØªØ­Ù…ÙŠÙ„.",
        "sponsor_viewed": "âœ… ØªÙ…Øª Ù…Ø´Ø§Ù‡Ø¯Ø© Ø§Ù„Ø±Ø§Ø¹ÙŠ! ØªÙ…Øª Ø¥Ø¶Ø§ÙØ© +{}",
        "refilled_send_again": "âœ… ØªÙ…Øª Ø¥Ø¹Ø§Ø¯Ø© Ø§Ù„ØªØ¹Ø¨Ø¦Ø© +{}! Ø£Ø±Ø³Ù„ Ø±Ø§Ø¨Ø·Ùƒ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.",
        "queued": "â³ ÙÙŠ Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ø§Ù†ØªØ¸Ø§Ø± #{}",
        "banned": "ðŸš« Ø£Ù†Øª Ù…Ø­Ø¸ÙˆØ±.",
        "no_links": "âŒ Ù„Ù… ÙŠØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ Ø±ÙˆØ§Ø¨Ø·.",
        "batch_count": "ðŸ“¦ Ø¯ÙØ¹Ø© {} Ø±ÙˆØ§Ø¨Ø·",
        "restore_invalid_json": "âŒ ÙØ´Ù„ Ø§Ù„Ø§Ø³ØªØ¹Ø§Ø¯Ø©: **{}** Ù„ÙŠØ³ JSON ØµØ§Ù„Ø­Ø§Ù‹.",
        "restore_failed": "âŒ ÙØ´Ù„ Ø§Ù„Ø§Ø³ØªØ¹Ø§Ø¯Ø©: {}",
        "restore_success": "âœ… **Ù†Ø¬Ø§Ø­ Ø§Ù„Ø§Ø³ØªØ¹Ø§Ø¯Ø©!**\nØ§Ù„Ù…Ù„Ù: **{}**\nØªÙ…Øª Ø§Ø³ØªØ¹Ø§Ø¯Ø© **{}** Ø¥Ø¯Ø®Ø§Ù„Ø§Øª.",
        "admin_edit_welcome_prompt": "âœï¸ Ø£Ø±Ø³Ù„ Ø±Ø³Ø§Ù„Ø© Ø§Ù„ØªØ±Ø­ÙŠØ¨ Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø©. Ø§Ø³ØªØ®Ø¯Ù… `{bot_name}` Ù„Ø§Ø³Ù… Ù…Ø³ØªØ®Ø¯Ù… Ø§Ù„Ø¨ÙˆØª.",
        "admin_welcome_updated": "âœ… ØªÙ… ØªØ­Ø¯ÙŠØ« Ø±Ø³Ø§Ù„Ø© Ø§Ù„ØªØ±Ø­ÙŠØ¨!",
        "menu_edit_welcome": "âœï¸ ØªØ­Ø±ÙŠØ± Ø±Ø³Ø§Ù„Ø© Ø§Ù„ØªØ±Ø­ÙŠØ¨",
        "cached_instant_video": "âš¡ Ø°Ø§ÙƒØ±Ø© ØªØ®Ø²ÙŠÙ† Ù…Ø¤Ù‚Øª ÙÙˆØ±ÙŠØ© [{}] {} {}",
        "cached_instant_audio": "âš¡ **Ø°Ø§ÙƒØ±Ø© ØªØ®Ø²ÙŠÙ† Ù…Ø¤Ù‚Øª ÙÙˆØ±ÙŠØ©** `{}`",
        "cached_instant_image": "âš¡ **Ø°Ø§ÙƒØ±Ø© ØªØ®Ø²ÙŠÙ† Ù…Ø¤Ù‚Øª ÙÙˆØ±ÙŠØ©** `{}`",
        "auto_delete_9m": "â³ Ø­Ø°Ù ØªÙ„Ù‚Ø§Ø¦ÙŠ ÙÙŠ 9 Ø¯Ù‚Ø§Ø¦Ù‚",
        "download_success": "âœ… ØªÙ… Ø§Ù„ØªØ­Ù…ÙŠÙ„ Ø¨Ù†Ø¬Ø§Ø­!"
    },
    "ru": {
        "welcome": "ðŸš€ **Ð”ÐžÐ‘Ð Ðž ÐŸÐžÐ–ÐÐ›ÐžÐ’ÐÐ¢Ð¬ Ð’ MICHAELBBC VAULT - Ð£ÐÐ˜Ð’Ð•Ð Ð¡ÐÐ›Ð¬ÐÐ«Ð™ Ð—ÐÐ“Ð Ð£Ð—Ð§Ð˜Ðš!**\n\nðŸ”¥ Ð§Ð¢Ðž Ð¯ Ð£ÐœÐ•Ð®:\nðŸŽ¬ Ð’Ð˜Ð”Ð•Ðž HD Ð‘ÐµÐ· Ð’Ð¾Ð´ÑÐ½Ñ‹Ñ… Ð—Ð½Ð°ÐºÐ¾Ð²!\nðŸŽµ ÐÐ£Ð”Ð˜Ðž MP3 192kbps!\nðŸ–¼ï¸ Ð˜Ð—ÐžÐ‘Ð ÐÐ–Ð•ÐÐ˜Ð¯ Ð¡ÐºÐ°Ñ‡Ð¸Ð²Ð°Ð½Ð¸Ðµ Ð’Ð¡Ð•Ð¥!\nðŸ“ Ð¡Ð£Ð‘Ð¢Ð˜Ð¢Ð Ð« ÐÐ²Ñ‚Ð¾!\nðŸ“¦ ÐŸÐÐšÐ•Ð¢Ð« 100+ Ð¡ÑÑ‹Ð»Ð¾Ðº!\nâš¡ ÐšÐ­Ð¨ 1 Ð¡ÐµÐº!\nðŸ’Ž Ð¥Ð ÐÐÐ˜Ð›Ð˜Ð©Ð• ÐÐ°Ð²ÑÐµÐ³Ð´Ð°!\nðŸ“¤ Ð—ÐÐ“Ð Ð£Ð—ÐšÐ Ð¤ÐÐ™Ð›ÐžÐ’!\nðŸ”— Ð¤ÐÐ™Ð›-Ð’-Ð¡Ð¡Ð«Ð›ÐšÐ£: Ð¡Ð¾Ð·Ð´Ð°Ð²Ð°Ð¹Ñ‚Ðµ ÑÑÑ‹Ð»ÐºÐ¸ Ð´Ð»Ñ Ð¾Ð±Ð¼ÐµÐ½Ð°!\n\nðŸ‘‰ Ð’Ð¡Ð¢ÐÐ’Ð¬Ð¢Ð• Ð¡Ð¡Ð«Ð›ÐšÐ£, Ð§Ð¢ÐžÐ‘Ð« ÐÐÐ§ÐÐ¢Ð¬! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ Ð’Ð¸Ð´ÐµÐ¾ (MP4)", "btn_audio": "ðŸŽµ ÐÑƒÐ´Ð¸Ð¾ (MP3)", "btn_image": "ðŸ–¼ï¸ Ð˜Ð·Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ñ", "btn_sub": "ðŸ“ Ð¡ÑƒÐ±Ñ‚Ð¸Ñ‚Ñ€Ñ‹ (SRT)",
        "ask_format": "ðŸ‘‡ **ÐžÐ¢Ð›Ð˜Ð§ÐÐž! ÐšÐ°ÐºÐ¾Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚ Ð²Ñ‹ Ñ…Ð¾Ñ‚Ð¸Ñ‚Ðµ? Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð½Ð¸Ð¶Ðµ!**",
        "fetching": "ðŸ“¥ **ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ðµ Ð²Ð°ÑˆÐµÐ³Ð¾ {}... ÐŸÐ¾Ð´Ð¾Ð¶Ð´Ð¸Ñ‚Ðµ! â³âœ¨**",
        "error_generic": "âŒ ÐžÐ¹! ÐžÑˆÐ¸Ð±ÐºÐ°! ðŸ˜¢ Ð¡ÑÑ‹Ð»ÐºÐ° Ð¿Ñ€Ð¸Ð²Ð°Ñ‚Ð½Ð°Ñ/Ð·Ð°Ð±Ð»Ð¾ÐºÐ¸Ñ€Ð¾Ð²Ð°Ð½Ð°. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ Ð¿ÑƒÐ±Ð»Ð¸Ñ‡Ð½ÑƒÑŽ!",
        "error_50mb": "âŒ Ð¡Ð»Ð¸ÑˆÐºÐ¾Ð¼ Ð±Ð¾Ð»ÑŒÑˆÐ¾Ð¹! ðŸ˜… Ð­Ñ‚Ð¾ Ð²Ð¸Ð´ÐµÐ¾ Ð±Ð¾Ð»ÑŒÑˆÐµ 300 ÐœÐ‘. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ ÐºÐ¾Ñ€Ð¾Ñ‡Ðµ!", 
        "error_no_img": "âŒ Ð˜Ð·Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ñ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ñ‹! ðŸ˜¢ ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ Ð´Ñ€ÑƒÐ³ÑƒÑŽ ÑÑÑ‹Ð»ÐºÑƒ!",
        "images_received": "â³ **ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¾ {} Ð¸Ð·Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ð¹.**",
        "select_lang": "ðŸŒ Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð²Ð°Ñˆ ÑÐ·Ñ‹Ðº! Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð½Ð¸Ð¶Ðµ! ðŸ‘‡", 
        "lang_set": "âœ… Ð¯Ð·Ñ‹Ðº ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½! ÐÐ°ÑÐ»Ð°Ð¶Ð´Ð°Ð¹Ñ‚ÐµÑÑŒ! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **ÐžÐ±Ð½Ð°Ñ€ÑƒÐ¶ÐµÐ½ Ð¿Ð°ÐºÐµÑ‚ ({} ÑÑÑ‹Ð»Ð¾Ðº)**\nÐšÐ°ÐºÐ¾Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚?",
        "batch_dest": "ðŸ“¦ **ÐšÑƒÐ´Ð° Ð¾Ñ‚Ð¿Ñ€Ð°Ð²Ð¸Ñ‚ÑŒ?**",
        "btn_chat": "ðŸ“¥ Ð’ Ñ‡Ð°Ñ‚", "btn_chan": "ðŸ“¢ Ð’ ÐºÐ°Ð½Ð°Ð»",
        "limit_reached": "âš ï¸ **Ð›Ð¸Ð¼Ð¸Ñ‚ Ð´Ð¾ÑÑ‚Ð¸Ð³Ð½ÑƒÑ‚!** Ð’Ñ‹ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ð»Ð¸ 4 Ð‘Ð•Ð¡ÐŸÐ›ÐÐ¢ÐÐ«Ð¥! ÐŸÐ¾ÑÐ¼Ð¾Ñ‚Ñ€Ð¸Ñ‚Ðµ 20-ÑÐµÐº Ñ€ÐµÐºÐ»Ð°Ð¼Ñƒ â†’ ÐŸÐ¾Ð»ÑƒÑ‡Ð¸Ñ‚Ðµ +1 Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÑƒ!",
        "refill_btn": "ðŸ”“ ÐžÑ‚ÐºÑ€Ñ‹Ñ‚ÑŒ ÑÑÑ‹Ð»ÐºÑƒ Ð¸ Ð¿Ð¾Ð¿Ð¾Ð»Ð½Ð¸Ñ‚ÑŒ +1",
        "join_btn": "ðŸ“¢ ÐŸÑ€Ð¸ÑÐ¾ÐµÐ´Ð¸Ð½Ð¸Ñ‚ÑŒÑÑ Ðº ÐºÐ°Ð½Ð°Ð»Ñƒ", "check_btn": "ðŸ’œ ÐŸÑ€Ð¾Ð²ÐµÑ€Ð¸Ñ‚ÑŒ Ð±Ð°Ð»Ð°Ð½Ñ",
        "limit_batch": "âš ï¸ **Ð›Ð¸Ð¼Ð¸Ñ‚ Ð¿Ð°ÐºÐµÑ‚Ð° Ð´Ð¾ÑÑ‚Ð¸Ð³Ð½ÑƒÑ‚ Ð½Ð° {} Ð¸Ð· {}**\nÐŸÐ¾ÑÐ¼Ð¾Ñ‚Ñ€Ð¸Ñ‚Ðµ 20-ÑÐµÐº Ñ€ÐµÐºÐ»Ð°Ð¼Ñƒ â†’ +1 Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð´Ð»Ñ Ð¿Ñ€Ð¾Ð´Ð¾Ð»Ð¶ÐµÐ½Ð¸Ñ.",
        "batch_start": "ðŸ“¦ **ÐŸÐ°ÐºÐµÑ‚ Ð·Ð°Ð¿ÑƒÑ‰ÐµÐ½:** {} **{} Ñ„Ð°Ð¹Ð»Ð¾Ð²**\nâ³ ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ°...",
        "batch_done": "ðŸ **Ð“Ð¾Ñ‚Ð¾Ð²Ð¾!** âœ… {} âŒ {}\nðŸ“¥ {} Ñ„Ð°Ð¹Ð»Ð¾Ð² Ð·Ð´ÐµÑÑŒ.",
        "batch_done_chan": "ðŸ **Ð“Ð¾Ñ‚Ð¾Ð²Ð¾!** âœ… {} âŒ {}\nðŸ“¢ {} Ñ„Ð°Ð¹Ð»Ð¾Ð² Ð¿ÐµÑ€ÐµÑÐ»Ð°Ð½Ð¾!",
        "dl_video": "ðŸ“¥ Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð²Ð¸Ð´ÐµÐ¾...", "dl_audio": "ðŸ“¥ Ð˜Ð·Ð²Ð»ÐµÑ‡ÐµÐ½Ð¸Ðµ Ð°ÑƒÐ´Ð¸Ð¾...", "dl_image": "ðŸ“¥ Ð¡ÐºÐ°Ñ‡Ð¸Ð²Ð°Ð½Ð¸Ðµ Ð¸Ð·Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ð¹...", "dl_sub": "ðŸ“¥ ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ðµ ÑÑƒÐ±Ñ‚Ð¸Ñ‚Ñ€Ð¾Ð²...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Ð—Ð°Ð±Ð»Ð¾ÐºÐ¸Ñ€Ð¾Ð²Ð°Ð½Ð¾/Ð¿Ñ€Ð¸Ð²Ð°Ñ‚Ð½Ð¾", "failed_generic": "âŒ ÐžÑˆÐ¸Ð±ÐºÐ°",
        "menu_lang": "ðŸŒ Ð¯Ð·Ñ‹Ðº", "menu_stats": "ðŸ“Š ÐœÐ¾Ñ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°", "menu_help": "ðŸ’¬ ÐŸÐ¾Ð´Ð´ÐµÑ€Ð¶ÐºÐ° / FAQ", "menu_join": "ðŸ“¢ ÐŸÑ€Ð¸ÑÐ¾ÐµÐ´Ð¸Ð½Ð¸Ñ‚ÑŒÑÑ Ðº ÐºÐ°Ð½Ð°Ð»Ñƒ",
        "menu_uploads": "ðŸ¿ Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ¸ Ñ„Ð°Ð½Ð°Ñ‚Ð¾Ð²", "menu_upload": "ðŸ“¤ Ð—Ð°Ð³Ñ€ÑƒÐ·Ð¸Ñ‚ÑŒ Ñ„Ð°Ð¹Ð»",
        "admin_upload_prompt": "ðŸ“‚ **Ð’Ñ…Ð¾Ð´ÑÑ‰Ð¸Ðµ Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ¸ Ñ„Ð°Ð½Ð°Ñ‚Ð¾Ð²**",
        "user_upload_prompt": "ðŸ“¤ **Ð—Ð°Ð³Ñ€ÑƒÐ·Ð¸Ñ‚ÑŒ Ñ„Ð°Ð¹Ð»**\nÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð²Ð¸Ð´ÐµÐ¾/Ð¸Ð·Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ðµ/Ñ„Ð°Ð¹Ð» ÐÐ´Ð¼Ð¸Ð½Ñƒ. Ð›Ð¸Ð¼Ð¸Ñ‚ 5/24Ñ‡.",
        "upload_success_user": "âœ… ÐžÑ‚Ð¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¾ ÐÐ´Ð¼Ð¸Ð½Ñƒ!",
        "upload_limit_reached": "âš ï¸ Ð”Ð¾ÑÑ‚Ð¸Ð³Ð½ÑƒÑ‚ Ð»Ð¸Ð¼Ð¸Ñ‚ Ð·Ð°Ð³Ñ€ÑƒÐ·Ð¾Ðº 5/24Ñ‡.",
        "no_uploads": "ðŸ“­ Ð—Ð°Ð³Ñ€ÑƒÐ·Ð¾Ðº Ð¿Ð¾ÐºÐ° Ð½ÐµÑ‚.",
        "stats_msg": "ðŸ“Š **Ð’Ð°ÑˆÐ° ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°:**\nâ€¢ ÐžÑÑ‚Ð°Ð»Ð¾ÑÑŒ Ð·Ð°Ð³Ñ€ÑƒÐ·Ð¾Ðº: {}\nâ€¢ ÐžÑÑ‚Ð°Ð»Ð¾ÑÑŒ Ð¿Ð°ÐºÐµÑ‚Ð¾Ð²: {}",
        "change_channel_prompt": "ðŸ”„ **Ð˜Ð·Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ ÐºÐ°Ð½Ð°Ð» Ð´Ð»Ñ Ð¿Ð°ÐºÐµÑ‚Ð¾Ð²**\n1. Ð£Ð±ÐµÐ´Ð¸Ñ‚ÐµÑÑŒ, Ñ‡Ñ‚Ð¾ Ñ Ð°Ð´Ð¼Ð¸Ð½ Ð² Ð½Ð¾Ð²Ð¾Ð¼ ÐºÐ°Ð½Ð°Ð»Ðµ.\n2. ÐŸÐµÑ€ÐµÑˆÐ»Ð¸Ñ‚Ðµ Ð»ÑŽÐ±Ð¾Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ Ð¸Ð· ÑÑ‚Ð¾Ð³Ð¾ ÐºÐ°Ð½Ð°Ð»Ð° ÑÑŽÐ´Ð°.",
        "disk_config_prompt": "ðŸ’¾ **ÐÐ°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ° Ð´Ð¸ÑÐºÐ°**\nÐ¢ÐµÐºÑƒÑ‰Ð¸Ð¹ Ð¼Ð¸Ð½. ÑÐ²Ð¾Ð±Ð¾Ð´Ð½Ñ‹Ð¹ Ð´Ð¸ÑÐº: **{} ÐœÐ‘**\nÐ§Ñ‚Ð¾Ð±Ñ‹ Ð¸Ð·Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ: `/setdisk <Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ðµ>`",
        "mtproto_config_prompt": "âš¡ **ÐÐ°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ° MTProto**\nÐ¢ÐµÐºÑƒÑ‰Ð¸Ð¹ Ð¼Ð°ÐºÑ. Ñ€Ð°Ð·Ð¼ÐµÑ€ Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ¸: **{} ÐœÐ‘**\nÐ§Ñ‚Ð¾Ð±Ñ‹ Ð¸Ð·Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ: `/setmtproto <Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ðµ>`",
        "free_panel_prompt": "ðŸ“¦ Ð‘Ð•Ð¡ÐŸÐ›ÐÐ¢ÐÐ«Ð• Ð—ÐÐ“Ð Ð£Ð—ÐšÐ˜\nÐ¢ÐµÐºÑƒÑ‰Ð¸Ðµ Ð±ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ñ‹Ðµ Ð² Ð´ÐµÐ½ÑŒ: {}",
        "reward_panel_prompt": "ðŸŽ ÐŸÐÐÐ•Ð›Ð¬ ÐÐÐ“Ð ÐÐ”\nÐ¢ÐµÐºÑƒÑ‰Ð°Ñ: +{} Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð·Ð° 20-ÑÐµÐº Ñ€ÐµÐºÐ»Ð°Ð¼Ñƒ",
        "ad_panel_prompt": "âš™ï¸ ÐŸÐ°Ð½ÐµÐ»ÑŒ Ñ€ÐµÐºÐ»Ð°Ð¼Ñ‹\nÐ¢ÐµÐºÑƒÑ‰Ð°Ñ: {}",
        "password_saved": "ðŸ” ÐŸÐ°Ñ€Ð¾Ð»ÑŒ ÑÐ¾Ñ…Ñ€Ð°Ð½ÐµÐ½.",
        "password_too_long": "ÐŸÐ°Ñ€Ð¾Ð»ÑŒ Ð´Ð¾Ð»Ð¶ÐµÐ½ Ð±Ñ‹Ñ‚ÑŒ Ð½Ðµ Ð±Ð¾Ð»ÐµÐµ 64 ÑÐ¸Ð¼Ð²Ð¾Ð»Ð¾Ð².",
        "file_to_link_prompt": "ðŸ”— **Ð¤Ð°Ð¹Ð»-Ð²-ÑÑÑ‹Ð»ÐºÑƒ**\nÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ñ„Ð°Ð¹Ð»(Ñ‹), ÐºÐ¾Ñ‚Ð¾Ñ€Ñ‹Ð¼Ð¸ Ñ…Ð¾Ñ‚Ð¸Ñ‚Ðµ Ð¿Ð¾Ð´ÐµÐ»Ð¸Ñ‚ÑŒÑÑ.",
        "link_invalid_expired": "âŒ Ð­Ñ‚Ð° ÑÑÑ‹Ð»ÐºÐ° Ð½ÐµÐ´ÐµÐ¹ÑÑ‚Ð²Ð¸Ñ‚ÐµÐ»ÑŒÐ½Ð° Ð¸Ð»Ð¸ Ð¸ÑÑ‚ÐµÐºÐ»Ð°.",
        "link_limit_reached": "â›” Ð­Ñ‚Ð° ÑÑÑ‹Ð»ÐºÐ° Ð´Ð¾ÑÑ‚Ð¸Ð³Ð»Ð° Ð»Ð¸Ð¼Ð¸Ñ‚Ð° Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ð½Ð¸Ñ.",
        "link_password_protected": "ðŸ” Ð­Ñ‚Ð° ÑÑÑ‹Ð»ÐºÐ° Ð·Ð°Ñ‰Ð¸Ñ‰ÐµÐ½Ð° Ð¿Ð°Ñ€Ð¾Ð»ÐµÐ¼. ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð¿Ð°Ñ€Ð¾Ð»ÑŒ.",
        "files_sent": "âœ… Ð’Ð°ÑˆÐ¸ Ñ„Ð°Ð¹Ð»Ñ‹ Ð¾Ñ‚Ð¿Ñ€Ð°Ð²Ð»ÐµÐ½Ñ‹.",
        "file_added": "ðŸ“¥ Ð”Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ Ñ„Ð°Ð¹Ð» #{}. ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ ÐµÑ‰Ðµ Ð¸Ð»Ð¸ Ð½Ð°Ð¶Ð¼Ð¸Ñ‚Ðµ Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ ÑÑÑ‹Ð»ÐºÑƒ.",
        "fl_cancelled": "Ð¤Ð°Ð¹Ð»-Ð²-ÑÑÑ‹Ð»ÐºÑƒ Ð¾Ñ‚Ð¼ÐµÐ½ÐµÐ½",
        "fl_start_again": "ÐÐ°Ñ‡Ð½Ð¸Ñ‚Ðµ Ð¤Ð°Ð¹Ð»-Ð²-ÑÑÑ‹Ð»ÐºÑƒ Ð·Ð°Ð½Ð¾Ð²Ð¾ Ñ /filetolink",
        "fl_choose_expiry": "Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÑÑ€Ð¾Ðº Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ñ ÑÑÑ‹Ð»ÐºÐ¸:",
        "fl_expiry_updated": "Ð¡Ñ€Ð¾Ðº Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ñ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½",
        "fl_choose_max_uses": "Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¼Ð°ÐºÑ. ÐºÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ ÑƒÑÐ¿ÐµÑˆÐ½Ñ‹Ñ… Ð´Ð¾ÑÑ‚Ð°Ð²Ð¾Ðº:",
        "fl_uses_updated": "Ð›Ð¸Ð¼Ð¸Ñ‚ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ð½Ð¸Ñ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½",
        "fl_set_password": "ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð¿Ð°Ñ€Ð¾Ð»ÑŒ Ð¸Ð»Ð¸ /clearpassword Ð´Ð»Ñ ÑƒÐ´Ð°Ð»ÐµÐ½Ð¸Ñ.",
        "fl_link_created": "Ð¡ÑÑ‹Ð»ÐºÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð°",
        "fl_link_ready": "ðŸ”— Ð’Ð°ÑˆÐ° ÑÑÑ‹Ð»ÐºÐ° Ð³Ð¾Ñ‚Ð¾Ð²Ð°:\n{}\nÐ¤Ð°Ð¹Ð»Ð¾Ð²: {}\nÐ¡Ñ‚Ð¾Ð¸Ð¼Ð¾ÑÑ‚ÑŒ: 1 Ð±ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ð°Ñ Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð² Ð´ÐµÐ½ÑŒ",
        "fl_daily_limit": "Ð”Ð½ÐµÐ²Ð½Ð¾Ð¹ Ð±ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ñ‹Ð¹ Ð»Ð¸Ð¼Ð¸Ñ‚ Ð´Ð¾ÑÑ‚Ð¸Ð³Ð½ÑƒÑ‚. ÐŸÐ¾ÑÐ¼Ð¾Ñ‚Ñ€Ð¸Ñ‚Ðµ Ñ€ÐµÐºÐ»Ð°Ð¼Ñƒ, Ñ‡Ñ‚Ð¾Ð±Ñ‹ Ð·Ð°Ñ€Ð°Ð±Ð¾Ñ‚Ð°Ñ‚ÑŒ Ð±Ð¾Ð»ÑŒÑˆÐµ.",
        "fl_ad_busy": "âš ï¸ Ð ÐµÐºÐ»Ð°Ð¼Ð½Ñ‹Ð¹ ÑÐµÑ€Ð²ÐµÑ€ Ð·Ð°Ð½ÑÑ‚.",
        "admin_skipped": "âœ… ÐŸÑ€Ð¾Ð¿ÑƒÑ‰ÐµÐ½Ð¾!",
        "admin_bypassed": "âœ… ÐžÐ±Ð¾Ð¹Ð´ÐµÐ½Ð¾",
        "free_set": "âœ… Ð‘ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ð¾ ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾ Ð½Ð° {}!",
        "free_updated": "âœ… Ð‘ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ñ‹Ðµ Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ¸ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ñ‹ Ð´Ð¾ {}!",
        "reward_set": "âœ… ÐÐ°Ð³Ñ€Ð°Ð´Ð° ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð° Ð½Ð° +{}!",
        "reward_updated": "âœ… ÐÐ°Ð³Ñ€Ð°Ð´Ð° Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð° Ð´Ð¾ +{}!",
        "mode_updated": "âœ… Ð ÐµÐ¶Ð¸Ð¼: {}",
        "support_opened": "âœï¸ ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ/Ñ„Ð¾Ñ‚Ð¾/Ð²Ð¸Ð´ÐµÐ¾/Ñ„Ð°Ð¹Ð» Ð½Ð¸Ð¶Ðµ.",
        "admin_reply_mode": "âœï¸ ÐžÑ‚Ð²ÐµÑ‚Ð¸Ñ‚ÑŒ {}:",
        "user_reply_mode": "âœï¸ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾Ð´Ð¾Ð»Ð¶ÐµÐ½Ð¸Ðµ Ð½Ð¸Ð¶Ðµ",
        "support_closed": "ðŸ”’ Ð—Ð°ÐºÑ€Ñ‹Ñ‚Ð¾",
        "drop_cancelled": "âŒ ÐžÑ‚Ð¼ÐµÐ½ÐµÐ½Ð¾",
        "drop_no_items": "âš ï¸ ÐÐµÑ‚ ÑÐ»ÐµÐ¼ÐµÐ½Ñ‚Ð¾Ð²!",
        "drop_timer_set": "{} ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾!",
        "drop_broadcasting": "ðŸš€ Ð¢Ñ€Ð°Ð½ÑÐ»ÑÑ†Ð¸Ñ {} ÑÐ»ÐµÐ¼ÐµÐ½Ñ‚Ð¾Ð² Ð´Ð»Ñ {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nÐÐ²Ñ‚Ð¾ÑƒÐ´Ð°Ð»ÐµÐ½Ð¸Ðµ Ñ‡ÐµÑ€ÐµÐ· {}\nÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ, Ñ‡Ñ‚Ð¾Ð±Ñ‹ Ð·Ð°Ð±Ñ€Ð°Ñ‚ÑŒ:",
        "drop_done": "âœ… Ð¢Ñ€Ð°Ð½ÑÐ»ÑÑ†Ð¸Ñ Ð²Ñ‹Ð¿Ð¾Ð»Ð½ÐµÐ½Ð° Ð´Ð»Ñ {}",
        "age_expired": "â³ Ð˜ÑÑ‚ÐµÐºÐ»Ð¾!",
        "age_claimed": "âŒ Ð£Ð¶Ðµ Ð·Ð°Ð±Ñ€Ð°Ð½Ð¾!",
        "age_verified": "ÐŸÑ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð¾!",
        "age_denied": "âŒ ÐžÑ‚ÐºÐ°Ð·Ð°Ð½Ð¾. Ð”Ð¾Ð»Ð¶Ð½Ð¾ Ð±Ñ‹Ñ‚ÑŒ 18+",
        "lang_updated": "ÐžÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾!",
        "batch_expired": "Ð˜ÑÑ‚ÐµÐºÐ»Ð¾",
        "batch_loading": "Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ°...",
        "batch_no_channel": "ÐšÐ°Ð½Ð°Ð» Ð½Ðµ Ð¿Ñ€Ð¸Ð²ÑÐ·Ð°Ð½!",
        "batch_setup_prompt": "ðŸ“¦ ÐÐ°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ°: Ð¡Ð´ÐµÐ»Ð°Ð¹Ñ‚Ðµ Ð±Ð¾Ñ‚Ð° Ð°Ð´Ð¼Ð¸Ð½Ð¾Ð¼ Ð² ÐºÐ°Ð½Ð°Ð»Ðµ Ð¸ Ð¿ÐµÑ€ÐµÑˆÐ»Ð¸Ñ‚Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ ÑÑŽÐ´Ð°",
        "batch_mode_activated": "Ð ÐµÐ¶Ð¸Ð¼ Ð°ÐºÑ‚Ð¸Ð²Ð¸Ñ€Ð¾Ð²Ð°Ð½!",
        "batch_change_dest": "ðŸ”„ **Ð˜Ð·Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ ÐºÐ°Ð½Ð°Ð» Ð½Ð°Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ñ**\nÐ¡Ð´ÐµÐ»Ð°Ð¹Ñ‚Ðµ Ð±Ð¾Ñ‚Ð° Ð°Ð´Ð¼Ð¸Ð½Ð¾Ð¼ Ð² Ð½Ð¾Ð²Ð¾Ð¼ ÐºÐ°Ð½Ð°Ð»Ðµ, Ð·Ð°Ñ‚ÐµÐ¼ Ð¿ÐµÑ€ÐµÑˆÐ»Ð¸Ñ‚Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ ÑÑŽÐ´Ð°.",
        "join_channel_first_alert": "Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ð¿Ñ€Ð¸ÑÐ¾ÐµÐ´Ð¸Ð½Ð¸Ñ‚ÐµÑÑŒ Ðº ÐºÐ°Ð½Ð°Ð»Ñƒ! ðŸ“¢ ÐžÐ±ÑÐ·Ð°Ñ‚ÐµÐ»ÑŒÐ½Ð¾!",
        "join_channel_first": "Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ð¿Ñ€Ð¸ÑÐ¾ÐµÐ´Ð¸Ð½Ð¸Ñ‚ÐµÑÑŒ Ðº ÐºÐ°Ð½Ð°Ð»Ñƒ! ðŸ“¢",
        "watch_timer_first": "â° Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ð¾Ñ‚ÐºÑ€Ð¾Ð¹Ñ‚Ðµ ÑÑÑ‹Ð»ÐºÑƒ Ð¸ Ð¿Ð¾ÑÐ¼Ð¾Ñ‚Ñ€Ð¸Ñ‚Ðµ 20-ÑÐµÐº Ñ‚Ð°Ð¹Ð¼ÐµÑ€!",
        "test_ad_verified": "âœ… Ð¢ÐµÑÑ‚Ð¾Ð²Ð°Ñ Ñ€ÐµÐºÐ»Ð°Ð¼Ð° Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð°! +1",
        "test_ad_verified_msg": "âœ… **Ð¢Ð•Ð¡Ð¢ÐžÐ’ÐÐ¯ Ð Ð•ÐšÐ›ÐÐœÐ ÐŸÐ ÐžÐ’Ð•Ð Ð•ÐÐ!**\nÐÐ°Ð³Ñ€Ð°Ð´Ð°: +1 Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð¿Ð¾Ð¿Ð¾Ð»Ð½ÐµÐ½Ð°!",
        "finish_timer_first": "â° Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ð·Ð°Ð²ÐµÑ€ÑˆÐ¸Ñ‚Ðµ 20-ÑÐµÐº Ñ‚Ð°Ð¹Ð¼ÐµÑ€!",
        "verified_added": "ÐŸÑ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð¾! +1 Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾",
        "resume_prompt": "âœ… ÐŸÑ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð¾! ÐŸÐ¾Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¾ +1. Ð’Ð¾Ð·Ð¾Ð±Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ?",
        "refilled_download": "âœ… ÐŸÐ¾Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¾ +1! Ð—Ð°Ð³Ñ€ÑƒÐ·Ð¸Ñ‚Ðµ ÑÐ½Ð¾Ð²Ð°.",
        "fetching_bundle": "âœ… ÐŸÑ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð¾! ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ðµ Ð¿Ð°ÐºÐµÑ‚Ð°...",
        "outdated_button": "Ð­Ñ‚Ð° ÐºÐ½Ð¾Ð¿ÐºÐ° ÑƒÑÑ‚Ð°Ñ€ÐµÐ»Ð°. ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ ÑÑÑ‹Ð»ÐºÑƒ ÑÐ½Ð¾Ð²Ð°.",
        "stopping": "ÐžÑÑ‚Ð°Ð½Ð¾Ð²ÐºÐ°...",
        "stopped": "ðŸ›‘ ÐžÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾",
        "resuming": "Ð’Ð¾Ð·Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ...",
        "checking_vault": "ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ñ…Ñ€Ð°Ð½Ð¸Ð»Ð¸Ñ‰Ð° Ð¸ Ð½Ð°Ð³Ñ€ÑƒÐ·ÐºÐ¸ ÑÐµÑ€Ð²ÐµÑ€Ð°...",
        "server_busy": "â³ **Ð¡ÐµÑ€Ð²ÐµÑ€ Ð·Ð°Ð½ÑÑ‚**\nÐÐºÑ‚Ð¸Ð²Ð½Ñ‹Ñ…: {}/{}\nÐ¡Ð²Ð¾Ð±Ð¾Ð´Ð½Ð¾: {} ÐœÐ‘\nÐžÑ‡ÐµÑ€ÐµÐ´ÑŒ: #{}\nÐ—Ð°Ð¿ÑƒÑÑ‚Ð¸Ñ‚ÑÑ Ð°Ð²Ñ‚Ð¾Ð¼Ð°Ñ‚Ð¸Ñ‡ÐµÑÐºÐ¸!",
        "simulated": "ðŸ›  Ð¡Ð¸Ð¼ÑƒÐ»Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¾! Ð¢ÐµÐ¿ÐµÑ€ÑŒ Ð½Ð°Ð¶Ð¼Ð¸Ñ‚Ðµ ÐŸÑ€Ð¾Ð²ÐµÑ€Ð¸Ñ‚ÑŒ Ð¸ Ð¿Ð¾Ð»ÑƒÑ‡Ð¸Ñ‚ÑŒ +1",
        "server_unreachable": "âŒ Ð¡ÐµÑ€Ð²ÐµÑ€ Ð½ÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿ÐµÐ½",
        "monetag_failed_twice": "Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ð·Ð°Ð²ÐµÑ€ÑˆÐ¸Ñ‚Ðµ Ð´Ð²Ðµ Ð½ÐµÑƒÐ´Ð°Ñ‡Ð½Ñ‹Ðµ Ð¿Ð¾Ð¿Ñ‹Ñ‚ÐºÐ¸ Monetag.",
        "monetag_fallback_prompt": "ðŸŒ Monetag Ð½Ðµ ÑÑ€Ð°Ð±Ð¾Ñ‚Ð°Ð» Ð´Ð²Ð°Ð¶Ð´Ñ‹. ÐŸÑ€Ð¾Ð´Ð¾Ð»Ð¶Ð¸Ñ‚ÑŒ Ñ Adsterra:",
        "adsterra_ready": "Ð ÐµÐ·ÐµÑ€Ð²Ð½Ñ‹Ð¹ Ð²Ð°Ñ€Ð¸Ð°Ð½Ñ‚ Adsterra Ð³Ð¾Ñ‚Ð¾Ð²",
        "finish_monetag": "ðŸ“º Ð—Ð°Ð²ÐµÑ€ÑˆÐ¸Ñ‚Ðµ Ñ€ÐµÐºÐ»Ð°Ð¼Ñƒ Monetag Ð² Mini App, Ð·Ð°Ñ‚ÐµÐ¼ Ð¿Ñ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ ÑÐ½Ð¾Ð²Ð°.",
        "monetag_failed_use_adsterra": "Monetag Ð½Ðµ ÑÑ€Ð°Ð±Ð¾Ñ‚Ð°Ð» Ð´Ð²Ð°Ð¶Ð´Ñ‹. Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹Ñ‚Ðµ Ñ€ÐµÐ·ÐµÑ€Ð²Ð½Ñ‹Ð¹ Ð²Ð°Ñ€Ð¸Ð°Ð½Ñ‚ Adsterra Ð½Ð¸Ð¶Ðµ.",
        "ad_link_expired": "Ð¡Ñ€Ð¾Ðº Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ñ Ñ€ÐµÐºÐ»Ð°Ð¼Ð½Ð¾Ð¹ ÑÑÑ‹Ð»ÐºÐ¸ Ð¸ÑÑ‚ÐµÐº. ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ ÑÑÑ‹Ð»ÐºÑƒ ÑÐ½Ð¾Ð²Ð°.",
        "ad_verified_added": "âœ… Ð ÐµÐºÐ»Ð°Ð¼Ð° Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð°! +{} Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾",
        "test_ad_completed": "âœ… Ð¢Ð•Ð¡Ð¢ÐžÐ’ÐÐ¯ Ð Ð•ÐšÐ›ÐÐœÐ ÐŸÐ ÐžÐ’Ð•Ð Ð•ÐÐ\nÐÐ°Ð³Ñ€Ð°Ð´Ð° Ð½Ð°Ñ‡Ð¸ÑÐ»ÐµÐ½Ð°: +{} Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ°.",
        "sponsor_viewed": "âœ… Ð¡Ð¿Ð¾Ð½ÑÐ¾Ñ€ Ð¿Ñ€Ð¾ÑÐ¼Ð¾Ñ‚Ñ€ÐµÐ½! +{} Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾",
        "refilled_send_again": "âœ… ÐŸÐ¾Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¾ +{}! ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ ÑÑÑ‹Ð»ÐºÑƒ ÑÐ½Ð¾Ð²Ð°.",
        "queued": "â³ Ð’ Ð¾Ñ‡ÐµÑ€ÐµÐ´Ð¸ #{}",
        "banned": "ðŸš« Ð’Ñ‹ Ð·Ð°Ð±Ð»Ð¾ÐºÐ¸Ñ€Ð¾Ð²Ð°Ð½Ñ‹.",
        "no_links": "âŒ Ð¡ÑÑ‹Ð»ÐºÐ¸ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ñ‹.",
        "batch_count": "ðŸ“¦ ÐŸÐ°ÐºÐµÑ‚ {} ÑÑÑ‹Ð»Ð¾Ðº",
        "restore_invalid_json": "âŒ ÐžÑˆÐ¸Ð±ÐºÐ° Ð²Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ñ: **{}** Ð½Ðµ ÑÐ²Ð»ÑÐµÑ‚ÑÑ Ð´Ð¾Ð¿ÑƒÑÑ‚Ð¸Ð¼Ñ‹Ð¼ JSON.",
        "restore_failed": "âŒ ÐžÑˆÐ¸Ð±ÐºÐ° Ð²Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ñ: {}",
        "restore_success": "âœ… **Ð’Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ ÑƒÑÐ¿ÐµÑˆÐ½Ð¾!**\nÐ¤Ð°Ð¹Ð»: **{}**\nÐ’Ð¾ÑÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾ **{}** Ð·Ð°Ð¿Ð¸ÑÐµÐ¹.",
        "admin_edit_welcome_prompt": "âœï¸ ÐžÑ‚Ð¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ð½Ð¾Ð²Ð¾Ðµ Ð¿Ñ€Ð¸Ð²ÐµÑ‚ÑÑ‚Ð²ÐµÐ½Ð½Ð¾Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ. Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹Ñ‚Ðµ `{bot_name}` Ð´Ð»Ñ Ð¸Ð¼ÐµÐ½Ð¸ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ Ð±Ð¾Ñ‚Ð°.",
        "admin_welcome_updated": "âœ… ÐŸÑ€Ð¸Ð²ÐµÑ‚ÑÑ‚Ð²ÐµÐ½Ð½Ð¾Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾!",
        "menu_edit_welcome": "âœï¸ Ð˜Ð·Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ Ð¿Ñ€Ð¸Ð²ÐµÑ‚ÑÑ‚Ð²ÐµÐ½Ð½Ð¾Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ",
        "cached_instant_video": "âš¡ ÐœÐ³Ð½Ð¾Ð²ÐµÐ½Ð½Ñ‹Ð¹ ÐºÑÑˆ [{}] {} {}",
        "cached_instant_audio": "âš¡ **ÐœÐ³Ð½Ð¾Ð²ÐµÐ½Ð½Ñ‹Ð¹ ÐºÑÑˆ** `{}`",
        "cached_instant_image": "âš¡ **ÐœÐ³Ð½Ð¾Ð²ÐµÐ½Ð½Ñ‹Ð¹ ÐºÑÑˆ** `{}`",
        "auto_delete_9m": "â³ ÐÐ²Ñ‚Ð¾ÑƒÐ´Ð°Ð»ÐµÐ½Ð¸Ðµ Ñ‡ÐµÑ€ÐµÐ· 9 Ð¼Ð¸Ð½",
        "download_success": "âœ… Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° ÑƒÑÐ¿ÐµÑˆÐ½Ð°!"
    },
    "pt": {
        "welcome": "ðŸš€ **BEM-VINDO AO MICHAELBBC VAULT - BAIXADOR DE MÃDIA COMPLETO!**\n\nðŸ”¥ O QUE POSSO FAZER:\nðŸŽ¬ VÃDEOS HD Sem Marca D'Ã¡gua!\nðŸŽµ ÃUDIO MP3 192kbps!\n??ï¸ IMAGENS ExtraÃ§Ã£o TOTAL!\nðŸ“ LEGENDAS Auto!\nðŸ“¦ LOTES 100+ Links!\nâš¡ CACHE 1 Seg!\nðŸ’Ž COFRE Para Sempre!\nðŸ“¤ ENVIAR ARQUIVOS!\nðŸ”— ARQUIVO-PARA-LINK: Crie links compartilhÃ¡veis!\n\nðŸ‘‰ COLE UM LINK PARA COMEÃ‡AR! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ VÃ­deo (MP4)", "btn_audio": "ðŸŽµ Ãudio (MP3)", "btn_image": "ðŸ–¼ï¸ Imagens", "btn_sub": "ðŸ“ Legendas (SRT)",
        "ask_format": "ðŸ‘‡ **INCRÃVEL! Qual formato vocÃª quer? Escolha abaixo!**",
        "fetching": "ðŸ“¥ **Buscando seu {}... Aguarde! â³âœ¨**",
        "error_generic": "âŒ Ops! Falhou! ðŸ˜¢ Link privado/bloqueado. Tente um link pÃºblico!",
        "error_50mb": "âŒ Muito grande! ðŸ˜… Este vÃ­deo tem mais de 300MB. Tente um mais curto!", 
        "error_no_img": "âŒ Nenhuma imagem encontrada! ðŸ˜¢ Tente outro link!",
        "images_received": "â³ **{} Imagens recebidas.**",
        "select_lang": "ðŸŒ Selecione seu idioma! Escolha abaixo! ðŸ‘‡", 
        "lang_set": "âœ… Idioma definido! Aproveite! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Lote Detectado ({} links)**\nQual formato?",
        "batch_dest": "ðŸ“¦ **Para onde enviar?**",
        "btn_chat": "ðŸ“¥ No Chat", "btn_chan": "ðŸ“¢ Para o Canal",
        "limit_reached": "âš ï¸ **Limite Atingido!** VocÃª usou 4 GRÃTIS! Assista a um anÃºncio de 20s â†’ Ganhe +1 download!",
        "refill_btn": "ðŸ”“ Abrir Link e Recarregar +1",
        "join_btn": "ðŸ“¢ Entrar no Canal", "check_btn": "ðŸ’œ Verificar Saldo",
        "limit_batch": "âš ï¸ **Limite do Lote Atingido em {} de {}**\nAssista a um anÃºncio de 20s â†’ +1 download para continuar.",
        "batch_start": "ðŸ“¦ **Lote Iniciado:** {} **{} arquivos**\nâ³ Processando...",
        "batch_done": "ðŸ **ConcluÃ­do!** âœ… {} âŒ {}\nðŸ“¥ {} arquivos aqui.",
        "batch_done_chan": "ðŸ **ConcluÃ­do!** âœ… {} âŒ {}\nðŸ“¢ {} arquivos encaminhados!",
        "dl_video": "ðŸ“¥ Baixando vÃ­deo...", "dl_audio": "ðŸ“¥ Extraindo Ã¡udio...", "dl_image": "ðŸ“¥ Extraindo imagens...", "dl_sub": "ðŸ“¥ Buscando legendas...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Bloqueado/privado", "failed_generic": "âŒ Falhou",
        "menu_lang": "ðŸŒ Idioma", "menu_stats": "ðŸ“Š Minhas EstatÃ­sticas", "menu_help": "ðŸ’¬ Suporte / FAQ", "menu_join": "ðŸ“¢ Entrar no Canal",
        "menu_uploads": "ðŸ¿ Envios de FÃ£s", "menu_upload": "ðŸ“¤ Enviar Arquivo",
        "admin_upload_prompt": "ðŸ“‚ **Caixa de Entrada de Envios de FÃ£s**",
        "user_upload_prompt": "ðŸ“¤ **Enviar Arquivo**\nEnvie vÃ­deo/imagem/arquivo para o Admin. Limite 5/24h.",
        "upload_success_user": "âœ… Enviado para o Admin!",
        "upload_limit_reached": "âš ï¸ Limite de envios 5/24h atingido.",
        "no_uploads": "ðŸ“­ Nenhum envio ainda.",
        "stats_msg": "ðŸ“Š **Suas EstatÃ­sticas:**\nâ€¢ Downloads Restantes: {}\nâ€¢ Lotes Restantes: {}",
        "change_channel_prompt": "ðŸ”„ **Alterar Canal de Lotes**\n1. Certifique-se de que sou admin no novo canal.\n2. Encaminhe qualquer mensagem desse canal para cÃ¡.",
        "disk_config_prompt": "ðŸ’¾ **Config de Disco**\nMÃ­nimo de disco livre atual: **{}MB**\nPara alterar: `/setdisk <valor>`",
        "mtproto_config_prompt": "âš¡ **Config MTProto**\nMax de upload atual: **{}MB**\nPara alterar: `/setmtproto <valor>`",
        "free_panel_prompt": "ðŸ“¦ DOWNLOADS GRÃTIS\nGrÃ¡tis atuais por dia: {}",
        "reward_panel_prompt": "ðŸŽ PAINEL DE RECOMPENSAS\nAtual: +{} download por anÃºncio de 20s",
        "ad_panel_prompt": "âš™ï¸ Painel de AnÃºncios\nAtual: {}",
        "password_saved": "ðŸ” Senha salva.",
        "password_too_long": "A senha deve ter 64 caracteres ou menos.",
        "file_to_link_prompt": "ðŸ”— **Arquivo-para-Link**\nEnvie o(s) arquivo(s) que deseja compartilhar.",
        "link_invalid_expired": "âŒ Este link Ã© invÃ¡lido ou expirou.",
        "link_limit_reached": "â›” Este link atingiu seu limite de uso.",
        "link_password_protected": "ðŸ” Este link estÃ¡ protegido por senha. Envie a senha.",
        "files_sent": "âœ… Seus arquivos foram enviados.",
        "file_added": "ðŸ“¥ Arquivo #{} adicionado. Envie mais ou toque em Criar Link.",
        "fl_cancelled": "Arquivo-para-Link cancelado",
        "fl_start_again": "Inicie Arquivo-para-Link novamente com /filetolink",
        "fl_choose_expiry": "Escolha a expiraÃ§Ã£o do link:",
        "fl_expiry_updated": "ExpiraÃ§Ã£o atualizada",
        "fl_choose_max_uses": "Escolha o mÃ¡ximo de entregas bem-sucedidas:",
        "fl_uses_updated": "Limite de uso atualizado",
        "fl_set_password": "Envie uma senha ou /clearpassword para remover.",
        "fl_link_created": "Link criado",
        "fl_link_ready": "ðŸ”— Seu link estÃ¡ pronto:\n{}\nArquivos: {}\nCusto: 1 download diÃ¡rio grÃ¡tis",
        "fl_daily_limit": "Limite diÃ¡rio grÃ¡tis atingido. Assista a um anÃºncio para ganhar mais.",
        "fl_ad_busy": "âš ï¸ Servidor de anÃºncios ocupado.",
        "admin_skipped": "âœ… Ignorado!",
        "admin_bypassed": "âœ… Ignorado",
        "free_set": "âœ… GrÃ¡tis definido para {}!",
        "free_updated": "âœ… Downloads GrÃ¡tis atualizados para {}!",
        "reward_set": "âœ… Recompensa definida para +{}!",
        "reward_updated": "âœ… Recompensa atualizada para +{}!",
        "mode_updated": "âœ… Modo: {}",
        "support_opened": "âœï¸ Envie mensagem/foto/vÃ­deo/arquivo abaixo.",
        "admin_reply_mode": "âœï¸ Responder a {}:",
        "user_reply_mode": "âœï¸ Digite o acompanhamento abaixo",
        "support_closed": "ðŸ”’ Fechado",
        "drop_cancelled": "âŒ Cancelado",
        "drop_no_items": "âš ï¸ Sem itens!",
        "drop_timer_set": "{} definido!",
        "drop_broadcasting": "ðŸš€ Transmitindo {} itens para {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nAuto-exclui em {}\nToque para reivindicar:",
        "drop_done": "âœ… TransmissÃ£o feita para {}",
        "age_expired": "â³ Expirado!",
        "age_claimed": "âŒ JÃ¡ reivindicado!",
        "age_verified": "Verificado!",
        "age_denied": "âŒ Negado. Deve ser 18+",
        "lang_updated": "Atualizado!",
        "batch_expired": "Expirado",
        "batch_loading": "Carregando...",
        "batch_no_channel": "Nenhum canal vinculado!",
        "batch_setup_prompt": "ðŸ“¦ ConfiguraÃ§Ã£o: Torne o bot admin no canal e encaminhe uma mensagem aqui",
        "batch_mode_activated": "Modo ativado!",
        "batch_change_dest": "ðŸ”„ **Alterar Canal de Destino**\nTorne o bot admin no novo canal, depois encaminhe uma mensagem aqui.",
        "join_channel_first_alert": "Entre no canal primeiro! ðŸ“¢ Deve entrar!",
        "join_channel_first": "Entre no canal primeiro! ðŸ“¢",
        "watch_timer_first": "â° Abra o link e assista ao temporizador de 20s primeiro!",
        "test_ad_verified": "âœ… AnÃºncio de Teste Verificado! +1",
        "test_ad_verified_msg": "âœ… **ANÃšNCIO DE TESTE VERIFICADO!**\nRecompensa: +1 download recarregado!",
        "finish_timer_first": "â° Termine o temporizador de 20s primeiro!",
        "verified_added": "Verificado! +1 adicionado",
        "resume_prompt": "âœ… Verificado! Recarregado +1. Retomar?",
        "refilled_download": "âœ… Recarregado +1! Baixe novamente.",
        "fetching_bundle": "âœ… Verificado! Buscando pacote...",
        "outdated_button": "Este botÃ£o estÃ¡ desatualizado. Envie seu link novamente.",
        "stopping": "Parando...",
        "stopped": "ðŸ›‘ Parado",
        "resuming": "Retomando...",
        "checking_vault": "Verificando cofre e carga do servidor...",
        "server_busy": "â³ **Servidor Ocupado**\nAtivos: {}/{}\nLivre: {}MB\nFila: #{}\nIniciarÃ¡ auto!",
        "simulated": "ðŸ›  Simulado! Agora toque em Verificar e Obter +1",
        "server_unreachable": "âŒ Servidor inacessÃ­vel",
        "monetag_failed_twice": "Complete duas tentativas falhas de Monetag primeiro.",
        "monetag_fallback_prompt": "ðŸŒ Monetag falhou duas vezes. Continue com Adsterra:",
        "adsterra_ready": "Fallback de Adsterra pronto",
        "finish_monetag": "ðŸ“º Termine o anÃºncio Monetag no Mini App, depois verifique.",
        "monetag_failed_use_adsterra": "Monetag falhou duas vezes. Use o fallback de Adsterra abaixo.",
        "ad_link_expired": "Link de anÃºncio expirado. Envie seu link novamente.",
        "ad_verified_added": "âœ… AnÃºncio verificado! +{} adicionado",
        "test_ad_completed": "âœ… ANÃšNCIO DE TESTE VERIFICADO\nRecompensa creditada: +{} download.",
        "sponsor_viewed": "âœ… Patrocinador visto! +{} adicionado",
        "refilled_send_again": "âœ… Recarregado +{}! Envie seu link novamente.",
        "queued": "â³ Na fila #{}",
        "banned": "ðŸš« VocÃª estÃ¡ banido.",
        "no_links": "âŒ Nenhum link encontrado.",
        "batch_count": "ðŸ“¦ Lote {} links",
        "restore_invalid_json": "âŒ Falha na restauraÃ§Ã£o: **{}** nÃ£o Ã© JSON vÃ¡lido.",
        "restore_failed": "âŒ Falha na restauraÃ§Ã£o: {}",
        "restore_success": "âœ… **RestauraÃ§Ã£o Bem-sucedida!**\nArquivo: **{}**\nRestauradas **{}** entradas.",
        "admin_edit_welcome_prompt": "âœï¸ Envie a nova Mensagem de Boas-vindas. Use `{bot_name}` para o nome de usuÃ¡rio.",
        "admin_welcome_updated": "âœ… Mensagem de boas-vindas atualizada!",
        "menu_edit_welcome": "âœï¸ Editar Mensagem de Boas-vindas",
        "cached_instant_video": "âš¡ Cache InstantÃ¢neo [{}] {} {}",
        "cached_instant_audio": "âš¡ **Cache InstantÃ¢neo** `{}`",
        "cached_instant_image": "âš¡ **Cache InstantÃ¢neo** `{}`",
        "auto_delete_9m": "â³ Auto-exclui em 9 mins",
        "download_success": "âœ… Download bem-sucedido!"
    },
    "id": {
        "welcome": "ðŸš€ **SELAMAT DATANG DI MICHAELBBC VAULT - PENGUNDUH MEDIA LENGKAP!**\n\nðŸ”¥ APA YANG BISA SAYA LAKUKAN:\nðŸŽ¬ VIDEO HD Tanpa Watermark!\nðŸŽµ AUDIO MP3 192kbps!\nðŸ–¼ï¸ GAMBAR Ekstraksi SEMUA!\nðŸ“ SUBTITLE Otomatis!\nðŸ“¦ BATCH 100+ Link!\nâš¡ CACHE 1 Detik!\nðŸ’Ž BRANKAS Selamanya!\nðŸ“¤ UNGGAH FILE!\nðŸ”— FILE-KE-LINK: Buat link yang bisa dibagikan!\n\nðŸ‘‰ TEMPEL LINK UNTUK MEMULAI! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ Video (MP4)", "btn_audio": "ðŸŽµ Audio (MP3)", "btn_image": "ðŸ–¼ï¸ Gambar", "btn_sub": "ðŸ“ Subtitle (SRT)",
        "ask_format": "ðŸ‘‡ **KEREN! Format apa yang Anda inginkan? Pilih di bawah!**",
        "fetching": "ðŸ“¥ **Mengambil {} Anda... Tunggu sebentar! â³âœ¨**",
        "error_generic": "âŒ Ups! Gagal! ðŸ˜¢ Link pribadi/diblokir. Coba link publik!",
        "error_50mb": "âŒ Terlalu besar! ðŸ˜… Video ini lebih dari 300MB. Coba yang lebih pendek!", 
        "error_no_img": "âŒ Tidak ada gambar ditemukan! ðŸ˜¢ Coba link lain!",
        "images_received": "â³ **{} Gambar diterima.**",
        "select_lang": "ðŸŒ Pilih bahasa Anda! Pilih di bawah! ðŸ‘‡", 
        "lang_set": "âœ… Bahasa diatur! Nikmati! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Batch Terdeteksi ({} link)**\nFormat apa?",
        "batch_dest": "ðŸ“¦ **Kirim ke mana?**",
        "btn_chat": "ðŸ“¥ Di Chat", "btn_chan": "ðŸ“¢ Ke Channel",
        "limit_reached": "âš ï¸ **Batas Tercapai!** Anda menggunakan 4 GRATIS! Tonton iklan 20d â†’ Dapatkan +1 unduhan!",
        "refill_btn": "ðŸ”“ Buka Link & Isi Ulang +1",
        "join_btn": "ðŸ“¢ Gabung Channel", "check_btn": "ðŸ’œ Cek Saldo",
        "limit_batch": "âš ï¸ **Batas Batch Tercapai pada {} dari {}**\nTonton iklan 20d â†’ +1 unduhan untuk melanjutkan.",
        "batch_start": "ðŸ“¦ **Batch Dimulai:** {} **{} file**\nâ³ Memproses...",
        "batch_done": "ðŸ **Selesai!** âœ… {} âŒ {}\nðŸ“¥ {} file di sini.",
        "batch_done_chan": "ðŸ **Selesai!** âœ… {} âŒ {}\nðŸ“¢ {} file diteruskan!",
        "dl_video": "ðŸ“¥ Mengunduh video...", "dl_audio": "ðŸ“¥ Mengekstrak audio...", "dl_image": "ðŸ“¥ Mengekstrak gambar...", "dl_sub": "ðŸ“¥ Mengambil subtitle...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Diblokir/pribadi", "failed_generic": "âŒ Gagal",
        "menu_lang": "ðŸŒ Bahasa", "menu_stats": "ðŸ“Š Statistik Saya", "menu_help": "ðŸ’¬ Dukungan / FAQ", "menu_join": "ðŸ“¢ Gabung Channel",
        "menu_uploads": "ðŸ¿ Unggahan Penggemar", "menu_upload": "ðŸ“¤ Unggah File",
        "admin_upload_prompt": "ðŸ“‚ **Kotak Masuk Unggahan Penggemar**",
        "user_upload_prompt": "ðŸ“¤ **Unggah File**\nKirim video/gambar/file ke Admin. Batas 5/24jam.",
        "upload_success_user": "âœ… Terkirim ke Admin!",
        "upload_limit_reached": "âš ï¸ Batas unggahan 5/24jam tercapai.",
        "no_uploads": "ðŸ“­ Belum ada unggahan.",
        "stats_msg": "ðŸ“Š **Statistik Anda:**\nâ€¢ Sisa Unduhan: {}\nâ€¢ Sisa Batch: {}",
        "change_channel_prompt": "ðŸ”„ **Ubah Channel Batch**\n1. Pastikan saya adalah admin di channel baru.\n2. Teruskan pesan apa pun dari channel tersebut ke sini.",
        "disk_config_prompt": "ðŸ’¾ **Konfigurasi Disk**\nMin disk bebas saat ini: **{}MB**\nUntuk mengubah: `/setdisk <nilai>`",
        "mtproto_config_prompt": "âš¡ **Konfigurasi MTProto**\nMax unggah saat ini: **{}MB**\nUntuk mengubah: `/setmtproto <nilai>`",
        "free_panel_prompt": "ðŸ“¦ UNDUHAN GRATIS\nGratis saat ini per hari: {}",
        "reward_panel_prompt": "ðŸŽ PANEL HADIAH\nSaat ini: +{} unduhan per iklan 20d",
        "ad_panel_prompt": "âš™ï¸ Panel Iklan\nSaat ini: {}",
        "password_saved": "ðŸ” Kata sandi disimpan.",
        "password_too_long": "Kata sandi harus 64 karakter atau kurang.",
        "file_to_link_prompt": "ðŸ”— **File-ke-Link**\nKirim file yang ingin Anda bagikan.",
        "link_invalid_expired": "âŒ Link ini tidak valid atau kedaluwarsa.",
        "link_limit_reached": "â›” Link ini mencapai batas penggunaan.",
        "link_password_protected": "ðŸ” Link ini dilindungi kata sandi. Kirim kata sandi.",
        "files_sent": "âœ… File Anda telah dikirim.",
        "file_added": "ðŸ“¥ File #{} ditambahkan. Kirim lebih banyak, atau ketuk Buat Link.",
        "fl_cancelled": "File-ke-Link dibatalkan",
        "fl_start_again": "Mulai File-ke-Link lagi dengan /filetolink",
        "fl_choose_expiry": "Pilih kedaluwarsa link:",
        "fl_expiry_updated": "Kedaluwarsa diperbarui",
        "fl_choose_max_uses": "Pilih max pengiriman berhasil:",
        "fl_uses_updated": "Batas penggunaan diperbarui",
        "fl_set_password": "Kirim kata sandi, atau /clearpassword untuk menghapus.",
        "fl_link_created": "Link dibuat",
        "fl_link_ready": "ðŸ”— Link Anda siap:\n{}\nFile: {}\nBiaya: 1 unduhan harian gratis",
        "fl_daily_limit": "Batas harian gratis tercapai. Tonton iklan untuk mendapatkan lebih banyak.",
        "fl_ad_busy": "âš ï¸ Server iklan sibuk.",
        "admin_skipped": "âœ… Dilewati!",
        "admin_bypassed": "âœ… Dilewati",
        "free_set": "âœ… Gratis diatur ke {}!",
        "free_updated": "âœ… Unduhan Gratis diperbarui ke {}!",
        "reward_set": "âœ… Hadiah diatur ke +{}!",
        "reward_updated": "âœ… Hadiah diperbarui ke +{}!",
        "mode_updated": "âœ… Mode: {}",
        "support_opened": "âœï¸ Kirim pesan/foto/video/file di bawah.",
        "admin_reply_mode": "âœï¸ Balas ke {}:",
        "user_reply_mode": "âœï¸ Ketik tindak lanjut di bawah",
        "support_closed": "ðŸ”’ Ditutup",
        "drop_cancelled": "âŒ Dibatalkan",
        "drop_no_items": "âš ï¸ Tidak ada item!",
        "drop_timer_set": "{} diatur!",
        "drop_broadcasting": "ðŸš€ Menyiarakan {} item ke {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nHapus otomatis dalam {}\nKetuk untuk klaim:",
        "drop_done": "âœ… Siaran selesai ke {}",
        "age_expired": "â³ Kedaluwarsa!",
        "age_claimed": "âŒ Sudah diklaim!",
        "age_verified": "Terverifikasi!",
        "age_denied": "âŒ Ditolak. Harus 18+",
        "lang_updated": "Diperbarui!",
        "batch_expired": "Kedaluwarsa",
        "batch_loading": "Memuat...",
        "batch_no_channel": "Tidak ada channel yang ditautkan!",
        "batch_setup_prompt": "ðŸ“¦ Pengaturan: Jadikan bot admin di channel dan teruskan pesan ke sini",
        "batch_mode_activated": "Mode diaktifkan!",
        "batch_change_dest": "ðŸ”„ **Ubah Channel Tujuan**\nJadikan bot admin di channel baru, lalu teruskan pesan ke sini.",
        "join_channel_first_alert": "Gabung channel dulu! ðŸ“¢ Wajib gabung!",
        "join_channel_first": "Gabung channel dulu! ðŸ“¢",
        "watch_timer_first": "â° Buka link dan tonton timer 20d dulu!",
        "test_ad_verified": "âœ… Iklan Uji Terverifikasi! +1",
        "test_ad_verified_msg": "âœ… **IKLAN UJI TERVERIFIKASI!**\nHadiah: +1 unduhan diisi ulang!",
        "finish_timer_first": "â° Selesaikan timer 20d dulu!",
        "verified_added": "Terverifikasi! +1 ditambahkan",
        "resume_prompt": "âœ… Terverifikasi! Diisi ulang +1. Lanjutkan?",
        "refilled_download": "âœ… Diisi ulang +1! Unduh lagi.",
        "fetching_bundle": "âœ… Terverifikasi! Mengambil paket...",
        "outdated_button": "Tombol ini kedaluwarsa. Kirim link Anda lagi.",
        "stopping": "Menghentikan...",
        "stopped": "ðŸ›‘ Berhenti",
        "resuming": "Melanjutkan...",
        "checking_vault": "Memeriksa brankas & beban server...",
        "server_busy": "â³ **Server Sibuk**\nAktif: {}/{}\nBebas: {}MB\nAntrian: #{}\nAkan mulai otomatis!",
        "simulated": "ðŸ›  Disimulasikan! Sekarang ketuk Periksa & Dapatkan +1",
        "server_unreachable": "âŒ Server tidak dapat dijangkau",
        "monetag_failed_twice": "Selesaikan dua upaya Monetag yang gagal terlebih dahulu.",
        "monetag_fallback_prompt": "ðŸŒ Monetag gagal dua kali. Lanjutkan dengan Adsterra:",
        "adsterra_ready": "Fallback Adsterra siap",
        "finish_monetag": "ðŸ“º Selesaikan iklan Monetag di Mini App, lalu periksa lagi.",
        "monetag_failed_use_adsterra": "Monetag gagal dua kali. Gunakan fallback Adsterra di bawah.",
        "ad_link_expired": "Link iklan kedaluwarsa. Kirim link Anda lagi.",
        "ad_verified_added": "âœ… Iklan terverifikasi! +{} ditambahkan",
        "test_ad_completed": "âœ… IKLAN UJI TERVERIFIKASI\nHadiah dikreditkan: +{} unduhan.",
        "sponsor_viewed": "âœ… Sponsor dilihat! +{} ditambahkan",
        "refilled_send_again": "âœ… Diisi ulang +{}! Kirim link Anda lagi.",
        "queued": "â³ Dalam antrian #{}",
        "banned": "ðŸš« Anda dibanned.",
        "no_links": "âŒ Tidak ada link ditemukan.",
        "batch_count": "ðŸ“¦ Batch {} link",
        "restore_invalid_json": "âŒ Gagal memulihkan: **{}** bukan JSON yang valid.",
        "restore_failed": "âŒ Gagal memulihkan: {}",
        "restore_success": "âœ… **Pemulihan Berhasil!**\nFile: **{}**\nDipulihkan **{}** entri.",
        "admin_edit_welcome_prompt": "âœï¸ Kirim Pesan Selamat Datang baru. Gunakan `{bot_name}` untuk username bot.",
        "admin_welcome_updated": "âœ… Pesan selamat datang diperbarui!",
        "menu_edit_welcome": "âœï¸ Edit Pesan Selamat Datang",
        "cached_instant_video": "âš¡ Cache Instan [{}] {} {}",
        "cached_instant_audio": "âš¡ **Cache Instan** `{}`",
        "cached_instant_image": "âš¡ **Cache Instan** `{}`",
        "auto_delete_9m": "â³ Hapus otomatis dalam 9 menit",
        "download_success": "âœ… Unduhan berhasil!"
    },
    "fr": {
        "welcome": "ðŸš€ **BIENVENUE SUR MICHAELBBC VAULT - TÃ‰LÃ‰CHARGEUR DE MÃ‰DIAS COMPLET!**\n\nðŸ”¥ CE QUE JE PEUX FAIRE:\nðŸŽ¬ VIDÃ‰OS HD Sans Filigrane!\nðŸŽµ AUDIO MP3 192kbps!\nðŸ–¼ï¸ IMAGES Extraction TOTALE!\nðŸ“ SOUS-TITRES Auto!\nðŸ“¦ LOTS 100+ Liens!\nâš¡ CACHE 1 Sec!\nðŸ’Ž COFFRE Pour Toujours!\nðŸ“¤ TÃ‰LÃ‰VERSER DES FICHIERS!\nðŸ”— FICHIER-VERS-LIEN: CrÃ©ez des liens partageables!\n\nðŸ‘‰ COLLEZ UN LIEN POUR COMMENCER! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ VidÃ©o (MP4)", "btn_audio": "ðŸŽµ Audio (MP3)", "btn_image": "ðŸ–¼ï¸ Images", "btn_sub": "ðŸ“ Sous-titres (SRT)",
        "ask_format": "ðŸ‘‡ **GÃ‰NIAL! Quel format voulez-vous? Choisissez ci-dessous!**",
        "fetching": "ðŸ“¥ **RÃ©cupÃ©ration de votre {}... Patientez! â³âœ¨**",
        "error_generic": "âŒ Oups! Ã‰chec! ðŸ˜¢ Lien privÃ©/bloquÃ©. Essayez un lien public!",
        "error_50mb": "âŒ Trop grand! ðŸ˜… Cette vidÃ©o dÃ©passe 300 Mo. Essayez une plus courte!", 
        "error_no_img": "âŒ Aucune image trouvÃ©e! ðŸ˜¢ Essayez un autre lien!",
        "images_received": "â³ **{} Images reÃ§ues.**",
        "select_lang": "ðŸŒ SÃ©lectionnez votre langue! Choisissez ci-dessous! ðŸ‘‡", 
        "lang_set": "âœ… Langue dÃ©finie! Profitez-en! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Lot DÃ©tectÃ© ({} liens)**\nQuel format?",
        "batch_dest": "ðŸ“¦ **OÃ¹ envoyer?**",
        "btn_chat": "ðŸ“¥ Dans le Chat", "btn_chan": "ðŸ“¢ Vers le Canal",
        "limit_reached": "âš ï¸ **Limite Atteinte!** Vous avez utilisÃ© 4 GRATUITS! Regardez une pub de 20s â†’ Obtenez +1 tÃ©lÃ©chargement!",
        "refill_btn": "ðŸ”“ Ouvrir le Lien et Recharger +1",
        "join_btn": "ðŸ“¢ Rejoindre le Canal", "check_btn": "ðŸ’œ VÃ©rifier le Solde",
        "limit_batch": "âš ï¸ **Limite du Lot Atteinte Ã  {} sur {}**\nRegardez une pub de 20s â†’ +1 tÃ©lÃ©chargement pour continuer.",
        "batch_start": "ðŸ“¦ **Lot DÃ©marrÃ©:** {} **{} fichiers**\nâ³ Traitement...",
        "batch_done": "ðŸ **TerminÃ©!** âœ… {} âŒ {}\nðŸ“¥ {} fichiers ici.",
        "batch_done_chan": "ðŸ **TerminÃ©!** âœ… {} âŒ {}\nðŸ“¢ {} fichiers transfÃ©rÃ©s!",
        "dl_video": "ðŸ“¥ TÃ©lÃ©chargement de la vidÃ©o...", "dl_audio": "ðŸ“¥ Extraction de l'audio...", "dl_image": "ðŸ“¥ Extraction des images...", "dl_sub": "ðŸ“¥ RÃ©cupÃ©ration des sous-titres...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ BloquÃ©/privÃ©", "failed_generic": "âŒ Ã‰chec",
        "menu_lang": "ðŸŒ Langue", "menu_stats": "ðŸ“Š Mes Statistiques", "menu_help": "ðŸ’¬ Support / FAQ", "menu_join": "ðŸ“¢ Rejoindre le Canal",
        "menu_uploads": "ðŸ¿ TÃ©lÃ©versements des Fans", "menu_upload": "ðŸ“¤ TÃ©lÃ©verser un Fichier",
        "admin_upload_prompt": "ðŸ“‚ **BoÃ®te de RÃ©ception des TÃ©lÃ©versements des Fans**",
        "user_upload_prompt": "ðŸ“¤ **TÃ©lÃ©verser un Fichier**\nEnvoyez vidÃ©o/image/fichier Ã  l'Admin. Limite 5/24h.",
        "upload_success_user": "âœ… EnvoyÃ© Ã  l'Admin!",
        "upload_limit_reached": "âš ï¸ Limite de tÃ©lÃ©versement 5/24h atteinte.",
        "no_uploads": "ðŸ“­ Aucun tÃ©lÃ©versement pour le moment.",
        "stats_msg": "ðŸ“Š **Vos Statistiques:**\nâ€¢ TÃ©lÃ©chargements Restants: {}\nâ€¢ Lots Restants: {}",
        "change_channel_prompt": "ðŸ”„ **Changer de Canal pour les Lots**\n1. Assurez-vous que je suis admin dans le nouveau canal.\n2. TransfÃ©rez n'importe quel message de ce canal ici.",
        "disk_config_prompt": "ðŸ’¾ **Config du Disque**\nMin disque libre actuel: **{} Mo**\nPour changer: `/setdisk <valeur>`",
        "mtproto_config_prompt": "âš¡ **Config MTProto**\nMax tÃ©lÃ©versement actuel: **{} Mo**\nPour changer: `/setmtproto <valeur>`",
        "free_panel_prompt": "ðŸ“¦ TÃ‰LÃ‰CHARGEMENTS GRATUITS\nGratuits actuels par jour: {}",
        "reward_panel_prompt": "ðŸŽ PANNEAU DE RÃ‰COMPENSES\nActuel: +{} tÃ©lÃ©chargement par pub de 20s",
        "ad_panel_prompt": "âš™ï¸ Panneau des Pubs\nActuel: {}",
        "password_saved": "ðŸ” Mot de passe enregistrÃ©.",
        "password_too_long": "Le mot de passe doit faire 64 caractÃ¨res ou moins.",
        "file_to_link_prompt": "ðŸ”— **Fichier-vers-Lien**\nEnvoyez le(s) fichier(s) que vous souhaitez partager.",
        "link_invalid_expired": "âŒ Ce lien est invalide ou a expirÃ©.",
        "link_limit_reached": "â›” Ce lien a atteint sa limite d'utilisation.",
        "link_password_protected": "ðŸ” Ce lien est protÃ©gÃ© par mot de passe. Envoyez le mot de passe.",
        "files_sent": "âœ… Vos fichiers ont Ã©tÃ© envoyÃ©s.",
        "file_added": "ðŸ“¥ Fichier #{} ajoutÃ©. Envoyez-en plus ou appuyez sur CrÃ©er un Lien.",
        "fl_cancelled": "Fichier-vers-Lien annulÃ©",
        "fl_start_again": "Recommencez Fichier-vers-Lien avec /filetolink",
        "fl_choose_expiry": "Choisissez l'expiration du lien:",
        "fl_expiry_updated": "Expiration mise Ã  jour",
        "fl_choose_max_uses": "Choisissez le max de livraisons rÃ©ussies:",
        "fl_uses_updated": "Limite d'utilisation mise Ã  jour",
        "fl_set_password": "Envoyez un mot de passe, ou /clearpassword pour supprimer.",
        "fl_link_created": "Lien crÃ©Ã©",
        "fl_link_ready": "ðŸ”— Votre lien est prÃªt:\n{}\nFichiers: {}\nCoÃ»t: 1 tÃ©lÃ©chargement quotidien gratuit",
        "fl_daily_limit": "Limite quotidienne gratuite atteinte. Regardez une pub pour en gagner plus.",
        "fl_ad_busy": "âš ï¸ Serveur de publicitÃ©s occupÃ©.",
        "admin_skipped": "âœ… IgnorÃ©!",
        "admin_bypassed": "âœ… ContournÃ©",
        "free_set": "âœ… Gratuit dÃ©fini Ã  {}!",
        "free_updated": "âœ… TÃ©lÃ©chargements Gratuits mis Ã  jour Ã  {}!",
        "reward_set": "âœ… RÃ©compense dÃ©finie Ã  +{}!",
        "reward_updated": "âœ… RÃ©compense mise Ã  jour Ã  +{}!",
        "mode_updated": "âœ… Mode: {}",
        "support_opened": "âœï¸ Envoyez message/photo/vidÃ©o/fichier ci-dessous.",
        "admin_reply_mode": "âœï¸ RÃ©pondre Ã  {}:",
        "user_reply_mode": "âœï¸ Tapez le suivi ci-dessous",
        "support_closed": "ðŸ”’ FermÃ©",
        "drop_cancelled": "âŒ AnnulÃ©",
        "drop_no_items": "âš ï¸ Aucun Ã©lÃ©ment!",
        "drop_timer_set": "{} dÃ©fini!",
        "drop_broadcasting": "ðŸš€ Diffusion de {} Ã©lÃ©ments Ã  {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nAuto-suppression dans {}\nAppuyez pour rÃ©clamer:",
        "drop_done": "âœ… Diffusion terminÃ©e pour {}",
        "age_expired": "â³ ExpirÃ©!",
        "age_claimed": "âŒ DÃ©jÃ  rÃ©clamÃ©!",
        "age_verified": "VÃ©rifiÃ©!",
        "age_denied": "âŒ RefusÃ©. Doit Ãªtre 18+",
        "lang_updated": "Mis Ã  jour!",
        "batch_expired": "ExpirÃ©",
        "batch_loading": "Chargement...",
        "batch_no_channel": "Aucun canal liÃ©!",
        "batch_setup_prompt": "ðŸ“¦ Configuration: Rendez le bot admin dans le canal et transfÃ©rez un message ici",
        "batch_mode_activated": "Mode activÃ©!",
        "batch_change_dest": "ðŸ”„ **Changer de Canal de Destination**\nRendez le bot admin dans le nouveau canal, puis transfÃ©rez un message ici.",
        "join_channel_first_alert": "Rejoignez le canal d'abord! ðŸ“¢ Obligatoire!",
        "join_channel_first": "Rejoignez le canal d'abord! ðŸ“¢",
        "watch_timer_first": "â° Ouvrez le lien et regardez le minuteur de 20s d'abord!",
        "test_ad_verified": "âœ… Pub de Test VÃ©rifiÃ©e! +1",
        "test_ad_verified_msg": "âœ… **PUB DE TEST VÃ‰RIFIÃ‰E!**\nRÃ©compense: +1 tÃ©lÃ©chargement rechargÃ©!",
        "finish_timer_first": "â° Terminez le minuteur de 20s d'abord!",
        "verified_added": "VÃ©rifiÃ©! +1 ajoutÃ©",
        "resume_prompt": "âœ… VÃ©rifiÃ©! RechargÃ© +1. Reprendre?",
        "refilled_download": "âœ… RechargÃ© +1! TÃ©lÃ©chargez Ã  nouveau.",
        "fetching_bundle": "âœ… VÃ©rifiÃ©! RÃ©cupÃ©ration du paquet...",
        "outdated_button": "Ce bouton est obsolÃ¨te. Envoyez votre lien Ã  nouveau.",
        "stopping": "ArrÃªt...",
        "stopped": "ðŸ›‘ ArrÃªtÃ©",
        "resuming": "Reprise...",
        "checking_vault": "VÃ©rification du coffre et de la charge du serveur...",
        "server_busy": "â³ **Serveur OccupÃ©**\nActifs: {}/{}\nLibre: {} Mo\nFile d'attente: #{}\nDÃ©marrage auto!",
        "simulated": "ðŸ›  SimulÃ©! Appuyez maintenant sur VÃ©rifier et Obtenir +1",
        "server_unreachable": "âŒ Serveur injoignable",
        "monetag_failed_twice": "Terminez d'abord deux tentatives Monetag Ã©chouÃ©es.",
        "monetag_fallback_prompt": "ðŸŒ Monetag a Ã©chouÃ© deux fois. Continuez avec Adsterra:",
        "adsterra_ready": "Solution de repli Adsterra prÃªte",
        "finish_monetag": "ðŸ“º Terminez la pub Monetag dans la Mini App, puis vÃ©rifiez Ã  nouveau.",
        "monetag_failed_use_adsterra": "Monetag a Ã©chouÃ© deux fois. Utilisez la solution de repli Adsterra ci-dessous.",
        "ad_link_expired": "Lien publicitaire expirÃ©. Envoyez votre lien Ã  nouveau.",
        "ad_verified_added": "âœ… Pub vÃ©rifiÃ©e! +{} ajoutÃ©",
        "test_ad_completed": "âœ… PUB DE TEST VÃ‰RIFIÃ‰E\nRÃ©compense crÃ©ditÃ©e: +{} tÃ©lÃ©chargement.",
        "sponsor_viewed": "âœ… Sponsor vu! +{} ajoutÃ©",
        "refilled_send_again": "âœ… RechargÃ© +{}! Envoyez votre lien Ã  nouveau.",
        "queued": "â³ En file d'attente #{}",
        "banned": "ðŸš« Vous Ãªtes banni.",
        "no_links": "âŒ Aucun lien trouvÃ©.",
        "batch_count": "ðŸ“¦ Lot {} liens",
        "restore_invalid_json": "âŒ Ã‰chec de la restauration: **{}** n'est pas un JSON valide.",
        "restore_failed": "âŒ Ã‰chec de la restauration: {}",
        "restore_success": "âœ… **Restauration RÃ©ussie!**\nFichier: **{}**\nRestaurÃ©es **{}** entrÃ©es.",
        "admin_edit_welcome_prompt": "âœï¸ Envoyez le nouveau Message de Bienvenue. Utilisez `{bot_name}` pour le nom d'utilisateur.",
        "admin_welcome_updated": "âœ… Message de bienvenue mis Ã  jour!",
        "menu_edit_welcome": "âœï¸ Modifier le Message de Bienvenue",
        "cached_instant_video": "âš¡ Cache InstantanÃ© [{}] {} {}",
        "cached_instant_audio": "âš¡ **Cache InstantanÃ©** `{}`",
        "cached_instant_image": "âš¡ **Cache InstantanÃ©** `{}`",
        "auto_delete_9m": "â³ Auto-suppression dans 9 mins",
        "download_success": "âœ… TÃ©lÃ©chargement rÃ©ussi !"
    },
    "tr": {
        "welcome": "ðŸš€ **MICHAELBBC VAULT'A HOÅžGELDÄ°NÄ°Z - TAM MEDYA Ä°NDÄ°RÄ°CÄ°!**\n\nðŸ”¥ NE YAPABÄ°LÄ°RÄ°M:\nðŸŽ¬ VÄ°DEOLAR HD FiligransÄ±z!\nðŸŽµ SES MP3 192kbps!\nðŸ–¼ï¸ GÃ–RSELLER Tam Ã‡ekim!\nðŸ“ ALTYAZILAR Oto!\nðŸ“¦ TOPLU 100+ BaÄŸlantÄ±!\nâš¡ Ã–NBELLEK 1 Sn!\nðŸ’Ž KASA Sonsuza Kadar!\nðŸ“¤ DOSYA YÃœKLE!\nðŸ”— DOSYADAN-LÄ°NKE: PaylaÅŸÄ±labilir baÄŸlantÄ±lar oluÅŸturun!\n\nðŸ‘‰ BAÅžLAMAK Ä°Ã‡Ä°N BAÄžLANTI YAPIÅžTIRIN! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ Video (MP4)", "btn_audio": "ðŸŽµ Ses (MP3)", "btn_image": "ðŸ–¼ï¸ GÃ¶rseller", "btn_sub": "ðŸ“ AltyazÄ±lar (SRT)",
        "ask_format": "ðŸ‘‡ **HARÄ°KA! Hangi formatÄ± istiyorsunuz? AÅŸaÄŸÄ±dan seÃ§in!**",
        "fetching": "ðŸ“¥ **{} getiriliyor... Bekleyin! â³âœ¨**",
        "error_generic": "âŒ Oops! BaÅŸarÄ±sÄ±z! ðŸ˜¢ BaÄŸlantÄ± Ã¶zel/engelli. Halka aÃ§Ä±k bir baÄŸlantÄ± deneyin!",
        "error_50mb": "âŒ Ã‡ok bÃ¼yÃ¼k! ðŸ˜… Bu video 300MB'Ä± aÅŸÄ±yor. Daha kÄ±sa bir tane deneyin!", 
        "error_no_img": "âŒ GÃ¶rsel bulunamadÄ±! ðŸ˜¢ BaÅŸka bir baÄŸlantÄ± deneyin!",
        "images_received": "â³ **{} GÃ¶rsel alÄ±ndÄ±.**",
        "select_lang": "ðŸŒ Dilinizi seÃ§in! AÅŸaÄŸÄ±dan seÃ§in! ðŸ‘‡", 
        "lang_set": "âœ… Dil ayarlandÄ±! Keyfini Ã§Ä±karÄ±n! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Toplu Ä°ÅŸlem AlgÄ±landÄ± ({} baÄŸlantÄ±)**\nHangi format?",
        "batch_dest": "ðŸ“¦ **Nereye gÃ¶nderilsin?**",
        "btn_chat": "ðŸ“¥ Sohbette", "btn_chan": "ðŸ“¢ Kanala",
        "limit_reached": "âš ï¸ **Limit AÅŸÄ±ldÄ±!** 4 ÃœCRETSÄ°Z kullandÄ±nÄ±z! 20 sn reklam izleyin â†’ +1 indirme kazanÄ±n!",
        "refill_btn": "ðŸ”“ BaÄŸlantÄ±yÄ± AÃ§ ve +1 Doldur",
        "join_btn": "ðŸ“¢ Kanala KatÄ±l", "check_btn": "ðŸ’œ Bakiyeyi Kontrol Et",
        "limit_batch": "âš ï¸ **Toplu Ä°ÅŸlem Limiti {}/{}'de AÅŸÄ±ldÄ±**\n20 sn reklam izleyin â†’ devam etmek iÃ§in +1 indirme.",
        "batch_start": "ðŸ“¦ **Toplu Ä°ÅŸlem BaÅŸladÄ±:** {} **{} dosya**\nâ³ Ä°ÅŸleniyor...",
        "batch_done": "ðŸ **Bitti!** âœ… {} âŒ {}\nðŸ“¥ Burada {} dosya var.",
        "batch_done_chan": "ðŸ **Bitti!** âœ… {} âŒ {}\nðŸ“¢ {} dosya iletildi!",
        "dl_video": "ðŸ“¥ Video indiriliyor...", "dl_audio": "ðŸ“¥ Ses Ã§Ä±karÄ±lÄ±yor...", "dl_image": "ðŸ“¥ GÃ¶rseller Ã§ekiliyor...", "dl_sub": "ðŸ“¥ AltyazÄ±lar getiriliyor...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Engelli/Ã¶zel", "failed_generic": "âŒ BaÅŸarÄ±sÄ±z",
        "menu_lang": "ðŸŒ Dil", "menu_stats": "ðŸ“Š Ä°statistiklerim", "menu_help": "ðŸ’¬ Destek / SSS", "menu_join": "ðŸ“¢ Kanala KatÄ±l",
        "menu_uploads": "ðŸ¿ Hayran YÃ¼klemeleri", "menu_upload": "ðŸ“¤ Dosya YÃ¼kle",
        "admin_upload_prompt": "ðŸ“‚ **Hayran YÃ¼klemeleri Gelen Kutusu**",
        "user_upload_prompt": "ðŸ“¤ **Dosya YÃ¼kle**\nYÃ¶neticiye video/gÃ¶rsel/dosya gÃ¶nderin. Limit 5/24s.",
        "upload_success_user": "âœ… YÃ¶neticiye gÃ¶nderildi!",
        "upload_limit_reached": "âš ï¸ 5/24s yÃ¼kleme limitine ulaÅŸÄ±ldÄ±.",
        "no_uploads": "ðŸ“­ HenÃ¼z yÃ¼kleme yok.",
        "stats_msg": "ðŸ“Š **Ä°statistikleriniz:**\nâ€¢ Kalan Ä°ndirme: {}\nâ€¢ Kalan Toplu Ä°ÅŸlem: {}",
        "change_channel_prompt": "ðŸ”„ **Toplu Ä°ÅŸlem KanalÄ±nÄ± DeÄŸiÅŸtir**\n1. Yeni kanalda yÃ¶netici olduÄŸumdan emin olun.\n2. O kanaldan herhangi bir mesajÄ± buraya iletin.",
        "disk_config_prompt": "ðŸ’¾ **Disk YapÄ±landÄ±rmasÄ±**\nMevcut min boÅŸ disk: **{}MB**\nDeÄŸiÅŸtirmek iÃ§in: `/setdisk <deÄŸer>`",
        "mtproto_config_prompt": "âš¡ **MTProto YapÄ±landÄ±rmasÄ±**\nMevcut max yÃ¼kleme: **{}MB**\nDeÄŸiÅŸtirmek iÃ§in: `/setmtproto <deÄŸer>`",
        "free_panel_prompt": "ðŸ“¦ ÃœCRETSÄ°Z Ä°NDÄ°RMELER\nGÃ¼nlÃ¼k mevcut Ã¼cretsiz: {}",
        "reward_panel_prompt": "ðŸŽ Ã–DÃœL PANELÄ°\nMevcut: 20 sn reklam baÅŸÄ±na +{} indirme",
        "ad_panel_prompt": "âš™ï¸ Reklam Paneli\nMevcut: {}",
        "password_saved": "ðŸ” Åžifre kaydedildi.",
        "password_too_long": "Åžifre 64 karakter veya daha az olmalÄ±dÄ±r.",
        "file_to_link_prompt": "ðŸ”— **Dosyadan-Link**\nPaylaÅŸmak istediÄŸiniz dosya(larÄ±) gÃ¶nderin.",
        "link_invalid_expired": "âŒ Bu baÄŸlantÄ± geÃ§ersiz veya sÃ¼resi dolmuÅŸ.",
        "link_limit_reached": "â›” Bu baÄŸlantÄ± kullanÄ±m limitine ulaÅŸtÄ±.",
        "link_password_protected": "ðŸ” Bu baÄŸlantÄ± ÅŸifre korumalÄ±dÄ±r. Åžifreyi gÃ¶nderin.",
        "files_sent": "âœ… DosyalarÄ±nÄ±z gÃ¶nderildi.",
        "file_added": "ðŸ“¥ Dosya #{} eklendi. Daha fazla gÃ¶nderin veya BaÄŸlantÄ± OluÅŸtur'a dokunun.",
        "fl_cancelled": "Dosyadan-Link iptal edildi",
        "fl_start_again": "/filetolink ile Dosyadan-Link'i yeniden baÅŸlatÄ±n",
        "fl_choose_expiry": "BaÄŸlantÄ± sona erme sÃ¼resini seÃ§in:",
        "fl_expiry_updated": "Sona erme gÃ¼ncellendi",
        "fl_choose_max_uses": "Maksimum baÅŸarÄ±lÄ± teslimat sayÄ±sÄ±nÄ± seÃ§in:",
        "fl_uses_updated": "KullanÄ±m limiti gÃ¼ncellendi",
        "fl_set_password": "Bir ÅŸifre gÃ¶nderin veya kaldÄ±rmak iÃ§in /clearpassword gÃ¶nderin.",
        "fl_link_created": "BaÄŸlantÄ± oluÅŸturuldu",
        "fl_link_ready": "ðŸ”— BaÄŸlantÄ±nÄ±z hazÄ±r:\n{}\nDosyalar: {}\nMaliyet: 1 Ã¼cretsiz gÃ¼nlÃ¼k indirme",
        "fl_daily_limit": "GÃ¼nlÃ¼k Ã¼cretsiz limite ulaÅŸÄ±ldÄ±. Daha fazlasÄ±nÄ± kazanmak iÃ§in reklam izleyin.",
        "fl_ad_busy": "âš ï¸ Reklam sunucusu meÅŸgul.",
        "admin_skipped": "âœ… AtlandÄ±!",
        "admin_bypassed": "âœ… AtlatÄ±ldÄ±",
        "free_set": "âœ… Ãœcretsiz {} olarak ayarlandÄ±!",
        "free_updated": "âœ… Ãœcretsiz Ä°ndirmeler {} olarak gÃ¼ncellendi!",
        "reward_set": "âœ… Ã–dÃ¼l +{} olarak ayarlandÄ±!",
        "reward_updated": "âœ… Ã–dÃ¼l +{} olarak gÃ¼ncellendi!",
        "mode_updated": "âœ… Mod: {}",
        "support_opened": "âœï¸ AÅŸaÄŸÄ±ya mesaj/fotoÄŸraf/video/dosya gÃ¶nderin.",
        "admin_reply_mode": "âœï¸ {} kiÅŸisine yanÄ±t ver:",
        "user_reply_mode": "âœï¸ AÅŸaÄŸÄ±ya takip mesajÄ± yazÄ±n",
        "support_closed": "ðŸ”’ KapatÄ±ldÄ±",
        "drop_cancelled": "âŒ Ä°ptal edildi",
        "drop_no_items": "âš ï¸ Ã–ÄŸe yok!",
        "drop_timer_set": "{} ayarlandÄ±!",
        "drop_broadcasting": "ðŸš€ {} Ã¶ÄŸe {} kiÅŸisine yayÄ±nlanÄ±yor...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\n{} iÃ§inde otomatik silinir\nTalep etmek iÃ§in dokunun:",
        "drop_done": "âœ… {} kiÅŸisine yayÄ±n tamamlandÄ±",
        "age_expired": "â³ SÃ¼resi doldu!",
        "age_claimed": "âŒ Zaten talep edildi!",
        "age_verified": "DoÄŸrulandÄ±!",
        "age_denied": "âŒ Reddedildi. 18+ olmalÄ±",
        "lang_updated": "GÃ¼ncellendi!",
        "batch_expired": "SÃ¼resi doldu",
        "batch_loading": "YÃ¼kleniyor...",
        "batch_no_channel": "BaÄŸlÄ± kanal yok!",
        "batch_setup_prompt": "ðŸ“¦ Kurulum: Botu kanalda yÃ¶netici yapÄ±n ve buraya bir mesaj iletin",
        "batch_mode_activated": "Mod etkinleÅŸtirildi!",
        "batch_change_dest": "ðŸ”„ **Hedef KanalÄ± DeÄŸiÅŸtir**\nBotu yeni kanalda yÃ¶netici yapÄ±n, ardÄ±ndan buraya bir mesaj iletin.",
        "join_channel_first_alert": "Ã–nce kanala katÄ±lÄ±n! ðŸ“¢ KatÄ±lmalÄ±sÄ±nÄ±z!",
        "join_channel_first": "Ã–nce kanala katÄ±lÄ±n! ðŸ“¢",
        "watch_timer_first": "â° Ã–nce baÄŸlantÄ±yÄ± aÃ§Ä±n ve 20 sn'lik zamanlayÄ±cÄ±yÄ± izleyin!",
        "test_ad_verified": "âœ… Test ReklamÄ± DoÄŸrulandÄ±! +1",
        "test_ad_verified_msg": "âœ… **TEST REKLAMI DOÄžRULANDI!**\nÃ–dÃ¼l: +1 indirme dolduruldu!",
        "finish_timer_first": "â° Ã–nce 20 sn'lik zamanlayÄ±cÄ±yÄ± tamamlayÄ±n!",
        "verified_added": "DoÄŸrulandÄ±! +1 eklendi",
        "resume_prompt": "âœ… DoÄŸrulandÄ±! +1 dolduruldu. Devam edilsin mi?",
        "refilled_download": "âœ… +1 dolduruldu! Tekrar indirin.",
        "fetching_bundle": "âœ… DoÄŸrulandÄ±! Paket getiriliyor...",
        "outdated_button": "Bu dÃ¼ÄŸme gÃ¼ncel deÄŸil. BaÄŸlantÄ±nÄ±zÄ± tekrar gÃ¶nderin.",
        "stopping": "Durduruluyor...",
        "stopped": "ðŸ›‘ Durduruldu",
        "resuming": "Devam ediliyor...",
        "checking_vault": "Kasa ve sunucu yÃ¼kÃ¼ kontrol ediliyor...",
        "server_busy": "â³ **Sunucu MeÅŸgul**\nAktif: {}/{}\nBoÅŸ: {}MB\nKuyruk: #{}\nOtomatik baÅŸlayacak!",
        "simulated": "ðŸ›  SimÃ¼le edildi! Åžimdi Kontrol Et ve +1 Al'a dokunun",
        "server_unreachable": "âŒ Sunucuya ulaÅŸÄ±lamÄ±yor",
        "monetag_failed_twice": "Ã–nce iki baÅŸarÄ±sÄ±z Monetag denemesini tamamlayÄ±n.",
        "monetag_fallback_prompt": "ðŸŒ Monetag iki kez baÅŸarÄ±sÄ±z oldu. Adsterra ile devam edin:",
        "adsterra_ready": "Adsterra yedeklemesi hazÄ±r",
        "finish_monetag": "ðŸ“º Mini Uygulama'da Monetag reklamÄ±nÄ± tamamlayÄ±n, sonra tekrar kontrol edin.",
        "monetag_failed_use_adsterra": "Monetag iki kez baÅŸarÄ±sÄ±z oldu. AÅŸaÄŸÄ±daki Adsterra yedeklemesini kullanÄ±n.",
        "ad_link_expired": "Reklam baÄŸlantÄ±sÄ±nÄ±n sÃ¼resi doldu. BaÄŸlantÄ±nÄ±zÄ± tekrar gÃ¶nderin.",
        "ad_verified_added": "âœ… Reklam doÄŸrulandÄ±! +{} eklendi",
        "test_ad_completed": "âœ… TEST REKLAMI DOÄžRULANDI\nÃ–dÃ¼l yatÄ±rÄ±ldÄ±: +{} indirme.",
        "sponsor_viewed": "âœ… Sponsor gÃ¶rÃ¼ntÃ¼lendi! +{} eklendi",
        "refilled_send_again": "âœ… +{} dolduruldu! BaÄŸlantÄ±nÄ±zÄ± tekrar gÃ¶nderin.",
        "queued": "â³ Kuyrukta #{}",
        "banned": "ðŸš« YasaklandÄ±nÄ±z.",
        "no_links": "âŒ BaÄŸlantÄ± bulunamadÄ±.",
        "batch_count": "ðŸ“¦ Toplu {} baÄŸlantÄ±",
        "restore_invalid_json": "âŒ Geri yÃ¼kleme baÅŸarÄ±sÄ±z: **{}** geÃ§erli bir JSON deÄŸil.",
        "restore_failed": "âŒ Geri yÃ¼kleme baÅŸarÄ±sÄ±z: {}",
        "restore_success": "âœ… **Geri YÃ¼kleme BaÅŸarÄ±lÄ±!**\nDosya: **{}**\n**{}** girdi geri yÃ¼klendi.",
        "admin_edit_welcome_prompt": "âœï¸ Yeni KarÅŸÄ±lama MesajÄ±nÄ± gÃ¶nderin. Bot kullanÄ±cÄ± adÄ± iÃ§in `{bot_name}` kullanÄ±n.",
        "admin_welcome_updated": "âœ… KarÅŸÄ±lama mesajÄ± gÃ¼ncellendi!",
        "menu_edit_welcome": "âœï¸ KarÅŸÄ±lama MesajÄ±nÄ± DÃ¼zenle",
        "cached_instant_video": "âš¡ AnÄ±nda Ã–nbellek [{}] {} {}",
        "cached_instant_audio": "âš¡ **AnÄ±nda Ã–nbellek** `{}`",
        "cached_instant_image": "âš¡ **AnÄ±nda Ã–nbellek** `{}`",
        "auto_delete_9m": "â³ 9 dakikada otomatik silinir",
        "download_success": "âœ… Ä°ndirme baÅŸarÄ±lÄ±!"
    },
    "de": {
        "welcome": "ðŸš€ **WILLKOMMEN IM MICHAELBBC VAULT - ALL-IN-ONE MEDIA DOWNLOADER!**\n\nðŸ”¥ WAS ICH KANN:\nðŸŽ¬ VIDEOS HD Ohne Wasserzeichen!\nðŸŽµ AUDIO MP3 192kbps!\nðŸ–¼ï¸ BILDER Komplett Extrahiert!\nðŸ“ UNTERTITEL Auto!\nðŸ“¦ STAPEL 100+ Links!\nâš¡ CACHE 1 Sek!\nðŸ’Ž TRESOR FÃ¼r Immer!\nðŸ“¤ DATEIEN HOCHLADEN!\nðŸ”— DATEI-ZU-LINK: Erstelle teilbare Links!\n\nðŸ‘‰ FÃœGE EINEN LINK EIN, UM ZU STARTEN! ðŸ‘‡",
        "btn_video": "ðŸŽ¬ Video (MP4)", "btn_audio": "ðŸŽµ Audio (MP3)", "btn_image": "ðŸ–¼ï¸ Bilder", "btn_sub": "ðŸ“ Untertitel (SRT)",
        "ask_format": "ðŸ‘‡ **TOLL! Welches Format mÃ¶chtest du? WÃ¤hle unten!**",
        "fetching": "ðŸ“¥ **Dein {} wird abgerufen... Warte kurz! â³âœ¨**",
        "error_generic": "âŒ Oops! Fehlgeschlagen! ðŸ˜¢ Link privat/gesperrt. Versuche einen Ã¶ffentlichen Link!",
        "error_50mb": "âŒ Zu groÃŸ! ðŸ˜… Dieses Video ist Ã¼ber 300MB. Versuche ein kÃ¼rzeres!", 
        "error_no_img": "âŒ Keine Bilder gefunden! ðŸ˜¢ Versuche einen anderen Link!",
        "images_received": "â³ **{} Bilder erhalten.**",
        "select_lang": "ðŸŒ WÃ¤hle deine Sprache! WÃ¤hle unten! ðŸ‘‡", 
        "lang_set": "âœ… Sprache eingestellt! Viel SpaÃŸ! ðŸŽ‰âœ¨",
        "batch_detected": "ðŸ“¦ **Stapel erkannt ({} Links)**\nWelches Format?",
        "batch_dest": "ðŸ“¦ **Wohin senden?**",
        "btn_chat": "ðŸ“¥ Im Chat", "btn_chan": "ðŸ“¢ An Kanal",
        "limit_reached": "âš ï¸ **Limit erreicht!** Du hast 4 KOSTENLOSE genutzt! Schau 20s Werbung â†’ Erhalte +1 Download!",
        "refill_btn": "ðŸ”“ Link Ã¶ffnen & +1 auffÃ¼llen",
        "join_btn": "ðŸ“¢ Kanal beitreten", "check_btn": "ðŸ’œ Guthaben prÃ¼fen",
        "limit_batch": "âš ï¸ **Stapel-Limit bei {} von {} erreicht**\nSchau 20s Werbung â†’ +1 Download um fortzufahren.",
        "batch_start": "ðŸ“¦ **Stapel gestartet:** {} **{} Dateien**\nâ³ Wird verarbeitet...",
        "batch_done": "ðŸ **Fertig!** âœ… {} âŒ {}\nðŸ“¥ {} Dateien hier.",
        "batch_done_chan": "ðŸ **Fertig!** âœ… {} âŒ {}\nðŸ“¢ {} Dateien weitergeleitet!",
        "dl_video": "ðŸ“¥ Video wird heruntergeladen...", "dl_audio": "ðŸ“¥ Audio wird extrahiert...", "dl_image": "ðŸ“¥ Bilder werden extrahiert...", "dl_sub": "ðŸ“¥ Untertitel werden abgerufen...",
        "failed_50": "âŒ >300MB", "failed_blocked": "âŒ Gesperrt/privat", "failed_generic": "âŒ Fehlgeschlagen",
        "menu_lang": "ðŸŒ Sprache", "menu_stats": "ðŸ“Š Meine Statistiken", "menu_help": "ðŸ’¬ Support / FAQ", "menu_join": "ðŸ“¢ Kanal beitreten",
        "menu_uploads": "ðŸ¿ Fan-Uploads", "menu_upload": "ðŸ“¤ Datei hochladen",
        "admin_upload_prompt": "ðŸ“‚ **Fan-Uploads Posteingang**",
        "user_upload_prompt": "ðŸ“¤ **Datei hochladen**\nSende Video/Bild/Datei an Admin. Limit 5/24h.",
        "upload_success_user": "âœ… An Admin gesendet!",
        "upload_limit_reached": "âš ï¸ Upload-Limit 5/24h erreicht.",
        "no_uploads": "ðŸ“­ Noch keine Uploads.",
        "stats_msg": "ðŸ“Š **Deine Statistiken:**\nâ€¢ Verbleibende Downloads: {}\nâ€¢ Verbleibende Stapel: {}",
        "change_channel_prompt": "ðŸ”„ **Stapel-Kanal Ã¤ndern**\n1. Stelle sicher, dass ich im neuen Kanal Admin bin.\n2. Leite eine beliebige Nachricht aus diesem Kanal hierher weiter.",
        "disk_config_prompt": "ðŸ’¾ **Speicher-Konfiguration**\nAktueller min. freier Speicher: **{}MB**\nZum Ã„ndern: `/setdisk <wert>`",
        "mtproto_config_prompt": "âš¡ **MTProto-Konfiguration**\nAktueller max. Upload: **{}MB**\nZum Ã„ndern: `/setmtproto <wert>`",
        "free_panel_prompt": "ðŸ“¦ KOSTENLOSE DOWNLOADS\nAktuell kostenlos pro Tag: {}",
        "reward_panel_prompt": "ðŸŽ BELOHNUNGS-PANEL\nAktuell: +{} Download pro 20s Werbung",
        "ad_panel_prompt": "âš™ï¸ Werbe-Panel\nAktuell: {}",
        "password_saved": "ðŸ” Passwort gespeichert.",
        "password_too_long": "Passwort muss 64 Zeichen oder weniger sein.",
        "file_to_link_prompt": "ðŸ”— **Datei-zu-Link**\nSende die Datei(en), die du teilen mÃ¶chtest.",
        "link_invalid_expired": "âŒ Dieser Link ist ungÃ¼ltig oder abgelaufen.",
        "link_limit_reached": "â›” Dieser Link hat sein Nutzungslimit erreicht.",
        "link_password_protected": "ðŸ” Dieser Link ist passwortgeschÃ¼tzt. Sende das Passwort.",
        "files_sent": "âœ… Deine Dateien wurden gesendet.",
        "file_added": "ðŸ“¥ Datei #{} hinzugefÃ¼gt. Sende mehr oder tippe auf Link erstellen.",
        "fl_cancelled": "Datei-zu-Link abgebrochen",
        "fl_start_again": "Starte Datei-zu-Link neu mit /filetolink",
        "fl_choose_expiry": "WÃ¤hle den Link-Ablauf:",
        "fl_expiry_updated": "Ablauf aktualisiert",
        "fl_choose_max_uses": "WÃ¤hle max. erfolgreiche Zustellungen:",
        "fl_uses_updated": "Nutzungslimit aktualisiert",
        "fl_set_password": "Sende ein Passwort oder /clearpassword zum Entfernen.",
        "fl_link_created": "Link erstellt",
        "fl_link_ready": "ðŸ”— Dein Link ist bereit:\n{}\nDateien: {}\nKosten: 1 kostenloser tÃ¤glicher Download",
        "fl_daily_limit": "TÃ¤gliches kostenloses Limit erreicht. Schau Werbung, um mehr zu verdienen.",
        "fl_ad_busy": "âš ï¸ Werbeserver beschÃ¤ftigt.",
        "admin_skipped": "âœ… Ãœbersprungen!",
        "admin_bypassed": "âœ… Umgangen",
        "free_set": "âœ… Kostenlos auf {} gesetzt!",
        "free_updated": "âœ… Kostenlose Downloads auf {} aktualisiert!",
        "reward_set": "âœ… Belohnung auf +{} gesetzt!",
        "reward_updated": "âœ… Belohnung auf +{} aktualisiert!",
        "mode_updated": "âœ… Modus: {}",
        "support_opened": "âœï¸ Sende Nachricht/Foto/Video/Datei unten.",
        "admin_reply_mode": "âœï¸ Antworte an {}:",
        "user_reply_mode": "âœï¸ Tippe die Fortsetzung unten",
        "support_closed": "ðŸ”’ Geschlossen",
        "drop_cancelled": "âŒ Abgebrochen",
        "drop_no_items": "âš ï¸ Keine Elemente!",
        "drop_timer_set": "{} eingestellt!",
        "drop_broadcasting": "ðŸš¡ Sende {} Elemente an {}...",
        "drop_flash_text": "ðŸš¨ FLASH DROP!\nAutomatische LÃ¶schung in {}\nTippe zum EinlÃ¶sen:",
        "drop_done": "âœ… Sendung abgeschlossen an {}",
        "age_expired": "â³ Abgelaufen!",
        "age_claimed": "âŒ Bereits eingelÃ¶st!",
        "age_verified": "Verifiziert!",
        "age_denied": "âŒ Abgelehnt. Muss 18+ sein",
        "lang_updated": "Aktualisiert!",
        "batch_expired": "Abgelaufen",
        "batch_loading": "Wird geladen...",
        "batch_no_channel": "Kein Kanal verknÃ¼pft!",
        "batch_setup_prompt": "ðŸ“¦ Einrichtung: Mache den Bot im Kanal zum Admin und leite eine Nachricht hierher weiter",
        "batch_mode_activated": "Modus aktiviert!",
        "batch_change_dest": "ðŸ”„ **Zielkanal Ã¤ndern**\nMache den Bot im neuen Kanal zum Admin, dann leite eine Nachricht hierher weiter.",
        "join_channel_first_alert": "Tritt zuerst dem Kanal bei! ðŸ“¢ Muss beitreten!",
        "join_channel_first": "Tritt zuerst dem Kanal bei! ðŸ“¢",
        "watch_timer_first": "â° Ã–ffne zuerst den Link und schaue den 20s Timer!",
        "test_ad_verified": "âœ… Test-Werbung verifiziert! +1",
        "test_ad_verified_msg": "âœ… **TEST-WERBUNG VERIFIZIERT!**\nBelohnung: +1 Download aufgefÃ¼llt!",
        "finish_timer_first": "â° SchlieÃŸe zuerst den 20s Timer ab!",
        "verified_added": "Verifiziert! +1 hinzugefÃ¼gt",
        "resume_prompt": "âœ… Verifiziert! +1 aufgefÃ¼llt. Fortsetzen?",
        "refilled_download": "âœ… +1 aufgefÃ¼llt! Lade erneut herunter.",
        "fetching_bundle": "âœ… Verifiziert! Paket wird abgerufen...",
        "outdated_button": "Diese SchaltflÃ¤che ist veraltet. Sende deinen Link erneut.",
        "stopping": "Wird gestoppt...",
        "stopped": "ðŸ›‘ Gestoppt",
        "resuming": "Wird fortgesetzt...",
        "checking_vault": "Tresor und Serverlast werden Ã¼berprÃ¼ft...",
        "server_busy": "â³ **Server beschÃ¤ftigt**\nAktiv: {}/{}\nFrei: {}MB\nWarteschlange: #{}\nStartet automatisch!",
        "simulated": "ðŸ›  Simuliert! Tippe jetzt auf PrÃ¼fen & +1 erhalten",
        "server_unreachable": "âŒ Server nicht erreichbar",
        "monetag_failed_twice": "SchlieÃŸe zuerst zwei fehlgeschlagene Monetag-Versuche ab.",
        "monetag_fallback_prompt": "ðŸŒ Monetag ist zweimal fehlgeschlagen. Mit Adsterra fortfahren:",
        "adsterra_ready": "Adsterra-Fallback bereit",
        "finish_monetag": "ðŸ“º SchlieÃŸe die Monetag-Werbung in der Mini-App ab, prÃ¼fe dann erneut.",
        "monetag_failed_use_adsterra": "Monetag ist zweimal fehlgeschlagen. Nutze den Adsterra-Fallback unten.",
        "ad_link_expired": "Werbelink abgelaufen. Sende deinen Link erneut.",
        "ad_verified_added": "âœ… Werbung verifiziert! +{} hinzugefÃ¼gt",
        "test_ad_completed": "âœ… TEST-WERBUNG VERIFIZIERT\nBelohnung gutgeschrieben: +{} Download.",
        "sponsor_viewed": "âœ… Sponsor angesehen! +{} hinzugefÃ¼gt",
        "refilled_send_again": "âœ… +{} aufgefÃ¼llt! Sende deinen Link erneut.",
        "queued": "â³ In Warteschlange #{}",
        "banned": "ðŸš« Du bist gesperrt.",
        "no_links": "âŒ Keine Links gefunden.",
        "batch_count": "ðŸ“¦ Stapel {} Links",
        "restore_invalid_json": "âŒ Wiederherstellung fehlgeschlagen: **{}** ist kein gÃ¼ltiges JSON.",
        "restore_failed": "âŒ Wiederherstellung fehlgeschlagen: {}",
        "restore_success": "âœ… **Wiederherstellung erfolgreich!**\nDatei: **{}**\n**{}** EintrÃ¤ge wiederhergestellt.",
        "admin_edit_welcome_prompt": "âœï¸ Sende die neue Willkommensnachricht. Verwende `{bot_name}` fÃ¼r den Bot-Benutzernamen.",
        "admin_welcome_updated": "âœ… Willkommensnachricht aktualisiert!",
        "menu_edit_welcome": "âœï¸ Willkommensnachricht bearbeiten",
        "cached_instant_video": "âš¡ Sofortiger Cache [{}] {} {}",
        "cached_instant_audio": "âš¡ **Sofortiger Cache** `{}`",
        "cached_instant_image": "âš¡ **Sofortiger Cache** `{}`",
        "auto_delete_9m": "â³ Automatische LÃ¶schung in 9 Min.",
        "download_success": "âœ… Download erfolgreich!"
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

    await send_debug(f"ðŸ” <b>Processing Link:</b>\n<code>{url}</code>")
    yt_id = youtube_id_from_url(url)
    if yt_id:
        return f"youtube_{yt_id}"     # same key format yt-dlp produced, so old cache entries still match

    short_link_domains = ["vt.tiktok.com", "vm.tiktok.com", "youtu.be/", "t.co/", "instagr.am/", "fb.watch/"]
    is_short_link = any(domain in url.lower() for domain in short_link_domains)

    if is_short_link:
        await send_debug("ðŸ”„ Resolving short link...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
            resolved_url = response.url
            if resolved_url != original_url and "google.com/sorry" not in resolved_url:
                url = resolved_url
                await send_debug(f"âœ… Resolved to:\n<code>{url}</code>")
        except Exception as e:
            await send_debug(f"âŒ Redirect failed: {str(e)[:100]}")

    tiktok_match = re.search(r'/video/(\d{15,20})', url)
    if tiktok_match:
        vid_id = tiktok_match.group(1)
        await send_debug(f"ðŸŽ¯ <b>TikTok Regex Match!</b>\nVideo ID: <code>{vid_id}</code>")
        return f"tiktok_{vid_id}"

    await send_debug("ðŸ¤– Trying yt-dlp extraction...")
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                if 'entries' in info and info['entries']: info = info['entries'][0]
                extractor = info.get('extractor', 'generic').replace(':', '').replace(' ', '')
                vid_id = info.get('id', '')
                if vid_id:
                    await send_debug(f"âœ… yt-dlp found ID: <code>{vid_id}</code>")
                    return f"{extractor}_{vid_id}"
    except Exception as e:
        await send_debug(f"âš ï¸ yt-dlp failed: {str(e)[:50]}")

    await send_debug("ðŸŽ² Using URL hash fallback.")
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

        cap = f"ðŸ“¦ AUTO-BACKUP {ts}\nFree: {free_mb}MB | Active: {active_downloads} | Queue: {download_queue.qsize()} | Vault: {VIDEO_VAULT_ID}"
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
        [InlineKeyboardButton("ðŸ“º Watch Monetag Ad +1", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("ðŸ“¢ Join Public Channel ðŸ’œ", url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton("âœ… Check & Get +1", callback_data="monetag_check")],
        [InlineKeyboardButton("â†ªï¸ Use Adsterra fallback (after 2 failures)", callback_data="monetag_fallback")],
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
    warn = await bot.send_message(chat_id=user_id, text="â³ Auto-deletes in 9 mins", reply_markup=kb)
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
    caption = f"ðŸ“¸ {len(file_paths)} items `{ckey}`"
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
            m = await send_video_file_fn(bot, chat_id, chat_id, p, f"ðŸŽ¬ `{ckey}`", "Markdown", status_msg)
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
    caption = f"âš¡ ðŸ“¸ {len(entry['items'])} items `{ckey}`"
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
        [KeyboardButton(t["menu_upload"]), KeyboardButton("ðŸ”— File-to-Link")],
        [KeyboardButton("ðŸŸ¢ Bot Status")],
        [KeyboardButton("ðŸ”„ Change Batch Channel")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("/stats"), KeyboardButton("/toggleads")])
        keyboard.append([KeyboardButton("/testad"), KeyboardButton("/adinfo")])
        keyboard.append([KeyboardButton("/tokencheck"), KeyboardButton("/broadcast")])
        keyboard.append([KeyboardButton("/ban"), KeyboardButton("/unban")])
        keyboard.append([KeyboardButton("/backup"), KeyboardButton("/restore")])
        keyboard.append([KeyboardButton("ðŸ’¾ Disk Config"), KeyboardButton("âš¡ MTProto Config")])
        keyboard.append([KeyboardButton(t["menu_uploads"]), KeyboardButton("âš¡ Create Flash Drop")])
        keyboard.append([KeyboardButton("ðŸŽ Set Reward (1/2/3/5)"), KeyboardButton("ðŸ“¦ Set Free DL (2/3/4/5)")])
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
        [InlineKeyboardButton("ðŸ‡¬ðŸ‡§ English", callback_data="lang_en"), InlineKeyboardButton("ðŸ‡®ðŸ‡³ à¤¹à¤¿à¤‚à¤¦à¥€", callback_data="lang_hi")],
        [InlineKeyboardButton("ðŸ‡ªðŸ‡¸ EspaÃ±ol", callback_data="lang_es"), InlineKeyboardButton("ðŸ‡¸ðŸ‡¦ Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©", callback_data="lang_ar")],
        [InlineKeyboardButton("ðŸ‡·ðŸ‡º Ð ÑƒÑÑÐºÐ¸Ð¹", callback_data="lang_ru"), InlineKeyboardButton("ðŸ‡§ðŸ‡· PortuguÃªs", callback_data="lang_pt")],
        [InlineKeyboardButton("ðŸ‡®ðŸ‡© Indonesia", callback_data="lang_id"), InlineKeyboardButton("ðŸ‡«ðŸ‡· FranÃ§ais", callback_data="lang_fr")],
        [InlineKeyboardButton("ðŸ‡¹ðŸ‡· TÃ¼rkÃ§e", callback_data="lang_tr"), InlineKeyboardButton("ðŸ‡©ðŸ‡ª Deutsch", callback_data="lang_de")]
    ]
    await update.message.reply_text(t["select_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

def file_link_keyboard(state):
    settings = state.get("settings", {})
    expiry = settings.get("expiry", "never")
    expiry_label = {"3600":"1 hour", "86400":"1 day", "604800":"7 days", "2592000":"30 days", "never":"Never"}.get(str(expiry), "Never")
    max_clicks = int(settings.get("max_clicks", 0) or 0)
    kb = [[InlineKeyboardButton(f"â³ Expiry: {expiry_label}", callback_data="fl_expiry")],
          [InlineKeyboardButton(f"ðŸ‘¥ Max uses: {max_clicks if max_clicks else 'Unlimited'}", callback_data="fl_maxuses")],
          [InlineKeyboardButton("ðŸ” Set password" if not settings.get("password") else "ðŸ” Change/remove password", callback_data="fl_password")],
          [InlineKeyboardButton(f"ðŸ“Ž Files: {len(state.get('items', []))}", callback_data="fl_refresh")],
          [InlineKeyboardButton("âœ… Create Link", callback_data="fl_create"), InlineKeyboardButton("âŒ Cancel", callback_data="fl_cancel")]]
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
    except Exception: await update.effective_message.reply_text("ðŸ“¢ Join our required channel first: " + PUBLIC_CHANNEL_URL); return
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
        if not drop: await update.message.reply_text("âŒ Invalid flash drop."); return
        if time.time() > drop["expires_at"]: await update.message.reply_text(t["age_expired"], parse_mode="Markdown"); return
        if "claimed_users" in drop and user_id in drop["claimed_users"]: await update.message.reply_text(t["age_claimed"], parse_mode="Markdown"); return
        keyboard = [[InlineKeyboardButton("âœ… Yes, 18+", callback_data=f"age_yes_{drop_id}"), InlineKeyboardButton("âŒ No", callback_data="age_no")]]
        await update.message.reply_text("ðŸ”ž Age verification?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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
        extra = [[InlineKeyboardButton("âŒ Skip (Admin)", callback_data="admin_skip_ad")]] if user_id == ADMIN_ID else None
        kb = adsgram_keyboard(user_id, "wall", msg_start, msg_end, extra)
        if kb: await update.message.reply_text("ðŸ“º **Sponsor**\nTap **Watch Ad**, finish the ad in the Mini App, then tap **Check & Get +1**.", reply_markup=kb, parse_mode="Markdown")
        else: await update.message.reply_text("âš ï¸ Ad server busy, try again in a moment.")
        return
    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)
    keyboard = [[InlineKeyboardButton("ðŸ”“ Open Link & Watch", url=bridge_link)], [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]]
    if user_id == ADMIN_ID: keyboard.append([InlineKeyboardButton("âŒ Skip (Admin)", callback_data="admin_skip_ad")])
    try:
        tut = await context.bot.forward_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        await asyncio.sleep(0.2)
    except Exception as e1:
        logger.error(f"Forward failed: {e1}")
        try: await context.bot.copy_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
        except Exception as e2: logger.error(f"Copy failed: {e2}")
    await update.message.reply_text("ðŸ‘‡ **CONTENT LOCKED ðŸ”’**" + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, download_type, start_index=0):
    if not urls: return
    lang = get_lang(user_id)
    t = LANGUAGES.get(lang, LANGUAGES["en"])
    success_count = fail_count = 0
    active_batch_sessions[user_id] = True
    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ›‘ Stop Batch", callback_data="stop_batch")]])
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
        status_msg = await bot.send_message(chat_id=chat_id, text=f"ðŸ“¥ [{index}/{len(urls)}] {t['dl_video']}")
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
                        sent = await bot.send_video(chat_id=target_destination_id, video=cached["file_id"], caption=f"Item {index}/{len(urls)} âš¡ Cached {qual_tag}")
                        if target_destination_id == chat_id:
                            warn = await bot.send_message(chat_id=target_destination_id, text="â³ Auto-deletes in 9 mins")
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
                    warn = await bot.send_message(chat_id=target_destination_id, text="â³ Auto-deletes in 9 mins")
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
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"âŒ [{index}] {t['failed_generic']}")
                fail_count += 1
        except Exception as e:
            try: await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"âŒ [{index}] {str(e)[:50]}")
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
        keyboard = [[InlineKeyboardButton("ðŸ’¬ Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("ðŸ”’ Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"ðŸ’¬ Ticket [{ticket_id}] From {user_id}\nðŸ“Ž Media below:", parse_mode="Markdown")
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
                f"âš¡ Flash Drop item #{len(drip_state['items'])} added. Send more files or tap Finish & Broadcast Drop.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("ðŸš€ Finish & Broadcast Drop")], [KeyboardButton("âŒ Cancel / Exit")]],
                    resize_keyboard=True
                )
            )
            return
        try:
            await update.message.forward(chat_id=PRIVATE_CHANNEL_ID)
            context.user_data.pop("admin_vault_upload_mode", None)
            await update.message.reply_text("âœ… Saved to vault!", reply_markup=get_main_keyboard(get_lang(user_id), True))
        except Exception as e:
            await update.message.reply_text(f"âŒ {e}", reply_markup=get_main_keyboard(get_lang(user_id), True))
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
            await update.message.reply_text("âŒ Failed to send your upload. Please try again.", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID))

async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    t = LANGUAGES.get(get_lang(user_id), LANGUAGES["en"])
    if is_banned(user_id): await update.message.reply_text(t["banned"]); return
    if "http" in text.lower():
        flood, wait = is_flood(user_id)
        if flood: await update.message.reply_text(f"ðŸ¢ **Slow down!** You sent {FLOOD_LIMIT} links in last minute.\nWait {wait}s before next link.", parse_mode="Markdown"); return
    track_user_activity(user_id)
    lang = get_lang(user_id)
    
    if text == t.get("menu_edit_welcome", "âœï¸ Edit Welcome Msg") and user_id == ADMIN_ID:
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
        if f_chat is None: await update.message.reply_text("âŒ Please forward a message directly from your channel, not a copied message.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        try:
            bot_member = await context.bot.get_chat_member(chat_id=f_chat.id, user_id=context.bot.id)
            if getattr(bot_member, "status", None) not in ("administrator", "creator"): await update.message.reply_text("âš ï¸ I detected the channel, but I'm not an admin there yet. Add me as an administrator, then forward a channel message again.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        except Exception as exc:
            logger.warning(f"Could not verify bot admin status in channel {getattr(f_chat, 'id', 'unknown')}: {exc}")
            await update.message.reply_text("âš ï¸ I couldn't verify my admin access. Please check my admin status and forward another channel message.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        linking_states.pop(str(user_id), None)
        save_linking_states(linking_states)
        await update.message.reply_text(f"âœ… Linked {getattr(f_chat, 'title', 'your channel')} successfully. You can now use batch downloads to that channel.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    fl_states = load_json_file(FILE_LINK_STATE_FILE)
    fl_state = fl_states.get(str(user_id))
    if fl_state and fl_state.get("mode") == "file_link_password":
        token = fl_state.get("token")
        links = load_json_file(FILE_LINKS_FILE)
        record = links.get(token)
        fl_states.pop(str(user_id), None); save_json_file(FILE_LINK_STATE_FILE, fl_states)
        if not record or (record.get("expires_at") and time.time() > record["expires_at"]): await update.message.reply_text(t["link_invalid_expired"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        if text.strip() != str(record.get("password", "")): await update.message.reply_text("âŒ Incorrect password.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        if record.get("max_clicks", 0) and record.get("clicks", 0) >= record["max_clicks"]: await update.message.reply_text(t["link_limit_reached"], reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID)); return
        await send_file_link_payload(update, context, token, record)
        return
    menu_texts = [t["menu_stats"], t["menu_lang"], t["menu_help"], t["menu_join"], t["menu_upload"], t["menu_uploads"], "ðŸ”— File-to-Link", "ðŸŸ¢ Bot Status", "ðŸ”„ Change Batch Channel", "ðŸ“¢ Broadcast", "âš¡ Create Flash Drop", "âš™ï¸ Ad Toggle Panel", t.get("menu_edit_welcome", "âœï¸ Edit Welcome Msg")]
    if text in menu_texts:
        if text != t["menu_upload"]:
            context.user_data.pop("admin_vault_upload_mode", None)
        support_states = load_json_file(SUPPORT_STATES_FILE)
        if str(user_id) in support_states: del support_states[str(user_id)]; save_json_file(SUPPORT_STATES_FILE, support_states)
    if text.strip() == "ðŸ”— File-to-Link": await file_to_link_command(update, context); return
    if text.strip() == "ðŸ”„ Change Batch Channel":
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
    if text == "ðŸ’¾ Disk Config" and user_id == ADMIN_ID:
        current = get_min_free_disk_mb()
        await update.message.reply_text(t["disk_config_prompt"].format(current), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return
    if text == "âš¡ MTProto Config" and user_id == ADMIN_ID:
        current = get_mtproto_max_mb()
        await update.message.reply_text(t["mtproto_config_prompt"].format(current), parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        return
    if text.startswith("ðŸ“¦ Set Free") and user_id == ADMIN_ID:
        current = get_free_amount()
        keyboard = [[InlineKeyboardButton(f"âœ… {i} (Current)" if i==current else f"{i} free", callback_data=f"set_free_{i}") for i in [2,3,4,5]]]
        await update.message.reply_text(t["free_panel_prompt"].format(current), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text.startswith("ðŸŽ Set Reward") and user_id == ADMIN_ID:
        current = get_reward_amount()
        keyboard = [[InlineKeyboardButton(f"âœ… {i} (Current)" if i==current else f"{i}", callback_data=f"set_reward_{i}") for i in [1,2,3,5]]]
        await update.message.reply_text(t["reward_panel_prompt"].format(current), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == "âš™ï¸ Ad Toggle Panel" and user_id == ADMIN_ID:
        config = load_json_file(CONFIG_FILE)
        mode = config.get("ad_mode", "auto").upper()
        keyboard = [[InlineKeyboardButton("ðŸ”„ Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("ðŸ“º Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("ðŸŒ Adsterra", callback_data="set_ad_adsterra")]]
        await update.message.reply_text(t["ad_panel_prompt"].format(mode), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    
    if user_id == ADMIN_ID and str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "admin_replying":
        target_user_id = support_states[str(user_id)]["target_user_id"]
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("ðŸ’¬ Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("ðŸ”’ Close", callback_data=f"support_close_{ticket_id}")]]
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"ðŸ’¬ **Admin Reply:**\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            await update.message.reply_text(f"âœ… Sent to {target_user_id}!", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True))
        except Exception as e: await update.message.reply_text(f"âŒ {e}", reply_markup=get_main_keyboard(lang, True))
        return
    if str(user_id) in support_states and isinstance(support_states[str(user_id)], dict) and support_states[str(user_id)].get("mode") == "user_writing":
        ticket_id = support_states[str(user_id)]["ticket_id"]
        del support_states[str(user_id)]
        save_json_file(SUPPORT_STATES_FILE, support_states)
        keyboard = [[InlineKeyboardButton("ðŸ’¬ Reply", callback_data=f"support_reply_{user_id}"), InlineKeyboardButton("ðŸ”’ Close", callback_data=f"support_close_{ticket_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"ðŸ’¬ Ticket [{ticket_id}] From {user_id}\n\n{text}", parse_mode="Markdown")
        await context.bot.send_message(chat_id=ADMIN_ID, text="Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("âœ… Sent!", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if text == "âš¡ Create Flash Drop" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        states[str(user_id)] = {"mode": "collecting", "items": []}
        save_json_file(DRIP_STATE_FILE, states)
        kb = [[KeyboardButton("ðŸš€ Finish & Broadcast Drop")],[KeyboardButton("âŒ Cancel / Exit")]]
        await update.message.reply_text("âš¡ Flash Drop Mode: Send files", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="Markdown")
        return
    if text == "ðŸŸ¢ Bot Status": await status_command(update, context); return
    if text.strip() in ("ðŸ§ª Test Ad", "ðŸ“¢ Ad Info"):
        if user_id != ADMIN_ID: await update.message.reply_text("âœ… Menu updated.", reply_markup=get_main_keyboard(lang, False)); return
        if text.strip() == "ðŸ§ª Test Ad": await send_test_ad(update.message, user_id); return
    if text.strip() == "ðŸ“¢ Ad Info" and user_id == ADMIN_ID: await update.message.reply_text(build_ad_info_text(user_id), reply_markup=get_main_keyboard(lang, True)); return
    if text == "ðŸ“¢ Broadcast" and user_id == ADMIN_ID: await update.message.reply_text("ðŸ“¢ /broadcast [message] or reply with /broadcast", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, True)); return
    if text == "âŒ Cancel / Exit" and user_id == ADMIN_ID:
        states = load_json_file(DRIP_STATE_FILE)
        if str(user_id) in states: del states[str(user_id)]; save_json_file(DRIP_STATE_FILE, states)
        await update.message.reply_text(t["drop_cancelled"], reply_markup=get_main_keyboard(lang, True), parse_mode="Markdown")
        return
    if text == "ðŸš€ Finish & Broadcast Drop" and user_id == ADMIN_ID:
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
        keyboard = [[InlineKeyboardButton("ðŸ’¬ Open Support", callback_data="open_support")]]
        await update.message.reply_text(f"Support: [Help]({HELP_CHANNEL_URL})", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    if text == t["menu_lang"]: await language_command(update, context); return
    if text == t["menu_upload"]:
        if user_id == ADMIN_ID:
            context.user_data["admin_vault_upload_mode"] = True
            prompt = "ðŸ“¤ **Admin File Upload**\\nSend the file(s) you want to save to the vault."
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
            f"ðŸ“¬ Displayed {shown} fan upload(s)." + (f"\\nâš ï¸ {failed} older upload(s) could not be retrieved." if failed else ""),
            reply_markup=get_main_keyboard(lang, True)
        )
        return
    extracted_urls = re.findall(r'https?://[^\s]+', text)
    filtered = [u for u in extracted_urls if not ("t.me/" in u and "start=" in u)]
    extracted_urls = filtered
    if not extracted_urls:
        if "t.me/" in text and "start=" in text: await update.message.reply_text("ðŸ‘† Please use the buttons above.", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
                else: await update.message.reply_text("âš ï¸ Ad server busy, try again in a moment.", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
                return
            else:
                try:
                    tut = await context.bot.forward_message(chat_id=chat_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID)
                    await asyncio.sleep(0.2)
                except: pass
                bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
                keyboard = [[InlineKeyboardButton("ðŸ”“ Open Link & Watch Timer â° 20s +1", url=bridge_link)], [InlineKeyboardButton("ðŸ“¢ Join Public Channel ðŸ’œ", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("ðŸ’œ Check & Get Files âœ… +1", callback_data="verify_user")]]
                await update.message.reply_text(t["limit_reached"] + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                return
    if active_batch_sessions.get(user_id, False): return
    if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
        f_chat = update.message.forward_origin.chat
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        await update.message.reply_text(f"âœ… Linked {f_chat.title}", parse_mode="Markdown", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
        return
    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"batchtype_video_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"batchtype_audio_{payload_key}")]]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    url = extracted_urls[0]
    status_preview = await update.message.reply_text("ðŸ” Checking link...")
    title, dur = fetch_url_metadata(url)
    try: await status_preview.delete()
    except: pass
    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url
    keyboard = [[InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")],[InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],[InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")]]
    await update.message.reply_text(f"ðŸŽ¬ {title}\nâ±ï¸ {dur}\n\n{t['ask_format']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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
        await update.message.reply_text(f"ðŸ”„ Restoring <b>{document.file_name}</b>...", parse_mode="HTML")
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
        keyboard = [[InlineKeyboardButton("ðŸŽ¬ Video", callback_data=f"batchtype_video_{payload_key}")]]
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
    for idx,(uid,info) in enumerate(sorted_users,1): top_text+=f"{idx}. `{uid}` â€” {info.get('total_interactions',0)}\n"
    if not top_text: top_text="No activity yet"
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    used_mb = get_downloads_usage_mb()
    cache = load_json_file(CACHE_FILE)
    flood_data = load_json_file(FLOOD_FILE)
    banned = load_json_file(BANNED_FILE)
    total_hits = sum(v.get("hits",0) for v in cache.values() if isinstance(v, dict))
    host_free = shutil.disk_usage(".").free // (1024*1024) if os.path.exists(".") else 0
    txt = (f"ðŸ“Š **ADVANCED ADMIN**\n\nâ€¢ Total: **{total_users}**\nâ€¢ 24h Active: **{active_24hr}**\nâ€¢ Ad Mode: **{mode}**\n\nðŸ“¢ **Ad Split:**\nâ€¢ Monetag: **{adsgram_count}**\nâ€¢ Adsterra: **{adsterra_count}**\n\nðŸ–¥ï¸ **Render:**\nâ€¢ Used: **{used_mb}MB**\nâ€¢ Free: **{free_mb}MB**\nâ€¢ Host: **{host_free}MB**\nâ€¢ Active: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\nâ€¢ Queue: **{download_queue.qsize()}**\nâ€¢ Cache: **{len(cache)}** files\nâ€¢ Hits: **{total_hits}** saved\nâ€¢ Flood: **{len(flood_data)}**\nâ€¢ Banned: **{len(banned)}**\n\nðŸŽžï¸ **Video Vault:** `{VIDEO_VAULT_ID}`\nðŸ† **Top 10:**\n{top_text}")
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_user_activity(update.message.from_user.id)
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    free_mb = shutil.disk_usage(".").free // (1024*1024)
    cache = load_json_file(CACHE_FILE)
    await update.message.reply_text(f"ðŸŸ¢ **Status V38 Monetag**\nMode: **{mode}**\nFree: **{free_mb}MB**\nDL: **{active_downloads}/{MAX_CONCURRENT_SHORT}**\nQueue: **{download_queue.qsize()}**\nCache: **{len(cache)}**\nVault: **{VIDEO_VAULT_ID}**\nReward: +1 realistic\nFlood: **ON**\nBackup: **6hr to {PRIVATE_CHANNEL_ID}**", parse_mode="Markdown", reply_markup=get_main_keyboard(get_lang(update.message.from_user.id), update.message.from_user.id == ADMIN_ID))

async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID: return
    file_list = "\n".join([f"   â€¢ <b>{f}</b>" for f in BACKUP_FILES])
    await update.message.reply_text(f"ðŸ”„ <b>Restore Backup Files</b>\n\n1. Go to your private backup channel.\n2. <b>Long-press</b> a backup file, then tap all the others to select them.\n3. Hit <b>Forward</b> and send them all to this bot at once!\n\n<b>Files to restore:</b>\n{file_list}\n\nI will automatically detect and restore each file! âš¡", parse_mode="HTML", reply_markup=get_main_keyboard("en", True))

async def toggle_ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    config = load_json_file(CONFIG_FILE)
    mode = config.get("ad_mode","auto").upper().replace("ADSGRAM","MONETAG")
    keyboard = [[InlineKeyboardButton("ðŸ”„ Auto", callback_data="set_ad_auto")],[InlineKeyboardButton("ðŸ“º Monetag", callback_data="set_ad_monetag")],[InlineKeyboardButton("ðŸŒ Adsterra", callback_data="set_ad_adsterra")]]
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
    status_msg = await update.message.reply_text(f"ðŸš€ Broadcasting to {len(all_users)}...", parse_mode="Markdown")
    success = fail = 0
    for uid in all_users:
        if uid == ADMIN_ID or is_banned(uid): continue
        try:
            if reply_msg: await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=reply_msg.message_id)
            else: await context.bot.send_message(chat_id=uid, text=" ".join(args), parse_mode="Markdown")
            success+=1
            await asyncio.sleep(0.05)
        except: fail+=1
    await status_msg.edit_text(f"âœ… Done\nSent: {success}\nFail: {fail}", parse_mode="Markdown")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: /ban <user_id>", reply_markup=get_main_keyboard("en", True)); return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        banned[target] = {"banned_at": time.time(), "reason": "spam"}
        save_json_file(BANNED_FILE, banned)
        await update.message.reply_text(f"ðŸš« Banned {target}", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except Exception as e: await update.message.reply_text(f"âŒ {e}", reply_markup=get_main_keyboard("en", True))

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: /unban <user_id>", reply_markup=get_main_keyboard("en", True)); return
    try:
        target = context.args[0]
        banned = load_json_file(BANNED_FILE)
        if target in banned:
            del banned[target]
            save_json_file(BANNED_FILE, banned)
            await update.message.reply_text(f"âœ… Unbanned {target}", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
        else: await update.message.reply_text(f"Not banned", reply_markup=get_main_keyboard("en", True))
    except Exception as e: await update.message.reply_text(f"âŒ {e}", reply_markup=get_main_keyboard("en", True))

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(f"ðŸ“¦ Backing up ALL files to {PRIVATE_CHANNEL_ID}...", reply_markup=get_main_keyboard("en", True))
    await backup_to_channel(context.bot)
    await update.message.reply_text("âœ… Full Backup sent!", reply_markup=get_main_keyboard("en", True))

async def set_disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/setdisk <mb>`\nExample: `/setdisk 500`", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
    try:
        value = int(context.args[0])
        if value < 50: await update.message.reply_text("âš ï¸ Value must be at least 50MB.", reply_markup=get_main_keyboard("en", True)); return
        config = load_json_file(CONFIG_FILE)
        config["min_free_disk_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"âœ… Minimum free disk space set to **{value}MB**", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except ValueError: await update.message.reply_text("âŒ Invalid number.", reply_markup=get_main_keyboard("en", True))

async def set_mtproto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/setmtproto <mb>`\nExample: `/setmtproto 1000`", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True)); return
    try:
        value = int(context.args[0])
        if value < 50: await update.message.reply_text("âš ï¸ Value must be at least 50MB.", reply_markup=get_main_keyboard("en", True)); return
        config = load_json_file(CONFIG_FILE)
        config["mtproto_max_mb"] = value
        save_json_file(CONFIG_FILE, config)
        await update.message.reply_text(f"âœ… MTProto max upload size set to **{value}MB**", parse_mode="Markdown", reply_markup=get_main_keyboard("en", True))
    except ValueError: await update.message.reply_text("âŒ Invalid number.", reply_markup=get_main_keyboard("en", True))

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
                await bot.send_message(chat_id=chat_id, text="ðŸ§ª Carousel trace:\n" + "\n".join(LAST_CAROUSEL_TRACE)[:3500])
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
            sent_media = await send_audio_file(bot, chat_id, file_paths[0], f"ðŸŽµ Size {size} `{ckey}`", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            try:
                vmsg = await bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent_media.audio.file_id, caption=ckey)
                cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "vault_msg_id": vmsg.message_id, "size": size}
            except: cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "size": size}
            os.remove(file_paths[0])
        else:
            sent_media = await send_video_file(bot, chat_id, chat_id, file_paths[0], f"âœ¨ {qual_tag} Size {size} `{ckey}`", "Markdown", status_msg)
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
                    f"ðŸ§ª DL error: {type(e).__name__}: {str(e)[:500]}\n"
                    f"MTProto: ready={MTPROTO['ready'].is_set()} api_id={bool(API_ID)} api_hash={bool(API_HASH)}"
                    f"{trace_txt}"))
            except Exception: pass
        if "FILE_TOO_LARGE" in str(e): err = t["error_50mb"]
        elif "MTPROTO_OFF" in str(e): err = "âš ï¸ Big files need fast mode, which is offline right now."
        elif "MTPROTO_PEER" in str(e): err = "âš ï¸ Send /start to this bot once, then send the link again."
        elif "SITE_BLOCKED" in str(e): err = "âš ï¸ This site is blocking downloads from our server right now. Please try again later."
        elif isinstance(e, (asyncio.TimeoutError, TimeoutError)): err = "âš ï¸ This is taking too long, so I stopped. Please try again later."
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
                  [InlineKeyboardButton("Never", callback_data="fl_exp_never"), InlineKeyboardButton("â¬… Back", callback_data="fl_refresh")]]
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
                  [InlineKeyboardButton("â¬… Back", callback_data="fl_refresh")]]
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
                        reward_kb = [[InlineKeyboardButton("ðŸ”“ Open Link & Watch Timer â° 20s +1", url=bridge_link)], [InlineKeyboardButton("ðŸ“¢ Join Public Channel ðŸ’œ", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("ðŸ’œ Check & Get +1", callback_data="verify_user")]]
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
        keyboard = [[InlineKeyboardButton("ðŸŽ Claim Now", url=claim_url)]]
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
            warn = await context.bot.send_message(chat_id=user_id, text=f"â³ Auto-deletes in {drop.get('delete_label','9 Minutes')}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            sent_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, sent_ids, drop.get("delete_delay",540)))
        except Exception as e: await context.bot.send_message(chat_id=user_id, text=f"âŒ {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
        keyboard = [[InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{dl_type}_{payload_key}")], [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{dl_type}_{payload_key}")], [InlineKeyboardButton("ðŸ”„ Change Channel", callback_data="change_channel")]]
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
        await query.message.reply_text(t["monetag_fallback_prompt"] + ADSTERRA_USER_GUIDE, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”“ Open Adsterra Link", url=bridge_link)], [InlineKeyboardButton("âœ… Check & Get +1", callback_data="verify_user")]]), parse_mode="Markdown")
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
            except Exception as e: await context.bot.send_message(chat_id=chat_id, text=f"âŒ {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
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
            keyboard = [[InlineKeyboardButton("â–¶ï¸ Resume Batch +1", callback_data="resume_batch")]]
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
            warn = await context.bot.send_message(chat_id=user_id, text="â³ Auto-deletes in 9 mins", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))
            fwd_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, fwd_ids, 540))
        except Exception as e: await query.message.reply_text(f"âŒ {e}", reply_markup=get_main_keyboard(lang, user_id == ADMIN_ID))

ADSTERRA_USER_GUIDE = (
    "\n\nâš ï¸ **Adsterra not opening or visit not detected?**\n"
    "1. Temporarily disable Private DNS, ad blockers, and ad-filtering apps.\n"
    "2. Turn off VPN or proxy.\n"
    "3. Tap **Open Link** and choose **Open in browser** (not inside Telegram).\n"
    "4. Let the page load and keep it open for at least **20 seconds**.\n"
    "5. Return here and tap **Check & Get +1**.\n\n"
    "Detection depends on Adsterra and your browser/network; these steps do not guarantee a reward."
)

TEST_AD_TEXT = "ðŸ§ª AD PLACEMENT TEST\n\n1ï¸âƒ£ User sends link\n2ï¸âƒ£ User gets 4 FREE downloads\n3ï¸âƒ£ LIMIT REACHED screen appears\n4ï¸âƒ£ Tap Watch Ad\n5ï¸âƒ£ Tap Check & Get +1\n\nðŸ‘‡ TRY THE AD NOW:"

async def send_adsgram_test(message, user_id):
    extra = [[InlineKeyboardButton("ðŸ›  Admin: simulate ad finished", callback_data="admin_sim_ad")]] if user_id == ADMIN_ID else None
    kb = adsgram_keyboard(user_id, "test", 0, 0, extra)
    if not kb: await message.reply_text("âš ï¸ Ad server not reachable.", reply_markup=get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)); return
    await message.reply_text(TEST_AD_TEXT, reply_markup=kb)

ADSTERRA_TEST_TEXT = "ðŸ§ª AD PLACEMENT TEST (Adsterra)\n\n1ï¸âƒ£ User sends link\n2ï¸âƒ£ LIMIT REACHED screen appears\n3ï¸âƒ£ Stay 20s on ad page\n4ï¸âƒ£ Tap Check & Get +1\n\nðŸ‘‡ TRY THE AD NOW:" + ADSTERRA_USER_GUIDE

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
    keyboard = [[InlineKeyboardButton("ðŸ”“ Open Link & Watch Timer â° 20s +1", url=bridge_link)], [InlineKeyboardButton("ðŸ“¢ Join Public Channel ðŸ’œ", url=PUBLIC_CHANNEL_URL)], [InlineKeyboardButton("ðŸ’œ Check & Get Files âœ… +1", callback_data="verify_user")]]
    await message.reply_text(ADSTERRA_TEST_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))

async def send_test_ad(message, user_id):
    if get_global_ab_network(user_id) == "monetag": await send_adsgram_test(message, user_id)
    else: await send_adsterra_test(message, user_id)

def build_ad_info_text(user_id):
    mode = load_json_file(CONFIG_FILE).get("ad_mode", "auto")
    monetag = "â€¢ Monetag: LIMIT REACHED screen -> Watch Ad Mini App -> Check & Get +1\n"
    adsterra = "â€¢ Adsterra: LIMIT REACHED screen -> Open Link 20s -> Check & Get +1\n"
    if mode in ("monetag", "adsgram"): head, body = "Mode: MONETAG only", monetag
    elif mode == "adsterra": head, body = "Mode: ADSTERRA only", adsterra
    else:
        net = "Monetag" if get_global_ab_network(user_id) == "monetag" else "Adsterra"
        head, body = f"Mode: AUTO (you currently get {net})", monetag + adsterra
    return ("ðŸ“¢ AD INFO\n\nBot: @Michaelbbcvaultbot\n" + head + "\n\nðŸ“ Exact ad placement:\n" + body + "\nâ€¢ Reward: +1 download per completed ad\n\nðŸ§ª To test: tap ðŸ§ª Test Ad or send /testad")

async def test_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await send_test_ad(update.message, update.effective_user.id)

async def tokencheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    mine = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:8] if BOT_TOKEN else "none"
    try: s = requests.get(f"{WEB_BASE_URL}/monetag-selfcheck", timeout=15).json()
    except Exception as e: await update.message.reply_text(f"âŒ Could not reach server: {type(e).__name__}", reply_markup=get_main_keyboard("en", True)); return
    same = (s.get("fingerprint") == mine)
    lines = ["ðŸ” TOKEN CHECK", f"Render bot: fingerprint {mine}", f"PythonAnywhere: fingerprint {s.get('fingerprint')}", f"PA token works: {s.get('telegram_ok')}"]
    lines.append("âœ… MATCH" if same else "âŒ DIFFERENT")
    await update.message.reply_text("\n".join(lines), reply_markup=get_main_keyboard("en", True))

async def ad_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(build_ad_info_text(update.effective_user.id), reply_markup=get_main_keyboard("en", True))

EXTRAS_STATUS = "â³ Extras not loaded yet"

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
            EXTRAS_STATUS = f"âœ… Extras loaded from: {os.path.basename(_path)}"
        except Exception as _e:
            EXTRAS_STATUS = f"âŒ Extras NOT loaded: {type(_e).__name__}: {str(_e)[:700]}"
            logger.exception("extras failed to load")
        print(EXTRAS_STATUS, flush=True)

        async def extras_status_command(update, context):
            if update.effective_user.id != ADMIN_ID: return
            await update.message.reply_text(EXTRAS_STATUS, reply_markup=get_main_keyboard("en", True))
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
        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        try:   # tell the admin on every restart whether the extras loaded (also refreshes the admin keyboard)
            await app.bot.send_message(chat_id=ADMIN_ID, text="ðŸ¤– Bot restarted\n" + EXTRAS_STATUS, reply_markup=get_main_keyboard("en", True))
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
    try: await status_msg.edit_text(f"ðŸ“¤ Uploading {os.path.getsize(path)/(1024*1024):.0f}MB in fast mode...")
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