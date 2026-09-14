import pytest
try:
    from service import calculate_discount, process_order, get_health_status
except ModuleNotFoundError:
    from demo_app.service import calculate_discount, process_order, get_health_status


def test_health_check():
    health = get_health_status()
    assert health["status"] == "healthy"
    assert health["service"] == "billing-service"


def test_calculate_discount_normal():
    # Normal case: valid non-zero discount factor
    res = calculate_discount(100.0, 2, discount_factor=10.0)
    assert res is not None
    assert isinstance(res, (int, float))


def test_calculate_discount_zero_edge_case():
    # Edge case: zero discount factor should not crash with unhandled ZeroDivisionError
    res = calculate_discount(100.0, 2, discount_factor=0.0)
    assert res is not None
    assert isinstance(res, (int, float))


def test_process_order_empty_cart():
    res = process_order({"items": []})
    assert res["success"] is False
