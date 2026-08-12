import os
import time
import subprocess
import asyncio
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID", 29008502))
API_HASH = os.environ.get("API_HASH", "0ec186387ca45429e36d77637743031e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8860451513:AAFtgWhYmeraUVhAUm32DJmnRL_oOvwfSlI")

# In-memory session
bot = Client("hls_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Dummy web server to satisfy Render's Web Service port binding requirement
async def handle(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

def humanbytes(size):
    if not size: return "0 B"
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
        text = (
            f"📥 **Downloading video from Telegram...**\n\n"
            f"[{bar}] `{percentage:.1f}%`\n"
            f"⚡ **Progress:** `{completed}` / `{total_size}`"
        )
        try:
            await status_msg.edit_text(text, parse_mode="markdown")
        except Exception:
            pass

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "👋 **Bot is Active!**\n\n"
        "Send any video file, and it will be converted into HLS format."
    )

@bot.on_message(filters.video | filters.document | filters.animation)
async def handle_video(client, message):
    media = message.video or message.document or message.animation
    if not media:
        return

    status = await message.reply_text("📥 **Downloading video from Telegram...**", parse_mode="markdown")
    job_id = str(message.id)
    out_dir = f"streams/{job_id}"
    os.makedirs(out_dir, exist_ok=True)
    input_path = f"{out_dir}/input.mp4"
    
    try:
        await message.download(
            file_name=input_path,
            progress=progress_bar,
            progress_args=(status, [time.time()])
        )
    except Exception as e:
        await status.edit_text(f"❌ **Download Failed:** `{str(e)}`")
        return

    await status.edit_text("⚙️ **Converting video to HLS format...**", parse_mode="markdown")
    m3u8_file = f"{out_dir}/playlist.m3u8"
    
    cmd = [
        "ffmpeg", "-i", input_path,
        "-c", "copy",
        "-start_number", "0",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-f", "hls", m3u8_file
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    
    if os.path.exists(m3u8_file):
        if os.path.exists(input_path):
            os.remove(input_path)
            
        await status.edit_text(
            f"✅ **Conversion Complete!**\n\n"
            f"📁 **Job ID:** `{job_id}`\n"
            f"💡 HLS files are successfully generated on the server storage.",
            parse_mode="markdown"
        )
    else:
        await status.edit_text("❌ **Conversion failed.**")

async def main():
    await start_web_server()
    await bot.start()
    print("Web service and Telegram bot started successfully!")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
