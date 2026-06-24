import base64
import json
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Secret key must be 32 bytes for AES-256
SECRET_KEY = hashlib.sha256(b"adx_custom_encryption_key_2026").digest()

def encrypt_appx_params(api, course_id, video_id, token, user_id):
    """
    Encrypts Appx API parameters into a secure base64 string.
    This prevents token leakage and enables dynamic fresh URL fetching.
    """
    data = {
        "type": "api",
        "a": str(api),
        "c": str(course_id),
        "vi": str(video_id),
        "t": str(token),
        "u": str(user_id)
    }
    return _encrypt_dict(data)

def encrypt_direct_url(url, key=None):
    """
    Encrypts a direct URL (like an image thumbnail or a direct PDF link).
    Optionally includes a decryption key if the PDF itself is encrypted.
    """
    data = {
        "type": "url",
        "url": str(url)
    }
    if key:
        data["key"] = str(key)
    return _encrypt_dict(data)

def _encrypt_dict(data):
    json_str = json.dumps(data)
    padded_data = pad(json_str.encode('utf-8'), AES.block_size)
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    encrypted_bytes = cipher.encrypt(padded_data)
    b64_enc = base64.b64encode(encrypted_bytes).decode('utf-8')
    return f"ADX_ENC:{b64_enc}"

def decrypt_appx_data(encrypted_str):
    """
    Decrypts the secure base64 string back into a dictionary of parameters.
    Returns the dictionary.
    """
    if not encrypted_str.startswith("ADX_ENC:"):
        raise ValueError("Invalid encryption format")
        
    b64_enc = encrypted_str.replace("ADX_ENC:", "")
    encrypted_bytes = base64.b64decode(b64_enc)
    
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    decrypted_padded_bytes = cipher.decrypt(encrypted_bytes)
    
    json_str = unpad(decrypted_padded_bytes, AES.block_size).decode('utf-8')
    return json.loads(json_str)

