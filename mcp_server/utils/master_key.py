"""Master key generation utility for OrderDesk MCP Server."""

import secrets


def generate_master_key(length: int = 48) -> str:
    """
    Generate a cryptographically secure master key.

    Args:
        length: Number of random bytes (default: 48 = 64 chars URL-safe)

    Returns:
        URL-safe base64-encoded random string (43-64 chars depending on length)

    Examples:
        >>> key = generate_master_key()
        >>> len(key)
        64
        >>> isinstance(key, str)
        True
    """
    # Generate cryptographically secure random bytes
    # secrets.token_urlsafe(48) produces a 64-character URL-safe string
    return secrets.token_urlsafe(length)


def validate_master_key_strength(master_key: str) -> tuple[bool, str | None]:
    """
    Validate master key strength.

    Args:
        master_key: Master key to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if key meets requirements
        - error_message: None if valid, error string if invalid

    Requirements:
        - At least 32 characters long
        - Contains URL-safe characters only
    """
    if len(master_key) < 32:
        return False, "Master key must be at least 32 characters long"

    # Check for URL-safe characters (alphanumeric, -, _)
    allowed_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    )
    if not all(c in allowed_chars for c in master_key):
        return False, "Master key contains invalid characters"

    return True, None

