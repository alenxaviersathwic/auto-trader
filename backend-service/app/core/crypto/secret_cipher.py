import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config.settings import settings


class SecretCipher:
    """
    AES-GCM encryption and decryption utility for sensitive secrets
    (e.g., API secrets, broker tokens).
    Key is derived from MASTER_ENCRYPTION_KEY.
    Format: base64(nonce_12_bytes + ciphertext_and_tag)
    """

    def __init__(self, key: str = settings.MASTER_ENCRYPTION_KEY):
        # Derive fixed 32-byte key via SHA-256 to ensure exact 256-bit key size
        self._key = hashlib.sha256(key.encode("utf-8")).digest()
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypts plaintext string into base64-encoded AES-GCM payload."""
        if not plaintext:
            return ""
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, encoded_ciphertext: str) -> str:
        """Decrypts base64-encoded AES-GCM payload back to plaintext string."""
        if not encoded_ciphertext:
            return ""
        try:
            raw = base64.b64decode(encoded_ciphertext.encode("utf-8"))
            if len(raw) < 28:  # 12 bytes nonce + at least 16 bytes tag
                raise ValueError("Ciphertext too short")
            nonce = raw[:12]
            ciphertext = raw[12:]
            plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError("Failed to decrypt secret: invalid key or corrupted payload") from e


# Global singleton instance
cipher = SecretCipher()
