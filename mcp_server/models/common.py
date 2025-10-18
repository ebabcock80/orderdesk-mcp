"""Common data models, error types, and result envelopes for MCP responses."""

from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field

# ============================================================================
# Exception Types
# ============================================================================


class MCPError(Exception):
    """Base exception for all MCP server errors."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP error format."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class OrderDeskError(MCPError):
    """Error from OrderDesk API."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: int | None = None,
        response: dict | None = None,
        details: dict | None = None,
    ):
        # Build details dict
        error_details = details.copy() if details else {}
        if status_code is not None:
            error_details["status_code"] = status_code
        if response is not None:
            error_details["response"] = response

        super().__init__(
            code=code or "ORDERDESK_API_ERROR", message=message, details=error_details
        )


class ValidationError(MCPError):
    """Input validation error."""

    def __init__(
        self,
        message: str,
        missing_fields: list[str] | None = None,
        invalid_fields: dict[str, str] | None = None,
        example: dict[str, Any] | None = None,
    ):
        details: dict[str, Any] = {}
        if missing_fields:
            details["missing_fields"] = missing_fields
        if invalid_fields:
            details["invalid_fields"] = invalid_fields
        if example:
            details["example_request"] = example

        super().__init__(code="VALIDATION_ERROR", message=message, details=details)


class AuthError(MCPError):
    """Authentication or authorization error."""

    def __init__(self, message: str):
        super().__init__(code="AUTH_ERROR", message=message)


class ConflictError(MCPError):
    """Concurrency conflict during mutation."""

    def __init__(self, message: str, retries: int | None = None):
        super().__init__(
            code="CONFLICT_ERROR",
            message=message,
            details={"retries_attempted": retries} if retries else {},
        )


class RateLimitError(MCPError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            details={"retry_after_seconds": retry_after} if retry_after else {},
        )


class NotFoundError(MCPError):
    """Resource not found."""

    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource_type} not found: {identifier}",
            details={"resource_type": resource_type, "identifier": identifier},
        )


# ============================================================================
# Result Envelope
# ============================================================================

T = TypeVar("T")


class Result[T](BaseModel):
    """
    Standard result envelope for MCP responses.

    Provides consistent response format with status, data, and error fields.
    """

    status: Literal["success", "error"]
    data: T | None = None
    error: dict[str, Any] | None = None

    @classmethod
    def success(cls, data: T, **kwargs) -> "Result[T]":
        """Create successful result."""
        return cls(status="success", data=data, **kwargs)

    @classmethod
    def failure(cls, error: MCPError) -> "Result[T]":
        """Create error result from exception."""
        return cls(status="error", error=error.to_dict()["error"])


# ============================================================================
# Common Response Models
# ============================================================================


class StatusResponse(BaseModel):
    """Standard status response."""

    status: Literal["success", "error"]
    message: str
    execution_time: str | None = None


class PaginationInfo(BaseModel):
    """Pagination information for list responses."""

    page: int = Field(ge=1, description="Current page number")
    limit: int = Field(ge=1, le=250, description="Items per page")
    total: int | None = Field(None, description="Total items (if available)")
    has_more: bool | None = Field(None, description="Whether more pages exist")


# ============================================================================
# Helper Functions
# ============================================================================


def validation_error_response(
    detail: str,
    missing: list[str] | None = None,
    invalid: dict[str, str] | None = None,
    example: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a validation error response with helpful information.

    Per specification: Validation errors should list missing fields
    and provide a minimal valid example.
    """
    error = ValidationError(
        message=detail, missing_fields=missing, invalid_fields=invalid, example=example
    )
    return error.to_dict()
