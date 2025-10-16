"""Pydantic models for OrderDesk API objects."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Address(BaseModel):
    """Address model for shipping/billing addresses."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    address3: Optional[str] = None
    address4: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None


class OrderItem(BaseModel):
    """Order item model."""

    id: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None
    weight: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class Order(BaseModel):
    """Order model matching OrderDesk API structure."""

    id: Optional[str] = None
    email: Optional[str] = None
    shipping_method: Optional[str] = None
    quantity_total: Optional[int] = None
    weight_total: Optional[float] = None
    product_total: Optional[float] = None
    shipping_total: Optional[float] = None
    handling_total: Optional[float] = None
    tax_total: Optional[float] = None
    discount_total: Optional[float] = None
    order_total: Optional[float] = None
    cc_number_masked: Optional[str] = None
    cc_exp: Optional[str] = None
    processor_response: Optional[str] = None
    payment_type: Optional[str] = None
    payment_status: Optional[str] = None
    processor_balance: Optional[float] = None
    refund_total: Optional[float] = None
    customer_id: Optional[str] = None
    email_count: Optional[str] = None
    ip_address: Optional[str] = None
    tag_color: Optional[str] = None
    source_name: Optional[str] = None
    source_id: Optional[str] = None
    fulfillment_name: Optional[str] = None
    fulfillment_id: Optional[str] = None
    tag_name: Optional[str] = None
    folder_id: Optional[int] = None
    date_added: Optional[datetime] = None
    date_updated: Optional[datetime] = None
    shipping: Optional[Address] = None
    customer: Optional[Address] = None
    return_address: Optional[Address] = None
    items: Optional[List[OrderItem]] = None
    notes: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[List[Dict[str, Any]]] = None


class InventoryItem(BaseModel):
    """Inventory item model."""

    id: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    weight: Optional[float] = None
    variation_list: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None
    manufacturer_sku: Optional[str] = None
    date_added: Optional[datetime] = None
    date_updated: Optional[datetime] = None


class OrderMutation(BaseModel):
    """Order mutation request model."""

    operations: List[Dict[str, Any]] = Field(
        ..., description="List of mutation operations to apply"
    )


class MoveFolderRequest(BaseModel):
    """Move order to folder request."""

    folder_id: Optional[int] = Field(None, description="Folder ID to move to")
    folder_name: Optional[str] = Field(None, description="Folder name to move to")


class AddItemsRequest(BaseModel):
    """Add items to order request."""

    items: List[OrderItem] = Field(..., description="Items to add to the order")


class UpdateAddressRequest(BaseModel):
    """Update order address request."""

    address_type: str = Field(..., description="Type of address: shipping, customer, or return")
    address: Address = Field(..., description="New address data")


class AddNoteRequest(BaseModel):
    """Add note to order request."""

    note: str = Field(..., description="Note text to add")
    note_type: Optional[str] = Field("general", description="Type of note")


class StoreCreateRequest(BaseModel):
    """Create store request."""

    store_id: str = Field(..., description="OrderDesk store ID")
    api_key: str = Field(..., description="OrderDesk API key")
    label: Optional[str] = Field(None, description="Optional label for the store")


class StoreResponse(BaseModel):
    """Store response model (no secrets)."""

    id: str
    store_id: str
    label: Optional[str] = None
    created_at: datetime


class ErrorResponse(BaseModel):
    """Error response model."""

    error: Dict[str, Any] = Field(
        ...,
        description="Error details including code, message, and request_id",
    )
