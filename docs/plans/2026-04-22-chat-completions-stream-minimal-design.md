# Chat Completions Stream Minimal Design

**Date:** 2026-04-22

## Goal

对 `POST /v1/chat/completions` 和 `POST /v1/responses` 的 `stream=true` 请求做最小兼容：
不再返回 `400`，而是按非流式路径直接返回普通 JSON。

## Context

当前实现会在服务层直接拒绝 `stream=true`，导致依赖流式开关但可接受非流式结果的客户端无法继续工作。
这次不实现 SSE，也不伪造流式协议，只移除硬拒绝分支，让请求落到现有同步处理逻辑。

## Options

### Option 1: 忽略 `stream` 并返回普通 JSON

- 改动最小
- 与现有结果结构完全一致
- 能解决“客户端默认带 stream=true 就失败”的兼容问题
- 不兼容严格要求 `text/event-stream` 的客户端

### Option 2: 返回兼容型 SSE

- 对客户端兼容性更高
- 需要新增流式响应封装
- 超出这次“最小修复”范围

## Decision

采用 Option 1。

## Scope

- 去掉服务层对 `stream=true` 的 `400` 拒绝
- 保持现有请求解析和响应结构不变
- 增加回归测试，确保 `stream=true` 时仍返回 `200`

## Out of Scope

- 真正的上游实时流式透传
- 本地伪 SSE 包装
- 新增限流、降级或静默 fallback 规则
