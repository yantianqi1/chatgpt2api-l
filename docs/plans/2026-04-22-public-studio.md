# 匿名公共生图面板 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不引入用户系统的前提下，为项目增加一个独立域名/独立端口的匿名公共生图面板，并用独立公共额度池隔离前台消费与后台号池。

**Architecture:** 保持一个 FastAPI 进程作为唯一状态拥有者，继续独占 `accounts.json` 和新的 `public_panel.json`。前端仍使用现有 Next 代码库，但构建出 `admin` 与 `studio` 两个静态产物；管理域名继续承载后台，公共域名只承载匿名图片工作台，并仅反代 `/api/public-panel/*`。

**Tech Stack:** FastAPI, Pydantic, Next.js static export, Axios, Docker multi-stage build, JSON file storage

---

### Task 1: 添加公共面板配置与额度服务

**Files:**
- Create: `services/public_panel_service.py`
- Modify: `services/config.py`
- Test: `test/test_public_panel_service.py`

**Step 1: 写失败测试，锁定公共面板配置行为**

```python
def test_service_loads_defaults_when_file_missing(tmp_path: Path) -> None:
    service = PublicPanelService(tmp_path / "public_panel.json")
    status = service.get_public_status()
    assert status["enabled"] is False
    assert status["quota"] == 0


def test_service_reserve_commit_and_release_quota(tmp_path: Path) -> None:
    service = PublicPanelService(tmp_path / "public_panel.json")
    service.update_config(enabled=True, quota=5, title="studio", description="demo")
    reservation = service.reserve_quota(3)
    service.commit_reservation(reservation)
    assert service.get_public_status()["quota"] == 2
```

**Step 2: 运行测试确认失败**

Run: `uv run python -m pytest test/test_public_panel_service.py -q`
Expected: FAIL，提示 `PublicPanelService` 未定义

**Step 3: 写最小实现**

```python
@dataclass(frozen=True)
class PublicPanelConfig:
    enabled: bool
    quota: int
    title: str
    description: str
    updated_at: str


class PublicPanelService:
    def __init__(self, store_file: Path):
        self.store_file = store_file
        self._lock = Lock()
```

实现内容只包含：

- 默认配置加载
- `get_public_status()`
- `get_admin_config()`
- `update_config(...)`
- `add_quota(amount)`
- `reserve_quota(count)`
- `commit_reservation(token)`
- `release_reservation(token)`

同时在 `services/config.py` 增加：

```python
public_panel_file=DATA_DIR / "public_panel.json"
```

**Step 4: 运行测试确认通过**

Run: `uv run python -m pytest test/test_public_panel_service.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/config.py services/public_panel_service.py test/test_public_panel_service.py
git commit -m "feat: add public panel quota service"
```

### Task 2: 抽离图片执行流程，支持公共额度预扣与失败回滚

**Files:**
- Create: `services/image_workflow_service.py`
- Modify: `services/chatgpt_service.py`
- Test: `test/test_image_workflow_service.py`

**Step 1: 写失败测试，锁定来源区分逻辑**

```python
def test_public_generation_rolls_back_quota_on_failure() -> None:
    quota = FakeQuotaGateway()
    backend = FakeImageBackend(error=ImageGenerationError("boom"))
    service = ImageWorkflowService(quota_gateway=quota, image_backend=backend)

    with pytest.raises(ImageGenerationError):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2)

    assert quota.released == [2]
```

**Step 2: 运行测试确认失败**

Run: `uv run python -m pytest test/test_image_workflow_service.py -q`
Expected: FAIL，提示 `ImageWorkflowService` 未定义

**Step 3: 写最小实现**

```python
class ImageWorkflowService:
    def generate_public(self, prompt: str, model: str, n: int) -> dict[str, object]:
        reservation = self.quota_gateway.reserve_quota(n)
        try:
            result = self.image_backend.generate_with_pool(prompt, model, n)
        except Exception:
            self.quota_gateway.release_reservation(reservation)
            raise
        self.quota_gateway.commit_reservation(reservation)
        return result
```

实现后把 `services/chatgpt_service.py` 中图片相关入口改成委托给 `ImageWorkflowService`，避免在 292 行的现有文件上继续堆逻辑。

**Step 4: 运行测试确认通过**

Run: `uv run python -m pytest test/test_image_workflow_service.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/chatgpt_service.py services/image_workflow_service.py test/test_image_workflow_service.py
git commit -m "refactor: extract source-aware image workflow"
```

### Task 3: 增加公共面板接口与管理接口

**Files:**
- Create: `services/api_public_panel.py`
- Modify: `services/api.py`
- Test: `test/test_public_panel_api.py`

**Step 1: 写失败测试，锁定接口边界**

```python
def test_public_status_does_not_require_admin_auth(client: TestClient) -> None:
    response = client.get("/api/public-panel/status")
    assert response.status_code == 200


def test_admin_public_panel_config_requires_auth(client: TestClient) -> None:
    response = client.get("/api/public-panel/config")
    assert response.status_code == 401
```

再加两个测试：

- 公共生成接口成功时扣减额度
- 公共生成接口失败时回滚额度

**Step 2: 运行测试确认失败**

Run: `uv run python -m pytest test/test_public_panel_api.py -q`
Expected: FAIL，提示路由不存在

**Step 3: 写最小实现**

在 `services/api_public_panel.py` 新增注册函数：

```python
def register_public_panel_routes(
    router: APIRouter,
    *,
    public_panel_service: PublicPanelService,
    image_workflow_service: ImageWorkflowService,
    require_auth_key: Callable[[str | None], None],
) -> None:
    ...
```

接口最少包括：

- `GET /api/public-panel/status`
- `GET /api/public-panel/config`
- `POST /api/public-panel/config`
- `POST /api/public-panel/quota/add`
- `POST /api/public-panel/images/generations`
- `POST /api/public-panel/images/edits`

并在 `services/api.py` 中只保留：

- 应用初始化
- 共享依赖构建
- 路由注册
- 静态资源兜底

避免继续把 `services/api.py` 从 420 行往上堆。

**Step 4: 运行测试确认通过**

Run: `uv run python -m pytest test/test_public_panel_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api.py services/api_public_panel.py test/test_public_panel_api.py
git commit -m "feat: add public panel api routes"
```

### Task 4: 拆分超大前端页面并引入应用变体

**Files:**
- Create: `web/src/lib/app-variant.ts`
- Create: `web/src/app/image/image-page-client.tsx`
- Create: `web/src/app/settings/settings-page-client.tsx`
- Create: `web/src/app/accounts/accounts-page-client.tsx`
- Modify: `web/src/app/image/page.tsx`
- Modify: `web/src/app/settings/page.tsx`
- Modify: `web/src/app/accounts/page.tsx`
- Modify: `web/src/app/login/page.tsx`
- Modify: `web/src/app/page.tsx`
- Modify: `web/src/components/top-nav.tsx`

**Step 1: 先写变体工具，避免页面里散落魔法字符串**

```ts
export type AppVariant = "admin" | "studio";

export function getAppVariant(): AppVariant {
  return process.env.NEXT_PUBLIC_APP_VARIANT === "studio" ? "studio" : "admin";
}

export function isStudioVariant() {
  return getAppVariant() === "studio";
}
```

**Step 2: 把现有超大页面拆成 server wrapper + client page**

做法：

- `page.tsx` 只负责做变体判断与 `notFound()`
- 原有客户端内容移动到 `*-page-client.tsx`

最少满足：

- `web/src/app/image/page.tsx` 不再保留 528 行客户端逻辑
- `web/src/app/settings/page.tsx` 不再保留 647 行客户端逻辑
- `web/src/app/accounts/page.tsx` 不再保留 823 行客户端逻辑

**Step 3: 在 wrapper 中实现变体路由边界**

约束：

- `studio` 变体下：`/accounts`、`/settings`、`/login` 必须 `notFound()`
- `admin` 变体下：保留现有页面
- `TopNav` 在 `studio` 变体不显示后台导航与退出按钮

**Step 4: 运行双构建验证**

Run: `cd web && NEXT_PUBLIC_APP_VARIANT=admin npm run build`
Expected: PASS

Run: `cd web && NEXT_PUBLIC_APP_VARIANT=studio npm run build`
Expected: PASS，且 studio 产物不再生成后台页面

**Step 5: Commit**

```bash
git add web/src/lib/app-variant.ts web/src/app web/src/components/top-nav.tsx
git commit -m "refactor: split frontend pages by app variant"
```

### Task 5: 管理端接入公共面板设置

**Files:**
- Create: `web/src/app/settings/components/public-panel-settings.tsx`
- Modify: `web/src/app/settings/settings-page-client.tsx`
- Modify: `web/src/lib/api.ts`

**Step 1: 扩展管理 API 客户端**

在 `web/src/lib/api.ts` 增加：

```ts
export async function fetchPublicPanelConfig() {
  return httpRequest<PublicPanelConfigResponse>("/api/public-panel/config");
}

export async function updatePublicPanelConfig(body: PublicPanelConfigUpdate) {
  return httpRequest<PublicPanelConfigResponse>("/api/public-panel/config", {
    method: "POST",
    body,
  });
}
```

**Step 2: 把设置页新功能放进独立组件**

不要继续把逻辑堆回 647 行的 `settings-page-client.tsx`。在 `public-panel-settings.tsx` 中单独处理：

- 开关
- 剩余额度展示
- 增加额度
- 标题/说明文案
- 保存按钮与提示

**Step 3: 在设置页挂接新组件**

只做组合，不写重复状态逻辑：

```tsx
<PublicPanelSettings />
```

**Step 4: 运行构建验证**

Run: `cd web && NEXT_PUBLIC_APP_VARIANT=admin npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/app/settings/components/public-panel-settings.tsx web/src/app/settings/settings-page-client.tsx web/src/lib/api.ts
git commit -m "feat: add public panel settings to admin"
```

### Task 6: 公共端接入匿名图片工作台

**Files:**
- Create: `web/src/lib/public-panel-api.ts`
- Create: `web/src/app/image/public-image-page-client.tsx`
- Modify: `web/src/app/image/page.tsx`
- Modify: `web/src/lib/request.ts`
- Modify: `web/src/app/page.tsx`

**Step 1: 新建公共 API 客户端，不复用管理员请求器**

```ts
export async function fetchPublicPanelStatus() {
  return publicRequest<PublicPanelStatus>("/api/public-panel/status");
}

export async function generatePublicImage(body: PublicGenerationBody) {
  return publicRequest<GenerationResponse>("/api/public-panel/images/generations", {
    method: "POST",
    body,
  });
}
```

要求：

- 不注入 `Authorization`
- 401 时不跳转 `/login`

**Step 2: 给图片页分成管理员版与公共版客户端**

公共版只保留：

- 文生图
- 编辑图
- 多图生成
- 本地历史记录
- 公共额度显示

管理员版继续保留当前逻辑。

**Step 3: 把额度来源改为公共状态**

公共版中把：

```ts
const data = await fetchAccounts();
setAvailableQuota(formatAvailableQuota(data.items));
```

替换成：

```ts
const status = await fetchPublicPanelStatus();
setAvailableQuota(String(status.quota));
```

生成提交时调用公共接口，不再访问 `/v1/images/*`。

**Step 4: 运行构建验证**

Run: `cd web && NEXT_PUBLIC_APP_VARIANT=studio npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/lib/public-panel-api.ts web/src/lib/request.ts web/src/app/image web/src/app/page.tsx
git commit -m "feat: add anonymous public studio client"
```

### Task 7: 产出双前端构建并增加公共服务部署

**Files:**
- Modify: `web/package.json`
- Modify: `web/next.config.ts`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Create: `deploy/nginx/studio.conf`

**Step 1: 为前端增加双构建脚本**

示例：

```json
{
  "scripts": {
    "build:admin": "NEXT_PUBLIC_APP_VARIANT=admin next build",
    "build:studio": "NEXT_PUBLIC_APP_VARIANT=studio next build"
  }
}
```

如果需要保留两个导出目录，可加一个小脚本把 `out/` 重命名到：

- `out-admin`
- `out-studio`

**Step 2: 调整 Docker 多阶段构建**

目标：

- 管理应用镜像内置 `web_dist_admin`
- 新公共静态镜像内置 `web_dist_studio`

可接受形式：

- 同一 `Dockerfile` 两个 target
- 或现有 `Dockerfile` + 新 `Dockerfile.studio`

只要最终得到两个服务即可。

**Step 3: 更新 Compose**

最少包含：

- `app`：当前管理应用
- `studio`：新的公共静态服务

公共域名的 `/api/public-panel/*` 仍反代到 `app`。

**Step 4: 跑构建级验证**

Run: `docker build --target app -t chatgpt2api-admin:test .`
Expected: PASS

Run: `docker build --target studio -t chatgpt2api-studio:test .`
Expected: PASS

**Step 5: Commit**

```bash
git add web/package.json web/next.config.ts Dockerfile docker-compose.yml README.md deploy/nginx/studio.conf
git commit -m "chore: add public studio build and deploy targets"
```

### Task 8: 全量验证与回归检查

**Files:**
- Test: `test/test_public_panel_service.py`
- Test: `test/test_image_workflow_service.py`
- Test: `test/test_public_panel_api.py`
- Verify: `web` build outputs

**Step 1: 跑后端测试**

Run: `uv run python -m pytest test/test_public_panel_service.py test/test_image_workflow_service.py test/test_public_panel_api.py -q`
Expected: PASS

**Step 2: 跑现有 API 回归测试**

Run: `uv run python -m pytest test/test_chat_completions_api.py -q`
Expected: PASS

**Step 3: 跑双前端构建**

Run: `cd web && npm run build:admin && npm run build:studio`
Expected: PASS

**Step 4: 做路由验收**

最少人工验证：

- 管理站能访问 `/accounts`、`/settings`
- 公共站访问 `/accounts` 返回 404
- 公共站能读取公共额度并完成图片生成
- 管理站生成图片不扣公共额度

**Step 5: Commit**

```bash
git add .
git commit -m "test: verify anonymous public studio split"
```
