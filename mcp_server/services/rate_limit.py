"""
Rate limiting service with token bucket algorithm.

Implements:
- Per-tenant rate limiting (default: 120 RPM)
- Read vs Write differentiation (per Q11: reads 2x limit, writes 1x limit)
- Token bucket algorithm (per Q11: allow bursts up to 2x rate)
- Per-IP rate limiting for WebUI

Per specification: Prevent abuse while allowing reasonable burst patterns.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from mcp_server.config import settings
from mcp_server.models.common import RateLimitError
from mcp_server.utils.logging import logger


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Per Q11: Allow bursts up to 2x rate, then throttle.
    """

    capacity: int  # Maximum tokens (burst allowance)
    rate: float  # Tokens per second refill rate
    tokens: float  # Current tokens available
    last_refill: float  # Last refill timestamp

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Returns:
            True if tokens available, False if rate limited
        """
        # Refill tokens based on time elapsed
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))
        self.last_refill = now

        # Check if enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Calculate seconds until tokens available."""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.rate


class RateLimiter:
    """
    Rate limiter with token bucket algorithm.

    Features:
    - Per-tenant rate limiting
    - Read vs Write differentiation (Q11)
    - Per-IP rate limiting (WebUI)
    - Burst allowance (2x base rate)
    """

    def __init__(self):
        # Per-tenant buckets
        self._tenant_buckets: dict[str, TokenBucket] = {}

        # Per-IP buckets (for WebUI)
        self._ip_buckets: dict[str, dict[str, TokenBucket]] = defaultdict(dict)

        # Configuration from settings
        self.tenant_rpm = settings.rate_limit_rpm
        self.tenant_rate = self.tenant_rpm / 60.0  # Tokens per second
        self.tenant_capacity = self.tenant_rpm * 2  # 2x burst allowance

        # WebUI rate limits
        self.webui_login_limit = settings.webui_rate_limit_login
        self.webui_signup_limit = settings.webui_rate_limit_signup

    def _get_tenant_bucket(self, tenant_id: str) -> TokenBucket:
        """Get or create token bucket for tenant."""
        if tenant_id not in self._tenant_buckets:
            self._tenant_buckets[tenant_id] = TokenBucket(
                capacity=self.tenant_capacity,
                rate=self.tenant_rate,
                tokens=self.tenant_capacity,  # Start full
                last_refill=time.time(),
            )
        return self._tenant_buckets[tenant_id]

    def _get_ip_bucket(self, ip_address: str, limit_type: str, rpm: int) -> TokenBucket:
        """Get or create token bucket for IP address."""
        if limit_type not in self._ip_buckets[ip_address]:
            rate = rpm / 60.0
            self._ip_buckets[ip_address][limit_type] = TokenBucket(
                capacity=rpm, rate=rate, tokens=rpm, last_refill=time.time()
            )
        return self._ip_buckets[ip_address][limit_type]

    async def check_tenant_limit(
        self, tenant_id: str, operation_type: Literal["read", "write"] = "read"
    ) -> bool:
        """
        Check if tenant has capacity for operation.

        Per Q11: Read operations use 1 token, write operations use 2 tokens.

        Args:
            tenant_id: Tenant ID
            operation_type: 'read' or 'write'

        Returns:
            True if allowed, False if rate limited
        """
        bucket = self._get_tenant_bucket(tenant_id)

        # Write operations consume 2x tokens (per Q11)
        tokens_needed = 2 if operation_type == "write" else 1

        allowed = bucket.consume(tokens_needed)

        if not allowed:
            retry_after = int(bucket.time_until_available(tokens_needed)) + 1
            logger.warning(
                "Tenant rate limited",
                tenant_id=tenant_id,
                operation_type=operation_type,
                retry_after=retry_after,
            )

        return allowed

    async def check_ip_limit(
        self, ip_address: str, limit_type: Literal["login", "signup", "console"]
    ) -> bool:
        """
        Check if IP has capacity for WebUI operation.

        Args:
            ip_address: Client IP
            limit_type: 'login', 'signup', or 'console'

        Returns:
            True if allowed, False if rate limited
        """
        limits = {
            "login": self.webui_login_limit,
            "signup": self.webui_signup_limit,
            "console": settings.webui_rate_limit_api_console,
        }

        rpm = limits.get(limit_type, 60)
        bucket = self._get_ip_bucket(ip_address, limit_type, rpm)

        allowed = bucket.consume(1)

        if not allowed:
            retry_after = int(bucket.time_until_available(1)) + 1
            logger.warning(
                "IP rate limited",
                ip_address=ip_address,
                limit_type=limit_type,
                retry_after=retry_after,
            )

        return allowed

    async def require_tenant_limit(
        self, tenant_id: str, operation_type: Literal["read", "write"] = "read"
    ) -> None:
        """
        Require tenant rate limit check, raise if exceeded.

        Raises:
            RateLimitError: If rate limit exceeded
        """
        bucket = self._get_tenant_bucket(tenant_id)
        tokens_needed = 2 if operation_type == "write" else 1

        if not bucket.consume(tokens_needed):
            retry_after = int(bucket.time_until_available(tokens_needed)) + 1
            raise RateLimitError(
                f"Rate limit exceeded for tenant {tenant_id}. Try again in {retry_after} seconds.",
                retry_after=retry_after,
            )

    async def require_ip_limit(
        self, ip_address: str, limit_type: Literal["login", "signup", "console"]
    ) -> None:
        """
        Require IP rate limit check, raise if exceeded.

        Raises:
            RateLimitError: If rate limit exceeded
        """
        if not await self.check_ip_limit(ip_address, limit_type):
            raise RateLimitError(
                f"Too many {limit_type} attempts. Please try again later.",
                retry_after=60,
            )

    def reset(
        self, tenant_id: str | None = None, ip_address: str | None = None
    ) -> None:
        """
        Reset rate limit (for testing).

        Args:
            tenant_id: Reset specific tenant, or all if None
            ip_address: Reset specific IP, or all if None
        """
        if tenant_id:
            self._tenant_buckets.pop(tenant_id, None)
        elif ip_address:
            self._ip_buckets.pop(ip_address, None)
        else:
            self._tenant_buckets.clear()
            self._ip_buckets.clear()


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance (lazy initialization)."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
