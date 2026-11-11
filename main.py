# -*- coding: utf-8 -*-
import time
import random
import json
import os
import hmac
import hashlib
import secrets
import sqlite3
import threading
import re as _re
import requests
from urllib.parse import parse_qsl, urlparse, parse_qs, quote
from urllib.request import Request, urlopen
import feedparser
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

app = Flask(__name__)
TOKEN_FILE = "/home/Michaelbbc/mysite/tokens.json"
REWARD_FILE = "/home/Michaelbbc/mysite/reward_config.json"
CATEGORIES_FILE = "/home/Michaelbbc/mysite/app_categories.json"
ITEMS_FILE = "/home/Michaelbbc/mysite/app_items.json"
POSTS_FILE = "/home/Michaelbbc/mysite/posts.json"
ADMIN_ID = 6248570946

# ===== ARCADE BACKUP CONFIG =====
ARCADE_BACKUP_FILE = "/home/Michaelbbc/mysite/arcade_backup.json"
BOT_CHANNEL_ID = "-1004347828512"

# ===== CONFIG =====
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
API_SECRET = os.getenv("API_SECRET", "change-me")

# ===== ARCADE BACKUP HELPERS =====
def load_arcade_backup():
    if os.path.exists(ARCADE_BACKUP_FILE):
        try:
            with open(ARCADE_BACKUP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_arcade_backup(data):
    try:
        with open(ARCADE_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving arcade backup: {e}")

def download_backup_from_telegram():
    """Attempts to download the latest arcade_backup.json from the Telegram channel via the Bot API."""
    if not BOT_TOKEN:
        return False
    
    try:
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
                                    with open(ARCADE_BACKUP_FILE, "wb") as f:
                                        f.write(r_download.content)
                                    print("Successfully restored arcade_backup.json from Telegram.")
                                    return True
    except Exception as e:
        print(f"Error downloading backup: {e}")
    return False

# Check if backup file is missing on startup, and try to fetch it
if not os.path.exists(ARCADE_BACKUP_FILE):
    print("Arcade backup missing, attempting to restore from Telegram...")
    download_backup_from_telegram()

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_tokens(tokens):
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=4)
    except Exception as e:
        print(f"Error saving tokens: {e}")

# ===== DYNAMIC ITEM STORAGE =====
def load_items():
    if os.path.exists(ITEMS_FILE):
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                return repair_obj(json.load(f))
        except:
            pass
    return [
        {"id": "1", "title": "Private Pharmacy Course Material", "desc": "Complete pharmacognosy & physical pharmaceutics vault files.", "meta": "📄 PDF • 14MB", "image": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=500&q=80", "category": "Courses", "downloads": 0, "pinned": True, "link": "https://t.me/Michaelbbcvaultbot?start=vid1"},
        {"id": "2", "title": "Tic Tac Toe Mini Game Bot", "desc": "Source code & build guide for interactive telegram arcade games.", "meta": "📦 ZIP • 3.2MB", "image": "https://images.unsplash.com/photo-1611996575749-79a3a250f948?w=500&q=80", "category": "Mini Apps", "downloads": 0, "pinned": False, "link": "https://t.me/Michaelbbcvaultbot?start=vid2"}
    ]

def save_items(items):
    try:
        with open(ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving items: {e}")

DEFAULT_CATEGORIES = ["Courses", "Vault Files", "Mini Apps"]

def load_categories():
    try:
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            data = repair_obj(json.load(f))
            if isinstance(data, list):
                cleaned = list(dict.fromkeys(str(x).strip() for x in data if str(x).strip()))
                return cleaned or DEFAULT_CATEGORIES.copy()
    except (OSError, ValueError, TypeError):
        pass
    existing = [str(i.get("category", "")).strip() for i in load_items()]
    return list(dict.fromkeys(DEFAULT_CATEGORIES + [x for x in existing if x]))

def save_categories(categories):
    with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=4, ensure_ascii=False)

# ===== BLOG CONFIG =====
DEFAULT_BLOG = {
    "url": "",
    "title": "My Blog",
    "tagline": "Latest news, tutorials and updates — fresh daily.",
    "about": "I write about tech, coding, student life, and side hustles. Follow for weekly updates.",
    "cta_text": "🚀 Visit My Blog",
    "categories": [
        {"label": "📰 Latest", "url": ""},
        {"label": "🔥 Trending", "url": ""},
        {"label": "📚 Topics", "url": ""},
        {"label": "💬 Contact", "url": ""}
    ],
    "socials": [
        {"name": "WhatsApp", "url": ""},
        {"name": "Telegram", "url": ""},
        {"name": "X", "url": ""},
        {"name": "Instagram", "url": ""}
    ],
    "latest_count": 3
}

def load_blog_cfg():
    cfg = dict(DEFAULT_BLOG)
    if os.path.exists(REWARD_FILE):
        try:
            with open(REWARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data.get("blog"), dict):
                    cfg.update(data["blog"])
                elif isinstance(data.get("blog_url"), str) and data["blog_url"]:
                    cfg["url"] = data["blog_url"]
        except Exception:
            pass
    return cfg

def save_blog_cfg(updates):
    data = {}
    if os.path.exists(REWARD_FILE):
        try:
            with open(REWARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    blog = data.get("blog") if isinstance(data.get("blog"), dict) else {}
    blog.update(updates or {})
    data["blog"] = blog
    try:
        with open(REWARD_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving blog: {e}")

def load_blog_url():
    return load_blog_cfg().get("url", "")

def save_blog_url(url):
    save_blog_cfg({"url": url.strip()})

# ===== POSTS STORAGE =====
def load_posts():
    if os.path.exists(POSTS_FILE):
        try:
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_posts(posts):
    try:
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving posts: {e}")

# ===== BLOG FEED FETCHER =====
_BLOG_CACHE = {"url": None, "ts": 0, "posts": []}
_BLOG_LOCK = threading.Lock()

def _strip_html(s):
    return _re.sub(r"<[^>]+>", "", s or "").strip()

def fetch_blog_posts(blog_url, force=False):
    if not blog_url: return []
    if "blogspot.com" not in blog_url:
        blog_url = "https://michaelbbc.blogspot.com"
    now = time.time()
    with _BLOG_LOCK:
        if not force and _BLOG_CACHE["url"] == blog_url and now - _BLOG_CACHE["ts"] < 300:
            return _BLOG_CACHE["posts"]
        posts = []
        try:
            rss = blog_url.rstrip("/") + "/feeds/posts/default?alt=rss"
            api_url = f"https://api.rss2json.com/v1/api.json?rss_url={quote(rss)}"
            req = Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                if data.get("status") == "ok" and data.get("items"):
                    for entry in data["items"][:6]:
                        img = entry.get("thumbnail", "")
                        if not img and entry.get("content"):
                            m = _re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry["content"])
                            if m: img = m.group(1)
                        posts.append({
                            "title": _strip_html(entry.get("title", ""))[:120],
                            "url": entry.get("link", ""),
                            "thumb": img,
                            "summary": _strip_html(entry.get("description", ""))[:160]
                        })
        except Exception as e:
            print(f"rss2json error: {e}")
        if not posts:
            try:
                feed_url = blog_url.rstrip("/") + "/feeds/posts/default?alt=rss"
                req = Request(feed_url, headers={"User-Agent": "Mozilla/5.0 MichaelBBC-Vault/1.0"})
                with urlopen(req, timeout=12) as r:
                    body = r.read()
                parsed = feedparser.parse(body)
                for entry in parsed.entries[:6]:
                    img = ""
                    if "media_content" in entry and entry.media_content:
                        img = entry.media_content[0].get("url", "")
                    elif "summary" in entry:
                        m = _re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary)
                        if m: img = m.group(1)
                    posts.append({
                        "title": _strip_html(entry.get("title", ""))[:120],
                        "url": entry.get("link", ""),
                        "thumb": img,
                        "summary": _strip_html(entry.get("summary", entry.get("description", "")))[:160]
                    })
            except Exception as e:
                print(f"Feedparser error: {e}")
        with _BLOG_LOCK:
            _BLOG_CACHE["url"] = blog_url
            _BLOG_CACHE["ts"] = now
            _BLOG_CACHE["posts"] = posts
        return posts

# ===== TEXT REPAIR =====
import shutil as _shutil
_CP1252_EXTRA = {}
for _b in range(0x80, 0xA0):
    try:
        _CP1252_EXTRA[bytes([_b]).decode("cp1252")] = _b
    except UnicodeDecodeError:
        pass

_RUN_CLASS = "[\u0080-\u00ff" + " ".join(_CP1252_EXTRA.keys()) + "]+"
_RUN_RE = _re.compile(_RUN_CLASS)
_MOJI_LEADS = "\u00c2\u00c3\u00e2\u00e3\u00f0"
_TRUNCATED_FIX = {b"\xf0\x9f\x93": b"\x81", b"\xf0\x9f\x83": b"\x8f", b"\xef\xb8": b"\x8f"}

def _run_to_bytes(run):
    out = bytearray()
    for ch in run:
        o = ord(ch)
        if o <= 0xFF:
            out.append(o)
        elif ch in _CP1252_EXTRA:
            out.append(_CP1252_EXTRA[ch])
        else:
            return None
    return bytes(out)

def _decode_damaged(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for tail, fix in _TRUNCATED_FIX.items():
        if data.endswith(tail):
            try:
                return (data + fix).decode("utf-8")
            except UnicodeDecodeError:
                pass
    if len(data) >= 4:
        for cut in (1, 2, 3):
            try:
                kept = data[:-cut].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if kept:
                return kept
    return None

def _fix_run(match):
    run = match.group(0)
    if run[0] not in _MOJI_LEADS:
        return run
    data = _run_to_bytes(run)
    if data is None:
        return run
    fixed = _decode_damaged(data)
    return run if fixed is None else fixed

def repair_text(value):
    if not isinstance(value, str):
        return value
    cur = value
    for _ in range(3):
        new = _RUN_RE.sub(_fix_run, cur)
        if new == cur:
            break
        cur = new
    return cur

def repair_obj(obj):
    if isinstance(obj, str):
        return repair_text(obj)
    if isinstance(obj, list):
        return [repair_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: repair_obj(v) for k, v in obj.items()}
    return obj

_text_repair_done = False

def repair_data_files():
    global _text_repair_done
    _text_repair_done = True
    for path in (ITEMS_FILE, CATEGORIES_FILE):
        try:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            fixed = repair_obj(data)
            if fixed != data:
                backup = path + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
                _shutil.copyfile(path, backup)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(fixed, f, indent=4, ensure_ascii=False)
                print("Text repair: fixed " + os.path.basename(path) + " (backup: " + os.path.basename(backup) + ")")
        except Exception as e:
            print("Text repair skipped for " + str(path) + ": " + str(e))

def get_free():
    if os.path.exists(REWARD_FILE):
        try:
            with open(REWARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("free", 4))
        except:
            pass
    return 4

def get_reward():
    if os.path.exists(REWARD_FILE):
        try:
            with open(REWARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("reward", 1))
        except:
            pass
    return 1

def get_user_profile(user_id, tokens):
    user_id_str = str(user_id)
    now = time.time()
    day_in_seconds = 86400
    if user_id_str not in tokens:
        tokens[user_id_str] = {
            "user_id": int(user_id),
            "downloads_left": get_free(),
            "batch_downloads_left": get_free() * 5,
            "last_reset": now,
            "msg_start": 0,
            "msg_end": 0,
            "clicked_ad": False,
            "verified": False,
            "expires": 0
        }
    else:
        profile = tokens[user_id_str]
        if now - profile.get("last_reset", 0) >= day_in_seconds:
            profile["downloads_left"] = get_free()
            profile["batch_downloads_left"] = get_free() * 5
            profile["last_reset"] = now
            profile["verified"] = False
    return tokens[user_id_str]

# ===== 1. POLISHED FRONTEND HUB TEMPLATE (ROUTE /) =====
HUB_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>MichaelBBC Vault & News Hub</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root {
--bg-color: #101114;
--card-bg: #191b20;
--accent-color: #8b75ff;
--text-color: #f7f7fb;
--muted-color: #a0a2ad;
--green-color: #24c66b;
--red-color: #ef4444;
--spring-transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: radial-gradient(ellipse at 85% 0%, rgba(111,83,220,.14), transparent 34%), var(--bg-color); color: var(--text-color); margin: 0; padding-bottom: 90px; -webkit-tap-highlight-color: transparent; user-select: none; }
.header { padding: 16px 20px; background: rgba(15,16,20,.94); backdrop-filter: blur(14px); display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.06); position: sticky; top: 0; z-index: 90; }
.header h2 { margin: 0; font-size: 18px; color: #a995ff; font-weight: 700; letter-spacing: -.4px; }
.badge { font-size: 11px; background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 6px; color: var(--muted-color); }
.bouncy-btn, .card, .cell, .chip, .game-card { transition: var(--spring-transition); cursor: pointer; }
.bouncy-btn:active, .card:active, .chip:active, .game-card:active { transform: scale(0.95); }
.tab-content { display: none; padding: 18px 16px 26px; opacity: 0; transform: translateY(12px); transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.tab-content.active { display: block; opacity: 1; transform: translateY(0); }
.search-box { position: relative; margin-bottom: 14px; }
.search-box input { width: 100%; background: #1b1d23; border: 1px solid rgba(255, 255, 255, 0.07); color: var(--text-color); padding: 14px 16px; border-radius: 13px; font-size: 14px; box-sizing: border-box; outline: none; }
.filter-bar { display: flex; gap: 9px; overflow-x: auto; padding-bottom: 17px; scrollbar-width: none; }
.filter-bar::-webkit-scrollbar { display: none; }
.chip { background: #1c1e25; padding: 8px 15px; border-radius: 20px; font-size: 12px; white-space: nowrap; color: #b5b6c0; border: 1px solid rgba(255,255,255,0.07); }
.chip.active { background: #8b75ff; border-color: #8b75ff; color: #fff; font-weight: bold; }
.grid { display: grid; grid-template-columns: 1fr; gap: 17px; }
@media(min-width: 500px) { .grid { grid-template-columns: 1fr 1fr; } }
.card { background: var(--card-bg); border-radius: 17px; overflow: hidden; border: 1px solid rgba(255,255,255,0.065); box-shadow: 0 8px 24px rgba(0,0,0,.17); opacity: 0; animation: cardPopIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; position: relative; }
.card.pinned { border: 1px solid rgba(151,128,255, .65); }
.pinned-badge { position: absolute; top: 8px; right: 8px; background: #8b75ff; color: #fff; font-size: 10px; font-weight: bold; padding: 3px 8px; border-radius: 7px; z-index: 2; }
.card img { width: 100%; height: 165px; object-fit: cover; background: #24232e; }
.card-body { padding: 15px 15px 16px; }
.card-title { font-size: 16px; font-weight: 700; margin-bottom: 7px; letter-spacing: -.2px; }
.card-meta { font-size: 11px; color: var(--muted-color); margin-bottom: 10px; display: flex; gap: 7px; align-items: center; }
.card-desc { font-size: 12px; color: var(--muted-color); margin-bottom: 15px; line-height: 1.55; }
.action-row { display: flex; gap: 9px; }
.btn { flex: 1; background: var(--green-color); color: #fff; border: 0; min-height: 43px; padding: 10px; border-radius: 10px; font-weight: 700; font-size: 13px; text-align: center; text-decoration: none; display: inline-flex; justify-content: center; align-items: center; }
.btn-copy { background: #292b33; width: 45px; flex: none; color: var(--text-color); }
.btn-danger { background: var(--red-color); padding: 6px 12px; font-size: 11px; flex: unset; }
.btn-edit { background: #292b33; color: #fff; padding: 6px 12px; font-size: 11px; flex: unset; border: 1px solid rgba(255,255,255,0.1); }
@keyframes cardPopIn { 0% { opacity: 0; transform: scale(0.85) translateY(20px); } 100% { opacity: 1; transform: scale(1) translateY(0); } }
.nav-bar { position: fixed; bottom: 0; left: 0; width: 100%; background: rgba(12,13,16,.97); backdrop-filter: blur(16px); display: flex; justify-content: space-around; padding: 11px 0 calc(10px + env(safe-area-inset-bottom)); border-top: 1px solid rgba(255,255,255,0.07); z-index: 100; }
.nav-item { background: none; border: 0; color: var(--muted-color); font-size: 11px; display: flex; flex-direction: column; align-items: center; gap: 5px; }
.nav-item.active { color: #a995ff; font-weight: bold; }
.news-hero { background: linear-gradient(135deg, #282044 0%, #171a29 100%); border: 1px solid rgba(190,173,255,.18); border-radius: 20px; padding: 20px; margin-bottom: 20px; }
.news-hero h2 { margin: 0 0 8px; font-size: 20px; letter-spacing: -.5px; }
.news-hero p { color: #d1cce2; font-size: 13px; margin: 0 0 14px; line-height: 1.45; }
.blog-cta { display:flex; align-items:center; justify-content:center; gap:8px; width:100%; padding:18px; margin-bottom:16px; border-radius:16px; background:linear-gradient(135deg,#8b75ff,#5c3fe0); color:#fff; text-align:center; font-weight:800; font-size:16px; text-decoration: none; border:1px solid rgba(255,255,255,.2); box-shadow:0 8px 24px rgba(139,117,255,.35); box-sizing:border-box; }
.blog-cta:active { transform:scale(0.97); }
.hero { position: relative; border-radius: 22px; padding: 22px 20px; margin-bottom: 18px; overflow: hidden; background: linear-gradient(135deg, #3a2b6b 0%, #241b46 48%, #171a29 100%); border: 1px solid rgba(190,173,255,.28); box-shadow: 0 12px 32px rgba(111,83,220,.24); }
.hero:before { content: ""; position: absolute; width: 220px; height: 220px; background: radial-gradient(circle, rgba(139,117,255,.55), transparent 70%); top: -100px; right: -80px; pointer-events: none; }
.hero .eyebrow { font-size: 11px; letter-spacing: 2px; color: #bfb1ff; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; }
.hero h1 { margin: 0 0 6px; font-size: 24px; font-weight: 800; letter-spacing: -.6px; line-height: 1.15; }
.hero p { margin: 0 0 16px; color: #d1cce2; font-size: 13px; line-height: 1.5; }
.section-title { font-size: 15px; font-weight: 800; margin: 22px 2px 12px; display: flex; justify-content: space-between; align-items: center; letter-spacing: -.2px; }
.section-title small { font-size: 11px; color: var(--muted-color); font-weight: 500; }
.cat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 6px; }
.cat-btn { background: var(--card-bg); border: 1px solid rgba(255,255,255,.08); border-radius: 14px; padding: 14px 12px; text-align: center; font-size: 13px; font-weight: 700; color: var(--text-color); text-decoration: none; transition: var(--spring-transition); }
.cat-btn:active { transform: scale(.96); background: #20222b; }
.post-card { display: flex; flex-direction: column; background: var(--card-bg); border: 1px solid rgba(255,255,255,.07); border-radius: 16px; overflow: hidden; margin-bottom: 16px; text-decoration: none; color: var(--text-color); transition: var(--spring-transition); }
.post-card:active { transform: scale(.98); background: #20222b; }
.post-img { width: 100%; height: auto; max-height: 250px; object-fit: cover; background: #24232e; }
.post-body { padding: 16px; }
.post-title { font-size: 16px; font-weight: 800; line-height: 1.35; margin-bottom: 8px; letter-spacing: -.2px; }
.post-content { font-size: 13px; color: var(--muted-color); line-height: 1.55; margin-bottom: 14px; position: relative; }
.post-content img { max-width: 100%; height: auto; border-radius: 10px; margin: 10px 0; display: block; }
.post-content.collapsed { max-height: 150px; overflow: hidden; mask-image: linear-gradient(to bottom, black 70%, transparent 100%); -webkit-mask-image: linear-gradient(to bottom, black 70%, transparent 100%); }
.read-more-btn { display: inline-block; background: transparent; color: var(--accent-color); font-size: 12px; font-weight: 700; border: 0; padding: 8px 0; cursor: pointer; margin-bottom: 10px; }
.post-link-btn { display: none; width: 100%; margin-top: 10px; }
.post-card.expanded .post-link-btn { display: inline-flex; }
.about-card { background: var(--card-bg); border: 1px solid rgba(255,255,255,.07); border-radius: 16px; padding: 16px; margin-top: 6px; }
.about-card p { margin: 0 0 12px; color: var(--muted-color); font-size: 13px; line-height: 1.55; }
.socials { display: flex; gap: 8px; flex-wrap: wrap; }
.social-btn { padding: 8px 14px; border-radius: 20px; background: #24232e; color: var(--text-color); font-size: 12px; font-weight: 700; text-decoration: none; border: 1px solid rgba(255,255,255,.08); transition: var(--spring-transition); }
.social-btn:active { transform: scale(.94); }
.empty-msg { text-align: center; color: var(--muted-color); font-size: 13px; padding: 20px; background: var(--card-bg); border-radius: 14px; border: 1px dashed rgba(255,255,255,.1); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.game-board { display: grid; grid-template-columns: repeat(3, 80px); gap: 10px; justify-content: center; margin: 20px auto; }
.cell { width: 80px; height: 80px; background: var(--card-bg); border: 2px solid rgba(255,255,255,0.1); font-size: 32px; font-weight: bold; color: var(--accent-color); display: flex; align-items: center; justify-content: center; border-radius: 12px; }
.cell-pop { animation: popCell 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
@keyframes popCell { 0% { transform: scale(0); } 70% { transform: scale(1.25); } 100% { transform: scale(1); } }
.whot-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:8px 0 10px; }
.whot-status { color:var(--muted-color); font-size:13px; line-height:1.5; text-align:center; min-height:38px; }
.whot-modebar { display:flex; gap:7px; flex-wrap:wrap; justify-content:center; margin:12px 0; }
.whot-modebar button,.whot-mini-btn { border:1px solid rgba(255,255,255,.18); border-radius:20px; padding:9px 12px; background:var(--card-bg); color:var(--text-color); font-weight:700; }
.whot-modebar button.active { background:var(--accent-color); color:#fff; }
.whot-opponent { display:flex; justify-content:space-between; align-items:center; padding:9px 12px; border-radius:10px; background:var(--card-bg); font-size:13px; margin:10px 0; }
.whot-table { position:relative; overflow:hidden; border-radius:22px; padding:12px 9px 16px; background:radial-gradient(ellipse at center,#18794e 0%,#075638 68%,#043b29 100%); border:5px solid #7b4a25; box-shadow:inset 0 0 0 2px rgba(255,255,255,.12),0 8px 22px #0005; perspective: 1000px; }
.whot-fan { display:flex; justify-content:center; align-items:center; min-height:72px; padding:4px 0; }
.whot-back { width:39px;height:58px; margin-left:-15px; border-radius:7px; border:2px solid #f2d48b; background:repeating-linear-gradient(45deg,#8c1824 0 5px,#b62b36 5px 10px); box-shadow:0 3px 6px #0007; position:relative; }
.whot-back:first-child { margin-left:0; }
.whot-back:after { content:'WHOT'; position:absolute; inset:17px 1px auto; color:#ffe8a8; font-size:7px; font-weight:900; text-align:center; transform:rotate(-28deg); }
.whot-pile-wrap { display:flex; justify-content:center; gap:30px; align-items:center; padding:14px 0; }
.whot-pile-wrap small { display:block; text-align:center; color:#f6edcf; font-size:10px; margin-bottom:8px; letter-spacing:1px; }
.whot-card { position:relative; width:88px; min-height:116px; border-radius:11px; border:3px solid #f8e8bd; box-shadow:0 5px 14px rgba(0,0,0,.3); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px; font-size:27px; font-weight:900; color:#171717; background:linear-gradient(145deg,#fffdf4,#eadfbe); transform-style:preserve-3d; transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.whot-card:before { content:''; position:absolute; inset:5px; border:1px solid currentColor; border-radius:7px; opacity:.35; pointer-events:none; }
.whot-card .whot-symbol { font-size:37px; line-height:1; }
.whot-card small { color:#333; font-size:9px; margin:0; }
.draw-card { background:repeating-linear-gradient(45deg,#761b29 0 7px,#a62635 7px 14px); color:#fff; border-color:#f5d68c; font-size:16px; }
.whot-hand { display:flex; flex-wrap:wrap; justify-content:center; gap:6px; min-height:90px; }
.whot-hand .whot-card { width:60px; min-height:86px; font-size:18px; border-width:2px; cursor:pointer; }
.whot-hand .whot-card .whot-symbol { font-size:27px; }
.whot-hand .whot-card small { font-size:7px; }
.whot-hand .whot-card:disabled { opacity:.55; cursor:not-allowed; }
.whot-hand .whot-card:not(:disabled):hover { transform: translateY(-8px) scale(1.05); }
.whot-hand .whot-card:not(:disabled):active { transform:translateY(-14px) scale(1.1); }
.whot-actions { margin:16px auto; max-width:300px; display:flex; gap:8px; justify-content:center; flex-wrap:wrap; }
.whot-rules { color:var(--muted-color); font-size:11px; line-height:1.5; text-align:center; }
.whot-actor { position:absolute; z-index:8; width:110px; height:150px; left:50%; top:65%; opacity:0; pointer-events:none; transform:translate(-50%,-50%) translate(-120px,95px) rotate(-18deg) scale(0.9); transform-origin: bottom right; }
.whot-actor .arm { position:absolute; width:95px; height:34px; left:0; top:65px; border-radius:22px; background:linear-gradient(135deg,#f4c29d,#c18561); transform:rotate(-18deg); box-shadow:0 6px 14px rgba(0,0,0,0.4); }
.whot-actor .palm { position:absolute; width:48px; height:44px; left:68px; top:44px; border-radius:50%; background:linear-gradient(135deg,#f9d0b2,#bd805d); transform:rotate(-15deg); box-shadow:0 4px 8px rgba(0,0,0,0.3); }
.whot-actor.go { animation:whotReach 0.8s cubic-bezier(0.22, 0.75, 0.2, 1) both; }
.whot-actor.opponent { transform:translate(-50%,-50%) scaleX(-1) translate(-120px,95px) rotate(-18deg) scale(0.9); }
.whot-actor.opponent.go { animation:whotReachOpponent 0.8s cubic-bezier(0.22, 0.75, 0.2, 1) both; }
@keyframes whotReach { 0% { opacity: 0; transform: translate(-50%,-50%) translate(-130px, 120px) rotate(-25deg) scale(0.8); } 20% { opacity: 1; transform: translate(-50%,-50%) translate(-60px, 40px) rotate(-12deg) scale(0.95); } 70% { opacity: 1; transform: translate(-50%,-50%) translate(10px, -15px) rotate(4deg) scale(1.05); } 100% { opacity: 0; transform: translate(-50%,-50%) translate(30px, -40px) rotate(10deg) scale(1); } }
@keyframes whotReachOpponent { 0% { opacity: 0; transform: translate(-50%,-50%) scaleX(-1) translate(-130px, 120px) rotate(-25deg) scale(0.8); } 20% { opacity: 1; transform: translate(-50%,-50%) scaleX(-1) translate(-60px, 40px) rotate(-12deg) scale(0.95); } 70% { opacity: 1; transform: translate(-50%,-50%) scaleX(-1) translate(10px, -15px) rotate(4deg) scale(1.05); } 100% { opacity: 0; transform: translate(-50%,-50%) scaleX(-1) translate(30px, -40px) rotate(10deg) scale(1); } }
.whot-play-card { animation:whotCardLand 0.5s cubic-bezier(0.18, 0.8, 0.25, 1) both; }
@keyframes whotCardLand { 0% { transform: translateY(70px) rotate(-22deg) scale(0.7); opacity: 0.2; } 70% { transform: translateY(-8px) rotate(3deg) scale(1.08); opacity: 1; } 100% { transform: none; opacity: 1; } }
@media(max-width:360px) { .whot-hand .whot-card { width:52px; min-height:77px; } .whot-pile-wrap { gap:20px; } .whot-back{width:32px;height:50px;margin-left:-13px} }
.arcade-subnav{display:flex;gap:7px;overflow-x:auto;padding:4px 0 14px;scrollbar-width:none}.arcade-subnav .chip{flex:none}
.arcade-panel{background:var(--card-bg);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:14px;margin:10px 0 16px}
.arcade-btn{border:1px solid rgba(255,255,255,.14);background:#292b33;color:#fff;border-radius:11px;padding:10px 13px;font-weight:700;margin:3px;cursor:pointer}
.arcade-btn.primary{background:var(--accent-color);border-color:var(--accent-color)}
.sea-board{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:3px;width:100%;max-width:430px;margin:10px auto;touch-action:manipulation}
.sea-cell{aspect-ratio:1/1;min-width:0;border:1px solid rgba(255,255,255,.15);border-radius:5px;background:#2478a5;color:#fff;padding:0;font-size:clamp(10px,3vw,16px);font-weight:900}
.sea-cell.own{background:#a96849}.sea-cell.ship{background:#c47c55}.sea-cell.hit{background:#df594d}.sea-cell.miss{background:#d9e8ee;color:#28617c}.sea-cell.target{outline:2px solid #ffe16a;outline-offset:-2px}
.sea-cell:disabled{opacity:1}.sea-ship-picks{display:flex;gap:6px;justify-content:center;flex-wrap:wrap}.sea-ship-picks button{font-size:12px}
.sea-status{text-align:center;color:var(--muted-color);min-height:36px;font-size:13px;line-height:1.45}
.word-wheel{width:min(270px,78vw);height:min(270px,78vw);border-radius:50%;background:#bd7da4;border:9px solid #d28caf;margin:15px auto;display:flex;align-items:center;justify-content:center;position:relative}
.word-wheel button{position:absolute;width:48px;height:48px;border:0;border-radius:13px;background:#f1c5d9;color:#34313a;font-size:25px;font-weight:900}
.word-wheel button:nth-child(1){top:12px;left:calc(50% - 24px)}.word-wheel button:nth-child(2){right:20px;top:calc(50% - 24px)}.word-wheel button:nth-child(3){bottom:12px;left:calc(50% - 24px)}.word-wheel button:nth-child(4){left:20px;top:calc(50% - 24px)}
.word-current{text-align:center;font-size:26px;letter-spacing:5px;min-height:36px;font-weight:900}.word-targets{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.word-target{background:#252832;border-radius:9px;padding:9px;text-align:center;letter-spacing:3px;font-weight:800;color:#aaa}.word-target.done{color:#66d68a;background:#183d2c}
.water-row{display:flex;justify-content:center;align-items:flex-end;gap:12px;flex-wrap:wrap;padding:20px 4px}.water-tube{height:150px;width:42px;border:3px solid #aab7c9;border-top:0;border-radius:0 0 15px 15px;display:flex;flex-direction:column-reverse;overflow:hidden;background:#ffffff12;padding:2px;cursor:pointer}.water-layer{height:25%;min-height:0;border-radius:3px}.water-tube.selected{transform:translateY(-9px);border-color:#ffe16a}.water-controls{text-align:center}
.sea-board{position:relative;padding:5px;border-radius:13px;background:radial-gradient(ellipse at 45% 35%,#2f9bc0 0%,#12658f 52%,#073b65 100%);box-shadow:inset 0 0 22px #031d3a99,0 8px 20px #0004;}
.sea-cell{position:relative;overflow:hidden;border:1px solid #ffffff20!important;border-radius:3px!important;background:linear-gradient(145deg,#2489b1,#12648f 60%,#0c527d)!important;box-shadow:inset 0 1px 4px #b9edff22;transition:filter .2s,transform .18s;}
.sea-cell:after{content:'';position:absolute;inset:0;background:repeating-linear-gradient(115deg,transparent 0 9px,#d8f6ff08 10px 11px);pointer-events:none}
.sea-cell.own{background:linear-gradient(145deg,#247fa2,#0b557e)!important}
.sea-cell.ship{background:linear-gradient(180deg,#8799a3,#465965 35%,#263d4c 70%,#172a37)!important;border:1px solid #c3d3d8!important;box-shadow:inset 0 2px 4px #fff7,inset 0 -3px 4px #0009,0 2px 3px #0018}
.sea-cell.ship:before{content:' ';position:absolute;left:12%;right:12%;top:27%;height:46%;border-radius:45% 45% 35% 35%;background:linear-gradient(180deg,#dce5e8,#667983 48%,#253d4a);box-shadow:0 1px 2px #0008}
.sea-cell.ship:before,.sea-cell.ship:after{display:none}
.sea-ship-art{position:absolute;z-index:7;pointer-events:none;filter:drop-shadow(0 3px 3px #001b);overflow:visible}
.sea-ship-art svg{width:100%;height:100%;overflow:visible}.sea-ship-art.sunk{filter:drop-shadow(0 0 5px #ff6b32) sepia(.72) saturate(1.7) hue-rotate(325deg);opacity:.94}.sea-ship-art.sunk:after{content:'';position:absolute;inset:8% 12%;border-radius:45%;background:radial-gradient(ellipse at 35% 45%,#ffb13b88,transparent 24%),radial-gradient(ellipse at 70% 55%,#ff542c66,transparent 30%);mix-blend-mode:screen;animation:seaWreckGlow 1.3s ease-in-out infinite alternate}@keyframes seaWreckGlow{from{opacity:.35}to{opacity:.9}}
.sea-cell.ship:after{content:'▪  ▪';position:absolute;z-index:1;top:34%;left:23%;right:20%;font-size:clamp(5px,1.7vw,9px);letter-spacing:3px;color:#eaf5f5;text-shadow:0 1px 2px #111}
.sea-impact-mark{position:absolute;z-index:10;inset:0;display:grid;place-items:center;color:#fff3a8;font-size:clamp(17px,4vw,26px);text-shadow:0 0 10px #ff3b16,0 2px 3px #000;pointer-events:none;animation:seaBlast .55s ease-out}
.sea-cell.hit{background:radial-gradient(circle,#ffe8a2 0 9%,#ff7a32 15%,#b51f25 38%,#45252c 70%)!important;animation:seaHit .55s ease-out}
.sea-cell.hit:before{content:'✹';position:absolute;inset:0;display:grid;place-items:center;color:#fff1b0;font-size:clamp(16px,4vw,25px);text-shadow:0 0 9px #ff4b00;animation:seaBlast .55s ease-out}
.sea-cell.miss{background:radial-gradient(circle,#e5fbff 0 5%,#70d9f5 8%,#176b98 30%,#0b527e 75%)!important}
.sea-cell.miss:before{content:'';position:absolute;width:45%;height:45%;left:27%;top:25%;border:2px solid #c8f7ff;border-radius:50%;animation:seaRipple .65s ease-out}
.sea-cell.target:not(:disabled){outline:2px solid #ffe17a;outline-offset:-3px;cursor:crosshair}
.sea-cell:disabled{opacity:1}
@keyframes seaHit{0%{filter:brightness(2.2);transform:scale(.8)}100%{filter:none;transform:scale(1)}}
@keyframes seaBlast{0%{transform:scale(.1) rotate(-30deg);opacity:0}45%{transform:scale(1.5) rotate(25deg);opacity:1}100%{transform:scale(1);opacity:.9}}
@keyframes seaRipple{0%{transform:scale(.1);opacity:1}100%{transform:scale(2.4);opacity:0}}
.sea-shell{position:fixed;z-index:30;width:9px;height:15px;border-radius:60% 60% 35% 35%;background:linear-gradient(90deg,#493d32,#d7c4a0 45%,#4a3526);box-shadow:0 0 8px #ffd37a;pointer-events:none;animation:seaShellFly .48s cubic-bezier(.2,.7,.25,1) forwards}
@keyframes seaShellFly{0%{transform:translate(0,0) rotate(35deg) scale(1.2);opacity:1}85%{opacity:1}100%{transform:translate(var(--dx),var(--dy)) rotate(420deg) scale(.55);opacity:0}}
.sea-cannon{position:relative;width:76px;height:36px;margin:4px auto 2px;filter:drop-shadow(0 3px 3px #0018)}
.sea-turret{position:absolute;left:22px;bottom:2px;width:34px;height:25px;border-radius:11px 11px 7px 7px;background:linear-gradient(145deg,#b7c5c9,#566b76 48%,#263b47);border:2px solid #d4e1e4;box-shadow:inset 0 2px 3px #fff8}
.sea-barrel{position:absolute;left:35px;top:4px;width:37px;height:9px;border-radius:6px 8px 8px 6px;background:linear-gradient(#dbe3e5,#465b66 55%,#192c36);border:1px solid #d6e1e4;transform:rotate(-22deg);transform-origin:5px 50%}
.sea-cannon.recoil .sea-barrel{animation:cannonRecoil .22s ease-out}
@keyframes cannonRecoil{0%{transform:rotate(-22deg) translateX(0)}45%{transform:rotate(-22deg) translateX(-7px)}100%{transform:rotate(-22deg) translateX(0)}}
.sea-action-row{display:flex;gap:7px;justify-content:center;flex-wrap:wrap;margin:9px 0}
.sea-fire-flash{animation:seaFireFlash .45s ease-out}@keyframes seaFireFlash{0%{filter:brightness(1)}25%{filter:brightness(2.5)}100%{filter:brightness(1)}}
.word-stage{background:radial-gradient(ellipse at top,#a76b9e,#714879 75%);border-radius:18px;padding:15px;color:#fff;overflow:hidden}
.word-crossword{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:5px;max-width:420px;margin:12px auto 18px}
.word-cell{aspect-ratio:1;border-radius:7px;background:#75ce38;color:#263d36;display:grid;place-items:center;font-weight:900;font-size:clamp(17px,5vw,27px);box-shadow:inset 0 -3px 0 #438d25;animation:wordCellIn .28s both}
.word-cell.blank{background:transparent;box-shadow:none}.word-cell.empty{background:#fff;color:#333;box-shadow:none}
@keyframes wordCellIn{from{transform:scale(.65);opacity:.3}to{transform:scale(1);opacity:1}}
.word-wheel{width:min(270px,78vw);height:min(270px,78vw);border-radius:50%;background:radial-gradient(circle at 35% 25%,#d99bb9,#b56f98);border:10px solid #d28caf;box-shadow:inset 0 0 0 5px #e4aac5,0 8px 18px #32152f55;margin:15px auto;touch-action:none}
.word-wheel button{width:52px;height:52px;border-radius:16px;background:#f5c8dc;box-shadow:0 4px 0 #a65e83,0 5px 12px #401d3855;touch-action:none;user-select:none;transition:transform .12s,background .12s}
.word-wheel button.picked{background:#fff0a8;transform:scale(1.12);box-shadow:0 0 0 4px #ffe58b66,0 4px 0 #a65e83}
.word-current{min-height:42px;background:#fff2;border-radius:10px;padding:6px;letter-spacing:5px}
.word-found-list{display:flex;justify-content:center;gap:7px;flex-wrap:wrap;font-size:12px}
.word-found-list span{background:#ffffff22;padding:5px 8px;border-radius:8px}
.water-row{gap:17px;perspective:900px}
.water-tube{position:relative;height:166px;width:48px;border:3px solid #dceaf4;border-top:0;border-radius:0 0 17px 17px;background:linear-gradient(90deg,#ffffff28,#ffffff08 35%,#ffffff30 75%,#ffffff12);box-shadow:inset 5px 0 8px #fff3,inset -5px 0 8px #0002,0 8px 13px #0004;overflow:visible;transition:transform .25s,border-color .25s;}
.water-tube:before{content:'';position:absolute;left:-3px;right:-3px;top:-7px;height:9px;border:3px solid #e6f5ff;border-radius:50%;background:#c9efff33;z-index:3}
.water-tube:after{content:'';position:absolute;left:7px;top:9px;width:5px;height:72%;border-radius:8px;background:linear-gradient(#fff9,#fff0);pointer-events:none}
.water-layer{height:25%;width:100%;border-radius:4px 4px 2px 2px;position:relative;box-shadow:inset 0 3px 5px #fff5,inset 0 -3px 4px #0002;animation:waterSettle .25s ease-out both}
.water-layer:after{content:'';position:absolute;left:0;right:0;top:0;height:4px;border-radius:50%;background:#ffffff75}
.water-tube.selected{transform:translateY(-13px) rotate(-3deg);border-color:#ffe16a;filter:drop-shadow(0 0 8px #ffe16a66)}
.water-tube.pouring{animation:waterTilt .55s ease-in-out}
.water-layer.flowing{animation:waterFlow .65s ease-in-out}
@keyframes waterTilt{0%,100%{transform:translateY(-8px) rotate(0)}35%,70%{transform:translateY(-16px) rotate(var(--tilt,13deg))}}
@keyframes waterFlow{0%{transform:translateY(-12px);filter:brightness(1.5)}100%{transform:translateY(0);filter:brightness(1)}}
@keyframes waterSettle{from{transform:scaleY(.4);transform-origin:bottom;opacity:.5}to{transform:scaleY(1);opacity:1}}
.water-stream{position:fixed;width:9px;height:80px;border-radius:10px;z-index:999;background:linear-gradient(90deg,#fff5,var(--pour-color),#fff8);filter:drop-shadow(0 0 5px var(--pour-color));pointer-events:none;animation:waterStream .48s ease-in forwards}
@keyframes waterStream{0%{opacity:0;transform:translate(0,0) scaleY(.1)}25%{opacity:1;transform:translate(0,0) scaleY(1)}100%{opacity:0;transform:translate(var(--stream-dx),var(--stream-dy)) scaleY(.7)}}
.arcade-panel{overflow:hidden}
.word-stage{padding:clamp(10px,3vw,18px)}
.word-crossword{width:min(100%,390px);gap:clamp(3px,1.1vw,6px)}
.word-wheel{width:min(270px,76vw);height:min(270px,76vw);touch-action:none;user-select:none;-webkit-user-select:none}
.word-wheel button{position:absolute;touch-action:none;user-select:none;-webkit-user-select:none;-webkit-tap-highlight-color:transparent}
.word-wheel button.picked{z-index:2}
.word-current{font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.water-row{position:relative;isolation:isolate;overflow:visible;min-height:190px;gap:clamp(9px,3vw,18px);padding:24px 6px 18px}
.water-tube{transform-origin:50% 8%;will-change:transform;z-index:1}
.water-tube.pouring{animation:waterTilt .72s cubic-bezier(.35,.05,.2,1) both;z-index:4}
.water-tube.receiving{animation:waterReceive .72s ease-out both}
.water-tube .water-layer{display:block;flex:0 0 25%;height:25%;width:100%;will-change:transform}
.water-stream-svg{position:fixed;inset:0;width:100vw;height:100vh;z-index:99999;pointer-events:none;overflow:visible}
.water-stream-path{fill:none;stroke:var(--pour-color);stroke-width:11;stroke-linecap:round;filter:drop-shadow(0 0 5px var(--pour-color));stroke-dasharray:1;stroke-dashoffset:1;animation:waterPath .62s ease-in-out forwards}
.water-stream-glint{fill:none;stroke:#ffffffaa;stroke-width:3;stroke-linecap:round;stroke-dasharray:1;stroke-dashoffset:1;animation:waterPath .62s ease-in-out forwards}
.water-drop{fill:var(--pour-color);filter:drop-shadow(0 1px 3px #0005);animation:waterDrop .62s ease-in forwards}
@keyframes waterPath{0%{stroke-dashoffset:1;opacity:.1}20%{opacity:1}100%{stroke-dashoffset:0;opacity:.9}}
@keyframes waterDrop{0%{transform:translateY(-14px) scale(.7);opacity:0}35%{opacity:1}100%{transform:translateY(12px) scale(1.15);opacity:0}}
@keyframes waterReceive{0%,100%{filter:none}35%{filter:brightness(1.35)}65%{transform:translateY(2px)}}
.water-layer.water-moving{animation:waterLiquidMove .62s ease-in-out}
@keyframes waterLiquidMove{0%{transform:translateY(-8px) scaleY(.82)}45%{transform:translateY(2px) scaleY(1.08)}100%{transform:translateY(0) scaleY(1)}}
.arcade-result{position:fixed;inset:0;z-index:100000;display:none;place-items:center;background:#061525b8;padding:24px;backdrop-filter:blur(5px)}
.arcade-result.show{display:grid;animation:resultFade .22s ease-out}
.arcade-result-card{width:min(320px,90vw);padding:25px 20px;border-radius:22px;text-align:center;background:linear-gradient(145deg,#263e58,#172538);border:1px solid #ffffff35;box-shadow:0 18px 55px #0008;color:#fff}
.arcade-result-card h3{font-size:25px;margin:5px 0 8px}.arcade-result-card p{color:#d5e4ef}
@keyframes resultFade{from{opacity:0}to{opacity:1}}
@media(max-width:390px){.water-tube{width:39px;height:148px}.water-row{gap:8px}.word-wheel{width:min(210px,64vw);height:min(210px,64vw);margin:12px auto}.word-stage{padding:10px 8px}.word-crossword{max-width:100%;gap:3px}.word-cell{min-width:0;min-height:29px;font-size:13px}.word-stage>p{font-size:12px!important;line-height:1.35;margin:6px 0 10px}.word-found-list{min-height:24px}}
.word-stage{width:100%;max-width:560px;margin:8px auto;padding:clamp(10px,3vw,18px);box-sizing:border-box}
.word-instructions{font-size:12px;line-height:1.4;text-align:center;margin:0 auto 10px;max-width:390px;color:#fff}
.word-crossword{width:min(100%,360px);grid-template-columns:repeat(8,minmax(0,1fr));gap:clamp(2px,.8vw,5px);margin:8px auto 10px}
.word-cell{min-width:0;min-height:0;font-size:clamp(12px,3.5vw,21px);border-radius:5px}
.word-current{min-height:34px;display:flex;align-items:center;justify-content:center;margin:6px auto;padding:5px 8px;font-size:clamp(17px,5vw,23px);letter-spacing:2px;max-width:360px}
.word-wheel{width:min(238px,66vw);height:min(238px,66vw);margin:10px auto 8px;border-width:8px;position:relative}
.word-wheel button{width:clamp(40px,12vw,48px);height:clamp(40px,12vw,48px);font-size:clamp(19px,6vw,24px);border-radius:13px}
.word-found-list{min-height:22px;margin:5px auto 8px;max-width:400px}
.word-controls{display:flex;flex-wrap:wrap;justify-content:center;gap:7px;margin:8px auto}
.word-controls .arcade-btn{flex:1 1 42%;max-width:180px;min-height:40px;margin:0;padding:8px 9px;font-size:12px}
#word-status{min-height:20px;text-align:center;margin:6px 0 0;font-size:12px}
@media(max-width:420px){.word-stage{border-radius:14px;padding:9px 7px}.word-crossword{width:min(100%,330px);gap:2px}.word-cell{border-radius:4px;font-size:clamp(11px,3.2vw,16px)}.word-wheel{width:min(218px,62vw);height:min(218px,62vw);margin:8px auto}.word-wheel button{width:42px;height:42px;font-size:21px}.word-controls .arcade-btn{flex-basis:45%;font-size:11px;padding:7px 5px}.word-found-list{font-size:11px}}
@media(min-width:700px){.word-stage{padding:18px 24px}.word-crossword{width:min(100%,390px)}.word-wheel{width:250px;height:250px}}
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.stat-card { background: var(--bg-color); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); text-align: center; }
.stat-num { font-size: 20px; font-weight: bold; color: var(--accent-color); }
.stat-label { font-size: 11px; color: var(--muted-color); }
input, textarea, select { width: 100%; background: var(--bg-color); border: 1px solid rgba(255,255,255,0.1); color: var(--text-color); padding: 10px; border-radius: 8px; margin-bottom: 10px; box-sizing: border-box; outline: none; }
label { font-size: 12px; color: var(--muted-color); margin-bottom: 4px; display: block; }
.whot-shape-picker { display:none; position:fixed; inset:0; background:rgba(0,0,0,.75); z-index:200; align-items:center; justify-content:center; }
.whot-shape-picker.open { display:flex; }
.whot-shape-box { background:#191b20; padding:24px; border-radius:16px; text-align:center; border:1px solid rgba(255,255,255,.1); max-width:320px; width:90%; }
.whot-shape-box h3 { margin:0 0 16px; font-size:16px; }
.whot-shape-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.whot-shape-btn { padding:14px; border-radius:12px; border:1px solid rgba(255,255,255,.15); background:#24232e; color:#fff; font-weight:700; font-size:14px; cursor:pointer; }
.whot-shape-btn:active { transform:scale(.96); }
</style>
</head>
<body>
<div class="header">
<h2>📁 MichaelBBC Vault</h2>
<span class="badge" id="user-badge">Connected</span>
</div>
<div id="tab-discover" class="tab-content active">
    <h3 style="margin-top:0; color:var(--accent-color); font-weight: 800; font-size: 22px;">📰 Latest Updates</h3>
    <p style="color:var(--muted-color); font-size:13px; margin-bottom:20px;">News, guides, and updates posted by the Admin.</p>
    <div id="postsContainer">
        <p style="text-align:center; color:var(--muted-color);">Loading posts...</p>
    </div>
</div>
<div id="tab-vault" class="tab-content">
    <section class="welcome-strip" style="background:linear-gradient(112deg,#282044 0%,#32265d 52%,#171a29 100%); padding:20px; border-radius:16px; margin-bottom:16px; border:1px solid rgba(190,173,255,.18);">
        <h2 style="margin:0 0 6px; font-size:22px;">Find your next useful download.</h2>
        <p style="margin:0; color:#d1cce2; font-size:12px;">Courses, resources and mini apps — all in one place.</p>
    </section>
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 Search courses, files..." oninput="debounceSearch()">
    </div>
    <div class="filter-bar">
        <div class="chip bouncy-btn active" onclick="filterCategory('All', this)">All</div>
        {% for category in categories %}
        <div class="chip bouncy-btn" onclick='filterCategory({{ category|tojson }}, this)'>{{ category }}</div>
        {% endfor %}
    </div>
    <div class="grid" id="itemsContainer"></div>
</div>
<div id="tab-games" class="tab-content">
    <div class="arcade-subnav" id="arcade-subnav">
        <div class="chip bouncy-btn active" onclick="switchGame('tictactoe', this)">⭕ Tic Tac Toe</div>
        <div class="chip bouncy-btn" onclick="switchGame('whot', this)">🃏 WHOT</div>
        <div class="chip bouncy-btn" onclick="switchGame('sea', this)">🚢 Sea Battle</div>
        <div class="chip bouncy-btn" onclick="switchGame('word', this)">🔤 World Puzzle</div>
        <div class="chip bouncy-btn" onclick="switchGame('water', this)">💧 Water Sort</div>
    </div>
    <div id="game-sea" style="display:none;">
        <div class="whot-head"><div><span class="eyebrow">ARCADE • NAVAL PUZZLE</span><h3 style="margin:0;">🚢 Sea Battle</h3></div><span class="badge" id="sea-turn">Set up fleet</span></div>
        <div class="arcade-panel" id="sea-lobby">
            <p style="text-align:center;color:var(--muted-color);font-size:13px;">Deploy your fleet, then battle the computer or challenge another player online.</p>
            <div style="text-align:center"><button class="arcade-btn primary" onclick="seaStartComputer()">🤖 Play Computer</button><button class="arcade-btn" onclick="seaCreateRoom()">➕ Create private room</button><button class="arcade-btn" onclick="seaJoinPrompt()">🔗 Join room</button><button class="arcade-btn" onclick="seaFindRandom()">🎲 Find opponent</button></div>
            <p id="sea-code" class="sea-status"></p>
        </div>
        <div class="arcade-panel" id="sea-play-panel" style="display:none;">
            <div class="sea-action-row"><button class="arcade-btn" id="sea-cancel" onclick="seaCancel()">✕ Cancel / Leave game</button></div><p id="sea-status" class="sea-status">Choose a ship, then tap a starting cell.</p>
            <div id="sea-setup-tools"><div class="sea-ship-picks" id="sea-ship-picks"></div><p style="text-align:center"><button class="arcade-btn" onclick="seaRotate()">↻ Rotate selected ship</button><button class="arcade-btn" onclick="seaResetPlacement()">Reset fleet</button><button class="arcade-btn primary" id="sea-confirm-fleet" onclick="seaConfirmFleet()">⚓ Confirm fleet / Start</button></p></div>
            <h4 id="sea-board-title" style="text-align:center;margin:8px 0">Your ocean</h4><div class="sea-board" id="sea-board"></div>
            <div id="sea-target-wrap" style="display:none"><h4 style="text-align:center;margin:18px 0 8px">Opponent's ocean — tap to fire</h4><div class="sea-cannon" id="sea-cannon"><span class="sea-turret"></span><span class="sea-barrel"></span></div><div class="sea-board" id="sea-target-board"></div></div>
        </div>
    </div>
    <div id="game-word" style="display:none;">
        <div class="whot-head"><div><span class="eyebrow">ARCADE • WORD CONNECT</span><h3 style="margin:0;">🔤 World Puzzle</h3></div><span class="badge" id="word-level">Level 1</span></div>
        <div class="word-stage"><p class="word-instructions">Swipe across the letters to form words. Each correct word fills the crossword.</p><div class="word-crossword" id="word-crossword"></div><div class="word-current" id="word-current">Swipe letters to make a word</div><div class="word-wheel" id="word-wheel"></div><div class="word-found-list" id="word-found-list"></div><div class="word-controls"><button class="arcade-btn" onclick="wordShuffle()">🔀 Shuffle</button><button class="arcade-btn" onclick="wordClear()">⌫ Clear</button><button class="arcade-btn primary" id="word-hint-ad" onclick="wordWatchHint()">💡 Get a hint · Watch ad</button><button class="arcade-btn primary" onclick="wordNext()">Next level →</button></div><p class="sea-status" id="word-status"></p></div>
    </div>
    <div id="game-water" style="display:none;">
        <div class="whot-head"><div><span class="eyebrow">ARCADE • SORTING PUZZLE</span><h3 style="margin:0;">💧 Water Sort</h3></div><span class="badge" id="water-level">Level 1</span></div>
        <div class="arcade-panel"><p style="text-align:center;color:var(--muted-color);font-size:13px">Sort each colour into its own tube. Tap a tube to pour into another.</p><div class="water-row" id="water-board" aria-label="Water sorting tubes"></div><div class="water-effects" id="water-effects" aria-hidden="true"></div><div class="water-controls"><button class="arcade-btn" onclick="waterUndo()">↶ Undo</button><button class="arcade-btn" onclick="waterNew()">🔄 Restart</button><button class="arcade-btn primary" onclick="waterNext()">Next level →</button></div><p class="sea-status" id="water-status"></p></div>
    </div>
    <div class="arcade-result" id="arcade-result" role="dialog" aria-modal="true"><div class="arcade-result-card"><div id="arcade-result-icon" style="font-size:48px">🏆</div><h3 id="arcade-result-title">You won!</h3><p id="arcade-result-text">Well played.</p><button class="arcade-btn primary" onclick="arcadeResultClose()">Continue</button></div></div>
    <div id="game-tictactoe">
        <h4 style="text-align:center; margin: 0 0 10px;" id="game-status">Player X's Turn</h4>
        <div class="game-board" id="board">
            <div class="cell bouncy-btn" onclick="cellClicked(0)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(1)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(2)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(3)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(4)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(5)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(6)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(7)"></div>
            <div class="cell bouncy-btn" onclick="cellClicked(8)"></div>
        </div>
        <button class="btn bouncy-btn" style="background:var(--card-bg); max-width: 180px; margin: 0 auto; display:block; color:var(--text-color);" onclick="resetGame()">🔄 Reset</button>
    </div>
    <div id="game-whot" style="display:none;">
        <div class="whot-head"><div><span class="eyebrow">ARCADE • NIGERIAN CARD GAME</span><h3 style="margin:0;">🃏 WHOT!</h3></div><span class="badge" id="whot-turn">Your turn</span></div>
        <div class="whot-modebar" id="whot-modebar">
            <button id="btn-mode-computer" class="active" onclick="whotSelectMode('computer')">🤖 Computer</button>
            <button id="btn-mode-online" onclick="whotSelectMode('online')">👥 Friend / Random</button>
        </div>
        <div id="whot-lobby" style="display:none; text-align:center; padding: 20px; background: var(--card-bg); border-radius: 16px; margin-bottom: 16px;">
            <h3 style="margin-top:0; color:var(--accent-color);">Play with Friends</h3>
            <p style="font-size:12px; color:var(--muted-color); margin-bottom:16px;">Create a room, or join with a code.</p>
            <button class="whot-mini-btn" style="width:100%; margin-bottom:8px; padding:12px;" onclick="whotCreateRoom()">➕ Create Private Room</button>
            <button class="whot-mini-btn" style="width:100%; margin-bottom:8px; padding:12px;" onclick="whotJoinRoomPrompt()">🔗 Join with Room Code</button>
            <button class="whot-mini-btn" style="width:100%; margin-bottom:8px; padding:12px;" onclick="whotFindRandom()">🎲 Find Random Opponent</button>
            <hr style="border-color:#333; margin:16px 0;">
            <button class="btn btn-danger" style="width:100%;" onclick="whotSelectMode('computer')">❌ Cancel & Play Computer</button>
        </div>
        <p id="whot-room-code" class="whot-status"></p>
        <p id="whot-status" class="whot-status" aria-live="polite">Choose a game mode to begin.</p>
        <div class="whot-table">
            <div class="whot-opponent"><span id="whot-opponent-name">🤖 Computer</span><strong id="whot-cpu-count">5 cards</strong></div>
            <div id="whot-opponent-fan" class="whot-fan" aria-label="Opponent's face-down cards"></div>
            <div class="whot-pile-wrap"><div><small>TOP CARD</small><div id="whot-top" class="whot-card top-card">1<br><small>CIRCLE</small></div></div><div><small>DRAW PILE</small><button type="button" id="whot-draw" class="whot-card draw-card" onclick="whotDraw()">WHOT</button></div></div>
            <div id="whot-actor" class="whot-actor" aria-hidden="true"><span class="arm"></span><span class="palm"></span></div>
            <div class="whot-opponent"><span>🙋 Your hand</span><strong id="whot-player-count">0 cards</strong></div>
            <div id="whot-hand" class="whot-hand"></div>
        </div>
        <div class="whot-actions" id="whot-actions-computer"><button class="btn bouncy-btn" type="button" onclick="whotNewGame()">🔄 New computer game</button></div>
        <p class="whot-rules">Match by number or shape. Specials: 1 Hold On, 2 Pick Two, 5 Pick Three, 8 Suspension, 14 General Market, 20 = WHOT (wild, pick shape).</p>
    </div>
</div>
<div id="tab-admin" class="tab-content">
    <h3 style="margin-top:0; color:var(--accent-color);">🛠️ Live Dashboard & Admin</h3>
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-num" id="statUsers">--</div><div class="stat-label">Total Users</div></div>
        <div class="stat-card"><div class="stat-num" id="statDownloads">--</div><div class="stat-label">Vault Items</div></div>
    </div>
    <h4>📰 Publish New Post</h4>
    <div style="background:var(--card-bg);padding:12px;border-radius:10px;margin-bottom:20px;">
        <p style="font-size:11px;color:var(--muted-color);margin-top:0;">This will instantly appear on the Discover tab for everyone.</p>
        <form action="/admin/add-post" method="POST">
            <input type="hidden" name="secret" value="{{ secret }}">
            <label>Post Title</label>
            <input type="text" name="title" placeholder="e.g. eFootball Update" required>
            <label>Post Message (Just type normally)</label>
            <textarea name="content" id="postContent" rows="6" placeholder="Write your news here. You can press Enter to start a new line." required></textarea>
            <div style="display:flex; gap:8px; margin-bottom:10px;">
                <input type="file" accept="image/*" onchange="insertImageInPost(this)" style="display:none;" id="inPostImageInput">
                <button type="button" class="btn bouncy-btn" style="background:#292b33; color:#fff; font-size:12px; min-height:38px;" onclick="document.getElementById('inPostImageInput').click()">🖼️ Insert Image in Post</button>
                <span id="inPostImageStatus" style="color:var(--green-color); font-size:12px; align-self:center;"></span>
            </div>
            <label>Add a Link (Optional)</label>
            <input type="text" name="link_text" placeholder="e.g. Watch Video">
            <input type="url" name="link_url" placeholder="https://example.com">
            <label>Cover Image (Optional)</label>
            <input type="file" accept="image/*" onchange="encodePostImage(this)">
            <input type="hidden" name="image" id="postImageBase64">
            <button type="submit" class="btn bouncy-btn" style="margin-top:8px;">🚀 Publish Post</button>
        </form>
    </div>
    <h4>🗑 Manage Posts</h4>
    <div style="background:var(--card-bg);padding:12px;border-radius:10px;margin-bottom:20px;">
        {% for p in posts %}
        <div style="display:flex;flex-direction:column;padding:10px;border-bottom:1px solid rgba(255,255,255,0.05);margin-bottom:8px;">
            <div style="font-size:13px;font-weight:bold;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ p.title }}</div>
            <div style="display:flex; gap:8px;">
                <button class="btn btn-edit" style="flex:1;" onclick="document.getElementById('edit-post-{{ p.id }}').style.display='block'">Edit</button>
                <a href="/admin/delete-post?id={{ p.id }}&secret={{ secret }}" class="btn btn-danger" style="flex:1;" onclick="return confirm('Delete this post?')">Delete</a>
            </div>
            <form id="edit-post-{{ p.id }}" action="/admin/edit-post" method="POST" style="display:none; margin-top:10px; background:#101114; padding:10px; border-radius:8px;">
                <input type="hidden" name="secret" value="{{ secret }}">
                <input type="hidden" name="id" value="{{ p.id }}">
                <label>Title</label><input type="text" name="title" value="{{ p.title }}" required>
                <label>Content</label><textarea name="content" rows="4" required>{{ p.content }}</textarea>
                <label>Link Text</label><input type="text" name="link_text" value="{{ p.link_text or '' }}">
                <label>Link URL</label><input type="url" name="link_url" value="{{ p.link_url or '' }}">
                <button type="submit" class="btn bouncy-btn" style="margin-top:8px; background:var(--accent-color);">Save Changes</button>
            </form>
        </div>
        {% endfor %}
    </div>
    <h4>📁 Manage Categories</h4>
    <div style="background:var(--card-bg);padding:12px;border-radius:10px;margin-bottom:20px;">
        <form action="/admin/category" method="POST" style="display:flex; gap:8px; margin-bottom:16px;">
            <input type="hidden" name="secret" value="{{ secret }}">
            <input type="hidden" name="action" value="add">
            <input type="text" name="name" placeholder="New category name" required style="margin-bottom:0;">
            <button type="submit" class="btn bouncy-btn" style="width:80px; flex:none;">Add</button>
        </form>
        {% for cat in categories %}
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);margin-bottom:8px;">
            <div style="font-size:13px;">{{ cat }}</div>
            <div style="display:flex; gap:6px;">
                <button class="btn btn-edit" style="padding:4px 8px; font-size:10px;" onclick="document.getElementById('edit-cat-{{ loop.index }}').style.display='block'">Rename</button>
                <form action="/admin/category" method="POST" style="display:inline;" onsubmit="return confirm('Delete category? Make sure no items are in it.')">
                    <input type="hidden" name="secret" value="{{ secret }}">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="old_name" value="{{ cat }}">
                    <button type="submit" class="btn btn-danger" style="padding:4px 8px; font-size:10px;">Del</button>
                </form>
            </div>
            <form id="edit-cat-{{ loop.index }}" action="/admin/category" method="POST" style="display:none; margin-top:10px; width:100%; background:#101114; padding:8px; border-radius:8px;">
                <input type="hidden" name="secret" value="{{ secret }}">
                <input type="hidden" name="action" value="rename">
                <input type="hidden" name="old_name" value="{{ cat }}">
                <input type="text" name="name" value="{{ cat }}" required style="margin-bottom:6px;">
                <button type="submit" class="btn bouncy-btn" style="background:var(--accent-color); padding:6px; font-size:11px;">Save Name</button>
            </form>
        </div>
        {% endfor %}
    </div>
    <form action="/admin/add-item" method="POST" style="background: var(--card-bg); padding: 14px; border-radius: 12px; margin-bottom: 20px;">
        <input type="hidden" name="secret" value="{{ secret }}">
        <h4 style="margin-top:0;">Add New Vault Item</h4>
        <label>Item Title</label><input type="text" name="title" placeholder="e.g. Pharmacognosy PDF" required>
        <label>Description</label><textarea name="desc" rows="2" placeholder="Short file description..." required></textarea>
        <label>Upload Image Directly</label><input type="file" id="imageInput" accept="image/*" onchange="encodeImageFileAsURL(this)"><input type="hidden" name="image" id="imageBase64" required>
        <label>File Indicator</label><input type="text" name="meta" value="📄 PDF • 5.0MB">
        <label>Category</label>
        <select name="category">
            {% for category in categories %}<option value="{{ category }}">{{ category }}</option>{% endfor %}
        </select>
        <label>Telegram Bot / File Link</label><input type="text" name="link" placeholder="https://t.me/..." required>
        <label><input type="checkbox" name="pinned" value="true" style="width:auto;"> Pin to top</label>
        <button type="submit" class="btn bouncy-btn">➕ Add New Item</button>
    </form>
    <h4>Existing Items Manager:</h4>
    {% for item in items %}
    <details style="background: var(--card-bg); padding: 12px; border-radius: 10px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.08);">
        <summary style="cursor:pointer; display:flex; justify-content:space-between; align-items:center; gap:10px;">
            <span><strong style="font-size:14px;">{{ item.title }}</strong><br><small style="color:var(--muted-color);">{{ item.category }}</small></span>
            <span style="color:var(--accent-color);">Edit ▾</span>
        </summary>
        <form action="/admin/edit-item" method="POST" style="margin-top:14px;">
            <input type="hidden" name="secret" value="{{ secret }}">
            <input type="hidden" name="id" value="{{ item.id }}">
            <label>Title</label><input type="text" name="title" value="{{ item.title }}" required>
            <label>Description</label><textarea name="desc" rows="2" required>{{ item.desc }}</textarea>
            <label>Link</label><input type="text" name="link" value="{{ item.link }}" required>
            <button type="submit" class="btn bouncy-btn">Save Changes</button>
        </form>
        <a href="/admin/delete-item?id={{ item.id }}&secret={{ secret }}" class="btn btn-danger" style="display:inline-block;margin-top:10px;" onclick="return confirm('Delete item?')">Delete Item</a>
    </details>
    {% endfor %}
</div>
<nav class="nav-bar">
    <button class="nav-item bouncy-btn active" onclick="switchTab('discover', this)">📰 <span>News</span></button>
    <button class="nav-item bouncy-btn" onclick="switchTab('vault', this)">📁 <span>Vault</span></button>
    <button class="nav-item bouncy-btn" onclick="switchTab('games', this)">🎮 <span>Arcade</span></button>
    <button class="nav-item bouncy-btn" id="admin-nav-btn" style="display:none;" onclick="switchTab('admin', this)">⚙️ <span>Admin</span></button>
</nav>
<div id="whot-shape-picker" class="whot-shape-picker">
    <div class="whot-shape-box">
        <h3>🃏 WHOT! Choose a shape</h3>
        <div class="whot-shape-grid">
            <button class="whot-shape-btn" onclick="whotShapeChosen('CIRCLE')">● CIRCLE</button>
            <button class="whot-shape-btn" onclick="whotShapeChosen('TRIANGLE')">▲ TRIANGLE</button>
            <button class="whot-shape-btn" onclick="whotShapeChosen('CROSS')">✚ CROSS</button>
            <button class="whot-shape-btn" onclick="whotShapeChosen('SQUARE')">■ SQUARE</button>
            <button class="whot-shape-btn" onclick="whotShapeChosen('STAR')">★ STAR</button>
            <button class="whot-shape-btn" onclick="whotShapeCancelled()" style="background:#3a1f1f;color:#ffb4b4;">Cancel</button>
        </div>
    </div>
</div>
<script>
    const tg = window.Telegram.WebApp;
    tg.ready(); tg.expand();
    const ADMIN_ID = 6248570946;
    const userId = (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) || null;
    if (userId == ADMIN_ID) {
        document.getElementById('admin-nav-btn').style.display = 'flex';
    }
    function arcadeResultShow(won,title,message){const el=document.getElementById('arcade-result');if(!el)return;document.getElementById('arcade-result-icon').textContent=won?'🏆':'💥';document.getElementById('arcade-result-title').textContent=title;document.getElementById('arcade-result-text').textContent=message;el.classList.add('show');if(tg.HapticFeedback)triggerHaptic('notification',won?'success':'error');}
    function arcadeResultClose(){document.getElementById('arcade-result').classList.remove('show')}
    function triggerHaptic(type = 'impact', style = 'light') {
        if (tg.HapticFeedback) {
            if (type === 'impact') tg.HapticFeedback.impactOccurred(style);
            if (type === 'notification') tg.HapticFeedback.notificationOccurred(style);
        }
    }
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playSound(type) {
        if (!audioCtx) return;
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        const now = audioCtx.currentTime;
        if (type === 'deal') {
            osc.type = 'triangle'; osc.frequency.setValueAtTime(320, now);
            osc.frequency.exponentialRampToValueAtTime(140, now + 0.12);
            gain.gain.setValueAtTime(0.25, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.12);
            osc.start(now); osc.stop(now + 0.12);
        } else if (type === 'win') {
            osc.type = 'sine'; osc.frequency.setValueAtTime(523.25, now);
            osc.frequency.setValueAtTime(659.25, now + 0.1); osc.frequency.setValueAtTime(783.99, now + 0.2);
            gain.gain.setValueAtTime(0.3, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.35);
            osc.start(now); osc.stop(now + 0.35);
        } else if (type === 'click') {
            osc.type = 'square'; osc.frequency.setValueAtTime(400, now);
            gain.gain.setValueAtTime(0.1, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.05);
            osc.start(now); osc.stop(now + 0.05);
        }
    }
    function switchTab(tabName, el) {
        playSound('click'); triggerHaptic('impact', 'light');
        document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.getElementById('tab-' + tabName).classList.add('active');
        el.classList.add('active');
    }
    async function loadPosts() {
        try {
            const res = await fetch('/api/posts');
            const data = await res.json();
            const box = document.getElementById('postsContainer');
            if (!data.ok || !data.posts || data.posts.length === 0) {
                box.innerHTML = '<p style="text-align:center; color:var(--muted-color);">No posts yet. The Admin will publish news soon!</p>';
                return;
            }
            box.innerHTML = '';
            data.posts.forEach(p => {
                const needsTruncation = p.content.length > 250 || p.link_url;
                const btnId = `read-more-${p.id}`;
                const card = document.createElement('div');
                card.className = 'post-card';
                card.id = `post-card-${p.id}`;
                card.innerHTML = `
                    ${p.image ? `<img src="${p.image}" class="post-img" loading="lazy">` : ''}
                    <div class="post-body">
                        <div class="post-title">${p.title}</div>
                        <div class="post-content ${needsTruncation ? 'collapsed' : ''}" id="post-content-${p.id}">${p.content}</div>
                        ${needsTruncation ? `<button class="read-more-btn" id="${btnId}" onclick="toggleReadMore('${p.id}')">Read More ▾</button>` : ''}
                        ${p.link_url ? `<a href="${p.link_url}" target="_blank" class="btn bouncy-btn post-link-btn" style="text-decoration:none;">${p.link_text || 'Click Here'} ↗</a>` : ''}
                    </div>
                `;
                box.appendChild(card);
            });
        } catch(e) { console.error(e); }
    }
    function toggleReadMore(postId) {
        playSound('click');
        const content = document.getElementById(`post-content-${postId}`);
        const card = document.getElementById(`post-card-${postId}`);
        const btn = document.getElementById(`read-more-${postId}`);
        if (content.classList.contains('collapsed')) {
            content.classList.remove('collapsed');
            card.classList.add('expanded');
            btn.innerText = 'Show Less ▴';
        } else {
            content.classList.add('collapsed');
            card.classList.remove('expanded');
            btn.innerText = 'Read More ▾';
        }
    }
    loadPosts();
    const rawItems = {{ items | tojson }};
    let sampleItems = rawItems.sort((a, b) => (b.pinned === true) - (a.pinned === true));
    document.getElementById('statDownloads').innerText = sampleItems.length;
    document.getElementById('statUsers').innerText = "~";
    function renderItems(items) {
        const container = document.getElementById('itemsContainer');
        container.innerHTML = '';
        if (items.length === 0) {
            container.innerHTML = '<p style="text-align:center; color:var(--muted-color); grid-column: 1/-1;">No items found.</p>';
            return;
        }
        items.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = `card bouncy-btn ${item.pinned ? 'pinned' : ''}`;
            card.style.animationDelay = `${idx * 0.08}s`;
            card.innerHTML = `
                ${item.pinned ? '<div class="pinned-badge">📌 PINNED</div>' : ''}
                <img src="${item.image}" alt="Thumbnail" loading="lazy">
                <div class="card-body">
                    <div class="card-title">${item.title}</div>
                    <div class="card-meta"><span>${item.meta || '📄 File'}</span></div>
                    <div class="card-desc">${item.desc}</div>
                    <div class="action-row">
                        <a href="${item.link}" target="_blank" class="btn bouncy-btn" onclick="playSound('click'); triggerHaptic('impact','medium')">📥 Download</a>
                        <button class="btn btn-copy bouncy-btn" onclick="playSound('click'); copyLink('${item.link}')">📋</button>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    }
    function copyLink(link) {
        triggerHaptic('notification', 'success');
        navigator.clipboard.writeText(link);
        tg.showAlert('Link copied to clipboard!');
    }
    let timer;
    function debounceSearch() {
        clearTimeout(timer);
        timer = setTimeout(() => {
            const q = document.getElementById('searchInput').value.toLowerCase();
            renderItems(sampleItems.filter(i => i.title.toLowerCase().includes(q) || i.desc.toLowerCase().includes(q)));
        }, 300);
    }
    function filterCategory(cat, el) {
        playSound('click'); triggerHaptic('impact', 'light');
        document.querySelectorAll('#tab-vault .filter-bar .chip').forEach(c => c.classList.remove('active'));
        el.classList.add('active');
        renderItems(cat === 'All' ? sampleItems : sampleItems.filter(i => i.category === cat));
    }
    function encodeImageFileAsURL(element) {
        const file = element.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = function() { document.getElementById('imageBase64').value = reader.result; }
            reader.readAsDataURL(file);
        }
    }
    function encodePostImage(element) {
        const file = element.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = function() { document.getElementById('postImageBase64').value = reader.result; }
            reader.readAsDataURL(file);
        }
    }
    function insertImageInPost(element) {
        const file = element.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = function() {
                const textarea = document.getElementById('postContent');
                const imgTag = `\n<img src="${reader.result}" style="max-width:100%; border-radius:8px; margin:10px 0;">\n`;
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                const text = textarea.value;
                textarea.value = text.substring(0, start) + imgTag + text.substring(end);
                element.value = '';
                document.getElementById('inPostImageStatus').innerText = '✅ Image added!';
                setTimeout(() => { document.getElementById('inPostImageStatus').innerText = ''; }, 3000);
            }
            reader.readAsDataURL(file);
        }
    }
    function switchGame(gameName, el) {
        playSound('click'); triggerHaptic('impact', 'light');
        document.querySelectorAll('#tab-games .arcade-subnav .chip').forEach(c => c.classList.remove('active'));
        el.classList.add('active');
        ['tictactoe','whot','sea','word','water'].forEach(name => { const el=document.getElementById('game-'+name); if(el) el.style.display = gameName === name ? 'block' : 'none'; });
        if (gameName === 'whot' && !whotStarted && !whotOnlineGame) whotNewGame();
        if (gameName === 'sea') seaInit();
        if (gameName === 'word') wordInit();
        if (gameName === 'water') waterInit();
    }
    const SEA_W=9, SEA_H=7, SEA_LENGTHS=[5,4,3,3,2];
    let seaCode=null,seaPoll=null,seaGame=null,seaAxis='H',seaSelected=0,seaPlaced=[],seaBusy=false,seaMode='online';
    let seaCpuShips=[],seaCpuShots=[],seaCpuHits=[],seaCpuMisses=[],seaPlayerHits=[],seaPlayerMisses=[],seaCpuTurnTimer=null,seaLastResultKey='';
    function seaInit(){if(!document.getElementById('sea-ship-picks').children.length)seaResetPlacement()}
    async function seaApi(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData||''},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'Sea Battle service error');return d}
    function seaStop(){if(seaPoll){clearInterval(seaPoll);seaPoll=null}if(seaCpuTurnTimer){clearTimeout(seaCpuTurnTimer);seaCpuTurnTimer=null}}
    function seaMessage(t){document.getElementById('sea-status').textContent=t}
    function seaResetPlacement(){seaPlaced=[];seaSelected=0;seaAxis='H';seaRenderSetup()}
    function seaRotate(){if(seaSelected>=SEA_LENGTHS.length){seaMessage('Select a ship first.');return}const current=seaPlaced[seaSelected];if(current&&current.cells.length){const first=current.cells[0],vertical=current.cells[0][1]===current.cells[1][1];seaAxis=vertical?'H':'V';}else seaAxis=seaAxis==='H'?'V':'H';playSound('click');seaRenderSetup();seaMessage('Selected ship direction: '+(seaAxis==='H'?'horizontal':'vertical')+'. Tap the board to reposition it.')}
    function seaRenderSetup(){const p=document.getElementById('sea-ship-picks');p.innerHTML='';SEA_LENGTHS.forEach((n,i)=>{const b=document.createElement('button');b.className='arcade-btn'+(i===seaSelected?' primary':'');b.textContent=(seaPlaced[i]?'✓ ':'')+['Carrier','Battleship','Cruiser','Submarine','Patrol boat'][i]+' · '+n;b.disabled=false;b.onclick=()=>{seaSelected=i;const sh=seaPlaced[i];if(sh&&sh.cells.length>1)seaAxis=sh.cells[0][1]===sh.cells[1][1]?'V':'H';seaRenderSetup();seaMessage('Editing '+['Carrier','Battleship','Cruiser','Submarine','Patrol boat'][i]+'. Rotate it or tap a new starting cell.')};p.appendChild(b)});const placed=seaPlaced.filter(Boolean).length;document.getElementById('sea-confirm-fleet').disabled=placed!==SEA_LENGTHS.length;document.getElementById('sea-confirm-fleet').textContent=placed===SEA_LENGTHS.length?'⚓ Confirm fleet / Start':'⚓ Place all '+SEA_LENGTHS.length+' ships';seaDrawOwnBoard(null)}
    function seaCoords(r,c,len,axis){const a=[];for(let k=0;k<len;k++)a.push([r+(axis==='V'?k:0),c+(axis==='H'?k:0)]);return a}
    function seaCellShipMarkup(ship,idx,r,c){const pos=ship.findIndex(([y,x])=>y===r&&x===c);const vertical=ship.length>1&&ship[0][1]===ship[1][1];return `<span class="ship-piece ${vertical?'vertical':''} ${pos===0?'bow':pos===ship.length-1?'stern':'mid'}"></span>`}
    function seaShipSvg(length,vertical,index){const w=vertical?100:length*100,h=vertical?length*100:100;let details='';for(let i=0;i<length;i++){const x=vertical?50:(i+.5)*100,y=vertical?(i+.5)*100:50;details+=`<circle cx="${x}" cy="${y}" r="5" fill="#b9d4df" stroke="#243a47" stroke-width="2"/>`;if(i>0&&i<length-1)details+=`<path d="M ${vertical?28:x-22} ${vertical?y-22:28} l ${vertical?44:0} ${vertical?0:44}" stroke="#d7e2e6" stroke-width="3" opacity=".75"/>`;}let hull,deck;if(vertical){hull=`M50 3 Q78 12 80 45 L80 ${h-45} Q75 ${h-8} 50 ${h-2} Q25 ${h-8} 20 ${h-45} L20 45 Q22 12 50 3Z`;deck=`<rect x="36" y="${h*.28}" width="28" height="${h*.42}" rx="10" fill="url(#deck${index})" stroke="#d8e4e8" stroke-width="3"/><rect x="42" y="${h*.40}" width="16" height="${h*.13}" rx="4" fill="#dce8ec"/>`;}else{hull=`M3 50 Q12 20 45 20 L${w-45} 20 Q${w-12} 20 ${w-3} 50 Q${w-12} 80 ${w-45} 80 L45 80 Q12 80 3 50Z`;deck=`<rect x="${w*.28}" y="34" width="${w*.42}" height="32" rx="10" fill="url(#deck${index})" stroke="#d8e4e8" stroke-width="3"/><rect x="${w*.40}" y="40" width="${w*.13}" height="20" rx="4" fill="#dce8ec"/>`;}return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="hull${index}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#d8e2e5"/><stop offset=".32" stop-color="#71858f"/><stop offset=".72" stop-color="#344c59"/><stop offset="1" stop-color="#152c39"/></linearGradient><linearGradient id="deck${index}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#c5d1d4"/><stop offset=".5" stop-color="#647984"/><stop offset="1" stop-color="#283e49"/></linearGradient></defs><path d="${hull}" fill="url(#hull${index})" stroke="#e3edf0" stroke-width="3"/><path d="${vertical?`M50 12 L50 ${h-12}`:`M12 50 L${w-12} 50`}" stroke="#eff7f8" stroke-width="2" opacity=".65"/>${deck}${details}<path d="${vertical?`M35 ${h*.18} L65 ${h*.18}`:`M${w*.18} 35 L${w*.82} 35`}" stroke="#f2f8fa" stroke-width="3" opacity=".7"/></svg>`}
    function seaDrawShipArt(board,ships){board.querySelectorAll('.sea-ship-art').forEach(x=>x.remove());if(!ships||!ships.length)return;const cells=board.querySelectorAll('.sea-cell'),br=board.getBoundingClientRect();ships.forEach((ship,i)=>{const first=ship[0],last=ship[ship.length-1],a=cells[first[0]*SEA_W+first[1]],z=cells[last[0]*SEA_W+last[1]];if(!a||!z)return;const ar=a.getBoundingClientRect(),zr=z.getBoundingClientRect(),vertical=first[1]===last[1],art=document.createElement('div');art.className='sea-ship-art'+(board.id==='sea-target-board'?' sunk':'');art.style.left=(ar.left-br.left)+'px';art.style.top=(ar.top-br.top)+'px';art.style.width=(vertical?ar.width:zr.right-ar.left)+'px';art.style.height=(vertical?zr.bottom-ar.top:ar.height)+'px';art.innerHTML=seaShipSvg(ship.length,vertical,i+1);board.appendChild(art)})}
    function seaDrawOwnBoard(preview){const b=document.getElementById('sea-board');b.innerHTML='';for(let r=0;r<SEA_H;r++)for(let c=0;c<SEA_W;c++){const cell=document.createElement('button');cell.className='sea-cell own';const found=seaPlaced.find((ship)=>ship&&ship.cells.some(x=>x[0]===r&&x[1]===c));if(found){cell.classList.add('ship');cell.innerHTML=seaCellShipMarkup(found.cells,0,r,c)}if(preview&&preview.some(x=>x[0]===r&&x[1]===c)){cell.classList.add('target');cell.textContent='＋'}cell.onclick=()=>seaPlaceAt(r,c);b.appendChild(cell)}seaDrawShipArt(b,seaPlaced.map(x=>x.cells))}
    function seaShowPlay(){document.getElementById('sea-play-panel').style.display='block';document.getElementById('sea-lobby').style.display='none'}
    function seaShowLobby(){document.getElementById('sea-play-panel').style.display='none';document.getElementById('sea-lobby').style.display='block';document.getElementById('sea-code').textContent=''}
    async function seaCreateRoom(){try{seaStop();seaLastIncomingCount=0;seaLastIncomingHitCount=0;seaLastResultKey='';seaMode='online';const d=await seaApi('/api/sea/create',{});seaCode=d.code;seaShowPlay();document.getElementById('sea-code').textContent='Room code: '+d.code+' — share with your friend';if(tg.openTelegramLink)tg.openTelegramLink(d.share_url);else window.open(d.share_url,'_blank');seaResetPlacement();seaMessage('Room created. Arrange your fleet while your friend joins.');seaStartPoll()}catch(e){tg.showAlert(e.message)}}
    async function seaJoinPrompt(){const code=prompt('Enter your Sea Battle room code');if(!code)return;try{seaStop();seaLastIncomingCount=0;seaLastIncomingHitCount=0;seaLastResultKey='';seaMode='online';const d=await seaApi('/api/sea/join',{code});seaCode=code.trim().toUpperCase();seaShowPlay();seaRenderOnline(d.game);seaStartPoll()}catch(e){tg.showAlert(e.message)}}
    async function seaFindRandom(){try{seaStop();seaLastIncomingCount=0;seaLastIncomingHitCount=0;seaLastResultKey='';seaMode='online';const d=await seaApi('/api/sea/random',{});seaCode=d.code;seaShowPlay();if(d.game)seaRenderOnline(d.game);else{seaResetPlacement();seaMessage(d.message)}seaStartPoll()}catch(e){tg.showAlert(e.message)}}
    async function seaCancel(){seaStop();seaLastIncomingCount=0;seaLastIncomingHitCount=0;if(seaMode==='online'&&seaCode){try{await seaApi('/api/sea/cancel',{code:seaCode})}catch(e){}}seaCode=null;seaGame=null;seaBusy=false;seaPlaced=[];seaMode='online';seaShowLobby();seaMessage('You left the Sea Battle game.');document.getElementById('sea-turn').textContent='Ready';}
    function seaPlaceAt(r,c){if(seaBusy||seaSelected>=SEA_LENGTHS.length)return;if(seaMode==='online'&&!seaCode)return;const len=SEA_LENGTHS[seaSelected],cells=seaCoords(r,c,len,seaAxis),others=seaPlaced.filter((sh,i)=>i!==seaSelected&&sh).flatMap(sh=>sh.cells);if(cells.some(([y,x])=>y<0||y>=SEA_H||x<0||x>=SEA_W)||cells.some(([y,x])=>others.some(([yy,xx])=>yy===y&&xx===x))){seaMessage('That ship will not fit there. Rotate it or choose another starting cell.');return}seaPlaced[seaSelected]={cells};playSound('deal');const next=SEA_LENGTHS.findIndex((_,i)=>!seaPlaced[i]);seaSelected=next<0?0:next;seaRenderSetup();seaMessage(next<0?'All ships placed. You can still select any ship to reposition or rotate it, then confirm your fleet.':'Ship placed. You can return to any ship to change its direction or position.')}
    function seaConfirmFleet(){if(seaPlaced.filter(Boolean).length!==SEA_LENGTHS.length){seaMessage('Place all five ships first.');return}if(seaMode==='computer')seaStartComputerBattle();else seaSubmitFleet()}
    async function seaSubmitFleet(){try{seaBusy=true;const d=await seaApi('/api/sea/place',{code:seaCode,ships:seaPlaced});seaRenderOnline(d.game)}catch(e){seaMessage(e.message)}finally{seaBusy=false}}
    function seaStartPoll(){seaStop();seaPoll=setInterval(async()=>{if(!seaCode||seaMode!=='online')return;try{const d=await seaApi('/api/sea/state?code='+encodeURIComponent(seaCode));seaRenderOnline(d.game)}catch(e){seaMessage(e.message)}},1300)}
    function seaRenderOnline(g){const incoming=(g.my_hits||[]).length+(g.my_misses||[]).length,hitCount=(g.my_hits||[]).length;if(incoming>seaLastIncomingCount){if(hitCount>seaLastIncomingHitCount)seaExplosionSound();else seaSplashSound();}seaLastIncomingCount=incoming;seaLastIncomingHitCount=hitCount;seaGame=g;seaShowPlay();document.getElementById('sea-turn').textContent=g.status==='finished'?'Finished':g.status==='waiting'?'Waiting':g.my_turn?'Your turn':'Opponent turn';document.getElementById('sea-board-title').textContent='Your fleet';document.getElementById('sea-setup-tools').style.display=g.placed?'none':'block';document.getElementById('sea-target-wrap').style.display=g.status==='playing'||g.status==='finished'?'block':'none';if(g.placed){seaPlaced=g.my_ships.map(c=>({cells:c}));seaDrawOnlineBoard('sea-board',g.my_ships,g.my_hits,g.my_misses,false)}else seaDrawOwnBoard(null);if(g.status==='playing'||g.status==='finished'){seaDrawOnlineBoard('sea-target-board',[],g.shots_hit,g.shots_miss,true);if(g.opponent_ships_revealed&&g.opponent_ships_revealed.length)seaDrawShipArt(document.getElementById('sea-target-board'),g.opponent_ships_revealed);else if(g.sunk_opponent_ships&&g.sunk_opponent_ships.length)seaDrawShipArt(document.getElementById('sea-target-board'),g.sunk_opponent_ships)}if(g.status==='finished'){seaStop();const won=g.winner===String(userId);seaMessage(won?'🎉 Victory! Enemy fleet destroyed.':'Your fleet has been defeated.');const key=seaCode+':'+g.winner;if(seaLastResultKey!==key){seaLastResultKey=key;playSound('win');arcadeResultShow(won,won?'You won!':'You lost',won?'Enemy fleet destroyed.':'Your fleet was destroyed.')}}else if(g.status==='cancelled'){seaStop();seaMessage('Your opponent left the match.');playSound('click');arcadeResultShow(false,'Match ended','Your opponent left the game.')}else seaMessage(g.status==='waiting'?'Waiting for an opponent to join…':g.status==='placing'?'Place all five ships. The battle begins when both fleets are ready.':g.my_turn?'Your turn — fire at the enemy ocean.':(g.message||'Opponent is aiming…'))}
    function seaDrawOnlineBoard(id,ships,hits,misses,target){const b=document.getElementById(id);b.innerHTML='';for(let r=0;r<SEA_H;r++)for(let c=0;c<SEA_W;c++){const key=r+','+c,cell=document.createElement('button');cell.className='sea-cell'+(target?'':' own');const isHit=hits.includes(key),isMiss=misses.includes(key),ship=ships.find(s=>s.some(([y,x])=>y===r&&x===c));if(isHit){cell.classList.add('hit');cell.textContent='✹'}else if(isMiss){cell.classList.add('miss');cell.textContent=''}else if(ship&&!target){cell.classList.add('ship');cell.innerHTML=seaCellShipMarkup(ship,0,r,c)}cell.disabled=!target||!seaGame||!seaGame.my_turn||seaGame.status!=='playing'||isHit||isMiss;cell.onclick=()=>seaFire(r,c);b.appendChild(cell)}if(!target){seaDrawShipArt(b,ships);hits.forEach(k=>{const [r,c]=k.split(',').map(Number),cell=b.querySelectorAll('.sea-cell')[r*SEA_W+c];if(cell){const mark=document.createElement('span');mark.className='sea-impact-mark';mark.textContent='✹';cell.appendChild(mark)}})}}
    function seaAnimateShell(r,c){const board=document.getElementById('sea-target-board'),cannon=document.getElementById('sea-cannon'),cells=board.querySelectorAll('.sea-cell'),target=cells[r*SEA_W+c];if(!target)return;const br=board.getBoundingClientRect(),cr=cannon.getBoundingClientRect(),tr=target.getBoundingClientRect(),shell=document.createElement('span');shell.className='sea-shell';shell.style.left=(cr.left+cr.width*.72)+'px';shell.style.top=(cr.top+cr.height*.25)+'px';shell.style.setProperty('--dx',(tr.left+tr.width/2-(cr.left+cr.width*.72))+'px');shell.style.setProperty('--dy',(tr.top+tr.height/2-(cr.top+cr.height*.25))+'px');cannon.classList.remove('recoil');void cannon.offsetWidth;cannon.classList.add('recoil');document.body.appendChild(shell);setTimeout(()=>shell.remove(),520)}
    async function seaFire(r,c){if(!seaGame||!seaGame.my_turn||seaGame.status!=='playing')return;playSound('click');seaCannonSound();seaAnimateShell(r,c);const board=document.getElementById('sea-target-board');board.classList.add('sea-fire-flash');setTimeout(()=>board.classList.remove('sea-fire-flash'),450);try{const d=await seaApi('/api/sea/fire',{code:seaCode,row:r,col:c});if(d.game.last_shot==='hit')seaExplosionSound();else seaSplashSound();seaRenderOnline(d.game)}catch(e){seaMessage(e.message)}}
    async function seaJoinInvite(code){try{seaLastIncomingCount=0;seaLastIncomingHitCount=0;seaLastResultKey='';seaMode='online';const d=await seaApi('/api/sea/join',{code});seaCode=code.toUpperCase();seaShowPlay();seaRenderOnline(d.game);seaStartPoll()}catch(e){tg.showAlert(e.message)}}
    function seaRandomFleet(){const fleet=[];for(const len of SEA_LENGTHS){let placed=false,tries=0;while(!placed&&tries++<500){const axis=Math.random()<.5?'H':'V',r=Math.floor(Math.random()*SEA_H),c=Math.floor(Math.random()*SEA_W),cells=seaCoords(r,c,len,axis);if(cells.every(([y,x])=>y>=0&&y<SEA_H&&x>=0&&x<SEA_W)&&!cells.some(([y,x])=>fleet.some(sh=>sh.cells.some(([yy,xx])=>yy===y&&xx===x)))){fleet.push({cells});placed=true}}if(!placed)return null}return fleet}
    function seaStartComputer(){seaStop();seaLastIncomingCount=0;seaLastIncomingHitCount=0;seaLastResultKey='';seaCode=null;seaGame=null;seaMode='computer';seaPlayerHits=[];seaPlayerMisses=[];seaCpuShots=[];seaCpuHits=[];seaCpuMisses=[];seaCpuShips=seaRandomFleet();seaShowPlay();seaResetPlacement();document.getElementById('sea-turn').textContent='Deploy fleet';document.getElementById('sea-setup-tools').style.display='block';document.getElementById('sea-target-wrap').style.display='none';seaMessage('Arrange your five ships. The computer has deployed its fleet.');}
    function seaStartComputerBattle(){seaBusy=false;document.getElementById('sea-setup-tools').style.display='none';document.getElementById('sea-target-wrap').style.display='block';document.getElementById('sea-board-title').textContent='Your fleet';document.getElementById('sea-turn').textContent='Your turn';seaDrawLocalBoards();seaMessage('Battle stations! Fire at the computer fleet.');}
    function seaDrawLocalBoards(){const own=document.getElementById('sea-board'),target=document.getElementById('sea-target-board');own.innerHTML='';target.innerHTML='';for(let r=0;r<SEA_H;r++)for(let c=0;c<SEA_W;c++){const k=r+','+c,cell=document.createElement('button');cell.className='sea-cell own';const ship=seaPlaced.find(x=>x&&x.cells.some(([y,x])=>y===r&&x===c));if(ship){cell.classList.add('ship');cell.innerHTML=seaCellShipMarkup(ship.cells,0,r,c)}if(seaCpuHits.includes(k)){cell.classList.add('hit');cell.textContent='✹'}else if(seaCpuMisses.includes(k))cell.classList.add('miss');cell.disabled=true;own.appendChild(cell);const t=document.createElement('button');t.className='sea-cell';if(seaPlayerHits.includes(k)){t.classList.add('hit');t.textContent='✹'}else if(seaPlayerMisses.includes(k))t.classList.add('miss');t.disabled=seaPlayerHits.includes(k)||seaPlayerMisses.includes(k)||seaMode!=='computer';t.onclick=()=>seaComputerFire(r,c);target.appendChild(t)}seaDrawShipArt(own,seaPlaced.map(x=>x.cells));seaCpuHits.forEach(k=>{const [r,c]=k.split(',').map(Number),cell=own.querySelectorAll('.sea-cell')[r*SEA_W+c];if(cell){const mark=document.createElement('span');mark.className='sea-impact-mark';mark.textContent='✹';cell.appendChild(mark)}});const sunk=seaCpuShips.filter(sh=>sh.cells.every(([y,x])=>seaPlayerHits.includes(y+','+x))).map(sh=>sh.cells);seaDrawShipArt(target,sunk)}
    function seaComputerFire(r,c){if(seaMode!=='computer'||seaCpuTurnTimer||seaPlayerHits.includes(r+','+c)||seaPlayerMisses.includes(r+','+c))return;seaCannonSound();const k=r+','+c,hit=seaCpuShips.some(sh=>sh.cells.some(([y,x])=>y===r&&x===c));(hit?seaPlayerHits:seaPlayerMisses).push(k);if(hit)seaExplosionSound();else seaSplashSound();seaDrawLocalBoards();const remaining=seaCpuShips.reduce((a,sh)=>a+sh.cells.filter(([y,x])=>!seaPlayerHits.includes(y+','+x)).length,0);if(!remaining){seaMessage('🎉 You destroyed the computer fleet!');document.getElementById('sea-turn').textContent='Victory';playSound('win');arcadeResultShow(true,'You won!','You destroyed the computer fleet.');return}document.getElementById('sea-turn').textContent='Computer aiming…';seaMessage(hit?'Direct hit! The computer is preparing its shot.':'Splash! The computer is preparing its shot.');seaCpuTurnTimer=setTimeout(seaComputerTurn,1100)}
    function seaComputerTurn(){seaCpuTurnTimer=null;let r,c,k;do{r=Math.floor(Math.random()*SEA_H);c=Math.floor(Math.random()*SEA_W);k=r+','+c}while(seaCpuShots.includes(k));seaCpuShots.push(k);const hit=seaPlaced.some(sh=>sh.cells.some(([y,x])=>y===r&&x===c));(hit?seaCpuHits:seaCpuMisses).push(k);seaCannonSound();setTimeout(()=>{if(hit)seaExplosionSound();else seaSplashSound();seaDrawLocalBoards();const remaining=seaPlaced.reduce((a,sh)=>a+sh.cells.filter(([y,x])=>!seaCpuHits.includes(y+','+x)).length,0);if(!remaining){seaMessage('💥 Your fleet has been destroyed. The computer wins.');document.getElementById('sea-turn').textContent='Defeat';playSound('win');arcadeResultShow(false,'Computer wins','Your entire fleet was destroyed.')}else{document.getElementById('sea-turn').textContent='Your turn';seaMessage(hit?'The computer scored a hit! Your turn.':'The computer missed. Your turn.')}},450)}
    function seaCannonSound(){try{const c=audioCtx;if(c.state==='suspended')c.resume();const t=c.currentTime,o=c.createOscillator(),g=c.createGain(),n=c.createBufferSource(),b=c.createBuffer(1,Math.floor(c.sampleRate*.16),c.sampleRate),d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=(Math.random()*2-1)*(1-i/d.length);n.buffer=b;const f=c.createBiquadFilter(),ng=c.createGain();o.type='sawtooth';o.frequency.setValueAtTime(105,t);o.frequency.exponentialRampToValueAtTime(38,t+.2);g.gain.setValueAtTime(.34,t);g.gain.exponentialRampToValueAtTime(.001,t+.25);f.type='lowpass';f.frequency.value=850;ng.gain.setValueAtTime(.22,t);ng.gain.exponentialRampToValueAtTime(.001,t+.13);o.connect(g);g.connect(c.destination);n.connect(f);f.connect(ng);ng.connect(c.destination);o.start(t);o.stop(t+.26);n.start(t)}catch(e){}}
    function seaExplosionSound(){try{const c=audioCtx;if(c.state==='suspended')c.resume();const t=c.currentTime,n=c.createBufferSource(),b=c.createBuffer(1,Math.floor(c.sampleRate*.62),c.sampleRate),d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/d.length,1.7);n.buffer=b;const f=c.createBiquadFilter(),g=c.createGain(),o=c.createOscillator(),og=c.createGain();f.type='lowpass';f.frequency.setValueAtTime(1200,t);f.frequency.exponentialRampToValueAtTime(120,t+.55);g.gain.setValueAtTime(.52,t);g.gain.exponentialRampToValueAtTime(.001,t+.6);o.type='sine';o.frequency.setValueAtTime(75,t);o.frequency.exponentialRampToValueAtTime(28,t+.32);og.gain.setValueAtTime(.45,t);og.gain.exponentialRampToValueAtTime(.001,t+.35);n.connect(f);f.connect(g);g.connect(c.destination);o.connect(og);og.connect(c.destination);n.start(t);o.start(t);o.stop(t+.36)}catch(e){}}
    function seaSplashSound(){try{const c=audioCtx;if(c.state==='suspended')c.resume();const t=c.currentTime,dur=.75,n=c.createBufferSource(),b=c.createBuffer(1,Math.floor(c.sampleRate*dur),c.sampleRate),a=b.getChannelData(0);for(let i=0;i<a.length;i++){const x=i/a.length,env=Math.pow(1-x,2.4);a[i]=(Math.random()*2-1)*env;}n.buffer=b;const f=c.createBiquadFilter(),g=c.createGain();f.type='bandpass';f.frequency.setValueAtTime(1900,t);f.frequency.exponentialRampToValueAtTime(520,t+.55);f.Q.value=.7;g.gain.setValueAtTime(.42,t);g.gain.exponentialRampToValueAtTime(.001,t+dur);n.connect(f);f.connect(g);g.connect(c.destination);n.start(t);const bubble=c.createOscillator(),bg=c.createGain();bubble.type='sine';bubble.frequency.setValueAtTime(560,t+.04);bubble.frequency.exponentialRampToValueAtTime(170,t+.42);bg.gain.setValueAtTime(.12,t+.04);bg.gain.exponentialRampToValueAtTime(.001,t+.44);bubble.connect(bg);bg.connect(c.destination);bubble.start(t+.04);bubble.stop(t+.45)}catch(e){}}
    function arcadeNoise(freq,duration,volume,filterType){try{const ctx=audioCtx;if(ctx.state==='suspended')ctx.resume();const n=Math.floor(ctx.sampleRate*duration),buf=ctx.createBuffer(1,n,ctx.sampleRate),data=buf.getChannelData(0);for(let i=0;i<n;i++)data[i]=(Math.random()*2-1)*(1-i/n);const src=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();src.buffer=buf;filter.type=filterType;filter.frequency.value=freq;gain.gain.value=volume;src.connect(filter);filter.connect(gain);gain.connect(ctx.destination);src.start();}catch(e){}}
    const seaInviteCode=new URLSearchParams(location.search).get('sea');
    if(seaInviteCode){setTimeout(()=>{const tab=document.querySelector('#arcade-subnav .chip:nth-child(3)');switchGame('sea',tab);seaJoinInvite(seaInviteCode)},600)}
    const ARCADE_PROGRESS_KEY='mbbc_arcade_progress_v1_'+String(userId||'guest');
    let arcadeProgress={wordLevel:0,wordFound:[],waterLevel:0,waterTubes:[],waterHistory:[]};
    let arcadeSaveTimer=null;
    function arcadeSaveProgress(){
        arcadeProgress.wordLevel=wordLevel;arcadeProgress.wordFound=wordFound.slice();
        arcadeProgress.waterLevel=waterLevel;arcadeProgress.waterTubes=waterTubes.map(t=>t.slice());
        try{localStorage.setItem(ARCADE_PROGRESS_KEY,JSON.stringify(arcadeProgress))}catch(e){}
        clearTimeout(arcadeSaveTimer);arcadeSaveTimer=setTimeout(()=>fetch('/api/arcade/progress',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData||''},body:JSON.stringify({progress:arcadeProgress})}).catch(()=>{}),250);
    }
    window.addEventListener('pagehide',()=>{try{if(arcadeSaveTimer)clearTimeout(arcadeSaveTimer);fetch('/api/arcade/progress',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData||''},body:JSON.stringify({progress:arcadeProgress})})}catch(e){}});
    async function arcadeLoadProgress(){
        let saved=null;try{saved=JSON.parse(localStorage.getItem(ARCADE_PROGRESS_KEY)||'null')}catch(e){}
        try{const r=await fetch('/api/arcade/progress',{headers:{'X-Telegram-Init-Data':tg.initData||''}});if(r.ok){const d=await r.json();if(d.ok&&d.progress)saved=d.progress}}catch(e){}
        if(!saved||typeof saved!=='object')return;
        if(Number.isInteger(saved.wordLevel)&&saved.wordLevel>=0){wordLevel=saved.wordLevel%WORD_LEVELS.length;wordFound=Array.isArray(saved.wordFound)?saved.wordFound.filter(w=>WORD_LEVELS[wordLevel].words.some(x=>x.w===w)):[];wordLoad(wordLevel);wordFound=Array.isArray(saved.wordFound)?saved.wordFound.filter(w=>WORD_LEVELS[wordLevel].words.some(x=>x.w===w)):[];wordRender();}
        if(Number.isInteger(saved.waterLevel)&&saved.waterLevel>=0)waterLevel=saved.waterLevel;
        if(Array.isArray(saved.waterTubes)&&saved.waterTubes.length&&saved.waterTubes.every(t=>Array.isArray(t)&&t.length<=4&&t.every(c=>Number.isInteger(c)&&c>=0&&c<WATER_COLORS.length))){waterTubes=saved.waterTubes.map(t=>t.slice());waterSelected=-1;waterHistory=[];document.getElementById('water-level').textContent='Level '+(waterLevel+1);waterRender();}
    }
    const WORD_LEVELS=[
      {letters:'PTOS',words:[{w:'TOPS',cells:[[0,0],[1,0],[2,0],[3,0]]},{w:'POST',cells:[[2,0],[2,1],[2,2],[2,3]]},{w:'POTS',cells:[[0,4],[1,4],[2,4],[3,4]]},{w:'OPT',cells:[[1,4],[1,5],[1,6]]},{w:'STOP',cells:[[3,4],[3,5],[3,6],[3,7]]},{w:'TOP',cells:[[3,5],[4,5],[5,5]]},{w:'POT',cells:[[5,5],[5,6],[5,7]]}]},
      {letters:'EARTH',words:[{w:'HEART',cells:[[0,1],[1,1],[2,1],[3,1],[4,1]]},{w:'EARTH',cells:[[2,0],[2,1],[2,2],[2,3],[2,4]]},{w:'HEAT',cells:[[0,1],[0,2],[0,3],[0,4]]},{w:'RATE',cells:[[2,2],[3,2],[4,2],[5,2]]},{w:'EAT',cells:[[5,2],[5,3],[5,4]]}]},
      {letters:'PLANE',words:[{w:'PLANE',cells:[[2,0],[2,1],[2,2],[2,3],[2,4]]},{w:'PLAN',cells:[[2,0],[3,0],[4,0],[5,0]]},{w:'PALE',cells:[[0,0],[0,1],[0,2],[0,3]]}]}
    ];
    let wordLevel=0,wordLetters=[],wordCurrent='',wordFound=[],wordPath=[],wordPointer=false,wordWheelPointerId=null;
    function wordInit(){if(!wordLetters.length)wordLoad(0)}
    function wordLoad(i){wordLevel=i%WORD_LEVELS.length;const l=WORD_LEVELS[wordLevel];wordLetters=l.letters.split('');wordFound=[];wordCurrent='';wordPath=[];document.getElementById('word-level').textContent='Level '+(wordLevel+1);wordRender();document.getElementById('word-status').textContent='Swipe the letters to find '+l.words.length+' hidden words.'}
    function wordGridMap(){const targets={},solved={};WORD_LEVELS[wordLevel].words.forEach(({w,cells})=>cells.forEach(([r,c],i)=>{const k=r+','+c;targets[k]=true;if(wordFound.includes(w))solved[k]=w[i]}));return {targets,solved}}
    function wordRender(){document.getElementById('word-current').textContent=wordCurrent.split('').join(' · ')||'Swipe letters to make a word';const map=wordGridMap(),grid=document.getElementById('word-crossword');grid.innerHTML='';for(let r=0;r<6;r++)for(let c=0;c<8;c++){const d=document.createElement('div'),k=r+','+c,ch=map.solved[k];d.className='word-cell'+(!map.targets[k]?' blank':ch?'':' empty');if(ch)d.textContent=ch;grid.appendChild(d)}const found=document.getElementById('word-found-list');found.innerHTML=wordFound.map(w=>'<span>✓ '+w+'</span>').join('');const wheel=document.getElementById('word-wheel');wheel.innerHTML='';const count=wordLetters.length,rad=wheel.clientWidth*.34;wordLetters.forEach((ch,i)=>{const b=document.createElement('button');b.type='button';b.textContent=ch;b.dataset.index=i;const angle=(-Math.PI/2)+(2*Math.PI*i/count);b.style.left='calc(50% + '+(Math.cos(angle)*rad)+'px - 21px)';b.style.top='calc(50% + '+(Math.sin(angle)*rad)+'px - 21px)';b.addEventListener('pointerdown',e=>{e.preventDefault();wordStart(i,b,e)});wheel.appendChild(b)});}
    function wordStart(i,b,e){if(e&&e.pointerId!==undefined)wordWheelPointerId=e.pointerId;wordPointer=true;wordCurrent='';wordPath=[];document.getElementById('word-wheel').querySelectorAll('.picked').forEach(x=>x.classList.remove('picked'));wordAdd(i,b)}
    function wordAdd(i,b){if(!wordPointer||wordPath.includes(i))return;wordPath.push(i);wordCurrent+=wordLetters[i];b.classList.add('picked');document.getElementById('word-current').textContent=wordCurrent.split('').join(' · ');playSound('click')}
    document.addEventListener('pointermove',e=>{if(!wordPointer)return;if(wordWheelPointerId!==null&&e.pointerId!==wordWheelPointerId)return;const el=document.elementFromPoint(e.clientX,e.clientY),b=el&&el.closest?el.closest('#word-wheel button'):null;if(b)wordAdd(Number(b.dataset.index),b)},{passive:false});
    function wordEnd(e){if(!wordPointer)return;if(e&&wordWheelPointerId!==null&&e.pointerId!==undefined&&e.pointerId!==wordWheelPointerId)return;wordPointer=false;wordWheelPointerId=null;wordSubmit()}
    document.addEventListener('pointerup',wordEnd);document.addEventListener('pointercancel',wordEnd);
    function wordClear(){wordPointer=false;wordWheelPointerId=null;wordCurrent='';wordPath=[];wordRender()}
    function wordShuffle(){wordLetters.sort(()=>Math.random()-.5);wordClear();wordRender();playSound('click')}
    function wordSubmit(){if(!wordCurrent){wordRender();return}const w=wordCurrent.toUpperCase(),level=WORD_LEVELS[wordLevel];if(level.words.some(x=>x.w===w)&&!wordFound.includes(w)){wordFound.push(w);playSound('win');triggerHaptic('notification','success');wordMessage('✓ '+w+' found!');if(wordFound.length===level.words.length){wordMessage('🎉 Crossword complete!');arcadeResultShow(true,'Puzzle complete!','You found every hidden word.');triggerHaptic('notification','success');playSound('win');}arcadeSaveProgress();}else{playSound('click');wordMessage(wordFound.includes(w)?'You already found '+w+'.':'Not one of the hidden words. Try again.')}wordCurrent='';wordPath=[];wordPointer=false;wordWheelPointerId=null;wordRender()}
    function wordMessage(t){document.getElementById('word-status').textContent=t}
    const WORD_HINTS=[{'TOPS':'A word for more than one top; also the highest parts of things.','POST':'To send a letter, or a strong upright pole.','POTS':'Containers used for cooking or growing plants.','OPT':'To make a choice.','STOP':'The opposite of go.','TOP':'The highest point, or a spinning toy.','POT':'A container used for cooking.'},{'HEART':'The organ that pumps blood around your body.','EARTH':'The planet we live on.','HEAT':'The opposite of cold.','RATE':'A speed, price, or level measured over time.','EAT':'What you do when you have a meal.'},{'PLANE':'A vehicle that flies through the sky.','PLAN':'A set of steps for what you intend to do.','PALE':'A word meaning light in colour.'}];
    let wordHintGranted=false,wordHintIndex=0;
    function wordGiveHint(){const next=WORD_LEVELS[wordLevel].words.find(x=>!wordFound.includes(x.w));if(!next){wordMessage('All words found!');return}const hint=(WORD_HINTS[wordLevel]||{})[next.w]||('Think of a common '+next.w.length+'-letter word.');wordMessage('💡 Hint: '+hint);wordHintGranted=false;}
    async function wordWatchHint(){
        const btn=document.getElementById('word-hint-ad');
        if(btn.disabled)return;
        if(wordFound.length>=WORD_LEVELS[wordLevel].words.length){wordMessage('You have already found every word in this level.');return;}
        btn.disabled=true;const old=btn.textContent;
        try{
            const pendingKey='mbbc_word_hint_nonce';
            const pendingNonce=sessionStorage.getItem(pendingKey);
            if(pendingNonce){
                btn.textContent='Checking your ad…';
                const check=await fetch('/arcade-hint-status',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData||''},body:JSON.stringify({nonce:pendingNonce})});
                const status=await check.json();
                if(check.ok&&status.status==='done'){
                    sessionStorage.removeItem(pendingKey);wordGiveHint();playSound('win');triggerHaptic('notification','success');return;
                }
                if(status.status==='pending'){wordMessage('Your sponsored page is still open. Finish the ad, return here, then tap Get a hint again.');return;}
                sessionStorage.removeItem(pendingKey);
            }
            btn.textContent='Opening sponsor page…';
            const start=await fetch('/arcade-hint-start',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg.initData||''},body:JSON.stringify({})});
            const data=await start.json();
            if(!start.ok||!data.ok||!data.url)throw new Error(data.error||'Could not start sponsored ad');
            sessionStorage.setItem(pendingKey,data.nonce);
            wordMessage('Complete the rewarded ad on the sponsored page. Return here and tap Get a hint to unlock your hint.');
            if(tg&&typeof tg.openLink==='function')tg.openLink(data.url);else window.location.href=data.url;
        }catch(e){wordMessage(e.message==='Open the Arcade inside Telegram to watch a rewarded ad.'?e.message:'Could not open the sponsored page. Please try again.');}
        finally{btn.textContent=old;btn.disabled=false;}
    }
    function wordNext(){if(wordFound.length<WORD_LEVELS[wordLevel].words.length){wordMessage('Find all the words before moving on.');return}wordLevel++;wordLoad(wordLevel);arcadeSaveProgress()}
    const WATER_COLORS=['#f15b5b','#4aa3df','#e9bd45','#56bd79','#a77be8','#e98bc1'];let waterLevel=0,waterTubes=[],waterSelected=-1,waterHistory=[],waterPourBusy=false;
    function waterInit(){if(!waterTubes.length)waterNew()}
    function waterNew(){const colors=4+Math.min(waterLevel,2),arr=[];for(let c=0;c<colors;c++)for(let n=0;n<4;n++)arr.push(c);for(let i=arr.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[arr[i],arr[j]]=[arr[j],arr[i]]}waterTubes=[];for(let i=0;i<colors;i++)waterTubes.push(arr.slice(i*4,i*4+4));waterTubes.push([],[]);waterSelected=-1;waterHistory=[];document.getElementById('water-level').textContent='Level '+(waterLevel+1);waterMsg('Tap a glass, then tap another glass to pour matching liquid.');waterRender();arcadeSaveProgress()}
    function waterMsg(t){document.getElementById('water-status').textContent=t}
    function waterRender(){const b=document.getElementById('water-board');b.innerHTML='';waterTubes.forEach((tube,i)=>{const el=document.createElement('button');el.type='button';el.className='water-tube'+(i===waterSelected?' selected':'');el.setAttribute('aria-label','Glass '+(i+1));tube.forEach(c=>{const d=document.createElement('span');d.className='water-layer';d.style.background='linear-gradient(90deg, '+WATER_COLORS[c]+'cc, '+WATER_COLORS[c]+', '+WATER_COLORS[c]+'bb)';el.appendChild(d)});el.onclick=()=>waterTap(i);b.appendChild(el)})}
    function waterSound(){try{const c=audioCtx;if(c.state==='suspended')c.resume();const t=c.currentTime,dur=.9,n=c.createBufferSource(),buf=c.createBuffer(1,Math.floor(c.sampleRate*dur),c.sampleRate),a=buf.getChannelData(0);for(let i=0;i<a.length;i++){const x=i/a.length,env=Math.pow(1-x,1.6);a[i]=(Math.random()*2-1)*env*.34;}n.buffer=buf;const f=c.createBiquadFilter(),g=c.createGain();f.type='bandpass';f.frequency.setValueAtTime(1150,t);f.frequency.linearRampToValueAtTime(720,t+.7);f.Q.value=.55;g.gain.setValueAtTime(.0001,t);g.gain.linearRampToValueAtTime(.3,t+.08);g.gain.exponentialRampToValueAtTime(.001,t+dur);n.connect(f);f.connect(g);g.connect(c.destination);n.start(t);for(let j=0;j<3;j++){const o=c.createOscillator(),og=c.createGain(),st=t+.12+j*.2;o.type='sine';o.frequency.setValueAtTime(460-j*65,st);o.frequency.exponentialRampToValueAtTime(180-j*20,st+.16);og.gain.setValueAtTime(.0001,st);og.gain.linearRampToValueAtTime(.10,st+.025);og.gain.exponentialRampToValueAtTime(.001,st+.19);o.connect(og);og.connect(c.destination);o.start(st);o.stop(st+.2)}}catch(e){}}
    function waterCompleteSound(){try{const c=audioCtx;if(c.state==='suspended')c.resume();const t=c.currentTime;[523.25,659.25,783.99,1046.5].forEach((f,i)=>{const o=c.createOscillator(),g=c.createGain(),st=t+i*.11;o.type='sine';o.frequency.setValueAtTime(f,st);g.gain.setValueAtTime(.0001,st);g.gain.linearRampToValueAtTime(.18,st+.025);g.gain.exponentialRampToValueAtTime(.001,st+.34);o.connect(g);g.connect(c.destination);o.start(st);o.stop(st+.36)})}catch(e){}}
    function waterPourVisual(fromIndex,toIndex,color){const tubes=document.querySelectorAll('.water-tube'),from=tubes[fromIndex],to=tubes[toIndex];if(!from||!to)return;const a=from.getBoundingClientRect(),b=to.getBoundingClientRect(),x1=a.left+a.width*.76,y1=a.top+16,x2=b.left+b.width*.52,y2=b.top+Math.max(12,b.height*.20),midY=Math.max(y1+18,(y1+y2)/2),path=`M ${x1} ${y1} Q ${x1+(x2-x1)*.32} ${midY} ${x2} ${y2}`;from.classList.add('pouring');to.classList.add('receiving');from.style.setProperty('--tilt',b.left>=a.left?'15deg':'-15deg');const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','water-stream-svg');const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',path);p.setAttribute('pathLength','1');p.setAttribute('class','water-stream-path');p.style.setProperty('--pour-color',WATER_COLORS[color]);const gl=document.createElementNS('http://www.w3.org/2000/svg','path');gl.setAttribute('d',path);gl.setAttribute('pathLength','1');gl.setAttribute('class','water-stream-glint');svg.append(p,gl);for(let j=0;j<4;j++){const drop=document.createElementNS('http://www.w3.org/2000/svg','circle');drop.setAttribute('cx',x2+(Math.random()-.5)*14);drop.setAttribute('cy',y2+4);drop.setAttribute('r',2+Math.random()*2);drop.setAttribute('class','water-drop');drop.style.setProperty('--pour-color',WATER_COLORS[color]);svg.appendChild(drop)}document.body.appendChild(svg);const layers=from.querySelectorAll('.water-layer');if(layers.length)layers[layers.length-1].classList.add('water-moving');setTimeout(()=>{svg.remove();from.classList.remove('pouring');to.classList.remove('receiving');if(layers.length)layers[layers.length-1].classList.remove('water-moving')},850)}
    function waterTap(i){if(waterPourBusy)return;if(waterSelected<0){if(waterTubes[i].length){waterSelected=i;waterRender();playSound('click')}return}if(waterSelected===i){waterSelected=-1;waterRender();return}const from=waterTubes[waterSelected],to=waterTubes[i];if(from.length&&to.length<4&&(!to.length||to[to.length-1]===from[from.length-1])){waterHistory.push(JSON.stringify(waterTubes));const color=from[from.length-1];waterPourBusy=true;waterPourVisual(waterSelected,i,color);waterSound();let count=0;while(from.length&&from[from.length-1]===color&&to.length<4){to.push(from.pop());count++}waterSelected=-1;setTimeout(()=>{waterRender();waterPourBusy=false;arcadeSaveProgress();if(waterTubes.every(t=>!t.length||(t.length===4&&t.every(x=>x===t[0])))){waterMsg('🎉 Beautiful! Every colour is sorted.');playSound('win');triggerHaptic('notification','success');waterCompleteSound();arcadeResultShow(true,'Level complete!','Every colour is sorted correctly.')}else waterMsg('Nice pour! Keep sorting the colours.')},900);return}waterSelected=i;waterRender();playSound('click');waterMsg('Pour into an empty glass or one with the same top colour.')}
    function waterUndo(){if(waterPourBusy)return;if(waterHistory.length){waterTubes=JSON.parse(waterHistory.pop());waterSelected=-1;waterRender();playSound('click');arcadeSaveProgress()}}function waterNext(){if(!waterTubes.every(t=>!t.length||(t.length===4&&t.every(x=>x===t[0])))){waterMsg('Sort every colour first.');return}waterLevel++;waterNew();arcadeSaveProgress()}
    const WHOT_SHAPES = ['CIRCLE', 'TRIANGLE', 'CROSS', 'SQUARE', 'STAR'];
    const WHOT_MAX = { CIRCLE: 14, TRIANGLE: 14, CROSS: 14, SQUARE: 14, STAR: 8 };
    const whotSymbols = { CIRCLE:'●', TRIANGLE:'▲', CROSS:'✚', SQUARE:'■', STAR:'★', WHOT:'W' };
    const whotColors = ['#c9343e','#d69a19','#2879b9','#25834f','#7448a5','#8b75ff'];
    const WHOT_SPECIAL = {
        1: 'HOLD_ON', 2: 'PICK_TWO', 5: 'PICK_THREE',
        8: 'SUSPENSION', 14: 'GENERAL_MARKET', 20: 'WHOT'
    };
    function whotBuildDeck() {
        const deck = [];
        WHOT_SHAPES.forEach((shape, si) => {
            for (let n = 1; n <= WHOT_MAX[shape]; n++) {
                deck.push({ number: n, shape, color: si });
            }
        });
        deck.push({ number: 20, shape: 'WHOT', color: 5 });
        return deck;
    }
    function whotShuffle(cards) {
        for (let i = cards.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [cards[i], cards[j]] = [cards[j], cards[i]];
        }
        return cards;
    }
    function whotCanPlay(card, top, declaredShape) {
        if (!card || !top) return false;
        if (card.shape === 'WHOT') return true;
        if (top.shape === 'WHOT') return card.shape === declaredShape;
        if (card.number === top.number) return true;
        if (card.shape === top.shape) return true;
        return false;
    }
    function whotApplySpecial(card, declaredShape) {
        const effect = WHOT_SPECIAL[card.number];
        switch (effect) {
            case 'HOLD_ON':        return { skipNext: true,  drawCount: 0, declaredShape: null };
            case 'SUSPENSION':     return { skipNext: true,  drawCount: 0, declaredShape: null };
            case 'PICK_TWO':       return { skipNext: true,  drawCount: 2, declaredShape: null };
            case 'PICK_THREE':     return { skipNext: true,  drawCount: 3, declaredShape: null };
            case 'GENERAL_MARKET': return { skipNext: true,  drawCount: 1, declaredShape: null };
            case 'WHOT':           return { skipNext: false, drawCount: 0, declaredShape: declaredShape };
            default:               return { skipNext: false, drawCount: 0, declaredShape: null };
        }
    }
    let whotDeck = [];
    let whotPlayer = [];
    let whotCpu = [];
    let whotTop = null;
    let whotStarted = false;
    let whotLocked = false;
    let whotDeclaredShape = null;
    let whotShapeResolve = null;
    let whotOnlineCode = null;
    let whotPollTimer = null;
    let whotOnlineGame = false;
    let whotLastOnlineTop = null;
    function whotStopPolling() {
        if (whotPollTimer) { clearInterval(whotPollTimer); whotPollTimer = null; }
    }
    function whotKillOnline() {
        whotStopPolling();
        whotOnlineGame = false;
        whotOnlineCode = null;
        whotLastOnlineTop = null;
        try { localStorage.removeItem('whot_state'); } catch(e) {}
    }
    function whotPromptShape() {
        const picker = document.getElementById('whot-shape-picker');
        picker.classList.add('open');
        return new Promise(resolve => { whotShapeResolve = resolve; });
    }
    function whotShapeChosen(shape) {
        document.getElementById('whot-shape-picker').classList.remove('open');
        if (whotShapeResolve) { whotShapeResolve(shape); whotShapeResolve = null; }
    }
    function whotShapeCancelled() {
        document.getElementById('whot-shape-picker').classList.remove('open');
        if (whotShapeResolve) { whotShapeResolve(null); whotShapeResolve = null; }
    }
    function whotSelectMode(mode) {
        playSound('click');
        if (mode === 'computer' && whotOnlineGame) {
            whotKillOnline();
            try { sessionStorage.clear(); } catch(e) {}
            setTimeout(() => { window.location.reload(); }, 100);
            return;
        }
        whotKillOnline();
        const lobby = document.getElementById('whot-lobby');
        const actionsComp = document.getElementById('whot-actions-computer');
        const btnComp = document.getElementById('btn-mode-computer');
        const btnOnline = document.getElementById('btn-mode-online');
        if (mode === 'computer') {
            btnComp.classList.add('active');
            btnOnline.classList.remove('active');
            lobby.style.display = 'none';
            actionsComp.style.display = 'flex';
            document.getElementById('whot-opponent-name').textContent = '🤖 Computer';
            whotNewGame();
        } else {
            btnOnline.classList.add('active');
            btnComp.classList.remove('active');
            lobby.style.display = 'block';
            actionsComp.style.display = 'none';
            whotStarted = false;
            whotLocked = true;
            document.getElementById('whot-hand').innerHTML = '';
            document.getElementById('whot-player-count').textContent = '—';
            document.getElementById('whot-cpu-count').textContent = '—';
            document.getElementById('whot-opponent-fan').innerHTML = '';
            document.getElementById('whot-turn').textContent = '—';
            document.getElementById('whot-room-code').textContent = '';
            whotMessage('Choose an option above to start playing online.');
        }
    }
    async function whotApi(path, body) {
        const response = await fetch(path, {
            method: body ? 'POST' : 'GET',
            headers: {'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg.initData || ''},
            body: body ? JSON.stringify(body) : undefined
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'WHOT service error');
        return data;
    }
    async function whotCreateRoom() {
        playSound('click');
        try {
            whotKillOnline();
            whotOnlineGame = true;
            const d = await whotApi('/api/whot/create', {});
            whotOnlineCode = d.code;
            document.getElementById('whot-room-code').textContent = 'Room Code: ' + d.code;
            if (tg.openTelegramLink) tg.openTelegramLink(d.share_url); else window.open(d.share_url, '_blank');
            whotMessage('Room created. Waiting for friend to join…');
            whotStartPolling();
        } catch(e) {
            whotKillOnline();
            whotMessage(e.message);
            tg.showAlert(e.message);
        }
    }
    async function whotJoinRoomPrompt() {
        playSound('click');
        const code = window.prompt('Enter your friend’s WHOT room code');
        if (!code) return;
        try {
            whotKillOnline();
            const d = await whotApi('/api/whot/join', {code});
            whotOnlineCode = code.toUpperCase();
            whotOnlineGame = true;
            whotRenderOnline(d.game);
            whotStartPolling();
        } catch(e) {
            whotKillOnline();
            whotMessage(e.message);
            tg.showAlert(e.message);
        }
    }
    async function whotFindRandom() {
        playSound('click');
        try {
            whotKillOnline();
            whotOnlineGame = true;
            const d = await whotApi('/api/whot/random', {});
            whotOnlineCode = d.code;
            if (d.matched) whotRenderOnline(d.game);
            else whotMessage(d.message);
            whotStartPolling();
        } catch(e) {
            whotKillOnline();
            whotMessage(e.message);
            tg.showAlert(e.message);
        }
    }
    function whotStartPolling() {
        whotStopPolling();
        whotPollTimer = setInterval(async () => {
            if (!whotOnlineGame || !whotOnlineCode) return;
            try {
                const d = await whotApi('/api/whot/state?code=' + encodeURIComponent(whotOnlineCode));
                if (!whotOnlineGame) return;
                whotRenderOnline(d.game);
            } catch(e) { whotMessage(e.message); }
        }, 1200);
    }
    function whotRenderOnline(g) {
        if (!whotOnlineGame) return;
        const topKey = JSON.stringify(g.top);
        if (whotLastOnlineTop && topKey !== whotLastOnlineTop) { whotAnimate('opponent'); playSound('deal'); }
        whotLastOnlineTop = topKey;
        whotStarted = g.status === 'playing';
        whotLocked = !g.my_turn || g.status !== 'playing';
        whotDeclaredShape = g.declared_shape || null;
        document.getElementById('whot-opponent-name').textContent = '👤 ' + g.opponent_name;
        document.getElementById('whot-cpu-count').textContent = g.opponent_count + ' cards';
        document.getElementById('whot-player-count').textContent = g.my_count + ' cards';
        document.getElementById('whot-turn').textContent = g.my_turn ? 'Your turn' : 'Opponent’s turn';
        document.getElementById('whot-top').outerHTML = whotCardMarkup(g.top, 'top-card').replace('<div class="whot-card','<div id="whot-top" class="whot-card');
        const fan = document.getElementById('whot-opponent-fan');
        fan.innerHTML = '';
        for (let i = 0; i < Math.min(g.opponent_count, 14); i++) {
            const b = document.createElement('span'); b.className = 'whot-back'; fan.appendChild(b);
        }
        const hand = document.getElementById('whot-hand');
        hand.innerHTML = '';
        whotPlayer = g.hand || [];
        whotPlayer.forEach((card, i) => {
            const b = document.createElement('button');
            b.type = 'button'; b.className = 'whot-card';
            b.style.borderColor = whotColors[card.color]; b.style.color = whotColors[card.color];
            b.innerHTML = `<span class="whot-symbol">${whotSymbols[card.shape] || '?'}</span>${card.number}<small>${card.shape}</small>`;
            b.disabled = whotLocked || !whotCanPlay(card, g.top, g.declared_shape);
            b.onclick = () => whotOnlineMove('play', i);
            hand.appendChild(b);
        });
        document.getElementById('whot-draw').disabled = whotLocked || g.deck_count === 0;
        whotMessage(g.status === 'waiting' ? 'Waiting for an opponent…' : g.status === 'finished' ? (g.winner === String(userId) ? '🎉 You won!' : g.message) : g.message);
    }
    async function whotOnlineMove(action, index) {
        if (!whotOnlineGame || !whotOnlineCode) return;
        let declared = null;
        if (action === 'play' && whotPlayer[index] && whotPlayer[index].shape === 'WHOT') {
            declared = await whotPromptShape();
            if (!declared) return;
        }
        try {
            whotAnimate('player'); playSound('deal');
            const payload = { code: whotOnlineCode, action, index };
            if (declared) payload.declared_shape = declared;
            const d = await whotApi('/api/whot/move', payload);
            if (!whotOnlineGame) return;
            whotRenderOnline(d.game);
        } catch(e) {
            whotMessage(e.message);
            tg.showAlert(e.message);
        }
    }
    function whotNewGame() {
        playSound('click');
        whotKillOnline();
        whotStarted = true;
        whotLocked = false;
        whotDeclaredShape = null;
        whotDeck = whotShuffle(whotBuildDeck());
        whotPlayer = whotDeck.splice(0, 5);
        whotCpu = whotDeck.splice(0, 5);
        whotTop = whotDeck.pop();
        while (whotTop && whotTop.shape === 'WHOT') {
            whotDeck.unshift(whotTop);
            whotTop = whotDeck.pop();
        }
        whotRenderLocal();
        playSound('deal');
        whotMessage('Your turn. Match by number or shape. (1=Hold On, 2=Pick Two, 5=Pick Three, 8=Suspension, 14=General Market, 20=WHOT)');
    }
    function whotCardMarkup(card, extra='') {
        const shapeLabel = card.shape === 'WHOT' ? 'WHOT!' : card.shape;
        const sym = whotSymbols[card.shape] || '?';
        const num = card.shape === 'WHOT' ? '20' : card.number;
        return `<div class="whot-card ${extra}" style="border-color:${whotColors[card.color]};color:${whotColors[card.color]}"><span class="whot-symbol">${sym}</span>${num}<small>${shapeLabel}</small></div>`;
    }
    function whotAnimate(actor) {
        const el = document.getElementById('whot-actor');
        el.classList.remove('go', 'opponent');
        if (actor === 'opponent' || actor === 'cpu') el.classList.add('opponent');
        void el.offsetWidth;
        el.classList.add('go');
        const top = document.getElementById('whot-top');
        if (top) {
            top.classList.remove('whot-play-card');
            void top.offsetWidth;
            top.classList.add('whot-play-card');
        }
    }
    function whotRenderLocal() {
        const topEl = document.getElementById('whot-top');
        if (topEl) topEl.outerHTML = whotCardMarkup(whotTop, 'top-card').replace('<div class="whot-card','<div id="whot-top" class="whot-card');
        document.getElementById('whot-player-count').textContent = `${whotPlayer.length} cards`;
        document.getElementById('whot-cpu-count').textContent = `${whotCpu.length} cards`;
        const fan = document.getElementById('whot-opponent-fan');
        fan.innerHTML = '';
        whotCpu.forEach(() => { const b = document.createElement('span'); b.className = 'whot-back'; fan.appendChild(b); });
        const hand = document.getElementById('whot-hand');
        hand.innerHTML = '';
        whotPlayer.forEach((card, index) => {
            const button = document.createElement('button');
            button.type = 'button'; button.className = 'whot-card';
            button.style.borderColor = whotColors[card.color]; button.style.color = whotColors[card.color];
            button.innerHTML = `<span class="whot-symbol">${whotSymbols[card.shape] || '?'}</span>${card.shape === 'WHOT' ? '20' : card.number}<small>${card.shape === 'WHOT' ? 'WHOT!' : card.shape}</small>`;
            button.disabled = whotLocked || !whotCanPlay(card, whotTop, whotDeclaredShape);
            button.addEventListener('click', () => whotPlayLocal(index));
            hand.appendChild(button);
        });
    }
    function whotMessage(message) { document.getElementById('whot-status').textContent = message; }
    function whotDraw() {
        if (whotOnlineGame === true && whotOnlineCode !== null && whotOnlineCode !== '') {
            whotOnlineMove('draw');
            return;
        }
        if (!whotStarted || whotLocked) return;
        if (!whotDeck.length) { whotMessage('The draw pile is empty!'); return; }
        playSound('deal');
        const drawn = whotDeck.pop();
        whotPlayer.push(drawn);
        whotRenderLocal();
        if (!whotCanPlay(drawn, whotTop, whotDeclaredShape)) {
            whotMessage('Card drawn does not match. Computer plays next.');
            whotLocked = true;
            window.setTimeout(whotCpuTurn, 1000);
        } else {
            whotMessage('Card drawn matches! You can play it or draw again.');
        }
    }
    async function whotPlayLocal(index) {
        if (whotLocked) return;
        const card = whotPlayer[index];
        if (!whotCanPlay(card, whotTop, whotDeclaredShape)) return;
        let declared = null;
        if (card.shape === 'WHOT') {
            declared = await whotPromptShape();
            if (!declared) return;
        }
        whotTop = whotPlayer.splice(index, 1)[0];
        playSound('deal'); triggerHaptic('impact', 'light');
        whotAnimate('player');
        const sp = whotApplySpecial(whotTop, declared);
        if (sp.declaredShape) whotDeclaredShape = sp.declaredShape;
        else if (whotTop.shape !== 'WHOT') whotDeclaredShape = null;
        whotRenderLocal();
        if (!whotPlayer.length) {
            whotLocked = true; playSound('win');
            whotMessage('🎉 You won!'); return;
        }
        if (sp.skipNext) {
            for (let i = 0; i < sp.drawCount; i++) {
                if (whotDeck.length) whotCpu.push(whotDeck.pop());
            }
            whotRenderLocal();
            whotLocked = false;
            const eff = WHOT_SPECIAL[whotTop.number];
            if (sp.drawCount) {
                whotMessage(`You played ${whotTop.number} (${eff}). Computer picks ${sp.drawCount} and is skipped — your turn again!`);
            } else {
                whotMessage(`You played ${whotTop.number} (${eff}). Computer is skipped — your turn again!`);
            }
            return;
        }
        whotLocked = true;
        whotMessage('You played. Computer is thinking...');
        window.setTimeout(whotCpuTurn, 1000);
    }
    function whotCpuTurn() {
        if (!whotStarted || whotOnlineGame) return;
        if (!whotCpu.length) {
            whotLocked = true; whotRenderLocal();
            whotMessage('🤖 Computer wins!'); return;
        }
        const index = whotCpu.findIndex(c => whotCanPlay(c, whotTop, whotDeclaredShape));
        if (index >= 0) {
            const card = whotCpu[index];
            let declared = null;
            if (card.shape === 'WHOT') {
                declared = WHOT_SHAPES[Math.floor(Math.random() * WHOT_SHAPES.length)];
            }
            whotTop = whotCpu.splice(index, 1)[0];
            whotAnimate('cpu'); playSound('deal');
            const sp = whotApplySpecial(whotTop, declared);
            if (sp.declaredShape) whotDeclaredShape = sp.declaredShape;
            else if (whotTop.shape !== 'WHOT') whotDeclaredShape = null;
            if (!whotCpu.length) {
                whotLocked = true; whotRenderLocal();
                whotMessage('🤖 Computer wins!'); return;
            }
            if (sp.skipNext) {
                for (let i = 0; i < sp.drawCount; i++) {
                    if (whotDeck.length) whotPlayer.push(whotDeck.pop());
                }
                whotLocked = true;
                whotRenderLocal();
                const eff = WHOT_SPECIAL[whotTop.number];
                if (sp.drawCount) {
                    whotMessage(`Computer played ${whotTop.number} (${eff}). You pick ${sp.drawCount} and are skipped!`);
                } else {
                    whotMessage(`Computer played ${whotTop.number} (${eff}). You are skipped!`);
                }
                window.setTimeout(whotCpuTurn, 1000);
                return;
            }
            whotLocked = false;
            whotRenderLocal();
            whotMessage('Computer played. Your turn.');
            return;
        }
        if (whotDeck.length) {
            const drawn = whotDeck.pop();
            whotCpu.push(drawn);
            playSound('deal');
            if (whotCanPlay(drawn, whotTop, whotDeclaredShape)) {
                let declared = null;
                if (drawn.shape === 'WHOT') {
                    declared = WHOT_SHAPES[Math.floor(Math.random() * WHOT_SHAPES.length)];
                }
                whotTop = whotCpu.pop();
                whotAnimate('cpu');
                const sp = whotApplySpecial(whotTop, declared);
                if (sp.declaredShape) whotDeclaredShape = sp.declaredShape;
                else if (whotTop.shape !== 'WHOT') whotDeclaredShape = null;
                if (!whotCpu.length) {
                    whotLocked = true; whotRenderLocal();
                    whotMessage('🤖 Computer wins!'); return;
                }
                if (sp.skipNext) {
                    for (let i = 0; i < sp.drawCount; i++) {
                        if (whotDeck.length) whotPlayer.push(whotDeck.pop());
                    }
                    whotLocked = true;
                    whotRenderLocal();
                    whotMessage(`Computer drew and played ${whotTop.number}. You pick ${sp.drawCount} and are skipped.`);
                    window.setTimeout(whotCpuTurn, 1000);
                    return;
                }
                whotLocked = false;
                whotRenderLocal();
                whotMessage('Computer drew and played. Your turn.');
                return;
            }
            whotMessage('Computer drew a card. Your turn.');
        } else {
            whotMessage('Draw pile empty! Your turn.');
        }
        whotLocked = false;
        whotRenderLocal();
    }
    const whotInviteCode = new URLSearchParams(location.search).get('whot');
    if (whotInviteCode) {
        whotSelectMode('online');
        setTimeout(() => { whotJoinInvite(whotInviteCode); }, 500);
    }
    async function whotJoinInvite(code) {
        try {
            whotKillOnline();
            const d = await whotApi('/api/whot/join', {code});
            whotOnlineCode = code.toUpperCase();
            whotOnlineGame = true;
            whotRenderOnline(d.game);
            whotStartPolling();
        } catch(e) {
            whotKillOnline();
            whotMessage(e.message);
            tg.showAlert(e.message);
        }
    }
    let board = ['', '', '', '', '', '', '', '', ''];
    let currentPlayer = 'X';
    let isGameActive = true;
    function cellClicked(index) {
        if (board[index] !== '' || !isGameActive) return;
        playSound('click'); triggerHaptic('impact', 'light');
        board[index] = currentPlayer;
        const el = document.getElementsByClassName('cell')[index];
        el.innerText = currentPlayer; el.classList.add('cell-pop');
        const wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
        for(let c of wins) {
            if (board[c[0]] && board[c[0]] === board[c[1]] && board[c[1]] === board[c[2]]) {
                playSound('win'); triggerHaptic('notification', 'success');
                document.getElementById('game-status').innerText = `Player ${currentPlayer} Wins! 🎉`;
                isGameActive = false; return;
            }
        }
        if (!board.includes('')) { document.getElementById('game-status').innerText = `It's a Draw! 🤝`; isGameActive = false; return; }
        currentPlayer = currentPlayer === 'X' ? 'O' : 'X';
        document.getElementById('game-status').innerText = `Player ${currentPlayer}'s Turn`;
    }
    function resetGame() {
        playSound('click');
        board = ['', '', '', '', '', '', '', '', '']; isGameActive = true; currentPlayer = 'X';
        document.getElementById('game-status').innerText = `Player X's Turn`;
        Array.from(document.getElementsByClassName('cell')).forEach(c => { c.innerText = ''; c.classList.remove('cell-pop'); });
    }
    arcadeLoadProgress();
    renderItems(sampleItems);
</script>
</body>
</html>
"""

# ===== MONETAG REWARDED INTERSTITIAL =====
MONETAG_ZONE_ID = "12168607"
MONETAG_PENDING = {}
MONETAG_LOCK = threading.Lock()
MONETAG_TTL = 15 * 60

@app.route('/arcade-hint-start', methods=['POST'])
def arcade_hint_start():
    user = _telegram_webapp_user()
    if not user:
        return jsonify({"ok": False, "error": "Open the Arcade inside Telegram to watch a rewarded ad."}), 401
    nonce = secrets.token_urlsafe(24)
    with MONETAG_LOCK:
        MONETAG_PENDING[nonce] = {"user_id": int(user['id']), "kind": "hint", "msg_start": 0, "msg_end": 0, "created": time.time(), "done": False, "claimed": False, "failures": 0}
        for key in list(MONETAG_PENDING):
            if time.time() - MONETAG_PENDING[key]["created"] > MONETAG_TTL:
                MONETAG_PENDING.pop(key, None)
    return jsonify({"ok": True, "nonce": nonce, "url": request.host_url.rstrip('/') + '/monetag?n=' + nonce})

@app.route('/arcade-hint-status', methods=['POST'])
def arcade_hint_status():
    user = _telegram_webapp_user()
    if not user:
        return jsonify({"status": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    nonce = str(data.get('nonce', ''))
    with MONETAG_LOCK:
        rec = MONETAG_PENDING.get(nonce)
        if not rec or rec.get('kind') != 'hint' or str(rec.get('user_id')) != user['id'] or time.time() - rec['created'] > MONETAG_TTL:
            return jsonify({"status": "expired"}), 410
        if not rec.get('done'):
            return jsonify({"status": "pending"})
        if rec.get('claimed'):
            return jsonify({"status": "claimed"}), 409
        rec['claimed'] = True
    return jsonify({"status": "done"})

@app.route('/monetag-start', methods=['POST'])
def monetag_start():
    data = request.get_json(silent=True) or {}
    if not _secret_ok(data.get('secret')):
        return jsonify({"status": "forbidden"}), 403
    try:
        uid = int(data.get('user_id'))
    except (TypeError, ValueError):
        return jsonify({"status": "invalid_user"}), 400
    nonce = secrets.token_urlsafe(24)
    record = {"user_id": uid, "kind": str(data.get("kind", "wall")), "msg_start": int(data.get("msg_start", 0) or 0), "msg_end": int(data.get("msg_end", 0) or 0), "created": time.time(), "done": False, "claimed": False, "failures": 0}
    with MONETAG_LOCK:
        MONETAG_PENDING[nonce] = record
        for key in list(MONETAG_PENDING):
            if time.time() - MONETAG_PENDING[key]["created"] > MONETAG_TTL:
                MONETAG_PENDING.pop(key, None)
    return jsonify({"status": "ok", "nonce": nonce})

@app.route('/monetag')
def monetag_page():
    nonce = request.args.get('n', '')
    with MONETAG_LOCK:
        rec = MONETAG_PENDING.get(nonce)
    valid = bool(rec and time.time() - rec["created"] <= MONETAG_TTL)
    if not valid:
        return "This ad session expired. Return to Telegram and request a new ad.", 410
    page = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Watch sponsor</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script async src="https://libtl.com/sdk.js" data-zone="12168607" data-sdk="show_12168607"></script>
<style>body{font:16px Arial;background:#101827;color:white;text-align:center;padding:28px}button{padding:14px 22px;border:0;border-radius:10px;background:#22c55e;color:#07130a;font-weight:bold}#msg{margin:24px}</style></head>
<body><h2>🎬 Sponsored message</h2><p>{{ 'Complete the rewarded ad to unlock your World Puzzle hint.' if ad_kind == 'hint' else 'Complete the rewarded ad to receive your download credit.' }}</p><button id="watch">Watch rewarded ad</button><div id="msg">{{ 'After the ad completes, return to World Puzzle and tap Get a hint again.' if ad_kind == 'hint' else 'Your reward is not credited until the ad flow completes and you verify in the bot.' }}</div>
<script>const nonce={{ nonce|tojson }}; const tg=window.Telegram?.WebApp; if(tg)tg.ready();
document.getElementById('watch').onclick=async()=>{const b=document.getElementById('watch'),m=document.getElementById('msg');b.disabled=true;m.textContent='Loading ad…';
try{let waited=0;while(typeof window.show_12168607!=='function'&&waited<12000){await new Promise(r=>setTimeout(r,250));waited+=250;}if(typeof window.show_12168607!=='function')throw new Error('Ad SDK did not load');await window.show_12168607();
const r=await fetch('/monetag-complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nonce})});if(!r.ok)throw new Error('Could not record completion');m.textContent={{ ('Ad completed! Return to World Puzzle and tap Get a hint again to unlock your hint.' if ad_kind == 'hint' else 'Ad completed successfully. Your reward has been credited. You can return to MichaelBBC Vault.')|tojson }};
}catch(e){try{const fr=await fetch('/monetag-failed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nonce})});const fd=await fr.json();m.textContent=fd.failures>=2?'Monetag failed twice. Return to Telegram and choose Adsterra fallback.':'Ad failed. You can retry Monetag.';}catch(_){m.textContent='The ad did not complete. Return to Telegram and try again.';}b.disabled=false;}};</script></body></html>'''
    return render_template_string(page, nonce=nonce, ad_kind=rec.get('kind', 'wall'))

@app.route('/monetag-failed', methods=['POST'])
def monetag_failed():
    data = request.get_json(silent=True) or {}
    nonce = str(data.get('nonce', ''))
    with MONETAG_LOCK:
        rec = MONETAG_PENDING.get(nonce)
        if not rec or time.time() - rec['created'] > MONETAG_TTL:
            return jsonify({"status": "expired"}), 410
        rec['failures'] = int(rec.get('failures', 0)) + 1
    return jsonify({"status": "fallback_available" if rec['failures'] >= 2 else "retry", "failures": rec['failures']})

@app.route('/monetag-complete', methods=['POST'])
def monetag_complete():
    data = request.get_json(silent=True) or {}
    nonce = str(data.get('nonce', ''))
    with MONETAG_LOCK:
        rec = MONETAG_PENDING.get(nonce)
        if not rec or time.time() - rec["created"] > MONETAG_TTL:
            return jsonify({"status": "expired"}), 410
        rec["done"] = True
    return jsonify({"status": "ok"})

@app.route('/monetag-status', methods=['POST'])
def monetag_status():
    data = request.get_json(silent=True) or {}
    if not _secret_ok(data.get('secret')):
        return jsonify({"status": "forbidden"}), 403
    try:
        uid = int(data.get('user_id'))
    except (TypeError, ValueError):
        return jsonify({"status": "invalid_user"}), 400
    with MONETAG_LOCK:
        matches = [(k, v) for k, v in MONETAG_PENDING.items() if v["user_id"] == uid and not v["claimed"]]
        if not matches:
            return jsonify({"status": "expired"})
        nonce, rec = max(matches, key=lambda item: item[1]["created"])
        if not rec["done"]:
            return jsonify({"status": "fallback_available" if int(rec.get("failures", 0)) >= 2 else "pending"})
        rec["claimed"] = True
        tokens = load_tokens()
        profile = get_user_profile(uid, tokens)
        reward = get_reward()
        profile["downloads_left"] = int(profile.get("downloads_left", 0)) + reward
        profile["batch_downloads_left"] = int(profile.get("batch_downloads_left", 0)) + reward * 5
        profile["verified"] = True
        save_tokens(tokens)
    return jsonify({"status": "done", "reward": reward, "kind": rec["kind"], "msg_start": rec["msg_start"], "msg_end": rec["msg_end"], "downloads_left": profile["downloads_left"]})

@app.route('/monetag-reward')
def monetag_admin_reward():
    if not _secret_ok(request.args.get('secret')) or str(request.args.get('userid')) != str(ADMIN_ID):
        return jsonify({"status": "forbidden"}), 403
    nonce = secrets.token_urlsafe(24)
    with MONETAG_LOCK:
        MONETAG_PENDING[nonce] = {"user_id": ADMIN_ID, "kind": "test", "msg_start": 0, "msg_end": 0, "created": time.time(), "done": True, "claimed": False}
    return jsonify({"status": "ok"})

# ===== FLASK BACKEND ROUTING =====
@app.route('/get_tokens', methods=['GET'])
def get_tokens_route():
    if not _secret_ok(request.headers.get("X-Api-Secret")):
        return jsonify({"status": "forbidden"}), 403
    return jsonify(load_tokens())

@app.route('/save_tokens', methods=['POST'])
def api_save_tokens():
    if not _secret_ok(request.headers.get("X-Api-Secret")):
        return jsonify({"status": "forbidden"}), 403
    try:
        new_tokens = request.json
        if new_tokens is not None:
            save_tokens(new_tokens)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "invalid data"}), 400

@app.route('/get_reward', methods=['GET'])
def get_reward_route():
    return jsonify({"reward": get_reward(), "free": get_free(), "status": "success"})

@app.route('/check-download', methods=['POST'])
def check_download():
    if not _secret_ok(request.headers.get("X-Api-Secret")):
        return jsonify({"status": "forbidden"}), 403
    data = request.json or {}
    user_id = data.get('user_id')
    is_batch = data.get('is_batch', False)
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    if int(user_id) == ADMIN_ID:
        return jsonify({"status": "allowed", "left": 999})
    tokens = load_tokens()
    profile = get_user_profile(user_id, tokens)
    if is_batch:
        if profile.get("batch_downloads_left", 20) > 0:
            profile["batch_downloads_left"] -= 1
            save_tokens(tokens)
            return jsonify({"status": "allowed", "left": profile["batch_downloads_left"]})
        else:
            save_tokens(tokens)
            return jsonify({"status": "blocked", "reason": "limit_reached", "left": 0})
    else:
        if profile["downloads_left"] > 0:
            profile["downloads_left"] -= 1
            if profile["downloads_left"] <= 0:
                profile["verified"] = False
            save_tokens(tokens)
            return jsonify({"status": "allowed", "left": profile["downloads_left"]})
        else:
            save_tokens(tokens)
            return jsonify({"status": "blocked", "reason": "limit_reached", "left": 0})

def _secret_ok(val):
    return bool(val) and hmac.compare_digest(str(val), str(API_SECRET))

DOWNLOAD_EVENTS_FILE = os.path.join(os.path.dirname(ITEMS_FILE), "item_download_events.json")
DOWNLOAD_RESET_MARKER = os.path.join(os.path.dirname(ITEMS_FILE), "download_counts_reset_v1.done")

def reset_legacy_download_counts_once():
    if os.path.exists(DOWNLOAD_RESET_MARKER):
        return
    items = load_items()
    changed = False
    for item in items:
        if int(item.get("downloads", 0) or 0) != 0:
            item["downloads"] = 0
            changed = True
    if changed:
        save_items(items)
        with open(DOWNLOAD_RESET_MARKER, "w", encoding="utf-8") as marker:
            marker.write("Download counts reset for verified delivery tracking.\n")

def _item_message_range(item):
    link = str(item.get("link", ""))
    try:
        code = parse_qs(urlparse(link).query).get("start", [""])[0]
        if not code.startswith("vid"):
            return None
        value = code[3:]
        if "to" in value:
            first, last = value.split("to", 1)
            start_id, end_id = int(first), int(last)
        else:
            start_id = end_id = int(value)
        return (min(start_id, end_id), max(start_id, end_id))
    except (ValueError, TypeError):
        return None

@app.route('/api/item-delivered', methods=['POST'])
def api_item_delivered():
    data = request.get_json(silent=True) or {}
    supplied_secret = request.headers.get("X-Api-Secret") or data.get("secret", "")
    if not _secret_ok(supplied_secret):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    try:
        msg_start = int(data.get("msg_start", 0))
        msg_end = int(data.get("msg_end", 0))
        delivered = {int(x) for x in data.get("delivered_message_ids", [])}
        user_id = str(int(data.get("user_id", 0)))
        event_id = str(data.get("event_id", ""))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid payload"}), 400
    if not event_id or not delivered or not user_id or msg_start <= 0 or msg_end < msg_start:
        return jsonify({"ok": False, "error": "incomplete delivery data"}), 400
    try:
        with open(DOWNLOAD_EVENTS_FILE, "r") as f:
            events = json.load(f)
        if not isinstance(events, list): events = []
    except (OSError, ValueError):
        events = []
    if event_id in events:
        return jsonify({"ok": True, "duplicate": True, "counted": 0})
    items = load_items()
    counted = 0
    for item in items:
        item_range = _item_message_range(item)
        if item_range and item_range == (msg_start, msg_end) and any(item_range[0] <= mid <= item_range[1] for mid in delivered):
            item["downloads"] = int(item.get("downloads", 0) or 0) + 1
            counted += 1
    if counted:
        save_items(items)
    events.append(event_id)
    events = events[-20000:]
    try:
        with open(DOWNLOAD_EVENTS_FILE, "w") as f:
            json.dump(events, f)
    except OSError as e:
        app.logger.error("Could not save item download event: %s", e)
    return jsonify({"ok": True, "counted": counted})

# ===== CUSTOM POSTS ROUTES =====
@app.route('/api/posts', methods=['GET'])
def api_posts():
    posts = load_posts()
    return jsonify({"ok": True, "posts": posts})

@app.route('/admin/add-post', methods=['POST'])
def admin_add_post():
    if not _secret_ok(request.form.get('secret')):
        return "Forbidden", 403
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    image = request.form.get('image', '').strip()
    link_text = request.form.get('link_text', '').strip()
    link_url = request.form.get('link_url', '').strip()
    if not title or not content:
        return "Title and Content are required", 400
    posts = load_posts()
    new_post = {
        "id": str(int(time.time() * 1000)),
        "title": title,
        "content": content,
        "image": image,
        "link_text": link_text,
        "link_url": link_url,
        "timestamp": time.time()
    }
    posts.insert(0, new_post)
    save_posts(posts)
    return redirect(url_for('home'))

@app.route('/admin/edit-post', methods=['POST'])
def admin_edit_post():
    if not _secret_ok(request.form.get('secret')):
        return "Forbidden", 403
    post_id = request.form.get('id')
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    link_text = request.form.get('link_text', '').strip()
    link_url = request.form.get('link_url', '').strip()
    posts = load_posts()
    for p in posts:
        if p.get('id') == post_id:
            p['title'] = title
            p['content'] = content
            p['link_text'] = link_text
            p['link_url'] = link_url
            break
    save_posts(posts)
    return redirect(url_for('home'))

@app.route('/admin/delete-post')
def admin_delete_post():
    if not _secret_ok(request.args.get('secret')):
        return "Forbidden", 403
    post_id = request.args.get('id')
    posts = load_posts()
    posts = [p for p in posts if p.get('id') != post_id]
    save_posts(posts)
    return redirect(url_for('home'))

@app.route('/admin/add-item', methods=['POST'])
def admin_add_item():
    if request.form.get('secret') != API_SECRET:
        return "Forbidden", 403
    items = load_items()
    new_item = {
        "id": str(int(time.time())),
        "title": request.form.get('title'),
        "desc": request.form.get('desc'),
        "meta": request.form.get('meta', '📄 File'),
        "image": request.form.get('image'),
        "category": request.form.get('category', 'Vault Files'),
        "downloads": 0,
        "pinned": True if request.form.get('pinned') == 'true' else False,
        "link": request.form.get('link')
    }
    items.insert(0, new_item)
    save_items(items)
    return redirect(url_for('home'))

@app.route('/admin/edit-item', methods=['POST'])
def admin_edit_item():
    if not _secret_ok(request.form.get('secret')):
        return "Forbidden", 403
    item_id = str(request.form.get('id', '')).strip()
    items = load_items()
    for item in items:
        if str(item.get('id')) == item_id:
            item['title'] = request.form.get('title', '').strip()
            item['desc'] = request.form.get('desc', '').strip()
            item['link'] = request.form.get('link', '').strip()
            break
    save_items(items)
    return redirect(url_for('home'))

@app.route('/admin/delete-item')
def admin_delete_item():
    if request.args.get('secret') != API_SECRET:
        return "Forbidden", 403
    item_id = request.args.get('id')
    items = load_items()
    items = [i for i in items if i['id'] != item_id]
    save_items(items)
    return redirect(url_for('home'))

@app.route('/admin/category', methods=['POST'])
def admin_manage_category():
    if not _secret_ok(request.form.get('secret')):
        return "Forbidden", 403
    categories = load_categories()
    action = request.form.get('action', '')
    name = request.form.get('name', '').strip()
    old_name = request.form.get('old_name', '').strip()
    if action == 'add':
        if not name:
            return "Category name is required", 400
        if any(x.casefold() == name.casefold() for x in categories):
            return "Category already exists", 400
        categories.append(name)
    elif action == 'rename':
        if not name or not old_name or old_name not in categories:
            return "Invalid category", 400
        if any(x.casefold() == name.casefold() and x != old_name for x in categories):
            return "Category already exists", 400
        categories[categories.index(old_name)] = name
        items = load_items()
        for item in items:
            if item.get('category') == old_name:
                item['category'] = name
        save_items(items)
    elif action == 'delete':
        if old_name not in categories:
            return "Category not found", 404
        if any(item.get('category') == old_name for item in load_items()):
            return "Move all items out of this category before deleting it", 400
        categories.remove(old_name)
        if not categories:
            return "At least one category must remain", 400
    else:
        return "Invalid action", 400
    save_categories(categories)
    return redirect(url_for('home'))

# ===== WHOT MULTIPLAYER SESSIONS =====
WHOT_DB = os.path.join(os.path.dirname(ITEMS_FILE), "whot_sessions.sqlite3")
_whot_db_lock = threading.RLock()
WHOT_SHAPES = ["CIRCLE", "TRIANGLE", "CROSS", "SQUARE", "STAR"]
WHOT_MAX = {"CIRCLE": 14, "TRIANGLE": 14, "CROSS": 14, "SQUARE": 14, "STAR": 8}
WHOT_SPECIAL_MAP = {
    1: "HOLD_ON",
    2: "PICK_TWO",
    5: "PICK_THREE",
    8: "SUSPENSION",
    14: "GENERAL_MARKET",
    20: "WHOT",
}

def _whot_db():
    conn = sqlite3.connect(WHOT_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS whot_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS whot_queue (user_id TEXT PRIMARY KEY, queued REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS sea_queue (user_id TEXT PRIMARY KEY, queued REAL NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS arcade_progress (user_id TEXT PRIMARY KEY, progress TEXT NOT NULL, updated REAL NOT NULL)")
    conn.commit()
    return conn

def _telegram_webapp_user():
    raw = request.headers.get("X-Telegram-Init-Data", "")
    if not raw or not BOT_TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(raw, keep_blank_values=True))
        supplied_hash = pairs.pop("hash", "")
        auth_date = int(pairs.get("auth_date", "0"))
        if not supplied_hash or time.time() - auth_date > 86400:
            return None
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied_hash):
            return None
        user = json.loads(pairs.get("user", "{}"))
        uid = str(int(user.get("id", 0)))
        return {"id": uid, "name": str(user.get("first_name", "Player"))[:40]}
    except Exception:
        return None

@app.route('/api/arcade/progress', methods=['GET', 'POST'])
def arcade_progress_api():
    user = _telegram_webapp_user()
    if not user:
        return jsonify({"ok": False, "error": "Open the Arcade inside Telegram to save progress."}), 401
    
    # Ensure backup file exists before accessing DB
    if not os.path.exists(ARCADE_BACKUP_FILE):
        download_backup_from_telegram()

    conn = _whot_db()
    if request.method == 'GET':
        row = conn.execute("SELECT progress FROM arcade_progress WHERE user_id=?", (user['id'],)).fetchone()
        conn.close()
        try:
            progress = json.loads(row['progress']) if row else {}
        except Exception:
            progress = {}
        
        # If DB is empty but we have a backup, restore it
        if not progress:
            backup_data = load_arcade_backup()
            if user['id'] in backup_data:
                progress = backup_data[user['id']]
                conn = _whot_db()
                conn.execute("INSERT OR REPLACE INTO arcade_progress(user_id,progress,updated) VALUES(?,?,?)",
                             (user['id'], json.dumps(progress, ensure_ascii=False), time.time()))
                conn.commit(); conn.close()
                
        return jsonify({"ok": True, "progress": progress})
    
    data = request.get_json(silent=True) or {}
    progress = data.get('progress')
    if not isinstance(progress, dict):
        conn.close()
        return jsonify({"ok": False, "error": "Invalid progress data."}), 400
    
    encoded = json.dumps(progress, ensure_ascii=False)
    if len(encoded) > 50000:
        conn.close()
        return jsonify({"ok": False, "error": "Progress data is too large."}), 413
    
    conn.execute("INSERT OR REPLACE INTO arcade_progress(user_id,progress,updated) VALUES(?,?,?)",
                 (user['id'], encoded, time.time()))
    conn.commit(); conn.close()
    
    # Also save to backup file
    backup_data = load_arcade_backup()
    backup_data[user['id']] = progress
    save_arcade_backup(backup_data)
    
    return jsonify({"ok": True, "saved": True})

def _whot_deck():
    cards = []
    for si, shape in enumerate(WHOT_SHAPES):
        for n in range(1, WHOT_MAX[shape] + 1):
            cards.append({"number": n, "shape": shape, "color": si})
    cards.append({"number": 20, "shape": "WHOT", "color": 5})
    random.shuffle(cards)
    return cards

def _whot_special(card):
    return WHOT_SPECIAL_MAP.get(card["number"])

def _whot_can_play(card, top, declared):
    if card["shape"] == "WHOT":
        return True
    if top["shape"] == "WHOT":
        return card["shape"] == declared
    if card["number"] == top["number"]:
        return True
    if card["shape"] == top["shape"]:
        return True
    return False

def _whot_new_state(code, first):
    deck = _whot_deck()
    top = deck.pop()
    while top["shape"] == "WHOT":
        deck.insert(0, top)
        top = deck.pop()
    return {"code": code, "players": [first], "names": {first["id"]: first["name"]},
            "hands": {first["id"]: [deck.pop() for _ in range(5)]}, "deck": deck,
            "top": top, "declared_shape": None, "turn": first["id"], "status": "waiting",
            "winner": None, "last_action": "Room created. Waiting for another player.",
            "updated": time.time()}

def _whot_save(conn, state):
    state["updated"] = time.time()
    conn.execute("INSERT OR REPLACE INTO whot_sessions(code,state,updated) VALUES(?,?,?)",
                 (state["code"], json.dumps(state, ensure_ascii=False), state["updated"]))
    conn.commit()

def _whot_get(conn, code):
    row = conn.execute("SELECT state FROM whot_sessions WHERE code=?", (code.upper(),)).fetchone()
    return json.loads(row["state"]) if row else None

def _whot_view(state, uid):
    if uid not in state.get("hands", {}): return None
    others = [p for p in state["players"] if p["id"] != uid]
    opponent = others[0] if others else None
    return {"code": state["code"], "status": state["status"], "hand": state["hands"].get(uid, []),
            "top": state["top"], "declared_shape": state.get("declared_shape"),
            "my_count": len(state["hands"].get(uid, [])),
            "opponent_count": len(state["hands"].get(opponent["id"], [])) if opponent else 0,
            "opponent_name": opponent["name"] if opponent else "Waiting for opponent",
            "turn": state["turn"], "my_turn": state["turn"] == uid,
            "deck_count": len(state["deck"]), "winner": state.get("winner"),
            "message": state.get("last_action", "")}

def _whot_auth_error():
    user = _telegram_webapp_user()
    if not user:
        return None, (jsonify({"ok": False, "error": "Open WHOT inside Telegram to authenticate."}), 401)
    return user, None

@app.route('/api/whot/create', methods=['POST'])
def whot_api_create():
    user, err = _whot_auth_error()
    if err: return err
    code = secrets.token_urlsafe(5).replace('-', '').replace(' ', '').upper()[:7]
    state = _whot_new_state(code, user)
    with _whot_db_lock:
        conn = _whot_db(); _whot_save(conn, state); conn.close()
    invite_url = quote(f"{request.host_url.rstrip('/')}/?whot={code}", safe="")
    return jsonify({"ok": True, "code": code, "share_url": f"https://t.me/share/url?url={invite_url}&text=Join%20my%20WHOT%20game"})

@app.route('/api/whot/join', methods=['POST'])
def whot_api_join():
    user, err = _whot_auth_error()
    if err: return err
    code = str((request.get_json(silent=True) or {}).get('code', '')).strip().upper()
    if not code: return jsonify({"ok": False, "error": "Enter a room code."}), 400
    with _whot_db_lock:
        conn = _whot_db(); state = _whot_get(conn, code)
        if not state: conn.close(); return jsonify({"ok": False, "error": "Room not found."}), 404
        if any(p['id'] == user['id'] for p in state['players']): pass
        elif len(state['players']) >= 2 or state['status'] != 'waiting':
            conn.close(); return jsonify({"ok": False, "error": "This room is already full."}), 409
        else:
            state['players'].append(user); state['names'][user['id']] = user['name']
            state['hands'][user['id']] = [state['deck'].pop() for _ in range(5)]
            state['status'] = 'playing'; state['turn'] = state['players'][0]['id']
            state['last_action'] = f"{user['name']} joined. {state['players'][0]['name']} starts."
            _whot_save(conn, state)
        view = _whot_view(state, user['id']); conn.close()
    return jsonify({"ok": True, "game": view})

@app.route('/api/whot/random', methods=['POST'])
def whot_api_random():
    user, err = _whot_auth_error()
    if err: return err
    with _whot_db_lock:
        conn = _whot_db()
        row = conn.execute("SELECT user_id FROM whot_queue WHERE user_id <>? ORDER BY queued LIMIT 1", (user['id'],)).fetchone()
        if row:
            other_id = row['user_id']; conn.execute("DELETE FROM whot_queue WHERE user_id IN (?,?)", (other_id, user['id']))
            other_row = conn.execute("SELECT state FROM whot_sessions WHERE json_extract(state,'$.players[0].id')=? AND json_extract(state,'$.status')='waiting' ORDER BY updated DESC LIMIT 1", (other_id,)).fetchone()
            state = json.loads(other_row['state']) if other_row else None
            if state:
                state['players'].append(user); state['names'][user['id']] = user['name']; state['hands'][user['id']] = [state['deck'].pop() for _ in range(5)]
                state['status']='playing'; state['turn']=state['players'][0]['id']; state['last_action']=f"Matched with {user['name']}."
                _whot_save(conn,state)
                view = _whot_view(state,user['id']); conn.close(); return jsonify({"ok":True, "matched":True, "game":view})
        code = secrets.token_urlsafe(5).replace('-', '').replace(' ', '').upper()[:7]
        state = _whot_new_state(code, user); _whot_save(conn,state)
        conn.execute("INSERT OR REPLACE INTO whot_queue(user_id,queued) VALUES(?,?)",(user['id'],time.time())); conn.commit(); conn.close()
    return jsonify({"ok":True, "matched":False, "code":code, "message": "Searching for an opponent… keep this screen open."})

@app.route('/api/whot/state', methods=['GET'])
def whot_api_state():
    user, err = _whot_auth_error()
    if err: return err
    code = request.args.get('code','').upper()
    with _whot_db_lock:
        conn=_whot_db(); state=_whot_get(conn,code); conn.close()
        if not state or user['id'] not in state.get('hands',{}): return jsonify({"ok":False,"error":"Game not found."}),404
    return jsonify({"ok":True,"game":_whot_view(state,user['id'])})

@app.route('/api/whot/move', methods=['POST'])
def whot_api_move():
    user, err = _whot_auth_error()
    if err: return err
    data = request.get_json(silent=True) or {}
    code = str(data.get('code', '')).upper()
    action = data.get('action')
    index = data.get('index')
    declared = data.get('declared_shape')
    with _whot_db_lock:
        conn = _whot_db(); state = _whot_get(conn, code)
        if not state or user['id'] not in state.get('hands', {}):
            conn.close(); return jsonify({"ok": False, "error": "Game not found."}), 404
        if state['status'] != 'playing' or state['turn'] != user['id']:
            conn.close(); return jsonify({"ok": False, "error": "Not your turn."}), 409
        hand = state['hands'][user['id']]
        opponent_id = next(p['id'] for p in state['players'] if p['id'] != user['id'])
        opp_hand = state['hands'][opponent_id]
        if action == 'play':
            try:
                card = hand[int(index)]
            except (ValueError, TypeError, IndexError):
                conn.close(); return jsonify({"ok": False, "error": "Invalid card."}), 400
            if not _whot_can_play(card, state['top'], state.get('declared_shape')):
                conn.close(); return jsonify({"ok": False, "error": "Match the number or shape."}), 400
            if card['shape'] == 'WHOT':
                if declared not in WHOT_SHAPES:
                    conn.close(); return jsonify({"ok": False, "error": "Declare a shape for WHOT."}), 400
                state['declared_shape'] = declared
            elif state['top']['shape'] == 'WHOT':
                state['declared_shape'] = None
            state['top'] = hand.pop(int(index))
            state['last_action'] = f"{user['name']} played a card."
            if not hand:
                state['winner'] = user['id']; state['status'] = 'finished'
                state['last_action'] = f"{user['name']} won!"
            else:
                effect = _whot_special(state['top'])
                if effect in ('PICK_TWO', 'PICK_THREE', 'GENERAL_MARKET'):
                    draw_count = {'PICK_TWO': 2, 'PICK_THREE': 3, 'GENERAL_MARKET': 1}[effect]
                    for _ in range(draw_count):
                        if state['deck']:
                            opp_hand.append(state['deck'].pop())
                    state['last_action'] = f"{user['name']} played {state['top']['number']} ({effect}). {draw_count} drawn and skipped."
                elif effect in ('HOLD_ON', 'SUSPENSION'):
                    state['last_action'] = f"{user['name']} played {state['top']['number']} ({effect}). Opponent skipped."
                else:
                    state['turn'] = opponent_id
                    state['last_action'] = f"{user['name']} played a card."
        elif action == 'draw':
            if not state['deck']:
                conn.close(); return jsonify({"ok": False, "error": "Draw pile empty."}), 409
            drawn = state['deck'].pop()
            hand.append(drawn)
            state['last_action'] = f"{user['name']} drew a card."
            if not _whot_can_play(drawn, state['top'], state.get('declared_shape')):
                state['turn'] = opponent_id
        else:
            conn.close(); return jsonify({"ok": False, "error": "Unknown action."}), 400
        _whot_save(conn, state)
        view = _whot_view(state, user['id']); conn.close()
    return jsonify({"ok": True, "game": view})

# ===== SEA BATTLE MULTIPLAYER =====
SEA_W, SEA_H = 9, 7
SEA_FLEET = [5, 4, 3, 3, 2]

def _sea_new_state(code, first):
    return {"code": code, "players": [first], "names": {first["id"]: first["name"]},
            "ships": {first["id"]: []}, "hits": {first["id"]: []}, "misses": {first["id"]: []},
            "turn": first["id"], "status": "waiting", "winner": None,
            "last_action": "Room created. Waiting for another player.", "updated": time.time()}

def _sea_save(conn, state):
    state["updated"] = time.time()
    conn.execute("INSERT OR REPLACE INTO sea_sessions(code,state,updated) VALUES(?,?,?)",
                 (state["code"], json.dumps(state, ensure_ascii=False), state["updated"]))
    conn.commit()

def _sea_get(conn, code):
    row = conn.execute("SELECT state FROM sea_sessions WHERE code=?", (code.upper(),)).fetchone()
    return json.loads(row["state"]) if row else None

def _sea_view(state, uid):
    if uid not in state.get("ships", {}): return None
    other = next((p for p in state["players"] if p["id"] != uid), None)
    opponent_id = other["id"] if other else None
    own_ships = state["ships"].get(uid, [])
    own_hits = state["hits"].get(uid, [])
    own_misses = state["misses"].get(uid, [])
    fired_hits = state.get("hits", {}).get(opponent_id, []) if opponent_id else []
    fired_misses = state.get("misses", {}).get(opponent_id, []) if opponent_id else []
    ready = len(own_ships) == len(SEA_FLEET)
    opponent_ships = state.get("ships", {}).get(opponent_id, []) if opponent_id else []
    opponent_hit_cells = set(state.get("hits", {}).get(opponent_id, [])) if opponent_id else set()
    sunk_opponent_ships = [ship for ship in opponent_ships if all(f"{r},{c}" in opponent_hit_cells for r,c in ship)]
    reveal_fleet = state.get("status") == "finished"
    return {"code": state["code"], "status": state["status"], "placed": ready,
            "my_ships": own_ships, "my_hits": own_hits, "my_misses": own_misses,
            "shots_hit": fired_hits, "shots_miss": fired_misses,
            "sunk_opponent_ships": sunk_opponent_ships,
            "opponent_ships_revealed": opponent_ships if reveal_fleet else [],
            "opponent_name": other["name"] if other else "Waiting for opponent",
            "opponent_ready": bool(opponent_id and len(state["ships"].get(opponent_id, [])) == len(SEA_FLEET)),
            "my_turn": state.get("turn") == uid, "winner": state.get("winner"),
            "message": state.get("last_action", "")}

def _sea_auth_error():
    user = _telegram_webapp_user()
    if not user:
        return None, (jsonify({"ok": False, "error": "Open Sea Battle inside Telegram to authenticate."}), 401)
    return user, None

def _sea_validate_ship(cells, existing):
    if not isinstance(cells, list) or len(cells) not in SEA_FLEET: return False
    try: coords = [(int(x[0]), int(x[1])) for x in cells]
    except (TypeError, ValueError, IndexError): return False
    if len(set(coords)) != len(coords): return False
    if any(r < 0 or r >= SEA_H or c < 0 or c >= SEA_W for r, c in coords): return False
    rows = {r for r, c in coords}; cols = {c for r, c in coords}
    if len(rows) == 1:
        ordered = sorted(c for r, c in coords)
        if ordered != list(range(ordered[0], ordered[0] + len(ordered))): return False
    elif len(cols) == 1:
        ordered = sorted(r for r, c in coords)
        if ordered != list(range(ordered[0], ordered[0] + len(ordered))): return False
    else: return False
    occupied = {(r, c) for ship in existing for r, c in ship}
    return not any(pos in occupied for pos in coords)

@app.route('/api/sea/cancel', methods=['POST'])
def sea_api_cancel():
    user, err = _sea_auth_error()
    if err: return err
    code = str((request.get_json(silent=True) or {}).get('code', '')).strip().upper()
    with _whot_db_lock:
        conn = _whot_db()
        conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sea_queue (user_id TEXT PRIMARY KEY, queued REAL NOT NULL)")
        state = _sea_get(conn, code)
        if state and any(p.get('id') == user['id'] for p in state.get('players', [])):
            state['status'] = 'cancelled'
            state['last_action'] = f"{user['name']} left the match."
            _sea_save(conn, state)
            conn.execute("DELETE FROM sea_queue WHERE user_id=?", (user['id'],))
            conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route('/api/sea/create', methods=['POST'])
def sea_api_create():
    user, err = _sea_auth_error()
    if err: return err
    code = secrets.token_urlsafe(5).replace('-', '').replace(' ', '').upper()[:7]
    state = _sea_new_state(code, user)
    with _whot_db_lock:
        conn = _whot_db()
        conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sea_queue (user_id TEXT PRIMARY KEY, queued REAL NOT NULL)")
        _sea_save(conn, state); conn.close()
    invite = quote(f"{request.host_url.rstrip('/')}/?sea={code}", safe="")
    return jsonify({"ok": True, "code": code, "share_url": f"https://t.me/share/url?url={invite}&text=Join%20my%20Sea%20Battle%20game"})

@app.route('/api/sea/join', methods=['POST'])
def sea_api_join():
    user, err = _sea_auth_error()
    if err: return err
    code = str((request.get_json(silent=True) or {}).get('code', '')).strip().upper()
    with _whot_db_lock:
        conn = _whot_db(); conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        state = _sea_get(conn, code)
        if not state or state.get('status') == 'cancelled': conn.close(); return jsonify({"ok": False, "error": "This room has been cancelled."}), 404
        if any(p['id'] == user['id'] for p in state['players']): pass
        elif len(state['players']) >= 2 or state['status'] != 'waiting': conn.close(); return jsonify({"ok": False, "error": "This room is already full."}), 409
        else:
            state['players'].append(user); state['names'][user['id']] = user['name']
            state['ships'][user['id']] = []; state['hits'][user['id']] = []; state['misses'][user['id']] = []
            state['status'] = 'placing'; state['last_action'] = f"{user['name']} joined. Both players can place their fleets."
            _sea_save(conn, state)
        view = _sea_view(state, user['id']); conn.close()
    return jsonify({"ok": True, "game": view})

@app.route('/api/sea/random', methods=['POST'])
def sea_api_random():
    user, err = _sea_auth_error()
    if err: return err
    with _whot_db_lock:
        conn = _whot_db(); conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sea_queue (user_id TEXT PRIMARY KEY, queued REAL NOT NULL)")
        row = conn.execute("SELECT user_id FROM sea_queue WHERE user_id <>? ORDER BY queued LIMIT 1", (user['id'],)).fetchone()
        state = None
        if row:
            other_id = row['user_id']
            other_row = conn.execute("SELECT state FROM sea_sessions WHERE json_extract(state,'$.players[0].id')=? AND json_extract(state,'$.status')='waiting' ORDER BY updated DESC LIMIT 1", (other_id,)).fetchone()
            if other_row:
                state = json.loads(other_row['state']); conn.execute("DELETE FROM sea_queue WHERE user_id=?", (other_id,))
                state['players'].append(user); state['names'][user['id']] = user['name']; state['ships'][user['id']] = []; state['hits'][user['id']] = []; state['misses'][user['id']] = []
                state['status'] = 'placing'; state['last_action'] = f"Matched with {user['name']}. Place your fleets."
                _sea_save(conn, state)
                view = _sea_view(state, user['id']); conn.close(); return jsonify({"ok": True, "matched": True, "code": state['code'], "game": view})
        code = secrets.token_urlsafe(5).replace('-', '').replace(' ', '').upper()[:7]
        state = _sea_new_state(code, user); _sea_save(conn, state)
        conn.execute("INSERT OR REPLACE INTO sea_queue(user_id,queued) VALUES(?,?)", (user['id'], time.time())); conn.commit(); conn.close()
    return jsonify({"ok": True, "matched": False, "code": code, "message": "Searching for an opponent… keep this screen open."})

@app.route('/api/sea/place', methods=['POST'])
def sea_api_place():
    user, err = _sea_auth_error()
    if err: return err
    data = request.get_json(silent=True) or {}; code = str(data.get('code', '')).upper(); ships = data.get('ships')
    if not isinstance(ships, list) or len(ships) != len(SEA_FLEET): return jsonify({"ok": False, "error": "Place all five ships first."}), 400
    with _whot_db_lock:
        conn = _whot_db(); conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        state = _sea_get(conn, code)
        if not state or user['id'] not in state['ships']: conn.close(); return jsonify({"ok": False, "error": "Game not found."}), 404
        if state['status'] not in ('placing', 'waiting'): conn.close(); return jsonify({"ok": False, "error": "Fleet placement is closed."}), 409
        clean=[]; occupied=[]
        for i, ship in enumerate(ships):
            cells = ship.get('cells') if isinstance(ship, dict) else ship
            if not _sea_validate_ship(cells, clean) or len(cells) != SEA_FLEET[i]: conn.close(); return jsonify({"ok": False, "error": f"Invalid placement for ship {i+1}."}), 400
            clean.append([[int(x[0]), int(x[1])] for x in cells])
        state['ships'][user['id']] = clean
        ready = all(len(state['ships'].get(p['id'], [])) == len(SEA_FLEET) for p in state['players'])
        if ready:
            state['status'] = 'playing'; state['turn'] = state['players'][0]['id']; state['last_action'] = 'Both fleets are ready. First player starts.'
        else:
            state['status'] = 'waiting' if len(state['players']) < 2 else 'placing'
            state['last_action'] = f"{user['name']} placed their fleet. Waiting for the other player."
        _sea_save(conn, state); view = _sea_view(state, user['id']); conn.close()
    return jsonify({"ok": True, "game": view})

@app.route('/api/sea/state', methods=['GET'])
def sea_api_state():
    user, err = _sea_auth_error()
    if err: return err
    code = request.args.get('code', '').upper()
    with _whot_db_lock:
        conn = _whot_db(); conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        state = _sea_get(conn, code); conn.close()
        if not state or user['id'] not in state.get('ships', {}): return jsonify({"ok": False, "error": "This Sea Battle room is no longer active."}), 404
    return jsonify({"ok": True, "game": _sea_view(state, user['id'])})

@app.route('/api/sea/fire', methods=['POST'])
def sea_api_fire():
    user, err = _sea_auth_error()
    if err: return err
    data = request.get_json(silent=True) or {}; code = str(data.get('code', '')).upper()
    try: r, c = int(data.get('row')), int(data.get('col'))
    except (TypeError, ValueError): return jsonify({"ok": False, "error": "Invalid target."}), 400
    if not (0 <= r < SEA_H and 0 <= c < SEA_W): return jsonify({"ok": False, "error": "Target is outside the ocean."}), 400
    key = f"{r},{c}"
    with _whot_db_lock:
        conn = _whot_db(); conn.execute("CREATE TABLE IF NOT EXISTS sea_sessions (code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL)")
        state = _sea_get(conn, code)
        if not state or user['id'] not in state.get('ships', {}): conn.close(); return jsonify({"ok": False, "error": "Game not found."}), 404
        if state['status'] != 'playing' or state['turn'] != user['id']: conn.close(); return jsonify({"ok": False, "error": "It is not your turn."}), 409
        opponent = next(p['id'] for p in state['players'] if p['id'] != user['id'])
        shots = state['hits'][opponent] + state['misses'][opponent]
        if key in shots: conn.close(); return jsonify({"ok": False, "error": "You already fired at that cell."}), 409
        enemy_cells = {(y, x) for ship in state['ships'][opponent] for y, x in ship}
        if (r, c) in enemy_cells:
            state['hits'][opponent].append(key); result = 'hit'
        else:
            state['misses'][opponent].append(key); result = 'miss'
        remaining = enemy_cells - {(int(v.split(',')[0]), int(v.split(',')[1])) for v in state['hits'][opponent]}
        if not remaining:
            state['status'] = 'finished'; state['winner'] = user['id']; state['last_action'] = f"{user['name']} destroyed the enemy fleet!"
        else:
            state['turn'] = opponent; state['last_action'] = f"{user['name']} fired: {result.upper()}."
        _sea_save(conn, state); view = _sea_view(state, user['id']); view['last_shot'] = result; conn.close()
    return jsonify({"ok": True, "game": view})

@app.route('/')
def home():
    reset_legacy_download_counts_once()
    items = load_items()
    response = app.make_response(render_template_string(
        HUB_TEMPLATE, items=items, categories=load_categories(),
        admin_id=ADMIN_ID, secret=API_SECRET, posts=load_posts()
    ))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response

@app.before_request
def _repair_text_once():
    if not _text_repair_done:
        repair_data_files()

@app.after_request
def _force_utf8(response):
    ctype = response.headers.get("Content-Type", "")
    if ctype.startswith("text/") and "charset" not in ctype.lower():
        response.headers["Content-Type"] = ctype + "; charset=utf-8"
    return response

try:
    repair_data_files()
except Exception as _e:
    print("Text repair at start failed: " + str(_e))

if __name__ == "__main__":
    app.run(debug=True)