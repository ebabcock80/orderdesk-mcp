"""
Tests for order MCP tools.

Per specification: Test orders.get and orders.list tools with caching.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.models.common import NotFoundError, ValidationError
from mcp_server.routers.orders import (
    GetOrderParams,
    ListOrdersParams,
    get_order_mcp,
    list_orders_mcp,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_authenticated_session():
    """Mock authenticated session context."""
    with patch("mcp_server.routers.orders.require_auth") as mock_auth:
        with patch("mcp_server.routers.orders.get_tenant_key") as mock_key:
            mock_auth.return_value = "tenant-123"
            mock_key.return_value = b"test-key" * 4  # 32 bytes
            yield


class TestGetOrderMCP:
    """Test orders.get MCP tool."""

    @pytest.mark.asyncio
    async def test_get_order_success(self, mock_db, mock_authenticated_session):
        """Should fetch order successfully."""
        params = GetOrderParams(order_id="123456", store_identifier="production")

        # Mock store service
        with patch("mcp_server.routers.orders.StoreService") as MockStoreService:
            mock_store_service = MockStoreService.return_value

            # Mock store
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )

            # Mock cache manager
            with patch("mcp_server.routers.orders.cache_manager") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)  # Cache miss
                mock_cache.set = AsyncMock()

                # Mock OrderDesk client
                with patch("mcp_server.routers.orders.OrderDeskClient") as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.get_order = AsyncMock(
                        return_value={
                            "id": "123456",
                            "email": "test@example.com",
                            "order_total": 29.99,
                        }
                    )
                    MockClient.return_value.__aenter__.return_value = (
                        mock_client_instance
                    )

                    result = await get_order_mcp(params, mock_db)

                    assert result["status"] == "success"
                    assert result["order"]["id"] == "123456"
                    assert not result["cached"]

    @pytest.mark.asyncio
    async def test_get_order_from_cache(self, mock_db, mock_authenticated_session):
        """Should return cached order if available."""
        params = GetOrderParams(order_id="123456", store_identifier="production")

        with patch("mcp_server.routers.orders.StoreService") as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )

            # Mock cache hit
            with patch("mcp_server.routers.orders.cache_manager") as mock_cache:
                mock_cache.get = AsyncMock(
                    return_value={"id": "123456", "email": "cached@example.com"}
                )

                result = await get_order_mcp(params, mock_db)

                assert result["status"] == "success"
                assert result["order"]["email"] == "cached@example.com"
                assert result["cached"]

    @pytest.mark.asyncio
    async def test_get_order_store_not_found(self, mock_db, mock_authenticated_session):
        """Should raise NotFoundError if store doesn't exist."""
        params = GetOrderParams(order_id="123456", store_identifier="nonexistent")

        with patch("mcp_server.routers.orders.StoreService") as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store_service.resolve_store = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError):
                await get_order_mcp(params, mock_db)

    @pytest.mark.asyncio
    async def test_get_order_no_active_store(self, mock_db, mock_authenticated_session):
        """Should raise ValidationError if no store specified and no active store."""
        params = GetOrderParams(order_id="123456")  # No store_identifier

        with patch("mcp_server.routers.orders.get_context") as mock_context:
            mock_context.return_value.active_store_id = None

            with pytest.raises(ValidationError) as exc_info:
                await get_order_mcp(params, mock_db)

            assert "No store specified" in exc_info.value.message


class TestListOrdersMCP:
    """Test orders.list MCP tool."""

    @pytest.mark.asyncio
    async def test_list_orders_success(self, mock_db, mock_authenticated_session):
        """Should list orders with pagination."""
        params = ListOrdersParams(store_identifier="production", limit=20, offset=0)

        with patch("mcp_server.routers.orders.StoreService") as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )

            with patch("mcp_server.routers.orders.cache_manager") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)  # Cache miss
                mock_cache.set = AsyncMock()

                with patch("mcp_server.routers.orders.OrderDeskClient") as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.list_orders = AsyncMock(
                        return_value={
                            "orders": [{"id": f"{i}"} for i in range(20)],
                            "count": 20,
                            "limit": 20,
                            "offset": 0,
                            "page": 1,
                            "has_more": True,
                        }
                    )
                    MockClient.return_value.__aenter__.return_value = (
                        mock_client_instance
                    )

                    result = await list_orders_mcp(params, mock_db)

                    assert result["status"] == "success"
                    assert len(result["orders"]) == 20
                    assert result["pagination"]["page"] == 1
                    assert result["pagination"]["has_more"]

    @pytest.mark.asyncio
    async def test_list_orders_with_filters(self, mock_db, mock_authenticated_session):
        """Should apply filters to list query."""
        params = ListOrdersParams(
            store_identifier="production",
            limit=50,
            offset=0,
            folder_id=5,
            status="open",
            search="urgent",
        )

        with patch("mcp_server.routers.orders.StoreService") as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )

            with patch("mcp_server.routers.orders.cache_manager") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)
                mock_cache.set = AsyncMock()

                with patch("mcp_server.routers.orders.OrderDeskClient") as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.list_orders = AsyncMock(
                        return_value={
                            "orders": [],
                            "count": 0,
                            "limit": 50,
                            "offset": 0,
                            "page": 1,
                            "has_more": False,
                        }
                    )
                    MockClient.return_value.__aenter__.return_value = (
                        mock_client_instance
                    )

                    await list_orders_mcp(params, mock_db)

                    # Verify filters were passed
                    mock_client_instance.list_orders.assert_called_once_with(
                        limit=50, offset=0, folder_id=5, status="open", search="urgent"
                    )


# Coverage target: >80%
