import json
import sys
import os

try:
    from adx_encryption import ADXEncryption
except ImportError:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    from adx_encryption import ADXEncryption

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

def encrypt_api_file(api, course_id, folder_id, item_id, token, user_id):
    """
    Encrypts parameters for a single file inside a folder (like ZIPs or PDFs).
    This allows Testingup to dynamically fetch the folder contents and extract the freshly signed link.
    """
    data = {
        "type": "api_file",
        "a": str(api),
        "c": str(course_id),
        "f": str(folder_id),
        "i": str(item_id),
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
    adx = ADXEncryption()
    encrypted_str = adx.encrypt(json_str)
    return f"ADX_ENC:{encrypted_str}"

def decrypt_appx_data(encrypted_str):
    """
    Decrypts the secure base64 string back into a dictionary of parameters.
    Returns the dictionary.
    """
    if not encrypted_str.startswith("ADX_ENC:"):
        raise ValueError("Invalid encryption format")
        
    b64_enc = encrypted_str.replace("ADX_ENC:", "")
    adx = ADXEncryption()
    decrypted_str = adx.decrypt(b64_enc)
    return json.loads(decrypted_str)


