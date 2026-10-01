from adapters.base import BaseCommerceAdapter
from adapters.shopify.adapter import ShopifyAdapter
from config.settings import settings

def get_commerce_adapter() -> BaseCommerceAdapter:
    adapter_name = settings.ACTIVE_COMMERCE_ADAPTER.lower()
    if adapter_name == "shopify":
        return ShopifyAdapter()
    raise ValueError(f"Commerce adapter '{adapter_name}' not supported.")