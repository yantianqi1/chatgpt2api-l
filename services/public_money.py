from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MONEY_DECIMAL_PLACES = Decimal("0.01")
MONEY_SCALE = Decimal("100")


def parse_money_to_cents(value: str | int | float) -> int:
    amount = _parse_money_decimal(value)
    return int(amount * MONEY_SCALE)


def format_cents(value: int) -> str:
    cents = _require_int(value, "value")
    amount = (Decimal(cents) / MONEY_SCALE).quantize(MONEY_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    return format(amount, "f")


def compute_cost_cents(*, price_cents: int, count: int) -> int:
    price = _require_int(price_cents, "price_cents")
    quantity = _require_int(count, "count", minimum=0)
    return price * quantity


def _parse_money_decimal(value: str | int | float) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TypeError("value must be a number or numeric string")

    try:
        return Decimal(str(value)).quantize(MONEY_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("value must be a valid money amount") from error


def _require_int(value: object, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be greater than or equal to {minimum}")
    return value
