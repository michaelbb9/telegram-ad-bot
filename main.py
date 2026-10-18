import time
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ----------------- CONFIGURATION -----------------
BOT_TOKEN = "8863904451:AAE1DbPBkeB1SXyCLIzDNbxTfEZIYd_sjWI"
ADSTERRA_LINK = "https://google.com"
DETECTED_CHANNEL_ID = -1004347828512  

REQUIRED_WAIT_TIME = 7  # Duration in seconds
DELETE_DELAY_TIME = 540  # 9 minutes in seconds

user_click_tracker = {}

# --- HEALTH CHECK SERVER FOR RENDER ---
async def handle_root_request(reader, writer):
    """Responds to Render's background system ping checks cleanly."""
    response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 12\r\n\r\nBot is alive"
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()

async def run_health_server():
    """Starts an asynchronous network socket to keep Render online."""
    port = int(os.environ.get("PORT", 8080))
    server = await asyncio.start_server(handle_root_request, "0.0.0.0", port)
    async with server:
        await server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    args = context.args  
    
    if not args:
        await update.message.reply_text(
            "👋 **Welcome!** Please click a specific video link from the main channel to unlock content.",
            parse_mode="Markdown"
        )
        return
    
    # FIXED: Safely extract the string from context.args list
    video_code = args[0] if isinstance(args, list) and len(args) > 0 else ""
    
    if video_code.startswith("vid"):
        clean_code = video_code.replace("vid", "")
        if "to" in clean_code:
            try:
                parts = clean_code.split("to")
                msg_start = int(parts[0])
                msg_end = int(parts[1])
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Invalid bundle format.")
                return
        else:
            try:
                msg_start = int(clean_code)
                msg_end = msg_start
            except ValueError:
                await update.message.reply_text("❌ Invalid video number.")
                return
    else:
        await update.message.reply_text("❌ Unknown link parameter layout.")
        return

    user_click_tracker[user_id] = {
        "click_time": None,  
        "msg_start": msg_start,
        "msg_end": msg_end
    }

    keyboard = [
        [InlineKeyboardButton("🟢 Watch Ads (for 7s)", url=ADSTERRA_LINK)],
        [InlineKeyboardButton("💜 I have clicked ads ⁉️", callback_data="verify_click")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=(
            "👇 **CONTENT LOCKED** 👇\n\n"
            "To unlock and receive your video bundle file packets right here in the chat:\n"
            "1️⃣ Click the ad button below.\n"
            "2️⃣ Stay on the page for **7 seconds**.\n"
            "3️⃣ Come back and press the verify button."
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def auto_delete_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    message_ids_to_delete = job.data
    for msg_id in message_ids_to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

async def handle_button_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    current_time = time.time()
    await query.answer()

    if query.data == "verify_click":
        if user_id not in user_click_tracker:
            await query.message.reply_text("❌ Please go back to the main channel and select a video link first.")
            return
        
        session = user_click_tracker[user_id]
        if session["click_time"] is None:
            user_click_tracker[user_id]["click_time"] = current_time
            await query.message.reply_text(
                text="⏳ **Timer initiated!** Please ensure you open the ad link and stay on it for 7 seconds before verifying again.",
                parse_mode="Markdown"
            )
            return

        elapsed_time = current_time - session["click_time"]
        if elapsed_time < REQUIRED_WAIT_TIME:
            remaining = int(REQUIRED_WAIT_TIME - elapsed_time)
            await query.message.reply_text(
                text=f"❌ **Access Denied!** You only waited {int(elapsed_time)}s. Please stay on the ad for another **{remaining} seconds**.",
                parse_mode="Markdown"
            )
        else:
            msg_start = session["msg_start"]
            msg_end = session["msg_end"]
            del user_click_tracker[user_id]
            await query.message.reply_text("✅ **Verification Successful!** Fetching your video bundle packet from the vault now...")
            
            forwarded_message_ids = []
            try:
                for target_msg_id in range(msg_start, msg_end + 1):
                    forwarded_msg = await context.bot.forward_message(
                        chat_id=user_id,
                        from_chat_id=DETECTED_CHANNEL_ID,
                        message_id=target_msg_id
                    )
                    forwarded_message_ids.append(forwarded_msg.message_id)
                    await asyncio.sleep(0.2)
                
                warning_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text="⏳ **Safety Alert:** These videos will automatically delete from this chat box in **9 minutes** for security reasons. Watch them now!"
                )
                forwarded_message_ids.append(warning_msg.message_id)
                
                # FIXED: Use job_queue delay directly instead of blocking inside sleep
                context.job_queue.run_once(auto_delete_task, when=DELETE_DELAY_TIME, data=forwarded_message_ids, chat_id=user_id)
                    
            except Exception as e:
                await query.message.reply_text(f"❌ **Error fetching file bundle.** Details: {e}")

async def post_init_callback(application: Application) -> None:
    """Spawns the health checker server inside the main async event loop context."""
    asyncio.create_task(run_health_server())

def main() -> None:
    print("Initializing Optimized Telegram Bot Server...")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init_callback).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button_clicks))
    app.run_polling()

if __name__ == "__main__":
    main()
