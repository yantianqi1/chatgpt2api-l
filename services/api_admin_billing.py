from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from services.public_money import format_cents, parse_money_to_cents


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
        updated = _update_model_pricing(
            billing_store.db_file,
            model=body.model.strip(),
            price_cents=parse_money_to_cents(body.price),
            enabled=body.enabled,
        )
        if not updated:
            raise HTTPException(status_code=404, detail={"error": "model not found"})
        return {"items": billing_store.list_model_pricing()}

    @router.get("/api/admin/billing/activation-codes")
    async def list_activation_codes(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": _list_activation_codes(billing_store.db_file)}

    @router.post("/api/admin/billing/activation-codes")
    async def create_activation_codes(body: ActivationCodeBatchRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        rows = billing_store.create_activation_codes(
            count=body.count,
            amount_cents=parse_money_to_cents(body.amount),
            batch_note=body.batch_note,
        )
        return {"items": [_format_activation_code(row) for row in rows]}


def _update_model_pricing(db_file, *, model: str, price_cents: int, enabled: bool) -> bool:
    with sqlite3.connect(db_file) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.execute(
            "UPDATE model_pricing SET price_cents = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE model = ?",
            (price_cents, 1 if enabled else 0, model),
        )
    return cursor.rowcount > 0


def _list_activation_codes(db_file) -> list[dict[str, object]]:
    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, code, amount_cents, batch_note, status, created_at, redeemed_by_user_id, redeemed_at
            FROM activation_codes
            ORDER BY id DESC
            """
        ).fetchall()
    return [_format_activation_code(row) for row in rows]


def _format_activation_code(row: sqlite3.Row | dict[str, object]) -> dict[str, object]:
    redeemed_by_user_id = row["redeemed_by_user_id"]
    redeemed_at = row["redeemed_at"]
    return {
        "id": str(row["id"]),
        "code": str(row["code"]),
        "amount": format_cents(int(row["amount_cents"])),
        "batch_note": str(row["batch_note"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "redeemed_by_user_id": None if redeemed_by_user_id is None else str(redeemed_by_user_id),
        "redeemed_at": None if redeemed_at is None else str(redeemed_at),
    }
