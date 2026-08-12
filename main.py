import os
import time
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from pyrogram import Client, filters
from pyrogram.types import Message

# Configs
API_ID = int(os.environ.get("API_ID", 29008502))
API_HASH = os.environ.get("API_HASH", "0ec186387ca45429e36d77637743031e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Hugging Face URL configuration
BASE_URL = os.environ.get("SPACE_HOST", "http://localhost:7860")

os.makedirs("hls_files", exist_ok=True)
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/hls", StaticFiles(directory="hls_files"), name="hls")

# Pyrogram Client
bot = Client("hls_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

def humanbytes(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

async def progress_bar(current, total, status_msg: Message, last_update_time):
    now = time.time()
    if now - last_update_time[0] > 3 or current == total:
        last_update_time[0] = now
        percentage = (current / total) * 100
        completed = humanbytes(current)
        total_size = humanbytes(total)
        bar = "█" * int(10 * current // total) + "░" * (10 - int(10 * current // total))
        text = f"📥 **Downloading...**\n\n[{bar}] `{percentage:.1f}%`\n⚡ `{completed}` / `{total_size}`"
        try: await status_msg.edit_text(text, parse_mode="markdown")
        except: pass

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("👋 Bot is ready! Send any video file (up to 2GB+).")

@bot.on_message(filters.video | filters.document)
async def handle_video(client, message):
    status = await message.reply_text("📥 **Starting Download...**")
    job_id = str(message.id)
    out_dir = f"hls_files/{job_id}"
    os.makedirs(out_dir, exist_ok=True)
    input_path = f"{out_dir}/input.mp4"
    
    try:
        await message.download(file_name=input_path, progress=progress_bar, progress_args=(status, [time.time()]))
    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")
        return

    await status.edit_text("⚙️ **Converting to HLS...**")
    m3u8_file = f"{out_dir}/playlist.m3u8"
    cmd = ["ffmpeg", "-i", input_path, "-c", "copy", "-start_number", "0", "-hls_time", "10", "-hls_list_size", "0", "-f", "hls", m3u8_file]
    
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    
    if os.path.exists(m3u8_file):
        os.remove(input_path)
        stream_link = f"{BASE_URL}/hls/{job_id}/playlist.m3u8"
        await status.edit_text(f"✅ **Done!**\n\n🔗 `{stream_link}`")
    else:
        await status.edit_text("❌ Conversion failed.")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.start())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
    
