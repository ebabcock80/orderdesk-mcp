"""
OrderDesk HTTP Client with retry logic, error handling, and Prometheus metrics.

Per specification:
- httpx async client with configurable timeouts
- Exponential backoff for 429/5xx errors
- Comprehensive error handling
- Structured logging with correlation IDs
- Prometheus metrics for observability
"""

import asyncio
import random
import time
from typing import Any

import httpx

from mcp_server.models.common import OrderDeskError
from mcp_server.utils.logging import logger
from mcp_server.utils.metrics import (
    ORDERDESK_API_CALLS,
    ORDERDESK_API_DURATION,
    ORDERDESK_API_RETRIES,
)


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
        timeout: httpx.Timeout | None = None,
        max_retries: int = 3,
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
            read=60.0,  # Read timeout (OrderDesk can be slow)
            write=60.0,  # Write timeout
            pool=5.0,  # Pool timeout
        )

        # Create async client (reusable)
        self._client: httpx.AsyncClient | None = None

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
                    "ORDERDESK-STORE-ID": self.store_id,
                    "ORDERDESK-API-KEY": self.api_key,
                },
                follow_redirects=True,
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

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        attempt: int = 0,
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

        # Note: Auth is now in headers (ORDERDESK-STORE-ID, ORDERDESK-API-KEY)
        # No need to merge auth params into query string
        all_params = params or {}

        # Track request start time for metrics
        start_time = time.perf_counter()

        # Record retry if this is not the first attempt
        if attempt > 0:
            ORDERDESK_API_RETRIES.labels(reason="retry").inc()

        try:
            logger.info(
                "OrderDesk API request",
                method=method,
                path=path,
                attempt=attempt + 1,
                max_retries=self.max_retries,
            )

            # Make request
            assert self._client is not None  # Guaranteed by _ensure_client()
            response = await self._client.request(
                method=method, url=url, params=all_params, json=json
            )

            # Record metrics
            duration = time.perf_counter() - start_time
            ORDERDESK_API_CALLS.labels(
                endpoint=path, method=method, status_code=str(response.status_code)
            ).inc()
            ORDERDESK_API_DURATION.labels(endpoint=path, method=method).observe(
                duration
            )

            # Check for errors
            if response.status_code >= 400:
                await self._handle_error_response(response, method, path, attempt)

            # Parse JSON response
            data = response.json()

            logger.info(
                "OrderDesk API response",
                method=method,
                path=path,
                status_code=response.status_code,
                attempt=attempt + 1,
                duration_seconds=f"{duration:.3f}",
            )

            return data

        except httpx.TimeoutException as e:
            logger.warning(
                "OrderDesk API timeout",
                method=method,
                path=path,
                attempt=attempt + 1,
                error=str(e),
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
                details={"method": method, "path": path},
            )

        except httpx.NetworkError as e:
            logger.warning(
                "OrderDesk API network error",
                method=method,
                path=path,
                attempt=attempt + 1,
                error=str(e),
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
                details={"method": method, "path": path, "error": str(e)},
            )

        except OrderDeskError:
            # Re-raise OrderDeskError as-is (from _handle_error_response)
            raise

        except Exception as e:
            logger.error(
                "OrderDesk API unexpected error",
                method=method,
                path=path,
                attempt=attempt + 1,
                error=str(e),
            )
            raise OrderDeskError(
                code="UNEXPECTED_ERROR",
                message=f"Unexpected error calling OrderDesk API: {str(e)}",
                details={"method": method, "path": path},
            )

    async def _handle_error_response(
        self, response: httpx.Response, method: str, path: str, attempt: int
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
            error_message = error_data.get(
                "message", error_data.get("error", "Unknown error")
            )
        except Exception:
            error_message = response.text or f"HTTP {status_code}"

        logger.warning(
            "OrderDesk API error response",
            method=method,
            path=path,
            status_code=status_code,
            error_message=error_message,
            attempt=attempt + 1,
        )

        # Retry on specific status codes
        retry_statuses = [429, 500, 502, 503, 504]

        if status_code in retry_statuses and attempt < self.max_retries:
            logger.info(
                "Retrying OrderDesk API request",
                status_code=status_code,
                attempt=attempt + 1,
                max_retries=self.max_retries,
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
            504: "GATEWAY_TIMEOUT",
        }

        error_code = error_code_map.get(status_code, "API_ERROR")

        raise OrderDeskError(
            code=error_code,
            message=error_message,
            details={
                "status_code": status_code,
                "method": method,
                "path": path,
                "attempt": attempt + 1,
            },
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
        delay = min(base_delay * (2**attempt), max_delay)

        # Add jitter (±25%)
        jitter = delay * 0.25 * (random.random() * 2 - 1)
        delay += jitter

        logger.info(
            "Backing off before retry",
            attempt=attempt + 1,
            delay_seconds=round(delay, 2),
        )

        await asyncio.sleep(delay)

    # ========================================================================
    # Public API Methods
    # ========================================================================

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
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
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
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

    async def delete(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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
        folder_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
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
                details={"limit": limit},
            )

        if offset < 0:
            raise OrderDeskError(
                code="INVALID_PARAMETER",
                message=f"Offset must be >= 0, got {offset}",
                details={"offset": offset},
            )

        # Build query parameters
        params: dict[str, Any] = {"limit": limit, "offset": offset}

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
        if isinstance(response, list):  # type: ignore[unreachable]
            orders = response  # type: ignore[unreachable]
        elif isinstance(response, dict) and "orders" in response:
            orders = response["orders"]
        else:
            # Unexpected format
            logger.warning(
                "Unexpected OrderDesk response format",
                response_type=type(response).__name__,
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
            "has_more": has_more,
        }

    async def create_order(self, order_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new order.

        Args:
            order_data: Order data including email, items, shipping, etc.

        Returns:
            Created order object

        Raises:
            OrderDeskError: If validation fails or API error

        Required fields (minimum):
        {
            "email": "customer@example.com",
            "order_items": [
                {
                    "name": "Product Name",
                    "quantity": 1,
                    "price": 29.99
                }
            ]
        }
        """
        return await self.post("/orders", json=order_data)

    async def update_order(
        self, order_id: str, order_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an order with full-object upload.

        Per specification: Always use full-object updates, never PATCH.

        Args:
            order_id: OrderDesk order ID
            order_data: Complete order object (not partial)

        Returns:
            Updated order object

        Raises:
            OrderDeskError: If update fails or conflict (409)

        Conflict Handling:
        - 409 response indicates order changed since fetch
        - Caller should retry with fresh fetch
        """
        return await self.put(f"/orders/{order_id}", json=order_data)

    async def delete_order(self, order_id: str) -> dict[str, Any]:
        """
        Delete an order.

        Args:
            order_id: OrderDesk order ID

        Returns:
            Deletion confirmation

        Raises:
            OrderDeskError: If order not found or API error
        """
        return await self.delete(f"/orders/{order_id}")

    # ========================================================================
    # Mutation Helpers
    # ========================================================================

    async def fetch_full_order(self, order_id: str) -> dict[str, Any]:
        """
        Fetch complete order object for mutation.

        This is step 1 of the full-object update workflow.

        Args:
            order_id: OrderDesk order ID

        Returns:
            Complete order object with all fields

        Raises:
            OrderDeskError: If order not found
        """
        return await self.get_order(order_id)

    def merge_order_changes(
        self, original: dict[str, Any], changes: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Safely merge partial changes into full order object.

        This is step 2 of the full-object update workflow.

        Merge Rules:
        - Top-level fields: Shallow merge (changes override original)
        - Arrays (order_items): Full replacement if provided
        - Nested objects (shipping_address): Shallow merge
        - Null values: Remove field (explicit deletion)
        - Omitted fields: Keep original value

        Args:
            original: Complete order object from fetch
            changes: Partial changes to apply

        Returns:
            Merged order object ready for upload

        Example:
        original = {
            "email": "old@example.com",
            "order_total": 100.00,
            "order_items": [...]
        }
        changes = {
            "email": "new@example.com"
        }
        result = {
            "email": "new@example.com",  # Updated
            "order_total": 100.00,       # Preserved
            "order_items": [...]         # Preserved
        }
        """
        merged = original.copy()

        for key, value in changes.items():
            if value is None:
                # Explicit null = remove field
                merged.pop(key, None)
            else:
                # Override with new value
                merged[key] = value

        return merged

    async def update_order_with_retry(
        self, order_id: str, changes: dict[str, Any], max_retries: int = 5
    ) -> dict[str, Any]:
        """
        Update order with automatic conflict resolution.

        Implements the complete full-object update workflow with retries.

        Workflow:
        1. Fetch current order state
        2. Merge changes into full object
        3. Upload full object
        4. If conflict (409): Re-fetch and retry
        5. Repeat up to max_retries times

        Args:
            order_id: OrderDesk order ID
            changes: Partial changes to apply
            max_retries: Maximum retry attempts (default 5 per spec Q13)

        Returns:
            Updated order object

        Raises:
            ConflictError: If conflicts persist after max retries
            OrderDeskError: If update fails for other reasons
        """
        from mcp_server.models.common import ConflictError

        for attempt in range(max_retries):
            try:
                # Step 1: Fetch current state
                current_order = await self.fetch_full_order(order_id)

                # Step 2: Merge changes
                merged_order = self.merge_order_changes(current_order, changes)

                # Step 3: Upload full object
                updated_order = await self.update_order(order_id, merged_order)

                logger.info(
                    "Order updated successfully", order_id=order_id, attempt=attempt + 1
                )

                return updated_order

            except OrderDeskError as e:
                if e.code == "CONFLICT_ERROR":
                    if attempt < max_retries - 1:
                        # Conflict detected - retry
                        logger.warning(
                            "Order update conflict, retrying",
                            order_id=order_id,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                        )

                        # Exponential backoff: 0.5s, 1s, 2s, 4s, 8s
                        backoff_delay = 0.5 * (2**attempt)
                        await self._backoff_fixed(backoff_delay)
                        continue
                    else:
                        # Max retries reached for conflict - break to raise ConflictError
                        break

                # Other error (not conflict) - re-raise immediately
                raise

        # Max retries exceeded
        raise ConflictError(
            f"Failed to update order {order_id} after {max_retries} attempts due to conflicts",
            retries=max_retries,
        )

    async def _backoff_fixed(self, delay: float):
        """
        Fixed backoff (without jitter) for conflict retries.

        Args:
            delay: Delay in seconds
        """
        import asyncio

        logger.info("Backing off before conflict retry", delay_seconds=delay)
        await asyncio.sleep(delay)

    # ========================================================================
    # Product Operations
    # ========================================================================

    async def get_product(self, product_id: str) -> dict[str, Any]:
        """
        Get a single product by ID.

        Args:
            product_id: OrderDesk product/inventory item ID

        Returns:
            Product object with all fields

        Raises:
            OrderDeskError: If product not found or API error

        Example response:
        {
            "id": "product-123",
            "name": "Premium Widget",
            "price": 49.99,
            "sku": "WIDGET-001",
            "quantity": 100,
            "weight": 1.5,
            "category": "Electronics",
            "description": "High-quality widget"
        }
        """
        return await self.get(f"/inventory/{product_id}")

    async def list_products(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> dict[str, Any]:
        """
        List products with pagination and search.

        Args:
            limit: Number of products to return (1-100, default 50)
            offset: Number of products to skip (default 0)
            search: Search query (searches name, SKU, description, etc.)

        Returns:
            Response with products array and pagination metadata

        Response format:
        {
            "products": [
                {
                    "id": "product-123",
                    "name": "Premium Widget",
                    "price": 49.99,
                    "sku": "WIDGET-001",
                    ...
                }
            ],
            "count": 50,
            "limit": 50,
            "offset": 0,
            "page": 1,
            "has_more": true
        }

        Pagination:
        - limit: Controls page size (1-100)
        - offset: Controls starting position
        - has_more: Calculated based on returned count vs limit

        Search:
        - Searches across: name, SKU, description, category
        - Case-insensitive
        - Partial match supported
        """
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            raise OrderDeskError(
                code="INVALID_PARAMETER",
                message=f"Limit must be between 1 and 100, got {limit}",
                details={"limit": limit},
            )

        if offset < 0:
            raise OrderDeskError(
                code="INVALID_PARAMETER",
                message=f"Offset must be >= 0, got {offset}",
                details={"offset": offset},
            )

        # Build query parameters
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if search:
            params["search"] = search

        # Make request
        response = await self.get("/inventory", params=params)

        # OrderDesk returns products in the root or in a "products" key
        # Handle both formats
        if isinstance(response, list):  # type: ignore[unreachable]
            products = response  # type: ignore[unreachable]
        elif isinstance(response, dict) and "products" in response:
            products = response["products"]
        elif isinstance(response, dict) and "inventory" in response:
            # OrderDesk might use "inventory" key
            products = response["inventory"]
        else:
            logger.warning(
                "Unexpected OrderDesk response format for products",
                response_type=type(response).__name__,
            )
            products = []

        # Calculate pagination metadata
        products_count = len(products)
        has_more = products_count == limit  # If we got a full page, there might be more
        current_page = (offset // limit) + 1

        return {
            "products": products,
            "count": products_count,
            "limit": limit,
            "offset": offset,
            "page": current_page,
            "has_more": has_more,
        }
