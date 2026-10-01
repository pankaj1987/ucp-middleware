from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class PolicySnapshot(BaseModel):
    policy_id: str
    type: Literal["return", "refund", "warranty", "cancellation"]
    summary: str
    url: Optional[str] = None

class LocationRef(BaseModel):
    location_id: str
    type: Literal["store", "restaurant", "hotel"]
    name: str
    address: str
    city: str
    postal_code: str
    country: str = "US"

class Product(BaseModel):
    id: str
    title: str
    description: str
    price: float
    currency: str = "USD"
    sku: Optional[str] = None
    image_url: Optional[str] = None
    in_stock: bool = True
    vertical_type: Literal["shopping", "food", "lodging"] = "shopping"

class CartItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = 1
    price: float
    title: str

class Cart(BaseModel):
    cart_id: str
    items: List[CartItem]
    subtotal: float
    currency: str = "USD"
    permalink: Optional[str] = None
    policies: List[PolicySnapshot] = Field(default_factory=list)

class ShippingAddress(BaseModel):
    first_name: str = "Valued"
    last_name: str = "Customer"
    address_line1: str
    city: str
    postal_code: str
    country: str = "US"

class CheckoutSession(BaseModel):
    checkout_id: str
    cart_id: str
    status: Literal["incomplete", "requires_action", "ready_for_complete", "completed"]
    shipping_address: Optional[ShippingAddress] = None
    pickup_location: Optional[LocationRef] = None
    items: List[CartItem]
    total_price: float
    currency: str = "USD"
    policies: List[PolicySnapshot] = Field(default_factory=list)