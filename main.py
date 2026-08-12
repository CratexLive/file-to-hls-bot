import os
import subprocess
import asyncio
from pyrogram import Client, filters
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

API_ID = int(os.environ.get("API_ID", 29008502))
API_HASH = os.environ.get("API_HASH", "0ec186387ca45429e36d77637743031e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8860451513:AAFtgWhYmeraUVhAUm32DJmnRL_oOvwfSlI")
BASE_URL = os.environ.get("BASE_URL", "https://your-app-name.koyeb.app")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("hls_files", exist_ok=True)
app.mount("/hls", StaticFiles(directory="hls_files"), name="hls")

bot = Client("hls_converter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "👋 **Welcome to HLS Converter Bot!**\n\n"
        "Send or forward me any video file (`.mp4`, `.mkv`), and I will convert it into an `.m3u8` streaming link for you."
    )

@bot.on_message(filters.video | filters.document)
async def handle_video(client, message):
    status = await message.reply("📥 **Downloading video from Telegram...**")
    
    job_id = str(message.id)
    out_dir = f"hls_files/{job_id}"
    os.makedirs(out_dir, exist_ok=True)
    
    video_path = await message.download(file_name=f"{out_dir}/input.mp4")
    await status.edit_text("⚙️ **Converting video to HLS (.m3u8)... Please wait.**")
    
    m3u8_file = f"{out_dir}/playlist.m3u8"
    
    cmd = [
        "ffmpeg", "-i", video_path,
        "-codec", "copy",
        "-start_number", "0",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-f", "hls", m3u8_file
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    
    if os.path.exists(m3u8_file):
        if os.path.exists(video_path):
            os.remove(video_path)
            
        stream_link = f"{BASE_URL.rstrip('/')}/hls/{job_id}/playlist.m3u8"
        await status.edit_text(
            f"✅ **Conversion Complete!**\n\n"
            f"🔗 **HLS Playlist Link:**\n`{stream_link}`\n\n"
            f"💡 *You can paste this link in Shaka Player, HLS.js, or any video web player.*"
        )
    else:
        await status.edit_text("❌ **Failed to convert video.** Please try another file format.")

async def start_all():
    port = int(os.environ.get("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    
    await bot.start()
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_all())
  
