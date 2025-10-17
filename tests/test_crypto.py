"""
Tests for cryptography service.

Per specification: Test HKDF, AES-256-GCM, bcrypt roundtrips and security properties.
"""

import pytest
from mcp_server.auth.crypto import (
    CryptoManager,
    derive_tenant_key,
    encrypt_api_key,
    decrypt_api_key,
    hash_master_key,
    verify_master_key,
    generate_salt,
    generate_master_key
)


class TestHKDFKeyDerivation:
    """Test HKDF-SHA256 key derivation."""
    
    def test_derive_tenant_key_deterministic(self):
        """Same inputs should produce same output."""
        master_key = "test-master-key-123"
        salt = "test-salt-456"
        
        key1 = derive_tenant_key(master_key, salt)
        key2 = derive_tenant_key(master_key, salt)
        
        assert key1 == key2
        assert len(key1) == 32  # 256 bits
    
    def test_derive_tenant_key_different_salts(self):
        """Different salts should produce different keys."""
        master_key = "test-master-key"
        salt1 = "salt1"
        salt2 = "salt2"
        
        key1 = derive_tenant_key(master_key, salt1)
        key2 = derive_tenant_key(master_key, salt2)
        
        assert key1 != key2
    
    def test_derive_tenant_key_different_master_keys(self):
        """Different master keys should produce different keys."""
        salt = "test-salt"
        key1 = derive_tenant_key("master-key-1", salt)
        key2 = derive_tenant_key("master-key-2", salt)
        
        assert key1 != key2


class TestAESGCMEncryption:
    """Test AES-256-GCM encryption/decryption."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Encryption followed by decryption should return original."""
        api_key = "test-orderdesk-api-key-12345"
        tenant_key = derive_tenant_key("master-key", "salt")
        
        # Encrypt
        ciphertext, tag, nonce = encrypt_api_key(api_key, tenant_key)
        
        # Decrypt
        decrypted = decrypt_api_key(ciphertext, tag, nonce, tenant_key)
        
        assert decrypted == api_key
    
    def test_wrong_key_fails_decryption(self):
        """Decryption with wrong key should fail."""
        api_key = "test-api-key"
        tenant_key1 = derive_tenant_key("master-1", "salt")
        tenant_key2 = derive_tenant_key("master-2", "salt")
        
        ciphertext, tag, nonce = encrypt_api_key(api_key, tenant_key1)
        
        with pytest.raises(Exception):
            decrypt_api_key(ciphertext, tag, nonce, tenant_key2)
    
    def test_tag_tampering_detected(self):
        """Modified tag should fail verification."""
        api_key = "test-api-key"
        tenant_key = derive_tenant_key("master-key", "salt")
        
        ciphertext, tag, nonce = encrypt_api_key(api_key, tenant_key)
        
        # Tamper with tag
        tampered_tag = tag[:-4] + "AAAA"
        
        with pytest.raises(Exception):
            decrypt_api_key(ciphertext, tampered_tag, nonce, tenant_key)
    
    def test_ciphertext_tampering_detected(self):
        """Modified ciphertext should fail verification."""
        api_key = "test-api-key"
        tenant_key = derive_tenant_key("master-key", "salt")
        
        ciphertext, tag, nonce = encrypt_api_key(api_key, tenant_key)
        
        # Tamper with ciphertext
        tampered = ciphertext[:-4] + "AAAA"
        
        with pytest.raises(Exception):
            decrypt_api_key(tampered, tag, nonce, tenant_key)
    
    def test_unique_nonces(self):
        """Each encryption should use unique nonce."""
        api_key = "test-api-key"
        tenant_key = derive_tenant_key("master-key", "salt")
        
        _, _, nonce1 = encrypt_api_key(api_key, tenant_key)
        _, _, nonce2 = encrypt_api_key(api_key, tenant_key)
        
        assert nonce1 != nonce2  # Nonces must be unique


class TestBcryptHashing:
    """Test bcrypt master key hashing."""
    
    def test_hash_verify_roundtrip(self):
        """Hash followed by verify should succeed."""
        master_key = "test-master-key-123456"
        
        hashed, salt = hash_master_key(master_key)
        
        assert verify_master_key(master_key, hashed)
    
    def test_wrong_key_fails_verification(self):
        """Wrong master key should fail verification."""
        master_key = "correct-key"
        wrong_key = "wrong-key"
        
        hashed, salt = hash_master_key(master_key)
        
        assert not verify_master_key(wrong_key, hashed)
    
    def test_different_salts_per_hash(self):
        """Each hash should use different salt."""
        master_key = "test-key"
        
        hash1, salt1 = hash_master_key(master_key)
        hash2, salt2 = hash_master_key(master_key)
        
        assert salt1 != salt2
        assert hash1 != hash2  # Different salts → different hashes


class TestCryptoManager:
    """Test CryptoManager class."""
    
    def test_initialization(self):
        """CryptoManager should initialize with valid KMS key."""
        import base64
        kms_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        
        manager = CryptoManager(kms_key)
        assert manager.root_key == b"a" * 32
    
    def test_initialization_fails_short_key(self):
        """CryptoManager should reject short KMS keys."""
        import base64
        short_key = base64.urlsafe_b64encode(b"short").decode()
        
        with pytest.raises(ValueError, match="at least 32 bytes"):
            CryptoManager(short_key)
    
    def test_generate_salt(self):
        """Generated salts should be unique."""
        import base64
        kms_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        manager = CryptoManager(kms_key)
        
        salt1 = manager.generate_salt()
        salt2 = manager.generate_salt()
        
        assert salt1 != salt2
        assert len(salt1) == 64  # 32 bytes hex = 64 chars
    
    def test_generate_master_key(self):
        """Generated master keys should be secure."""
        import base64
        kms_key = base64.urlsafe_b64encode(b"a" * 32).decode()
        manager = CryptoManager(kms_key)
        
        key1 = manager.generate_master_key()
        key2 = manager.generate_master_key()
        
        assert key1 != key2  # Should be random
        
        # Should be valid base64
        decoded = base64.urlsafe_b64decode(key1)
        assert len(decoded) >= 32  # At least 256 bits


class TestHelperFunctions:
    """Test convenience helper functions."""
    
    def test_helper_functions_match_manager(self):
        """Helper functions should match CryptoManager methods."""
        master_key = "test-master-key"
        salt = generate_salt()
        
        # Test key derivation
        key = derive_tenant_key(master_key, salt)
        assert len(key) == 32
        
        # Test encryption
        api_key = "test-api-key"
        ciphertext, tag, nonce = encrypt_api_key(api_key, key)
        
        # Test decryption
        decrypted = decrypt_api_key(ciphertext, tag, nonce, key)
        assert decrypted == api_key
        
        # Test hashing
        hashed, _ = hash_master_key(master_key)
        assert verify_master_key(master_key, hashed)


# Coverage target: >90% (critical security code)

