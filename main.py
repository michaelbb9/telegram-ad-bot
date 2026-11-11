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
import subprocess
import imageio_ffmpeg
import yt_dlp
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Auto-install gallery-dl if missing
try:
    import gallery_dl
except ImportError:
    os.system("pip install gallery-dl")
    import gallery_dl

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

# --- 100% COMPLETE 10-LANGUAGE DICTIONARY ---
LANGUAGES = {
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
    "hi": {
        "welcome": "🚀 **MICHAELBBC VAULT में स्वागत है - ऑल मीडिया डाउनलोडर!**\n\n🔥 मैं क्या कर सकता हूँ:\n🎬 वीडियो HD नो वॉटरमार्क!\n🎵 ऑडियो MP3 192kbps!\n🖼️ इमेजेस स्क्रेप ALL!\n📝 सबटाइटल्स ऑटो!\n📦 बैच 100+ लिंक्स!\n⚡ कैश 1 सेकंड!\n💎 वॉल्ट फॉरेवर!\n📤 फाइलें अपलोड करें!\n🔗 फाइल-टू-लिंक: शेयर लिंक बनाएं!\n\n👉 शुरू करने के लिए लिंक पेस्ट करें! 👇",
        "btn_video": "🎬 वीडियो (MP4)", "btn_audio": "🎵 ऑडियो (MP3)", "btn_image": "🖼️ इमेजेस", "btn_sub": "📝 सबटाइटल्स (SRT)",
        "ask_format": "👇 **शानदार! कौन सा फॉर्मेट चाहते हैं? नीचे चुनें!**",
        "fetching": "📥 **आपका {} लाया जा रहा है... रुके रहें! ⏳✨**",
        "error_generic": "❌ ओह! विफल! 😢 लिंक प्राइवेट/ब्लॉक है। पब्लिक लिंक आज़माएं!",
        "error_50mb": "❌ बहुत बड़ा! 😅 यह वीडियो 300MB से अधिक है। छोटा वाला आज़माएं!", 
        "error_no_img": "❌ कोई इमेज नहीं मिली! 😢 दूसरा लिंक आज़माएं!",
        "images_received": "⏳ **{} इमेजेस प्राप्त हुईं।**",
        "select_lang": "🌍 अपनी भाषा चुनें! नीचे चुनें! 👇", 
        "lang_set": "✅ भाषा सेट हो गई! आनंद लें! 🎉✨",
        "batch_detected": "📦 **बैच डिटेक्ट हुआ ({} लिंक्स)**\nकौन सा फॉर्मेट?",
        "batch_dest": "📦 **कहाँ भेजें?**",
        "btn_chat": "📥 चैट में", "btn_chan": "📢 चैनल में",
        "limit_reached": "⚠️ **लिमिट पूरी हो गई!** आपने 4 फ्री इस्तेमाल कर लिए! 20 सेकंड का विज्ञापन देखें → +1 डाउनलोड पाएं!",
        "refill_btn": "🔓 लिंक खोलें और +1 रिफिल करें",
        "join_btn": "📢 चैनल जॉइन करें", "check_btn": "💜 बैलेंस चेक करें",
        "limit_batch": "⚠️ **बैच लिमिट {} में से {} पर पहुँच गई**\nजारी रखने के लिए 20 सेकंड का विज्ञापन देखें → +1 डाउनलोड।",
        "batch_start": "📦 **बैच शुरू:** {} **{} फाइलें**\n⏳ प्रोसेसिंग...",
        "batch_done": "🏁 **हो गया!** ✅ {} ❌ {}\n📥 {} फाइलें यहाँ हैं।",
        "batch_done_chan": "🏁 **हो गया!** ✅ {} ❌ {}\n📢 {} फाइलें फॉरवर्ड की गईं!",
        "dl_video": "📥 वीडियो डाउनलोड हो रहा है...", "dl_audio": "📥 ऑडियो निकाला जा रहा है...", "dl_image": "📥 इमेजेस स्क्रेप हो रही हैं...", "dl_sub": "📥 सबटाइटल्स लाए जा रहे हैं...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ ब्लॉक/प्राइवेट", "failed_generic": "❌ विफल",
        "menu_lang": "🌍 भाषा", "menu_stats": "📊 मेरे आंकड़े", "menu_help": "💬 सपोर्ट / FAQ", "menu_join": "📢 चैनल जॉइन करें",
        "menu_uploads": "🍿 फैन अपलोड्स", "menu_upload": "📤 फाइल अपलोड करें",
        "admin_upload_prompt": "📂 **फैन अपलोड्स इनबॉक्स**",
        "user_upload_prompt": "📤 **फाइल अपलोड करें**\nएडमिन को वीडियो/इमेज/फाइल भेजें। लिमिट 5/24घंटे।",
        "upload_success_user": "✅ एडमिन को भेज दिया गया!",
        "upload_limit_reached": "⚠️ अपलोड लिमिट 5/24घंटे पूरी हो गई।",
        "no_uploads": "📭 अभी तक कोई अपलोड नहीं।",
        "stats_msg": "📊 **आपके आंकड़े:**\n• डाउनलोड बचे: {}\n• बैच बचे: {}",
        "change_channel_prompt": "🔄 **बैच चैनल बदलें**\n1. सुनिश्चित करें कि मैं नए चैनल में एडमिन हूँ।\n2. उस चैनल से कोई भी मैसेज यहाँ फॉरवर्ड करें।",
        "disk_config_prompt": "💾 **डिस्क कॉन्फ़िगरेशन**\nवर्तमान न्यूनतम फ्री डिस्क: **{}MB**\nबदलने के लिए: `/setdisk <value>`",
        "mtproto_config_prompt": "⚡ **MTProto कॉन्फ़िगरेशन**\nवर्तमान अधिकतम अपलोड: **{}MB**\nबदलने के लिए: `/setmtproto <value>`",
        "free_panel_prompt": "📦 फ्री डाउनलोड्स\nवर्तमान फ्री प्रति दिन: {}",
        "reward_panel_prompt": "🎁 रिवॉर्ड पैनल\nवर्तमान: +{} डाउनलोड प्रति 20 सेकंड विज्ञापन",
        "ad_panel_prompt": "⚙️ विज्ञापन पैनल\nवर्तमान: {}",
        "password_saved": "🔐 पासवर्ड सेव हो गया।",
        "password_too_long": "पासवर्ड 64 अक्षरों से कम होना चाहिए।",
        "file_to_link_prompt": "🔗 **फाइल-टू-लिंक**\nवह फाइल(ें) भेजें जिन्हें आप शेयर करना चाहते हैं।",
        "link_invalid_expired": "❌ यह लिंक अमान्य है या समाप्त हो गया है।",
        "link_limit_reached": "⛔ इस लिंक ने अपनी उपयोग सीमा पार कर ली है।",
        "link_password_protected": "🔐 यह लिंक पासवर्ड से सुरक्षित है। पासवर्ड भेजें।",
        "files_sent": "✅ आपकी फाइलें भेज दी गई हैं।",
        "file_added": "📥 फाइल #{} जोड़ी गई। और भेजें, या 'Create Link' टैप करें।",
        "fl_cancelled": "फाइल-टू-लिंक रद्द किया गया",
        "fl_start_again": "/filetolink के साथ फिर से शुरू करें",
        "fl_choose_expiry": "लिंक समाप्ति चुनें:",
        "fl_expiry_updated": "समाप्ति अपडेट हो गई",
        "fl_choose_max_uses": "अधिकतम सफल डिलीवरी चुनें:",
        "fl_uses_updated": "उपयोग सीमा अपडेट हो गई",
        "fl_set_password": "पासवर्ड भेजें, या हटाने के लिए /clearpassword भेजें।",
        "fl_link_created": "लिंक बनाया गया",
        "fl_link_ready": "🔗 आपका लिंक तैयार है:\n{}\nफाइलें: {}\nलागत: 1 फ्री दैनिक डाउनलोड",
        "fl_daily_limit": "दैनिक फ्री लिमिट पूरी हो गई। अधिक कमाने के लिए विज्ञापन देखें।",
        "fl_ad_busy": "⚠️ विज्ञापन सर्वर व्यस्त है।",
        "admin_skipped": "✅ छोड़ दिया गया!",
        "admin_bypassed": "✅ बायपास किया गया",
        "free_set": "✅ फ्री {} पर सेट किया गया!",
        "free_updated": "✅ फ्री डाउनलोड्स {} पर अपडेट किए गए!",
        "reward_set": "✅ रिवॉर्ड +{} पर सेट किया गया!",
        "reward_updated": "✅ रिवॉर्ड +{} पर अपडेट किया गया!",
        "mode_updated": "✅ मोड: {}",
        "support_opened": "✍️ नीचे मैसेज/फोटो/वीडियो/फाइल भेजें।",
        "admin_reply_mode": "✍️ {} को रिप्लाई करें:",
        "user_reply_mode": "✍️ नीचे फॉलो-अप टाइप करें",
        "support_closed": "🔒 बंद किया गया",
        "drop_cancelled": "❌ रद्द किया गया",
        "drop_no_items": "⚠️ कोई आइटम नहीं!",
        "drop_timer_set": "{} सेट किया गया!",
        "drop_broadcasting": "🚀 {} आइटम {} को ब्रॉडकास्ट किया जा रहा है...",
        "drop_flash_text": "🚨 फ्लैश ड्रॉप!\n{} में ऑटो-डिलीट होगा\nक्लेम करने के लिए टैप करें:",
        "drop_done": "✅ {} को ब्रॉडकास्ट हो गया",
        "age_expired": "⏳ समाप्त हो गया!",
        "age_claimed": "❌ पहले ही क्लेम किया जा चुका है!",
        "age_verified": "सत्यापित!",
        "age_denied": "❌ अस्वीकृत। 18+ होना चाहिए",
        "lang_updated": "अपडेट किया गया!",
        "batch_expired": "समाप्त हो गया",
        "batch_loading": "लोड हो रहा है...",
        "batch_no_channel": "कोई चैनल लिंक नहीं किया गया!",
        "batch_setup_prompt": "📦 सेटअप: चैनल में बॉट को एडमिन बनाएं और यहाँ एक मैसेज फॉरवर्ड करें",
        "batch_mode_activated": "मोड सक्रिय किया गया!",
        "batch_change_dest": "🔄 **डेस्टिनेशन चैनल बदलें**\nनए चैनल में बॉट को एडमिन बनाएं, फिर यहाँ मैसेज फॉरवर्ड करें।",
        "join_channel_first_alert": "पहले चैनल जॉइन करें! 📢 जॉइन करना आवश्यक है!",
        "join_channel_first": "पहले चैनल जॉइन करें! 📢",
        "watch_timer_first": "⏰ पहले लिंक खोलें और 20 सेकंड का टाइमर देखें!",
        "test_ad_verified": "✅ टेस्ट विज्ञापन सत्यापित! +1",
        "test_ad_verified_msg": "✅ **टेस्ट विज्ञापन सत्यापित!**\nरिवॉर्ड: +1 डाउनलोड रिफिल किया गया!",
        "finish_timer_first": "⏰ पहले 20 सेकंड का टाइमर पूरा करें!",
        "verified_added": "सत्यापित! +1 जोड़ा गया",
        "resume_prompt": "✅ सत्यापित! +1 रिफिल किया गया। फिर से शुरू करें?",
        "refilled_download": "✅ +1 रिफिल किया गया! फिर से डाउनलोड करें।",
        "fetching_bundle": "✅ सत्यापित! बंडल लाया जा रहा है...",
        "outdated_button": "यह बटन पुराना है। अपना लिंक फिर से भेजें।",
        "stopping": "रोका जा रहा है...",
        "stopped": "🛑 रुक गया",
        "resuming": "फिर से शुरू हो रहा है...",
        "checking_vault": "वॉल्ट और सर्वर लोड चेक किया जा रहा है...",
        "server_busy": "⏳ **सर्वर व्यस्त है**\nसक्रिय: {}/{}\nफ्री: {}MB\nकतार: #{}\nऑटो शुरू होगा!",
        "simulated": "🛠 सिम्युलेट किया गया! अब चेक करें और +1 प्राप्त करें",
        "server_unreachable": "❌ सर्वर पहुँच से बाहर है",
        "monetag_failed_twice": "पहले दो विफल Monetag प्रयास पूरे करें।",
        "monetag_fallback_prompt": "🌐 Monetag दो बार विफल रहा। Adsterra के साथ जारी रखें:",
        "adsterra_ready": "Adsterra फॉलबैक तैयार है",
        "finish_monetag": "📺 Mini App में Monetag विज्ञापन पूरा करें, फिर चेक करें।",
        "monetag_failed_use_adsterra": "Monetag दो बार विफल रहा। नीचे दिए गए Adsterra फॉलबैक का उपयोग करें।",
        "ad_link_expired": "विज्ञापन लिंक समाप्त हो गया है। अपना लिंक फिर से भेजें।",
        "ad_verified_added": "✅ विज्ञापन सत्यापित! +{} जोड़ा गया",
        "test_ad_completed": "✅ टेस्ट विज्ञापन सत्यापित\nरिवॉर्ड जमा किया गया: +{} डाउनलोड।",
        "sponsor_viewed": "✅ स्पॉन्सर देखा गया! +{} जोड़ा गया",
        "refilled_send_again": "✅ +{} रिफिल किया गया! अपना लिंक फिर से भेजें।",
        "queued": "⏳ कतार #{}",
        "banned": "🚫 आप बैन कर दिए गए हैं।",
        "no_links": "❌ कोई लिंक नहीं मिला।",
        "batch_count": "📦 बैच {} लिंक्स",
        "restore_invalid_json": "❌ रिस्टोर विफल: **{}** मान्य JSON नहीं है।",
        "restore_failed": "❌ रिस्टोर विफल: {}",
        "restore_success": "✅ **रिस्टोर सफल!**\nफाइल: **{}**\n**{}** एंट्रीज रिस्टोर की गईं।",
        "admin_edit_welcome_prompt": "✏️ नया वेलकम मैसेज भेजें। बॉट यूजरनेम के लिए `{bot_name}` का उपयोग करें।",
        "admin_welcome_updated": "✅ वेलकम मैसेज अपडेट हो गया!",
        "menu_edit_welcome": "✏️ वेलकम मैसेज एडिट करें",
        "cached_instant_video": "⚡ कैश किया गया तात्कालिक [{}] {} {}",
        "cached_instant_audio": "⚡ **कैश किया गया तात्कालिक** `{}`",
        "cached_instant_image": "⚡ **कैश किया गया तात्कालिक** `{}`",
        "auto_delete_9m": "⏳ 9 मिनट में ऑटो-डिलीट",
        "download_success": "✅ डाउनलोड सफल!"
    },
    "es": {
        "welcome": "🚀 **BIENVENIDO A MICHAELBBC VAULT - DESCARGADOR DE MEDIOS!**\n\n🔥 QUÉ PUEDO HACER:\n🎬 VIDEOS HD Sin Marca de Agua!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMÁGENES Scraping TOTAL!\n📝 SUBTÍTULOS Auto!\n📦 LOTES 100+ Enlaces!\n⚡ CACHE 1 Seg!\n💎 VAULT Para Siempre!\n📤 SUBIR ARCHIVOS!\n🔗 ARCHIVO-A-ENLACE: Crea enlaces compartibles!\n\n👉 PEGA UN ENLACE PARA EMPEZAR! 👇",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Imágenes", "btn_sub": "📝 Subtítulos (SRT)",
        "ask_format": "👇 **GENIAL! ¿Qué formato quieres? Elige abajo!**",
        "fetching": "📥 **Obteniendo tu {}... Espera un momento! ⏳✨**",
        "error_generic": "❌ Ups! Falló! 😢 Enlace privado/bloqueado. Prueba un enlace público!",
        "error_50mb": "❌ Demasiado grande! 😅 Este video supera los 300MB. Prueba uno más corto!", 
        "error_no_img": "❌ No se encontraron imágenes! 😢 Prueba otro enlace!",
        "images_received": "⏳ **{} Imágenes recibidas.**",
        "select_lang": "🌍 Selecciona tu idioma! Elige abajo! 👇", 
        "lang_set": "✅ Idioma configurado! Disfruta! 🎉✨",
        "batch_detected": "📦 **Lote Detectado ({} enlaces)**\n¿Qué formato?",
        "batch_dest": "📦 **Dónde enviar?**",
        "btn_chat": "📥 En Chat", "btn_chan": "📢 Al Canal",
        "limit_reached": "⚠️ **Límite Alcanzado!** Usaste 4 GRATIS! Mira un anuncio de 20s → Obtén +1 descarga!",
        "refill_btn": "🔓 Abrir Enlace y Recargar +1",
        "join_btn": "📢 Unirse al Canal", "check_btn": "💜 Verificar Saldo",
        "limit_batch": "⚠️ **Límite de Lote Alcanzado en {} de {}**\nMira un anuncio de 20s → +1 descarga para continuar.",
        "batch_start": "📦 **Lote Iniciado:** {} **{} archivos**\n⏳ Procesando...",
        "batch_done": "🏁 **Listo!** ✅ {} ❌ {}\n📥 {} archivos aquí.",
        "batch_done_chan": "🏁 **Listo!** ✅ {} ❌ {}\n📢 {} archivos reenviados!",
        "dl_video": "📥 Descargando video...", "dl_audio": "📥 Extrayendo audio...", "dl_image": "📥 Obteniendo imágenes...", "dl_sub": "📥 Obteniendo subtítulos...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Bloqueado/privado", "failed_generic": "❌ Falló",
        "menu_lang": "🌍 Idioma", "menu_stats": "📊 Mis Estadísticas", "menu_help": "💬 Soporte / FAQ", "menu_join": "📢 Unirse al Canal",
        "menu_uploads": "🍿 Subidas de Fans", "menu_upload": "📤 Subir Archivo",
        "admin_upload_prompt": "📂 **Bandeja de Subidas de Fans**",
        "user_upload_prompt": "📤 **Subir Archivo**\nEnvía video/imagen/archivo al Admin. Límite 5/24h.",
        "upload_success_user": "✅ Enviado al Admin!",
        "upload_limit_reached": "⚠️ Límite de subidas 5/24h alcanzado.",
        "no_uploads": "📭 Aún no hay subidas.",
        "stats_msg": "📊 **Tus Estadísticas:**\n• Descargas Restantes: {}\n• Lotes Restantes: {}",
        "change_channel_prompt": "🔄 **Cambiar Canal de Lotes**\n1. Asegúrate de que soy admin en el nuevo canal.\n2. Reenvía cualquier mensaje de ese canal aquí.",
        "disk_config_prompt": "💾 **Config de Disco**\nMin disco libre actual: **{}MB**\nPara cambiar: `/setdisk <valor>`",
        "mtproto_config_prompt": "⚡ **Config MTProto**\nMax subida actual: **{}MB**\nPara cambiar: `/setmtproto <valor>`",
        "free_panel_prompt": "📦 DESCARGAS GRATIS\nGratis actuales por día: {}",
        "reward_panel_prompt": "🎁 PANEL DE RECOMPENSAS\nActual: +{} descarga por anuncio de 20s",
        "ad_panel_prompt": "⚙️ Panel de Anuncios\nActual: {}",
        "password_saved": "🔐 Contraseña guardada.",
        "password_too_long": "La contraseña debe tener 64 caracteres o menos.",
        "file_to_link_prompt": "🔗 **Archivo-a-Enlace**\nEnvía el/los archivo(s) que quieres compartir.",
        "link_invalid_expired": "❌ Este enlace es inválido o expiró.",
        "link_limit_reached": "⛔ Este enlace alcanzó su límite de uso.",
        "link_password_protected": "🔐 Este enlace está protegido con contraseña. Envía la contraseña.",
        "files_sent": "✅ Tus archivos han sido enviados.",
        "file_added": "📥 Archivo #{} añadido. Envía más o toca Crear Enlace.",
        "fl_cancelled": "Archivo-a-Enlace cancelado",
        "fl_start_again": "Inicia Archivo-a-Enlace de nuevo con /filetolink",
        "fl_choose_expiry": "Elige la expiración del enlace:",
        "fl_expiry_updated": "Expiración actualizada",
        "fl_choose_max_uses": "Elige el máximo de entregas exitosas:",
        "fl_uses_updated": "Límite de uso actualizado",
        "fl_set_password": "Envía una contraseña, o /clearpassword para eliminar.",
        "fl_link_created": "Enlace creado",
        "fl_link_ready": "🔗 Tu enlace está listo:\n{}\nArchivos: {}\nCosto: 1 descarga diaria gratis",
        "fl_daily_limit": "Límite diario gratis alcanzado. Mira un anuncio para ganar más.",
        "fl_ad_busy": "⚠️ Servidor de anuncios ocupado.",
        "admin_skipped": "✅ Omitido!",
        "admin_bypassed": "✅ Omitido",
        "free_set": "✅ Gratis configurado a {}!",
        "free_updated": "✅ Descargas Gratis actualizadas a {}!",
        "reward_set": "✅ Recompensa configurada a +{}!",
        "reward_updated": "✅ Recompensa actualizada a +{}!",
        "mode_updated": "✅ Modo: {}",
        "support_opened": "✍️ Envía mensaje/foto/video/archivo abajo.",
        "admin_reply_mode": "✍️ Responder a {}:",
        "user_reply_mode": "✍️ Escribe el seguimiento abajo",
        "support_closed": "🔒 Cerrado",
        "drop_cancelled": "❌ Cancelado",
        "drop_no_items": "⚠️ Sin elementos!",
        "drop_timer_set": "{} configurado!",
        "drop_broadcasting": "🚀 Transmitiendo {} elementos a {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nAuto-elimina en {}\nToca para reclamar:",
        "drop_done": "✅ Transmisión hecha a {}",
        "age_expired": "⏳ Expirado!",
        "age_claimed": "❌ Ya reclamado!",
        "age_verified": "Verificado!",
        "age_denied": "❌ Denegado. Debe ser 18+",
        "lang_updated": "Actualizado!",
        "batch_expired": "Expirado",
        "batch_loading": "Cargando...",
        "batch_no_channel": "Ningún canal vinculado!",
        "batch_setup_prompt": "📦 Configuración: Haz bot admin en el canal y reenvía un mensaje aquí",
        "batch_mode_activated": "Modo activado!",
        "batch_change_dest": "🔄 **Cambiar Canal de Destino**\nHaz bot admin en el nuevo canal, luego reenvía un mensaje aquí.",
        "join_channel_first_alert": "Únete al canal primero! 📢 Debes unirte!",
        "join_channel_first": "Únete al canal primero! 📢",
        "watch_timer_first": "⏰ Abre el enlace y mira el temporizador de 20s primero!",
        "test_ad_verified": "✅ Anuncio de Prueba Verificado! +1",
        "test_ad_verified_msg": "✅ **ANUNCIO DE PRUEBA VERIFICADO!**\nRecompensa: +1 descarga recargada!",
        "finish_timer_first": "⏰ Termina el temporizador de 20s primero!",
        "verified_added": "Verificado! +1 añadido",
        "resume_prompt": "✅ Verificado! Recargado +1. ¿Reanudar?",
        "refilled_download": "✅ Recargado +1! Descarga de nuevo.",
        "fetching_bundle": "✅ Verificado! Obteniendo paquete...",
        "outdated_button": "Este botón está desactualizado. Envía tu enlace de nuevo.",
        "stopping": "Deteniendo...",
        "stopped": "🛑 Detenido",
        "resuming": "Reanudando...",
        "checking_vault": "Verificando vault y carga del servidor...",
        "server_busy": "⏳ **Servidor Ocupado**\nActivos: {}/{}\nLibre: {}MB\nCola: #{}\nIniciará auto!",
        "simulated": "🛠 Simulado! Ahora toca Verificar y Obtener +1",
        "server_unreachable": "❌ Servidor inalcanzable",
        "monetag_failed_twice": "Completa dos intentos fallidos de Monetag primero.",
        "monetag_fallback_prompt": "🌐 Monetag falló dos veces. Continúa con Adsterra:",
        "adsterra_ready": "Fallback de Adsterra listo",
        "finish_monetag": "📺 Termina el anuncio de Monetag en Mini App, luego verifica.",
        "monetag_failed_use_adsterra": "Monetag falló dos veces. Usa el fallback de Adsterra abajo.",
        "ad_link_expired": "Enlace de anuncio expirado. Envía tu enlace de nuevo.",
        "ad_verified_added": "✅ Anuncio verificado! +{} añadido",
        "test_ad_completed": "✅ ANUNCIO DE PRUEBA VERIFICADO\nRecompensa acreditada: +{} descarga.",
        "sponsor_viewed": "✅ Patrocinador visto! +{} añadido",
        "refilled_send_again": "✅ Recargado +{}! Envía tu enlace de nuevo.",
        "queued": "⏳ En cola #{}",
        "banned": "🚫 Estás prohibido.",
        "no_links": "❌ No se encontraron enlaces.",
        "batch_count": "📦 Lote {} enlaces",
        "restore_invalid_json": "❌ Restauración fallida: **{}** no es JSON válido.",
        "restore_failed": "❌ Restauración fallida: {}",
        "restore_success": "✅ **Restauración Exitosa!**\nArchivo: **{}**\nRestauradas **{}** entradas.",
        "admin_edit_welcome_prompt": "✏️ Envía el nuevo Mensaje de Bienvenida. Usa `{bot_name}` para el nombre de usuario.",
        "admin_welcome_updated": "✅ Mensaje de bienvenida actualizado!",
        "menu_edit_welcome": "✏️ Editar Mensaje de Bienvenida",
        "cached_instant_video": "⚡ Caché Instantánea [{}] {} {}",
        "cached_instant_audio": "⚡ **Caché Instantánea** `{}`",
        "cached_instant_image": "⚡ **Caché Instantánea** `{}`",
        "auto_delete_9m": "⏳ Auto-elimina en 9 mins",
        "download_success": "✅ ¡Descarga exitosa!"
    },
    "ar": {
        "welcome": "🚀 **مرحباً بك في MICHAELBBC VAULT - محمل الوسائط الشامل!**\n\n🔥 ماذا يمكنني أن أفعل:\n🎬 فيديوهات HD بدون علامة مائية!\n🎵 صوت MP3 192kbps!\n🖼️ سحب جميع الصور!\n📝 ترجمات تلقائية!\n📦 دفعات 100+ رابط!\n⚡ ذاكرة تخزين مؤقت 1 ثانية!\n💎 خزنة للأبد!\n📤 رفع الملفات!\n🔗 ملف-إلى-رابط: إنشاء روابط قابلة للمشاركة!\n\n👉 الصق رابطاً للبدء! 👇",
        "btn_video": "🎬 فيديو (MP4)", "btn_audio": "🎵 صوت (MP3)", "btn_image": "🖼️ صور", "btn_sub": "📝 ترجمات (SRT)",
        "ask_format": "👇 **رائع! ما التنسيق الذي تريده؟ اختر أدناه!**",
        "fetching": "📥 **جاري جلب {}... انتظر قليلاً! ⏳✨**",
        "error_generic": "❌ عذراً! فشل! 😢 الرابط خاص/محظور. جرب رابطاً عاماً!",
        "error_50mb": "❌ كبير جداً! 😅 هذا الفيديو يتجاوز 300 ميجابايت. جرب فيديو أقصر!", 
        "error_no_img": "❌ لم يتم العثور على صور! 😢 جرب رابطاً آخر!",
        "images_received": "⏳ **تم استلام {} صورة.**",
        "select_lang": "🌍 اختر لغتك! اختر أدناه! 👇", 
        "lang_set": "✅ تم تعيين اللغة! استمتع! 🎉✨",
        "batch_detected": "📦 **تم اكتشاف دفعة ({} روابط)**\nما التنسيق؟",
        "batch_dest": "📦 **أين نرسل؟**",
        "btn_chat": "📥 في الدردشة", "btn_chan": "📢 إلى القناة",
        "limit_reached": "⚠️ **تم الوصول للحد الأقصى!** استخدمت 4 مجاناً! شاهد إعلان 20 ثانية → احصل على +1 تحميل!",
        "refill_btn": "🔓 افتح الرابط وأعد التعبئة +1",
        "join_btn": "📢 انضم للقناة", "check_btn": "💜 تحقق من الرصيد",
        "limit_batch": "⚠️ **تم الوصول لحد الدفعة عند {} من {}**\nشاهد إعلان 20 ثانية → +1 تحميل للمتابعة.",
        "batch_start": "📦 **بدأت الدفعة:** {} **{} ملفات**\n⏳ جاري المعالجة...",
        "batch_done": "🏁 **تم!** ✅ {} ❌ {}\n📥 {} ملفات هنا.",
        "batch_done_chan": "🏁 **تم!** ✅ {} ❌ {}\n📢 تم إعادة توجيه {} ملفات!",
        "dl_video": "📥 جاري تحميل الفيديو...", "dl_audio": "📥 جاري استخراج الصوت...", "dl_image": "📥 جاري سحب الصور...", "dl_sub": "📥 جاري جلب الترجمات...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ محظور/خاص", "failed_generic": "❌ فشل",
        "menu_lang": "🌍 اللغة", "menu_stats": "📊 إحصائياتي", "menu_help": "💬 الدعم / الأسئلة الشائعة", "menu_join": "📢 انضم للقناة",
        "menu_uploads": "🍿 رفع المعجبين", "menu_upload": "📤 رفع ملف",
        "admin_upload_prompt": "📂 **صندوق وارد رفع المعجبين**",
        "user_upload_prompt": "📤 **رفع ملف**\nأرسل فيديو/صورة/ملف للمسؤول. الحد 5/24 ساعة.",
        "upload_success_user": "✅ تم الإرسال للمسؤول!",
        "upload_limit_reached": "⚠️ تم الوصول لحد الرفع 5/24 ساعة.",
        "no_uploads": "📭 لا توجد عمليات رفع بعد.",
        "stats_msg": "📊 **إحصائياتك:**\n• التحميلات المتبقية: {}\n• الدفعات المتبقية: {}",
        "change_channel_prompt": "🔄 **تغيير قناة الدفعات**\n1. تأكد من أنني مسؤول في القناة الجديدة.\n2. أعد توجيه أي رسالة من تلك القناة إلى هنا.",
        "disk_config_prompt": "💾 **إعدادات القرص**\nالحد الأدنى الحالي للمساحة الحرة: **{} ميجابايت**\nللتغيير: `/setdisk <value>`",
        "mtproto_config_prompt": "⚡ **إعدادات MTProto**\nالحد الأقصى الحالي للرفع: **{} ميجابايت**\nللتغيير: `/setmtproto <value>`",
        "free_panel_prompt": "📦 التحميلات المجانية\nالمجاني الحالي يومياً: {}",
        "reward_panel_prompt": "🎁 لوحة المكافآت\nالحالي: +{} تحميل لكل إعلان 20 ثانية",
        "ad_panel_prompt": "⚙️ لوحة الإعلانات\nالحالي: {}",
        "password_saved": "🔐 تم حفظ كلمة المرور.",
        "password_too_long": "يجب أن تكون كلمة المرور 64 حرفاً أو أقل.",
        "file_to_link_prompt": "🔗 **ملف-إلى-رابط**\nأرسل الملف(ات) التي تريد مشاركتها.",
        "link_invalid_expired": "❌ هذا الرابط غير صالح أو منتهي الصلاحية.",
        "link_limit_reached": "⛔ وصل هذا الرابط إلى حد الاستخدام.",
        "link_password_protected": "🔐 هذا الرابط محمي بكلمة مرور. أرسل كلمة المرور.",
        "files_sent": "✅ تم إرسال ملفاتك.",
        "file_added": "📥 تمت إضافة الملف #{}. أرسل المزيد، أو اضغط على إنشاء رابط.",
        "fl_cancelled": "تم إلغاء ملف-إلى-رابط",
        "fl_start_again": "ابدأ ملف-إلى-رابط مرة أخرى باستخدام /filetolink",
        "fl_choose_expiry": "اختر انتهاء صلاحية الرابط:",
        "fl_expiry_updated": "تم تحديث الانتهاء",
        "fl_choose_max_uses": "اختر الحد الأقصى للتسليمات الناجحة:",
        "fl_uses_updated": "تم تحديث حد الاستخدام",
        "fl_set_password": "أرسل كلمة مرور، أو /clearpassword للإزالة.",
        "fl_link_created": "تم إنشاء الرابط",
        "fl_link_ready": "🔗 رابطك جاهز:\n{}\nالملفات: {}\nالتكلفة: 1 تحميل يومي مجاني",
        "fl_daily_limit": "تم الوصول للحد اليومي المجاني. شاهد إعلاناً لكسب المزيد.",
        "fl_ad_busy": "⚠️ خادم الإعلانات مشغول.",
        "admin_skipped": "✅ تم التخطي!",
        "admin_bypassed": "✅ تم التجاوز",
        "free_set": "✅ تم تعيين المجاني إلى {}!",
        "free_updated": "✅ تم تحديث التحميلات المجانية إلى {}!",
        "reward_set": "✅ تم تعيين المكافأة إلى +{}!",
        "reward_updated": "✅ تم تحديث المكافأة إلى +{}!",
        "mode_updated": "✅ الوضع: {}",
        "support_opened": "✍️ أرسل رسالة/صورة/فيديو/ملف أدناه.",
        "admin_reply_mode": "✍️ الرد على {}:",
        "user_reply_mode": "✍️ اكتب المتابعة أدناه",
        "support_closed": "🔒 مغلق",
        "drop_cancelled": "❌ ملغي",
        "drop_no_items": "⚠️ لا توجد عناصر!",
        "drop_timer_set": "تم تعيين {}!",
        "drop_broadcasting": "🚀 جاري البث {} عناصر إلى {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nحذف تلقائي في {}\nاضغط للمطالبة:",
        "drop_done": "✅ تم البث إلى {}",
        "age_expired": "⏳ منتهي الصلاحية!",
        "age_claimed": "❌ تمت المطالبة به بالفعل!",
        "age_verified": "تم التحقق!",
        "age_denied": "❌ مرفوض. يجب أن يكون 18+",
        "lang_updated": "تم التحديث!",
        "batch_expired": "منتهي الصلاحية",
        "batch_loading": "جاري التحميل...",
        "batch_no_channel": "لا توجد قناة مرتبطة!",
        "batch_setup_prompt": "📦 الإعداد: اجعل البوت مسؤولاً في القناة وأعد توجيه رسالة إلى هنا",
        "batch_mode_activated": "تم تفعيل الوضع!",
        "batch_change_dest": "🔄 **تغيير قناة الوجهة**\nاجعل البوت مسؤولاً في القناة الجديدة، ثم أعد توجيه رسالة إلى هنا.",
        "join_channel_first_alert": "انضم للقناة أولاً! 📢 يجب الانضمام!",
        "join_channel_first": "انضم للقناة أولاً! 📢",
        "watch_timer_first": "⏰ افتح الرابط وشاهد المؤقت لمدة 20 ثانية أولاً!",
        "test_ad_verified": "✅ تم التحقق من إعلان الاختبار! +1",
        "test_ad_verified_msg": "✅ **تم التحقق من إعلان الاختبار!**\nالمكافأة: تم إعادة تعبئة +1 تحميل!",
        "finish_timer_first": "⏰ أنهٍ مؤقت 20 ثانية أولاً!",
        "verified_added": "تم التحقق! تمت إضافة +1",
        "resume_prompt": "✅ تم التحقق! تمت إعادة التعبئة +1. استئناف؟",
        "refilled_download": "✅ تمت إعادة التعبئة +1! حمل مرة أخرى.",
        "fetching_bundle": "✅ تم التحقق! جاري جلب الحزمة...",
        "outdated_button": "هذا الزر قديم. أرسل رابطك مرة أخرى.",
        "stopping": "جاري الإيقاف...",
        "stopped": "🛑 تم الإيقاف",
        "resuming": "جاري الاستئناف...",
        "checking_vault": "جاري فحص الخزنة وحمل الخادم...",
        "server_busy": "⏳ **الخادم مشغول**\nنشط: {}/{}\nحر: {} ميجابايت\nقائمة الانتظار: #{}\nسيبدأ تلقائياً!",
        "simulated": "🛠 تمت المحاكاة! اضغط الآن على تحقق واحصل على +1",
        "server_unreachable": "❌ الخادم غير متاح",
        "monetag_failed_twice": "أكمل محاولتين فاشلتين لـ Monetag أولاً.",
        "monetag_fallback_prompt": "🌐 فشل Monetag مرتين. تابع مع Adsterra:",
        "adsterra_ready": "بديل Adsterra جاهز",
        "finish_monetag": "📺 أنهٍ إعلان Monetag في التطبيق المصغر، ثم تحقق مرة أخرى.",
        "monetag_failed_use_adsterra": "فشل Monetag مرتين. استخدم بديل Adsterra أدناه.",
        "ad_link_expired": "انتهت صلاحية رابط الإعلان. أرسل رابطك مرة أخرى.",
        "ad_verified_added": "✅ تم التحقق من الإعلان! تمت إضافة +{}",
        "test_ad_completed": "✅ تم التحقق من إعلان الاختبار\nتم اعتماد المكافأة: +{} تحميل.",
        "sponsor_viewed": "✅ تمت مشاهدة الراعي! تمت إضافة +{}",
        "refilled_send_again": "✅ تمت إعادة التعبئة +{}! أرسل رابطك مرة أخرى.",
        "queued": "⏳ في قائمة الانتظار #{}",
        "banned": "🚫 أنت محظور.",
        "no_links": "❌ لم يتم العثور على روابط.",
        "batch_count": "📦 دفعة {} روابط",
        "restore_invalid_json": "❌ فشل الاستعادة: **{}** ليس JSON صالحاً.",
        "restore_failed": "❌ فشل الاستعادة: {}",
        "restore_success": "✅ **نجاح الاستعادة!**\nالملف: **{}**\nتمت استعادة **{}** إدخالات.",
        "admin_edit_welcome_prompt": "✏️ أرسل رسالة الترحيب الجديدة. استخدم `{bot_name}` لاسم مستخدم البوت.",
        "admin_welcome_updated": "✅ تم تحديث رسالة الترحيب!",
        "menu_edit_welcome": "✏️ تحرير رسالة الترحيب",
        "cached_instant_video": "⚡ ذاكرة تخزين مؤقت فورية [{}] {} {}",
        "cached_instant_audio": "⚡ **ذاكرة تخزين مؤقت فورية** `{}`",
        "cached_instant_image": "⚡ **ذاكرة تخزين مؤقت فورية** `{}`",
        "auto_delete_9m": "⏳ حذف تلقائي في 9 دقائق",
        "download_success": "✅ تم التحميل بنجاح!"
    },
    "ru": {
        "welcome": "🚀 **ДОБРО ПОЖАЛОВАТЬ В MICHAELBBC VAULT - УНИВЕРСАЛЬНЫЙ ЗАГРУЗЧИК!**\n\n🔥 ЧТО Я УМЕЮ:\n🎬 ВИДЕО HD Без Водяных Знаков!\n🎵 АУДИО MP3 192kbps!\n🖼️ ИЗОБРАЖЕНИЯ Скачивание ВСЕХ!\n📝 СУБТИТРЫ Авто!\n📦 ПАКЕТЫ 100+ Ссылок!\n⚡ КЭШ 1 Сек!\n💎 ХРАНИЛИЩЕ Навсегда!\n📤 ЗАГРУЗКА ФАЙЛОВ!\n🔗 ФАЙЛ-В-ССЫЛКУ: Создавайте ссылки для обмена!\n\n👉 ВСТАВЬТЕ ССЫЛКУ, ЧТОБЫ НАЧАТЬ! 👇",
        "btn_video": "🎬 Видео (MP4)", "btn_audio": "🎵 Аудио (MP3)", "btn_image": "🖼️ Изображения", "btn_sub": "📝 Субтитры (SRT)",
        "ask_format": "👇 **ОТЛИЧНО! Какой формат вы хотите? Выберите ниже!**",
        "fetching": "📥 **Получение вашего {}... Подождите! ⏳✨**",
        "error_generic": "❌ Ой! Ошибка! 😢 Ссылка приватная/заблокирована. Попробуйте публичную!",
        "error_50mb": "❌ Слишком большой! 😅 Это видео больше 300 МБ. Попробуйте короче!", 
        "error_no_img": "❌ Изображения не найдены! 😢 Попробуйте другую ссылку!",
        "images_received": "⏳ **Получено {} изображений.**",
        "select_lang": "🌍 Выберите ваш язык! Выберите ниже! 👇", 
        "lang_set": "✅ Язык установлен! Наслаждайтесь! 🎉✨",
        "batch_detected": "📦 **Обнаружен пакет ({} ссылок)**\nКакой формат?",
        "batch_dest": "📦 **Куда отправить?**",
        "btn_chat": "📥 В чат", "btn_chan": "📢 В канал",
        "limit_reached": "⚠️ **Лимит достигнут!** Вы использовали 4 БЕСПЛАТНЫХ! Посмотрите 20-сек рекламу → Получите +1 загрузку!",
        "refill_btn": "🔓 Открыть ссылку и пополнить +1",
        "join_btn": "📢 Присоединиться к каналу", "check_btn": "💜 Проверить баланс",
        "limit_batch": "⚠️ **Лимит пакета достигнут на {} из {}**\nПосмотрите 20-сек рекламу → +1 загрузка для продолжения.",
        "batch_start": "📦 **Пакет запущен:** {} **{} файлов**\n⏳ Обработка...",
        "batch_done": "🏁 **Готово!** ✅ {} ❌ {}\n📥 {} файлов здесь.",
        "batch_done_chan": "🏁 **Готово!** ✅ {} ❌ {}\n📢 {} файлов переслано!",
        "dl_video": "📥 Загрузка видео...", "dl_audio": "📥 Извлечение аудио...", "dl_image": "📥 Скачивание изображений...", "dl_sub": "📥 Получение субтитров...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Заблокировано/приватно", "failed_generic": "❌ Ошибка",
        "menu_lang": "🌍 Язык", "menu_stats": "📊 Моя статистика", "menu_help": "💬 Поддержка / FAQ", "menu_join": "📢 Присоединиться к каналу",
        "menu_uploads": "🍿 Загрузки фанатов", "menu_upload": "📤 Загрузить файл",
        "admin_upload_prompt": "📂 **Входящие загрузки фанатов**",
        "user_upload_prompt": "📤 **Загрузить файл**\nОтправьте видео/изображение/файл Админу. Лимит 5/24ч.",
        "upload_success_user": "✅ Отправлено Админу!",
        "upload_limit_reached": "⚠️ Достигнут лимит загрузок 5/24ч.",
        "no_uploads": "📭 Загрузок пока нет.",
        "stats_msg": "📊 **Ваша статистика:**\n• Осталось загрузок: {}\n• Осталось пакетов: {}",
        "change_channel_prompt": "🔄 **Изменить канал для пакетов**\n1. Убедитесь, что я админ в новом канале.\n2. Перешлите любое сообщение из этого канала сюда.",
        "disk_config_prompt": "💾 **Настройка диска**\nТекущий мин. свободный диск: **{} МБ**\nЧтобы изменить: `/setdisk <значение>`",
        "mtproto_config_prompt": "⚡ **Настройка MTProto**\nТекущий макс. размер загрузки: **{} МБ**\nЧтобы изменить: `/setmtproto <значение>`",
        "free_panel_prompt": "📦 БЕСПЛАТНЫЕ ЗАГРУЗКИ\nТекущие бесплатные в день: {}",
        "reward_panel_prompt": "🎁 ПАНЕЛЬ НАГРАД\nТекущая: +{} загрузка за 20-сек рекламу",
        "ad_panel_prompt": "⚙️ Панель рекламы\nТекущая: {}",
        "password_saved": "🔐 Пароль сохранен.",
        "password_too_long": "Пароль должен быть не более 64 символов.",
        "file_to_link_prompt": "🔗 **Файл-в-ссылку**\nОтправьте файл(ы), которыми хотите поделиться.",
        "link_invalid_expired": "❌ Эта ссылка недействительна или истекла.",
        "link_limit_reached": "⛔ Эта ссылка достигла лимита использования.",
        "link_password_protected": "🔐 Эта ссылка защищена паролем. Отправьте пароль.",
        "files_sent": "✅ Ваши файлы отправлены.",
        "file_added": "📥 Добавлен файл #{}. Отправьте еще или нажмите Создать ссылку.",
        "fl_cancelled": "Файл-в-ссылку отменен",
        "fl_start_again": "Начните Файл-в-ссылку заново с /filetolink",
        "fl_choose_expiry": "Выберите срок действия ссылки:",
        "fl_expiry_updated": "Срок действия обновлен",
        "fl_choose_max_uses": "Выберите макс. количество успешных доставок:",
        "fl_uses_updated": "Лимит использования обновлен",
        "fl_set_password": "Отправьте пароль или /clearpassword для удаления.",
        "fl_link_created": "Ссылка создана",
        "fl_link_ready": "🔗 Ваша ссылка готова:\n{}\nФайлов: {}\nСтоимость: 1 бесплатная загрузка в день",
        "fl_daily_limit": "Дневной бесплатный лимит достигнут. Посмотрите рекламу, чтобы заработать больше.",
        "fl_ad_busy": "⚠️ Рекламный сервер занят.",
        "admin_skipped": "✅ Пропущено!",
        "admin_bypassed": "✅ Обойдено",
        "free_set": "✅ Бесплатно установлено на {}!",
        "free_updated": "✅ Бесплатные загрузки обновлены до {}!",
        "reward_set": "✅ Награда установлена на +{}!",
        "reward_updated": "✅ Награда обновлена до +{}!",
        "mode_updated": "✅ Режим: {}",
        "support_opened": "✍️ Отправьте сообщение/фото/видео/файл ниже.",
        "admin_reply_mode": "✍️ Ответить {}:",
        "user_reply_mode": "✍️ Введите продолжение ниже",
        "support_closed": "🔒 Закрыто",
        "drop_cancelled": "❌ Отменено",
        "drop_no_items": "⚠️ Нет элементов!",
        "drop_timer_set": "{} установлено!",
        "drop_broadcasting": "🚀 Трансляция {} элементов для {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nАвтоудаление через {}\nНажмите, чтобы забрать:",
        "drop_done": "✅ Трансляция выполнена для {}",
        "age_expired": "⏳ Истекло!",
        "age_claimed": "❌ Уже забрано!",
        "age_verified": "Проверено!",
        "age_denied": "❌ Отказано. Должно быть 18+",
        "lang_updated": "Обновлено!",
        "batch_expired": "Истекло",
        "batch_loading": "Загрузка...",
        "batch_no_channel": "Канал не привязан!",
        "batch_setup_prompt": "📦 Настройка: Сделайте бота админом в канале и перешлите сообщение сюда",
        "batch_mode_activated": "Режим активирован!",
        "batch_change_dest": "🔄 **Изменить канал назначения**\nСделайте бота админом в новом канале, затем перешлите сообщение сюда.",
        "join_channel_first_alert": "Сначала присоединитесь к каналу! 📢 Обязательно!",
        "join_channel_first": "Сначала присоединитесь к каналу! 📢",
        "watch_timer_first": "⏰ Сначала откройте ссылку и посмотрите 20-сек таймер!",
        "test_ad_verified": "✅ Тестовая реклама проверена! +1",
        "test_ad_verified_msg": "✅ **ТЕСТОВАЯ РЕКЛАМА ПРОВЕРЕНА!**\nНаграда: +1 загрузка пополнена!",
        "finish_timer_first": "⏰ Сначала завершите 20-сек таймер!",
        "verified_added": "Проверено! +1 добавлено",
        "resume_prompt": "✅ Проверено! Пополнено +1. Возобновить?",
        "refilled_download": "✅ Пополнено +1! Загрузите снова.",
        "fetching_bundle": "✅ Проверено! Получение пакета...",
        "outdated_button": "Эта кнопка устарела. Отправьте ссылку снова.",
        "stopping": "Остановка...",
        "stopped": "🛑 Остановлено",
        "resuming": "Возобновление...",
        "checking_vault": "Проверка хранилища и нагрузки сервера...",
        "server_busy": "⏳ **Сервер занят**\nАктивных: {}/{}\nСвободно: {} МБ\nОчередь: #{}\nЗапустится автоматически!",
        "simulated": "🛠 Симулировано! Теперь нажмите Проверить и получить +1",
        "server_unreachable": "❌ Сервер недоступен",
        "monetag_failed_twice": "Сначала завершите две неудачные попытки Monetag.",
        "monetag_fallback_prompt": "🌐 Monetag не сработал дважды. Продолжить с Adsterra:",
        "adsterra_ready": "Резервный вариант Adsterra готов",
        "finish_monetag": "📺 Завершите рекламу Monetag в Mini App, затем проверьте снова.",
        "monetag_failed_use_adsterra": "Monetag не сработал дважды. Используйте резервный вариант Adsterra ниже.",
        "ad_link_expired": "Срок действия рекламной ссылки истек. Отправьте ссылку снова.",
        "ad_verified_added": "✅ Реклама проверена! +{} добавлено",
        "test_ad_completed": "✅ ТЕСТОВАЯ РЕКЛАМА ПРОВЕРЕНА\nНаграда начислена: +{} загрузка.",
        "sponsor_viewed": "✅ Спонсор просмотрен! +{} добавлено",
        "refilled_send_again": "✅ Пополнено +{}! Отправьте ссылку снова.",
        "queued": "⏳ В очереди #{}",
        "banned": "🚫 Вы заблокированы.",
        "no_links": "❌ Ссылки не найдены.",
        "batch_count": "📦 Пакет {} ссылок",
        "restore_invalid_json": "❌ Ошибка восстановления: **{}** не является допустимым JSON.",
        "restore_failed": "❌ Ошибка восстановления: {}",
        "restore_success": "✅ **Восстановление успешно!**\nФайл: **{}**\nВосстановлено **{}** записей.",
        "admin_edit_welcome_prompt": "✏️ Отправьте новое приветственное сообщение. Используйте `{bot_name}` для имени пользователя бота.",
        "admin_welcome_updated": "✅ Приветственное сообщение обновлено!",
        "menu_edit_welcome": "✏️ Изменить приветственное сообщение",
        "cached_instant_video": "⚡ Мгновенный кэш [{}] {} {}",
        "cached_instant_audio": "⚡ **Мгновенный кэш** `{}`",
        "cached_instant_image": "⚡ **Мгновенный кэш** `{}`",
        "auto_delete_9m": "⏳ Автоудаление через 9 мин",
        "download_success": "✅ Загрузка успешна!"
    },
    "pt": {
        "welcome": "🚀 **BEM-VINDO AO MICHAELBBC VAULT - BAIXADOR DE MÍDIA COMPLETO!**\n\n🔥 O QUE POSSO FAZER:\n🎬 VÍDEOS HD Sem Marca D'água!\n🎵 ÁUDIO MP3 192kbps!\n🖼️ IMAGENS Extração TOTAL!\n📝 LEGENDAS Auto!\n📦 LOTES 100+ Links!\n⚡ CACHE 1 Seg!\n💎 COFRE Para Sempre!\n📤 ENVIAR ARQUIVOS!\n🔗 ARQUIVO-PARA-LINK: Crie links compartilháveis!\n\n👉 COLE UM LINK PARA COMEÇAR! 👇",
        "btn_video": "🎬 Vídeo (MP4)", "btn_audio": "🎵 Áudio (MP3)", "btn_image": "🖼️ Imagens", "btn_sub": "📝 Legendas (SRT)",
        "ask_format": "👇 **INCRÍVEL! Qual formato você quer? Escolha abaixo!**",
        "fetching": "📥 **Buscando seu {}... Aguarde! ⏳✨**",
        "error_generic": "❌ Ops! Falhou! 😢 Link privado/bloqueado. Tente um link público!",
        "error_50mb": "❌ Muito grande! 😅 Este vídeo tem mais de 300MB. Tente um mais curto!", 
        "error_no_img": "❌ Nenhuma imagem encontrada! 😢 Tente outro link!",
        "images_received": "⏳ **{} Imagens recebidas.**",
        "select_lang": "🌍 Selecione seu idioma! Escolha abaixo! 👇", 
        "lang_set": "✅ Idioma definido! Aproveite! 🎉✨",
        "batch_detected": "📦 **Lote Detectado ({} links)**\nQual formato?",
        "batch_dest": "📦 **Para onde enviar?**",
        "btn_chat": "📥 No Chat", "btn_chan": "📢 Para o Canal",
        "limit_reached": "⚠️ **Limite Atingido!** Você usou 4 GRÁTIS! Assista a um anúncio de 20s → Ganhe +1 download!",
        "refill_btn": "🔓 Abrir Link e Recarregar +1",
        "join_btn": "📢 Entrar no Canal", "check_btn": "💜 Verificar Saldo",
        "limit_batch": "⚠️ **Limite do Lote Atingido em {} de {}**\nAssista a um anúncio de 20s → +1 download para continuar.",
        "batch_start": "📦 **Lote Iniciado:** {} **{} arquivos**\n⏳ Processando...",
        "batch_done": "🏁 **Concluído!** ✅ {} ❌ {}\n📥 {} arquivos aqui.",
        "batch_done_chan": "🏁 **Concluído!** ✅ {} ❌ {}\n📢 {} arquivos encaminhados!",
        "dl_video": "📥 Baixando vídeo...", "dl_audio": "📥 Extraindo áudio...", "dl_image": "📥 Extraindo imagens...", "dl_sub": "📥 Buscando legendas...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Bloqueado/privado", "failed_generic": "❌ Falhou",
        "menu_lang": "🌍 Idioma", "menu_stats": "📊 Minhas Estatísticas", "menu_help": "💬 Suporte / FAQ", "menu_join": "📢 Entrar no Canal",
        "menu_uploads": "🍿 Envios de Fãs", "menu_upload": "📤 Enviar Arquivo",
        "admin_upload_prompt": "📂 **Caixa de Entrada de Envios de Fãs**",
        "user_upload_prompt": "📤 **Enviar Arquivo**\nEnvie vídeo/imagem/arquivo para o Admin. Limite 5/24h.",
        "upload_success_user": "✅ Enviado para o Admin!",
        "upload_limit_reached": "⚠️ Limite de envios 5/24h atingido.",
        "no_uploads": "📭 Nenhum envio ainda.",
        "stats_msg": "📊 **Suas Estatísticas:**\n• Downloads Restantes: {}\n• Lotes Restantes: {}",
        "change_channel_prompt": "🔄 **Alterar Canal de Lotes**\n1. Certifique-se de que sou admin no novo canal.\n2. Encaminhe qualquer mensagem desse canal para cá.",
        "disk_config_prompt": "💾 **Config de Disco**\nMínimo de disco livre atual: **{}MB**\nPara alterar: `/setdisk <valor>`",
        "mtproto_config_prompt": "⚡ **Config MTProto**\nMax de upload atual: **{}MB**\nPara alterar: `/setmtproto <valor>`",
        "free_panel_prompt": "📦 DOWNLOADS GRÁTIS\nGrátis atuais por dia: {}",
        "reward_panel_prompt": "🎁 PAINEL DE RECOMPENSAS\nAtual: +{} download por anúncio de 20s",
        "ad_panel_prompt": "⚙️ Painel de Anúncios\nAtual: {}",
        "password_saved": "🔐 Senha salva.",
        "password_too_long": "A senha deve ter 64 caracteres ou menos.",
        "file_to_link_prompt": "🔗 **Arquivo-para-Link**\nEnvie o(s) arquivo(s) que deseja compartilhar.",
        "link_invalid_expired": "❌ Este link é inválido ou expirou.",
        "link_limit_reached": "⛔ Este link atingiu seu limite de uso.",
        "link_password_protected": "🔐 Este link está protegido por senha. Envie a senha.",
        "files_sent": "✅ Seus arquivos foram enviados.",
        "file_added": "📥 Arquivo #{} adicionado. Envie mais ou toque em Criar Link.",
        "fl_cancelled": "Arquivo-para-Link cancelado",
        "fl_start_again": "Inicie Arquivo-para-Link novamente com /filetolink",
        "fl_choose_expiry": "Escolha a expiração do link:",
        "fl_expiry_updated": "Expiração atualizada",
        "fl_choose_max_uses": "Escolha o máximo de entregas bem-sucedidas:",
        "fl_uses_updated": "Limite de uso atualizado",
        "fl_set_password": "Envie uma senha ou /clearpassword para remover.",
        "fl_link_created": "Link criado",
        "fl_link_ready": "🔗 Seu link está pronto:\n{}\nArquivos: {}\nCusto: 1 download diário grátis",
        "fl_daily_limit": "Limite diário grátis atingido. Assista a um anúncio para ganhar mais.",
        "fl_ad_busy": "⚠️ Servidor de anúncios ocupado.",
        "admin_skipped": "✅ Ignorado!",
        "admin_bypassed": "✅ Ignorado",
        "free_set": "✅ Grátis definido para {}!",
        "free_updated": "✅ Downloads Grátis atualizados para {}!",
        "reward_set": "✅ Recompensa definida para +{}!",
        "reward_updated": "✅ Recompensa atualizada para +{}!",
        "mode_updated": "✅ Modo: {}",
        "support_opened": "✍️ Envie mensagem/foto/vídeo/arquivo abaixo.",
        "admin_reply_mode": "✍️ Responder a {}:",
        "user_reply_mode": "✍️ Digite o acompanhamento abaixo",
        "support_closed": "🔒 Fechado",
        "drop_cancelled": "❌ Cancelado",
        "drop_no_items": "⚠️ Sem itens!",
        "drop_timer_set": "{} definido!",
        "drop_broadcasting": "🚀 Transmitindo {} itens para {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nAuto-exclui em {}\nToque para reivindicar:",
        "drop_done": "✅ Transmissão feita para {}",
        "age_expired": "⏳ Expirado!",
        "age_claimed": "❌ Já reivindicado!",
        "age_verified": "Verificado!",
        "age_denied": "❌ Negado. Deve ser 18+",
        "lang_updated": "Atualizado!",
        "batch_expired": "Expirado",
        "batch_loading": "Carregando...",
        "batch_no_channel": "Nenhum canal vinculado!",
        "batch_setup_prompt": "📦 Configuração: Torne o bot admin no canal e encaminhe uma mensagem aqui",
        "batch_mode_activated": "Modo ativado!",
        "batch_change_dest": "🔄 **Alterar Canal de Destino**\nTorne o bot admin no novo canal, depois encaminhe uma mensagem aqui.",
        "join_channel_first_alert": "Entre no canal primeiro! 📢 Deve entrar!",
        "join_channel_first": "Entre no canal primeiro! 📢",
        "watch_timer_first": "⏰ Abra o link e assista ao temporizador de 20s primeiro!",
        "test_ad_verified": "✅ Anúncio de Teste Verificado! +1",
        "test_ad_verified_msg": "✅ **ANÚNCIO DE TESTE VERIFICADO!**\nRecompensa: +1 download recarregado!",
        "finish_timer_first": "⏰ Termine o temporizador de 20s primeiro!",
        "verified_added": "Verificado! +1 adicionado",
        "resume_prompt": "✅ Verificado! Recarregado +1. Retomar?",
        "refilled_download": "✅ Recarregado +1! Baixe novamente.",
        "fetching_bundle": "✅ Verificado! Buscando pacote...",
        "outdated_button": "Este botão está desatualizado. Envie seu link novamente.",
        "stopping": "Parando...",
        "stopped": "🛑 Parado",
        "resuming": "Retomando...",
        "checking_vault": "Verificando cofre e carga do servidor...",
        "server_busy": "⏳ **Servidor Ocupado**\nAtivos: {}/{}\nLivre: {}MB\nFila: #{}\nIniciará auto!",
        "simulated": "🛠 Simulado! Agora toque em Verificar e Obter +1",
        "server_unreachable": "❌ Servidor inacessível",
        "monetag_failed_twice": "Complete duas tentativas falhas de Monetag primeiro.",
        "monetag_fallback_prompt": "🌐 Monetag falhou duas vezes. Continue com Adsterra:",
        "adsterra_ready": "Fallback de Adsterra pronto",
        "finish_monetag": "📺 Termine o anúncio Monetag no Mini App, depois verifique.",
        "monetag_failed_use_adsterra": "Monetag falhou duas vezes. Use o fallback de Adsterra abaixo.",
        "ad_link_expired": "Link de anúncio expirado. Envie seu link novamente.",
        "ad_verified_added": "✅ Anúncio verificado! +{} adicionado",
        "test_ad_completed": "✅ ANÚNCIO DE TESTE VERIFICADO\nRecompensa creditada: +{} download.",
        "sponsor_viewed": "✅ Patrocinador visto! +{} adicionado",
        "refilled_send_again": "✅ Recarregado +{}! Envie seu link novamente.",
        "queued": "⏳ Na fila #{}",
        "banned": "🚫 Você está banido.",
        "no_links": "❌ Nenhum link encontrado.",
        "batch_count": "📦 Lote {} links",
        "restore_invalid_json": "❌ Falha na restauração: **{}** não é JSON válido.",
        "restore_failed": "❌ Falha na restauração: {}",
        "restore_success": "✅ **Restauração Bem-sucedida!**\nArquivo: **{}**\nRestauradas **{}** entradas.",
        "admin_edit_welcome_prompt": "✏️ Envie a nova Mensagem de Boas-vindas. Use `{bot_name}` para o nome de usuário.",
        "admin_welcome_updated": "✅ Mensagem de boas-vindas atualizada!",
        "menu_edit_welcome": "✏️ Editar Mensagem de Boas-vindas",
        "cached_instant_video": "⚡ Cache Instantâneo [{}] {} {}",
        "cached_instant_audio": "⚡ **Cache Instantâneo** `{}`",
        "cached_instant_image": "⚡ **Cache Instantâneo** `{}`",
        "auto_delete_9m": "⏳ Auto-exclui em 9 mins",
        "download_success": "✅ Download bem-sucedido!"
    },
    "id": {
        "welcome": "🚀 **SELAMAT DATANG DI MICHAELBBC VAULT - PENGUNDUH MEDIA LENGKAP!**\n\n🔥 APA YANG BISA SAYA LAKUKAN:\n🎬 VIDEO HD Tanpa Watermark!\n🎵 AUDIO MP3 192kbps!\n🖼️ GAMBAR Ekstraksi SEMUA!\n📝 SUBTITLE Otomatis!\n📦 BATCH 100+ Link!\n⚡ CACHE 1 Detik!\n💎 BRANKAS Selamanya!\n📤 UNGGAH FILE!\n🔗 FILE-KE-LINK: Buat link yang bisa dibagikan!\n\n👉 TEMPEL LINK UNTUK MEMULAI! 👇",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Gambar", "btn_sub": "📝 Subtitle (SRT)",
        "ask_format": "👇 **KEREN! Format apa yang Anda inginkan? Pilih di bawah!**",
        "fetching": "📥 **Mengambil {} Anda... Tunggu sebentar! ⏳✨**",
        "error_generic": "❌ Ups! Gagal! 😢 Link pribadi/diblokir. Coba link publik!",
        "error_50mb": "❌ Terlalu besar! 😅 Video ini lebih dari 300MB. Coba yang lebih pendek!", 
        "error_no_img": "❌ Tidak ada gambar ditemukan! 😢 Coba link lain!",
        "images_received": "⏳ **{} Gambar diterima.**",
        "select_lang": "🌍 Pilih bahasa Anda! Pilih di bawah! 👇", 
        "lang_set": "✅ Bahasa diatur! Nikmati! 🎉✨",
        "batch_detected": "📦 **Batch Terdeteksi ({} link)**\nFormat apa?",
        "batch_dest": "📦 **Kirim ke mana?**",
        "btn_chat": "📥 Di Chat", "btn_chan": "📢 Ke Channel",
        "limit_reached": "⚠️ **Batas Tercapai!** Anda menggunakan 4 GRATIS! Tonton iklan 20d → Dapatkan +1 unduhan!",
        "refill_btn": "🔓 Buka Link & Isi Ulang +1",
        "join_btn": "📢 Gabung Channel", "check_btn": "💜 Cek Saldo",
        "limit_batch": "⚠️ **Batas Batch Tercapai pada {} dari {}**\nTonton iklan 20d → +1 unduhan untuk melanjutkan.",
        "batch_start": "📦 **Batch Dimulai:** {} **{} file**\n⏳ Memproses...",
        "batch_done": "🏁 **Selesai!** ✅ {} ❌ {}\n📥 {} file di sini.",
        "batch_done_chan": "🏁 **Selesai!** ✅ {} ❌ {}\n📢 {} file diteruskan!",
        "dl_video": "📥 Mengunduh video...", "dl_audio": "📥 Mengekstrak audio...", "dl_image": "📥 Mengekstrak gambar...", "dl_sub": "📥 Mengambil subtitle...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Diblokir/pribadi", "failed_generic": "❌ Gagal",
        "menu_lang": "🌍 Bahasa", "menu_stats": "📊 Statistik Saya", "menu_help": "💬 Dukungan / FAQ", "menu_join": "📢 Gabung Channel",
        "menu_uploads": "🍿 Unggahan Penggemar", "menu_upload": "📤 Unggah File",
        "admin_upload_prompt": "📂 **Kotak Masuk Unggahan Penggemar**",
        "user_upload_prompt": "📤 **Unggah File**\nKirim video/gambar/file ke Admin. Batas 5/24jam.",
        "upload_success_user": "✅ Terkirim ke Admin!",
        "upload_limit_reached": "⚠️ Batas unggahan 5/24jam tercapai.",
        "no_uploads": "📭 Belum ada unggahan.",
        "stats_msg": "📊 **Statistik Anda:**\n• Sisa Unduhan: {}\n• Sisa Batch: {}",
        "change_channel_prompt": "🔄 **Ubah Channel Batch**\n1. Pastikan saya adalah admin di channel baru.\n2. Teruskan pesan apa pun dari channel tersebut ke sini.",
        "disk_config_prompt": "💾 **Konfigurasi Disk**\nMin disk bebas saat ini: **{}MB**\nUntuk mengubah: `/setdisk <nilai>`",
        "mtproto_config_prompt": "⚡ **Konfigurasi MTProto**\nMax unggah saat ini: **{}MB**\nUntuk mengubah: `/setmtproto <nilai>`",
        "free_panel_prompt": "📦 UNDUHAN GRATIS\nGratis saat ini per hari: {}",
        "reward_panel_prompt": "🎁 PANEL HADIAH\nSaat ini: +{} unduhan per iklan 20d",
        "ad_panel_prompt": "⚙️ Panel Iklan\nSaat ini: {}",
        "password_saved": "🔐 Kata sandi disimpan.",
        "password_too_long": "Kata sandi harus 64 karakter atau kurang.",
        "file_to_link_prompt": "🔗 **File-ke-Link**\nKirim file yang ingin Anda bagikan.",
        "link_invalid_expired": "❌ Link ini tidak valid atau kedaluwarsa.",
        "link_limit_reached": "⛔ Link ini mencapai batas penggunaan.",
        "link_password_protected": "🔐 Link ini dilindungi kata sandi. Kirim kata sandi.",
        "files_sent": "✅ File Anda telah dikirim.",
        "file_added": "📥 File #{} ditambahkan. Kirim lebih banyak, atau ketuk Buat Link.",
        "fl_cancelled": "File-ke-Link dibatalkan",
        "fl_start_again": "Mulai File-ke-Link lagi dengan /filetolink",
        "fl_choose_expiry": "Pilih kedaluwarsa link:",
        "fl_expiry_updated": "Kedaluwarsa diperbarui",
        "fl_choose_max_uses": "Pilih max pengiriman berhasil:",
        "fl_uses_updated": "Batas penggunaan diperbarui",
        "fl_set_password": "Kirim kata sandi, atau /clearpassword untuk menghapus.",
        "fl_link_created": "Link dibuat",
        "fl_link_ready": "🔗 Link Anda siap:\n{}\nFile: {}\nBiaya: 1 unduhan harian gratis",
        "fl_daily_limit": "Batas harian gratis tercapai. Tonton iklan untuk mendapatkan lebih banyak.",
        "fl_ad_busy": "⚠️ Server iklan sibuk.",
        "admin_skipped": "✅ Dilewati!",
        "admin_bypassed": "✅ Dilewati",
        "free_set": "✅ Gratis diatur ke {}!",
        "free_updated": "✅ Unduhan Gratis diperbarui ke {}!",
        "reward_set": "✅ Hadiah diatur ke +{}!",
        "reward_updated": "✅ Hadiah diperbarui ke +{}!",
        "mode_updated": "✅ Mode: {}",
        "support_opened": "✍️ Kirim pesan/foto/video/file di bawah.",
        "admin_reply_mode": "✍️ Balas ke {}:",
        "user_reply_mode": "✍️ Ketik tindak lanjut di bawah",
        "support_closed": "🔒 Ditutup",
        "drop_cancelled": "❌ Dibatalkan",
        "drop_no_items": "⚠️ Tidak ada item!",
        "drop_timer_set": "{} diatur!",
        "drop_broadcasting": "🚀 Menyiarakan {} item ke {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nHapus otomatis dalam {}\nKetuk untuk klaim:",
        "drop_done": "✅ Siaran selesai ke {}",
        "age_expired": "⏳ Kedaluwarsa!",
        "age_claimed": "❌ Sudah diklaim!",
        "age_verified": "Terverifikasi!",
        "age_denied": "❌ Ditolak. Harus 18+",
        "lang_updated": "Diperbarui!",
        "batch_expired": "Kedaluwarsa",
        "batch_loading": "Memuat...",
        "batch_no_channel": "Tidak ada channel yang ditautkan!",
        "batch_setup_prompt": "📦 Pengaturan: Jadikan bot admin di channel dan teruskan pesan ke sini",
        "batch_mode_activated": "Mode diaktifkan!",
        "batch_change_dest": "🔄 **Ubah Channel Tujuan**\nJadikan bot admin di channel baru, lalu teruskan pesan ke sini.",
        "join_channel_first_alert": "Gabung channel dulu! 📢 Wajib gabung!",
        "join_channel_first": "Gabung channel dulu! 📢",
        "watch_timer_first": "⏰ Buka link dan tonton timer 20d dulu!",
        "test_ad_verified": "✅ Iklan Uji Terverifikasi! +1",
        "test_ad_verified_msg": "✅ **IKLAN UJI TERVERIFIKASI!**\nHadiah: +1 unduhan diisi ulang!",
        "finish_timer_first": "⏰ Selesaikan timer 20d dulu!",
        "verified_added": "Terverifikasi! +1 ditambahkan",
        "resume_prompt": "✅ Terverifikasi! Diisi ulang +1. Lanjutkan?",
        "refilled_download": "✅ Diisi ulang +1! Unduh lagi.",
        "fetching_bundle": "✅ Terverifikasi! Mengambil paket...",
        "outdated_button": "Tombol ini kedaluwarsa. Kirim link Anda lagi.",
        "stopping": "Menghentikan...",
        "stopped": "🛑 Berhenti",
        "resuming": "Melanjutkan...",
        "checking_vault": "Memeriksa brankas & beban server...",
        "server_busy": "⏳ **Server Sibuk**\nAktif: {}/{}\nBebas: {}MB\nAntrian: #{}\nAkan mulai otomatis!",
        "simulated": "🛠 Disimulasikan! Sekarang ketuk Periksa & Dapatkan +1",
        "server_unreachable": "❌ Server tidak dapat dijangkau",
        "monetag_failed_twice": "Selesaikan dua upaya Monetag yang gagal terlebih dahulu.",
        "monetag_fallback_prompt": "🌐 Monetag gagal dua kali. Lanjutkan dengan Adsterra:",
        "adsterra_ready": "Fallback Adsterra siap",
        "finish_monetag": "📺 Selesaikan iklan Monetag di Mini App, lalu periksa lagi.",
        "monetag_failed_use_adsterra": "Monetag gagal dua kali. Gunakan fallback Adsterra di bawah.",
        "ad_link_expired": "Link iklan kedaluwarsa. Kirim link Anda lagi.",
        "ad_verified_added": "✅ Iklan terverifikasi! +{} ditambahkan",
        "test_ad_completed": "✅ IKLAN UJI TERVERIFIKASI\nHadiah dikreditkan: +{} unduhan.",
        "sponsor_viewed": "✅ Sponsor dilihat! +{} ditambahkan",
        "refilled_send_again": "✅ Diisi ulang +{}! Kirim link Anda lagi.",
        "queued": "⏳ Dalam antrian #{}",
        "banned": "🚫 Anda dibanned.",
        "no_links": "❌ Tidak ada link ditemukan.",
        "batch_count": "📦 Batch {} link",
        "restore_invalid_json": "❌ Gagal memulihkan: **{}** bukan JSON yang valid.",
        "restore_failed": "❌ Gagal memulihkan: {}",
        "restore_success": "✅ **Pemulihan Berhasil!**\nFile: **{}**\nDipulihkan **{}** entri.",
        "admin_edit_welcome_prompt": "✏️ Kirim Pesan Selamat Datang baru. Gunakan `{bot_name}` untuk username bot.",
        "admin_welcome_updated": "✅ Pesan selamat datang diperbarui!",
        "menu_edit_welcome": "✏️ Edit Pesan Selamat Datang",
        "cached_instant_video": "⚡ Cache Instan [{}] {} {}",
        "cached_instant_audio": "⚡ **Cache Instan** `{}`",
        "cached_instant_image": "⚡ **Cache Instan** `{}`",
        "auto_delete_9m": "⏳ Hapus otomatis dalam 9 menit",
        "download_success": "✅ Unduhan berhasil!"
    },
    "fr": {
        "welcome": "🚀 **BIENVENUE SUR MICHAELBBC VAULT - TÉLÉCHARGEUR DE MÉDIAS COMPLET!**\n\n🔥 CE QUE JE PEUX FAIRE:\n🎬 VIDÉOS HD Sans Filigrane!\n🎵 AUDIO MP3 192kbps!\n🖼️ IMAGES Extraction TOTALE!\n📝 SOUS-TITRES Auto!\n📦 LOTS 100+ Liens!\n⚡ CACHE 1 Sec!\n💎 COFFRE Pour Toujours!\n📤 TÉLÉVERSER DES FICHIERS!\n🔗 FICHIER-VERS-LIEN: Créez des liens partageables!\n\n👉 COLLEZ UN LIEN POUR COMMENCER! 👇",
        "btn_video": "🎬 Vidéo (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Images", "btn_sub": "📝 Sous-titres (SRT)",
        "ask_format": "👇 **GÉNIAL! Quel format voulez-vous? Choisissez ci-dessous!**",
        "fetching": "📥 **Récupération de votre {}... Patientez! ⏳✨**",
        "error_generic": "❌ Oups! Échec! 😢 Lien privé/bloqué. Essayez un lien public!",
        "error_50mb": "❌ Trop grand! 😅 Cette vidéo dépasse 300 Mo. Essayez une plus courte!", 
        "error_no_img": "❌ Aucune image trouvée! 😢 Essayez un autre lien!",
        "images_received": "⏳ **{} Images reçues.**",
        "select_lang": "🌍 Sélectionnez votre langue! Choisissez ci-dessous! 👇", 
        "lang_set": "✅ Langue définie! Profitez-en! 🎉✨",
        "batch_detected": "📦 **Lot Détecté ({} liens)**\nQuel format?",
        "batch_dest": "📦 **Où envoyer?**",
        "btn_chat": "📥 Dans le Chat", "btn_chan": "📢 Vers le Canal",
        "limit_reached": "⚠️ **Limite Atteinte!** Vous avez utilisé 4 GRATUITS! Regardez une pub de 20s → Obtenez +1 téléchargement!",
        "refill_btn": "🔓 Ouvrir le Lien et Recharger +1",
        "join_btn": "📢 Rejoindre le Canal", "check_btn": "💜 Vérifier le Solde",
        "limit_batch": "⚠️ **Limite du Lot Atteinte à {} sur {}**\nRegardez une pub de 20s → +1 téléchargement pour continuer.",
        "batch_start": "📦 **Lot Démarré:** {} **{} fichiers**\n⏳ Traitement...",
        "batch_done": "🏁 **Terminé!** ✅ {} ❌ {}\n📥 {} fichiers ici.",
        "batch_done_chan": "🏁 **Terminé!** ✅ {} ❌ {}\n📢 {} fichiers transférés!",
        "dl_video": "📥 Téléchargement de la vidéo...", "dl_audio": "📥 Extraction de l'audio...", "dl_image": "📥 Extraction des images...", "dl_sub": "📥 Récupération des sous-titres...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Bloqué/privé", "failed_generic": "❌ Échec",
        "menu_lang": "🌍 Langue", "menu_stats": "📊 Mes Statistiques", "menu_help": "💬 Support / FAQ", "menu_join": "📢 Rejoindre le Canal",
        "menu_uploads": "🍿 Téléversements des Fans", "menu_upload": "📤 Téléverser un Fichier",
        "admin_upload_prompt": "📂 **Boîte de Réception des Téléversements des Fans**",
        "user_upload_prompt": "📤 **Téléverser un Fichier**\nEnvoyez vidéo/image/fichier à l'Admin. Limite 5/24h.",
        "upload_success_user": "✅ Envoyé à l'Admin!",
        "upload_limit_reached": "⚠️ Limite de téléversement 5/24h atteinte.",
        "no_uploads": "📭 Aucun téléversement pour le moment.",
        "stats_msg": "📊 **Vos Statistiques:**\n• Téléchargements Restants: {}\n• Lots Restants: {}",
        "change_channel_prompt": "🔄 **Changer de Canal pour les Lots**\n1. Assurez-vous que je suis admin dans le nouveau canal.\n2. Transférez n'importe quel message de ce canal ici.",
        "disk_config_prompt": "💾 **Config du Disque**\nMin disque libre actuel: **{} Mo**\nPour changer: `/setdisk <valeur>`",
        "mtproto_config_prompt": "⚡ **Config MTProto**\nMax téléversement actuel: **{} Mo**\nPour changer: `/setmtproto <valeur>`",
        "free_panel_prompt": "📦 TÉLÉCHARGEMENTS GRATUITS\nGratuits actuels par jour: {}",
        "reward_panel_prompt": "🎁 PANNEAU DE RÉCOMPENSES\nActuel: +{} téléchargement par pub de 20s",
        "ad_panel_prompt": "⚙️ Panneau des Pubs\nActuel: {}",
        "password_saved": "🔐 Mot de passe enregistré.",
        "password_too_long": "Le mot de passe doit faire 64 caractères ou moins.",
        "file_to_link_prompt": "🔗 **Fichier-vers-Lien**\nEnvoyez le(s) fichier(s) que vous souhaitez partager.",
        "link_invalid_expired": "❌ Ce lien est invalide ou a expiré.",
        "link_limit_reached": "⛔ Ce lien a atteint sa limite d'utilisation.",
        "link_password_protected": "🔐 Ce lien est protégé par mot de passe. Envoyez le mot de passe.",
        "files_sent": "✅ Vos fichiers ont été envoyés.",
        "file_added": "📥 Fichier #{} ajouté. Envoyez-en plus ou appuyez sur Créer un Lien.",
        "fl_cancelled": "Fichier-vers-Lien annulé",
        "fl_start_again": "Recommencez Fichier-vers-Lien avec /filetolink",
        "fl_choose_expiry": "Choisissez l'expiration du lien:",
        "fl_expiry_updated": "Expiration mise à jour",
        "fl_choose_max_uses": "Choisissez le max de livraisons réussies:",
        "fl_uses_updated": "Limite d'utilisation mise à jour",
        "fl_set_password": "Envoyez un mot de passe, ou /clearpassword pour supprimer.",
        "fl_link_created": "Lien créé",
        "fl_link_ready": "🔗 Votre lien est prêt:\n{}\nFichiers: {}\nCoût: 1 téléchargement quotidien gratuit",
        "fl_daily_limit": "Limite quotidienne gratuite atteinte. Regardez une pub pour en gagner plus.",
        "fl_ad_busy": "⚠️ Serveur de publicités occupé.",
        "admin_skipped": "✅ Ignoré!",
        "admin_bypassed": "✅ Contourné",
        "free_set": "✅ Gratuit défini à {}!",
        "free_updated": "✅ Téléchargements Gratuits mis à jour à {}!",
        "reward_set": "✅ Récompense définie à +{}!",
        "reward_updated": "✅ Récompense mise à jour à +{}!",
        "mode_updated": "✅ Mode: {}",
        "support_opened": "✍️ Envoyez message/photo/vidéo/fichier ci-dessous.",
        "admin_reply_mode": "✍️ Répondre à {}:",
        "user_reply_mode": "✍️ Tapez le suivi ci-dessous",
        "support_closed": "🔒 Fermé",
        "drop_cancelled": "❌ Annulé",
        "drop_no_items": "⚠️ Aucun élément!",
        "drop_timer_set": "{} défini!",
        "drop_broadcasting": "🚀 Diffusion de {} éléments à {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nAuto-suppression dans {}\nAppuyez pour réclamer:",
        "drop_done": "✅ Diffusion terminée pour {}",
        "age_expired": "⏳ Expiré!",
        "age_claimed": "❌ Déjà réclamé!",
        "age_verified": "Vérifié!",
        "age_denied": "❌ Refusé. Doit être 18+",
        "lang_updated": "Mis à jour!",
        "batch_expired": "Expiré",
        "batch_loading": "Chargement...",
        "batch_no_channel": "Aucun canal lié!",
        "batch_setup_prompt": "📦 Configuration: Rendez le bot admin dans le canal et transférez un message ici",
        "batch_mode_activated": "Mode activé!",
        "batch_change_dest": "🔄 **Changer de Canal de Destination**\nRendez le bot admin dans le nouveau canal, puis transférez un message ici.",
        "join_channel_first_alert": "Rejoignez le canal d'abord! 📢 Obligatoire!",
        "join_channel_first": "Rejoignez le canal d'abord! 📢",
        "watch_timer_first": "⏰ Ouvrez le lien et regardez le minuteur de 20s d'abord!",
        "test_ad_verified": "✅ Pub de Test Vérifiée! +1",
        "test_ad_verified_msg": "✅ **PUB DE TEST VÉRIFIÉE!**\nRécompense: +1 téléchargement rechargé!",
        "finish_timer_first": "⏰ Terminez le minuteur de 20s d'abord!",
        "verified_added": "Vérifié! +1 ajouté",
        "resume_prompt": "✅ Vérifié! Rechargé +1. Reprendre?",
        "refilled_download": "✅ Rechargé +1! Téléchargez à nouveau.",
        "fetching_bundle": "✅ Vérifié! Récupération du paquet...",
        "outdated_button": "Ce bouton est obsolète. Envoyez votre lien à nouveau.",
        "stopping": "Arrêt...",
        "stopped": "🛑 Arrêté",
        "resuming": "Reprise...",
        "checking_vault": "Vérification du coffre et de la charge du serveur...",
        "server_busy": "⏳ **Serveur Occupé**\nActifs: {}/{}\nLibre: {} Mo\nFile d'attente: #{}\nDémarrage auto!",
        "simulated": "🛠 Simulé! Appuyez maintenant sur Vérifier et Obtenir +1",
        "server_unreachable": "❌ Serveur injoignable",
        "monetag_failed_twice": "Terminez d'abord deux tentatives Monetag échouées.",
        "monetag_fallback_prompt": "🌐 Monetag a échoué deux fois. Continuez avec Adsterra:",
        "adsterra_ready": "Solution de repli Adsterra prête",
        "finish_monetag": "📺 Terminez la pub Monetag dans la Mini App, puis vérifiez à nouveau.",
        "monetag_failed_use_adsterra": "Monetag a échoué deux fois. Utilisez la solution de repli Adsterra ci-dessous.",
        "ad_link_expired": "Lien publicitaire expiré. Envoyez votre lien à nouveau.",
        "ad_verified_added": "✅ Pub vérifiée! +{} ajouté",
        "test_ad_completed": "✅ PUB DE TEST VÉRIFIÉE\nRécompense créditée: +{} téléchargement.",
        "sponsor_viewed": "✅ Sponsor vu! +{} ajouté",
        "refilled_send_again": "✅ Rechargé +{}! Envoyez votre lien à nouveau.",
        "queued": "⏳ En file d'attente #{}",
        "banned": "🚫 Vous êtes banni.",
        "no_links": "❌ Aucun lien trouvé.",
        "batch_count": "📦 Lot {} liens",
        "restore_invalid_json": "❌ Échec de la restauration: **{}** n'est pas un JSON valide.",
        "restore_failed": "❌ Échec de la restauration: {}",
        "restore_success": "✅ **Restauration Réussie!**\nFichier: **{}**\nRestaurées **{}** entrées.",
        "admin_edit_welcome_prompt": "✏️ Envoyez le nouveau Message de Bienvenue. Utilisez `{bot_name}` pour le nom d'utilisateur.",
        "admin_welcome_updated": "✅ Message de bienvenue mis à jour!",
        "menu_edit_welcome": "✏️ Modifier le Message de Bienvenue",
        "cached_instant_video": "⚡ Cache Instantané [{}] {} {}",
        "cached_instant_audio": "⚡ **Cache Instantané** `{}`",
        "cached_instant_image": "⚡ **Cache Instantané** `{}`",
        "auto_delete_9m": "⏳ Auto-suppression dans 9 mins",
        "download_success": "✅ Téléchargement réussi !"
    },
    "tr": {
        "welcome": "🚀 **MICHAELBBC VAULT'A HOŞGELDİNİZ - TAM MEDYA İNDİRİCİ!**\n\n🔥 NE YAPABİLİRİM:\n🎬 VİDEOLAR HD Filigransız!\n🎵 SES MP3 192kbps!\n🖼️ GÖRSELLER Tam Çekim!\n📝 ALTYAZILAR Oto!\n📦 TOPLU 100+ Bağlantı!\n⚡ ÖNBELLEK 1 Sn!\n💎 KASA Sonsuza Kadar!\n📤 DOSYA YÜKLE!\n🔗 DOSYADAN-LİNKE: Paylaşılabilir bağlantılar oluşturun!\n\n👉 BAŞLAMAK İÇİN BAĞLANTI YAPIŞTIRIN! 👇",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Ses (MP3)", "btn_image": "🖼️ Görseller", "btn_sub": "📝 Altyazılar (SRT)",
        "ask_format": "👇 **HARİKA! Hangi formatı istiyorsunuz? Aşağıdan seçin!**",
        "fetching": "📥 **{} getiriliyor... Bekleyin! ⏳✨**",
        "error_generic": "❌ Oops! Başarısız! 😢 Bağlantı özel/engelli. Halka açık bir bağlantı deneyin!",
        "error_50mb": "❌ Çok büyük! 😅 Bu video 300MB'ı aşıyor. Daha kısa bir tane deneyin!", 
        "error_no_img": "❌ Görsel bulunamadı! 😢 Başka bir bağlantı deneyin!",
        "images_received": "⏳ **{} Görsel alındı.**",
        "select_lang": "🌍 Dilinizi seçin! Aşağıdan seçin! 👇", 
        "lang_set": "✅ Dil ayarlandı! Keyfini çıkarın! 🎉✨",
        "batch_detected": "📦 **Toplu İşlem Algılandı ({} bağlantı)**\nHangi format?",
        "batch_dest": "📦 **Nereye gönderilsin?**",
        "btn_chat": "📥 Sohbette", "btn_chan": "📢 Kanala",
        "limit_reached": "⚠️ **Limit Aşıldı!** 4 ÜCRETSİZ kullandınız! 20 sn reklam izleyin → +1 indirme kazanın!",
        "refill_btn": "🔓 Bağlantıyı Aç ve +1 Doldur",
        "join_btn": "📢 Kanala Katıl", "check_btn": "💜 Bakiyeyi Kontrol Et",
        "limit_batch": "⚠️ **Toplu İşlem Limiti {}/{}'de Aşıldı**\n20 sn reklam izleyin → devam etmek için +1 indirme.",
        "batch_start": "📦 **Toplu İşlem Başladı:** {} **{} dosya**\n⏳ İşleniyor...",
        "batch_done": "🏁 **Bitti!** ✅ {} ❌ {}\n📥 Burada {} dosya var.",
        "batch_done_chan": "🏁 **Bitti!** ✅ {} ❌ {}\n📢 {} dosya iletildi!",
        "dl_video": "📥 Video indiriliyor...", "dl_audio": "📥 Ses çıkarılıyor...", "dl_image": "📥 Görseller çekiliyor...", "dl_sub": "📥 Altyazılar getiriliyor...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Engelli/özel", "failed_generic": "❌ Başarısız",
        "menu_lang": "🌍 Dil", "menu_stats": "📊 İstatistiklerim", "menu_help": "💬 Destek / SSS", "menu_join": "📢 Kanala Katıl",
        "menu_uploads": "🍿 Hayran Yüklemeleri", "menu_upload": "📤 Dosya Yükle",
        "admin_upload_prompt": "📂 **Hayran Yüklemeleri Gelen Kutusu**",
        "user_upload_prompt": "📤 **Dosya Yükle**\nYöneticiye video/görsel/dosya gönderin. Limit 5/24s.",
        "upload_success_user": "✅ Yöneticiye gönderildi!",
        "upload_limit_reached": "⚠️ 5/24s yükleme limitine ulaşıldı.",
        "no_uploads": "📭 Henüz yükleme yok.",
        "stats_msg": "📊 **İstatistikleriniz:**\n• Kalan İndirme: {}\n• Kalan Toplu İşlem: {}",
        "change_channel_prompt": "🔄 **Toplu İşlem Kanalını Değiştir**\n1. Yeni kanalda yönetici olduğumdan emin olun.\n2. O kanaldan herhangi bir mesajı buraya iletin.",
        "disk_config_prompt": "💾 **Disk Yapılandırması**\nMevcut min boş disk: **{}MB**\nDeğiştirmek için: `/setdisk <değer>`",
        "mtproto_config_prompt": "⚡ **MTProto Yapılandırması**\nMevcut max yükleme: **{}MB**\nDeğiştirmek için: `/setmtproto <değer>`",
        "free_panel_prompt": "📦 ÜCRETSİZ İNDİRMELER\nGünlük mevcut ücretsiz: {}",
        "reward_panel_prompt": "🎁 ÖDÜL PANELİ\nMevcut: 20 sn reklam başına +{} indirme",
        "ad_panel_prompt": "⚙️ Reklam Paneli\nMevcut: {}",
        "password_saved": "🔐 Şifre kaydedildi.",
        "password_too_long": "Şifre 64 karakter veya daha az olmalıdır.",
        "file_to_link_prompt": "🔗 **Dosyadan-Link**\nPaylaşmak istediğiniz dosya(ları) gönderin.",
        "link_invalid_expired": "❌ Bu bağlantı geçersiz veya süresi dolmuş.",
        "link_limit_reached": "⛔ Bu bağlantı kullanım limitine ulaştı.",
        "link_password_protected": "🔐 Bu bağlantı şifre korumalıdır. Şifreyi gönderin.",
        "files_sent": "✅ Dosyalarınız gönderildi.",
        "file_added": "📥 Dosya #{} eklendi. Daha fazla gönderin veya Bağlantı Oluştur'a dokunun.",
        "fl_cancelled": "Dosyadan-Link iptal edildi",
        "fl_start_again": "/filetolink ile Dosyadan-Link'i yeniden başlatın",
        "fl_choose_expiry": "Bağlantı sona erme süresini seçin:",
        "fl_expiry_updated": "Sona erme güncellendi",
        "fl_choose_max_uses": "Maksimum başarılı teslimat sayısını seçin:",
        "fl_uses_updated": "Kullanım limiti güncellendi",
        "fl_set_password": "Bir şifre gönderin veya kaldırmak için /clearpassword gönderin.",
        "fl_link_created": "Bağlantı oluşturuldu",
        "fl_link_ready": "🔗 Bağlantınız hazır:\n{}\nDosyalar: {}\nMaliyet: 1 ücretsiz günlük indirme",
        "fl_daily_limit": "Günlük ücretsiz limite ulaşıldı. Daha fazlasını kazanmak için reklam izleyin.",
        "fl_ad_busy": "⚠️ Reklam sunucusu meşgul.",
        "admin_skipped": "✅ Atlandı!",
        "admin_bypassed": "✅ Atlatıldı",
        "free_set": "✅ Ücretsiz {} olarak ayarlandı!",
        "free_updated": "✅ Ücretsiz İndirmeler {} olarak güncellendi!",
        "reward_set": "✅ Ödül +{} olarak ayarlandı!",
        "reward_updated": "✅ Ödül +{} olarak güncellendi!",
        "mode_updated": "✅ Mod: {}",
        "support_opened": "✍️ Aşağıya mesaj/fotoğraf/video/dosya gönderin.",
        "admin_reply_mode": "✍️ {} kişisine yanıt ver:",
        "user_reply_mode": "✍️ Aşağıya takip mesajı yazın",
        "support_closed": "🔒 Kapatıldı",
        "drop_cancelled": "❌ İptal edildi",
        "drop_no_items": "⚠️ Öğe yok!",
        "drop_timer_set": "{} ayarlandı!",
        "drop_broadcasting": "🚀 {} öğe {} kişisine yayınlanıyor...",
        "drop_flash_text": "🚨 FLASH DROP!\n{} içinde otomatik silinir\nTalep etmek için dokunun:",
        "drop_done": "✅ {} kişisine yayın tamamlandı",
        "age_expired": "⏳ Süresi doldu!",
        "age_claimed": "❌ Zaten talep edildi!",
        "age_verified": "Doğrulandı!",
        "age_denied": "❌ Reddedildi. 18+ olmalı",
        "lang_updated": "Güncellendi!",
        "batch_expired": "Süresi doldu",
        "batch_loading": "Yükleniyor...",
        "batch_no_channel": "Bağlı kanal yok!",
        "batch_setup_prompt": "📦 Kurulum: Botu kanalda yönetici yapın ve buraya bir mesaj iletin",
        "batch_mode_activated": "Mod etkinleştirildi!",
        "batch_change_dest": "🔄 **Hedef Kanalı Değiştir**\nBotu yeni kanalda yönetici yapın, ardından buraya bir mesaj iletin.",
        "join_channel_first_alert": "Önce kanala katılın! 📢 Katılmalısınız!",
        "join_channel_first": "Önce kanala katılın! 📢",
        "watch_timer_first": "⏰ Önce bağlantıyı açın ve 20 sn'lik zamanlayıcıyı izleyin!",
        "test_ad_verified": "✅ Test Reklamı Doğrulandı! +1",
        "test_ad_verified_msg": "✅ **TEST REKLAMI DOĞRULANDI!**\nÖdül: +1 indirme dolduruldu!",
        "finish_timer_first": "⏰ Önce 20 sn'lik zamanlayıcıyı tamamlayın!",
        "verified_added": "Doğrulandı! +1 eklendi",
        "resume_prompt": "✅ Doğrulandı! +1 dolduruldu. Devam edilsin mi?",
        "refilled_download": "✅ +1 dolduruldu! Tekrar indirin.",
        "fetching_bundle": "✅ Doğrulandı! Paket getiriliyor...",
        "outdated_button": "Bu düğme güncel değil. Bağlantınızı tekrar gönderin.",
        "stopping": "Durduruluyor...",
        "stopped": "🛑 Durduruldu",
        "resuming": "Devam ediliyor...",
        "checking_vault": "Kasa ve sunucu yükü kontrol ediliyor...",
        "server_busy": "⏳ **Sunucu Meşgul**\nAktif: {}/{}\nBoş: {}MB\nKuyruk: #{}\nOtomatik başlayacak!",
        "simulated": "🛠 Simüle edildi! Şimdi Kontrol Et ve +1 Al'a dokunun",
        "server_unreachable": "❌ Sunucuya ulaşılamıyor",
        "monetag_failed_twice": "Önce iki başarısız Monetag denemesini tamamlayın.",
        "monetag_fallback_prompt": "🌐 Monetag iki kez başarısız oldu. Adsterra ile devam edin:",
        "adsterra_ready": "Adsterra yedeklemesi hazır",
        "finish_monetag": "📺 Mini Uygulama'da Monetag reklamını tamamlayın, sonra tekrar kontrol edin.",
        "monetag_failed_use_adsterra": "Monetag iki kez başarısız oldu. Aşağıdaki Adsterra yedeklemesini kullanın.",
        "ad_link_expired": "Reklam bağlantısının süresi doldu. Bağlantınızı tekrar gönderin.",
        "ad_verified_added": "✅ Reklam doğrulandı! +{} eklendi",
        "test_ad_completed": "✅ TEST REKLAMI DOĞRULANDI\nÖdül yatırıldı: +{} indirme.",
        "sponsor_viewed": "✅ Sponsor görüntülendi! +{} eklendi",
        "refilled_send_again": "✅ +{} dolduruldu! Bağlantınızı tekrar gönderin.",
        "queued": "⏳ Kuyrukta #{}",
        "banned": "🚫 Yasaklandınız.",
        "no_links": "❌ Bağlantı bulunamadı.",
        "batch_count": "📦 Toplu {} bağlantı",
        "restore_invalid_json": "❌ Geri yükleme başarısız: **{}** geçerli bir JSON değil.",
        "restore_failed": "❌ Geri yükleme başarısız: {}",
        "restore_success": "✅ **Geri Yükleme Başarılı!**\nDosya: **{}**\n**{}** girdi geri yüklendi.",
        "admin_edit_welcome_prompt": "✏️ Yeni Karşılama Mesajını gönderin. Bot kullanıcı adı için `{bot_name}` kullanın.",
        "admin_welcome_updated": "✅ Karşılama mesajı güncellendi!",
        "menu_edit_welcome": "✏️ Karşılama Mesajını Düzenle",
        "cached_instant_video": "⚡ Anında Önbellek [{}] {} {}",
        "cached_instant_audio": "⚡ **Anında Önbellek** `{}`",
        "cached_instant_image": "⚡ **Anında Önbellek** `{}`",
        "auto_delete_9m": "⏳ 9 dakikada otomatik silinir",
        "download_success": "✅ İndirme başarılı!"
    },
    "de": {
        "welcome": "🚀 **WILLKOMMEN IM MICHAELBBC VAULT - ALL-IN-ONE MEDIA DOWNLOADER!**\n\n🔥 WAS ICH KANN:\n🎬 VIDEOS HD Ohne Wasserzeichen!\n🎵 AUDIO MP3 192kbps!\n🖼️ BILDER Komplett Extrahiert!\n📝 UNTERTITEL Auto!\n📦 STAPEL 100+ Links!\n⚡ CACHE 1 Sek!\n💎 TRESOR Für Immer!\n📤 DATEIEN HOCHLADEN!\n🔗 DATEI-ZU-LINK: Erstelle teilbare Links!\n\n👉 FÜGE EINEN LINK EIN, UM ZU STARTEN! 👇",
        "btn_video": "🎬 Video (MP4)", "btn_audio": "🎵 Audio (MP3)", "btn_image": "🖼️ Bilder", "btn_sub": "📝 Untertitel (SRT)",
        "ask_format": "👇 **TOLL! Welches Format möchtest du? Wähle unten!**",
        "fetching": "📥 **Dein {} wird abgerufen... Warte kurz! ⏳✨**",
        "error_generic": "❌ Oops! Fehlgeschlagen! 😢 Link privat/gesperrt. Versuche einen öffentlichen Link!",
        "error_50mb": "❌ Zu groß! 😅 Dieses Video ist über 300MB. Versuche ein kürzeres!", 
        "error_no_img": "❌ Keine Bilder gefunden! 😢 Versuche einen anderen Link!",
        "images_received": "⏳ **{} Bilder erhalten.**",
        "select_lang": "🌍 Wähle deine Sprache! Wähle unten! 👇", 
        "lang_set": "✅ Sprache eingestellt! Viel Spaß! 🎉✨",
        "batch_detected": "📦 **Stapel erkannt ({} Links)**\nWelches Format?",
        "batch_dest": "📦 **Wohin senden?**",
        "btn_chat": "📥 Im Chat", "btn_chan": "📢 An Kanal",
        "limit_reached": "⚠️ **Limit erreicht!** Du hast 4 KOSTENLOSE genutzt! Schau 20s Werbung → Erhalte +1 Download!",
        "refill_btn": "🔓 Link öffnen & +1 auffüllen",
        "join_btn": "📢 Kanal beitreten", "check_btn": "💜 Guthaben prüfen",
        "limit_batch": "⚠️ **Stapel-Limit bei {} von {} erreicht**\nSchau 20s Werbung → +1 Download um fortzufahren.",
        "batch_start": "📦 **Stapel gestartet:** {} **{} Dateien**\n⏳ Wird verarbeitet...",
        "batch_done": "🏁 **Fertig!** ✅ {} ❌ {}\n📥 {} Dateien hier.",
        "batch_done_chan": "🏁 **Fertig!** ✅ {} ❌ {}\n📢 {} Dateien weitergeleitet!",
        "dl_video": "📥 Video wird heruntergeladen...", "dl_audio": "📥 Audio wird extrahiert...", "dl_image": "📥 Bilder werden extrahiert...", "dl_sub": "📥 Untertitel werden abgerufen...",
        "failed_50": "❌ >300MB", "failed_blocked": "❌ Gesperrt/privat", "failed_generic": "❌ Fehlgeschlagen",
        "menu_lang": "🌍 Sprache", "menu_stats": "📊 Meine Statistiken", "menu_help": "💬 Support / FAQ", "menu_join": "📢 Kanal beitreten",
        "menu_uploads": "🍿 Fan-Uploads", "menu_upload": "📤 Datei hochladen",
        "admin_upload_prompt": "📂 **Fan-Uploads Posteingang**",
        "user_upload_prompt": "📤 **Datei hochladen**\nSende Video/Bild/Datei an Admin. Limit 5/24h.",
        "upload_success_user": "✅ An Admin gesendet!",
        "upload_limit_reached": "⚠️ Upload-Limit 5/24h erreicht.",
        "no_uploads": "📭 Noch keine Uploads.",
        "stats_msg": "📊 **Deine Statistiken:**\n• Verbleibende Downloads: {}\n• Verbleibende Stapel: {}",
        "change_channel_prompt": "🔄 **Stapel-Kanal ändern**\n1. Stelle sicher, dass ich im neuen Kanal Admin bin.\n2. Leite eine beliebige Nachricht aus diesem Kanal hierher weiter.",
        "disk_config_prompt": "💾 **Speicher-Konfiguration**\nAktueller min. freier Speicher: **{}MB**\nZum Ändern: `/setdisk <wert>`",
        "mtproto_config_prompt": "⚡ **MTProto-Konfiguration**\nAktueller max. Upload: **{}MB**\nZum Ändern: `/setmtproto <wert>`",
        "free_panel_prompt": "📦 KOSTENLOSE DOWNLOADS\nAktuell kostenlos pro Tag: {}",
        "reward_panel_prompt": "🎁 BELOHNUNGS-PANEL\nAktuell: +{} Download pro 20s Werbung",
        "ad_panel_prompt": "⚙️ Werbe-Panel\nAktuell: {}",
        "password_saved": "🔐 Passwort gespeichert.",
        "password_too_long": "Passwort muss 64 Zeichen oder weniger sein.",
        "file_to_link_prompt": "🔗 **Datei-zu-Link**\nSende die Datei(en), die du teilen möchtest.",
        "link_invalid_expired": "❌ Dieser Link ist ungültig oder abgelaufen.",
        "link_limit_reached": "⛔ Dieser Link hat sein Nutzungslimit erreicht.",
        "link_password_protected": "🔐 Dieser Link ist passwortgeschützt. Sende das Passwort.",
        "files_sent": "✅ Deine Dateien wurden gesendet.",
        "file_added": "📥 Datei #{} hinzugefügt. Sende mehr oder tippe auf Link erstellen.",
        "fl_cancelled": "Datei-zu-Link abgebrochen",
        "fl_start_again": "Starte Datei-zu-Link neu mit /filetolink",
        "fl_choose_expiry": "Wähle den Link-Ablauf:",
        "fl_expiry_updated": "Ablauf aktualisiert",
        "fl_choose_max_uses": "Wähle max. erfolgreiche Zustellungen:",
        "fl_uses_updated": "Nutzungslimit aktualisiert",
        "fl_set_password": "Sende ein Passwort oder /clearpassword zum Entfernen.",
        "fl_link_created": "Link erstellt",
        "fl_link_ready": "🔗 Dein Link ist bereit:\n{}\nDateien: {}\nKosten: 1 kostenloser täglicher Download",
        "fl_daily_limit": "Tägliches kostenloses Limit erreicht. Schau Werbung, um mehr zu verdienen.",
        "fl_ad_busy": "⚠️ Werbeserver beschäftigt.",
        "admin_skipped": "✅ Übersprungen!",
        "admin_bypassed": "✅ Umgangen",
        "free_set": "✅ Kostenlos auf {} gesetzt!",
        "free_updated": "✅ Kostenlose Downloads auf {} aktualisiert!",
        "reward_set": "✅ Belohnung auf +{} gesetzt!",
        "reward_updated": "✅ Belohnung auf +{} aktualisiert!",
        "mode_updated": "✅ Modus: {}",
        "support_opened": "✍️ Sende Nachricht/Foto/Video/Datei unten.",
        "admin_reply_mode": "✍️ Antworte an {}:",
        "user_reply_mode": "✍️ Tippe die Fortsetzung unten",
        "support_closed": "🔒 Geschlossen",
        "drop_cancelled": "❌ Abgebrochen",
        "drop_no_items": "⚠️ Keine Elemente!",
        "drop_timer_set": "{} eingestellt!",
        "drop_broadcasting": "🚡 Sende {} Elemente an {}...",
        "drop_flash_text": "🚨 FLASH DROP!\nAutomatische Löschung in {}\nTippe zum Einlösen:",
        "drop_done": "✅ Sendung abgeschlossen an {}",
        "age_expired": "⏳ Abgelaufen!",
        "age_claimed": "❌ Bereits eingelöst!",
        "age_verified": "Verifiziert!",
        "age_denied": "❌ Abgelehnt. Muss 18+ sein",
        "lang_updated": "Aktualisiert!",
        "batch_expired": "Abgelaufen",
        "batch_loading": "Wird geladen...",
        "batch_no_channel": "Kein Kanal verknüpft!",
        "batch_setup_prompt": "📦 Einrichtung: Mache den Bot im Kanal zum Admin und leite eine Nachricht hierher weiter",
        "batch_mode_activated": "Modus aktiviert!",
        "batch_change_dest": "🔄 **Zielkanal ändern**\nMache den Bot im neuen Kanal zum Admin, dann leite eine Nachricht hierher weiter.",
        "join_channel_first_alert": "Tritt zuerst dem Kanal bei! 📢 Muss beitreten!",
        "join_channel_first": "Tritt zuerst dem Kanal bei! 📢",
        "watch_timer_first": "⏰ Öffne zuerst den Link und schaue den 20s Timer!",
        "test_ad_verified": "✅ Test-Werbung verifiziert! +1",
        "test_ad_verified_msg": "✅ **TEST-WERBUNG VERIFIZIERT!**\nBelohnung: +1 Download aufgefüllt!",
        "finish_timer_first": "⏰ Schließe zuerst den 20s Timer ab!",
        "verified_added": "Verifiziert! +1 hinzugefügt",
        "resume_prompt": "✅ Verifiziert! +1 aufgefüllt. Fortsetzen?",
        "refilled_download": "✅ +1 aufgefüllt! Lade erneut herunter.",
        "fetching_bundle": "✅ Verifiziert! Paket wird abgerufen...",
        "outdated_button": "Diese Schaltfläche ist veraltet. Sende deinen Link erneut.",
        "stopping": "Wird gestoppt...",
        "stopped": "🛑 Gestoppt",
        "resuming": "Wird fortgesetzt...",
        "checking_vault": "Tresor und Serverlast werden überprüft...",
        "server_busy": "⏳ **Server beschäftigt**\nAktiv: {}/{}\nFrei: {}MB\nWarteschlange: #{}\nStartet automatisch!",
        "simulated": "🛠 Simuliert! Tippe jetzt auf Prüfen & +1 erhalten",
        "server_unreachable": "❌ Server nicht erreichbar",
        "monetag_failed_twice": "Schließe zuerst zwei fehlgeschlagene Monetag-Versuche ab.",
        "monetag_fallback_prompt": "🌐 Monetag ist zweimal fehlgeschlagen. Mit Adsterra fortfahren:",
        "adsterra_ready": "Adsterra-Fallback bereit",
        "finish_monetag": "📺 Schließe die Monetag-Werbung in der Mini-App ab, prüfe dann erneut.",
        "monetag_failed_use_adsterra": "Monetag ist zweimal fehlgeschlagen. Nutze den Adsterra-Fallback unten.",
        "ad_link_expired": "Werbelink abgelaufen. Sende deinen Link erneut.",
        "ad_verified_added": "✅ Werbung verifiziert! +{} hinzugefügt",
        "test_ad_completed": "✅ TEST-WERBUNG VERIFIZIERT\nBelohnung gutgeschrieben: +{} Download.",
        "sponsor_viewed": "✅ Sponsor angesehen! +{} hinzugefügt",
        "refilled_send_again": "✅ +{} aufgefüllt! Sende deinen Link erneut.",
        "queued": "⏳ In Warteschlange #{}",
        "banned": "🚫 Du bist gesperrt.",
        "no_links": "❌ Keine Links gefunden.",
        "batch_count": "📦 Stapel {} Links",
        "restore_invalid_json": "❌ Wiederherstellung fehlgeschlagen: **{}** ist kein gültiges JSON.",
        "restore_failed": "❌ Wiederherstellung fehlgeschlagen: {}",
        "restore_success": "✅ **Wiederherstellung erfolgreich!**\nDatei: **{}**\n**{}** Einträge wiederhergestellt.",
        "admin_edit_welcome_prompt": "✏️ Sende die neue Willkommensnachricht. Verwende `{bot_name}` für den Bot-Benutzernamen.",
        "admin_welcome_updated": "✅ Willkommensnachricht aktualisiert!",
        "menu_edit_welcome": "✏️ Willkommensnachricht bearbeiten",
        "cached_instant_video": "⚡ Sofortiger Cache [{}] {} {}",
        "cached_instant_audio": "⚡ **Sofortiger Cache** `{}`",
        "cached_instant_image": "⚡ **Sofortiger Cache** `{}`",
        "auto_delete_9m": "⏳ Automatische Löschung in 9 Min.",
        "download_success": "✅ Download erfolgreich!"
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
        
        # FETCH THE ARCADE BACKUP FIRST (Before building the file list)
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

        # UPLOAD FILES
        cap = f"📦 AUTO-BACKUP {ts}\nFree: {free_mb}MB | Active: {active_downloads} | Queue: {download_queue.qsize()} | Vault: {VIDEO_VAULT_ID}"
        first = True
        
        # Ensure arcade_backup.json is prioritized in the list if it exists
        files_to_upload = BACKUP_FILES.copy()
        if "arcade_backup.json" in files_to_upload:
            files_to_upload.remove("arcade_backup.json")
            files_to_upload.insert(0, "arcade_backup.json")

        for fname in files_to_upload:
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

def download_media_engine(url: str, download_type: str, max_mb=None):
    # FIX #1: Strip query params (fixes Instagram ?img_index bug)
    url = url.split('?')[0]
    
    cap_mb = int(max_mb or get_mtproto_max_mb())
    cap_bytes = cap_mb * 1024 * 1024
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    http_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    cookiefile = None
    if "tiktok.com" in url.lower() and os.path.exists("tiktok_cookies.txt"): cookiefile = "tiktok_cookies.txt"
    elif os.path.exists("cookies.txt"): cookiefile = "cookies.txt"
    
    if download_type == 'audio':
        ydl_opts = {
            'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL,
            'format': 'bestaudio/best', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'ffmpeg_location': ffmpeg_path, 'max_filesize': cap_bytes, 'noplaylist': True
        }
        if cookiefile: ydl_opts['cookiefile'] = cookiefile
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'entries' in info and info['entries']: info = info['entries'][0]
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            path = f"{base}.mp3"
            if os.path.exists(path):
                if os.path.getsize(path) > cap_bytes:
                    os.remove(path)
                    raise ValueError("FILE_TOO_LARGE")
                return [path], "audio", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("FILE_NOT_FOUND")

    elif download_type == 'images':
        # Your suggested tools: gallery-dl, fxtwitter, reddit.json
        urls_to_download = []
        
        # 1. Try gallery-dl (Instagram, Facebook, X, etc.)
        try:
            logger.info(f"Trying gallery-dl for {url}")
            res = subprocess.run(["gallery-dl", "--get-urls", url], capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and res.stdout.strip():
                urls_to_download = [u for u in res.stdout.splitlines() if u.startswith('http')]
        except Exception as e:
            logger.error(f"gallery-dl failed: {e}")

        # 2. Reddit .json fallback
        if not urls_to_download and "reddit.com" in url:
            try:
                logger.info("Trying Reddit .json for gallery")
                r = requests.get(url + ".json" if not url.endswith(".json") else url, headers=http_headers, timeout=15)
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    post = data[0]["data"]["children"][0]["data"]
                    if "media_metadata" in post:
                        for img_id, img_data in post["media_metadata"].items():
                            if "s" in img_data and "u" in img_data["s"]:
                                urls_to_download.append(img_data["s"]["u"])
                    elif "url" in post and post["url"].endswith((".jpg", ".png", ".jpeg")):
                        urls_to_download.append(post["url"])
            except Exception as e:
                logger.error(f"Reddit json failed: {e}")

        # 3. X/Twitter fxtwitter fallback
        if not urls_to_download and ("twitter.com" in url or "x.com" in url):
            try:
                logger.info("Trying fxtwitter API")
                clean_url = url.replace("twitter.com", "fxtwitter.com").replace("x.com", "fxtwitter.com")
                r = requests.get(f"https://api.fxtwitter.com/{clean_url.split('://')[1]}", headers=http_headers, timeout=15)
                data = r.json()
                if "tweet" in data and "media" in data["tweet"] and "all" in data["tweet"]["media"]:
                    for media in data["tweet"]["media"]["all"]:
                        if media.get("type") == "photo":
                            urls_to_download.append(media["url"])
            except Exception as e:
                logger.error(f"fxtwitter failed: {e}")

        # 4. Generic fallback (scrape HTML)
        if not urls_to_download:
            try:
                res = requests.get(url, headers=http_headers, timeout=15)
                soup = BeautifulSoup(res.text, 'html.parser')
                og = soup.find('meta', property='og:image')
                if og and og.get('content'): urls_to_download.append(og['content'])
            except: pass

        if not urls_to_download:
            raise ValueError("NO_IMAGES")

        paths = []
        for i, img_url in enumerate(urls_to_download):
            try:
                data = requests.get(img_url, headers=http_headers, timeout=15).content
                path = os.path.join(output_dir, f"img_{int(time.time())}_{i}.jpg")
                with open(path, 'wb') as f: f.write(data)
                if os.path.getsize(path) > 1000: paths.append(path)
            except: pass
            
        if paths:
            total_size = sum(os.path.getsize(p) for p in paths)
            return paths, "gallery", f"{total_size/(1024*1024):.1f}MB"
        raise ValueError("NO_IMAGES")
        
    else:
        # Video mode (With gallery-dl fallback for carousels)
        ydl_opts = {
            'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL,
            'noplaylist': False  # Enable playlists for carousels
        }
        if cookiefile: ydl_opts['cookiefile'] = cookiefile

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
                opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, f'%(id)s_{qual_name}_%(autonumber)s.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path, 'max_filesize': cap_bytes})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    valid_paths = []
                    if 'entries' in info:
                        for e in info['entries']:
                            p = ydl.prepare_filename(e)
                            if not os.path.exists(p) and os.path.exists(os.path.splitext(p)[0]+".mp4"): p = os.path.splitext(p)[0]+".mp4"
                            if os.path.exists(p): valid_paths.append(p)
                    else:
                        p = ydl.prepare_filename(info)
                        if not os.path.exists(p) and os.path.exists(os.path.splitext(p)[0]+".mp4"): p = os.path.splitext(p)[0]+".mp4"
                        if os.path.exists(p): valid_paths.append(p)
                    
                    if valid_paths:
                        total_size = sum(os.path.getsize(p) for p in valid_paths)
                        if total_size > cap_bytes:
                            for p in valid_paths: os.remove(p)
                            too_big = True
                            continue
                            
                        actual_height = info.get('height', 0) if 'entries' not in info else (info['entries'][0].get('height', 0) if info['entries'] else 0)
                        if actual_height >= 1080: best_quality = "1080p"
                        elif actual_height >= 720: best_quality = "720p"
                        elif actual_height >= 480: best_quality = "480p"
                        elif actual_height >= 360: best_quality = "360p"
                        else: best_quality = "worst"
                        
                        res_type = "gallery" if len(valid_paths) > 1 else best_quality
                        return valid_paths, res_type, f"{total_size/(1024*1024):.1f}MB"
                    too_big = True
            except Exception as e:
                if "Unsupported URL" in str(e) or "403" in str(e): raise e
                last_err = e
                continue
        if too_big or last_err is None: raise ValueError("FILE_TOO_LARGE")
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
                
                if len(file_paths) > 1:
                    # BATCH GALLERY SEND
                    media_group = []
                    for i, p in enumerate(file_paths[:10]): # Telegram limit 10
                        ext = os.path.splitext(p)[1].lower()
                        if ext in ('.mp4', '.mkv', '.webm', '.mov'):
                            media_group.append(InputMediaVideo(media=open(p, 'rb'), caption=f"Item {index}/{len(urls)} ({i+1}/{len(file_paths)}) {qual_tag}") if i == 0 else InputMediaVideo(media=open(p, 'rb')))
                        else:
                            media_group.append(InputMediaPhoto(media=open(p, 'rb'), caption=f"Item {index}/{len(urls)} ({i+1}/{len(file_paths)}) {qual_tag}") if i == 0 else InputMediaPhoto(media=open(p, 'rb')))
                    
                    sent_media = await bot.send_media_group(chat_id=target_destination_id, media=media_group)
                    if target_destination_id == chat_id:
                        warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                        msg_ids = [m.message_id for m in sent_media] + [warn.message_id]
                        asyncio.create_task(schedule_deletion(bot, target_destination_id, msg_ids, 540))
                else:
                    # BATCH SINGLE SEND
                    sent = await send_video_file(bot, chat_id, target_destination_id, file_paths[0], f"Item {index}/{len(urls)} {qual_tag} Size {size}", None, status_msg)
                    if target_destination_id == chat_id:
                        warn = await bot.send_message(chat_id=target_destination_id, text="⏳ Auto-deletes in 9 mins")
                        asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent.message_id, warn.message_id], 540))
                
                for p in file_paths: 
                    if os.path.exists(p): os.remove(p)
                    
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

async def cached_download_and_send(bot, chat_id, user_id, url, dl_type, t):
    cache = load_json_file(CACHE_FILE)
    ckey = await get_canonical_key(url, chat_id, bot)
    
    if ckey in cache and "file_id" in cache[ckey] and "qualities" not in cache[ckey]:
        cache[ckey]["qualities"] = {"720p": {"file_id": cache[ckey]["file_id"], "vault_msg_id": cache[ckey].get("vault_msg_id"), "size": cache[ckey].get("size", "unknown")}}
        del cache[ckey]["file_id"]
        save_json_file(CACHE_FILE, cache)
    
    if ckey in cache and cache[ckey].get("type") in ("video", "images", "audio"):
        cached_qualities = cache[ckey].get("qualities", {})
        if dl_type == 'video': qualities_order = ["1080p", "720p", "480p", "360p", "worst", "gallery"]
        elif dl_type == 'audio': qualities_order = ["audio"]
        else: qualities_order = ["original", "gallery"]
            
        best_cached_quality = None
        for q in qualities_order:
            if q in cached_qualities:
                best_cached_quality = q
                break
                
        if best_cached_quality:
            try:
                cached = cached_qualities[best_cached_quality]
                file_ids = cached.get("file_ids") or [cached.get("file_id")]
                if file_ids and file_ids[0]:
                    sz = cached.get("size", "")
                    qual_tag = f"[{best_cached_quality}]"
                    kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
                    
                    if len(file_ids) > 1:
                        # CACHED MULTI-FILE (ALBUM)
                        media_group = []
                        for i, fid in enumerate(file_ids[:10]):
                            if best_cached_quality in ("gallery", "video"):
                                media_group.append(InputMediaVideo(media=fid, caption=f"⚡ Cached Album ({i+1}/{len(file_ids)})") if i == 0 else InputMediaVideo(media=fid))
                            else:
                                media_group.append(InputMediaPhoto(media=fid, caption=f"⚡ Cached Album ({i+1}/{len(file_ids)})") if i == 0 else InputMediaPhoto(media=fid))
                        sent = await bot.send_media_group(chat_id=chat_id, media=media_group)
                        warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                        asyncio.create_task(schedule_deletion(bot, chat_id, [m.message_id for m in sent] + [warn.message_id], 540))
                    else:
                        # CACHED SINGLE FILE
                        file_id = file_ids[0]
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
        effective_max_mb = get_mtproto_max_mb()
        if free_mb < min_free + 150: effective_max_mb = min(effective_max_mb, 50)
            
        file_paths, res, size = await asyncio.to_thread(download_media_engine, url, dl_type, effective_max_mb)
        if not file_paths: raise ValueError("FILE_NOT_FOUND")
        
        cache = load_json_file(CACHE_FILE)
        if ckey not in cache: cache[ckey] = {"type": dl_type, "timestamp": time.time(), "qualities": {}, "hits": 0}
            
        qual_tag = f"[{res}]"
        kb = get_main_keyboard(get_lang(user_id), user_id == ADMIN_ID)
        
        if len(file_paths) > 1:
            # MULTI-FILE (ALBUM) DOWNLOAD SUCCESS
            media_group = []
            sent_media = []
            
            # Send in chunks of 10 (Telegram limit)
            for i in range(0, len(file_paths), 10):
                chunk = file_paths[i:i+10]
                media_group = []
                for j, p in enumerate(chunk):
                    ext = os.path.splitext(p)[1].lower()
                    cap_text = f"✨ {qual_tag} Size {size}" if (i == 0 and j == 0) else None
                    if ext in ('.mp4', '.mkv', '.webm', '.mov'):
                        media_group.append(InputMediaVideo(media=open(p, 'rb'), caption=cap_text))
                    else:
                        media_group.append(InputMediaPhoto(media=open(p, 'rb'), caption=cap_text))
                
                chunk_sent = await bot.send_media_group(chat_id=chat_id, media=media_group)
                sent_media.extend(chunk_sent)
            
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(schedule_deletion(bot, chat_id, [m.message_id for m in sent_media] + [warn.message_id], 540))
            
            try:
                # Save just the first file ID for the album preview in cache
                first_fid = sent_media[0].video.file_id if sent_media[0].video else sent_media[0].photo[-1].file_id
                cache[ckey]["qualities"][res] = {"file_ids": [m.video.file_id if m.video else m.photo[-1].file_id for m in sent_media], "size": size}
            except Exception as e:
                logger.error(f"Vault save fail (album): {e}")
            
            for p in file_paths: os.remove(p)
            
        else:
            # SINGLE FILE DOWNLOAD SUCCESS
            if dl_type == 'images':
                media_group = [InputMediaPhoto(media=open(file_paths[0], 'rb'))]
                sent_media = await bot.send_media_group(chat_id=chat_id, media=media_group)
                warn = await bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)), reply_markup=kb)
                asyncio.create_task(schedule_deletion(bot, chat_id, [m.message_id for m in sent_media] + [warn.message_id], 540))
                try:
                    vmsg = await bot.send_photo(chat_id=VIDEO_VAULT_ID, photo=sent_media[0].photo[-1].file_id, caption=ckey)
                    cache[ckey]["qualities"]["original"] = {"file_id": sent_media[0].photo[-1].file_id, "vault_msg_id": vmsg.message_id, "size": size}
                except: cache[ckey]["qualities"]["original"] = {"file_id": sent_media[0].photo[-1].file_id, "size": size}
                os.remove(file_paths[0])
            elif dl_type == 'audio':
                sent_media = await send_audio_file(bot, chat_id, file_paths[0], f"🎵 Size {size} `{ckey}`", "Markdown", status_msg)
                warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                asyncio.create_task(schedule_deletion(bot, chat_id, [sent_media.message_id, warn.message_id], 540))
                try:
                    vmsg = await bot.send_audio(chat_id=VIDEO_VAULT_ID, audio=sent_media.audio.file_id, caption=ckey)
                    cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "vault_msg_id": vmsg.message_id, "size": size}
                except: cache[ckey]["qualities"]["audio"] = {"file_id": sent_media.audio.file_id, "size": size}
                os.remove(file_paths[0])
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
        if "FILE_TOO_LARGE" in str(e): err = t["error_50mb"]
        elif "MTPROTO_OFF" in str(e): err = "⚠️ Big files need fast mode, which is offline right now."
        elif "MTPROTO_PEER" in str(e): err = "⚠️ Send /start to this bot once, then send the link again."
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