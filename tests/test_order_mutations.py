"""
Tests for order mutation operations.

Per specification: Test create, update, delete with full-object workflow and conflict resolution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.models.common import ConflictError, OrderDeskError
from mcp_server.routers.orders import (
    CreateOrderParams,
    DeleteOrderParams,
    UpdateOrderParams,
    create_order_mcp,
    delete_order_mcp,
    update_order_mcp,
)
from mcp_server.services.orderdesk_client import OrderDeskClient


class TestMergeOrderChanges:
    """Test safe merge helper."""

    def test_merge_simple_field_update(self):
        """Should update specified fields and preserve others."""
        client = OrderDeskClient("12345", "key")

        original = {
            "id": "123",
            "email": "old@example.com",
            "order_total": 100.00,
            "status": "open"
        }

        changes = {
            "email": "new@example.com"
        }

        merged = client.merge_order_changes(original, changes)

        assert merged["email"] == "new@example.com"  # Updated
        assert merged["order_total"] == 100.00  # Preserved
        assert merged["status"] == "open"  # Preserved

    def test_merge_null_removes_field(self):
        """Should remove field when value is explicitly None."""
        client = OrderDeskClient("12345", "key")

        original = {
            "id": "123",
            "email": "test@example.com",
            "customer_notes": "Old notes"
        }

        changes = {
            "customer_notes": None  # Explicit null
        }

        merged = client.merge_order_changes(original, changes)

        assert "customer_notes" not in merged  # Removed
        assert merged["email"] == "test@example.com"  # Preserved

    def test_merge_array_replacement(self):
        """Should replace arrays completely when provided."""
        client = OrderDeskClient("12345", "key")

        original = {
            "id": "123",
            "order_items": [
                {"id": "1", "name": "Product A"}
            ]
        }

        changes = {
            "order_items": [
                {"id": "2", "name": "Product B"},
                {"id": "3", "name": "Product C"}
            ]
        }

        merged = client.merge_order_changes(original, changes)

        assert len(merged["order_items"]) == 2
        assert merged["order_items"][0]["name"] == "Product B"


class TestUpdateOrderWithRetry:
    """Test conflict resolution workflow."""

    @pytest.mark.asyncio
    async def test_update_succeeds_first_try(self):
        """Should succeed on first attempt if no conflict."""
        client = OrderDeskClient("12345", "key")

        with patch.object(client, 'fetch_full_order', new_callable=AsyncMock) as mock_fetch:
            with patch.object(client, 'update_order', new_callable=AsyncMock) as mock_update:
                mock_fetch.return_value = {
                    "id": "123",
                    "email": "old@example.com",
                    "order_total": 100.00
                }

                mock_update.return_value = {
                    "id": "123",
                    "email": "new@example.com",
                    "order_total": 100.00
                }

                result = await client.update_order_with_retry(
                    "123",
                    {"email": "new@example.com"}
                )

                assert result["email"] == "new@example.com"
                assert mock_fetch.call_count == 1
                assert mock_update.call_count == 1

    @pytest.mark.asyncio
    async def test_update_retries_on_conflict(self):
        """Should retry on 409 conflict."""
        client = OrderDeskClient("12345", "key")

        with patch.object(client, 'fetch_full_order', new_callable=AsyncMock) as mock_fetch:
            with patch.object(client, 'update_order', new_callable=AsyncMock) as mock_update:
                with patch.object(client, '_backoff_fixed', new_callable=AsyncMock):
                    # First fetch
                    mock_fetch.return_value = {
                        "id": "123",
                        "email": "old@example.com"
                    }

                    # First update fails with conflict, second succeeds
                    mock_update.side_effect = [
                        OrderDeskError("Conflict", code="CONFLICT_ERROR"),
                        {"id": "123", "email": "new@example.com"}
                    ]

                    result = await client.update_order_with_retry("123", {"email": "new@example.com"})

                    assert result["email"] == "new@example.com"
                    assert mock_fetch.call_count == 2  # Retried once
                    assert mock_update.call_count == 2

    @pytest.mark.asyncio
    async def test_update_max_retries_exceeded(self):
        """Should raise ConflictError after max retries."""
        client = OrderDeskClient("12345", "key")

        with patch.object(client, 'fetch_full_order', new_callable=AsyncMock) as mock_fetch:
            with patch.object(client, 'update_order', new_callable=AsyncMock) as mock_update:
                with patch.object(client, '_backoff_fixed', new_callable=AsyncMock):
                    mock_fetch.return_value = {"id": "123"}

                    # All attempts fail with conflict
                    mock_update.side_effect = OrderDeskError("Conflict", code="CONFLICT_ERROR")

                    with pytest.raises(ConflictError) as exc_info:
                        await client.update_order_with_retry("123", {"email": "test"}, max_retries=3)

                    assert "after 3 attempts" in str(exc_info.value.message)
                    assert mock_fetch.call_count == 3
                    assert mock_update.call_count == 3


class TestCreateOrderMCP:
    """Test orders.create MCP tool."""

    @pytest.mark.asyncio
    async def test_create_order_success(self):
        """Should create order successfully."""
        params = CreateOrderParams(
            order_data={
                "email": "customer@example.com",
                "order_items": [{"name": "Product A", "quantity": 1, "price": 29.99}]
            },
            store_identifier="production"
        )

        mock_db = MagicMock()

        with patch('mcp_server.routers.orders.require_auth') as mock_auth:
            with patch('mcp_server.routers.orders.get_tenant_key') as mock_key:
                mock_auth.return_value = "tenant-123"
                mock_key.return_value = b"test-key" * 4

                with patch('mcp_server.routers.orders.StoreService') as MockStoreService:
                    mock_store_service = MockStoreService.return_value
                    mock_store = MagicMock()
                    mock_store.store_id = "12345"
                    mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
                    mock_store_service.get_decrypted_credentials = AsyncMock(
                        return_value=("12345", "api-key")
                    )

                    with patch('mcp_server.routers.orders.cache_manager') as mock_cache:
                        mock_cache.invalidate_pattern = AsyncMock()

                        with patch('mcp_server.routers.orders.OrderDeskClient') as MockClient:
                            mock_client_instance = AsyncMock()
                            mock_client_instance.create_order = AsyncMock(return_value={
                                "id": "123456",
                                "email": "customer@example.com",
                                "order_total": 29.99
                            })
                            MockClient.return_value.__aenter__.return_value = mock_client_instance

                            result = await create_order_mcp(params, mock_db)

                            assert result["status"] == "success"
                            assert result["order"]["id"] == "123456"
                            # Verify cache was invalidated
                            mock_cache.invalidate_pattern.assert_called_once()


class TestUpdateOrderMCP:
    """Test orders.update MCP tool."""

    @pytest.mark.asyncio
    async def test_update_order_success(self):
        """Should update order with safe merge."""
        params = UpdateOrderParams(
            order_id="123456",
            changes={"email": "newemail@example.com"},
            store_identifier="production"
        )

        mock_db = MagicMock()

        with patch('mcp_server.routers.orders.require_auth') as mock_auth:
            with patch('mcp_server.routers.orders.get_tenant_key') as mock_key:
                mock_auth.return_value = "tenant-123"
                mock_key.return_value = b"test-key" * 4

                with patch('mcp_server.routers.orders.StoreService') as MockStoreService:
                    mock_store_service = MockStoreService.return_value
                    mock_store = MagicMock()
                    mock_store.store_id = "12345"
                    mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
                    mock_store_service.get_decrypted_credentials = AsyncMock(
                        return_value=("12345", "api-key")
                    )

                    with patch('mcp_server.routers.orders.cache_manager') as mock_cache:
                        mock_cache.delete = AsyncMock()
                        mock_cache.invalidate_pattern = AsyncMock()

                        with patch('mcp_server.routers.orders.OrderDeskClient') as MockClient:
                            mock_client_instance = AsyncMock()
                            mock_client_instance.update_order_with_retry = AsyncMock(return_value={
                                "id": "123456",
                                "email": "newemail@example.com"
                            })
                            MockClient.return_value.__aenter__.return_value = mock_client_instance

                            result = await update_order_mcp(params, mock_db)

                            assert result["status"] == "success"
                            assert result["order"]["email"] == "newemail@example.com"
                            # Verify cache was invalidated
                            assert mock_cache.delete.called
                            assert mock_cache.invalidate_pattern.called


class TestDeleteOrderMCP:
    """Test orders.delete MCP tool."""

    @pytest.mark.asyncio
    async def test_delete_order_success(self):
        """Should delete order and invalidate cache."""
        params = DeleteOrderParams(
            order_id="123456",
            store_identifier="production"
        )

        mock_db = MagicMock()

        with patch('mcp_server.routers.orders.require_auth') as mock_auth:
            with patch('mcp_server.routers.orders.get_tenant_key') as mock_key:
                mock_auth.return_value = "tenant-123"
                mock_key.return_value = b"test-key" * 4

                with patch('mcp_server.routers.orders.StoreService') as MockStoreService:
                    mock_store_service = MockStoreService.return_value
                    mock_store = MagicMock()
                    mock_store.store_id = "12345"
                    mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
                    mock_store_service.get_decrypted_credentials = AsyncMock(
                        return_value=("12345", "api-key")
                    )

                    with patch('mcp_server.routers.orders.cache_manager') as mock_cache:
                        mock_cache.delete = AsyncMock()
                        mock_cache.invalidate_pattern = AsyncMock()

                        with patch('mcp_server.routers.orders.OrderDeskClient') as MockClient:
                            mock_client_instance = AsyncMock()
                            mock_client_instance.delete_order = AsyncMock(return_value={"deleted": True})
                            MockClient.return_value.__aenter__.return_value = mock_client_instance

                            result = await delete_order_mcp(params, mock_db)

                            assert result["status"] == "success"
                            assert "deleted successfully" in result["message"]
                            # Verify cache was invalidated
                            assert mock_cache.delete.called
                            assert mock_cache.invalidate_pattern.called


# Coverage target: >80%

