# Image Studio Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 补齐图像工作台的默认模型、单次产图设置、额度展示、自动模式判断、失败重试与整组重跑能力。

**Architecture:** 后端继续以 `services.config` 和 `/api/image/settings` 作为唯一运行时配置来源，前端在设置页维护这组配置，并在图像页消费它来决定默认模型、张数上限和重试次数。会话记录保存足够的请求上下文，使“重新生成”可以复用同一条会话并整组重跑。

**Tech Stack:** FastAPI, Python unittest, Next.js App Router, React, TypeScript, localforage, Sonner

---

### Task 1: 补全后端图片运行时设置默认值测试

**Files:**
- Modify: `test/test_config.py`
- Test: `test/test_config.py`

**Step 1: Write the failing test**

增加断言，验证默认模型为 `gpt-image-2`，并保留 `max_count_per_request`、`auto_retry_times` 的持久化行为。

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest test.test_config`

**Step 3: Write minimal implementation**

如果测试暴露默认值或归一化缺口，只修改 `services/config.py`。

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest test.test_config`

### Task 2: 设置页接入图片生成设置

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/settings/page.tsx`

**Step 1: Write the failing usage path**

先在设置页引入缺失的图片设置请求函数和本地状态，触发 TypeScript 报错。

**Step 2: Run check to verify it fails**

Run: `npm run lint`

**Step 3: Write minimal implementation**

新增 `fetchImageSettings`/`updateImageSettings`，在设置页添加“图片生成设置”卡片，支持默认模型、单次最多产图张数、自动重试次数。

**Step 4: Run check to verify it passes**

Run: `npm run lint`

### Task 3: 图像页接入运行时设置与顶部额度卡片

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/image/page.tsx`
- Modify: `web/src/app/image/components/image-composer.tsx`

**Step 1: Write the failing usage path**

在图像页先引用新的运行时设置类型与顶部头部数据，让类型检查暴露未实现字段。

**Step 2: Run check to verify it fails**

Run: `npm run lint`

**Step 3: Write minimal implementation**

加载图片设置，默认模型改为 `gpt-image-2`，张数输入上限跟随后端配置，顶部展示 “GPT-image-2:共享平台” 与剩余额度信息块。

**Step 4: Run check to verify it passes**

Run: `npm run lint`

### Task 4: 自动模式判断、前端重试与整组重跑

**Files:**
- Modify: `web/src/store/image-conversations.ts`
- Modify: `web/src/app/image/page.tsx`
- Modify: `web/src/app/image/components/image-results.tsx`

**Step 1: Write the failing usage path**

先让会话结果区引用不存在的重跑元信息和重试入口，触发类型报错。

**Step 2: Run check to verify it fails**

Run: `npm run lint`

**Step 3: Write minimal implementation**

保存请求快照，提交时按参考图是否存在自动判断生成/编辑；单张失败按配置次数重试；结果区增加“重新生成”按钮并整组重跑。

**Step 4: Run check to verify it passes**

Run: `npm run lint`

### Task 5: 完整验证

**Files:**
- Verify: `test/test_config.py`
- Verify: `web/src/app/settings/page.tsx`
- Verify: `web/src/app/image/page.tsx`

**Step 1: Run backend tests**

Run: `python3 -m unittest test.test_config`

**Step 2: Run frontend static checks**

Run: `npm run lint`

**Step 3: Record actual outcomes**

如果有失败，按真实输出继续修；不写“应该可以”式结论。
