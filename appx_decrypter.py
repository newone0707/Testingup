import aiohttp
import logging
from custom_crypto import decrypt_appx_data
from enc import decrypt, decode_base64

async def safe_fetch_json(url, headers):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logging.error(f"Failed to fetch JSON from {url}: {e}")
    return None

async def resolve_appx_link(encrypted_string):
    """
    Takes an ADX_ENC: string and returns the actual URL.
    For URLs, it returns them directly.
    For API payloads, it fetches fresh links from Appx to prevent expiration.
    """
    try:
        data = decrypt_appx_data(encrypted_string)
        
        if data["type"] == "url":
            url = data["url"]
            if "key" in data:
                return f"{url}*{data['key']}"
            return url
            
        elif data["type"] == "api":
            api_base = data["a"]
            course_id = data["c"]
            fi = data["vi"]
            token = data["t"]
            userid = data["u"]
            
            url = f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&folder_wise_course=1&ytflag=1&video_id={fi}"
            headers = {}
            if userid:
                url += f"&userid={userid}"
                headers["User-ID"] = userid
            if token:
                headers["Authorization"] = token
                headers["token"] = token
                
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
                    if '.m3u8' in dfl or '.mp4' in dfl or 'genomic' in dfl or '/' in dfl:
                        final_link = f"https://appxsignurl.vercel.app/appx/{dfl}?appxv=3"
                    else:
                        final_link = f"https://youtu.be/{dfl}"
                    outputs.append(final_link)

            if vl:
                dvl = decrypt(vl)
                if dvl:
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
                            outputs.append(f"{da}*{k2}")
                            break
                    elif a:
                        if not a.startswith('http') and ':' in a:
                            da = decrypt(a)
                        else:
                            da = a
                        if da:
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
        logging.error(f"Error resolving Appx link: {e}")
        return None
