import os
from pyrogram import Client, filters

# Load credentials from Render environment variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("⚠️ Missing API_ID, API_HASH, or TELEGRAM_TOKEN environment variables!")

# Initialize Pyrogram MTProto Client using your bot token and API credentials
app = Client(
    "mtproto_heavy_worker",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("download_large"))
async def handle_large_file(client, message):
    """
    Listens for /download_large command sent to the bot, 
    bypassing 20MB/50MB bot restrictions using MTProto sockets.
    """
    status_msg = await message.reply_text("📥 Initializing MTProto high-speed stream...")
    
    if not message.reply_to_message:
        await status_msg.edit_text("⚠️ Please reply to a large video or document with `/download_large`.")
        return

    try:
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)

        # Download files up to 2GB smoothly via MTProto
        file_path = await client.download_media(
            message.reply_to_message,
            file_name=f"{download_dir}/"
        )
        
        await status_msg.edit_text(f"✅ Successfully downloaded large file via MTProto:\n`{file_path}`")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ MTProto Download Error: `{str(e)}`")

if __name__ == "__main__":
    print("🚀 Starting separate MTProto Worker...")
    app.run()
