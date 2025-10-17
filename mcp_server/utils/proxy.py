"""Proxy header parsing and trust utilities."""

import ipaddress

from fastapi import Request


def get_real_client_ip(request: Request) -> str:
    """Get the real client IP address, considering proxy headers."""
    # If not trusting proxy, use direct connection IP
    if not request.app.state.settings.trust_proxy:
        return request.client.host if request.client else "unknown"

    # Check various proxy headers in order of preference
    headers_to_check = [
        "CF-Connecting-IP",  # Cloudflare
        "X-Forwarded-For",   # Standard proxy header
        "X-Real-IP",         # Nginx
        "X-Client-IP",       # Apache
    ]

    for header in headers_to_check:
        value = request.headers.get(header)
        if value:
            # X-Forwarded-For can contain multiple IPs, take the first one
            if header == "X-Forwarded-For":
                value = value.split(",")[0].strip()

            # Validate IP address
            try:
                ipaddress.ip_address(value)
                return value
            except ValueError:
                continue

    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"


def get_protocol(request: Request) -> str:
    """Get the protocol (http/https) considering proxy headers."""
    # If not trusting proxy, use request URL scheme
    if not request.app.state.settings.trust_proxy:
        return request.url.scheme

    # Check X-Forwarded-Proto header
    proto = request.headers.get("X-Forwarded-Proto")
    if proto:
        return proto.lower()

    # Fallback to request URL scheme
    return request.url.scheme


def should_add_hsts(request: Request) -> bool:
    """Determine if HSTS header should be added."""
    return get_protocol(request) == "https"


def get_cloudflare_ray(request: Request) -> str | None:
    """Get Cloudflare Ray ID if present."""
    return request.headers.get("CF-Ray")
