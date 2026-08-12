import os
import time
import subprocess
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID", 29008502))
API_HASH = os.environ.get("API_HASH", "0ec186387ca45429e36d77637743031e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

bot = Client("hls_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

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
        "Send any video file, and it will be converted into a permanent HLS stream link for your website."
    )

@bot.on_message(filters.video | filters.document)
async def handle_video(client, message):
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
        await status.edit_text("🚀 **Pushing stream files to GitHub Pages...**", parse_mode="markdown")
        if os.path.exists(input_path):
            os.remove(input_path)
            
        try:
            subprocess.run(["git", "config", "user.name", "HLS-Bot"], check=True)
            subprocess.run(["git", "config", "user.email", "bot@github.com"], check=True)
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", f"Add HLS stream {job_id}"], check=True)
            subprocess.run(["git", "push"], check=True)
            
            stream_link = f"https://cratexlive.github.io/file-to-hls-bot/streams/{job_id}/playlist.m3u8"
            
            await status.edit_text(
                f"✅ **Conversion Complete!**\n\n"
                f"🔗 **HLS Playlist Link:**\n`{stream_link}`\n\n"
                f"💡 **You can paste this link in Shaka Player on your website.**",
                parse_mode="markdown"
            )
        except Exception as e:
            await status.edit_text(f"❌ **Git Push Error:** `{str(e)}`")
    else:
        await status.edit_text("❌ **Conversion failed.**")

async def main():
    await bot.start()
    print("Bot started successfully!")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
