from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from services.public_money import format_cents
from services.public_money import parse_money_to_cents


class ModelPricingUpdateRequest(BaseModel):
    model: str = Field(..., min_length=1)
    price: str | int | float
    enabled: bool


class ActivationCodeBatchRequest(BaseModel):
    count: int = Field(..., ge=1)
    amount: str | int | float
    batch_note: str = Field(default="")


def register_admin_billing_routes(router: APIRouter, *, billing_store, require_auth_key) -> None:
    @router.get("/api/admin/billing/model-pricing")
    async def list_model_pricing(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": billing_store.list_model_pricing()}

    @router.post("/api/admin/billing/model-pricing")
    async def update_model_pricing(body: ModelPricingUpdateRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        model = _parse_model_name(body.model)
        updated = billing_store.update_model_pricing(
            model=model,
            price_cents=_parse_money(body.price),
            enabled=body.enabled,
        )
        if not updated:
            raise HTTPException(status_code=404, detail={"error": "model not found"})
        return {"items": updated}

    @router.get("/api/admin/billing/activation-codes")
    async def list_activation_codes(
        authorization: str | None = Header(default=None),
        status: str | None = None,
        batch_note: str | None = None,
        redeemed_username: str | None = None,
    ):
        require_auth_key(authorization)
        return {
            "items": _serialize_activation_codes(
                billing_store.list_activation_codes(
                    status=_normalize_optional_text(status),
                    batch_note=_normalize_optional_text(batch_note),
                    redeemed_username=_normalize_optional_text(redeemed_username),
                )
            )
        }

    @router.post("/api/admin/billing/activation-codes")
    async def create_activation_codes(body: ActivationCodeBatchRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": _serialize_activation_codes(billing_store.create_activation_codes(count=body.count, amount_cents=_parse_money(body.amount), batch_note=body.batch_note))}


def _parse_model_name(value: str) -> str:
    model = str(value or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail={"error": "model is required"})
    return model


def _parse_money(value: str | int | float) -> int:
    try:
        return parse_money_to_cents(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


def _serialize_activation_codes(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [_serialize_activation_code(item) for item in items]


def _serialize_activation_code(item: dict[str, object]) -> dict[str, object]:
    return {**item, "amount": format_cents(int(item["amount_cents"]))}


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
