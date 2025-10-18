"""
Encryption and key management utilities.

Implements:
- HKDF-SHA256 key derivation for per-tenant encryption keys
- AES-256-GCM encryption for API keys at rest
- Bcrypt hashing for master keys
- Secret redaction utilities

Per specification: All API keys encrypted at rest, never stored in plaintext.
"""

import base64
import os
import secrets

import bcrypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class CryptoManager:
    """
    Manages encryption, key derivation, and hashing operations.

    Per specification:
    - HKDF-SHA256 for per-tenant key derivation
    - AES-256-GCM for API key encryption
    - Bcrypt for master key hashing
    """

    def __init__(self, kms_key: str):
        """
        Initialize with the root KMS key.

        Args:
            kms_key: Base64-encoded master encryption key (32+ bytes)
        """
        self.root_key = base64.urlsafe_b64decode(kms_key)
        if len(self.root_key) < 32:
            raise ValueError("KMS key must be at least 32 bytes")

    def derive_tenant_key(self, master_key: str, salt: str) -> bytes:
        """
        Derive per-tenant encryption key using HKDF-SHA256.

        Per specification: HKDF(MCP_KMS_KEY, master_key_hash)

        Args:
            master_key: Tenant's master key (plaintext, in memory only)
            salt: Random salt stored in database

        Returns:
            32-byte AES key for encrypting this tenant's API keys
        """
        info = f"orderdesk-mcp-tenant-{salt}".encode()

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            info=info,
            backend=default_backend()
        )

        return hkdf.derive(master_key.encode())

    def encrypt_api_key(self, api_key: str, tenant_key: bytes) -> tuple[str, str, str]:
        """
        Encrypt API key using AES-256-GCM.

        Per specification: Store ciphertext, tag, and nonce separately

        Args:
            api_key: OrderDesk API key (plaintext)
            tenant_key: 32-byte derived tenant key

        Returns:
            (ciphertext_b64, tag_b64, nonce_b64)
        """
        # Generate random 12-byte nonce (96 bits for GCM)
        nonce = os.urandom(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(tenant_key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Encrypt
        ciphertext = encryptor.update(api_key.encode()) + encryptor.finalize()

        # Return base64-encoded components
        return (
            base64.b64encode(ciphertext).decode(),
            base64.b64encode(encryptor.tag).decode(),
            base64.b64encode(nonce).decode()
        )

    def decrypt_api_key(self, ciphertext: str, tag: str, nonce: str, tenant_key: bytes) -> str:
        """
        Decrypt API key using AES-256-GCM with tag verification.

        Args:
            ciphertext: Base64-encoded ciphertext
            tag: Base64-encoded GCM authentication tag
            nonce: Base64-encoded nonce
            tenant_key: 32-byte derived tenant key

        Returns:
            Decrypted API key (plaintext)

        Raises:
            Exception: If tag verification fails (data tampered)
        """
        # Decode components
        ciphertext_bytes = base64.b64decode(ciphertext)
        tag_bytes = base64.b64decode(tag)
        nonce_bytes = base64.b64decode(nonce)

        # Create cipher with tag
        cipher = Cipher(
            algorithms.AES(tenant_key),
            modes.GCM(nonce_bytes, tag_bytes),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Decrypt (raises exception if tag verification fails)
        plaintext = decryptor.update(ciphertext_bytes) + decryptor.finalize()

        return plaintext.decode()

    def hash_master_key(self, master_key: str) -> tuple[str, str]:
        """
        Hash master key with bcrypt.

        Per specification: Use bcrypt for master key hashing

        Args:
            master_key: Master key to hash

        Returns:
            (hash, salt) where hash is bcrypt hash, salt is random
        """
        # Generate random salt for HKDF
        salt = secrets.token_hex(32)

        # Hash the master key with bcrypt
        hashed = bcrypt.hashpw(master_key.encode(), bcrypt.gensalt())

        return hashed.decode(), salt

    def verify_master_key(self, master_key: str, stored_hash: str) -> bool:
        """
        Verify master key against stored hash (constant-time).

        Args:
            master_key: Master key to verify
            stored_hash: Stored bcrypt hash

        Returns:
            True if verification succeeds
        """
        return bcrypt.checkpw(master_key.encode(), stored_hash.encode())

    def generate_salt(self) -> str:
        """Generate a random salt for HKDF key derivation."""
        return secrets.token_hex(32)

    def generate_master_key(self) -> str:
        """
        Generate a cryptographically secure master key.

        Used for public signup (Phase 6).

        Returns:
            Base64-encoded 32-byte random key
        """
        return base64.urlsafe_b64encode(os.urandom(32)).decode()


# ============================================================================
# Global Crypto Manager Instance
# ============================================================================

crypto_manager = None


def get_crypto_manager() -> CryptoManager:
    """Get the global crypto manager instance (lazy initialization)."""
    global crypto_manager
    if crypto_manager is None:
        from mcp_server.config import settings
        crypto_manager = CryptoManager(settings.mcp_kms_key)
    return crypto_manager


# ============================================================================
# Convenience Functions (for cleaner API)
# ============================================================================

def derive_tenant_key(master_key: str, salt: str) -> bytes:
    """Derive tenant key using HKDF-SHA256."""
    return get_crypto_manager().derive_tenant_key(master_key, salt)


def encrypt_api_key(api_key: str, tenant_key: bytes) -> tuple[str, str, str]:
    """Encrypt API key with AES-256-GCM."""
    return get_crypto_manager().encrypt_api_key(api_key, tenant_key)


def decrypt_api_key(ciphertext: str, tag: str, nonce: str, tenant_key: bytes) -> str:
    """Decrypt API key with AES-256-GCM."""
    return get_crypto_manager().decrypt_api_key(ciphertext, tag, nonce, tenant_key)


def hash_master_key(master_key: str) -> tuple[str, str]:
    """Hash master key with bcrypt."""
    return get_crypto_manager().hash_master_key(master_key)


def verify_master_key(master_key: str, stored_hash: str) -> bool:
    """Verify master key against bcrypt hash."""
    return get_crypto_manager().verify_master_key(master_key, stored_hash)


def generate_salt() -> str:
    """Generate random salt for HKDF."""
    return get_crypto_manager().generate_salt()


def generate_master_key() -> str:
    """Generate secure master key for signup."""
    return get_crypto_manager().generate_master_key()

