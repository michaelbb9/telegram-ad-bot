# =====================================================================
# extras.py  -  add-on module for the Michaelbbcvault bot
#
# Features
#   1. Download progress card (thumbnail + title + quality + progress bar)
#   2. Post details in every caption (author, username, region, views,
#      likes, comments, shares, description) when the site provides them
#   3. YouTube quality picker
#   4. Per-site limits (max minutes / max MB / heavy MB / heavy cost),
#      configurable by the admin ("📏 Limits" button)
#   5. Heavy downloads cost extra credits, with a "watch ads" refill prompt
#   6. Forced channel membership, checked on EVERY use, configurable by the
#      admin ("📢 Required Channels" button)
#   7. "Change Batch Channel" now has a Cancel button and no longer traps links
#
# It is wired in with init(globals()) and register(app); see the patch notes.
# Every feature fails OPEN: if something here breaks, users are not locked out.
# =====================================================================
import asyncio
import contextvars
import logging
import os
import re
import shutil
import time
import types

import yt_dlp
import yt_dlp.utils
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
                      KeyboardButton, ReplyKeyboardMarkup, Update)
from telegram.ext import (ApplicationHandlerStop, CallbackQueryHandler, CommandHandler,
                          MessageHandler, TypeHandler, filters)

logger = logging.getLogger("extras")
G = {}                                   # main program's globals (filled by init)

# ---------------------------------------------------------------------
# per-request context (set by the download wrapper, read in worker threads)
# ---------------------------------------------------------------------
CTX_REPORTER = contextvars.ContextVar("extras_reporter", default=None)
CTX_QUALITY = contextvars.ContextVar("extras_quality", default=None)   # None=auto, 0=lowest, else max height

DEFAULT_LIMITS = {"max_minutes": 10, "max_mb": 200, "heavy_mb": 100, "heavy_cost": 3}
LIMIT_LABELS = {"max_minutes": "⏱ Max minutes", "max_mb": "📦 Max size (MB)",
                "heavy_mb": "⚡ Heavy from (MB)", "heavy_cost": "🎟 Heavy cost (credits)"}
LIMIT_RANGES = {"max_minutes": (1, 600), "max_mb": (10, 2000), "heavy_mb": (1, 2000), "heavy_cost": (1, 20)}
SITES = [("default", "Default (all other sites)"), ("youtube", "YouTube"), ("tiktok", "TikTok"),
         ("instagram", "Instagram"), ("facebook", "Facebook"), ("twitter", "X / Twitter"),
         ("reddit", "Reddit"), ("pinterest", "Pinterest"), ("threads", "Threads"),
         ("vimeo", "Vimeo"), ("dailymotion", "Dailymotion"), ("twitch", "Twitch")]
SITE_DOMAINS = {"youtube": ("youtube.com", "youtu.be"), "tiktok": ("tiktok.com",),
                "instagram": ("instagram.com", "instagr.am"), "facebook": ("facebook.com", "fb.watch", "fb.com"),
                "twitter": ("twitter.com", "x.com", "t.co"), "reddit": ("reddit.com", "redd.it"),
                "pinterest": ("pinterest.", "pin.it"), "threads": ("threads.net", "threads.com"),
                "vimeo": ("vimeo.com",), "dailymotion": ("dailymotion.com", "dai.ly"), "twitch": ("twitch.tv",)}
CANCEL_WORDS = ("❌ Cancel", "/cancel", "Cancel", "cancel")
YT_ID_RE = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/|embed/))([A-Za-z0-9_-]{11})')


# =====================================================================
# 1. settings helpers
# =====================================================================
def _admin():
    return G["ADMIN_ID"]


def _cfg():
    try:
        return G["load_json_file"](G["CONFIG_FILE"]) or {}
    except Exception:
        return {}


def _save_cfg(cfg):
    G["save_json_file"](G["CONFIG_FILE"], cfg)


def site_of(url):
    low = (url or "").lower()
    for site, doms in SITE_DOMAINS.items():
        if any(d in low for d in doms):
            return site
    return "default"


def get_limits(site):
    lim = dict(DEFAULT_LIMITS)
    stored = _cfg().get("site_limits", {})
    lim.update(stored.get("default", {}))
    if site != "default":
        lim.update(stored.get(site, {}))
    return {k: int(lim[k]) for k in DEFAULT_LIMITS}


def set_limit(site, field, value):
    cfg = _cfg()
    cfg.setdefault("site_limits", {}).setdefault(site, {})[field] = int(value)
    _save_cfg(cfg)


def reset_site_limits(site):
    cfg = _cfg()
    cfg.setdefault("site_limits", {}).pop(site, None)
    _save_cfg(cfg)


def required_channels():
    return list(_cfg().get("required_channels", []))


def save_required_channels(chans):
    cfg = _cfg()
    cfg["required_channels"] = chans
    _save_cfg(cfg)


# =====================================================================
# 2. probing a link (title, duration, formats, thumbnails, stats)
# =====================================================================
_PROBE_CACHE = {}


def _cookiefile(url):
    low = url.lower()
    if "tiktok.com" in low and os.path.exists("tiktok_cookies.txt"):
        return "tiktok_cookies.txt"
    if os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None


def _probe_sync(url):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
            "socket_timeout": 15, "http_headers": {"User-Agent": "Mozilla/5.0"}}
    if G.get("PROXY_URL"):
        opts["proxy"] = G["PROXY_URL"]
    cf = _cookiefile(url)
    if cf:
        opts["cookiefile"] = cf
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        info = entries[0] if entries else None
    return info


async def probe(url):
    """Metadata for a link, or None. Cached for 10 minutes."""
    now = time.time()
    hit = _PROBE_CACHE.get(url)
    if hit and now - hit[0] < 600:
        return hit[1]
    try:
        info = await asyncio.wait_for(asyncio.to_thread(_probe_sync, url), timeout=30)
    except Exception as e:
        logger.info(f"probe failed for {url[:60]}: {type(e).__name__}")
        return None
    if info:
        if len(_PROBE_CACHE) > 200:
            _PROBE_CACHE.clear()
        _PROBE_CACHE[url] = (now, info)
    return info


def _fsize(f, duration):
    s = f.get("filesize") or f.get("filesize_approx")
    if not s and f.get("tbr") and duration:
        s = f["tbr"] * 1000 / 8 * duration
    return int(s) if s else None


_CODEC_RANK = {"av01": 4, "vp09": 3, "vp9": 3, "hev1": 2, "hvc1": 2, "avc1": 1}


def _vcodec_rank(f):
    return _CODEC_RANK.get((f.get("vcodec") or "")[:4], 0)


def heights_available(info):
    hs = sorted({f["height"] for f in (info.get("formats") or [])
                 if f.get("height") and f.get("vcodec") not in (None, "none")})
    return hs


def est_size(info, max_height=None):
    """Estimated bytes to download at the best quality <= max_height (None = best)."""
    if not info:
        return None
    fmts = info.get("formats") or []
    dur = info.get("duration") or 0
    vids = [f for f in fmts if f.get("vcodec") not in (None, "none") and f.get("height")
            and (max_height is None or max_height <= 0 or f["height"] <= max_height)]
    if max_height == 0:                      # lowest quality
        vids = [f for f in fmts if f.get("vcodec") not in (None, "none") and f.get("height")]
        if vids:
            lowest = min(f["height"] for f in vids)
            vids = [f for f in vids if f["height"] == lowest]
    if not vids:
        # single-file sites that do not list heights
        f = info.get("requested_formats") or [info]
        sizes = [_fsize(x, dur) for x in f]
        return sum(sizes) if sizes and all(sizes) else None
    top = max(f["height"] for f in vids) if max_height != 0 else vids[0]["height"]
    cands = [f for f in vids if f["height"] == top]
    best = max(cands, key=lambda f: (_vcodec_rank(f), f.get("tbr") or 0))
    size = _fsize(best, dur)
    if best.get("acodec") in (None, "none"):
        auds = [f for f in fmts if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]
        if auds:
            a = max(auds, key=lambda f: f.get("abr") or f.get("tbr") or 0)
            sa = _fsize(a, dur)
            if size is None and sa is None:
                return None
            size = (size or 0) + (sa or 0)
    return size


def mb(n):
    return None if n is None else n / (1024 * 1024)


def fmt_mb(n):
    return "?" if n is None else (f"{mb(n):.0f}MB" if mb(n) >= 10 else f"{mb(n):.1f}MB")


def parse_size_mb(s):
    m = re.search(r"([\d.]+)\s*MB", str(s or ""), re.I)
    return float(m.group(1)) if m else None


# =====================================================================
# 3. post details for captions
# =====================================================================
def _clean(s, limit=None):
    s = re.sub(r"[*_`\[\]]", "", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[:limit - 1].rstrip() + "…"
    return s


def _num(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return None


def _username(info):
    uid = str(info.get("uploader_id") or "")
    if uid and not uid.isdigit():
        return uid.lstrip("@")
    url = info.get("uploader_url") or info.get("channel_url") or ""
    m = re.search(r"/@?([A-Za-z0-9._-]+)/?$", url.split("?")[0])
    if m and m.group(1).lower() not in ("channel", "user", "c"):
        return m.group(1)
    up = info.get("uploader")
    if up and re.fullmatch(r"[A-Za-z0-9._]+", str(up)):
        return up
    return None


def build_meta(info, max_len=640):
    """Return the details block (without leading newlines) or ''."""
    if not info:
        return ""
    lines = []
    author = info.get("creators") and ", ".join(info["creators"][:2]) or info.get("channel") or info.get("uploader") or info.get("creator")
    if author:
        lines.append(f"🎥 Author : {_clean(author, 60)}")
    uname = _username(info)
    if uname:
        lines.append(f"👤 Username : @{_clean(uname, 40)}")
    region = info.get("region") or info.get("country") or info.get("location")
    if region:
        lines.append(f"🌍 Region : {_clean(region, 40)}")
    for key, label in (("view_count", "▶️ Views"), ("like_count", "👍 Likes"),
                       ("comment_count", "💬 Comments"), ("repost_count", "🔗 Shares")):
        v = _num(info.get(key))
        if v is not None:
            lines.append(f"{label} : {v}")
    desc = info.get("description") or info.get("title")
    head = "\n".join(lines)
    if desc:
        room = max(60, max_len - len(head) - 20)
        lines.append(f"📝 Description : {_clean(desc, room)}")
    return "\n".join(lines)[:max_len]


# =====================================================================
# 4. policy: limits, credits, ads
# =====================================================================
def evaluate(site, duration_s, size_bytes, is_admin, credits_left):
    """Return dict(action=allow|block|ads, cost=int, reason=str)."""
    lim = get_limits(site)
    size_mb = mb(size_bytes) if size_bytes else None
    minutes = (duration_s or 0) / 60.0
    over_len = bool(duration_s) and minutes > lim["max_minutes"]
    over_size = size_mb is not None and size_mb > lim["max_mb"]
    heavy = over_len or (size_mb is not None and size_mb > lim["heavy_mb"])
    cost = lim["heavy_cost"] if heavy else 1
    if is_admin:
        return {"action": "allow", "cost": 1, "reason": "admin", "heavy": heavy, "limits": lim}
    if over_size:
        return {"action": "block", "cost": cost, "reason": "size", "heavy": heavy, "limits": lim}
    if credits_left is not None and credits_left < cost:
        return {"action": "ads", "cost": cost, "reason": "credits", "heavy": heavy, "limits": lim}
    return {"action": "allow", "cost": cost, "reason": "heavy" if heavy else "normal", "heavy": heavy, "limits": lim}


async def credits_left(user_id):
    def _get():
        try:
            prof = (G["load_tokens"]() or {}).get(str(user_id), {})
            return int(prof.get("downloads_left", G["get_free_amount"]()))
        except Exception as e:
            logger.warning(f"credits lookup failed: {e}")
            return None
    return await asyncio.to_thread(_get)


async def charge(user_id, cost):
    for _ in range(max(1, int(cost))):
        try:
            await asyncio.to_thread(_ORIG["deduct_download_counter"], user_id, False)
        except Exception as e:
            logger.warning(f"deduct failed: {e}")


async def send_refill_prompt(bot, chat_id, user_id, t, url, need, have):
    """Same ad flow as the normal 'limit reached' screen, with a clearer message."""
    g = G
    try:
        g["pending_single_links"][f"retry_{user_id}"] = url
        head = (f"⚡ **This download needs {need} credits** and you have {have}.\n"
                f"Watch an ad to refill, then I'll continue automatically. 👇")
        network = g["get_global_ab_network"](user_id)
        if network == "monetag":
            kb = await asyncio.to_thread(g["adsgram_keyboard"], user_id, "wall", 0, 0)
            if kb:
                await bot.send_message(chat_id=chat_id, text=head, reply_markup=kb, parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=chat_id, text="⚠️ Ad server busy, try again in a moment.")
            return
        try:
            await bot.forward_message(chat_id=chat_id, from_chat_id=g["PRIVATE_CHANNEL_ID"],
                                      message_id=g["TUTORIAL_MESSAGE_ID"])
            await asyncio.sleep(0.2)
        except Exception:
            pass
        bridge = f"{g['BRIDGE_URL']}?user={user_id}&start_msg=0&end_msg=0"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 Open Link & Watch Timer ⏰ 20s +1", url=bridge)],
            [InlineKeyboardButton("📢 Join Public Channel 💜", url=g["PUBLIC_CHANNEL_URL"])],
            [InlineKeyboardButton("💜 Check & Get Files ✅ +1", callback_data="verify_user")]])
        await bot.send_message(chat_id=chat_id, text=head + g.get("ADSTERRA_USER_GUIDE", ""),
                               reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"refill prompt failed: {e}")
        await bot.send_message(chat_id=chat_id, text=f"⚡ This download needs {need} credits and you have {have}. "
                                                   f"Please refill with the ad button in the menu.")


# =====================================================================
# 5. progress card
# =====================================================================
class Reporter:
    def __init__(self, bot, chat_id, msg, kind, loop, title, quality, size_label, extra_line=""):
        self.bot, self.chat_id, self.msg, self.kind, self.loop = bot, chat_id, msg, kind, loop
        self.title, self.quality, self.size_label, self.extra = title, quality, size_label, extra_line
        self.pct, self.last, self.busy = 0, 0.0, False
        self.finished, self.seen = 0, set()

    def reset(self):
        self.finished, self.seen = 0, set()

    def text(self, pct, stage="🔄 Preparing the file:"):
        head = f"🎬 {self.title}\n\n🎞 {self.quality}"
        if self.size_label:
            head += f"   📦 {self.size_label}"
        if pct is None:
            tail = f"\n\n{stage}"
        else:
            filled = max(0, min(10, int(pct / 10)))
            bar = "■" * filled + "□" * (10 - filled)
            tail = f"\n\n{stage}\n{bar} ≈{pct}%"
        return head + tail + (f"\n\n{self.extra}" if self.extra else "")

    def hook(self, d):                       # runs inside yt-dlp's worker thread
        try:
            st = d.get("status")
            info = d.get("info_dict") or {}
            n = len(info.get("requested_formats") or []) or 1
            if st == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                frac = min(1.0, (d.get("downloaded_bytes") or 0) / total) if total else 0.0
                overall = (self.finished + frac) / n
            elif st == "finished":
                fn = d.get("filename") or str(len(self.seen))
                if fn not in self.seen:
                    self.seen.add(fn)
                    self.finished += 1
                overall = min(1.0, self.finished / n)
            else:
                return
            self.push(int(min(99, max(0, overall * 100))))
        except Exception:
            pass

    def push(self, pct):
        now = time.time()
        if self.busy or pct - self.pct < 2 or now - self.last < 3:
            return
        self.pct, self.last = pct, now
        try:
            asyncio.run_coroutine_threadsafe(self._edit(self.text(pct)), self.loop)
        except Exception:
            pass

    async def _edit(self, text):
        self.busy = True
        try:
            await edit_status(self.bot, self.chat_id, self.msg, self.kind, text)
        finally:
            self.busy = False

    async def stage(self, text):
        await edit_status(self.bot, self.chat_id, self.msg, self.kind, self.text(None, text))


async def edit_status(bot, chat_id, msg, kind, text):
    try:
        if kind == "photo":
            await bot.edit_message_caption(chat_id=chat_id, message_id=msg.message_id, caption=text[:1000])
        else:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=text[:4000])
    except Exception:
        pass


def thumb_candidates(info):
    urls = []
    for th in sorted((info or {}).get("thumbnails") or [], key=lambda x: (x.get("preference") or 0, x.get("height") or 0), reverse=True):
        u = th.get("url") or ""
        if u.split("?")[0].lower().endswith((".jpg", ".jpeg", ".png")) and u not in urls:
            urls.append(u)
    t = (info or {}).get("thumbnail")
    if t and t not in urls:
        urls.append(t)
    return urls[:3]


async def start_status(bot, chat_id, user_id, info, quality_label, size_label, ckey):
    """Send the progress card. Returns (message, reporter)."""
    title = _clean((info or {}).get("title") or "Your download", 80)
    extra = f"🆔 {ckey}" if user_id == _admin() else ""
    rep = Reporter(bot, chat_id, None, "text", asyncio.get_running_loop(), title, quality_label, size_label, extra)
    text = rep.text(0)
    msg, kind = None, "text"
    for u in thumb_candidates(info):
        try:
            msg = await bot.send_photo(chat_id=chat_id, photo=u, caption=text[:1000])
            kind = "photo"
            break
        except Exception:
            continue
    if msg is None:
        msg = await bot.send_message(chat_id=chat_id, text=text)
    rep.msg, rep.kind = msg, kind
    return msg, rep


async def show_error(bot, chat_id, status_msg, text, kb=None):
    """Replace the progress card with an error. (Editing a message can not attach a reply keyboard,
    so delete + send.)"""
    try:
        if status_msg is not None:
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
    except Exception:
        pass
    try:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    except Exception as e:
        logger.error(f"show_error failed: {e}")


# =====================================================================
# 6. the new download flow (replaces cached_download_and_send)
# =====================================================================
_ORIG = {}
QUALITY_MEMORY = {}          # (user_id, url) -> (cap, timestamp): survives the "watch an ad" retry


class LimitHit(Exception):
    def __init__(self, kind, need=0, have=0, size_mb=0.0, limit_mb=0):
        super().__init__(f"LIMIT_{kind}")
        self.kind, self.need, self.have, self.size_mb, self.limit_mb = kind, need, have, size_mb, limit_mb


def _remember_quality(user_id, url, cap):
    QUALITY_MEMORY[(user_id, url)] = (cap, time.time())
    if len(QUALITY_MEMORY) > 500:
        QUALITY_MEMORY.clear()


def _recall_quality(user_id, url):
    hit = QUALITY_MEMORY.get((user_id, url))
    if hit and time.time() - hit[1] < 1800:
        return hit[0]
    return None


def _quality_order(dl_type, cap):
    if dl_type == "audio":
        return ["audio"]
    if dl_type != "video":
        return ["original"]
    order = ["1080p", "720p", "480p", "360p", "worst"]
    if cap is None:
        return order
    if cap == 0:
        return ["worst"]
    return [q for q in order if q != "worst" and int(q[:-1]) <= cap]


def _plan_estimate(info, cap, is_admin, site):
    """Return (estimated_bytes_or_None, label) for what the engine will most likely download."""
    if not info:
        return None, "Auto"
    if site == "youtube" and heights_available(info):
        lim = get_limits(site)
        if cap is not None:
            e = est_size(info, cap)
            hs = [h for h in heights_available(info) if (cap == 0 or h <= cap)]
            label = f"{(min(heights_available(info)) if cap == 0 else (max(hs) if hs else cap))}p"
            return e, label
        last = (None, "Auto")
        for H in (1080, 720, 480, 360, 0):
            e = est_size(info, H)
            hs = [h for h in heights_available(info) if (H == 0 or h <= H)]
            label = f"{(min(heights_available(info)) if H == 0 else (max(hs) if hs else H))}p"
            last = (e, label)
            if e is None or is_admin or mb(e) <= lim["max_mb"]:
                return last
        return last
    e = est_size(info)
    h = info.get("height")
    return e, (f"{h}p" if h else "Auto")


def _block_text(site, est_bytes, lim, duration):
    minutes = f" ({int((duration or 0) // 60)} min)" if duration else ""
    base = f"❌ This video{minutes} is about {fmt_mb(est_bytes)}, over the {lim['max_mb']}MB limit."
    return base + (" Pick a lower quality." if site == "youtube" else " Try a shorter video.")


async def _send_block(bot, chat_id, user_id, url, site, est_bytes, lim, duration, kb):
    text = _block_text(site, est_bytes, lim, duration)
    markup = kb
    if site == "youtube" and YT_ID_RE.search(url):
        key = f"single_{user_id}_{int(time.time())}"
        G["pending_single_links"][key] = url
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎞 Choose a lower quality", callback_data=f"fmt_vid_{key}")]])
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _fresh_download(bot, chat_id, user_id, url, dl_type, t, ckey, cap, site, is_admin, kb, cache):
    g = G
    info = None
    if dl_type in ("video", "audio"):
        info = await probe(url)
    duration = (info or {}).get("duration")
    est, qlabel = (None, "Auto")
    cost = 1
    lim = get_limits(site)
    if dl_type == "video":
        est, qlabel = _plan_estimate(info, cap, is_admin, site)
        have = await credits_left(user_id)
        d = evaluate(site, duration, est, is_admin, have)
        if d["action"] == "block":
            await _send_block(bot, chat_id, user_id, url, site, est, lim, duration, kb)
            return False
        if d["action"] == "ads":
            await send_refill_prompt(bot, chat_id, user_id, t, url, d["cost"], have)
            return False
        cost = d["cost"]
    elif dl_type == "audio":
        qlabel = "MP3 192kbps"

    if cap is not None:
        _remember_quality(user_id, url, cap)

    # ---- status card ----
    if dl_type in ("video", "audio"):
        status_msg, rep = await start_status(bot, chat_id, user_id, info, qlabel, fmt_mb(est) if est else "", ckey)
    else:
        status_msg = await bot.send_message(chat_id=chat_id, text=t["fetching"].format(dl_type), parse_mode="Markdown")
        rep = None
    tok_rep = CTX_REPORTER.set(rep)
    tok_q = CTX_QUALITY.set(cap)
    trace = g.get("LAST_CAROUSEL_TRACE")
    try:
        free_mb = shutil.disk_usage(".").free // (1024 * 1024)
        min_free = g["get_min_free_disk_mb"]()
        effective = g["mtproto_limit_mb"]() if "mtproto_limit_mb" in g else g["get_mtproto_max_mb"]()
        if free_mb < min_free + 150:
            effective = min(effective, 50)
        if not is_admin:
            effective = min(effective, lim["max_mb"])
        if trace is not None:
            trace.clear()
        file_paths, res, size = await asyncio.wait_for(
            asyncio.to_thread(g["download_media_engine"], url, dl_type, effective), timeout=600)
        if is_admin and trace:
            try:
                await bot.send_message(chat_id=chat_id, text="🧪 Carousel trace:\n" + "\n".join(trace)[:3500])
            except Exception:
                pass
        if not file_paths:
            raise ValueError("FILE_NOT_FOUND")

        # ---- re-check with the real size (covers links whose size was unknown) ----
        actual = parse_size_mb(size)
        if dl_type == "video" and res != "carousel" and not is_admin and actual is not None:
            have2 = await credits_left(user_id)
            d2 = evaluate(site, duration, int(actual * 1048576), is_admin, have2)
            if d2["action"] == "block":
                for p in file_paths:
                    try: os.remove(p)
                    except Exception: pass
                raise LimitHit("SIZE", size_mb=actual, limit_mb=lim["max_mb"])
            if d2["action"] == "ads":
                for p in file_paths:
                    try: os.remove(p)
                    except Exception: pass
                raise LimitHit("CREDITS", need=d2["cost"], have=have2 or 0)
            cost = max(cost, d2["cost"])
        if rep:
            await rep.stage("📤 Sending to Telegram…")

        cache = g["load_json_file"](g["CACHE_FILE"])
        if ckey not in cache:
            cache[ckey] = {"type": dl_type, "timestamp": time.time(), "qualities": {}, "hits": 0}
        meta = build_meta(info) if (info and dl_type in ("video", "audio")) else ""
        meta_block = ("\n\n" + meta) if meta else ""
        qual_tag = f"[{res}]"

        if res == "carousel":
            try:
                results = await g["send_carousel"](bot, chat_id, file_paths, ckey, status_msg, g["send_video_file"])
                if not results:
                    raise ValueError("FILE_NOT_FOUND")
                await g["save_carousel_cache"](bot, ckey, results, size)
                warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
                asyncio.create_task(g["schedule_deletion"](bot, chat_id, [r["message_id"] for r in results] + [warn.message_id], 540))
            finally:
                shutil.rmtree(os.path.dirname(file_paths[0]), ignore_errors=True)
            await _delete_quiet(bot, chat_id, status_msg)
            await charge(user_id, 1)
            await bot.send_message(chat_id=chat_id, text=t["download_success"], reply_markup=kb)
            return True

        if dl_type == "images":
            media_group = [InputMediaPhoto(media=open(p, "rb")) for p in file_paths]
            sent_media = await bot.send_media_group(chat_id=chat_id, media=media_group)
            warn = await bot.send_message(chat_id=chat_id, text=t["images_received"].format(len(file_paths)), reply_markup=kb)
            asyncio.create_task(g["schedule_deletion"](bot, chat_id, [m.message_id for m in sent_media] + [warn.message_id], 540))
            fid = sent_media[0].photo[-1].file_id
            try:
                vmsg = await bot.send_photo(chat_id=g["VIDEO_VAULT_ID"], photo=fid, caption=ckey)
                cache[ckey]["qualities"]["original"] = {"file_id": fid, "vault_msg_id": vmsg.message_id, "size": size}
            except Exception:
                cache[ckey]["qualities"]["original"] = {"file_id": fid, "size": size}
            for p in file_paths:
                try: os.remove(p)
                except Exception: pass
        elif dl_type == "audio":
            sent_media = await g["send_audio_file"](bot, chat_id, file_paths[0], f"🎵 Size {size} `{ckey}`{meta_block}", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(g["schedule_deletion"](bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            fid = sent_media.audio.file_id
            try:
                vmsg = await bot.send_audio(chat_id=g["VIDEO_VAULT_ID"], audio=fid, caption=ckey)
                cache[ckey]["qualities"]["audio"] = {"file_id": fid, "vault_msg_id": vmsg.message_id, "size": size}
            except Exception:
                cache[ckey]["qualities"]["audio"] = {"file_id": fid, "size": size}
            os.remove(file_paths[0])
        else:
            sent_media = await g["send_video_file"](bot, chat_id, chat_id, file_paths[0], f"✨ {qual_tag} Size {size} `{ckey}`{meta_block}", "Markdown", status_msg)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(g["schedule_deletion"](bot, chat_id, [sent_media.message_id, warn.message_id], 540))
            fid = sent_media.video.file_id
            try:
                vmsg = await bot.send_video(chat_id=g["VIDEO_VAULT_ID"], video=fid, caption=f"{ckey} [{res}]")
                cache[ckey]["qualities"][res] = {"file_id": fid, "vault_msg_id": vmsg.message_id, "size": size}
            except Exception as e:
                logger.error(f"Vault save fail: {e}")
                cache[ckey]["qualities"][res] = {"file_id": fid, "size": size}
            try: os.remove(file_paths[0])
            except Exception: pass

        cache[ckey]["hits"] = cache[ckey].get("hits", 0) + 1
        if meta:
            cache[ckey]["meta"] = meta
        if duration:
            cache[ckey]["duration"] = duration
        g["save_json_file"](g["CACHE_FILE"], cache)
        await _delete_quiet(bot, chat_id, status_msg)
        await charge(user_id, cost)
        await bot.send_message(chat_id=chat_id, text=t["download_success"], reply_markup=kb)
        return True

    except Exception as e:
        logger.error(f"DL {ckey}: {e}")
        if is_admin:
            tr = ("\nTrace:\n" + "\n".join(trace)[:1200]) if trace else ""
            mt = g.get("MTPROTO", {}).get("ready")
            try:
                await bot.send_message(chat_id=chat_id, text=(
                    f"🧪 DL error: {type(e).__name__}: {str(e)[:500]}\n"
                    f"MTProto: ready={mt.is_set() if mt else '?'} api_id={bool(g.get('API_ID'))} api_hash={bool(g.get('API_HASH'))}{tr}"))
            except Exception:
                pass
        msg = str(e)
        markup = kb
        if isinstance(e, LimitHit) and e.kind == "SIZE":
            err = f"❌ This video is about {e.size_mb:.0f}MB, over the {e.limit_mb}MB limit." + (" Pick a lower quality." if site == "youtube" else "")
        elif isinstance(e, LimitHit) and e.kind == "CREDITS":
            await show_error(bot, chat_id, status_msg, "⏳ One moment…", kb)
            await send_refill_prompt(bot, chat_id, user_id, t, url, e.need, e.have)
            return False
        elif "FILE_TOO_LARGE" in msg:
            err = f"❌ Too big! 😅 The limit is {effective_limit(site, is_admin)}MB per file." + (" Pick a lower quality." if site == "youtube" else " Try a shorter one!")
            if site == "youtube" and YT_ID_RE.search(url) and dl_type == "video":
                key = f"single_{user_id}_{int(time.time())}"
                g["pending_single_links"][key] = url
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎞 Choose a lower quality", callback_data=f"fmt_vid_{key}")]])
        elif "SITE_BLOCKED" in msg:
            err = "⚠️ This site is blocking downloads from our server right now. Please try again later."
        elif "MTPROTO_OFF" in msg:
            err = "⚠️ Big files need fast mode, which is offline right now."
        elif "MTPROTO_PEER" in msg:
            err = "⚠️ Send /start to this bot once, then send the link again."
        elif isinstance(e, (asyncio.TimeoutError, TimeoutError)):
            err = "⚠️ This is taking too long, so I stopped. Please try again later."
        else:
            err = t["error_generic"]
        await show_error(bot, chat_id, status_msg, err, markup)
        return False
    finally:
        CTX_REPORTER.reset(tok_rep)
        CTX_QUALITY.reset(tok_q)


def effective_limit(site, is_admin):
    try:
        return G["get_mtproto_max_mb"]() if is_admin else get_limits(site)["max_mb"]
    except Exception:
        return 200


async def _delete_quiet(bot, chat_id, msg):
    try:
        if msg is not None:
            await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
    except Exception:
        pass


async def _cache_hit(bot, chat_id, user_id, url, dl_type, t, ckey, cap, site, is_admin, kb, cache):
    """Serve from cache. Returns True/False when handled, None when there is nothing usable."""
    g = G
    entry = cache.get(ckey)
    if not entry:
        return None
    # ---- carousel ----
    if entry.get("type") == "carousel" and dl_type in ("video", "images"):
        try:
            ids = await g["send_cached_carousel"](bot, chat_id, entry, ckey)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(g["schedule_deletion"](bot, chat_id, ids + [warn.message_id], 540))
            entry["hits"] = entry.get("hits", 0) + 1
            g["save_json_file"](g["CACHE_FILE"], cache)
            await charge(user_id, 1)
            return True
        except Exception as e:
            logger.error(f"Carousel cache hit failed {ckey}: {e}")
            return None
    if entry.get("type") not in ("video", "images", "audio"):
        return None
    cq = entry.get("qualities", {})
    best = next((q for q in _quality_order(dl_type, cap) if q in cq), None)
    if not best:
        return None
    cached = cq[best]
    cost = 1
    if dl_type == "video":
        sz = parse_size_mb(cached.get("size"))
        have = await credits_left(user_id)
        d = evaluate(site, entry.get("duration"), int(sz * 1048576) if sz else None, is_admin, have)
        if d["action"] == "block":
            await _send_block(bot, chat_id, user_id, url, site, int(sz * 1048576) if sz else None, d["limits"], entry.get("duration"), kb)
            return False
        if d["action"] == "ads":
            await send_refill_prompt(bot, chat_id, user_id, t, url, d["cost"], have)
            return False
        cost = d["cost"]
    meta = entry.get("meta") or ""
    meta_block = ("\n\n" + meta) if meta else ""
    try:
        file_id = cached.get("file_id")
        if file_id:
            qual_tag = f"[{best}]"
            if dl_type == "video":
                sent = await bot.send_video(chat_id=chat_id, video=file_id, caption=t["cached_instant_video"].format(qual_tag, cached.get("size", ""), ckey) + meta_block, reply_markup=kb)
            elif dl_type == "audio":
                sent = await bot.send_audio(chat_id=chat_id, audio=file_id, caption=t["cached_instant_audio"].format(ckey) + meta_block, reply_markup=kb)
            else:
                sent = await bot.send_photo(chat_id=chat_id, photo=file_id, caption=t["cached_instant_image"].format(ckey), reply_markup=kb)
            warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"], reply_markup=kb)
            asyncio.create_task(g["schedule_deletion"](bot, chat_id, [sent.message_id, warn.message_id], 540))
            entry["hits"] = entry.get("hits", 0) + 1
            g["save_json_file"](g["CACHE_FILE"], cache)
            await charge(user_id, cost)
            return True
    except Exception as e:
        logger.error(f"Cache send fail {ckey} {best}: {e}")
        try:
            vmid = cached.get("vault_msg_id")
            if vmid:
                fwd = await bot.forward_message(chat_id=chat_id, from_chat_id=g["VIDEO_VAULT_ID"], message_id=vmid)
                warn = await bot.send_message(chat_id=chat_id, text=t["auto_delete_9m"] + " (from vault)", reply_markup=kb)
                asyncio.create_task(g["schedule_deletion"](bot, chat_id, [fwd.message_id, warn.message_id], 540))
                entry["hits"] = entry.get("hits", 0) + 1
                g["save_json_file"](g["CACHE_FILE"], cache)
                await charge(user_id, cost)
                return True
        except Exception as e2:
            logger.error(f"Vault fallback fail: {e2}")
            cq.pop(best, None)
            g["save_json_file"](g["CACHE_FILE"], cache)
    return None


async def cached_download_and_send(bot, chat_id, user_id, url, dl_type, t):
    """Drop-in replacement for the original function. Falls back to the original if the NEW
    code fails before the download starts."""
    g = G
    try:
        is_admin = user_id == _admin()
        kb = g["get_main_keyboard"](g["get_lang"](user_id), is_admin)
        cache = g["load_json_file"](g["CACHE_FILE"])
        ckey = await g["get_canonical_key"](url, chat_id, bot)
        if ckey in cache and "file_id" in cache[ckey] and "qualities" not in cache[ckey]:
            c = cache[ckey]
            c["qualities"] = {"720p": {"file_id": c["file_id"], "vault_msg_id": c.get("vault_msg_id"), "size": c.get("size", "unknown")}}
            del c["file_id"]
            g["save_json_file"](g["CACHE_FILE"], cache)
        cap = CTX_QUALITY.get()
        if cap is None:
            cap = _recall_quality(user_id, url)
        site = site_of(url)
        handled = await _cache_hit(bot, chat_id, user_id, url, dl_type, t, ckey, cap, site, is_admin, kb, cache)
        if handled is not None:
            return handled
    except Exception as e:
        logger.exception(f"extras pre-flight failed, using the original flow: {e}")
        return await _ORIG["cached_download_and_send"](bot, chat_id, user_id, url, dl_type, t)
    return await _fresh_download(bot, chat_id, user_id, url, dl_type, t, ckey, cap, site, is_admin, kb, cache)


async def run_with_quality(bot, chat_id, user_id, url, dl_type, t, cap=None):
    tok = CTX_QUALITY.set(cap)
    try:
        return await G["cached_download_and_send"](bot, chat_id, user_id, url, dl_type, t)
    finally:
        CTX_QUALITY.reset(tok)


# =====================================================================
# 7. YouTube quality picker
# =====================================================================
def _yt_menu(info, user_id, key):
    is_admin = user_id == _admin()
    hs = heights_available(info)
    dur = info.get("duration")
    rows, seen = [[InlineKeyboardButton("⭐ Auto (best that fits)", callback_data=f"ytq_auto_{key}")]], set()
    for H in (1080, 720, 480, 360):
        under = [h for h in hs if h <= H]
        if not under or max(under) in seen:
            continue
        actual = max(under)
        seen.add(actual)
        rows.append([_yt_button(info, "youtube", H, f"{actual}p", dur, is_admin, key)])
    if hs and min(hs) < 360 and min(hs) not in seen:
        rows.append([_yt_button(info, "youtube", 0, f"{min(hs)}p (lowest)", dur, is_admin, key)])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"ytq_cancel_{key}")])
    return InlineKeyboardMarkup(rows)


def _yt_button(info, site, cap, label, dur, is_admin, key):
    est = est_size(info, cap)
    d = evaluate(site, dur, est, is_admin, None)
    icon = "🚫" if d["action"] == "block" else ("⚡" if d["heavy"] and not is_admin else "🎞")
    extra = f" · {d['cost']} credits" if (d["heavy"] and not is_admin and d["action"] != "block") else ""
    return InlineKeyboardButton(f"{icon} {label} · ~{fmt_mb(est)}{extra}", callback_data=f"ytq_{cap}_{key}")


async def on_fmt_vid(update, context):
    q = update.callback_query
    try:
        key = q.data[len("fmt_vid_"):]
        url = G["pending_single_links"].get(key)
        if not url or not YT_ID_RE.search(url) or not _cfg().get("yt_quality_menu", True):
            return                                   # not YouTube: the normal flow continues
        info = await probe(url)
        if not info or not heights_available(info):
            return
        dur = info.get("duration") or 0
        title = _clean(info.get("title"), 70)
        text = (f"🎬 {title}\n⏱ {int(dur // 60)}m {int(dur % 60)}s\n\n"
                f"Choose a quality:\n🎞 normal · ⚡ uses extra credits · 🚫 too big")
        await q.answer()
        await q.message.edit_text(text, reply_markup=_yt_menu(info, q.from_user.id, key))
    except ApplicationHandlerStop:
        raise
    except Exception as e:
        logger.error(f"quality menu failed, using the normal flow: {e}")
        return
    raise ApplicationHandlerStop


async def on_ytq(update, context):
    q = update.callback_query
    user_id, chat_id = q.from_user.id, q.message.chat_id
    t = G["LANGUAGES"].get(G["get_lang"](user_id), G["LANGUAGES"]["en"])
    try:
        _, capstr, key = q.data.split("_", 2)
    except ValueError:
        await q.answer()
        raise ApplicationHandlerStop
    if capstr == "cancel":
        G["pending_single_links"].pop(key, None)
        await q.answer()
        try: await q.message.delete()
        except Exception: pass
        raise ApplicationHandlerStop
    url = G["pending_single_links"].get(key)
    if not url:
        await q.answer(t.get("batch_expired", "Expired, send the link again."), show_alert=True)
        raise ApplicationHandlerStop
    cap = None if capstr == "auto" else int(capstr)
    if cap is not None and user_id != _admin():
        info = await probe(url)
        if info:
            est = est_size(info, cap)
            d = evaluate("youtube", info.get("duration"), est, False, None)
            if d["action"] == "block":
                await q.answer(f"🚫 About {fmt_mb(est)}, over the {d['limits']['max_mb']}MB limit. Pick a lower quality.", show_alert=True)
                raise ApplicationHandlerStop
    G["pending_single_links"].pop(key, None)
    await q.answer(t.get("checking_vault", "Checking…"))
    try: await q.message.delete()
    except Exception: pass
    lang = G["get_lang"](user_id)
    ckey = await G["get_canonical_key"](url, chat_id, context.bot)
    cache = G["load_json_file"](G["CACHE_FILE"])
    if ckey in cache:
        await run_with_quality(context.bot, chat_id, user_id, url, "video", t, cap)
        raise ApplicationHandlerStop
    if await G["acquire_slot"]():
        try:
            await run_with_quality(context.bot, chat_id, user_id, url, "video", t, cap)
        finally:
            await G["release_slot"]()
    else:
        pos = G["download_queue"].qsize() + 1
        await G["download_queue"].put({"func": run_with_quality, "args": (context.bot, chat_id, user_id, url, "video", t, cap), "kwargs": {}})
        free_mb = shutil.disk_usage(".").free // (1024 * 1024)
        await context.bot.send_message(chat_id=chat_id, text=t["server_busy"].format(G["active_downloads"], G["MAX_CONCURRENT_SHORT"], free_mb, pos),
                                       parse_mode="Markdown", reply_markup=G["get_main_keyboard"](lang, user_id == _admin()))
    raise ApplicationHandlerStop


# =====================================================================
# 8. required channels (gate that checks EVERY time)
# =====================================================================
_JOIN_OK = {}            # user_id -> (timestamp, signature)
_PROMPT_MSG = {}         # user_id -> (chat_id, message_id)
_ADMIN_WARNED = {}       # channel id -> timestamp


async def _notify_admin_once(bot, ch, err):
    now = time.time()
    if now - _ADMIN_WARNED.get(ch.get("id"), 0) < 3600:
        return
    _ADMIN_WARNED[ch.get("id")] = now
    try:
        await bot.send_message(chat_id=_admin(), text=(
            f"⚠️ I can't check membership for “{ch.get('title')}” ({err}).\n"
            f"Make sure I am an ADMIN in that channel. Until then users are NOT blocked by it."))
    except Exception:
        pass


async def _is_member(bot, uid, ch):
    try:
        m = await bot.get_chat_member(chat_id=ch["id"], user_id=uid)
        st = getattr(m, "status", "")
        if st in ("member", "administrator", "creator"):
            return True
        if st == "restricted":
            return bool(getattr(m, "is_member", True))
        return False
    except Exception as e:
        s = str(e).lower()
        if "user not found" in s or "participant_id_invalid" in s:
            return False
        logger.warning(f"membership check failed for {ch.get('id')}: {e}")
        await _notify_admin_once(bot, ch, str(e)[:80])
        return True                      # fail open


async def missing_channels(bot, uid, chans, use_cache=True):
    sig = tuple(c["id"] for c in chans)
    hit = _JOIN_OK.get(uid)
    if use_cache and hit and hit[1] == sig and time.time() - hit[0] < 45:
        return []
    results = await asyncio.gather(*[_is_member(bot, uid, c) for c in chans], return_exceptions=True)
    missing = [c for c, ok in zip(chans, results) if ok is False]
    if not missing:
        _JOIN_OK[uid] = (time.time(), sig)
    else:
        _JOIN_OK.pop(uid, None)
    return missing


def join_keyboard(chans, missing):
    miss_ids = {c["id"] for c in missing}
    rows = [[InlineKeyboardButton(("📢 Join " if c["id"] in miss_ids else "✅ ") + _clean(c.get("title"), 30), url=c.get("url") or "https://t.me/")]
            for c in chans]
    rows.append([InlineKeyboardButton("✅ I've joined", callback_data="extras_checkjoin")])
    return InlineKeyboardMarkup(rows)


async def gate(update, context):
    try:
        user = update.effective_user
        if not user or user.is_bot or user.id == _admin():
            return
        if update.callback_query is None and update.message is None:
            return
        chat = update.effective_chat
        if chat is not None and chat.type != "private":
            return
        if update.callback_query is not None and update.callback_query.data == "extras_checkjoin":
            return
        chans = required_channels()
        if not chans:
            return
        missing = await missing_channels(context.bot, user.id, chans)
        if not missing:
            return
        chat_id = chat.id if chat else user.id
        old = _PROMPT_MSG.pop(user.id, None)
        if old:
            try: await context.bot.delete_message(chat_id=old[0], message_id=old[1])
            except Exception: pass
        if update.callback_query is not None:
            try: await update.callback_query.answer("🔒 Please join our channels first.", show_alert=False)
            except Exception: pass
        sent = await context.bot.send_message(chat_id=chat_id, reply_markup=join_keyboard(chans, missing), text=(
            "🔒 Please join our channels to use this bot.\n\n"
            "Join every channel below, then tap “✅ I've joined”.\n"
            "I check this every time, so please stay subscribed."))
        _PROMPT_MSG[user.id] = (chat_id, sent.message_id)
    except ApplicationHandlerStop:
        raise
    except Exception as e:
        logger.error(f"gate error (users are NOT blocked): {e}")
        return
    raise ApplicationHandlerStop


async def on_checkjoin(update, context):
    q = update.callback_query
    uid = q.from_user.id
    chans = required_channels()
    missing = await missing_channels(context.bot, uid, chans, use_cache=False) if chans else []
    if missing:
        names = ", ".join(_clean(c.get("title"), 25) for c in missing)
        await q.answer(f"❌ You still need to join: {names}", show_alert=True)
        try: await q.message.edit_reply_markup(reply_markup=join_keyboard(chans, missing))
        except Exception: pass
        raise ApplicationHandlerStop
    await q.answer("✅ Verified! Welcome.")
    try: await q.message.delete()
    except Exception: pass
    _PROMPT_MSG.pop(uid, None)
    lang = G["get_lang"](uid)
    await context.bot.send_message(chat_id=q.message.chat_id, text="✅ You're in! Paste a link to start. 👇",
                                   reply_markup=G["get_main_keyboard"](lang, uid == _admin()))
    raise ApplicationHandlerStop


# =====================================================================
# 9. admin panels: required channels + limits
# =====================================================================
def _cancel_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)


def _main_kb(uid):
    return G["get_main_keyboard"](G["get_lang"](uid), uid == _admin())


async def channels_home(bot, chat_id):
    chans = required_channels()
    lines = [f"{i + 1}. {_clean(c.get('title'), 40)}  ({c['id']})" for i, c in enumerate(chans)]
    text = ("📢 Required channels (users must join ALL before using the bot)\n\n" +
            ("\n".join(lines) if lines else "None yet. Users can use the bot freely.") +
            "\n\nI check membership on every message, so users who leave are blocked again.")
    rows = [[InlineKeyboardButton(f"❌ Remove: {_clean(c.get('title'), 28)}", callback_data=f"extras_reqdel_{i}")] for i, c in enumerate(chans)]
    rows.append([InlineKeyboardButton("➕ Add channel", callback_data="extras_reqadd")])
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(rows))


def _lim_home_markup():
    rows, row = [], []
    for site, name in SITES:
        l = get_limits(site)
        row.append(InlineKeyboardButton(f"{name.split(' (')[0]} · {l['max_minutes']}m/{l['max_mb']}MB", callback_data=f"extras_limsite_{site}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


LIM_HOME_TEXT = ("📏 Download limits\n\nTap a site to change its limits. “Default” applies to every site that has no "
                 "own setting.\nButton shows: max minutes / max size.")


def _site_view(site):
    name = dict(SITES).get(site, site)
    l = get_limits(site)
    own = (_cfg().get("site_limits", {}).get(site) or {}) if site != "default" else (_cfg().get("site_limits", {}).get("default") or {})
    text = (f"📏 {name}\n\n⏱ Max length: {l['max_minutes']} min\n📦 Max size: {l['max_mb']} MB\n"
            f"⚡ Heavy from: {l['heavy_mb']} MB\n🎟 Heavy cost: {l['heavy_cost']} credits\n\n"
            f"Rules\n• Bigger than {l['max_mb']}MB → blocked (you are exempt)\n"
            f"• Over {l['heavy_mb']}MB or longer than {l['max_minutes']} min → {l['heavy_cost']} credits\n"
            f"• Otherwise 1 credit\n"
            f"{'• Using its own settings' if own else '• Using the default settings'}")
    rows = [[InlineKeyboardButton(f"{LIMIT_LABELS[f]}: {l[f]}", callback_data=f"extras_limset_{site}_{f}")] for f in DEFAULT_LIMITS]
    if site != "default":
        rows.append([InlineKeyboardButton("♻️ Reset to default", callback_data=f"extras_limreset_{site}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="extras_limhome")])
    return text, InlineKeyboardMarkup(rows)


async def on_admin_cb(update, context):
    q = update.callback_query
    uid, chat_id = q.from_user.id, q.message.chat_id
    if uid != _admin():
        await q.answer("Admin only.", show_alert=True)
        raise ApplicationHandlerStop
    data = q.data
    await q.answer()
    if data == "extras_limhome":
        await q.message.edit_text(LIM_HOME_TEXT, reply_markup=_lim_home_markup())
    elif data.startswith("extras_limsite_"):
        text, kb = _site_view(data[len("extras_limsite_"):])
        await q.message.edit_text(text, reply_markup=kb)
    elif data.startswith("extras_limreset_"):
        site = data[len("extras_limreset_"):]
        reset_site_limits(site)
        text, kb = _site_view(site)
        await q.message.edit_text(text, reply_markup=kb)
    elif data.startswith("extras_limset_"):
        site, field = data[len("extras_limset_"):].split("_", 1)
        lo, hi = LIMIT_RANGES[field]
        context.user_data["extras_state"] = {"mode": "lim_edit", "site": site, "field": field}
        await context.bot.send_message(chat_id=chat_id, reply_markup=_cancel_kb(), text=(
            f"✏️ {dict(SITES).get(site, site)} · {LIMIT_LABELS[field]}\n"
            f"Current: {get_limits(site)[field]}\nSend the new number ({lo} to {hi}), or ❌ Cancel."))
    elif data == "extras_reqhome":
        await channels_home(context.bot, chat_id)
    elif data == "extras_reqadd":
        context.user_data["extras_state"] = {"mode": "req_add"}
        await context.bot.send_message(chat_id=chat_id, reply_markup=_cancel_kb(), text=(
            "➕ Add a required channel\n\nForward any message from the channel, or send its @username / t.me link / -100… ID.\n"
            "I must be an ADMIN in that channel so I can check members.\nSend ❌ Cancel to stop."))
    elif data.startswith("extras_reqdel_"):
        try:
            idx = int(data[len("extras_reqdel_"):])
            chans = required_channels()
            gone = chans.pop(idx)
            save_required_channels(chans)
            _JOIN_OK.clear()
            await q.message.edit_text(f"🗑 Removed “{_clean(gone.get('title'), 40)}”.")
        except Exception:
            await q.message.edit_text("That channel is already gone.")
        await channels_home(context.bot, chat_id)
    raise ApplicationHandlerStop


async def _resolve_channel(bot, message, text):
    fo = getattr(message, "forward_origin", None)
    chat = getattr(fo, "chat", None) if fo is not None and getattr(fo, "type", None) == "channel" else None
    if chat is None:
        chat = getattr(message, "forward_from_chat", None)
    ident = chat.id if chat is not None else None
    if ident is None:
        m = re.search(r"(?:t\.me/|@)([A-Za-z][A-Za-z0-9_]{3,})", text or "")
        if m:
            ident = "@" + m.group(1)
        elif re.fullmatch(r"-100\d{5,}", (text or "").strip()):
            ident = int(text.strip())
    if ident is None:
        return None, "I couldn't read that. Forward a message from the channel, or send @username / -100… ID."
    try:
        full = await bot.get_chat(ident)
    except Exception as e:
        return None, f"I can't find that channel ({str(e)[:80]}). Add me as admin first, then try again."
    if getattr(full, "type", "") not in ("channel", "supergroup"):
        return None, "That is not a channel or group."
    try:
        me = await bot.get_chat_member(chat_id=full.id, user_id=bot.id)
        if getattr(me, "status", "") not in ("administrator", "creator"):
            return None, "I'm in that channel but not an admin. Make me an admin, then try again."
    except Exception as e:
        return None, f"I can't check my admin status there ({str(e)[:80]})."
    return full, None


async def admin_router(update, context):
    """Admin-only: buttons + the text steps of our panels."""
    msg = update.message
    if msg is None:
        return
    uid = msg.from_user.id
    text = (msg.text or "").strip()
    st = context.user_data.get("extras_state")
    if st and text in CANCEL_WORDS:
        context.user_data.pop("extras_state", None)
        await msg.reply_text("Cancelled.", reply_markup=_main_kb(uid))
        raise ApplicationHandlerStop
    if text in ("📏 Limits", "/limits"):
        context.user_data.pop("extras_state", None)
        await msg.reply_text(LIM_HOME_TEXT, reply_markup=_lim_home_markup())
        raise ApplicationHandlerStop
    if text in ("📢 Required Channels", "/channels"):
        context.user_data.pop("extras_state", None)
        await channels_home(context.bot, msg.chat_id)
        raise ApplicationHandlerStop
    if not st:
        return
    if text in _menu_texts() or re.search(r"https?://", text):
        context.user_data.pop("extras_state", None)       # admin moved on: let the normal handlers run
        return
    mode = st.get("mode")
    if mode == "lim_edit":
        try:
            val = int(re.sub(r"[^\d]", "", text))
            lo, hi = LIMIT_RANGES[st["field"]]
            if not lo <= val <= hi:
                raise ValueError
        except Exception:
            await msg.reply_text(f"Please send a whole number between {LIMIT_RANGES[st['field']][0]} and {LIMIT_RANGES[st['field']][1]}, or ❌ Cancel.", reply_markup=_cancel_kb())
            raise ApplicationHandlerStop
        set_limit(st["site"], st["field"], val)
        context.user_data.pop("extras_state", None)
        await msg.reply_text("✅ Saved.", reply_markup=_main_kb(uid))
        stext, skb = _site_view(st["site"])
        await msg.reply_text(stext, reply_markup=skb)
        raise ApplicationHandlerStop
    if mode == "req_add":
        full, err = await _resolve_channel(context.bot, msg, text)
        if err:
            await msg.reply_text("❌ " + err, reply_markup=_cancel_kb())
            raise ApplicationHandlerStop
        chans = required_channels()
        if any(c["id"] == full.id for c in chans):
            context.user_data.pop("extras_state", None)
            await msg.reply_text("That channel is already in the list.", reply_markup=_main_kb(uid))
            raise ApplicationHandlerStop
        url = f"https://t.me/{full.username}" if getattr(full, "username", None) else None
        if not url:
            try:
                url = await context.bot.export_chat_invite_link(full.id)
            except Exception:
                context.user_data["extras_state"] = {"mode": "req_add_link", "id": full.id, "title": full.title or str(full.id)}
                await msg.reply_text("This channel is private. Send me its invite link (https://t.me/+…).", reply_markup=_cancel_kb())
                raise ApplicationHandlerStop
        chans.append({"id": full.id, "title": full.title or str(full.id), "url": url})
        save_required_channels(chans)
        _JOIN_OK.clear()
        context.user_data.pop("extras_state", None)
        await msg.reply_text(f"✅ Added “{_clean(full.title, 40)}”.", reply_markup=_main_kb(uid))
        await channels_home(context.bot, msg.chat_id)
        raise ApplicationHandlerStop
    if mode == "req_add_link":
        if "t.me/" not in text:
            await msg.reply_text("Please send a t.me invite link, or ❌ Cancel.", reply_markup=_cancel_kb())
            raise ApplicationHandlerStop
        chans = required_channels()
        chans.append({"id": st["id"], "title": st["title"], "url": text})
        save_required_channels(chans)
        _JOIN_OK.clear()
        context.user_data.pop("extras_state", None)
        await msg.reply_text(f"✅ Added “{_clean(st['title'], 40)}”.", reply_markup=_main_kb(uid))
        await channels_home(context.bot, msg.chat_id)
        raise ApplicationHandlerStop


# =====================================================================
# 10. "Change Batch Channel": cancel button, and links are never trapped
# =====================================================================
def _menu_texts():
    s = {"🔗 File-to-Link", "🟢 Bot Status", "🔄 Change Batch Channel", "📢 Broadcast", "⚡ Create Flash Drop",
         "⚙️ Ad Toggle Panel", "📏 Limits", "📢 Required Channels", "💾 Disk Config", "⚡ MTProto Config",
         "🧪 Test Ad", "📢 Ad Info"}
    for lang in G["LANGUAGES"].values():
        for k, v in lang.items():
            if k.startswith("menu_") and isinstance(v, str):
                s.add(v)
    return s


async def batch_channel_router(update, context):
    msg = update.message
    if msg is None or msg.from_user is None:
        return
    uid = msg.from_user.id
    text = (msg.text or "").strip()
    lang = G["get_lang"](uid)
    t = G["LANGUAGES"].get(lang, G["LANGUAGES"]["en"])
    if text == "🔄 Change Batch Channel":
        states = G["load_linking_states"]()
        states[str(uid)] = "waiting_for_channel"
        G["save_linking_states"](states)
        await msg.reply_text(t["change_channel_prompt"], parse_mode="Markdown", reply_markup=_cancel_kb())
        raise ApplicationHandlerStop
    states = G["load_linking_states"]()
    if states.get(str(uid)) != "waiting_for_channel":
        return
    def _clear():
        states.pop(str(uid), None)
        G["save_linking_states"](states)
    if text in CANCEL_WORDS:
        _clear()
        await msg.reply_text("✅ Cancelled.", reply_markup=_main_kb(uid))
        raise ApplicationHandlerStop
    fo = getattr(msg, "forward_origin", None)
    is_channel_forward = (fo is not None and getattr(fo, "type", None) == "channel") or getattr(msg, "forward_from_chat", None) is not None
    if is_channel_forward:
        return                                           # the normal handler links the channel
    if re.search(r"https?://", text) or text in _menu_texts():
        _clear()                                         # the user moved on: process their link/button normally
        return
    await msg.reply_text("❌ Please forward a message directly from your channel (not a copied message), or tap ❌ Cancel.",
                         reply_markup=_cancel_kb())
    raise ApplicationHandlerStop


# =====================================================================
# 11. wiring
# =====================================================================
_INITED = False
_CANON = {}


def init(g):
    """Call once with the main program's globals()."""
    global G, _INITED
    G = g
    if _INITED:
        return
    _INITED = True
    for name in ("cached_download_and_send", "deduct_download_counter", "get_canonical_key", "get_main_keyboard"):
        _ORIG[name] = g[name]

    # progress hooks + quality cap inside every yt-dlp call
    base = yt_dlp.YoutubeDL

    class PatchedYDL(base):
        def __init__(self, params=None, *a, **k):
            params = dict(params or {})
            rep = CTX_REPORTER.get()
            if rep is not None and not params.get("skip_download"):
                params["progress_hooks"] = list(params.get("progress_hooks") or []) + [rep.hook]
            super().__init__(params, *a, **k)

        def extract_info(self, url, download=True, *a, **k):
            if download:
                rep = CTX_REPORTER.get()
                if rep is not None:
                    rep.reset()
                cap = CTX_QUALITY.get()
                if cap is not None:
                    m = re.search(r"height<=(\d+)", str(self.params.get("format") or ""))
                    if m and int(m.group(1)) > cap:
                        raise yt_dlp.utils.DownloadError("TIER_SKIPPED")
            return super().extract_info(url, download, *a, **k)

    yt_dlp.YoutubeDL = PatchedYDL
    if "yt_dlp" in g:
        g["yt_dlp"].YoutubeDL = PatchedYDL

    async def canon(url, chat_id=None, bot=None):
        now = time.time()
        hit = _CANON.get(url)
        if hit and now - hit[0] < 300:
            return hit[1]
        if chat_id != _admin():                          # debug messages only for the admin
            chat_id, bot = None, None
        key = await _ORIG["get_canonical_key"](url, chat_id, bot)
        if len(_CANON) > 500:
            _CANON.clear()
        _CANON[url] = (now, key)
        return key
    g["get_canonical_key"] = canon

    def kb_with_admin_buttons(lang_code, is_admin):
        kb = _ORIG["get_main_keyboard"](lang_code, is_admin)
        if not is_admin:
            return kb
        rows = [list(r) for r in kb.keyboard]
        rows.append([KeyboardButton("📏 Limits"), KeyboardButton("📢 Required Channels")])
        return ReplyKeyboardMarkup(rows, resize_keyboard=True)
    g["get_main_keyboard"] = kb_with_admin_buttons

    async def tell_uploading(status_msg, path):
        if status_msg is None:
            return
        text = f"📤 Uploading {os.path.getsize(path) / (1024 * 1024):.0f}MB in fast mode…"
        rep = CTX_REPORTER.get()
        if rep is not None:
            await rep.stage(text)
            return
        try:
            if getattr(status_msg, "photo", None):
                await status_msg.edit_caption(caption=text)
            else:
                await status_msg.edit_text(text)
        except Exception:
            pass
    if "_tell_uploading" in g:
        g["_tell_uploading"] = tell_uploading

    if not os.getenv("EXTRAS_DISABLE_DOWNLOAD"):
        g["cached_download_and_send"] = cached_download_and_send


def register(app):
    """Add our handlers. They run BEFORE the bot's own handlers (negative groups)."""
    admin = filters.User(user_id=G["ADMIN_ID"])
    app.add_handler(TypeHandler(Update, gate), group=-4)
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, batch_channel_router), group=-3)
    app.add_handler(MessageHandler(filters.ALL & admin, admin_router), group=-2)
    app.add_handler(CallbackQueryHandler(on_checkjoin, pattern=r"^extras_checkjoin$"), group=-2)
    app.add_handler(CallbackQueryHandler(on_admin_cb, pattern=r"^extras_"), group=-2)
    app.add_handler(CallbackQueryHandler(on_fmt_vid, pattern=r"^fmt_vid_"), group=-2)
    app.add_handler(CallbackQueryHandler(on_ytq, pattern=r"^ytq_"), group=-2)
