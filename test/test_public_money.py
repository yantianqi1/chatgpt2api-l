from __future__ import annotations

import pytest

from services.public_money import compute_cost_cents
from services.public_money import format_cents
from services.public_money import parse_money_to_cents


def test_parse_money_to_cents_uses_two_decimal_places() -> None:
    assert parse_money_to_cents("1.23") == 123
    assert parse_money_to_cents("0.50") == 50
    assert parse_money_to_cents("1.235") == 124


def test_compute_request_cost_multiplies_price_by_n() -> None:
    assert compute_cost_cents(price_cents=125, count=3) == 375


def test_format_cents_uses_two_decimal_places() -> None:
    assert format_cents(124) == "1.24"
    assert format_cents(-50) == "-0.50"


def test_compute_cost_cents_rejects_bool_and_negative_count() -> None:
    with pytest.raises(TypeError, match="count must be an int"):
        compute_cost_cents(price_cents=125, count=True)

    with pytest.raises(ValueError, match="count must be greater than or equal to 0"):
        compute_cost_cents(price_cents=125, count=-1)


def test_parse_money_to_cents_rejects_bool_and_invalid_input() -> None:
    with pytest.raises(TypeError, match="value must be a number or numeric string"):
        parse_money_to_cents(True)

    with pytest.raises(ValueError, match="value must be a valid money amount"):
        parse_money_to_cents("abc")
