# ChatGPT2API Public Studio Comic Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate a local-first comic creation workspace into `chatgpt2api-l`'s public studio shell without breaking the existing single-image experience, while keeping the comic feature isolated enough to extract later.

**Architecture:** Keep the existing public image page at `/`, add a studio-only `/comic` route, and implement the comic domain as a separate backend package under `services/comic/` plus a route entry in `services/api_comic.py`. Persist projects, chapters, scenes, tasks, and rendered assets under `data/comic-projects/`, and run long jobs through an in-process worker that reuses `ChatGPTService` for both text generation and scene image rendering.

**Tech Stack:** FastAPI, Python 3.13, local JSON/file storage, existing account-pool-backed `ChatGPTService`, Next.js 16 App Router, TypeScript, existing shared UI components.

---

## Preconditions

- Implement from `chatgpt2api-l` `main`, not from `wip/main-before-public-studio-merge`.
- Keep the current public image page working throughout; do not replace it with the comic workflow.
- Do not introduce SQLite, Redis, Celery, Prisma, or a second backend stack.

### Task 1: Add comic storage models and file-backed project store

**Files:**
- Create: `services/comic/__init__.py`
- Create: `services/comic/models.py`
- Create: `services/comic/store.py`
- Modify: `services/config.py`
- Test: `test/test_comic_store.py`

**Step 1: Write the failing test**

Cover these cases in `test/test_comic_store.py`:

- creating a project creates `data/comic-projects/{project_id}/project.json`
- characters, chapters, scenes, and tasks are saved under predictable subdirectories
- deleting a project removes its whole directory tree
- loading a missing project raises a clear error

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest test/test_comic_store.py -q
```

Expected: FAIL because `services.comic.store` and related models do not exist yet.

**Step 3: Write minimal implementation**

Implement:

- immutable dataclasses or typed dict models for `ComicProject`, `CharacterProfile`, `ComicChapter`, `ComicScene`, `ComicTask`, `ComicAsset`
- a `ComicProjectStore` that manages:
  - `list_projects()`
  - `create_project(...)`
  - `get_project(...)`
  - `save_characters(...)`
  - `save_chapter(...)`
  - `save_scene(...)`
  - `save_task(...)`
  - `delete_project(...)`
- config helper in `services/config.py` for `comic_projects_dir`

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest test/test_comic_store.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add services/comic/__init__.py services/comic/models.py services/comic/store.py services/config.py test/test_comic_store.py
git commit -m "feat: add comic project file store"
```

### Task 2: Add prompt builders and comic workflow service

**Files:**
- Create: `services/comic/prompts.py`
- Create: `services/comic/workflow.py`
- Test: `test/test_comic_workflow.py`

**Step 1: Write the failing test**

Cover these cases:

- chapter split prompt includes source text and requests strict JSON
- scene script prompt injects chapter text, style prompt, and only relevant characters
- render prompt composes global style + scene description + character appearance
- workflow methods call `ChatGPTService.generate_text_with_pool(...)` or `generate_with_pool(...)` with the built prompt

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest test/test_comic_workflow.py -q
```

Expected: FAIL because prompt builders and workflow service do not exist.

**Step 3: Write minimal implementation**

Implement:

- `build_chapter_split_prompt(...)`
- `build_scene_script_prompt(...)`
- `build_scene_rewrite_prompt(...)`
- `build_scene_render_prompt(...)`
- `ComicWorkflowService` with methods:
  - `split_chapters(...)`
  - `generate_scene_script(...)`
  - `rewrite_scene(...)`
  - `render_scene(...)`

Make parsing explicit. If JSON parsing fails, raise a domain error instead of silently repairing output.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest test/test_comic_workflow.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add services/comic/prompts.py services/comic/workflow.py test/test_comic_workflow.py
git commit -m "feat: add comic workflow and prompt builders"
```

### Task 3: Add persistent comic task service and in-process worker

**Files:**
- Create: `services/comic/tasks.py`
- Create: `services/comic/worker.py`
- Modify: `services/api.py`
- Test: `test/test_comic_tasks.py`

**Step 1: Write the failing test**

Cover these cases:

- creating a task saves a `queued` task file
- worker picks queued tasks and marks them `running`
- successful task ends as `completed`
- partially failed batch render ends as `completed_with_errors`
- startup recovery marks stale `running` tasks as `failed`

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest test/test_comic_tasks.py -q
```

Expected: FAIL because there is no comic task queue or worker yet.

**Step 3: Write minimal implementation**

Implement:

- `ComicTaskService` for create/list/update/retry
- `ComicWorker` that scans task files on an interval
- startup recovery for stale `running` tasks
- worker lifecycle start/stop from FastAPI lifespan in `services/api.py`

Use explicit task statuses:

- `queued`
- `running`
- `completed`
- `completed_with_errors`
- `failed`

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest test/test_comic_tasks.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add services/comic/tasks.py services/comic/worker.py services/api.py test/test_comic_tasks.py
git commit -m "feat: add comic task worker"
```

### Task 4: Expose FastAPI comic routes and static asset serving

**Files:**
- Create: `services/api_comic.py`
- Modify: `services/api.py`
- Test: `test/test_comic_api.py`

**Step 1: Write the failing test**

Cover these cases:

- project CRUD works through `/api/comic/projects`
- import endpoint creates a task instead of blocking until completion
- chapter script generation endpoint returns `task_id`
- scene render endpoint returns `task_id`
- task list endpoint returns progress and error fields
- rendered comic assets can be accessed from a mounted static directory

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest test/test_comic_api.py -q
```

Expected: FAIL because comic routes are not registered.

**Step 3: Write minimal implementation**

Implement route registration in `services/api_comic.py` and wire it into `create_app()` in `services/api.py`.

Use API groups:

- `/api/comic/projects`
- `/api/comic/projects/{project_id}/characters`
- `/api/comic/projects/{project_id}/chapters`
- `/api/comic/projects/{project_id}/scenes`
- `/api/comic/tasks`

Mount comic asset output directory similarly to `/generated-images`, but keep it isolated from existing single-image outputs.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest test/test_comic_api.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add services/api_comic.py services/api.py test/test_comic_api.py
git commit -m "feat: add comic api routes"
```

### Task 5: Add studio navigation and route-isolated comic entry

**Files:**
- Create: `web/src/components/studio-nav.tsx`
- Create: `web/src/app/comic/page.tsx`
- Modify: `web/src/app/layout.tsx`
- Modify: `web/src/app/page.tsx`
- Test: `web` studio build

**Step 1: Write the failing test**

Because this frontend currently relies on build verification rather than component tests, define the first failure as:

- `npm run build:studio` fails because `/comic` route and `StudioNav` do not exist

**Step 2: Run build to verify it fails**

Run:

```bash
cd web && npm run build:studio
```

Expected: FAIL once route references are added but components are still missing.

**Step 3: Write minimal implementation**

Implement:

- `StudioNav` visible only in `studio` variant
- nav entries:
  - `/` for existing public image page
  - `/comic` for new comic workspace
- `web/src/app/comic/page.tsx` as a thin wrapper around a future comic client component

Do not merge comic behavior into `PublicImagePageClient`.

**Step 4: Run build to verify it passes**

Run:

```bash
cd web && npm run build:studio
```

Expected: PASS

**Step 5: Commit**

```bash
git add web/src/components/studio-nav.tsx web/src/app/comic/page.tsx web/src/app/layout.tsx web/src/app/page.tsx
git commit -m "feat: add studio comic navigation shell"
```

### Task 6: Add frontend comic API client and page state hooks

**Files:**
- Create: `web/src/lib/comic-api.ts`
- Create: `web/src/features/comic/types.ts`
- Create: `web/src/features/comic/use-comic-projects.ts`
- Create: `web/src/features/comic/use-comic-tasks.ts`
- Test: `web` studio build

**Step 1: Write the failing test**

Again use build verification as the initial failure:

- imports from `@/lib/comic-api` and `@/features/comic/*` fail because the files do not exist

**Step 2: Run build to verify it fails**

Run:

```bash
cd web && npm run build:studio
```

Expected: FAIL with missing module errors.

**Step 3: Write minimal implementation**

Implement:

- typed request helpers for project/character/chapter/scene/task endpoints
- shared frontend types matching backend payloads
- hooks for:
  - project list refresh
  - task polling every 2-3 seconds
  - task-triggering actions that immediately return `task_id`

Keep polling logic isolated from UI components.

**Step 4: Run build to verify it passes**

Run:

```bash
cd web && npm run build:studio
```

Expected: PASS

**Step 5: Commit**

```bash
git add web/src/lib/comic-api.ts web/src/features/comic/types.ts web/src/features/comic/use-comic-projects.ts web/src/features/comic/use-comic-tasks.ts
git commit -m "feat: add comic frontend client and polling hooks"
```

### Task 7: Build the comic workspace UI

**Files:**
- Create: `web/src/features/comic/comic-page-client.tsx`
- Create: `web/src/features/comic/components/comic-project-list.tsx`
- Create: `web/src/features/comic/components/comic-project-form.tsx`
- Create: `web/src/features/comic/components/comic-character-panel.tsx`
- Create: `web/src/features/comic/components/comic-chapter-panel.tsx`
- Create: `web/src/features/comic/components/comic-scene-board.tsx`
- Create: `web/src/features/comic/components/comic-task-panel.tsx`
- Modify: `web/src/app/comic/page.tsx`
- Test: `web` studio build

**Step 1: Write the failing test**

Define the failure as the workspace route rendering an empty or broken page because the comic client and panels do not exist yet.

**Step 2: Run build to verify it fails**

Run:

```bash
cd web && npm run build:studio
```

Expected: FAIL due to missing workspace components.

**Step 3: Write minimal implementation**

Build the MVP UI in this order:

- project list and project create dialog
- import entry supporting:
  - full text paste
  - chapter text paste
  - file upload placeholder wired to backend import endpoint
- character card editor
- chapter list with “generate script” action
- scene board with:
  - inline edit
  - single render
  - batch render
- task panel showing current progress and failures

Do not add automatic page composition or advanced version history in this phase.

**Step 4: Run build to verify it passes**

Run:

```bash
cd web && npm run build:studio
```

Expected: PASS

**Step 5: Commit**

```bash
git add web/src/app/comic/page.tsx web/src/features/comic/comic-page-client.tsx web/src/features/comic/components
git commit -m "feat: add comic workspace ui"
```

### Task 8: Run focused verification before broader rollout

**Files:**
- Test: `test/test_comic_store.py`
- Test: `test/test_comic_workflow.py`
- Test: `test/test_comic_tasks.py`
- Test: `test/test_comic_api.py`
- Test: `web` studio build output

**Step 1: Run backend comic tests**

Run:

```bash
uv run pytest test/test_comic_store.py test/test_comic_workflow.py test/test_comic_tasks.py test/test_comic_api.py -q
```

Expected: PASS

**Step 2: Run existing public panel regression tests**

Run:

```bash
uv run pytest test/test_public_panel_api.py test/test_public_panel_service.py test/test_image_workflow_service.py -q
```

Expected: PASS

**Step 3: Run frontend studio build**

Run:

```bash
cd web && npm run build:studio
```

Expected: PASS and exported files update under `web_dist_studio`

**Step 4: Manual smoke verification**

Run the app locally and verify:

- `/` still opens the existing public image studio
- `/comic` opens the comic workspace
- project creation works
- chapter split task runs
- scene script task runs
- batch render task persists progress across page refresh

**Step 5: Commit**

```bash
git add services web test
git commit -m "feat: integrate comic workspace into public studio"
```

Plan complete and saved to `docs/plans/2026-04-23-chatgpt2api-l-comic-integration.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
