from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from core.models.schemas import Product, Cart, CartItem, CheckoutSession, ShippingAddress, LocationRef

class BaseCommerceAdapter(ABC):
    @abstractmethod
    async def search_products(self, query: str = "", limit: int = 10) -> List[Product]:
        pass

    @abstractmethod
    async def get_product(self, product_id: str) -> Optional[Product]:
        pass

    @abstractmethod
    async def create_cart(self, items: List[CartItem]) -> Cart:
        pass

    @abstractmethod
    async def init_checkout(
        self,
        cart_id: str,
        address: Optional[ShippingAddress] = None,
        pickup: Optional[LocationRef] = None
    ) -> CheckoutSession:
        pass

    @abstractmethod
    async def complete_order(self, checkout_id: str, payment_token: str) -> Dict[str, Any]:
        pass