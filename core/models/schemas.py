from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from core.models.policies import PolicySnapshot

class AttributionContext(BaseModel):
    source_platform: str = Field("google_gemini_ui", description="Calling AI agent platform")
    referral_id: Optional[str] = Field("ref_gemini_shopping_graph_01")
    ad_id: Optional[str] = Field(None)
    campaign: Optional[str] = Field("ucp_autonomous_v2026_08_25")

class LocationRef(BaseModel):
    location_id: str
    name: Optional[str] = None
    address: Optional[str] = None

class CartItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    title: str
    price: float
    quantity: int = 1

class ShippingAddress(BaseModel):
    first_name: str = "Valued"
    last_name: str = "Customer"
    address_line1: str
    city: str
    postal_code: str
    country: str = "US"

class Cart(BaseModel):
    cart_id: str
    items: List[CartItem]
    subtotal: float
    currency: str = "USD"
    permalink: Optional[str] = None
    policies: List[PolicySnapshot] = Field(default_factory=list)

class CheckoutSession(BaseModel):
    checkout_id: str
    cart_id: str
    status: str = "ready_for_complete"  # ready_for_complete | requires_action | completed
    shipping_address: Optional[ShippingAddress] = None
    pickup_location: Optional[LocationRef] = None
    items: List[CartItem] = Field(default_factory=list)
    total_price: float = 0.0
    currency: str = "USD"
    policies: List[PolicySnapshot] = Field(default_factory=list)
    action_challenge: Optional[Dict[str, Any]] = None

class Product(BaseModel):
    id: str
    title: str
    description: str
    price: float
    currency: str = "USD"
    sku: Optional[str] = None
    in_stock: bool = True
    vertical_type: str = "shopping"
    policies: List[PolicySnapshot] = Field(default_factory=list)