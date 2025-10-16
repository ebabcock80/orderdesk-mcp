"""Store management endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mcp_server.auth.middleware import AuthError
from mcp_server.models.database import get_db
from mcp_server.models.orderdesk import StoreCreateRequest, StoreResponse
from mcp_server.services.tenant import TenantService

router = APIRouter()


@router.post("/stores", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def create_store(
    store_data: StoreCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new store for the authenticated tenant."""
    try:
        tenant_id = request.state.tenant_id
        tenant_service = TenantService(db)
        
        # Check if store already exists for this tenant
        existing_stores = tenant_service.list_stores(tenant_id)
        for store in existing_stores:
            if store.store_id == store_data.store_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Store {store_data.store_id} already exists for this tenant",
                )
        
        return tenant_service.create_store(tenant_id, store_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create store: {str(e)}",
        )


@router.get("/stores", response_model=List[StoreResponse])
async def list_stores(
    request: Request,
    db: Session = Depends(get_db),
):
    """List all stores for the authenticated tenant."""
    try:
        tenant_id = request.state.tenant_id
        tenant_service = TenantService(db)
        return tenant_service.list_stores(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list stores: {str(e)}",
        )


@router.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a store."""
    try:
        tenant_id = request.state.tenant_id
        tenant_service = TenantService(db)
        
        success = tenant_service.delete_store(tenant_id, store_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete store: {str(e)}",
        )
