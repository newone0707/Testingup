import logging
import requests
import asyncio
import base64
import time
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from custom_crypto import decrypt_appx_data

_AES_KEY = b'638udh3829162018'
_AES_IV = b'fedcba9876543210'

# Simple TTL cache: { cache_key: (expires_at, fresh_url) }
_url_cache = {}
_CACHE_TTL = 600  # 10 minutes


def _aes_decrypt(enc_str):
    if not enc_str:
        return ""
    try:
        enc = b64decode(enc_str.split(':')[0])
        cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception:
        return ""


def _decode_b64(s):
    try:
        return base64.b64decode(s).decode('utf-8') if s else ""
    except Exception:
        return ""


def _cached_get(url, headers, timeout=15):
    cache_key = f"{url}|{headers.get('Authorization', '')}"
    now = time.time()
    if cache_key in _url_cache:
        expires, val = _url_cache[cache_key]
        if now < expires:
            return val
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            _url_cache[cache_key] = (now + _CACHE_TTL, data)
            return data
    except Exception as e:
        logging.warning(f"API fetch failed: {url[:80]} -> {e}")
    return None


async def resolve_appx_link(encrypted_string, override_token=None):
    """
    Resolve an ADX_ENC: string or a raw URL to a fresh download link.
    Returns the fresh URL (possibly with *key suffix) or None.
    """
    try:
        if not encrypted_string.startswith("ADX_ENC:"):
            return encrypted_string

        data = decrypt_appx_data(encrypted_string)

        if data["type"] == "url":
            url = data.get("url", "")
            key = data.get("key", "")
            if url:
                return f"{url}*{key}" if key else url
            return None

        if data["type"] in ("api", "api_file"):
            api_base = data.get("a", "")
            course_id = data.get("c", "")
            fi = data.get("vi") or data.get("i") or data.get("f", "")
            userid = data.get("u", "")
            token = override_token or data.get("t", "")

            headers = {
                "Client-Service": "Appx",
                "Auth-Key": "appxapi",
                "source": "website",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            if userid:
                headers["User-ID"] = userid
            if token:
                headers["Authorization"] = token
                headers["token"] = token

            # 1. Try fetchVideoDetailsById for the actual download link
            for ytflag in ('0', '1'):
                url = f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&video_id={fi}&ytflag={ytflag}&folder_wise_course=1"
                if userid:
                    url += f"&userid={userid}"
                r4 = _cached_get(url, headers)
                if r4 and r4.get("data"):
                    break

            if not r4 or not r4.get("data"):
                # Fallback: try without token (public courses)
                headers.pop("Authorization", None)
                headers.pop("token", None)
                for ytflag in ('0', '1'):
                    url = f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}&video_id={fi}&ytflag={ytflag}&folder_wise_course=1"
                    r4 = _cached_get(url, headers)
                    if r4 and r4.get("data"):
                        break

            if r4 and r4.get("data"):
                jdata = r4["data"]
                outputs = []

                # Priority 1: encrypted_links (path + key)
                for link in jdata.get("encrypted_links", []) or []:
                    raw_p = link.get("path", "") if isinstance(link, dict) else str(link)
                    raw_k = link.get("key", "") if isinstance(link, dict) else ""
                    if raw_p:
                        dec_p = raw_p if raw_p.startswith("http") else _aes_decrypt(raw_p)
                        if dec_p and dec_p.startswith("http"):
                            if raw_k:
                                dec_k = _aes_decrypt(raw_k)
                                if dec_k:
                                    outputs.append(f"{dec_p}*{dec_k}")
                                else:
                                    outputs.append(dec_p)
                            else:
                                outputs.append(dec_p)
                            break

                # Priority 2: file_link
                if not outputs:
                    fl = jdata.get("file_link", "") or ""
                    if fl:
                        dec_fl = fl if fl.startswith("http") else _aes_decrypt(fl)
                        if dec_fl and dec_fl.startswith("http"):
                            outputs.append(dec_fl)

                # Priority 3: download_link
                if not outputs:
                    dl = jdata.get("download_link", "") or ""
                    if dl:
                        dec_dl = dl if dl.startswith("http") else _aes_decrypt(dl)
                        if dec_dl and dec_dl.startswith("http"):
                            outputs.append(dec_dl)

                if outputs:
                    return outputs[0]

            # 2. If no video link, try get_mpd_drm_links for DRM content
            url = f"{api_base}/get/get_mpd_drm_links?videoid={fi}&folder_wise_course=1"
            r5 = _cached_get(url, headers)
            if r5 and r5.get("data"):
                drm_data = r5["data"]
                if isinstance(drm_data, list) and len(drm_data) > 0:
                    path = drm_data[0].get("path", "")
                    key = drm_data[0].get("key", "")
                    if path:
                        dec_path = path if path.startswith("http") else _aes_decrypt(path)
                        if dec_path:
                            if key:
                                dec_key = _aes_decrypt(key)
                                return f"{dec_path}*{dec_key}" if dec_key else dec_path
                            return dec_path

            return None

    except Exception as e:
        logging.error(f"resolve_appx_link error: {e}", exc_info=True)
        return None
