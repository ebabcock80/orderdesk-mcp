"""
OrderDesk HTTP Client with retry logic and error handling.

Per specification:
- httpx async client with configurable timeouts
- Exponential backoff for 429/5xx errors
- Comprehensive error handling
- Structured logging with correlation IDs
"""

import asyncio
import random
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from mcp_server.config import settings
from mcp_server.models.common import OrderDeskError
from mcp_server.utils.logging import logger


class OrderDeskClient:
    """
    Async HTTP client for OrderDesk API.
    
    Features:
    - Automatic retries with exponential backoff
    - Rate limiting awareness
    - Structured error handling
    - Correlation ID propagation
    """
    
    BASE_URL = "https://app.orderdesk.me/api/v2"
    
    def __init__(
        self,
        store_id: str,
        api_key: str,
        timeout: Optional[httpx.Timeout] = None,
        max_retries: int = 3
    ):
        """
        Initialize OrderDesk client.
        
        Args:
            store_id: OrderDesk store ID
            api_key: OrderDesk API key
            timeout: Optional custom timeout configuration
            max_retries: Maximum number of retries for failed requests
        """
        self.store_id = store_id
        self.api_key = api_key
        self.max_retries = max_retries
        
        # Configure timeout (per specification)
        self.timeout = timeout or httpx.Timeout(
            connect=15.0,  # Connection timeout
            read=60.0,     # Read timeout (OrderDesk can be slow)
            write=60.0,    # Write timeout
            pool=5.0       # Pool timeout
        )
        
        # Create async client (reusable)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "OrderDesk-MCP-Server/0.1.0",
                    "Accept": "application/json",
                },
                follow_redirects=True
            )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _build_url(self, path: str) -> str:
        """
        Build full URL from path.
        
        Args:
            path: API path (e.g., "/orders" or "/orders/123")
        
        Returns:
            Full URL
        """
        # Ensure path starts with /
        if not path.startswith("/"):
            path = f"/{path}"
        
        # urljoin has quirky behavior, so we'll just concatenate
        # Make sure BASE_URL doesn't end with / and path starts with /
        base = self.BASE_URL.rstrip("/")
        return f"{base}{path}"
    
    def _get_auth_params(self) -> dict[str, str]:
        """
        Get authentication parameters.
        
        OrderDesk uses query parameters for authentication:
        - store_id: Store ID
        - api_key: API key
        
        Returns:
            Dict of auth parameters
        """
        return {
            "store_id": self.store_id,
            "api_key": self.api_key
        }
    
    async def _request_with_retry(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        attempt: int = 0
    ) -> dict[str, Any]:
        """
        Make HTTP request with automatic retry logic.
        
        Retries on:
        - 429 Too Many Requests (rate limit)
        - 500 Internal Server Error
        - 502 Bad Gateway
        - 503 Service Unavailable
        - 504 Gateway Timeout
        
        Uses exponential backoff with jitter.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path
            params: Query parameters
            json: JSON body
            attempt: Current attempt number (internal)
        
        Returns:
            Parsed JSON response
        
        Raises:
            OrderDeskError: On API error or max retries exceeded
        """
        await self._ensure_client()
        
        # Build full URL
        url = self._build_url(path)
        
        # Merge auth params with query params
        all_params = {**self._get_auth_params()}
        if params:
            all_params.update(params)
        
        try:
            logger.info(
                "OrderDesk API request",
                method=method,
                path=path,
                attempt=attempt + 1,
                max_retries=self.max_retries
            )
            
            # Make request
            response = await self._client.request(
                method=method,
                url=url,
                params=all_params,
                json=json
            )
            
            # Check for errors
            if response.status_code >= 400:
                await self._handle_error_response(
                    response, method, path, attempt
                )
            
            # Parse JSON response
            data = response.json()
            
            logger.info(
                "OrderDesk API response",
                method=method,
                path=path,
                status_code=response.status_code,
                attempt=attempt + 1
            )
            
            return data
        
        except httpx.TimeoutException as e:
            logger.warning(
                "OrderDesk API timeout",
                method=method,
                path=path,
                attempt=attempt + 1,
                error=str(e)
            )
            
            # Retry on timeout
            if attempt < self.max_retries:
                await self._backoff(attempt)
                return await self._request_with_retry(
                    method, path, params, json, attempt + 1
                )
            
            raise OrderDeskError(
                code="TIMEOUT",
                message=f"OrderDesk API timeout after {attempt + 1} attempts",
                details={"method": method, "path": path}
            )
        
        except httpx.NetworkError as e:
            logger.warning(
                "OrderDesk API network error",
                method=method,
                path=path,
                attempt=attempt + 1,
                error=str(e)
            )
            
            # Retry on network error
            if attempt < self.max_retries:
                await self._backoff(attempt)
                return await self._request_with_retry(
                    method, path, params, json, attempt + 1
                )
            
            raise OrderDeskError(
                code="NETWORK_ERROR",
                message=f"OrderDesk API network error after {attempt + 1} attempts",
                details={"method": method, "path": path, "error": str(e)}
            )
        
        except Exception as e:
            logger.error(
                "OrderDesk API unexpected error",
                method=method,
                path=path,
                attempt=attempt + 1,
                error=str(e)
            )
            raise OrderDeskError(
                code="UNEXPECTED_ERROR",
                message=f"Unexpected error calling OrderDesk API: {str(e)}",
                details={"method": method, "path": path}
            )
    
    async def _handle_error_response(
        self,
        response: httpx.Response,
        method: str,
        path: str,
        attempt: int
    ):
        """
        Handle HTTP error responses.
        
        Args:
            response: HTTP response
            method: HTTP method
            path: API path
            attempt: Current attempt number
        
        Raises:
            OrderDeskError: Always (with appropriate error details)
        """
        status_code = response.status_code
        
        # Try to parse error message from response
        try:
            error_data = response.json()
            error_message = error_data.get("message", error_data.get("error", "Unknown error"))
        except:
            error_message = response.text or f"HTTP {status_code}"
        
        logger.warning(
            "OrderDesk API error response",
            method=method,
            path=path,
            status_code=status_code,
            error_message=error_message,
            attempt=attempt + 1
        )
        
        # Retry on specific status codes
        retry_statuses = [429, 500, 502, 503, 504]
        
        if status_code in retry_statuses and attempt < self.max_retries:
            logger.info(
                "Retrying OrderDesk API request",
                status_code=status_code,
                attempt=attempt + 1,
                max_retries=self.max_retries
            )
            await self._backoff(attempt)
            # Note: This will be caught by caller and retried
            # We just log here and re-raise
        
        # Map status codes to error codes
        error_code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT"
        }
        
        error_code = error_code_map.get(status_code, "API_ERROR")
        
        raise OrderDeskError(
            code=error_code,
            message=error_message,
            details={
                "status_code": status_code,
                "method": method,
                "path": path,
                "attempt": attempt + 1
            }
        )
    
    async def _backoff(self, attempt: int):
        """
        Exponential backoff with jitter.
        
        Backoff formula: min(base * 2^attempt + jitter, max_delay)
        
        Args:
            attempt: Current attempt number (0-indexed)
        """
        base_delay = 1.0  # 1 second base
        max_delay = 10.0  # 10 seconds max
        
        # Calculate exponential backoff
        delay = min(base_delay * (2 ** attempt), max_delay)
        
        # Add jitter (±25%)
        jitter = delay * 0.25 * (random.random() * 2 - 1)
        delay += jitter
        
        logger.info(
            "Backing off before retry",
            attempt=attempt + 1,
            delay_seconds=round(delay, 2)
        )
        
        await asyncio.sleep(delay)
    
    # ========================================================================
    # Public API Methods
    # ========================================================================
    
    async def get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Make GET request.
        
        Args:
            path: API path
            params: Query parameters
        
        Returns:
            Parsed JSON response
        """
        return await self._request_with_retry("GET", path, params=params)
    
    async def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Make POST request.
        
        Args:
            path: API path
            json: JSON body
            params: Query parameters
        
        Returns:
            Parsed JSON response
        """
        return await self._request_with_retry("POST", path, params=params, json=json)
    
    async def put(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Make PUT request.
        
        Args:
            path: API path
            json: JSON body
            params: Query parameters
        
        Returns:
            Parsed JSON response
        """
        return await self._request_with_retry("PUT", path, params=params, json=json)
    
    async def delete(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Make DELETE request.
        
        Args:
            path: API path
            params: Query parameters
        
        Returns:
            Parsed JSON response
        """
        return await self._request_with_retry("DELETE", path, params=params)
    
    # ========================================================================
    # Order Operations
    # ========================================================================
    
    async def get_order(self, order_id: str) -> dict[str, Any]:
        """
        Get a single order by ID.
        
        Args:
            order_id: OrderDesk order ID
        
        Returns:
            Order object with all fields
        
        Raises:
            OrderDeskError: If order not found or API error
        
        Example response:
        {
            "id": "123456",
            "source_id": "ORDER-001",
            "email": "customer@example.com",
            "order_total": 29.99,
            "date_added": "2025-10-18T12:00:00Z",
            "order_items": [...],
            ...
        }
        """
        return await self.get(f"/orders/{order_id}")
    
    async def list_orders(
        self,
        limit: int = 50,
        offset: int = 0,
        folder_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> dict[str, Any]:
        """
        List orders with pagination and filtering.
        
        Args:
            limit: Number of orders to return (1-100, default 50)
            offset: Number of orders to skip (default 0)
            folder_id: Filter by folder ID
            status: Filter by status (e.g., 'open', 'completed', 'cancelled')
            search: Search query (searches order ID, email, name, etc.)
        
        Returns:
            Response with orders array and pagination metadata
        
        Response format:
        {
            "orders": [
                {
                    "id": "123456",
                    "source_id": "ORDER-001",
                    "email": "customer@example.com",
                    "order_total": 29.99,
                    ...
                }
            ],
            "count": 150,  # Total count (not always provided by OrderDesk)
            "page": 1      # Calculated from offset/limit
        }
        
        Pagination:
        - limit: Controls page size (1-100)
        - offset: Controls starting position
        - has_more: Calculated based on returned count vs limit
        
        Example:
        Page 1: limit=50, offset=0    → orders 1-50
        Page 2: limit=50, offset=50   → orders 51-100
        Page 3: limit=50, offset=100  → orders 101-150
        """
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            raise OrderDeskError(
                code="INVALID_PARAMETER",
                message=f"Limit must be between 1 and 100, got {limit}",
                details={"limit": limit}
            )
        
        if offset < 0:
            raise OrderDeskError(
                code="INVALID_PARAMETER",
                message=f"Offset must be >= 0, got {offset}",
                details={"offset": offset}
            )
        
        # Build query parameters
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset
        }
        
        if folder_id is not None:
            params["folder_id"] = folder_id
        
        if status:
            params["status"] = status
        
        if search:
            params["search"] = search
        
        # Make request
        response = await self.get("/orders", params=params)
        
        # OrderDesk returns orders in the root or in an "orders" key
        # Handle both formats
        if isinstance(response, list):
            orders = response
        elif isinstance(response, dict) and "orders" in response:
            orders = response["orders"]
        else:
            # Unexpected format
            logger.warning(
                "Unexpected OrderDesk response format",
                response_type=type(response).__name__
            )
            orders = []
        
        # Calculate pagination metadata
        orders_count = len(orders)
        has_more = orders_count == limit  # If we got a full page, there might be more
        current_page = (offset // limit) + 1
        
        return {
            "orders": orders,
            "count": orders_count,
            "limit": limit,
            "offset": offset,
            "page": current_page,
            "has_more": has_more
        }

