"""OrderDesk API client with retry logic and request logging."""

import asyncio
import copy
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import httpx
import structlog
from httpx import HTTPStatusError, RequestError

from mcp_server.config import settings

logger = structlog.get_logger(__name__)


class OrderDeskAPIError(Exception):
    """OrderDesk API error."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message)


class ConcurrentUpdateError(OrderDeskAPIError):
    """Raised when order update fails due to concurrent modification."""

    pass


class OrderDeskClient:
    """Async OrderDesk API client with retry logic."""

    def __init__(self, store_id: str, api_key: str):
        self.store_id = store_id
        self.api_key = api_key
        self.base_url = "https://app.orderdesk.me/api/v2"
        
        # Create httpx client with timeouts
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=60.0),
            headers={
                "ORDERDESK-STORE-ID": store_id,
                "ORDERDESK-API-KEY": api_key,
                "Content-Type": "application/json",
            },
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic and logging."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_id = str(uuid.uuid4())
        
        # Retry configuration
        max_retries = 3
        base_delay = 0.25  # 250ms
        
        for attempt in range(max_retries + 1):
            start_time = time.time()
            
            try:
                # Make request
                if method.upper() == "GET":
                    response = await self.client.get(url, params=params)
                elif method.upper() == "POST":
                    response = await self.client.post(url, json=data, params=params)
                elif method.upper() == "PUT":
                    response = await self.client.put(url, json=data, params=params)
                elif method.upper() == "DELETE":
                    response = await self.client.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log request
                logger.info(
                    "orderdesk_api_request",
                    tenant_id=tenant_id,
                    store_id=self.store_id,
                    method=method.upper(),
                    endpoint=endpoint,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    request_id=request_id,
                    attempt=attempt + 1,
                )

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("X-Retry-After", 1))
                    if attempt < max_retries:
                        logger.warning(
                            "orderdesk_rate_limited",
                            tenant_id=tenant_id,
                            store_id=self.store_id,
                            retry_after=retry_after,
                            request_id=request_id,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise OrderDeskAPIError(
                            "OrderDesk API rate limit exceeded",
                            status_code=429,
                        )

                # Check for server errors
                if response.status_code >= 500:
                    if attempt < max_retries:
                        # Exponential backoff with jitter
                        delay = base_delay * (2 ** attempt) + (time.time() % 1)
                        logger.warning(
                            "orderdesk_server_error",
                            tenant_id=tenant_id,
                            store_id=self.store_id,
                            status_code=response.status_code,
                            delay=delay,
                            request_id=request_id,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise OrderDeskAPIError(
                            f"OrderDesk API server error: {response.status_code}",
                            status_code=response.status_code,
                        )

                # Raise for other HTTP errors
                response.raise_for_status()
                
                # Parse response
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": "success", "data": response.text}

            except RequestError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    "orderdesk_request_error",
                    tenant_id=tenant_id,
                    store_id=self.store_id,
                    method=method.upper(),
                    endpoint=endpoint,
                    error=str(e),
                    duration_ms=duration_ms,
                    request_id=request_id,
                    attempt=attempt + 1,
                )
                
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + (time.time() % 1)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise OrderDeskAPIError(f"Request failed: {str(e)}")

            except HTTPStatusError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    "orderdesk_http_error",
                    tenant_id=tenant_id,
                    store_id=self.store_id,
                    method=method.upper(),
                    endpoint=endpoint,
                    status_code=e.response.status_code,
                    error=str(e),
                    duration_ms=duration_ms,
                    request_id=request_id,
                    attempt=attempt + 1,
                )
                
                # Don't retry client errors (4xx except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise OrderDeskAPIError(
                        f"OrderDesk API client error: {e.response.status_code}",
                        status_code=e.response.status_code,
                    )
                
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + (time.time() % 1)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise OrderDeskAPIError(
                        f"OrderDesk API error: {e.response.status_code}",
                        status_code=e.response.status_code,
                    )

        # This should never be reached
        raise OrderDeskAPIError("Max retries exceeded")

    # Order methods
    async def get_order(self, order_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a single order."""
        return await self._make_request("GET", f"orders/{order_id}", tenant_id=tenant_id)

    async def list_orders(
        self,
        params: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List orders with optional filters."""
        return await self._make_request("GET", "orders", params=params, tenant_id=tenant_id)

    async def create_order(self, order_data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new order."""
        return await self._make_request("POST", "orders", data=order_data, tenant_id=tenant_id)

    async def update_order(
        self, order_id: str, order_data: Dict[str, Any], tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an order (full object replacement)."""
        return await self._make_request("PUT", f"orders/{order_id}", data=order_data, tenant_id=tenant_id)

    async def delete_order(self, order_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete an order."""
        return await self._make_request("DELETE", f"orders/{order_id}", tenant_id=tenant_id)

    # Inventory methods
    async def get_inventory_item(self, item_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a single inventory item."""
        return await self._make_request("GET", f"inventory-items/{item_id}", tenant_id=tenant_id)

    async def list_inventory_items(
        self,
        params: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List inventory items."""
        return await self._make_request("GET", "inventory-items", params=params, tenant_id=tenant_id)

    async def create_inventory_item(
        self, item_data: Dict[str, Any], tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new inventory item."""
        return await self._make_request("POST", "inventory-items", data=item_data, tenant_id=tenant_id)

    async def update_inventory_item(
        self, item_id: str, item_data: Dict[str, Any], tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an inventory item."""
        return await self._make_request("PUT", f"inventory-items/{item_id}", data=item_data, tenant_id=tenant_id)

    async def delete_inventory_item(self, item_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete an inventory item."""
        return await self._make_request("DELETE", f"inventory-items/{item_id}", tenant_id=tenant_id)

    # Store methods
    async def get_store_settings(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get store settings and folder list."""
        return await self._make_request("GET", "store", tenant_id=tenant_id)

    # Test connection
    async def test_connection(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Test API connection."""
        return await self._make_request("GET", "test", tenant_id=tenant_id)


async def mutate_order_full(
    client: OrderDeskClient,
    store_id: str,
    order_id: str,
    mutator: Callable[[Dict[str, Any]], Dict[str, Any]],
    max_retries: int = 3,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch → Mutate → Full Update with concurrency safety."""
    for attempt in range(max_retries):
        # Fetch current order
        order = await client.get_order(order_id, tenant_id=tenant_id)
        original_updated = order.get("date_updated")
        
        # Apply mutation to a copy
        modified = mutator(copy.deepcopy(order))
        
        try:
            # Attempt full update
            updated = await client.update_order(order_id, modified, tenant_id=tenant_id)
            return updated
        except OrderDeskAPIError as e:
            # Check if this is a concurrent update issue
            if e.status_code == 409 or "conflict" in e.message.lower():
                if attempt < max_retries - 1:
                    logger.warning(
                        "order_concurrent_update_retry",
                        tenant_id=tenant_id,
                        store_id=store_id,
                        order_id=order_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                    )
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    raise ConcurrentUpdateError(
                        f"Order {order_id} was modified concurrently",
                        status_code=409,
                    )
            else:
                # Re-raise other errors
                raise
    
    # This should never be reached
    raise ConcurrentUpdateError(f"Max retries exceeded for order {order_id}")
