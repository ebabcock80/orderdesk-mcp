"""
Tests for product MCP tools.

Per specification: Test products.get and products.list with 60-second caching.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.routers.products import (
    get_product_mcp, list_products_mcp,
    GetProductParams, ListProductsParams
)
from mcp_server.models.common import NotFoundError, ValidationError


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_authenticated_session():
    """Mock authenticated session context."""
    with patch('mcp_server.routers.products.require_auth') as mock_auth:
        with patch('mcp_server.routers.products.get_tenant_key') as mock_key:
            mock_auth.return_value = "tenant-123"
            mock_key.return_value = b"test-key" * 4  # 32 bytes
            yield


class TestGetProductMCP:
    """Test products.get MCP tool."""
    
    @pytest.mark.asyncio
    async def test_get_product_success(self, mock_db, mock_authenticated_session):
        """Should fetch product successfully."""
        params = GetProductParams(
            product_id="product-123",
            store_identifier="production"
        )
        
        with patch('mcp_server.routers.products.StoreService') as MockStoreService:
            mock_store_service = MockStoreService.return_value
            
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )
            
            with patch('mcp_server.routers.products.cache_manager') as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)  # Cache miss
                mock_cache.set = AsyncMock()
                
                with patch('mcp_server.routers.products.OrderDeskClient') as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.get_product = AsyncMock(return_value={
                        "id": "product-123",
                        "name": "Premium Widget",
                        "price": 49.99,
                        "sku": "WIDGET-001",
                        "quantity": 100
                    })
                    MockClient.return_value.__aenter__.return_value = mock_client_instance
                    
                    result = await get_product_mcp(params, mock_db)
                    
                    assert result["status"] == "success"
                    assert result["product"]["id"] == "product-123"
                    assert result["product"]["price"] == 49.99
                    assert result["cached"] == False
    
    @pytest.mark.asyncio
    async def test_get_product_from_cache(self, mock_db, mock_authenticated_session):
        """Should return cached product if available (60s TTL)."""
        params = GetProductParams(product_id="product-123", store_identifier="production")
        
        with patch('mcp_server.routers.products.StoreService') as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )
            
            # Mock cache hit
            with patch('mcp_server.routers.products.cache_manager') as mock_cache:
                mock_cache.get = AsyncMock(return_value={
                    "id": "product-123",
                    "name": "Cached Widget",
                    "price": 39.99
                })
                
                result = await get_product_mcp(params, mock_db)
                
                assert result["status"] == "success"
                assert result["product"]["name"] == "Cached Widget"
                assert result["cached"] == True
    
    @pytest.mark.asyncio
    async def test_get_product_not_found(self, mock_db, mock_authenticated_session):
        """Should raise NotFoundError if product doesn't exist."""
        params = GetProductParams(product_id="nonexistent", store_identifier="production")
        
        with patch('mcp_server.routers.products.StoreService') as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )
            
            with patch('mcp_server.routers.products.cache_manager') as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)
                
                with patch('mcp_server.routers.products.OrderDeskClient') as MockClient:
                    from mcp_server.models.common import OrderDeskError
                    
                    mock_client_instance = AsyncMock()
                    mock_client_instance.get_product = AsyncMock(
                        side_effect=OrderDeskError("Not found", code="NOT_FOUND")
                    )
                    MockClient.return_value.__aenter__.return_value = mock_client_instance
                    
                    with pytest.raises(NotFoundError):
                        await get_product_mcp(params, mock_db)


class TestListProductsMCP:
    """Test products.list MCP tool."""
    
    @pytest.mark.asyncio
    async def test_list_products_success(self, mock_db, mock_authenticated_session):
        """Should list products with pagination."""
        params = ListProductsParams(
            store_identifier="production",
            limit=20,
            offset=0
        )
        
        with patch('mcp_server.routers.products.StoreService') as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )
            
            with patch('mcp_server.routers.products.cache_manager') as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)  # Cache miss
                mock_cache.set = AsyncMock()
                
                with patch('mcp_server.routers.products.OrderDeskClient') as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.list_products = AsyncMock(return_value={
                        "products": [
                            {"id": f"product-{i}", "name": f"Product {i}", "price": 10.0 * i}
                            for i in range(1, 21)
                        ],
                        "count": 20,
                        "limit": 20,
                        "offset": 0,
                        "page": 1,
                        "has_more": True
                    })
                    MockClient.return_value.__aenter__.return_value = mock_client_instance
                    
                    result = await list_products_mcp(params, mock_db)
                    
                    assert result["status"] == "success"
                    assert len(result["products"]) == 20
                    assert result["pagination"]["page"] == 1
                    assert result["pagination"]["has_more"] == True
                    assert result["cached"] == False
    
    @pytest.mark.asyncio
    async def test_list_products_with_search(self, mock_db, mock_authenticated_session):
        """Should apply search filter."""
        params = ListProductsParams(
            store_identifier="production",
            limit=50,
            offset=0,
            search="widget"
        )
        
        with patch('mcp_server.routers.products.StoreService') as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )
            
            with patch('mcp_server.routers.products.cache_manager') as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)
                mock_cache.set = AsyncMock()
                
                with patch('mcp_server.routers.products.OrderDeskClient') as MockClient:
                    mock_client_instance = AsyncMock()
                    mock_client_instance.list_products = AsyncMock(return_value={
                        "products": [{"id": "1", "name": "Widget"}],
                        "count": 1,
                        "limit": 50,
                        "offset": 0,
                        "page": 1,
                        "has_more": False
                    })
                    MockClient.return_value.__aenter__.return_value = mock_client_instance
                    
                    result = await list_products_mcp(params, mock_db)
                    
                    # Verify search was passed
                    mock_client_instance.list_products.assert_called_once_with(
                        limit=50,
                        offset=0,
                        search="widget"
                    )
    
    @pytest.mark.asyncio
    async def test_list_products_from_cache(self, mock_db, mock_authenticated_session):
        """Should return cached products (60s TTL)."""
        params = ListProductsParams(store_identifier="production")
        
        with patch('mcp_server.routers.products.StoreService') as MockStoreService:
            mock_store_service = MockStoreService.return_value
            mock_store = MagicMock()
            mock_store.store_id = "12345"
            mock_store_service.resolve_store = AsyncMock(return_value=mock_store)
            mock_store_service.get_decrypted_credentials = AsyncMock(
                return_value=("12345", "api-key")
            )
            
            # Mock cache hit
            with patch('mcp_server.routers.products.cache_manager') as mock_cache:
                mock_cache.get = AsyncMock(return_value={
                    "products": [{"id": "1", "name": "Cached Product"}],
                    "pagination": {"count": 1, "page": 1, "has_more": False}
                })
                
                result = await list_products_mcp(params, mock_db)
                
                assert result["status"] == "success"
                assert result["products"][0]["name"] == "Cached Product"
                assert result["cached"] == True


# Coverage target: >80%

