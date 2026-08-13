import os
import asyncio
import aiofiles
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8860451513:AAFtgWhYmeraUVhAUm32DJmnRL_oOvwfSlI")
BASE_URL = os.environ.get("BASE_URL", "https://file-to-hls-bot-2.onrender.com")

os.makedirs("hls_files", exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/hls", StaticFiles(directory="hls_files"), name="hls")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot is live"}

# --- Anti-Sleep Mechanism ---
async def self_ping():
    """Pings the Render app URL every 10 minutes to prevent spin-down."""
    await asyncio.sleep(30)
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(BASE_URL)
                print(f"🔄 Self-ping status: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Self-ping failed: {e}")
            await asyncio.sleep(600)

# --- Telegram Bot Logic ---
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to Advanced HLS Converter Bot!**\n\n"
        "Send or forward me any video file (up to **2GB**), and I will convert it into an `.m3u8` streaming link with live progress tracking.",
        parse_mode="Markdown"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    status_msg = await message.reply_text("📥 **Initializing download (Large file support)...**", parse_mode="Markdown")
    
    job_id = str(message.message_id)
    out_dir = f"hls_files/{job_id}"
    os.makedirs(out_dir, exist_ok=True)
    
    video_obj = message.video or message.document
    file_size_mb = video_obj.file_size / (1024 * 1024)
    
    if file_size_mb > 2048:
        await status_msg.edit_text("❌ **File too large!** Max supported size is 2GB.")
        return

    try:
        await status_msg.edit_text(f"📥 **Downloading video ({file_size_mb:.1f} MB)... Please wait.**", parse_mode="Markdown")
        
        file_info = await video_obj.get_file()
        file_url = file_info.file_path
        
        input_path = f"{out_dir}/input.mp4"
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", file_url) as response:
                async with aiofiles.open(input_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        await f.write(chunk)
                        
        await status_msg.edit_text("⚙️ **Starting HLS Conversion...**", parse_mode="Markdown")
        
        m3u8_file = f"{out_dir}/playlist.m3u8"
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-hls_time", "10",
            "-hls_list_size", "0",
            "-f", "hls", m3u8_file
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="ignore")
            if "frame=" in decoded:
                try:
                    await status_msg.edit_text(f"⚙️ **Converting...**\n`{decoded.strip()}`", parse_mode="Markdown")
                except Exception:
                    pass
                    
        await proc.wait()
        
        if os.path.exists(m3u8_file):
            if os.path.exists(input_path):
                os.remove(input_path)
                
            stream_link = f"{BASE_URL.rstrip('/')}/hls/{job_id}/playlist.m3u8"
            await status_msg.edit_text(
                f"✅ **Conversion Complete!**\n\n"
                f"📊 **File Size:** {file_size_mb:.1f} MB\n"
                f"🔗 **HLS Playlist Link:**\n`{stream_link}`\n\n"
                f"💡 *Paste this link into Shaka Player or HLS.js web players.*",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text("❌ **Failed to convert video.** Codec error or unsupported format.")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ **An error occurred:** `{str(e)}`", parse_mode="Markdown")

tg_app.add_handler(CommandHandler("start", start_cmd))
tg_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))

@app.on_event("startup")
async def startup_event():
    await tg_app.initialize()
    await tg_app.start()
    # Drop pending updates forces clearing any old stuck sessions
    await tg_app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    print("🤖 Telegram Bot Polling Started!")
    asyncio.create_task(self_ping())

@app.on_event("shutdown")
async def shutdown_event():
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
