from __future__ import annotations

from services.public_money import compute_cost_cents
from services.public_money import parse_money_to_cents


def test_parse_money_to_cents_uses_two_decimal_places() -> None:
    assert parse_money_to_cents("1.23") == 123
    assert parse_money_to_cents("0.50") == 50


def test_compute_request_cost_multiplies_price_by_n() -> None:
    assert compute_cost_cents(price_cents=125, count=3) == 375
