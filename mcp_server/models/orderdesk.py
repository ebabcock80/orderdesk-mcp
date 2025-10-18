"""Pydantic models for OrderDesk API objects."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Address(BaseModel):
    """Address model for shipping/billing addresses."""

    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    address1: str | None = None
    address2: str | None = None
    address3: str | None = None
    address4: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None


class OrderItem(BaseModel):
    """Order item model."""

    id: str | None = None
    name: str | None = None
    code: str | None = None
    price: float | None = None
    quantity: int | None = None
    weight: float | None = None
    metadata: dict[str, Any] | None = None


class Order(BaseModel):
    """Order model matching OrderDesk API structure."""

    id: str | None = None
    email: str | None = None
    shipping_method: str | None = None
    quantity_total: int | None = None
    weight_total: float | None = None
    product_total: float | None = None
    shipping_total: float | None = None
    handling_total: float | None = None
    tax_total: float | None = None
    discount_total: float | None = None
    order_total: float | None = None
    cc_number_masked: str | None = None
    cc_exp: str | None = None
    processor_response: str | None = None
    payment_type: str | None = None
    payment_status: str | None = None
    processor_balance: float | None = None
    refund_total: float | None = None
    customer_id: str | None = None
    email_count: str | None = None
    ip_address: str | None = None
    tag_color: str | None = None
    source_name: str | None = None
    source_id: str | None = None
    fulfillment_name: str | None = None
    fulfillment_id: str | None = None
    tag_name: str | None = None
    folder_id: int | None = None
    date_added: datetime | None = None
    date_updated: datetime | None = None
    shipping: Address | None = None
    customer: Address | None = None
    return_address: Address | None = None
    items: list[OrderItem] | None = None
    notes: list[dict[str, Any]] | None = None
    metadata: list[dict[str, Any]] | None = None


class InventoryItem(BaseModel):
    """Inventory item model."""

    id: str | None = None
    name: str | None = None
    code: str | None = None
    price: float | None = None
    stock: int | None = None
    weight: float | None = None
    variation_list: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None
    manufacturer_sku: str | None = None
    date_added: datetime | None = None
    date_updated: datetime | None = None


class OrderMutation(BaseModel):
    """Order mutation request model."""

    operations: list[dict[str, Any]] = Field(
        ..., description="List of mutation operations to apply"
    )


class MoveFolderRequest(BaseModel):
    """Move order to folder request."""

    folder_id: int | None = Field(None, description="Folder ID to move to")
    folder_name: str | None = Field(None, description="Folder name to move to")


class AddItemsRequest(BaseModel):
    """Add items to order request."""

    items: list[OrderItem] = Field(..., description="Items to add to the order")


class UpdateAddressRequest(BaseModel):
    """Update order address request."""

    address_type: str = Field(
        ..., description="Type of address: shipping, customer, or return"
    )
    address: Address = Field(..., description="New address data")


class AddNoteRequest(BaseModel):
    """Add note to order request."""

    note: str = Field(..., description="Note text to add")
    note_type: str | None = Field("general", description="Type of note")


class StoreCreateRequest(BaseModel):
    """Create store request."""

    store_id: str = Field(..., description="OrderDesk store ID")
    api_key: str = Field(..., description="OrderDesk API key")
    label: str | None = Field(None, description="Optional label for the store")


class StoreResponse(BaseModel):
    """Store response model (no secrets)."""

    id: str
    store_id: str
    label: str | None = None
    created_at: datetime


class ErrorResponse(BaseModel):
    """Error response model."""

    error: dict[str, Any] = Field(
        ...,
        description="Error details including code, message, and request_id",
    )
