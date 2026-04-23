# ChatGPT2API Public Studio 漫创集成设计

**目标**

把“小说/章节文本 -> AI 拆章 -> 分镜脚本 -> 分镜图片集”的漫创能力，合并到 `chatgpt2api-l` 的公开生图主模块里，同时保留后续把该模块拆成独立图像创作平台的边界。

## 现状结论

基于对 `chatgpt2api-l` `main` 分支的结构检查，当前事实如下：

- 前端不是独立 SPA，而是 `web/src/app` 下的 Next.js App Router。
- 公开生图主入口在 [web/src/app/page.tsx](/Volumes/Fanxiang%20S500Pro/%E9%A1%B9%E7%9B%AE/chatgpt2api-l/web/src/app/page.tsx)；`studio` 变体下它直接渲染 `PublicImagePageClient`。
- 当前公开生图工作台核心在 [web/src/app/public-image-page-client.tsx](/Volumes/Fanxiang%20S500Pro/%E9%A1%B9%E7%9B%AE/chatgpt2api-l/web/src/app/public-image-page-client.tsx)，它复用了 `image` 模块的输入框、历史记录和结果展示组件。
- 后端主入口在 [services/api.py](/Volumes/Fanxiang%20S500Pro/%E9%A1%B9%E7%9B%AE/chatgpt2api-l/services/api.py)，框架是 FastAPI，当前已经有公开生图路由注册点 [services/api_public_panel.py](/Volumes/Fanxiang%20S500Pro/%E9%A1%B9%E7%9B%AE/chatgpt2api-l/services/api_public_panel.py)。
- 后端已经有可复用的文生文和生图能力：
  - `ChatGPTService.generate_text_with_pool(...)`
  - `ChatGPTService.generate_with_pool(...)`
  - `ChatGPTService.edit_with_pool(...)`
- 当前项目的数据持久化风格是“本地 JSON/文件存储”，而不是数据库。`accounts.json`、`public_panel.json`、`generated-images/` 都是这个模式。

结论很明确：**不要把漫创模块按 `Express + Prisma + SQLite` 独立移植进来**。这样会在一个已经是 `FastAPI + Next + 本地 JSON` 的项目里硬塞第二套后端技术栈，后期维护和拆分都会变差。

## 核心决策

### 决策 1：合并到 public studio 壳层，但不塞进现有单文件页面

不把所有漫创 UI 直接堆进 `public-image-page-client.tsx`。  
改为：

- 保留 `/` 继续作为现有“单图生图”入口
- 新增 `/comic` 作为“漫创工作台”
- 在 `studio` 变体下增加一个轻量导航，在“单图创作 / 漫创工作台”之间切换

这样既满足“合并进公开生图主模块”，又避免把现有首页变成无法维护的大组件。

### 决策 2：前端按功能隔离，后续可整块拆出

新增前端代码统一收敛到：

- `web/src/app/comic/*`
- `web/src/features/comic/*`

`app/comic` 只负责路由入口，具体业务、组件、请求、轮询逻辑都放在 `features/comic`。  
这样后续想拆成独立产品时，可以整体迁移 `features/comic` 和对应 route wrapper，而不用从现有 image studio 组件里剥代码。

### 决策 3：后端新增 comic 子域，不污染现有 image/public-panel 服务

新增后端代码统一收敛到：

- `services/comic/*`
- `services/api_comic.py`

现有的 `api_public_panel.py` 继续专注公开生图配额与匿名图片生成；漫创是一个新的功能子域，不复用“public panel config”那套语义。

### 决策 4：沿用目标项目的文件存储风格，不引入数据库

漫创数据落地采用本地目录 + JSON 文件：

```text
data/
  comic-projects/
    {project_id}/
      project.json
      characters.json
      chapters/
        {chapter_id}.json
      scenes/
        {scene_id}.json
      tasks/
        {task_id}.json
      assets/
        scene-{scene_id}/
          {asset_id}.png
      source/
        original.txt
```

理由：

- 目标项目已经是这个风格，接入成本最低
- 不需要为首版引入 SQLite、Prisma、迁移体系
- 后续拆分时，这套数据目录也更容易整体搬迁

### 决策 5：长任务用“本地持久化任务 + 进程内 worker”

漫创里所有耗时操作都后台化：

- AI 拆章
- 章节生成分镜
- 单条重写分镜
- 单张出图
- 批量出图

实现方式不是 Redis / Celery / SQLite 队列，而是：

- JSON 持久化任务文件
- FastAPI 进程内 worker 线程
- 前端定时轮询任务状态

这和当前项目的部署模型、复杂度等级一致。

## 集成方案

### 前端集成

`studio` 变体下新增一个公共工作台导航：

- `/`：单图创作
- `/comic`：漫创工作台

其中：

- [web/src/app/page.tsx](/Volumes/Fanxiang%20S500Pro/%E9%A1%B9%E7%9B%AE/chatgpt2api-l/web/src/app/page.tsx) 继续渲染 `PublicImagePageClient`
- 新增 `web/src/app/comic/page.tsx`
- `layout.tsx` 在 `studio` 变体下显示 `StudioNav`

漫创页面结构建议为：

- 项目列表
- 项目总览
- 角色卡编辑
- 章节列表
- 章节工作台
- 分镜工作台
- 任务面板

其中项目总览、章节和分镜工作台保持同页切换或侧边切换，不做太深路由，以降低首版复杂度。

### 后端集成

新增 API 前缀：

- `GET /api/comic/projects`
- `POST /api/comic/projects`
- `GET /api/comic/projects/{project_id}`
- `PATCH /api/comic/projects/{project_id}`
- `DELETE /api/comic/projects/{project_id}`
- `POST /api/comic/projects/{project_id}/import`
- `GET /api/comic/projects/{project_id}/characters`
- `POST /api/comic/projects/{project_id}/characters`
- `PATCH /api/comic/projects/{project_id}/characters/{character_id}`
- `GET /api/comic/projects/{project_id}/chapters`
- `PATCH /api/comic/projects/{project_id}/chapters/{chapter_id}`
- `POST /api/comic/projects/{project_id}/chapters/{chapter_id}/generate-script`
- `GET /api/comic/projects/{project_id}/scenes`
- `PATCH /api/comic/projects/{project_id}/scenes/{scene_id}`
- `POST /api/comic/projects/{project_id}/scenes/{scene_id}/render`
- `POST /api/comic/projects/{project_id}/chapters/{chapter_id}/render-batch`
- `GET /api/comic/tasks`
- `POST /api/comic/tasks/{task_id}/retry`

这些接口分成两类：

- 同步 CRUD：立即返回
- 任务触发：只创建任务，真正执行交给 worker

### 文本与图片能力复用

漫创不需要再造一套模型调用链，直接复用目标项目已有能力：

- 拆章、生成分镜：复用 `ChatGPTService.generate_text_with_pool(...)`
- 分镜出图：复用 `ChatGPTService.generate_with_pool(...)`
- 后续如需参考图重绘：复用 `ChatGPTService.edit_with_pool(...)`

为避免业务层直接拼大段字符串，新增 `services/comic/prompts.py`：

- `build_chapter_split_prompt(...)`
- `build_scene_script_prompt(...)`
- `build_scene_rewrite_prompt(...)`
- `build_scene_render_prompt(...)`

## 为什么不选其他方案

### 方案 A：把漫创直接塞进 `public-image-page-client.tsx`

不选。  
这是最短路径，但会立即把现有首页变成高耦合巨型组件，后续拆分最痛苦。

### 方案 B：现在就做成独立仓库 / 独立平台

不选。  
你现在的目标是“先接进现有公开生图主模块”，那就优先复用现成账号池、文生文、生图、Next 壳层和部署链路。现在就拆仓库，会重复造太多基础设施。

### 方案 C：引入数据库和外部队列

不选。  
这和 `chatgpt2api-l` 当前技术基线不一致，首版收益不够，复杂度过高。

## 后续可拆分边界

为了让未来独立成图像创作平台更轻松，这次集成必须保持下面几个边界：

1. 漫创前端只依赖：
   - `web/src/features/comic/*`
   - 少量 shared ui 组件
   - 一个 `comic-api.ts`

2. 漫创后端只依赖：
   - `services/comic/*`
   - `services/chatgpt_service.py`
   - 通用配置与文件工具

3. 公开生图首页和漫创工作台只共享壳层，不共享业务状态

这样未来拆分时，实际需要处理的只有：

- 把 `services/comic/*` 和相关 API 提取出来
- 把 `web/src/features/comic/*` 和 `app/comic` 提取出来
- 再决定是否把文件存储换成数据库

## 实施建议

实施时不要基于当前工作树的 `wip/main-before-public-studio-merge` 直接开做。  
因为你明确点的是“主分支那个公开生图界面”。更稳的做法是：

- 以 `main` 为基线开新分支
- 先把 comic 模块按上面方案接进去
- 再决定是否把 `wip/main-before-public-studio-merge` 上的变更挑回来

否则你会在“历史 WIP 差异”和“新漫创集成”之间同时处理两类不确定性，调试成本会明显升高。
