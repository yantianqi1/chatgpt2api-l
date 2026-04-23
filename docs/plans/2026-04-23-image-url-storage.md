# Image URL Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将图片结果改为本地落盘并通过本服务返回稳定 URL，默认替换现有 `b64_json` 输出。

**Architecture:** 后端在拿到上游下载链接后下载图片二进制，保存到 `data/generated-images/`，通过 `CHATGPT2API_PUBLIC_BASE_URL` 拼接绝对 URL，并由 FastAPI 挂载静态路径。图片 API 默认返回 `url`；前端改为优先消费 `url`，并兼容旧的 `b64_json` 历史数据。

**Tech Stack:** FastAPI, StaticFiles, local filesystem, existing curl_cffi download flow, Next.js frontend

---

### Task 1: Add failing backend tests

**Files:**
- Modify: `test/test_chat_completions_api.py`
- Modify: `test/test_config.py`
- Modify: `test/test_public_panel_api.py`

**Step 1: Write the failing tests**

- 配置层读取 `.env` 中的 `CHATGPT2API_PUBLIC_BASE_URL`
- `chat/completions` 图片结果默认返回 Markdown URL
- `responses` 图片结果默认返回 URL
- 公共面板图片接口返回 `url`

**Step 2: Run tests to verify they fail**

Run: `uv run pytest test/test_config.py test/test_chat_completions_api.py test/test_public_panel_api.py -q`

**Step 3: Implement the minimal code to make them pass**

- 新增配置字段与 URL 输出逻辑

**Step 4: Re-run tests**

Run: `uv run pytest test/test_config.py test/test_chat_completions_api.py test/test_public_panel_api.py -q`

**Step 5: Commit**

```bash
git add test/test_config.py test/test_chat_completions_api.py test/test_public_panel_api.py services/config.py services/utils.py services/chatgpt_service.py
git commit -m "feat: return generated image urls by default"
```

### Task 2: Add local file storage and static hosting

**Files:**
- Create: `services/generated_image_store.py`
- Modify: `services/image_service.py`
- Modify: `services/api.py`
- Modify: `docker-compose.yml`
- Modify: `.gitignore`

**Step 1: Write the failing test**

- 验证图片能写入 `data/generated-images`
- 验证 `/generated-images/...` 可访问

**Step 2: Run test to verify it fails**

Run: `uv run pytest test/test_chat_completions_api.py -q`

**Step 3: Write minimal implementation**

- 下载图片二进制并落盘
- 构建绝对 URL
- 挂载静态文件路由
- Compose 传入 `.env`

**Step 4: Re-run tests**

Run: `uv run pytest test/test_chat_completions_api.py -q`

**Step 5: Commit**

```bash
git add services/generated_image_store.py services/image_service.py services/api.py docker-compose.yml .gitignore
git commit -m "feat: store generated images locally"
```

### Task 3: Update frontend for URL-first rendering

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/store/image-conversations.ts`
- Modify: `web/src/app/image/page.tsx`
- Modify: `web/src/app/public-image-page-client.tsx`
- Modify: `web/src/app/image/components/image-results.tsx`

**Step 1: Write the failing test or verify broken type usage**

- 确认前端仍假设只有 `b64_json`

**Step 2: Implement minimal compatibility**

- 请求 `response_format: "url"`
- 存储结构支持 `url`
- 渲染优先使用 `url`，回退旧 `b64_json`

**Step 3: Run relevant verification**

Run: `npm --prefix web run build`

**Step 4: Commit**

```bash
git add web/src/lib/api.ts web/src/store/image-conversations.ts web/src/app/image/page.tsx web/src/app/public-image-page-client.tsx web/src/app/image/components/image-results.tsx
git commit -m "feat: render generated images from urls"
```

### Task 4: Final verification

**Files:**
- Verify only

**Step 1: Run backend tests**

Run: `uv run pytest test/test_config.py test/test_chat_completions_api.py test/test_public_panel_api.py test/test_image_workflow_service.py -q`

**Step 2: Run frontend build**

Run: `npm --prefix web run build`

**Step 3: Rebuild and start container**

Run: `docker compose up -d --build`

**Step 4: Smoke check endpoints**

Run:

```bash
curl -i http://127.0.0.1:8081/v1/models -H 'Authorization: Bearer chatgpt2api'
curl -i http://127.0.0.1:8081/
```

**Step 5: Commit**

```bash
git add .
git commit -m "feat: serve generated images from local urls"
```
