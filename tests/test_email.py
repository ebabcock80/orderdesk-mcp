"""Tests for email service and magic links."""

from datetime import UTC, datetime, timedelta

import pytest

from mcp_server.email.magic_link import MagicLinkService
from mcp_server.email.providers import ConsoleEmailProvider, SMTPEmailProvider
from mcp_server.email.service import EmailMessage, EmailService
from mcp_server.models.database import MagicLink


class TestConsoleEmailProvider:
    """Tests for console email provider."""

    @pytest.mark.asyncio
    async def test_console_provider_sends_email(self):
        """Test that console provider can send emails."""
        provider = ConsoleEmailProvider(from_email="test@example.com")

        message = EmailMessage(
            to="recipient@example.com",
            subject="Test Subject",
            html_body="<p>Test HTML Body</p>",
            text_body="Test Text Body",
        )

        success = await provider.send_email(message)
        assert success is True

    @pytest.mark.asyncio
    async def test_console_provider_is_always_configured(self):
        """Test that console provider is always configured."""
        provider = ConsoleEmailProvider()
        assert await provider.is_configured() is True


class TestSMTPEmailProvider:
    """Tests for SMTP email provider."""

    @pytest.mark.asyncio
    async def test_smtp_provider_is_configured(self):
        """Test SMTP provider configuration check."""
        # Not configured (missing required fields)
        provider = SMTPEmailProvider(
            host="smtp.example.com",
            port=587,
            from_email=None,
        )
        assert await provider.is_configured() is False

        # Configured
        provider = SMTPEmailProvider(
            host="smtp.example.com",
            port=587,
            from_email="noreply@example.com",
        )
        assert await provider.is_configured() is True

    @pytest.mark.asyncio
    async def test_smtp_provider_configuration(self):
        """Test SMTP provider initialization."""
        provider = SMTPEmailProvider(
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="secret",
            use_tls=True,
            from_email="noreply@example.com",
        )

        assert provider.host == "smtp.example.com"
        assert provider.port == 587
        assert provider.username == "user@example.com"
        assert provider.password == "secret"
        assert provider.use_tls is True
        assert provider.from_email == "noreply@example.com"


class TestEmailService:
    """Tests for email service."""

    @pytest.mark.asyncio
    async def test_email_service_with_console_provider(self):
        """Test email service with console provider."""
        provider = ConsoleEmailProvider()
        service = EmailService(provider=provider)

        success = await service.send_email(
            to="test@example.com",
            subject="Test Subject",
            template_name="verification",
            context={
                "email": "test@example.com",
                "verification_link": "https://example.com/verify/token123",
            },
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_email_service_without_provider(self):
        """Test that email service fails gracefully without provider."""
        service = EmailService(provider=None)

        success = await service.send_email(
            to="test@example.com",
            subject="Test",
            template_name="verification",
            context={},
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_send_verification_email(self):
        """Test sending verification email."""
        provider = ConsoleEmailProvider()
        service = EmailService(provider=provider)

        success = await service.send_verification_email(
            to="test@example.com",
            verification_link="https://example.com/verify/token123",
            master_key="test-master-key-12345",
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_send_welcome_email(self):
        """Test sending welcome email."""
        provider = ConsoleEmailProvider()
        service = EmailService(provider=provider)

        success = await service.send_welcome_email(
            to="test@example.com",
            master_key="test-master-key-12345",
        )

        assert success is True

    def test_email_service_is_enabled(self):
        """Test checking if email service is enabled."""
        # Enabled
        provider = ConsoleEmailProvider()
        service = EmailService(provider=provider)
        assert service.is_enabled() is True

        # Disabled
        service = EmailService(provider=None)
        assert service.is_enabled() is False


class TestMagicLinkService:
    """Tests for magic link service."""

    def test_generate_magic_link(self, db_session):
        """Test generating a magic link."""
        service = MagicLinkService(db_session)

        token, token_hash = service.generate_magic_link(
            email="test@example.com",
            purpose="email_verification",
            ip_address="127.0.0.1",
            expiry_seconds=900,
        )

        # Check token format
        assert len(token) > 0
        assert len(token_hash) == 64  # SHA256 hex = 64 chars

        # Check database record
        magic_link = (
            db_session.query(MagicLink)
            .filter(MagicLink.token_hash == token_hash)
            .first()
        )

        assert magic_link is not None
        assert magic_link.email == "test@example.com"
        assert magic_link.purpose == "email_verification"
        assert magic_link.used is False
        assert magic_link.ip_address == "127.0.0.1"
        # Use naive datetime for comparison (SQLite stores naive)
        assert magic_link.expires_at > datetime.now(UTC).replace(tzinfo=None)

    def test_verify_magic_link_success(self, db_session):
        """Test verifying a valid magic link."""
        service = MagicLinkService(db_session)

        # Generate link
        token, token_hash = service.generate_magic_link(
            email="test@example.com",
            purpose="email_verification",
            expiry_seconds=900,
        )

        # Verify link
        success, email, tenant_id = service.verify_magic_link(
            token=token,
            purpose="email_verification",
        )

        assert success is True
        assert email == "test@example.com"
        assert tenant_id is None  # No tenant ID set in this test

        # Check that link is marked as used
        magic_link = (
            db_session.query(MagicLink)
            .filter(MagicLink.token_hash == token_hash)
            .first()
        )
        assert magic_link.used is True
        assert magic_link.used_at is not None
        assert magic_link.token == ""  # Token cleared after use

    def test_verify_magic_link_already_used(self, db_session):
        """Test that used magic link cannot be reused."""
        service = MagicLinkService(db_session)

        # Generate and use link
        token, _ = service.generate_magic_link(
            email="test@example.com",
            purpose="email_verification",
        )
        service.verify_magic_link(token=token, purpose="email_verification")

        # Try to use again
        success, email, tenant_id = service.verify_magic_link(
            token=token,
            purpose="email_verification",
        )

        assert success is False
        assert email is None
        assert tenant_id is None

    def test_verify_magic_link_expired(self, db_session):
        """Test that expired magic link is rejected."""
        service = MagicLinkService(db_session)

        # Generate link with very short expiry
        token, token_hash = service.generate_magic_link(
            email="test@example.com",
            purpose="email_verification",
            expiry_seconds=1,
        )

        # Manually set expiry to past (use naive datetime for SQLite)
        magic_link = (
            db_session.query(MagicLink)
            .filter(MagicLink.token_hash == token_hash)
            .first()
        )
        magic_link.expires_at = (datetime.now(UTC) - timedelta(seconds=10)).replace(
            tzinfo=None
        )
        db_session.commit()

        # Try to verify
        success, email, tenant_id = service.verify_magic_link(
            token=token,
            purpose="email_verification",
        )

        assert success is False
        assert email is None

    def test_verify_magic_link_wrong_purpose(self, db_session):
        """Test that magic link with wrong purpose is rejected."""
        service = MagicLinkService(db_session)

        # Generate link for email verification
        token, _ = service.generate_magic_link(
            email="test@example.com",
            purpose="email_verification",
        )

        # Try to verify with different purpose
        success, email, tenant_id = service.verify_magic_link(
            token=token,
            purpose="password_reset",  # Wrong purpose
        )

        assert success is False
        assert email is None

    def test_verify_magic_link_invalid_token(self, db_session):
        """Test that invalid token is rejected."""
        service = MagicLinkService(db_session)

        # Try to verify non-existent token
        success, email, tenant_id = service.verify_magic_link(
            token="invalid-token-12345",
            purpose="email_verification",
        )

        assert success is False
        assert email is None

    def test_cleanup_expired_links(self, db_session):
        """Test cleaning up expired magic links."""
        service = MagicLinkService(db_session)

        # Create expired link with long expiry to control when it expires
        token1, token_hash1 = service.generate_magic_link(
            email="expired@example.com",
            purpose="email_verification",
            expiry_seconds=3600,  # 1 hour (we'll manually expire it)
        )

        # Create valid link with very long expiry
        token2, token_hash2 = service.generate_magic_link(
            email="valid@example.com",
            purpose="email_verification",
            expiry_seconds=7200,  # 2 hours (definitely not expired)
        )

        # Manually expire first link (use naive datetime for SQLite)
        magic_link1 = (
            db_session.query(MagicLink)
            .filter(MagicLink.token_hash == token_hash1)
            .first()
        )
        magic_link1.expires_at = (datetime.now(UTC) - timedelta(seconds=10)).replace(
            tzinfo=None
        )
        db_session.commit()

        # Cleanup - should only delete the manually expired link
        service.cleanup_expired_links()

        # Expecting to cleanup the one expired link (plus maybe old test data)
        # Get remaining links for our specific test
        remaining_test_links = (
            db_session.query(MagicLink)
            .filter(MagicLink.token_hash.in_([token_hash1, token_hash2]))
            .all()
        )

        # Should only have the valid link remaining
        assert len(remaining_test_links) == 1
        assert remaining_test_links[0].token_hash == token_hash2

    def test_get_active_link_count(self, db_session):
        """Test getting count of active magic links."""
        service = MagicLinkService(db_session)

        # Use unique email to avoid test isolation issues
        import uuid

        email = f"test-{uuid.uuid4()}@example.com"

        # Initially no links
        assert service.get_active_link_count(email, "email_verification") == 0

        # Create 3 links
        service.generate_magic_link(email, "email_verification")
        service.generate_magic_link(email, "email_verification")
        service.generate_magic_link(email, "email_verification")

        assert service.get_active_link_count(email, "email_verification") == 3

        # Different purpose should not count
        assert service.get_active_link_count(email, "password_reset") == 0
