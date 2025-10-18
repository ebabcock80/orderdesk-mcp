"""Magic link generation and verification for email verification."""

import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy.orm import Session

from mcp_server.models.database import MagicLink
from mcp_server.utils.logging import logger


class MagicLinkService:
    """Service for generating and verifying magic links."""

    def __init__(self, db: Session):
        self.db = db

    def generate_magic_link(
        self,
        email: str,
        purpose: str = "email_verification",
        tenant_id: str | None = None,
        ip_address: str | None = None,
        expiry_seconds: int = 900,  # 15 minutes default
    ) -> tuple[str, str]:
        """
        Generate a magic link token for email verification.

        Args:
            email: Email address to verify
            purpose: Purpose of magic link ('email_verification', 'password_reset', etc.)
            tenant_id: Optional tenant ID (if user already exists)
            ip_address: Optional IP address for tracking
            expiry_seconds: Token expiry time in seconds (default: 15 minutes)

        Returns:
            Tuple of (token, token_hash) where token is the raw token to send via email
        """
        # Generate cryptographically secure random token
        token = secrets.token_urlsafe(32)  # 32 bytes = 43 chars URL-safe

        # Hash token for storage (never store plaintext tokens)
        token_hash = sha256(token.encode()).hexdigest()

        # Calculate expiry time
        expires_at = datetime.now(UTC) + timedelta(seconds=expiry_seconds)

        # Create magic link record
        magic_link = MagicLink(
            email=email,
            token=token,  # Store raw token temporarily (will be cleared on use)
            token_hash=token_hash,
            purpose=purpose,
            tenant_id=tenant_id,
            ip_address=ip_address,
            used=False,
            expires_at=expires_at,
        )

        self.db.add(magic_link)
        self.db.commit()

        logger.info(
            "Magic link generated",
            email=email,
            purpose=purpose,
            expires_at=expires_at,
        )

        return token, token_hash

    def verify_magic_link(
        self,
        token: str,
        purpose: str = "email_verification",
    ) -> tuple[bool, str | None, str | None]:
        """
        Verify a magic link token.

        Args:
            token: Raw token from URL
            purpose: Expected purpose of magic link

        Returns:
            Tuple of (success, email, tenant_id)
            - success: True if valid and not expired
            - email: Email address from magic link
            - tenant_id: Tenant ID if available
        """
        # Hash the provided token
        token_hash = sha256(token.encode()).hexdigest()

        # Find magic link by hash
        magic_link = (
            self.db.query(MagicLink)
            .filter(
                MagicLink.token_hash == token_hash,
                MagicLink.purpose == purpose,
                MagicLink.used == False,  # noqa: E712
            )
            .first()
        )

        if not magic_link:
            logger.warning(
                "Magic link not found or already used", token_hash=token_hash[:8]
            )
            return False, None, None

        # Check expiry (use naive datetime since SQLite stores naive)
        now = datetime.now(UTC).replace(tzinfo=None)
        if magic_link.expires_at < now:
            logger.warning(
                "Magic link expired",
                email=magic_link.email,
                expired_at=magic_link.expires_at,
            )
            return False, None, None

        # Mark as used
        magic_link.used = True  # type: ignore[assignment]
        magic_link.used_at = datetime.now(UTC)  # type: ignore[assignment]
        magic_link.token = ""  # type: ignore[assignment]  # Clear raw token after use
        self.db.commit()

        logger.info(
            "Magic link verified successfully",
            email=magic_link.email,
            purpose=purpose,
        )

        # Return the actual values (not Column objects)
        return (
            True,
            str(magic_link.email),
            str(magic_link.tenant_id) if magic_link.tenant_id else None,
        )

    def cleanup_expired_links(self) -> int:
        """
        Clean up expired magic links.

        Returns:
            Number of links deleted
        """
        # Use naive datetime since SQLite stores naive
        now = datetime.now(UTC).replace(tzinfo=None)
        count = self.db.query(MagicLink).filter(MagicLink.expires_at < now).delete()
        self.db.commit()

        if count > 0:
            logger.info("Cleaned up expired magic links", count=count)

        return count

    def get_active_link_count(self, email: str, purpose: str) -> int:
        """
        Get count of active (non-expired, non-used) magic links for an email.

        Args:
            email: Email address
            purpose: Link purpose

        Returns:
            Count of active links
        """
        # Use naive datetime since SQLite stores naive
        now = datetime.now(UTC).replace(tzinfo=None)
        return (
            self.db.query(MagicLink)
            .filter(
                MagicLink.email == email,
                MagicLink.purpose == purpose,
                MagicLink.used == False,  # noqa: E712
                MagicLink.expires_at > now,
            )
            .count()
        )
