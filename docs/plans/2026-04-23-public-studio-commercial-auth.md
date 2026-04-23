# Public Studio Commercial Auth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build commercial authentication, personal quota, activation code recharge, and per-model pricing for the public image studio while keeping anonymous usage available.

**Architecture:** Add a SQLite-backed billing/auth subsystem alongside the existing public panel JSON quota system. Anonymous traffic continues to use `public_panel`, while authenticated traffic uses user balance and server-side session cookies. Pricing is centralized in a model pricing table and all balance changes are recorded in a ledger.

**Tech Stack:** FastAPI, SQLite (`sqlite3`), Next.js App Router, React, existing `sonner` UI, pytest, FastAPI TestClient

---

### Task 1: Add billing/auth persistence layer

**Files:**
- Create: `services/public_billing_store.py`
- Modify: `services/config.py`
- Test: `test/test_public_billing_store.py`

**Step 1: Write the failing tests**

```python
def test_store_bootstraps_default_model_prices(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    prices = store.list_model_pricing()

    assert [item["model"] for item in prices] == ["gpt-image-1", "gpt-image-2"]
    assert prices[0]["price"] == "1.00"


def test_store_creates_user_with_signup_bonus(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    user = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=100)

    assert user["username"] == "demo"
    assert user["balance"] == "1.00"
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_billing_store.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `PublicBillingStore`

**Step 3: Write minimal implementation**

```python
class PublicBillingStore:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self._init_db()

    def list_model_pricing(self) -> list[dict[str, str]]:
        ...

    def create_user(self, *, username: str, password_hash: str, signup_bonus_cents: int) -> dict[str, str]:
        ...
```

Implementation details:
- Initialize SQLite schema on first use
- Create tables: `users`, `user_sessions`, `activation_codes`, `quota_ledger`, `model_pricing`
- Seed `gpt-image-1` and `gpt-image-2`
- Store money as integer cents

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_billing_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/public_billing_store.py services/config.py test/test_public_billing_store.py
git commit -m "feat: add public billing store"
```

### Task 2: Add pricing and money helpers

**Files:**
- Create: `services/public_money.py`
- Test: `test/test_public_money.py`

**Step 1: Write the failing tests**

```python
def test_parse_money_to_cents_uses_two_decimal_places() -> None:
    assert parse_money_to_cents("1.23") == 123
    assert parse_money_to_cents("0.50") == 50


def test_compute_request_cost_multiplies_price_by_n() -> None:
    assert compute_cost_cents(price_cents=125, count=3) == 375
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_money.py -v`
Expected: FAIL because helper module is missing

**Step 3: Write minimal implementation**

```python
from decimal import Decimal, ROUND_HALF_UP


def parse_money_to_cents(value: str | int | float) -> int:
    ...


def format_cents(value: int) -> str:
    ...


def compute_cost_cents(*, price_cents: int, count: int) -> int:
    return price_cents * count
```

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_money.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/public_money.py test/test_public_money.py
git commit -m "feat: add public money helpers"
```

### Task 3: Add password hashing and session helpers

**Files:**
- Create: `services/public_auth_service.py`
- Test: `test/test_public_auth_service.py`

**Step 1: Write the failing tests**

```python
def test_hash_and_verify_password() -> None:
    service = PublicAuthService(...)
    hashed = service.hash_password("secret")

    assert hashed != "secret"
    assert service.verify_password("secret", hashed) is True
    assert service.verify_password("wrong", hashed) is False


def test_session_token_is_not_stored_in_plaintext(tmp_path: Path) -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_auth_service.py -v`
Expected: FAIL due to missing service

**Step 3: Write minimal implementation**

```python
class PublicAuthService:
    def hash_password(self, password: str) -> str:
        ...

    def verify_password(self, password: str, password_hash: str) -> bool:
        ...

    def create_session(self, user_id: str) -> tuple[str, dict[str, object]]:
        ...
```

Implementation details:
- Use salted PBKDF2 via standard library
- Generate random session token
- Persist only token hash

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_auth_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/public_auth_service.py test/test_public_auth_service.py
git commit -m "feat: add public auth service"
```

### Task 4: Add public auth API routes

**Files:**
- Create: `services/api_public_auth.py`
- Modify: `services/api.py`
- Test: `test/test_public_auth_api.py`

**Step 1: Write the failing tests**

```python
def test_register_creates_user_sets_cookie_and_returns_balance(tmp_path: Path) -> None:
    response = client.post("/api/public-auth/register", json={"username": "demo", "password": "secret"})

    assert response.status_code == 200
    assert response.json()["user"]["balance"] == "1.00"
    assert "set-cookie" in response.headers


def test_login_rejects_invalid_password(tmp_path: Path) -> None:
    ...


def test_redeem_requires_login(tmp_path: Path) -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_public_auth_api.py -v`
Expected: FAIL because routes do not exist

**Step 3: Write minimal implementation**

```python
def register_public_auth_routes(router: APIRouter, *, auth_service, billing_store) -> None:
    @router.post("/api/public-auth/register")
    async def register(...):
        ...

    @router.post("/api/public-auth/login")
    async def login(...):
        ...

    @router.post("/api/public-auth/logout")
    async def logout(...):
        ...

    @router.get("/api/public-auth/me")
    async def me(...):
        ...

    @router.post("/api/public-auth/redeem")
    async def redeem(...):
        ...
```

Implementation details:
- Set HttpOnly cookie on register/login
- Clear cookie on logout
- Require session for redeem/me

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_public_auth_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api.py services/api_public_auth.py test/test_public_auth_api.py
git commit -m "feat: add public auth api routes"
```

### Task 5: Add activation code generation and redeem logic

**Files:**
- Modify: `services/public_billing_store.py`
- Modify: `services/public_auth_service.py`
- Test: `test/test_public_activation_codes.py`

**Step 1: Write the failing tests**

```python
def test_generate_activation_codes_with_amount_and_batch_note(tmp_path: Path) -> None:
    codes = store.create_activation_codes(count=2, amount_cents=550, batch_note="april")

    assert len(codes) == 2
    assert all(len(item["code"]) == 32 for item in codes)


def test_redeem_activation_code_marks_it_used_and_adds_balance(tmp_path: Path) -> None:
    ...


def test_redeem_activation_code_cannot_be_reused(tmp_path: Path) -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_activation_codes.py -v`
Expected: FAIL because generation/redeem methods are incomplete

**Step 3: Write minimal implementation**

```python
def create_activation_codes(self, *, count: int, amount_cents: int, batch_note: str) -> list[dict[str, object]]:
    ...


def redeem_activation_code(self, *, code: str, user_id: str) -> dict[str, object]:
    ...
```

Implementation details:
- Use transaction for redeem
- Update `users.balance_cents`
- Update `activation_codes.status/redeemed_by_user_id/redeemed_at`
- Insert ledger row

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest python -m pytest test/test_public_activation_codes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/public_billing_store.py services/public_auth_service.py test/test_public_activation_codes.py
git commit -m "feat: add activation code billing flow"
```

### Task 6: Add model pricing management API

**Files:**
- Create: `services/api_admin_billing.py`
- Modify: `services/api.py`
- Test: `test/test_admin_billing_api.py`

**Step 1: Write the failing tests**

```python
def test_admin_can_list_model_pricing(tmp_path: Path) -> None:
    response = client.get("/api/admin/billing/model-pricing", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["model"] == "gpt-image-1"


def test_admin_can_update_model_pricing(tmp_path: Path) -> None:
    ...


def test_admin_can_batch_generate_activation_codes(tmp_path: Path) -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_admin_billing_api.py -v`
Expected: FAIL because admin billing routes do not exist

**Step 3: Write minimal implementation**

```python
@router.get("/api/admin/billing/model-pricing")
async def list_model_pricing(...):
    ...

@router.post("/api/admin/billing/model-pricing")
async def update_model_pricing(...):
    ...

@router.get("/api/admin/billing/activation-codes")
async def list_activation_codes(...):
    ...

@router.post("/api/admin/billing/activation-codes")
async def create_activation_codes(...):
    ...
```

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_admin_billing_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api.py services/api_admin_billing.py test/test_admin_billing_api.py
git commit -m "feat: add admin billing api"
```

### Task 7: Route anonymous and authenticated public image charging separately

**Files:**
- Modify: `services/image_workflow_service.py`
- Modify: `services/api_public_panel.py`
- Modify: `services/public_billing_store.py`
- Test: `test/test_image_workflow_service.py`
- Test: `test/test_public_panel_api.py`

**Step 1: Write the failing tests**

```python
def test_authenticated_public_generation_uses_user_balance_not_public_panel(tmp_path: Path) -> None:
    ...


def test_authenticated_public_generation_fails_when_balance_is_insufficient(tmp_path: Path) -> None:
    ...


def test_anonymous_public_generation_still_uses_public_panel_quota(tmp_path: Path) -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_image_workflow_service.py test/test_public_panel_api.py -v`
Expected: FAIL because current flow has only anonymous public quota behavior

**Step 3: Write minimal implementation**

```python
class ImageWorkflowService:
    def generate_public_anonymous(...):
        ...

    def generate_public_authenticated(...):
        ...
```

Implementation details:
- Read model pricing
- Compute cost from price × n
- Anonymous path reserves/commits `public_panel`
- Authenticated path debits user balance only on success

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_image_workflow_service.py test/test_public_panel_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/image_workflow_service.py services/api_public_panel.py services/public_billing_store.py test/test_image_workflow_service.py test/test_public_panel_api.py
git commit -m "feat: split anonymous and user image charging"
```

### Task 8: Build public login/register/redeem UI

**Files:**
- Create: `web/src/app/login/components/public-auth-panel.tsx`
- Modify: `web/src/app/login/login-page-client.tsx`
- Modify: `web/src/app/public-image-page-client.tsx`
- Create: `web/src/lib/public-auth-api.ts`
- Test: manual build validation

**Step 1: Write the failing test surrogate**

No frontend unit framework is present. Use build failure as the red gate.

Implementation target:

```tsx
<Tabs defaultValue="login">
  <TabsTrigger value="login">登录</TabsTrigger>
  <TabsTrigger value="register">注册</TabsTrigger>
</Tabs>
```

**Step 2: Run build to verify current behavior is missing**

Run: `npm run build`
Expected: current build passes, but login/register/redeem UI does not exist yet

**Step 3: Write minimal implementation**

Implementation details:
- Replace admin-like password-key page with public auth page
- Add `login/register` tabs
- Add cookie-based `me` fetch on load
- Add redeem modal/panel in public image page header
- Show personal balance in logged-in state

**Step 4: Run build to verify it passes**

Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/app/login/components/public-auth-panel.tsx web/src/app/login/login-page-client.tsx web/src/app/public-image-page-client.tsx web/src/lib/public-auth-api.ts
git commit -m "feat: add public auth ui"
```

### Task 9: Build admin billing page

**Files:**
- Create: `web/src/app/billing/page.tsx`
- Create: `web/src/app/billing/billing-page-client.tsx`
- Modify: `web/src/components/top-nav.tsx`
- Modify: `web/src/lib/api.ts`
- Test: manual build validation

**Step 1: Write the failing test surrogate**

No frontend unit framework is present. Use build failure as red gate after route/module creation.

Implementation target:

```tsx
const navItems = [
  { href: "/image", label: "画图" },
  { href: "/accounts", label: "号池管理" },
  { href: "/billing", label: "商业化" },
  { href: "/settings", label: "设置" },
];
```

**Step 2: Run build to verify current page is missing**

Run: `npm run build`
Expected: current build passes, but `/billing` route does not exist yet

**Step 3: Write minimal implementation**

Implementation details:
- Add model pricing table
- Add activation code generator form
- Add activation code list filters and result table
- Use admin auth request path

**Step 4: Run build to verify it passes**

Run: `npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/app/billing/page.tsx web/src/app/billing/billing-page-client.tsx web/src/components/top-nav.tsx web/src/lib/api.ts
git commit -m "feat: add admin billing page"
```

### Task 10: Run full verification and update docs

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-04-23-public-studio-commercial-auth-design.md`

**Step 1: Write the verification checklist**

Verification targets:
- public auth APIs
- activation code flows
- model pricing admin APIs
- image charge routing
- frontend build

**Step 2: Run tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_public_billing_store.py test/test_public_money.py test/test_public_auth_service.py test/test_public_auth_api.py test/test_public_activation_codes.py test/test_admin_billing_api.py test/test_image_workflow_service.py test/test_public_panel_api.py test/test_chat_completions_api.py
```

Expected: PASS

**Step 3: Run build**

Run: `npm run build`
Expected: PASS

**Step 4: Update README**

Add:
- public auth overview
- signup bonus behavior
- activation code management
- model pricing rule `price × n`

**Step 5: Commit**

```bash
git add README.md docs/plans/2026-04-23-public-studio-commercial-auth-design.md
git commit -m "docs: add public studio auth documentation"
```
