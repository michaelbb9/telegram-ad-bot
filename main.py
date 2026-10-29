import time
import json
import os
import asyncio
import threading
import requests
import logging
import re
import imageio_ffmpeg
import yt_dlp
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- FIX FFMPEG EXECUTION PERMISSIONS FOR RENDER ---
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
try:
    os.chmod(ffmpeg_path, 0o755)
except Exception as e:
    logging.error(f"Could not set ffmpeg permissions: {e}")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "8863904451:AAFYl9yyjTvKTaliLR5iqTsvZr2tytFi3bk").strip()
ADMIN_ID = 6248570946
DETECTED_CHANNEL_ID = -1004347828512
PRIVATE_CHANNEL_ID = -1004347828512
TUTORIAL_MESSAGE_ID = 108
WEB_BASE_URL = "https://michaelbbc.pythonanywhere.com"
BRIDGE_URL = f"{WEB_BASE_URL}/bridge"
PUBLIC_CHANNEL_URL = "https://t.me/booksaufio"
PUBLIC_CHANNEL_USERNAME = "@booksaufio"
HELP_CHANNEL_URL = "https://t.me/faqandaupport"
DELETE_DELAY_TIME = 540 

PROXY_URL = None 
CHANNELS_FILE = "user_channels.json"
LINKING_STATE_FILE = "linking_states.json"
LANG_FILE = "user_languages.json"

active_batch_sessions = {}
pending_batch_payloads = {}
paused_batches = {}
pending_single_links = {}

# --- TRANSLATIONS DICTIONARY ---
LANGUAGES = {
    "en": {
        "welcome": "🚀 **Welcome to the Ultimate Media Downloader Bot!** 🚀\n\nI am your all-in-one Swiss Army Knife for social media. Here is everything I can do:\n\n🎬 **Video Downloader:** Paste any link (TikTok, Insta, Twitter, FB) to get the video in the highest quality possible.\n\n🎵 **Audio / MP3 Extractor:** Turn any video into an MP3 audio file instantly.\n\n🖼️ **Image / Gallery Saver:** Download photos from Instagram posts, Facebook, or Pinterest.\n\n📝 **Subtitle Extractor:** Grab the subtitle text files (SRT) from videos.\n\n📦 **Massive Batch Downloader:** Paste up to 100+ links at once, or upload a `.txt` file.\n\n⚠️ **Rules & Limits:**\n• Telegram limits bots to 50MB per file.\n• You get 20 free batch downloads. After that, you must watch a quick 20-second sponsor timer to refill.\n\n👉 **Just paste a link to get started!**",
        "btn_video": "🎬 Video (MP4)",
        "btn_audio": "🎵 Audio (MP3)",
        "btn_image": "🖼️ Images (Gallery)",
        "btn_sub": "📝 Subtitles (SRT)",
        "ask_format": "👇 **What would you like to download?**",
        "fetching": "📥 **Fetching {}... Please wait.**",
        "error_generic": "❌ Failed to download. Link might be private, or site blocked the bot.",
        "error_50mb": "❌ File exceeds Telegram's 50MB limit.",
        "error_no_img": "❌ No images found at this link.",
        "deletes_in_9": "⏳ **Auto-deletes in 9 minutes.**",
        "images_received": "⏳ **{} Images received. Auto-deletes in 9 minutes.**",
        "select_lang": "🌍 Please select your language:",
        "lang_set": "✅ Language set to English!",
        "batch_detected": "📦 **Batch Detected ({} links)**\nWhere to send these?",
        "btn_chat": "📥 Download in Chat",
        "btn_chan": "📢 Forward to Private Channel",
        "limit_reached": "⚠️ **Limit Reached!** Refill to continue.",
        "refill_btn": "🔓 Open Link & Refill",
        "join_btn": "📢 Join Public Channel",
        "check_btn": "💜 Check Balance",
        "limit_batch": "⚠️ **Batch Limit Reached! (Stopped at link {} of {})**\n\nRefill to continue:",
        "batch_start": "📦 **Batch Processing Started:** Found **{} links**.\n\n⏳ *Processing...*",
        "batch_done": "🏁 **Batch Finished!**\n✅ Success: {}\n❌ Failed: {}\n\n📥 **{} videos sent here.**",
        "batch_done_chan": "🏁 **Batch Finished!**\n✅ Success: {}\n❌ Failed: {}\n\n📢 **{} videos forwarded!**",
        "dl_video": "📥 Downloading video...",
        "failed_50": "❌ Failed: Video > 50MB.",
        "failed_blocked": "❌ Failed: Site blocked bot or link private.",
        "failed_generic": "❌ Download failed.",
        "menu_lang": "🌍 Language",
        "menu_stats": "📊 My Stats",
        "menu_help": "📢 FAQ / Help",
        "menu_join": "📢 Join Channel",
        "stats_msg": "📊 **Your Stats:**\n\n• Normal Downloads Left: {}\n• Batch Downloads Left: {}\n\n*Stats reset every 24 hours. Watch the sponsor timer to refill!*"
    },
    "es": {
        "welcome": "🚀 **¡Bienvenido al Bot Definitivo de Descargas!** 🚀\n\nSoy tu navaja suiza todo en uno para redes sociales. Esto es lo que puedo hacer:\n\n🎬 **Descargador de Video:** Pega cualquier enlace (TikTok, Insta, Twitter, FB) para obtener el video en la mejor calidad.\n\n🎵 **Extractor de Audio / MP3:** Convierte cualquier video en un archivo MP3 al instante.\n\n🖼️ **Guardador de Imágenes:** Descarga fotos de Instagram, Facebook o Pinterest.\n\n📝 **Extractor de Subtítulos:** Obtén los archivos de subtítulos (SRT).\n\n📦 **Descargador Masivo:** Pega hasta 100+ enlaces a la vez, o sube un archivo `.txt`.\n\n⚠️ **Reglas y Límites:**\n• Telegram limita a los bots a 50MB por archivo.\n• Tienes 20 descargas por lotes gratis. Después de eso, debes ver un temporizador de 20 segundos.\n\n👉 **¡Solo pega un enlace para comenzar!**",
        "btn_video": "🎬 Video (MP4)",
        "btn_audio": "🎵 Audio (MP3)",
        "btn_image": "🖼️ Imágenes (Galería)",
        "btn_sub": "📝 Subtítulos (SRT)",
        "ask_format": "👇 **¿Qué te gustaría descargar?**",
        "fetching": "📥 **Obteniendo {}... Por favor espera.**",
        "error_generic": "❌ Error al descargar. El enlace puede ser privado o el sitio bloqueó el bot.",
        "error_50mb": "❌ El archivo supera el límite de 50MB de Telegram.",
        "error_no_img": "❌ No se encontraron imágenes en este enlace.",
        "deletes_in_9": "⏳ **Se elimina automáticamente en 9 minutos.**",
        "images_received": "⏳ **{} Imágenes recibidas. Se eliminan en 9 minutos.**",
        "select_lang": "🌍 Por favor selecciona tu idioma:",
        "lang_set": "✅ ¡Idioma cambiado a Español!",
        "batch_detected": "📦 **Lote Detectado ({} enlaces)**\n¿A dónde enviarlos?",
        "btn_chat": "📥 Descargar en el Chat",
        "btn_chan": "📢 Reenviar al Canal Privado",
        "limit_reached": "⚠️ **¡Límite alcanzado!** Recarga para continuar.",
        "refill_btn": "🔓 Abrir Enlace y Recargar",
        "join_btn": "📢 Unirse al Canal Público",
        "check_btn": "💜 Verificar Saldo",
        "limit_batch": "⚠️ **¡Límite de lote alcanzado! (Detenido en el enlace {} de {})**\n\nRecarga para continuar:",
        "batch_start": "📦 **Procesamiento por lotes iniciado:** Encontrados **{} enlaces**.\n\n⏳ *Procesando...*",
        "batch_done": "🏁 **¡Lote Terminado!**\n✅ Éxito: {}\n❌ Fallidos: {}\n\n📥 **{} videos enviados aquí.**",
        "batch_done_chan": "🏁 **¡Lote Terminado!**\n✅ Éxito: {}\n❌ Fallidos: {}\n\n📢 **{} videos reenviados!**",
        "dl_video": "📥 Descargando video...",
        "failed_50": "❌ Fallido: Video > 50MB.",
        "failed_blocked": "❌ Fallido: Sitio bloqueó el bot o enlace privado.",
        "failed_generic": "❌ Descarga fallida.",
        "menu_lang": "🌍 Idioma",
        "menu_stats": "📊 Mis Estadísticas",
        "menu_help": "📢 Ayuda",
        "menu_join": "📢 Unirse al Canal",
        "stats_msg": "📊 **Tus Estadísticas:**\n\n• Descargas Normales Restantes: {}\n• Descargas por Lote Restantes: {}\n\n*Las estadísticas se reinician cada 24 horas. ¡Mira el temporizador para recargar!*"
    },
    "fr": {
        "welcome": "🚀 **Bienvenue sur le Bot de Téléchargement Ultime !** 🚀\n\nJe suis votre couteau suisse tout-en-un. Voici ce que je peux faire :\n\n🎬 **Téléchargeur Vidéo :** Collez un lien (TikTok, Insta, Twitter, FB) pour la meilleure qualité.\n\n🎵 **Extracteur Audio / MP3 :** Transformez une vidéo en MP3.\n\n🖼️ **Sauveur d'Images :** Téléchargez des photos d'Instagram, Facebook.\n\n📝 **Extracteur de Sous-titres :** Obtenez les fichiers SRT.\n\n📦 **Téléchargeur de Masse :** Collez jusqu'à 100+ liens ou un fichier `.txt`.\n\n⚠️ **Règles & Limites :**\n• Telegram limite à 50MB par fichier.\n• Vous avez 20 téléchargements gratuits. Ensuite, regardez une pub de 20 secondes.\n\n👉 **Collez un lien pour commencer !**",
        "btn_video": "🎬 Vidéo (MP4)",
        "btn_audio": "🎵 Audio (MP3)",
        "btn_image": "🖼️ Images (Galerie)",
        "btn_sub": "📝 Sous-titres (SRT)",
        "ask_format": "👇 **Que voulez-vous télécharger ?**",
        "fetching": "📥 **Récupération de {}... Veuillez patienter.**",
        "error_generic": "❌ Échec. Lien privé ou site bloqué.",
        "error_50mb": "❌ Fichier dépasse la limite de 50MB.",
        "error_no_img": "❌ Aucune image trouvée.",
        "deletes_in_9": "⏳ **Suppression auto dans 9 minutes.**",
        "images_received": "⏳ **{} Images reçues. Suppression dans 9 minutes.**",
        "select_lang": "🌍 Veuillez choisir votre langue :",
        "lang_set": "✅ Langue définie sur Français !",
        "batch_detected": "📦 **Lot Détecté ({} liens)**\nOù les envoyer ?",
        "btn_chat": "📥 Télécharger dans le Chat",
        "btn_chan": "📢 Transférer au Canal Privé",
        "limit_reached": "⚠️ **Limite atteinte !** Rechargez pour continuer.",
        "refill_btn": "🔓 Ouvrir le lien & Recharger",
        "join_btn": "📢 Rejoindre le Canal Public",
        "check_btn": "💜 Vérifier le Solde",
        "limit_batch": "⚠️ **Limite de lot atteinte ! (Arrêté au lien {} sur {})**\n\nRechargez pour continuer :",
        "batch_start": "📦 **Traitement du lot commencé :** **{} liens** trouvés.\n\n⏳ *Traitement...*",
        "batch_done": "🏁 **Lot Terminé !**\n✅ Succès : {}\n❌ Échecs : {}\n\n📥 **{} vidéos envoyées ici.**",
        "batch_done_chan": "🏁 **Lot Terminé !**\n✅ Succès : {}\n❌ Échecs : {}\n\n📢 **{} vidéos transférées !**",
        "dl_video": "📥 Téléchargement de la vidéo...",
        "failed_50": "❌ Échec : Vidéo > 50MB.",
        "failed_blocked": "❌ Échec : Site a bloqué le bot ou lien privé.",
        "failed_generic": "❌ Échec du téléchargement.",
        "menu_lang": "🌍 Langue",
        "menu_stats": "📊 Mes Stats",
        "menu_help": "📢 Aide",
        "menu_join": "📢 Rejoindre",
        "stats_msg": "📊 **Vos Statistiques :**\n\n• Téléchargements Normaux Restants : {}\n• Téléchargements par Lot Restants : {}\n\n*Réinitialisé toutes les 24h. Regardez le temporisateur pour recharger !*"
    },
    "ar": {
        "welcome": "🚀 **مرحبًا بك في بوت التحميل الشامل!** 🚀\n\nأنا أداة الكل في واحد الخاصة بك. إليك ما يمكنني فعله:\n\n🎬 **تحميل الفيديو:** الصق أي رابط (تيك توك، انستغرام، تويتر، فيسبوك) للحصول على أفضل جودة.\n\n🎵 **استخراج الصوت / MP3:** تحويل أي فيديو إلى ملف MP3 على الفور.\n\n🖼️ **حفظ الصور:** قم بتنزيل الصور من انستغرام وفيسبوك.\n\n📝 **استخراج الترجمة:** احصل على ملفات SRT.\n\n📦 **تحميل دفعة:** الصق 100+ رابط أو ملف `.txt`.\n\n⚠️ **القواعد والحدود:**\n• تيليجرام يحدد 50 ميجابايت لكل ملف.\n• لديك 20 تحميلاً مجانياً. بعد ذلك، شاهد إعلاناً لمدة 20 ثانية.\n\n👉 **فقط الصق رابطاً للبدء!**",
        "btn_video": "🎬 فيديو (MP4)",
        "btn_audio": "🎵 صوت (MP3)",
        "btn_image": "🖼️ صور (معرض)",
        "btn_sub": "📝 ترجمة (SRT)",
        "ask_format": "👇 **ماذا تريد أن تحمل؟**",
        "fetching": "📥 **جاري جلب {}... يرجى الانتظار.**",
        "error_generic": "❌ فشل التحميل. قد يكون الرابط خاصاً أو الموقع حظر البوت.",
        "error_50mb": "❌ الملف يتجاوز حد 50 ميجابايت.",
        "error_no_img": "❌ لم يتم العثور على صور.",
        "deletes_in_9": "⏳ **حذف تلقائي في 9 دقائق.**",
        "images_received": "⏳ **تم استلام {} صور. حذف في 9 دقائق.**",
        "select_lang": "🌍 يرجى اختيار لغتك:",
        "lang_set": "✅ تم ضبط اللغة على العربية!",
        "batch_detected": "📦 **تم اكتشاف دفعة ({} روابط)**\nأين ترسلها؟",
        "btn_chat": "📥 تحميل في الدردشة",
        "btn_chan": "📢 إعادة توجيه للقناة الخاصة",
        "limit_reached": "⚠️ **تم الوصول للحد!** أعد التعبئة للمتابعة.",
        "refill_btn": "🔓 فتح الرابط وإعادة التعبئة",
        "join_btn": "📢 انضم للقناة العامة",
        "check_btn": "💜 تحقق من الرصيد",
        "limit_batch": "⚠️ **تم الوصول لحد الدفعة! (توقف عند الرابط {} من {})**\n\nأعد التعبئة للمتابعة:",
        "batch_start": "📦 **بدأت معالجة الدفعة:** تم العثور على **{} روابط**.\n\n⏳ *جاري المعالجة...*",
        "batch_done": "🏁 **انتهت الدفعة!**\n✅ نجاح: {}\n❌ فشل: {}\n\n📥 **تم إرسال {} فيديو هنا.**",
        "batch_done_chan": "🏁 **انتهت الدفعة!**\n✅ نجاح: {}\n❌ فشل: {}\n\n📢 **تم إعادة توجيه {} فيديو!**",
        "dl_video": "📥 جاري تحميل الفيديو...",
        "failed_50": "❌ فشل: الفيديو > 50 ميجابايت.",
        "failed_blocked": "❌ فشل: الموقع حظر البوت أو الرابط خاص.",
        "failed_generic": "❌ فشل التحميل.",
        "menu_lang": "🌍 اللغة",
        "menu_stats": "📊 إحصائياتي",
        "menu_help": "📢 مساعدة",
        "menu_join": "📢 انضم للقناة",
        "stats_msg": "📊 **إحصائياتك:**\n\n• التحميلات العادية المتبقية: {}\n• تحميلات الدفعة المتبقية: {}\n\n*يتم إعادة التعيين كل 24 ساعة. شاهد المؤقت لإعادة التعبئة!*"
    },
    "hi": {
        "welcome": "🚀 **अल्टीमेट मीडिया डाउनलोडर बॉट में आपका स्वागत है!** 🚀\n\nमैं सोशल मीडिया के लिए आपका ऑल-इन-वन टूल हूं। यहाँ मैं क्या कर सकता हूँ:\n\n🎬 **वीडियो डाउनलोडर:** कोई भी लिंक (TikTok, Insta, Twitter, FB) पेस्ट करें और सर्वोत्तम गुणवत्ता में वीडियो प्राप्त करें।\n\n🎵 **ऑडियो / MP3 एक्सट्रैक्टर:** किसी भी वीडियो को तुरंत MP3 ऑडियो फ़ाइल में बदलें।\n\n🖼️ **इमेज / गैलरी सेवर:** Instagram, Facebook या Pinterest से तस्वीरें डाउनलोड करें।\n\n📝 **सबटाइटल एक्सट्रैक्टर:** वीडियो से सबटाइटल (SRT) फ़ाइलें प्राप्त करें।\n\n📦 **मैसिव बैच डाउनलोडर:** एक बार में 100+ लिंक पेस्ट करें, या `.txt` फ़ाइल अपलोड करें।\n\n⚠️ **नियम और सीमाएँ:**\n• Telegram की सीमा 50MB प्रति फ़ाइल है।\n• आपको 20 मुफ़्त बैच डाउनलोड मिलते हैं। उसके बाद, रिफिल के लिए 20 सेकंड का टाइमर देखें।\n\n👉 **शुरू करने के लिए बस एक लिंक पेस्ट करें!**",
        "btn_video": "🎬 वीडियो (MP4)",
        "btn_audio": "🎵 ऑडियो (MP3)",
        "btn_image": "🖼️ तस्वीरें (गैलरी)",
        "btn_sub": "📝 सबटाइटल (SRT)",
        "ask_format": "👇 **आप क्या डाउनलोड करना चाहेंगे?**",
        "fetching": "📥 **{} प्राप्त किया जा रहा है... कृपया प्रतीक्षा करें।**",
        "error_generic": "❌ डाउनलोड विफल। लिंक निजी हो सकता है, या साइट ने बॉट को ब्लॉक कर दिया है।",
        "error_50mb": "❌ फ़ाइल Telegram की 50MB सीमा से अधिक है।",
        "error_no_img": "❌ इस लिंक पर कोई तस्वीर नहीं मिली।",
        "deletes_in_9": "⏳ **9 मिनट में स्वतः हट जाएगा।**",
        "images_received": "⏳ **{} तस्वीरें प्राप्त हुईं। 9 मिनट में हट जाएंगी।**",
        "select_lang": "🌍 कृपया अपनी भाषा चुनें:",
        "lang_set": "✅ भाषा हिंदी में सेट हो गई!",
        "batch_detected": "📦 **बैच पाया गया ({} लिंक)**\nइन्हें कहाँ भेजें?",
        "btn_chat": "📥 चैट में डाउनलोड करें",
        "btn_chan": "📢 प्राइवेट चैनल में फॉरवर्ड करें",
        "limit_reached": "⚠️ **सीमा समाप्त!** जारी रखने के लिए रिफिल करें।",
        "refill_btn": "🔓 लिंक खोलें और रिफिल करें",
        "join_btn": "📢 पब्लिक चैनल से जुड़ें",
        "check_btn": "💜 बैलेंस जांचें",
        "limit_batch": "⚠️ **बैच सीमा समाप्त! ({} में से {} लिंक पर रुक गया)**\n\nजारी रखने के लिए रिफिल करें:",
        "batch_start": "📦 **बैच प्रोसेसिंग शुरू हुई:** **{} लिंक** मिले।\n\n⏳ *प्रोसेसिंग...*",
        "batch_done": "🏁 **बैच समाप्त!**\n✅ सफल: {}\n❌ विफल: {}\n\n📥 **{} वीडियो यहाँ भेजे गए।**",
        "batch_done_chan": "🏁 **बैच समाप्त!**\n✅ सफल: {}\n❌ विफल: {}\n\n📢 **{} वीडियो फॉरवर्ड किए गए!**",
        "dl_video": "📥 वीडियो डाउनलोड हो रहा है...",
        "failed_50": "❌ विफल: वीडियो > 50MB.",
        "failed_blocked": "❌ विफल: साइट ने बॉट को ब्लॉक किया या लिंक निजी है।",
        "failed_generic": "❌ डाउनलोड विफल।",
        "menu_lang": "🌍 भाषा",
        "menu_stats": "📊 मेरे आंकड़े",
        "menu_help": "📢 सहायता",
        "menu_join": "📢 चैनल से जुड़ें",
        "stats_msg": "📊 **आपके आंकड़े:**\n\n• सामान्य डाउनलोड शेष: {}\n• बैच डाउनलोड शेष: {}\n\n*हर 24 घंटे में रीसेट होता है। रिफिल के लिए टाइमर देखें!*"
    },
    "ru": {
        "welcome": "🚀 **Добро пожаловать в Ultimate Media Downloader Bot!** 🚀\n\nЯ ваш универсальный инструмент для социальных сетей. Вот что я умею:\n\n🎬 **Загрузчик видео:** Вставьте любую ссылку (TikTok, Insta, Twitter, FB), чтобы получить видео в максимальном качестве.\n\n🎵 **Извлечение аудио / MP3:** Мгновенно конвертируйте видео в MP3.\n\n🖼️ **Сохранение изображений:** Скачивайте фото из Instagram, Facebook или Pinterest.\n\n📝 **Извлечение субтитров:** Получайте файлы субтитров (SRT).\n\n📦 **Массовая загрузка:** Вставьте до 100+ ссылок или загрузите файл `.txt`.\n\n⚠️ **Правила и ограничения:**\n• Лимит Telegram — 50 МБ на файл.\n• Вам доступно 20 бесплатных пакетных загрузок. После этого нужно посмотреть 20-секундную рекламу.\n\n👉 **Просто вставьте ссылку, чтобы начать!**",
        "btn_video": "🎬 Видео (MP4)",
        "btn_audio": "🎵 Аудио (MP3)",
        "btn_image": "🖼️ Изображения",
        "btn_sub": "📝 Субтитры (SRT)",
        "ask_format": "👇 **Что вы хотите скачать?**",
        "fetching": "📥 **Загрузка {}... Пожалуйста, подождите.**",
        "error_generic": "❌ Не удалось скачать. Ссылка может быть приватной, или сайт заблокировал бота.",
        "error_50mb": "❌ Файл превышает лимит Telegram в 50 МБ.",
        "error_no_img": "❌ По этой ссылке изображения не найдены.",
        "deletes_in_9": "⏳ **Автоудаление через 9 минут.**",
        "images_received": "⏳ **Получено {} изображений. Автоудаление через 9 минут.**",
        "select_lang": "🌍 Пожалуйста, выберите язык:",
        "lang_set": "✅ Язык изменен на русский!",
        "batch_detected": "📦 **Обнаружена пакетная загрузка ({} ссылок)**\nКуда их отправить?",
        "btn_chat": "📥 Скачать в чат",
        "btn_chan": "📢 Переслать в приватный канал",
        "limit_reached": "⚠️ **Лимит исчерпан!** Пополните баланс, чтобы продолжить.",
        "refill_btn": "🔓 Открыть ссылку и пополнить",
        "join_btn": "📢 Присоединиться к каналу",
        "check_btn": "💜 Проверить баланс",
        "limit_batch": "⚠️ **Лимит пакета исчерпан! (Остановлено на ссылке {} из {})**\n\nПополните, чтобы продолжить:",
        "batch_start": "📦 **Начата пакетная обработка:** Найдено **{} ссылок**.\n\n⏳ *Обработка...*",
        "batch_done": "🏁 **Пакет завершен!**\n✅ Успешно: {}\n❌ Ошибок: {}\n\n📥 **{} видео отправлено сюда.**",
        "batch_done_chan": "🏁 **Пакет завершен!**\n✅ Успешно: {}\n❌ Ошибок: {}\n\n📢 **{} видео переслано!**",
        "dl_video": "📥 Скачивание видео...",
        "failed_50": "❌ Ошибка: Видео > 50 МБ.",
        "failed_blocked": "❌ Ошибка: Сайт заблокировал бота или ссылка приватная.",
        "failed_generic": "❌ Ошибка загрузки.",
        "menu_lang": "🌍 Язык",
        "menu_stats": "📊 Моя статистика",
        "menu_help": "📢 Помощь",
        "menu_join": "📢 Канал",
        "stats_msg": "📊 **Ваша статистика:**\n\n• Обычных загрузок осталось: {}\n• Пакетных загрузок осталось: {}\n\n*Сбрасывается каждые 24 часа. Смотрите таймер для пополнения!*"
    }
}

web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is alive and running!", 200

def load_json_file(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_json_file(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

def get_lang(user_id):
    langs = load_json_file(LANG_FILE)
    return langs.get(str(user_id), "en")

def load_tokens():
    try:
        response = requests.get(f"{WEB_BASE_URL}/get_tokens", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
    return {}

def save_tokens(tokens):
    try:
        requests.post(f"{WEB_BASE_URL}/save_tokens", json=tokens, timeout=5)
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")

def load_user_channels():
    return load_json_file(CHANNELS_FILE)

def save_user_channels(channels):
    save_json_file(CHANNELS_FILE, channels)

def load_linking_states():
    return load_json_file(LINKING_STATE_FILE)

def save_linking_states(states):
    save_json_file(LINKING_STATE_FILE, states)

async def schedule_deletion(bot, chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

def scrape_html_images(url, cookiefile=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    cookies = None
    if cookiefile and os.path.exists(cookiefile):
        try:
            import http.cookiejar
            cj = http.cookiejar.MozillaCookieJar(cookiefile)
            cj.load(ignore_discard=True, ignore_expires=True)
            cookies = {cookie.name: cookie.value for cookie in cj}
        except: pass

    try:
        res = requests.get(url, headers=headers, cookies=cookies, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(res.text, 'html.parser')
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            return og_img['content']
        tw_img = soup.find('meta', name='twitter:image')
        if tw_img and tw_img.get('content'):
            return tw_img['content']
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and ('scontent' in src or 'fbcdn' in src):
                return src
    except Exception as e:
        logger.error(f"HTML Scrape error: {e}")
    return None

def download_media_engine(url: str, download_type: str):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    url_lower = url.lower()
    http_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept-Language': 'en-US,en;q=0.9'}

    cookiefile = None
    if "tiktok.com" in url_lower and os.path.exists("tiktok_cookies.txt"): cookiefile = "tiktok_cookies.txt"
    elif "twitter.com" in url_lower or "x.com" in url_lower: cookiefile = "twitter_cookies.txt" if os.path.exists("twitter_cookies.txt") else None
    elif "facebook.com" in url_lower: cookiefile = "facebook_cookies.txt" if os.path.exists("facebook_cookies.txt") else None
    elif "naijafap.com" in url_lower: cookiefile = "naijafap_cookies.txt" if os.path.exists("naijafap_cookies.txt") else None
    elif os.path.exists("cookies.txt"): cookiefile = "cookies.txt"

    ydl_opts = {'quiet': True, 'no_warnings': True, 'http_headers': http_headers, 'proxy': PROXY_URL}
    if cookiefile: ydl_opts['cookiefile'] = cookiefile

    if download_type == 'audio':
        ydl_opts.update({'format': 'bestaudio/best', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'ffmpeg_location': ffmpeg_path})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            path = f"{base}.mp3"
            if os.path.exists(path): return [path], "Audio MP3", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("FILE_NOT_FOUND")

    elif download_type == 'subtitles':
        ydl_opts.update({'skip_download': True, 'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': ['en'], 'subtitlesformat': 'srt', 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s')})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = os.path.splitext(ydl.prepare_filename(info))[0]
            for ext in ['.en.srt', '.en.vtt']:
                if os.path.exists(base+ext): return [base+ext], "Subtitles", "Text"
        raise ValueError("NO_SUBTITLES")

    elif download_type == 'images':
        img_url = scrape_html_images(url, cookiefile)
        if img_url:
            img_data = requests.get(img_url, headers=http_headers, timeout=15).content
            ext = '.png' if '.png' in img_url else '.webp' if '.webp' in img_url else '.jpg'
            path = os.path.join(output_dir, f"image_{int(time.time())}{ext}")
            with open(path, 'wb') as f: f.write(img_data)
            if os.path.getsize(path) > 1000: return [path], "Image", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
        raise ValueError("NO_IMAGES")

    else:
        for fmt in ["bestvideo+bestaudio/best", "best[height<=1080]", "best[height<=720]", "best[height<=480]", "best"]:
            try:
                ydl_opts.update({'format': fmt, 'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'), 'merge_output_format': 'mp4', 'ffmpeg_location': ffmpeg_path})
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path) and os.path.exists(os.path.splitext(path)[0]+".mp4"): path = os.path.splitext(path)[0]+".mp4"
                    if os.path.exists(path):
                        if os.path.getsize(path) > 50*1024*1024: os.remove(path); continue
                        return [path], f"{info.get('height', 'HD')}p", f"{os.path.getsize(path)/(1024*1024):.1f}MB"
            except Exception as e:
                if "Unsupported URL" in str(e) or "403" in str(e): raise e
                continue
        raise ValueError("FILE_TOO_LARGE")


def get_main_keyboard(lang_code):
    t = LANGUAGES[lang_code]
    # We send the text of the buttons, so we can catch them in handle_media_link
    keyboard = [
        [KeyboardButton(t["menu_stats"]), KeyboardButton(t["menu_lang"])],
        [KeyboardButton(t["menu_join"]), KeyboardButton(t["menu_help"])]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    lang = get_lang(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"), InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇮🇳 हिंदी (Hindi)", callback_data="lang_hi"), InlineKeyboardButton("🇷🇺 Русский (Russian)", callback_data="lang_ru")]
    ]
    await update.message.reply_text(LANGUAGES[lang]["select_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if not args:
        # Send welcome message WITH the permanent bottom keyboard
        await update.message.reply_text(t["welcome"], reply_markup=get_main_keyboard(lang), parse_mode="Markdown")
        return

    video_code = args[0]
    if video_code.startswith("vid"):
        clean_code = video_code.replace("vid", "")
        if "to" in clean_code:
            try:
                parts = clean_code.split("to")
                msg_start, msg_end = int(parts[0]), int(parts[1])
            except (ValueError, IndexError): return
        else:
            try:
                msg_start = int(clean_code)
                msg_end = msg_start
            except ValueError: return
    else: return

    bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg={msg_start}&end_msg={msg_end}"
    tokens = load_tokens()
    tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": int(msg_start), "msg_end": int(msg_end), "clicked_ad": False, "verified": False, "expires": time.time() + 600}
    save_tokens(tokens)

    keyboard = [
        [InlineKeyboardButton("🔓 Open Link & Watch Timer", url=bridge_link)],
        [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)],
        [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    caption_text = "👇 **CONTENT LOCKED** 👇\n\nWatch the ad to unlock your files."
    try:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=PRIVATE_CHANNEL_ID, message_id=TUTORIAL_MESSAGE_ID, caption=caption_text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        await update.message.reply_text(text=caption_text, reply_markup=reply_markup, parse_mode="Markdown")

async def process_url_batch(bot, user_id, chat_id, target_destination_id, urls, start_index=0):
    if not urls: return
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    success_count = 0
    fail_count = 0
    active_batch_sessions[user_id] = True

    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Batch", callback_data="stop_batch")]])
    batch_notice = await bot.send_message(chat_id=chat_id, text=t["batch_start"].format(len(urls)), reply_markup=stop_markup, parse_mode="Markdown")

    consecutive_fails = 0

    for index, url in enumerate(urls[start_index:], start=start_index + 1):
        if not active_batch_sessions.get(user_id, False): break
        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Skipped YouTube.")
            continue

        if consecutive_fails >= 3:
            cooldown_msg = await bot.send_message(chat_id=chat_id, text=f"⏳ **Site Rate Limit Detected.** Pausing for 60 seconds...")
            await asyncio.sleep(60)
            try: await cooldown_msg.delete()
            except: pass
            consecutive_fails = 0

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": True}, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except Exception:
            await bot.send_message(chat_id=chat_id, text=f"❌ [{index}/{len(urls)}] Connection error.")
            break

        if res_data.get("status") != "allowed":
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)
            paused_batches[user_id] = {"urls": urls, "next_index": index - 1, "target_destination_id": target_destination_id, "chat_id": chat_id}
            keyboard = [
                [InlineKeyboardButton(t["refill_btn"], url=bridge_link)],
                [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]
            ]
            await bot.send_message(chat_id=chat_id, text=t["limit_batch"].format(index, len(urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            break 

        status_msg = await bot.send_message(chat_id=chat_id, text=f"📥 [{index}/{len(urls)}] {t['dl_video']}")

        try:
            file_paths, resolution, size_str = download_media_engine(url, 'video')
            if file_paths and os.path.exists(file_paths[0]):
                file_path = file_paths[0]
                with open(file_path, 'rb') as media_file:
                    sent_media = await bot.send_video(chat_id=target_destination_id, video=media_file, caption=f"✨ **Batch Item {index}/{len(urls)}**\n📐 Quality: {resolution}\n📦 Size: {size_str}", parse_mode="Markdown")
                
                if target_destination_id == chat_id:
                    warning_msg = await bot.send_message(chat_id=target_destination_id, text=t["deletes_in_9"])
                    asyncio.create_task(schedule_deletion(bot, target_destination_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                
                os.remove(file_path)
                await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                success_count += 1
                consecutive_fails = 0 
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}/{len(urls)}] Failed.")
                fail_count += 1
                consecutive_fails += 1
        except Exception as e:
            consecutive_fails += 1
            try:
                error_text = t["failed_50"] if "FILE_TOO_LARGE" in str(e) else t["failed_blocked"] if "403" in str(e) else t["failed_generic"]
                await bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ [{index}/{len(urls)}] {error_text}")
            except Exception: pass
            fail_count += 1
        await asyncio.sleep(4) 

    if user_id in active_batch_sessions: del active_batch_sessions[user_id]
    try: await bot.delete_message(chat_id=chat_id, message_id=batch_notice.message_id)
    except: pass

    if user_id not in paused_batches:
        dest_text = t["batch_done_chan"].format(success_count, fail_count, success_count) if target_destination_id != chat_id else t["batch_done"].format(success_count, fail_count, success_count)
        await bot.send_message(chat_id=chat_id, text=dest_text, parse_mode="Markdown")


async def handle_media_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    # --- NEW: Handle Menu Keyboard Buttons ---
    if text == t["menu_stats"]:
        tokens = load_tokens()
        profile = tokens.get(str(user_id), {})
        d_left = profile.get("downloads_left", 4)
        b_left = profile.get("batch_downloads_left", 20)
        if user_id == ADMIN_ID:
            d_left, b_left = "∞", "∞"
        await update.message.reply_text(t["stats_msg"].format(d_left, b_left), parse_mode="Markdown")
        return

    if text == t["menu_join"]:
        await update.message.reply_text(f"📢 [Click here to join the channel]({PUBLIC_CHANNEL_URL})", parse_mode="Markdown", disable_web_page_preview=True)
        return

    if text == t["menu_help"]:
        await update.message.reply_text(f"💬 [Click here for FAQ / Support]({HELP_CHANNEL_URL})", parse_mode="Markdown", disable_web_page_preview=True)
        return
        
    if text == t["menu_lang"]:
        await language_command(update, context)
        return

    # --- Standard text processing ---
    if active_batch_sessions.get(user_id, False): return
    linking_states = load_linking_states()
    if linking_states.get(str(user_id)) == "waiting_for_channel":
        if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
            f_chat = update.message.forward_origin.chat
            user_channels = load_user_channels()
            user_channels[str(user_id)] = f_chat.id
            save_user_channels(user_channels)
            del linking_states[str(user_id)]
            save_linking_states(linking_states)
            keyboard = [[InlineKeyboardButton("🔄 Change Linked Channel", callback_data="change_channel")]]
            await update.message.reply_text(f"✅ **Channel Linked!**\n📢 {f_chat.title}\n🆔 `{f_chat.id}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("❌ Forward a message from your channel to link it.")
            return

    if update.message.forward_origin and getattr(update.message.forward_origin, 'type', None) == 'channel':
        f_chat = update.message.forward_origin.chat
        user_channels = load_user_channels()
        user_channels[str(user_id)] = f_chat.id
        save_user_channels(user_channels)
        keyboard = [[InlineKeyboardButton("🔄 Change Linked Channel", callback_data="change_channel")]]
        await update.message.reply_text(f"✅ **Channel Linked!**\n📢 {f_chat.title}\n🆔 `{f_chat.id}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    extracted_urls = re.findall(r'https?://[^\s]+', text)
    if not extracted_urls: return

    if len(extracted_urls) > 1:
        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{payload_key}")],
            [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{payload_key}")]
        ]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    url = extracted_urls[0]
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        await update.message.reply_text("❌ YouTube is paused.")
        return

    payload_key = f"single_{user_id}_{int(time.time())}"
    pending_single_links[payload_key] = url

    keyboard = [
        [InlineKeyboardButton(t["btn_video"], callback_data=f"fmt_vid_{payload_key}")],
        [InlineKeyboardButton(t["btn_audio"], callback_data=f"fmt_aud_{payload_key}")],
        [InlineKeyboardButton(t["btn_image"], callback_data=f"fmt_img_{payload_key}")],
        [InlineKeyboardButton(t["btn_sub"], callback_data=f"fmt_sub_{payload_key}")]
    ]
    await update.message.reply_text(t["ask_format"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if active_batch_sessions.get(user_id, False): return
    if not document.file_name or not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Please upload a valid `.txt` file.")
        return

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        extracted_urls = re.findall(r'https?://[^\s]+', file_bytes.decode('utf-8', errors='ignore'))
        if not extracted_urls:
            await update.message.reply_text("❌ No links found inside.")
            return

        payload_key = f"batch_{user_id}_{int(time.time())}"
        pending_batch_payloads[payload_key] = extracted_urls
        keyboard = [
            [InlineKeyboardButton(t["btn_chat"], callback_data=f"dest_chat_{payload_key}")],
            [InlineKeyboardButton(t["btn_chan"], callback_data=f"dest_chan_{payload_key}")]
        ]
        await update.message.reply_text(t["batch_detected"].format(len(extracted_urls)), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"File error: {e}")
        await update.message.reply_text("❌ Failed to read file.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.from_user.id != ADMIN_ID: return
    tokens = load_tokens()
    await update.message.reply_text(f"📊 **ADMIN STATS**\nTotal Users: {len(tokens)}", parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    lang = get_lang(user_id)
    t = LANGUAGES[lang]

    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        langs = load_json_file(LANG_FILE)
        langs[str(user_id)] = new_lang
        save_json_file(LANG_FILE, langs)
        new_t = LANGUAGES[new_lang]
        await query.answer(new_t["lang_set"], show_alert=True)
        # Update the bottom keyboard to the new language!
        await query.message.reply_text(new_t["welcome"], reply_markup=get_main_keyboard(new_lang), parse_mode="Markdown")
        await query.message.delete()
        return

    if data.startswith("fmt_"):
        parts = data.split("_", 2)
        fmt_type, payload_key = parts[1], parts[2]
        url = pending_single_links.pop(payload_key, None)
        if not url:
            await query.answer("❌ Session expired.", show_alert=True)
            return
        await query.answer("Processing...")
        await query.message.delete()

        dl_type = 'video'
        if fmt_type == 'aud': dl_type = 'audio'
        elif fmt_type == 'img': dl_type = 'images'
        elif fmt_type == 'sub': dl_type = 'subtitles'

        try:
            response = requests.post(f"{WEB_BASE_URL}/check-download", json={"user_id": user_id, "is_batch": False}, timeout=5)
            res_data = response.json() if response.status_code == 200 else {}
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text="❌ Server error.")
            return

        if res_data.get("status") != "allowed":
            bridge_link = f"{BRIDGE_URL}?user={user_id}&start_msg=0&end_msg=0"
            tokens = load_tokens()
            tokens[str(user_id)] = {"user_id": int(user_id), "msg_start": 0, "msg_end": 0, "clicked_ad": False, "verified": False, "expires": time.time() + 600}
            save_tokens(tokens)
            keyboard = [
                [InlineKeyboardButton(t["refill_btn"], url=bridge_link)],
                [InlineKeyboardButton(t["join_btn"], url=PUBLIC_CHANNEL_URL)],
                [InlineKeyboardButton(t["check_btn"], callback_data="verify_user")]
            ]
            await context.bot.send_message(chat_id=chat_id, text=t["limit_reached"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        status_msg = await context.bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type))

        try:
            file_paths, resolution, size_str = download_media_engine(url, dl_type)
            if not file_paths: raise ValueError("FILE_NOT_FOUND")

            if dl_type == 'images':
                media_group = [InputMediaPhoto(media=open(p, 'rb')) for p in file_paths]
                sent_media = await context.bot.send_media_group(chat_id=chat_id, media=media_group)
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)))
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [m.message_id for m in sent_media] + [warning_msg.message_id], DELETE_DELAY_TIME))
                for p in file_paths: os.remove(p)
            elif dl_type == 'audio':
                with open(file_paths[0], 'rb') as f:
                    sent_media = await context.bot.send_audio(chat_id=chat_id, audio=f, title="Extracted Audio", caption=f"🎵 **Audio**\n📦 Size: {size_str}", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["deletes_in_9"])
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_paths[0])
            elif dl_type == 'subtitles':
                with open(file_paths[0], 'rb') as f:
                    sent_media = await context.bot.send_document(chat_id=chat_id, document=f, caption=f"📝 **Subtitles**", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["deletes_in_9"])
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_paths[0])
            else:
                with open(file_paths[0], 'rb') as f:
                    sent_media = await context.bot.send_video(chat_id=chat_id, video=f, caption=f"✨ **Video**\n📐 Quality: {resolution}\n📦 Size: {size_str}", parse_mode="Markdown")
                warning_msg = await context.bot.send_message(chat_id=chat_id, text=t["deletes_in_9"])
                asyncio.create_task(schedule_deletion(context.bot, chat_id, [sent_media.message_id, warning_msg.message_id], DELETE_DELAY_TIME))
                os.remove(file_paths[0])

            await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception as e:
            logger.error(f"Single download error: {e}")
            error_msg = t["error_50mb"] if "FILE_TOO_LARGE" in str(e) else t["error_no_img"] if "NO_IMAGES" in str(e) else t["error_generic"]
            help_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Ask for Help", url=HELP_CHANNEL_URL)]])
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=error_msg, reply_markup=help_keyboard)
        return

    if data == "stop_batch":
        active_batch_sessions[user_id] = False
        await query.answer("🛑 Stopping...", show_alert=True)
        try: await query.edit_message_text("🛑 **Batch Stopped.**")
        except: pass
        return

    if data == "resume_batch":
        paused = paused_batches.pop(user_id, None)
        if not paused:
            await query.answer("❌ Session expired.", show_alert=True)
            return
        await query.answer("▶️ Resuming...")
        await query.message.delete()
        asyncio.create_task(process_url_batch(context.bot, user_id, paused["chat_id"], paused["target_destination_id"], paused["urls"], start_index=paused["next_index"]))
        return

    if data.startswith("dest_chat_") or data.startswith("dest_chan_"):
        parts = data.split("_", 2)
        action_type, payload_key = parts[1], parts[2]
        urls = pending_batch_payloads.pop(payload_key, None)
        if not urls:
            await query.answer("❌ Session expired.", show_alert=True)
            return

        if action_type == "chat":
            await query.answer("📥 Loading...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, chat_id, urls))
        elif action_type == "chan":
            user_channels = load_user_channels()
            target_channel_id = user_channels.get(str(user_id))
            if not target_channel_id:
                await query.answer("❌ No private channel linked!", show_alert=True)
                linking_states = load_linking_states()
                linking_states[str(user_id)] = "waiting_for_channel"
                save_linking_states(linking_states)
                await query.message.edit_text("📦 **Setup Required!**\n\n1. Make bot Admin in your channel.\n2. **Forward any message** from the channel here.", parse_mode="Markdown")
                return
            await query.answer("📢 Loading...")
            await query.message.delete()
            asyncio.create_task(process_url_batch(context.bot, user_id, chat_id, target_channel_id, urls))
        return

    if data == "change_channel":
        linking_states = load_linking_states()
        linking_states[str(user_id)] = "waiting_for_channel"
        save_linking_states(linking_states)
        await query.answer("🔄 Mode activated!")
        await query.message.reply_text("🔄 **Change Channel**\n\nForward a message from your new channel here.", parse_mode="Markdown")
        return

    if data == "verify_user":
        try:
            member = await context.bot.get_chat_member(chat_id=PUBLIC_CHANNEL_USERNAME, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                await query.answer("❌ Join public channel first!", show_alert=True)
                return
        except Exception:
            await query.answer("⚠️ Join the channel first!", show_alert=True)
            return

        tokens = load_tokens()
        user_str = str(user_id)
        if user_str not in tokens: return
        token_data = tokens[user_str]
        if not token_data.get("verified", False):
            await query.answer("❌ Finish the timer first!", show_alert=True)
            return

        msg_start, msg_end = token_data.get("msg_start", 0), token_data.get("msg_end", 0)
        del tokens[user_str]
        save_tokens(tokens)
        await query.answer("✅ Verified!")

        if user_id in paused_batches:
            keyboard = [[InlineKeyboardButton("▶️ Resume Batch", callback_data="resume_batch")]]
            await query.message.reply_text("✅ **Verified!** Refilled.\nClick below to resume!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        if msg_start == 0:
            await query.message.reply_text("✅ **Refilled!** You can download again.")
            return

        await query.message.reply_text("✅ **Verified!** Fetching bundle...")
        forwarded_ids = []
        try:
            for target_msg_id in range(msg_start, msg_end + 1):
                fwd = await context.bot.forward_message(chat_id=user_id, from_chat_id=DETECTED_CHANNEL_ID, message_id=target_msg_id)
                forwarded_ids.append(fwd.message_id)
                asyncio.sleep(0.2)
            warn = await context.bot.send_message(chat_id=user_id, text=t["deletes_in_9"])
            forwarded_ids.append(warn.message_id)
            asyncio.create_task(schedule_deletion(context.bot, user_id, forwarded_ids, DELETE_DELAY_TIME))
        except Exception as e:
            await query.message.reply_text(f"❌ Error: {e}")


def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("language", language_command))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media_link))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(CallbackQueryHandler(handle_buttons))
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()
    loop.run_until_complete(start_bot())

if not getattr(web_app, '_bot_started', False):
    web_app._bot_started = True
    print("Starting Telegram bot thread...")
    threading.Thread(target=run_telegram_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)