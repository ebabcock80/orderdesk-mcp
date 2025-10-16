"""Encryption and key management utilities."""

import base64
import hashlib
import secrets
from typing import Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from passlib.context import CryptContext

from mcp_server.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class CryptoManager:
    """Manages encryption, key derivation, and hashing operations."""

    def __init__(self, kms_key: str):
        """Initialize with the root KMS key."""
        self.root_key = base64.urlsafe_b64decode(kms_key)

    def derive_tenant_key(self, master_key: str, salt: bytes) -> bytes:
        """Derive a per-tenant encryption key using HKDF."""
        master_key_bytes = master_key.encode("utf-8")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"orderdesk-tenant-key",
        )
        return hkdf.derive(master_key_bytes)

    def hash_master_key(self, master_key: str) -> Tuple[str, str]:
        """Hash a master key with a random salt."""
        salt = secrets.token_hex(32)
        hashed = pwd_context.hash(master_key + salt)
        return hashed, salt

    def verify_master_key(self, master_key: str, hashed: str, salt: str) -> bool:
        """Verify a master key against its hash and salt."""
        return pwd_context.verify(master_key + salt, hashed)

    def encrypt_api_key(self, api_key: str, tenant_key: bytes) -> str:
        """Encrypt an API key using the tenant's derived key."""
        fernet = Fernet(base64.urlsafe_b64encode(tenant_key))
        encrypted = fernet.encrypt(api_key.encode("utf-8"))
        return base64.urlsafe_b64encode(encrypted).decode("utf-8")

    def decrypt_api_key(self, encrypted_api_key: str, tenant_key: bytes) -> str:
        """Decrypt an API key using the tenant's derived key."""
        fernet = Fernet(base64.urlsafe_b64encode(tenant_key))
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_api_key.encode("utf-8"))
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode("utf-8")

    def generate_salt(self) -> str:
        """Generate a random salt for key derivation."""
        return secrets.token_hex(32)


# Global crypto manager instance (lazy initialization)
crypto_manager = None

def get_crypto_manager():
    """Get the global crypto manager instance."""
    global crypto_manager
    if crypto_manager is None:
        from mcp_server.config import settings
        crypto_manager = CryptoManager(settings.mcp_kms_key)
    return crypto_manager
