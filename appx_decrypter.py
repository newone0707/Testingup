import aiohttp
import logging
from custom_crypto import decrypt_appx_data
from base64 import b64decode
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def decrypt(enc):
    try:
        if not enc:
            return ""
        enc = b64decode(enc.split(':')[0])
        key = '638udh3829162018'.encode('utf-8')
        iv = 'fedcba9876543210'.encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception as e:
        return ""

def decode_base64(encoded_str):
    try:
        if not encoded_str:
            return ""
        decoded_bytes = base64.b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        return ""

import aiohttp
import asyncio

async def safe_fetch_json(url, headers):
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            h = dict(headers)
            if "User-Agent" not in h:
                h["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            async with session.get(url, headers=h) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    print(f"Failed API Fetch: Status {resp.status}, Body: {text}")
                    return None
    except Exception as e:
        import traceback
        print(f"Failed to fetch JSON from {url}: {e}\n{traceback.format_exc()}")
    return None

async def resolve_appx_link(encrypted_string):
    """
    Takes an ADX_ENC: string and returns the actual URL.
    For URLs, it returns them directly.
    For API payloads, it fetches fresh links from Appx to prevent expiration.
    """
    try:
        import re
        data = decrypt_appx_data(encrypted_string)
        
        if data["type"] == "url":
            url = data["url"]
            if url:
                url = re.sub(r'\.zip', '.m3u8', url, flags=re.IGNORECASE)
            if "key" in data:
                return f"{url}*{data['key']}"
            return url
            
        elif data["type"] == "api_file":
            api_base = data["a"]
            course_id = data["c"]
            folder_id = data["f"]
            fi = data["i"]
            token = data["t"]
            userid = data["u"]
            
            url = f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id={folder_id}&folder_wise_course=1"
            headers = {}
            if userid:
                url += f"&userid={userid}"
                headers["User-ID"] = userid
            if token:
                headers["Authorization"] = token
                headers["token"] = token
            headers["appx-version"] = "2"
            headers["device_type"] = "WEB"
            headers["Client-Service"] = "Appx"
            headers["source"] = "website"
            headers["Auth-Key"] = "appxapi"
                
            r4 = await safe_fetch_json(url, headers)
            if not r4 or not r4.get("data"):
                return None
                
            items = r4.get("data", [])
            for item in items:
                if str(item.get("id")) == str(fi):
                    item_link = item.get('file_link') or item.get('pdf_link')
                    if item_link:
                        if not item_link.startswith('http') and ':' in item_link:
                            dec = decrypt(item_link)
                            if dec: item_link = dec
                        if item_link:
                            item_link = re.sub(r'\.zip', '.m3u8', item_link, flags=re.IGNORECASE)
                        return item_link
            return None

        elif data["type"] == "api":
            api_base = data["a"]
            course_id = data["c"]
            fi = data["vi"]
            token = data["t"]
            userid = data["u"]
            
            # Fetch freshly signed DRM / MPD / m3u8 links directly from the official Appx backend!
            url = f"{api_base}/get/get_mpd_drm_links?videoid={fi}&folder_wise_course=1"
            headers = {}
            if userid:
                headers["User-ID"] = userid
            if token:
                headers["Authorization"] = token
                headers["token"] = token
            headers["appx-version"] = "2"
            headers["device_type"] = "WEB"
            headers["Client-Service"] = "Appx"
            headers["source"] = "website"
            headers["Auth-Key"] = "appxapi"
                
            r4 = await safe_fetch_json(url, headers)
            if r4 and r4.get("data"):
                drm_data = r4.get("data", [])
                if isinstance(drm_data, list) and len(drm_data) > 0:
                    path = drm_data[0].get("path", "")
                    if path:
                        decrypted_path = decrypt(path)
                        if decrypted_path:
                            decrypted_path = re.sub(r'\.zip', '.m3u8', decrypted_path, flags=re.IGNORECASE)
                            return decrypted_path
            
            # Fallback to fetchVideoDetailsById if get_mpd_drm_links fails
            url = f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&folder_wise_course=1&ytflag=1&video_id={fi}"
            if userid:
                url += f"&userid={userid}"
                
            r4 = await safe_fetch_json(url, headers)
            if not r4 or not r4.get("data"):
                return None
                
            jdata = r4.get("data")
            vl = jdata.get("download_link", "")
            fl = jdata.get("video_id", "")
            
            outputs = []
            
            if fl:
                dfl = decrypt(fl)
                if dfl:
                    dfl = re.sub(r'\.zip', '.m3u8', dfl, flags=re.IGNORECASE)
                    if not ('.m3u8' in dfl or '.mp4' in dfl or 'genomic' in dfl or '/' in dfl):
                        final_link = f"https://youtu.be/{dfl}"
                        outputs.append(final_link)

            if vl:
                dvl = decrypt(vl)
                if dvl:
                    dvl = re.sub(r'\.zip', '.m3u8', dvl, flags=re.IGNORECASE)
                    outputs.append(dvl)
            elif not fl:
                for link in jdata.get("encrypted_links", []):
                    a = link.get("path")
                    k = link.get("key")
                    if a and k:
                        k1 = decrypt(k)
                        k2 = decode_base64(k1)
                        da = decrypt(a)
                        if da:
                            da = re.sub(r'\.zip', '.m3u8', da, flags=re.IGNORECASE)
                            outputs.append(f"{da}*{k2}")
                            break
                    elif a:
                        if not a.startswith('http') and ':' in a:
                            da = decrypt(a)
                        else:
                            da = a
                        if da:
                            da = re.sub(r'\.zip', '.m3u8', da, flags=re.IGNORECASE)
                            outputs.append(da)
                            break

            for pdf_num in range(1, 3):
                pdf_link = jdata.get(f"pdf_link{'' if pdf_num == 1 else str(pdf_num)}", "")
                pdf_key = jdata.get(f"pdf{'_' if pdf_num == 1 else str(pdf_num)}_encryption_key", "")
                
                if pdf_link:
                    dp = ""
                    if not pdf_link.startswith('http') and ':' in pdf_link:
                        dp = decrypt(pdf_link)
                    else:
                        dp = pdf_link
                    
                    if dp:
                        dp = re.sub(r'\.zip', '.m3u8', dp, flags=re.IGNORECASE)
                        if pdf_key:
                            dpk = decrypt(pdf_key)
                            if dpk and dpk != "abcdefg":
                                outputs.append(f"{dp}*{dpk}")
                            else:
                                outputs.append(dp)
                        else:
                            outputs.append(dp)
            
            return outputs[0] if outputs else None
            
    except Exception as e:
        import traceback
        logging.error(f"Error resolving Appx link: {e}\n{traceback.format_exc()}")
        return None

