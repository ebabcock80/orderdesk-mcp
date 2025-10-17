"""Test authentication and encryption."""

from fastapi import status

from mcp_server.auth.crypto import crypto_manager


def test_crypto_manager_key_derivation():
    """Test key derivation and encryption/decryption."""
    master_key = "test-master-key"
    salt = crypto_manager.generate_salt()

    # Derive tenant key
    tenant_key = crypto_manager.derive_tenant_key(master_key, salt.encode("utf-8"))
    assert len(tenant_key) == 32

    # Test encryption/decryption
    api_key = "test-api-key-12345"
    encrypted = crypto_manager.encrypt_api_key(api_key, tenant_key)
    decrypted = crypto_manager.decrypt_api_key(encrypted, tenant_key)

    assert decrypted == api_key
    assert encrypted != api_key


def test_master_key_hashing():
    """Test master key hashing and verification."""
    master_key = "test-master-key"

    # Hash master key
    hashed, salt = crypto_manager.hash_master_key(master_key)
    assert hashed != master_key
    assert len(salt) > 0

    # Verify master key
    assert crypto_manager.verify_master_key(master_key, hashed, salt)
    assert not crypto_manager.verify_master_key("wrong-key", hashed, salt)


def test_auth_middleware(client, master_key):
    """Test authentication middleware."""
    # Test without auth header
    response = client.get("/stores")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test with invalid auth header
    response = client.get("/stores", headers={"Authorization": "Invalid"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test with valid auth header (should auto-provision tenant)
    response = client.get("/stores", headers={"Authorization": f"Bearer {master_key}"})
    assert response.status_code == status.HTTP_200_OK


def test_health_endpoint_no_auth(client):
    """Test that health endpoint doesn't require authentication."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
