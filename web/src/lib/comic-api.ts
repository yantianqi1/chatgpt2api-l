import { httpRequest } from "@/lib/request";
import type {
  ComicChapter,
  ComicChapterSaveInput,
  ComicCharacterProfile,
  ComicCharactersSaveInput,
  ComicImportInput,
  ComicProjectCreateInput,
  ComicProjectSnapshot,
  ComicProjectSummary,
  ComicProjectUpdateInput,
  ComicScene,
  ComicSceneSaveInput,
  ComicTask,
  ComicTaskTriggerResponse,
} from "@/features/comic/types";

const publicComicRequest = {
  redirectOnUnauthorized: false,
  skipAuth: true,
} as const;

export function buildComicAssetUrl(projectId: string, relativePath: string) {
  const normalizedPath = String(relativePath || "").replace(/^\/+/, "");
  return `/comic-assets/${projectId}/${normalizedPath}`;
}

export async function fetchComicProjects() {
  return httpRequest<ComicProjectSummary[]>("/api/comic/projects", publicComicRequest);
}

export async function createComicProject(payload: ComicProjectCreateInput) {
  return httpRequest<ComicProjectSummary>("/api/comic/projects", {
    method: "POST",
    body: payload,
    ...publicComicRequest,
  });
}

export async function fetchComicProject(projectId: string) {
  return httpRequest<ComicProjectSnapshot>(`/api/comic/projects/${projectId}`, publicComicRequest);
}

export async function updateComicProject(projectId: string, payload: ComicProjectUpdateInput) {
  return httpRequest<ComicProjectSummary>(`/api/comic/projects/${projectId}`, {
    method: "PATCH",
    body: payload,
    ...publicComicRequest,
  });
}

export async function deleteComicProject(projectId: string) {
  return httpRequest<void>(`/api/comic/projects/${projectId}`, {
    method: "DELETE",
    ...publicComicRequest,
  });
}

export async function importComicProject(projectId: string, payload: ComicImportInput) {
  return httpRequest<ComicTaskTriggerResponse>(`/api/comic/projects/${projectId}/import`, {
    method: "POST",
    body: payload,
    ...publicComicRequest,
  });
}

export async function fetchComicCharacters(projectId: string) {
  return httpRequest<ComicCharacterProfile[]>(`/api/comic/projects/${projectId}/characters`, publicComicRequest);
}

export async function saveComicCharacters(projectId: string, payload: ComicCharactersSaveInput) {
  return httpRequest<ComicCharacterProfile[]>(`/api/comic/projects/${projectId}/characters`, {
    method: "POST",
    body: payload,
    ...publicComicRequest,
  });
}

export async function fetchComicChapters(projectId: string) {
  return httpRequest<ComicChapter[]>(`/api/comic/projects/${projectId}/chapters`, publicComicRequest);
}

export async function saveComicChapter(projectId: string, chapterId: string, payload: ComicChapterSaveInput) {
  return httpRequest<ComicChapter>(`/api/comic/projects/${projectId}/chapters/${chapterId}`, {
    method: "PATCH",
    body: payload,
    ...publicComicRequest,
  });
}

export async function queueChapterScript(projectId: string, chapterId: string) {
  return httpRequest<ComicTaskTriggerResponse>(`/api/comic/projects/${projectId}/chapters/${chapterId}/generate-script`, {
    method: "POST",
    ...publicComicRequest,
  });
}

export async function queueChapterBatchRender(projectId: string, chapterId: string) {
  return httpRequest<ComicTaskTriggerResponse>(`/api/comic/projects/${projectId}/chapters/${chapterId}/render-batch`, {
    method: "POST",
    ...publicComicRequest,
  });
}

export async function fetchComicScenes(projectId: string, chapterId?: string) {
  const query = chapterId ? `?chapter_id=${encodeURIComponent(chapterId)}` : "";
  return httpRequest<ComicScene[]>(`/api/comic/projects/${projectId}/scenes${query}`, publicComicRequest);
}

export async function saveComicScene(projectId: string, sceneId: string, payload: ComicSceneSaveInput) {
  return httpRequest<ComicScene>(`/api/comic/projects/${projectId}/scenes/${sceneId}`, {
    method: "PATCH",
    body: payload,
    ...publicComicRequest,
  });
}

export async function queueSceneRender(projectId: string, sceneId: string) {
  return httpRequest<ComicTaskTriggerResponse>(`/api/comic/projects/${projectId}/scenes/${sceneId}/render`, {
    method: "POST",
    ...publicComicRequest,
  });
}

export async function fetchComicTasks(projectId?: string) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return httpRequest<ComicTask[]>(`/api/comic/tasks${query}`, publicComicRequest);
}

export async function retryComicTask(taskId: string) {
  return httpRequest<ComicTaskTriggerResponse>(`/api/comic/tasks/${taskId}/retry`, {
    method: "POST",
    ...publicComicRequest,
  });
}
