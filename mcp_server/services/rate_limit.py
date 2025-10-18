"""Rate limiting service for signup and other operations."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from mcp_server.models.database import MagicLink
from mcp_server.utils.logging import logger


class RateLimitService:
    """Service for rate limiting signups and other operations."""

    def __init__(self, db: Session):
        self.db = db

    def check_signup_rate_limit(
        self,
        ip_address: str,
        limit_per_hour: int = 3,
    ) -> tuple[bool, int]:
        """
        Check if IP address has exceeded signup rate limit.

        Args:
            ip_address: Client IP address
            limit_per_hour: Maximum signups allowed per hour

        Returns:
            Tuple of (is_allowed, remaining_attempts)
            - is_allowed: True if signup is allowed
            - remaining_attempts: Number of signup attempts remaining
        """
        # Count signup attempts in the last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        count = (
            self.db.query(MagicLink)
            .filter(
                and_(
                    MagicLink.ip_address == ip_address,
                    MagicLink.purpose == "email_verification",
                    MagicLink.created_at > one_hour_ago,
                )
            )
            .count()
        )

        is_allowed = count < limit_per_hour
        remaining = max(0, limit_per_hour - count)

        if not is_allowed:
            logger.warning(
                "Signup rate limit exceeded",
                ip_address=ip_address,
                count=count,
                limit=limit_per_hour,
            )

        return is_allowed, remaining

    def get_rate_limit_reset_time(
        self,
        ip_address: str,
    ) -> datetime | None:
        """
        Get the time when rate limit will reset for an IP address.

        Args:
            ip_address: Client IP address

        Returns:
            Datetime when rate limit resets, or None if no limit active
        """
        # Find oldest magic link in the last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        oldest = (
            self.db.query(MagicLink)
            .filter(
                and_(
                    MagicLink.ip_address == ip_address,
                    MagicLink.purpose == "email_verification",
                    MagicLink.created_at > one_hour_ago,
                )
            )
            .order_by(MagicLink.created_at.asc())
            .first()
        )

        if oldest:
            # Rate limit resets 1 hour after oldest attempt
            return oldest.created_at + timedelta(hours=1)

        return None
