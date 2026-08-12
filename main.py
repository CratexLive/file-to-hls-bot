import os
import asyncio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8860451513:AAFtgWhYmeraUVhAUm32DJmnRL_oOvwfSlI")
BASE_URL = os.environ.get("BASE_URL", "https://hls-tele-bot.onrender.com")

ALLOWED_DOMAINS = [
    "https://yourdomain.com",
    "https://www.yourdomain.com",
    "http://localhost:3000"
]

os.makedirs("hls_files", exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def verify_domain_origin(request: Request, call_next):
    if request.url.path.startswith("/hls"):
        referer = request.headers.get("referer")
        origin = request.headers.get("origin")
        
        if referer or origin:
            is_allowed = any(
                (referer and referer.startswith(domain)) or (origin and origin.startswith(domain))
                for domain in ALLOWED_DOMAINS
            )
            if not is_allowed:
                return Response(content="Access Denied: Domain not authorized", status_code=403)

    response = await call_next(request)
    return response

app.mount("/hls", StaticFiles(directory="hls_files"), name="hls")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot is live"}

# --- Telegram Bot Setup ---
tg_app = Application.builder().token(BOT_TOKEN).read_timeout(300).write_timeout(300).build()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to HLS Converter Bot!**\n\n"
        "Send or forward me any video file (`.mp4`, `.mkv`), and I will convert it into an `.m3u8` streaming link for you.",
        parse_mode="Markdown"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    status = await message.reply_text("📥 **Downloading video from Telegram...**", parse_mode="Markdown")
    
    job_id = str(message.message_id)
    out_dir = f"hls_files/{job_id}"
    os.makedirs(out_dir, exist_ok=True)
    
    video_obj = message.video or message.document
    video_file = await video_obj.get_file()
    input_path = f"{out_dir}/input.mp4"
    
    # Download with custom timeout handling
    await video_file.download_to_drive(input_path)
    
    await status.edit_text("⚙️ **Converting video to HLS (.m3u8)... Fast processing active.**", parse_mode="Markdown")
    
    m3u8_file = f"{out_dir}/playlist.m3u8"
    
    # Fast FFmpeg command without re-encoding video streams
    cmd = [
        "ffmpeg", "-i", input_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-start_number", "0",
        "-hls_time", "6",
        "-hls_list_size", "0",
        "-f", "hls", m3u8_file
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    
    if os.path.exists(m3u8_file):
        if os.path.exists(input_path):
            os.remove(input_path)
            
        stream_link = f"{BASE_URL.rstrip('/')}/hls/{job_id}/playlist.m3u8"
        await status.edit_text(
            f"✅ **Conversion Complete!**\n\n"
            f"🔗 **HLS Playlist Link:**\n`{stream_link}`\n\n"
            f"💡 *You can paste this link in Shaka Player on your website.*",
            parse_mode="Markdown"
        )
    else:
        await status.edit_text("❌ **Failed to convert video.** Please try another file format.")

tg_app.add_handler(CommandHandler("start", start_cmd))
tg_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))

@app.on_event("startup")
async def startup_event():
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)
    print("🤖 Telegram Bot Polling Started!")

@app.on_event("shutdown")
async def shutdown_event():
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
