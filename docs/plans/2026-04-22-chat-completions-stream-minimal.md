# Chat Completions Stream Minimal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `stream=true` 的聊天与图片聊天请求不再被 `400` 拒绝，而是按现有非流式逻辑直接返回 JSON。

**Architecture:** 保持 API 路由和响应结构不变，只移除服务层对 `stream` 的硬拒绝。通过测试锁定文本聊天、图片聊天和 Responses 的最小兼容行为，避免误改请求解析逻辑。

**Tech Stack:** FastAPI, unittest, TestClient

---

### Task 1: 为 chat completions 补失败测试

**Files:**
- Modify: `test/test_chat_completions_api.py`
- Test: `test/test_chat_completions_api.py`

**Step 1: Write the failing test**

增加两个测试：
- 文本聊天在 `stream=true` 时返回 `200`
- 图片聊天在 `stream=true` 时返回 `200`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest test/test_chat_completions_api.py -q`
Expected: FAIL，错误来自当前 `stream is not supported`

**Step 3: Write minimal implementation**

删除服务层对 `stream` 的 `400` 拒绝分支。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest test/test_chat_completions_api.py -q`
Expected: PASS

**Step 5: Commit**

在所有验证通过后再统一提交。

### Task 2: 为 responses 补失败测试

**Files:**
- Modify: `test/test_chat_completions_api.py`
- Test: `test/test_chat_completions_api.py`

**Step 1: Write the failing test**

增加 `POST /v1/responses` 在 `stream=true` 时返回 `200` 的测试。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest test/test_chat_completions_api.py -q`
Expected: FAIL，错误来自当前 `stream is not supported`

**Step 3: Write minimal implementation**

删除 `create_response` 中对 `stream` 的 `400` 拒绝分支。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest test/test_chat_completions_api.py -q`
Expected: PASS

**Step 5: Commit**

在所有验证通过后再统一提交。
