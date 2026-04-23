"use client";

import { startTransition, useEffect, useEffectEvent, useState } from "react";

import {
  createComicProject,
  deleteComicProject,
  fetchComicProject,
  fetchComicProjects,
  importComicProject,
  saveComicChapter,
  saveComicCharacters,
  saveComicScene,
  updateComicProject,
} from "@/lib/comic-api";
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
  ComicTaskTriggerResponse,
} from "@/features/comic/types";

function sortProjects(items: ComicProjectSummary[]) {
  return [...items].sort((left, right) => right.updated_at.localeCompare(left.updated_at));
}

function upsertProject(items: ComicProjectSummary[], nextProject: ComicProjectSummary) {
  return sortProjects([nextProject, ...items.filter((item) => item.id !== nextProject.id)]);
}

export function useComicProjects() {
  const [projects, setProjects] = useState<ComicProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<ComicProjectSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProjectLoading, setIsProjectLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshProjects = useEffectEvent(async () => {
    try {
      const nextProjects = await fetchComicProjects();
      startTransition(() => {
        setProjects(sortProjects(nextProjects));
        setSelectedProjectId((current) => current ?? nextProjects[0]?.id ?? null);
      });
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "读取漫画项目失败");
    } finally {
      setIsLoading(false);
    }
  });

  const loadProject = useEffectEvent(async (projectId: string) => {
    setIsProjectLoading(true);
    try {
      const snapshot = await fetchComicProject(projectId);
      startTransition(() => {
        setSelectedProjectId(projectId);
        setSelectedProject(snapshot);
      });
      setError(null);
      return snapshot;
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "读取漫画项目详情失败");
      throw nextError;
    } finally {
      setIsProjectLoading(false);
    }
  });

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!selectedProjectId) {
      setSelectedProject(null);
      return;
    }
    void loadProject(selectedProjectId);
  }, [loadProject, selectedProjectId]);

  const createProject = async (payload: ComicProjectCreateInput) => {
    const project = await createComicProject(payload);
    startTransition(() => {
      setProjects((current) => upsertProject(current, project));
      setSelectedProjectId(project.id);
    });
    return project;
  };

  const updateProject = async (projectId: string, payload: ComicProjectUpdateInput) => {
    const project = await updateComicProject(projectId, payload);
    startTransition(() => {
      setProjects((current) => upsertProject(current, project));
    });
    if (selectedProjectId === projectId) {
      await loadProject(projectId);
    }
    return project;
  };

  const removeProject = async (projectId: string) => {
    await deleteComicProject(projectId);
    startTransition(() => {
      setProjects((current) => current.filter((item) => item.id !== projectId));
      setSelectedProjectId((current) => (current === projectId ? null : current));
      setSelectedProject((current) => (current?.project.id === projectId ? null : current));
    });
  };

  const importSource = async (projectId: string, payload: ComicImportInput): Promise<ComicTaskTriggerResponse> => {
    const response = await importComicProject(projectId, payload);
    await Promise.all([refreshProjects(), loadProject(projectId)]);
    return response;
  };

  const persistCharacters = async (projectId: string, payload: ComicCharactersSaveInput): Promise<ComicCharacterProfile[]> => {
    const characters = await saveComicCharacters(projectId, payload);
    await loadProject(projectId);
    return characters;
  };

  const persistChapter = async (
    projectId: string,
    chapterId: string,
    payload: ComicChapterSaveInput,
  ): Promise<ComicChapter> => {
    const chapter = await saveComicChapter(projectId, chapterId, payload);
    await loadProject(projectId);
    return chapter;
  };

  const persistScene = async (
    projectId: string,
    sceneId: string,
    payload: ComicSceneSaveInput,
  ): Promise<ComicScene> => {
    const scene = await saveComicScene(projectId, sceneId, payload);
    await loadProject(projectId);
    return scene;
  };

  return {
    projects,
    selectedProjectId,
    selectedProject,
    isLoading,
    isProjectLoading,
    error,
    setSelectedProjectId,
    refreshProjects,
    loadProject,
    createProject,
    updateProject,
    removeProject,
    importSource,
    persistCharacters,
    persistChapter,
    persistScene,
  };
}
