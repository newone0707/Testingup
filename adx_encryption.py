import base64
import os
from cryptography.fernet import Fernet

class ADXEncryption:
    """
    ADX Encryption Setup for securely handling expiring links between Extractor and Uploader.
    """
    def __init__(self, secret_key=None):
        if secret_key:
            self.key = secret_key
        else:
            self.key = os.environ.get("ADX_SECRET_KEY", "kX-11V6oO5_P4s0K1YF_3-9oXg_vI74g_U_L-s2q1oY=").encode('utf-8')
            
        self.cipher = Fernet(self.key)

    def get_key(self) -> bytes:
        return self.key

    def encrypt(self, raw_url: str) -> str:
        """Encrypts a URL using ADX encryption to prevent tampering."""
        try:
            encrypted_bytes = self.cipher.encrypt(raw_url.encode('utf-8'))
            # Encode in base64 to make it safe to pass around
            return base64.b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            print(f"ADX Encryption Error: {e}")
            return ""

    def decrypt(self, encrypted_string: str) -> str:
        """Decrypts an ADX encrypted string back to the original URL."""
        try:
            encrypted_bytes = base64.b64decode(encrypted_string.encode('utf-8'))
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"ADX Decryption Error: {e}")
            return ""
