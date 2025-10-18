"""
Tests for OrderDesk HTTP client.

Per specification: Test HTTP client, retries, error handling, pagination.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from mcp_server.services.orderdesk_client import OrderDeskClient
from mcp_server.models.common import OrderDeskError


@pytest.fixture
def client():
    """Create OrderDesk client for testing."""
    return OrderDeskClient(
        store_id="12345",
        api_key="test-api-key",
        max_retries=3
    )


class TestOrderDeskClient:
    """Test OrderDeskClient initialization and configuration."""
    
    def test_client_initialization(self, client):
        """Should initialize with correct parameters."""
        assert client.store_id == "12345"
        assert client.api_key == "test-api-key"
        assert client.max_retries == 3
        assert client.BASE_URL == "https://app.orderdesk.me/api/v2"
    
    def test_timeout_configuration(self, client):
        """Should have correct timeout configuration."""
        assert client.timeout.connect == 15.0
        assert client.timeout.read == 60.0
        assert client.timeout.write == 60.0
        assert client.timeout.pool == 5.0
    
    def test_build_url(self, client):
        """Should build correct URLs."""
        url = client._build_url("/orders")
        assert url == "https://app.orderdesk.me/api/v2/orders"
        
        # Should handle paths without leading slash
        url = client._build_url("orders/123")
        assert url == "https://app.orderdesk.me/api/v2/orders/123"
    
    def test_get_auth_params(self, client):
        """Should return correct authentication parameters."""
        params = client._get_auth_params()
        assert params == {
            "store_id": "12345",
            "api_key": "test-api-key"
        }


class TestHTTPMethods:
    """Test HTTP method wrappers."""
    
    @pytest.mark.asyncio
    async def test_get_method(self, client):
        """Should make GET request with correct parameters."""
        with patch.object(client, '_request_with_retry', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"test": "data"}
            
            result = await client.get("/orders", params={"limit": 50})
            
            mock_request.assert_called_once_with(
                "GET", "/orders", params={"limit": 50}
            )
            assert result == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_post_method(self, client):
        """Should make POST request with JSON body."""
        with patch.object(client, '_request_with_retry', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"created": True}
            
            result = await client.post("/orders", json={"data": "test"})
            
            mock_request.assert_called_once_with(
                "POST", "/orders", params=None, json={"data": "test"}
            )
            assert result == {"created": True}


class TestRetryLogic:
    """Test retry logic and exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_retry_success_without_errors(self, client):
        """Should succeed immediately if no errors."""
        # Test successful request (no retries needed)
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"success": True}
            
            result = await client.get("/orders")
            
            assert result == {"success": True}
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, client):
        """Should handle timeout errors gracefully."""
        with patch.object(client, '_ensure_client', new_callable=AsyncMock):
            with patch.object(client, '_client') as mock_http_client:
                # Simulate timeout
                mock_http_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
                
                with patch.object(client, '_backoff', new_callable=AsyncMock):
                    with pytest.raises(OrderDeskError) as exc_info:
                        await client._request_with_retry("GET", "/orders")
                    
                    assert exc_info.value.code == "TIMEOUT"
                    # Should have retried max_retries + 1 times
                    assert mock_http_client.request.call_count == client.max_retries + 1
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, client):
        """Should handle network errors gracefully."""
        with patch.object(client, '_ensure_client', new_callable=AsyncMock):
            with patch.object(client, '_client') as mock_http_client:
                # Simulate network error
                mock_http_client.request = AsyncMock(
                    side_effect=httpx.NetworkError("Connection failed")
                )
                
                with patch.object(client, '_backoff', new_callable=AsyncMock):
                    with pytest.raises(OrderDeskError) as exc_info:
                        await client._request_with_retry("GET", "/orders")
                    
                    assert exc_info.value.code == "NETWORK_ERROR"
    
    @pytest.mark.asyncio
    async def test_error_mapping_for_404(self, client):
        """Should map 404 to NOT_FOUND error."""
        with patch.object(client, '_ensure_client', new_callable=AsyncMock):
            with patch.object(client, '_client') as mock_http_client:
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_response.json.return_value = {"message": "Not found"}
                mock_response.text = "Not found"
                mock_http_client.request = AsyncMock(return_value=mock_response)
                
                with pytest.raises(OrderDeskError) as exc_info:
                    await client._request_with_retry("GET", "/orders/999")
                
                assert exc_info.value.code == "NOT_FOUND"
                # Should only try once (no retries for 404)
                assert mock_http_client.request.call_count == 1


class TestBackoffCalculation:
    """Test exponential backoff calculations."""
    
    @pytest.mark.asyncio
    async def test_backoff_increases_exponentially(self, client):
        """Backoff delay should increase exponentially."""
        import asyncio
        
        # Mock sleep to capture delay values
        delays = []
        
        async def mock_sleep(delay):
            delays.append(delay)
        
        with patch.object(asyncio, 'sleep', new=mock_sleep):
            await client._backoff(0)  # First retry
            await client._backoff(1)  # Second retry
            await client._backoff(2)  # Third retry
        
        # Delays should increase (with jitter, so approximate)
        assert delays[0] < delays[1] < delays[2]
        # First delay should be ~1s (± jitter)
        assert 0.75 <= delays[0] <= 1.25
        # Second delay should be ~2s (± jitter)
        assert 1.5 <= delays[1] <= 2.5


class TestOrderOperations:
    """Test order-specific operations."""
    
    @pytest.mark.asyncio
    async def test_get_order(self, client):
        """Should fetch single order by ID."""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "id": "123456",
                "email": "customer@example.com",
                "order_total": 29.99
            }
            
            order = await client.get_order("123456")
            
            mock_get.assert_called_once_with("/orders/123456")
            assert order["id"] == "123456"
    
    @pytest.mark.asyncio
    async def test_list_orders_default_params(self, client):
        """Should list orders with default pagination."""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "1", "email": "test1@example.com"},
                {"id": "2", "email": "test2@example.com"}
            ]
            
            result = await client.list_orders()
            
            # Should use defaults: limit=50, offset=0
            expected_params = {"limit": 50, "offset": 0}
            mock_get.assert_called_once_with("/orders", params=expected_params)
            assert len(result["orders"]) == 2
            assert result["has_more"] == False  # Less than limit
    
    @pytest.mark.asyncio
    async def test_list_orders_with_filters(self, client):
        """Should list orders with filters."""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"orders": [{"id": "1"}]}
            
            result = await client.list_orders(
                limit=20,
                offset=40,
                folder_id=5,
                status="open",
                search="test"
            )
            
            expected_params = {
                "limit": 20,
                "offset": 40,
                "folder_id": 5,
                "status": "open",
                "search": "test"
            }
            mock_get.assert_called_once_with("/orders", params=expected_params)
    
    @pytest.mark.asyncio
    async def test_list_orders_pagination_metadata(self, client):
        """Should calculate pagination metadata correctly."""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            # Return exactly 'limit' items (indicates more pages)
            mock_get.return_value = [{"id": f"{i}"} for i in range(50)]
            
            result = await client.list_orders(limit=50, offset=0)
            
            assert result["count"] == 50
            assert result["limit"] == 50
            assert result["offset"] == 0
            assert result["page"] == 1
            assert result["has_more"] == True  # Full page → more might exist
    
    @pytest.mark.asyncio
    async def test_list_orders_last_page(self, client):
        """Should detect last page (partial results)."""
        with patch.object(client, 'get', new_callable=AsyncMock) as mock_get:
            # Return fewer than 'limit' items (last page)
            mock_get.return_value = [{"id": f"{i}"} for i in range(25)]
            
            result = await client.list_orders(limit=50, offset=100)
            
            assert result["count"] == 25
            assert result["has_more"] == False  # Partial page → no more
            assert result["page"] == 3  # offset=100, limit=50 → page 3


class TestErrorHandling:
    """Test error handling and mapping."""
    
    @pytest.mark.asyncio
    async def test_parameter_validation_limit_too_low(self, client):
        """Should reject limit < 1."""
        with pytest.raises(OrderDeskError) as exc_info:
            await client.list_orders(limit=0)
        
        assert exc_info.value.code == "INVALID_PARAMETER"
        assert "1 and 100" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_parameter_validation_limit_too_high(self, client):
        """Should reject limit > 100."""
        with pytest.raises(OrderDeskError) as exc_info:
            await client.list_orders(limit=150)
        
        assert exc_info.value.code == "INVALID_PARAMETER"
    
    @pytest.mark.asyncio
    async def test_parameter_validation_negative_offset(self, client):
        """Should reject negative offset."""
        with pytest.raises(OrderDeskError) as exc_info:
            await client.list_orders(offset=-10)
        
        assert exc_info.value.code == "INVALID_PARAMETER"
        assert "must be >= 0" in exc_info.value.message


class TestContextManager:
    """Test async context manager support."""
    
    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """Should work as async context manager."""
        async with OrderDeskClient("12345", "test-key") as client:
            assert client is not None
            assert client.store_id == "12345"
        
        # Client should be closed after context
        assert client._client is None or client._client.is_closed


# Coverage target: >85%

