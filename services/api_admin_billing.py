from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

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
        updated = billing_store.update_model_pricing(
            model=body.model.strip(),
            price_cents=parse_money_to_cents(body.price),
            enabled=body.enabled,
        )
        if not updated:
            raise HTTPException(status_code=404, detail={"error": "model not found"})
        return {"items": updated}

    @router.get("/api/admin/billing/activation-codes")
    async def list_activation_codes(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": billing_store.list_activation_codes()}

    @router.post("/api/admin/billing/activation-codes")
    async def create_activation_codes(body: ActivationCodeBatchRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": billing_store.create_activation_codes(count=body.count, amount_cents=parse_money_to_cents(body.amount), batch_note=body.batch_note)}
