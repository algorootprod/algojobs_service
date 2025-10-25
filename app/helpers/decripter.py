import base64
import hashlib
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.configs import config

shared_secret = config.SHARED_SECRET

encryption_key = hashlib.sha256(shared_secret.encode()).digest()

def decrypt_api_key(encrypted_str):
    iv_b64, auth_tag_b64, encrypted_b64 = encrypted_str.split('.')
    iv = base64.b64decode(iv_b64)
    auth_tag = base64.b64decode(auth_tag_b64)
    encrypted = base64.b64decode(encrypted_b64)

    # Ciphertext with auth tag appended (as required by AESGCM)
    ciphertext_with_tag = encrypted + auth_tag

    aesgcm = AESGCM(encryption_key)
    decrypted = aesgcm.decrypt(iv, ciphertext_with_tag, None)

    try:
        return json.loads(decrypted.decode())
    except json.JSONDecodeError:
        return decrypted.decode()

