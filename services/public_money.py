from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MONEY_DECIMAL_PLACES = Decimal("0.01")
MONEY_SCALE = Decimal("100")


def parse_money_to_cents(value: str | int | float) -> int:
    amount = Decimal(str(value)).quantize(MONEY_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    return int(amount * MONEY_SCALE)


def format_cents(value: int) -> str:
    amount = (Decimal(value) / MONEY_SCALE).quantize(MONEY_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    return format(amount, "f")


def compute_cost_cents(*, price_cents: int, count: int) -> int:
    return price_cents * count
