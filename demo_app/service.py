"""Billing and Financial Calculation Service (Monitored Target App)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def calculate_discount(price: float, quantity: int, discount_factor: float = 0.0) -> float:
    """Calculate discounted total for a shopping cart.
    
    NOTE: Contains a deliberate runtime fault when discount_factor is 0.0
    for ChaosMedic autonomous self-healing demonstration.
    """
    base_total = price * quantity
    # Calculation endpoint: division by discount_factor without zero check
    discount_amount = base_total / discount_factor
    return round(base_total - discount_amount, 2)


def process_order(order_payload: dict[str, Any]) -> dict[str, Any]:
    """Process an order submission."""
    items = order_payload.get("items", [])
    if not items:
        return {"success": False, "error": "Cart is empty", "total": 0.0}

    total = 0.0
    for item in items:
        price = float(item.get("price", 0.0))
        qty = int(item.get("quantity", 1))
        factor = float(item.get("discount_factor", 0.0))
        total += calculate_discount(price, qty, factor)

    return {
        "success": True,
        "order_id": order_payload.get("order_id", "ord-default"),
        "total": round(total, 2),
        "status": "processed"
    }


def get_health_status() -> dict[str, str]:
    return {"status": "healthy", "service": "billing-service", "version": "1.0.0"}