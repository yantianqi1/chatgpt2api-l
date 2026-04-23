"use client";

import { startTransition, useEffect, useEffectEvent, useState } from "react";

import {
  fetchComicTasks,
  queueChapterBatchRender,
  queueChapterScript,
  queueSceneRender,
  retryComicTask,
} from "@/lib/comic-api";
import type { ComicTask, ComicTaskTriggerResponse } from "@/features/comic/types";

const DEFAULT_POLL_INTERVAL_MS = 2500;

export function useComicTasks(projectId?: string | null, pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS) {
  const [tasks, setTasks] = useState<ComicTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshTasks = useEffectEvent(async () => {
    try {
      const nextTasks = await fetchComicTasks(projectId ?? undefined);
      startTransition(() => {
        setTasks(nextTasks);
      });
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "读取漫画任务失败");
    } finally {
      setIsLoading(false);
    }
  });

  useEffect(() => {
    void refreshTasks();
  }, [refreshTasks]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshTasks();
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs, refreshTasks]);

  const triggerAndRefresh = async (action: () => Promise<ComicTaskTriggerResponse>) => {
    const result = await action();
    await refreshTasks();
    return result;
  };

  const triggerChapterScript = async (nextProjectId: string, chapterId: string) => {
    return triggerAndRefresh(() => queueChapterScript(nextProjectId, chapterId));
  };

  const triggerSceneRender = async (nextProjectId: string, sceneId: string) => {
    return triggerAndRefresh(() => queueSceneRender(nextProjectId, sceneId));
  };

  const triggerBatchRender = async (nextProjectId: string, chapterId: string) => {
    return triggerAndRefresh(() => queueChapterBatchRender(nextProjectId, chapterId));
  };

  const retryTask = async (taskId: string) => {
    return triggerAndRefresh(() => retryComicTask(taskId));
  };

  return {
    tasks,
    isLoading,
    error,
    refreshTasks,
    triggerChapterScript,
    triggerSceneRender,
    triggerBatchRender,
    retryTask,
  };
}
