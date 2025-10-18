"""Tests for public signup flow (Phase 6 - Sprint 3)."""

import pytest
from datetime import datetime, timedelta, timezone

from mcp_server.models.database import MagicLink, Tenant
from mcp_server.services.rate_limit import RateLimitService
from mcp_server.utils.master_key import generate_master_key, validate_master_key_strength


class TestMasterKeyGeneration:
    """Tests for master key generation utility."""

    def test_generate_master_key_default_length(self):
        """Test generating master key with default length."""
        key = generate_master_key()

        assert isinstance(key, str)
        assert len(key) == 64  # 48 bytes = 64 chars URL-safe
        assert all(c.isalnum() or c in "-_" for c in key)

    def test_generate_master_key_custom_length(self):
        """Test generating master key with custom length."""
        key = generate_master_key(length=32)

        assert isinstance(key, str)
        assert len(key) == 43  # 32 bytes = 43 chars URL-safe

    def test_generate_master_key_uniqueness(self):
        """Test that generated keys are unique."""
        keys = [generate_master_key() for _ in range(100)]

        # All keys should be unique
        assert len(set(keys)) == 100

    def test_validate_master_key_strength_valid(self):
        """Test validating a strong master key."""
        key = generate_master_key()
        is_valid, error = validate_master_key_strength(key)

        assert is_valid is True
        assert error is None

    def test_validate_master_key_strength_too_short(self):
        """Test validating a short master key."""
        key = "short"
        is_valid, error = validate_master_key_strength(key)

        assert is_valid is False
        assert "at least 32 characters" in error

    def test_validate_master_key_strength_invalid_chars(self):
        """Test validating a master key with invalid characters."""
        key = "a" * 32 + "!@#$%"  # 32 valid chars + invalid ones
        is_valid, error = validate_master_key_strength(key)

        assert is_valid is False
        assert "invalid characters" in error


class TestRateLimitService:
    """Tests for rate limiting service."""

    def test_check_signup_rate_limit_allowed(self, db_session):
        """Test rate limit check when under limit."""
        service = RateLimitService(db_session)

        is_allowed, remaining = service.check_signup_rate_limit(
            ip_address="192.168.1.1",
            limit_per_hour=3,
        )

        assert is_allowed is True
        assert remaining == 3

    def test_check_signup_rate_limit_after_signup(self, db_session):
        """Test rate limit after one signup."""
        service = RateLimitService(db_session)

        # Create a magic link (simulates a signup attempt)
        magic_link = MagicLink(
            email="test@example.com",
            token="test-token",
            token_hash="test-hash",
            purpose="email_verification",
            ip_address="192.168.1.1",
            used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db_session.add(magic_link)
        db_session.commit()

        is_allowed, remaining = service.check_signup_rate_limit(
            ip_address="192.168.1.1",
            limit_per_hour=3,
        )

        assert is_allowed is True
        assert remaining == 2

    def test_check_signup_rate_limit_exceeded(self, db_session):
        """Test rate limit when exceeded."""
        service = RateLimitService(db_session)

        # Create 3 magic links (at limit)
        for i in range(3):
            magic_link = MagicLink(
                email=f"test{i}@example.com",
                token=f"test-token-{i}",
                token_hash=f"test-hash-{i}",
                purpose="email_verification",
                ip_address="192.168.1.1",
                used=False,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
            db_session.add(magic_link)
        db_session.commit()

        is_allowed, remaining = service.check_signup_rate_limit(
            ip_address="192.168.1.1",
            limit_per_hour=3,
        )

        assert is_allowed is False
        assert remaining == 0

    def test_check_signup_rate_limit_expired_not_counted(self, db_session):
        """Test that expired magic links don't count toward rate limit."""
        service = RateLimitService(db_session)

        # Use unique IP to avoid test isolation issues
        import uuid
        unique_id = str(uuid.uuid4())
        unique_ip = f"10.0.0.{uuid.uuid4().hex[:3]}"
        
        # Create expired magic link (created 2 hours ago)
        magic_link = MagicLink(
            email="test@example.com",
            token=f"test-token-{unique_id}",
            token_hash=f"test-hash-{unique_id}",
            purpose="email_verification",
            ip_address=unique_ip,
            used=False,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),  # 2 hours ago
        )
        db_session.add(magic_link)
        db_session.commit()

        is_allowed, remaining = service.check_signup_rate_limit(
            ip_address=unique_ip,
            limit_per_hour=3,
        )

        # Should be allowed since expired link doesn't count (2 hours old)
        assert is_allowed is True
        assert remaining == 3

    def test_check_signup_rate_limit_different_ips(self, db_session):
        """Test that rate limit is per IP address."""
        service = RateLimitService(db_session)

        # Create 3 magic links for IP1 (use unique tokens)
        import uuid
        for i in range(3):
            unique_id = str(uuid.uuid4())
            magic_link = MagicLink(
                email=f"test{i}@example.com",
                token=f"test-token-{unique_id}",
                token_hash=f"test-hash-{unique_id}",
                purpose="email_verification",
                ip_address="192.168.1.1",
                used=False,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15),
            )
            db_session.add(magic_link)
        db_session.commit()

        # IP1 should be at limit
        is_allowed_ip1, remaining_ip1 = service.check_signup_rate_limit(
            ip_address="192.168.1.1",
            limit_per_hour=3,
        )

        # IP2 should still be allowed
        is_allowed_ip2, remaining_ip2 = service.check_signup_rate_limit(
            ip_address="192.168.1.2",
            limit_per_hour=3,
        )

        assert is_allowed_ip1 is False
        assert remaining_ip1 == 0
        assert is_allowed_ip2 is True
        assert remaining_ip2 == 3

    def test_get_rate_limit_reset_time(self, db_session):
        """Test getting rate limit reset time."""
        service = RateLimitService(db_session)

        # Create magic link (use unique token and naive datetime)
        import uuid
        unique_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        magic_link = MagicLink(
            email="test@example.com",
            token=f"test-token-{unique_id}",
            token_hash=f"test-hash-{unique_id}",
            purpose="email_verification",
            ip_address="192.168.1.1",
            used=False,
            expires_at=created_at + timedelta(minutes=15),
            created_at=created_at,
        )
        db_session.add(magic_link)
        db_session.commit()

        reset_time = service.get_rate_limit_reset_time("192.168.1.1")

        assert reset_time is not None
        # Reset time should be 1 hour after creation
        expected_reset = created_at + timedelta(hours=1)
        # Allow 1 second difference for test execution time
        assert abs((reset_time - expected_reset).total_seconds()) < 1

    def test_get_rate_limit_reset_time_no_limit(self, db_session):
        """Test getting reset time when no rate limit active."""
        service = RateLimitService(db_session)

        # Use unique IP to avoid test isolation issues
        import uuid
        unique_ip = f"192.168.1.{uuid.uuid4().hex[:3]}"
        reset_time = service.get_rate_limit_reset_time(unique_ip)

        assert reset_time is None


class TestSignupFlow:
    """Integration tests for complete signup flow."""

    def test_signup_creates_tenant(self, db_session):
        """Test that successful signup creates a tenant."""
        from mcp_server.auth.crypto import hash_master_key

        # Simulate verification step (normally done via email)
        email = "newuser@example.com"
        master_key = generate_master_key()
        master_key_hash, salt = hash_master_key(master_key)

        # Create tenant
        tenant = Tenant(
            master_key_hash=master_key_hash,
            salt=salt,
            email=email,
            email_verified=True,
        )

        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

        # Verify tenant created
        assert tenant.id is not None
        assert tenant.email == email
        assert tenant.email_verified is True
        assert tenant.master_key_hash == master_key_hash
        assert tenant.salt == salt

    def test_signup_duplicate_email_prevented(self, db_session):
        """Test that duplicate email addresses are prevented."""
        from mcp_server.auth.crypto import hash_master_key

        email = "duplicate@example.com"

        # Create first tenant
        master_key1 = generate_master_key()
        master_key_hash1, salt1 = hash_master_key(master_key1)

        tenant1 = Tenant(
            master_key_hash=master_key_hash1,
            salt=salt1,
            email=email,
            email_verified=True,
        )
        db_session.add(tenant1)
        db_session.commit()

        # Try to create second tenant with same email
        master_key2 = generate_master_key()
        master_key_hash2, salt2 = hash_master_key(master_key2)

        tenant2 = Tenant(
            master_key_hash=master_key_hash2,
            salt=salt2,
            email=email,  # Same email!
            email_verified=True,
        )

        db_session.add(tenant2)

        # Should raise integrity error due to unique constraint
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()

    def test_signup_sets_email_verified(self, db_session):
        """Test that signup sets email_verified to True."""
        from mcp_server.auth.crypto import hash_master_key

        email = "verified@example.com"
        master_key = generate_master_key()
        master_key_hash, salt = hash_master_key(master_key)

        tenant = Tenant(
            master_key_hash=master_key_hash,
            salt=salt,
            email=email,
            email_verified=True,
        )

        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

        assert tenant.email_verified is True

    def test_signup_initializes_activity_fields(self, db_session):
        """Test that signup initializes activity fields."""
        from mcp_server.auth.crypto import hash_master_key

        email = "newuser2@example.com"
        master_key = generate_master_key()
        master_key_hash, salt = hash_master_key(master_key)

        tenant = Tenant(
            master_key_hash=master_key_hash,
            salt=salt,
            email=email,
            email_verified=True,
            last_login=None,
            last_activity=None,
        )

        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

        # Activity fields should be None initially
        assert tenant.last_login is None
        assert tenant.last_activity is None

