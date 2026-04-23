# Image URL Storage Design

## Goal

把图片生成结果从超长 `base64` 响应改为“本机磁盘存储 + 本服务静态托管 + 对外返回稳定 URL”，降低 `chat/completions` / `responses` / `/v1/images/*` 的响应体积，避免中转层超时。

## Current Problem

- 上游下载链接已获取到，但服务端又把图片完整下载并转成 `b64_json`
- `chat/completions` 再把 `b64_json` 包进 `data:image/...;base64,...` 文本
- `stream=true` 也会把整段超长内容一次性塞进单个 SSE 事件
- 外部中转层需要转发、渲染、记录超长文本，容易触发 504

## Chosen Approach

采用本地磁盘存储，并由当前 FastAPI 服务直接托管静态文件：

1. 上游生成完成后，服务端下载图片二进制
2. 图片写入 `data/generated-images/`
3. 通过 `CHATGPT2API_PUBLIC_BASE_URL` 生成绝对 URL
4. FastAPI 挂载 `/generated-images`
5. 所有图片 API 默认返回 `url`

## API Behavior

### `/v1/images/generations` and `/v1/images/edits`

- 默认 `response_format` 改为 `url`
- 保留 `b64_json` 兼容能力，显式请求时仍可返回 `b64_json`
- `url` 模式下返回：

```json
{
  "created": 1710000000,
  "data": [
    {
      "url": "https://example.com/generated-images/abc.png",
      "revised_prompt": "..."
    }
  ]
}
```

### `/v1/chat/completions`

- 图片请求默认返回 Markdown 图片链接
- 例如：`![image_1](https://example.com/generated-images/abc.png)`
- 不再默认返回 `data:image/...base64,...`

### `/v1/responses`

- 图片工具输出默认把 `output[].result` 改为 URL
- 保持结构不变，只改变结果内容

## Configuration

新增环境变量：

- `CHATGPT2API_PUBLIC_BASE_URL`
  - 示例：`https://api.example.com`
  - 用于拼接静态图片绝对地址

支持两种加载方式：

- 进程环境变量
- 项目根目录 `.env`

Docker Compose 运行时通过 `env_file: .env` 传入容器。

## Storage

- 存储目录：`data/generated-images/`
- 文件名：UUID + 推断扩展名
- 托管路径：`/generated-images/<filename>`

第一版不做清理任务，不引入数据库，不加 CDN 特性，先把响应体缩小和链路稳定性问题解决掉。

## Frontend Compatibility

项目自带前端目前依赖 `b64_json`。需要同步改成：

- 优先使用 `url`
- 回退兼容旧历史里的 `b64_json`

这样旧会话不丢，新生成结果走 URL。

## Risks

- 若 `CHATGPT2API_PUBLIC_BASE_URL` 配错，外部访问会拿到错误链接
- 若服务部署在多实例且未共享磁盘，图片 URL 会跨实例失效
- 若磁盘未清理，长期运行会增长

## Non-Goals

- 不实现对象存储
- 不做图片过期回收
- 不做签名 URL
- 不改变上游生成逻辑
