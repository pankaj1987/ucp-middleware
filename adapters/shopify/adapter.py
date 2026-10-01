import re
import secrets
import time
from typing import Any, Dict, List, Optional

import httpx

from adapters.base import BaseCommerceAdapter
from config.settings import settings
from core.models.policies import PolicySnapshot, get_default_item_policies
from core.models.schemas import (
    AttributionContext,
    Cart,
    CartItem,
    CheckoutSession,
    Product,
    ShippingAddress,
)
from core.permalinks import generate_permalink_token


class ShopifyAdapter(BaseCommerceAdapter):

    def __init__(self):
        self.storefront_url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        self.admin_orders_url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/orders.json"
        self.storefront_headers = {
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": settings.SHOPIFY_STOREFRONT_TOKEN,
        }
        self.admin_headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": settings.SHOPIFY_ADMIN_ACCESS_TOKEN,
        }

    async def search_products(
        self, query: str = "", limit: int = 10
    ) -> List[Product]:
        gql = """
        query SearchCatalog($query: String!, $first: Int!) {
          products(query: $query, first: $first) {
            edges {
              node {
                id
                title
                description
                variants(first: 1) {
                  edges {
                    node {
                      id
                      price { amount currencyCode }
                      sku
                      availableForSale
                    }
                  }
                }
              }
            }
          }
        }
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.storefront_url,
                headers=self.storefront_headers,
                json={
                    "query": gql,
                    "variables": {"query": query, "first": limit},
                },
            )
            data = (
                resp.json()
                .get("data", {})
                .get("products", {})
                .get("edges", [])
            )
            results = []
            for edge in data:
                node = edge["node"]
                variant = (
                    node["variants"]["edges"][0]["node"]
                    if node["variants"]["edges"]
                    else None
                )
                results.append(
                    Product(
                        id=node["id"],
                        title=node["title"],
                        description=node["description"] or "",
                        price=(
                            float(variant["price"]["amount"])
                            if variant
                            else 0.0
                        ),
                        currency=(
                            variant["price"]["currencyCode"]
                            if variant
                            else "USD"
                        ),
                        sku=variant["id"] if variant else None,
                        in_stock=(
                            variant.get("availableForSale", True)
                            if variant
                            else True
                        ),
                        policies=get_default_item_policies(),
                    )
                )
            return results

    async def get_product(self, product_id: str) -> Optional[Product]:
        gql = """
        query GetProduct($id: ID!) {
          product(id: $id) {
            id
            title
            description
            variants(first: 1) {
              edges {
                node {
                  id
                  price { amount currencyCode }
                  sku
                  availableForSale
                }
              }
            }
          }
        }
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.storefront_url,
                headers=self.storefront_headers,
                json={"query": gql, "variables": {"id": product_id}},
            )
            prod = resp.json().get("data", {}).get("product")
            if not prod:
                return None
            variant = (
                prod["variants"]["edges"][0]["node"]
                if prod["variants"]["edges"]
                else None
            )
            return Product(
                id=prod["id"],
                title=prod["title"],
                description=prod["description"] or "",
                price=float(variant["price"]["amount"]) if variant else 0.0,
                currency=variant["price"]["currencyCode"] if variant else "USD",
                sku=variant["id"] if variant else None,
                in_stock=(
                    variant.get("availableForSale", True) if variant else True
                ),
            )

    async def create_cart(self, items: List[CartItem]) -> Cart:
        subtotal = sum(i.price * i.quantity for i in items)
        cart_id = (
            f"cart_{abs(hash(str([(i.product_id, i.quantity) for i in items])))}"
        )

        # Generate UCP Permalink (#523)
        token = generate_permalink_token([i.model_dump() for i in items])
        permalink = f"http://localhost:8000/cart/recover?token={token}"

        return Cart(
            cart_id=cart_id,
            items=items,
            subtotal=subtotal,
            currency="USD",
            permalink=permalink,
            policies=get_default_item_policies(),
        )

    async def init_checkout(
        self,
        cart_id: str,
        address: Optional[ShippingAddress] = None,
        pickup: Optional[Dict[str, Any]] = None,
        items: Optional[List[CartItem]] = None,
    ) -> CheckoutSession:
        items_list = items or []
        total = sum(i.price * i.quantity for i in items_list)

        # Step-Up 3DS2 Risk Rule: transactions > $100 require dynamic step-up challenge
        if total > 100.0:
            # Generate cryptographically secure 6-digit OTP
            dynamic_otp = f"{secrets.randbelow(900000) + 100000}"
            expires_at = int(time.time()) + 300  # 5 minutes validity

            # Simulate outbound delivery (SMS / Email dispatch)
            recipient = address.city if address else "Customer"
            print("\n=======================================================")
            print(f"📲 [SMS GATEWAY DISPATCH] To cardholder in {recipient}")
            print(f"   Your 3DS2 One-Time Passcode is: {dynamic_otp}")
            print(f"   Valid for 5 minutes (Expires at unix: {expires_at})")
            print("=======================================================\n")

            return CheckoutSession(
                checkout_id=f"chk_{cart_id}",
                cart_id=cart_id,
                status="requires_action",
                shipping_address=address,
                items=items_list,
                total_price=total,
                currency="USD",
                policies=get_default_item_policies(),
                action_challenge={
                    "action_type": "3ds2_challenge",
                    "challenge_id": f"3ds_{cart_id[-8:]}",
                    "amount": total,
                    "currency": "USD",
                    "message": "High-value transaction requires 3DS2 cardholder verification.",
                    "expires_at": expires_at,
                    # Server retains dynamic code internally for verification
                    "_expected_otp": dynamic_otp,
                    "attempts_remaining": 3,
                },
            )

        return CheckoutSession(
            checkout_id=f"chk_{cart_id}",
            cart_id=cart_id,
            status="ready_for_complete",
            shipping_address=address,
            items=items_list,
            total_price=total,
            currency="USD",
            policies=get_default_item_policies(),
        )

    async def complete_order(
        self,
        checkout_id: str,
        payment_token: str,
        items: Optional[List[Dict[str, Any]]] = None,
        address: Optional[Dict[str, Any]] = None,
        attribution: Optional[AttributionContext] = None,
    ) -> Dict[str, Any]:
        attr = attribution or AttributionContext()
        lines = []
        if items:
            for item in items:
                raw_id = item.get("variant_id") or item.get("product_id") or ""
                match = re.search(r"\d+", str(raw_id))
                var_numeric = int(match.group(0)) if match else None
                entry: Dict[str, Any] = {
                    "title": item.get("title", "Product"),
                    "price": str(item.get("price", "0.00")),
                    "quantity": int(item.get("quantity", 1)),
                }
                if var_numeric:
                    entry["variant_id"] = var_numeric
                lines.append(entry)
        else:
            lines.append(
                {
                    "title": "General Merchandise",
                    "price": "39.00",
                    "quantity": 1,
                }
            )

        addr_data = address or {
            "first_name": "Valued",
            "last_name": "Customer",
            "address1": "100 Market Street",
            "city": "San Francisco",
            "zip": "94105",
            "country": "US",
        }

        # Shopify payload preserving Attribution Context (#391) and Policy tags (#572)
        payload = {
            "order": {
                "line_items": lines,
                "email": "customer.ucp.agent@example.com",
                "financial_status": "paid",
                "shipping_address": {
                    "first_name": addr_data.get("first_name", "Valued"),
                    "last_name": addr_data.get("last_name", "Customer"),
                    "address1": addr_data.get(
                        "address_line1",
                        addr_data.get("address1", "100 Market St"),
                    ),
                    "city": addr_data.get("city", "San Francisco"),
                    "zip": addr_data.get(
                        "postal_code", addr_data.get("zip", "94105")
                    ),
                    "country": addr_data.get("country", "US"),
                },
                "tags": f"UCP_Order,UCP_v2026-08-25,{attr.source_platform},{attr.campaign}",
                "note_attributes": [
                    {
                        "name": "ucp_source_platform",
                        "value": attr.source_platform,
                    },
                    {
                        "name": "ucp_referral_id",
                        "value": str(attr.referral_id),
                    },
                    {
                        "name": "ucp_policy_retention",
                        "value": "POL-30D-RET,POL-1Y-WARR",
                    },
                    {"name": "ucp_payment_token", "value": payment_token},
                ],
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.admin_orders_url,
                headers=self.admin_headers,
                json=payload,
                timeout=30.0,
            )
            if resp.status_code not in (200, 201):
                raise ValueError(
                    f"Shopify Admin Order commit failed ({resp.status_code}): {resp.text}"
                )

            created = resp.json().get("order", {})
            return {
                "order_id": str(created.get("id")),
                "order_number": f"#{created.get('order_number')}",
                "name": created.get("name"),
                "status": "completed",
                "financial_status": created.get("financial_status"),
                "total_price": created.get("total_price"),
                "currency": created.get("currency"),
                "policies": [
                    p.model_dump() for p in get_default_item_policies()
                ],
                "attribution": attr.model_dump(),
                "admin_url": f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/orders/{created.get('id')}",
            }