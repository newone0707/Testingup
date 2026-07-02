import os
import re
import zipfile
import shutil
import time
import mmap
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures
from curl_cffi import requests as cffi_requests
from math import ceil
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message
from io import BytesIO
from pathlib import Path  
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

def duration(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)

def get_mps_and_keys(api_url):
    response = requests.get(api_url)
    response_json = response.json()
    mpd = response_json.get('MPD')
    keys = response_json.get('KEYS')
    return mpd, keys
   
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka

async def pdf_download(url, file_name, chunk_size=1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name   
   

def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info


async def decrypt_and_merge_video(mpd_url, keys_string, output_path, output_name, quality="720"):
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        cmd1 = f'yt-dlp -f "bv[height<={quality}]+ba/b" -o "{output_path}/file.%(ext)s" --allow-unplayable-format --no-check-certificate --external-downloader aria2c "{mpd_url}"'
        print(f"Running command: {cmd1}")
        os.system(cmd1)
        
        avDir = list(output_path.iterdir())
        print(f"Downloaded files: {avDir}")
        print("Decrypting")

        video_decrypted = False
        audio_decrypted = False

        for data in avDir:
            if data.suffix == ".mp4" and not video_decrypted:
                cmd2 = f'mp4decrypt {keys_string} --show-progress "{data}" "{output_path}/video.mp4"'
                print(f"Running command: {cmd2}")
                os.system(cmd2)
                if (output_path / "video.mp4").exists():
                    video_decrypted = True
                data.unlink()
            elif data.suffix == ".m4a" and not audio_decrypted:
                cmd3 = f'mp4decrypt {keys_string} --show-progress "{data}" "{output_path}/audio.m4a"'
                print(f"Running command: {cmd3}")
                os.system(cmd3)
                if (output_path / "audio.m4a").exists():
                    audio_decrypted = True
                data.unlink()

        if not video_decrypted or not audio_decrypted:
            raise FileNotFoundError("Decryption failed: video or audio file not found.")

        cmd4 = f'ffmpeg -i "{output_path}/video.mp4" -i "{output_path}/audio.m4a" -c copy "{output_path}/{output_name}.mp4"'
        print(f"Running command: {cmd4}")
        os.system(cmd4)
        if (output_path / "video.mp4").exists():
            (output_path / "video.mp4").unlink()
        if (output_path / "audio.m4a").exists():
            (output_path / "audio.m4a").unlink()
        
        filename = output_path / f"{output_name}.mp4"

        if not filename.exists():
            raise FileNotFoundError("Merged video file not found.")

        cmd5 = f'ffmpeg -i "{filename}" 2>&1 | grep "Duration"'
        duration_info = os.popen(cmd5).read()
        print(f"Duration info: {duration_info}")

        return str(filename)

    except Exception as e:
        print(f"Error during decryption and merging: {str(e)}")
        raise

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"


async def download_video(url,cmd, name):
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    global failed_counter
    print(download_cmd)
    logging.info(download_cmd)
    k = subprocess.run(download_cmd, shell=True, capture_output=True, text=True)
    if k.returncode != 0:
        print(f"YT-DLP ERROR: {k.stderr}")
        with open("last_dl_error.txt", "w", encoding="utf-8") as f:
            f.write(str(k.stderr)[-500:])
    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        await download_video(url, cmd, name)
    failed_counter = 0
    try:
        if os.path.isfile(name):
            return name
        elif os.path.isfile(f"{name}.webm"):
            return f"{name}.webm"
        name = name.split(".")[0]
        if os.path.isfile(f"{name}.mp4"):
            return f"{name}.mp4"
        elif os.path.isfile(f"{name}.mkv"):
            return f"{name}.mkv"
        elif os.path.isfile(f"{name}.mp4.webm"):
            return f"{name}.mp4.webm"

        return None
    except FileNotFoundError as exc:
        return None


async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name, channel_id):
    reply = await bot.send_message(channel_id, f"Downloading pdf:\n<pre><code>{name}</code></pre>")
    time.sleep(1)
    start_time = time.time()
    await bot.send_document(ka, caption=cc1)
    count+=1
    await reply.delete (True)
    time.sleep(1)
    os.remove(ka)
    time.sleep(3) 


def get_key_bytes(key_str):
    if not key_str:
        return b''
    if isinstance(key_str, bytes):
        return key_str
    if isinstance(key_str, str):
        try:
            return bytes.fromhex(key_str)
        except ValueError:
            return key_str.encode('utf-8')
    return b''

def decrypt_file(file_path, key_str):
    if not os.path.exists(file_path):
        return False
    key = get_key_bytes(key_str)
    if not key:
        return True

    with open(file_path, "r+b") as f:
        num_bytes = min(28, os.path.getsize(file_path))
        with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
            for i in range(num_bytes):
                mmapped_file[i] ^= key[i] if i < len(key) else i
    return True  

def sync_download(url, output_path, referer):
    print(f"DEBUG sync_download URL: {url}")
    try:
        ref_header = referer + "/" if referer and not referer.endswith("/") else referer
        origin_header = referer[:-1] if referer and referer.endswith("/") else referer
        r = cffi_requests.get(url, stream=True, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': ref_header, 'Origin': origin_header}, impersonate="chrome")
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Direct Download Error: {e}")
        return False

def decrypt_chunk(data, key_str):
    key = get_key_bytes(key_str)
    if not key:
        return data
    data_bytearray = bytearray(data)
    num_bytes = min(28, len(data_bytearray))
    for i in range(num_bytes):
        data_bytearray[i] ^= key[i] if i < len(key) else i
    return bytes(data_bytearray)

def handle_zip_video(zip_path, name, key):
    temp_dir = f'{name}_temp'
    os.makedirs(temp_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        chunks = []
        for root, _, files in os.walk(temp_dir):
            for f in files:
                if f.endswith('.tsf') or f.endswith('.ts') or f.endswith('.m4s'):
                    chunks.append(os.path.join(root, f))
        
        if not chunks:
            print('No tsf chunks found in zip!')
            return None

        # Sort chunks numerically
        def get_num(f):
            m = re.search(r'\d+', os.path.basename(f))
            return int(m.group()) if m else 0
        chunks.sort(key=get_num)
        
        ts_output = f'{name}.ts'
        with open(ts_output, 'wb') as outfile:
            for chunk_file in chunks:
                with open(chunk_file, 'rb') as infile:
                    data = infile.read()
                    if key:
                        data = decrypt_chunk(data, key)
                    outfile.write(data)
        
        mp4_output = f'{name}.mp4'
        res = subprocess.run(f'ffmpeg -y -i "{ts_output}" -c copy -bsf:a aac_adtstoasc "{mp4_output}"', shell=True, capture_output=True)
        if res.returncode != 0:
            res = subprocess.run(f'ffmpeg -y -i "{ts_output}" -c copy "{mp4_output}"', shell=True, capture_output=True)
        
        if res.returncode != 0:
            os.rename(ts_output, mp4_output)
        else:
            if os.path.exists(ts_output): os.remove(ts_output)
            
        if os.path.exists(mp4_output):
            return mp4_output
        return None
    except Exception as e:
        print(f'Zip extraction error: {e}')
        return None
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def download_and_decrypt_video(url, cmd, name, key, referer=""):
    if not key:
        m = re.search(r'encrypted-([a-fA-F0-9]+)', url)
        if m:
            key = m.group(1)
            
    if ("encrypted.mkv" in url or "encrypted.mp4" in url or ".zip" in url or "appx" in url or "classx" in url or "akamai" in url) and not (".m3u8" in url or ".mpd" in url):
        is_zip = ".zip" in url
        output_path = f"{name}.zip" if is_zip else f"{name}.mp4"
        if ".mkv" in url:
            output_path = f"{name}.mkv"
        print(f"Using curl_cffi for direct download: {url}")
        success = await asyncio.to_thread(sync_download, url, output_path, referer)
        if success:
            video_path = output_path
        else:
            print("Direct download failed. Falling back...")
            if is_zip:
                download_cmd = f'aria2c -x 16 -j 32 -s 16 -k 1M -o "{output_path}" "{url}"'
                print(f"Downloading ZIP using aria2c: {download_cmd}")
                os.system(download_cmd)
                if os.path.exists(output_path):
                    video_path = output_path
                else:
                    video_path = None
            else:
                video_path = await download_video(url, cmd, name)
    else:
        video_path = await download_video(url, cmd, name)

    if video_path:
        if video_path.endswith('.zip') or ".zip" in url:
            # Handle Appx zipped tsf chunks
            print(f"Extracting and decrypting chunks from {video_path}...")
            mp4_path = await asyncio.to_thread(handle_zip_video, video_path, name, key)
            if os.path.exists(video_path): os.remove(video_path)
            if mp4_path:
                print(f"Zip {video_path} converted to mp4 successfully.")
                return mp4_path
            return None

        def is_valid_video_header(fp):
            try:
                with open(fp, 'rb') as f:
                    h = f.read(16)
                    if h.startswith(b'\x1a\x45\xdf\xa3') or b'ftyp' in h or b'moov' in h or h.startswith(b'\x47'):
                        return True
            except Exception:
                pass
            return False

        if is_valid_video_header(video_path):
            print(f"File {video_path} is already a valid unencrypted video file. Skipping XOR decrypt.")
            return video_path

        decrypted = decrypt_file(video_path, key)
        if decrypted:
            print(f"File {video_path} decrypted successfully.")
            return video_path
        else:
            print(f"Failed to decrypt {video_path}.")  
            return None  

async def send_vid(bot: Client, m: Message, cc, filename, vidwatermark, thumb, name, prog, channel_id):
    subprocess.run(f'ffmpeg -i "{filename}" -ss 00:00:10 -vframes 1 "{filename}.jpg"', shell=True)
    await prog.delete (True)
    reply1 = await bot.send_message(channel_id, f"**📩 Uploading Video 📩:-**\n<blockquote>**{name}**</blockquote>")
    reply = await m.reply_text(f"**Generate Thumbnail:**\n<blockquote>**{name}**</blockquote>")
    try:
        if thumb == "/d":
            thumbnail = f"{filename}.jpg"
        else:
            thumbnail = thumb  
        
        if vidwatermark == "/d":
            w_filename = f"{filename}"
        else:
            w_filename = f"w_{filename}"
            font_path = "vidwater.ttf"
            subprocess.run(
                f'ffmpeg -i "{filename}" -vf "drawtext=fontfile={font_path}:text=\'{vidwatermark}\':fontcolor=white@0.3:fontsize=h/6:x=(w-text_w)/2:y=(h-text_h)/2" -codec:a copy "{w_filename}"',
                shell=True
            )
            
    except Exception as e:
        await m.reply_text(str(e))

    dur = int(duration(w_filename))
    start_time = time.time()

    try:
        sent_msg = await bot.send_video(channel_id, w_filename, caption=cc, supports_streaming=True, height=720, width=1280, thumb=thumbnail, duration=dur, progress=progress_bar, progress_args=(reply, start_time))
    except Exception:
        sent_msg = await bot.send_document(channel_id, w_filename, caption=cc, progress=progress_bar, progress_args=(reply, start_time))
    os.remove(w_filename)
    await reply.delete(True)
    await reply1.delete(True)
    os.remove(f"{filename}.jpg")
    
    file_id = None
    if sent_msg.video:
        file_id = sent_msg.video.file_id
    elif sent_msg.document:
        file_id = sent_msg.document.file_id
    return file_id
