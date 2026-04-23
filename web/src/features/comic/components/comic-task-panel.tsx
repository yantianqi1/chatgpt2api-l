"use client";

import { RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ComicTask } from "@/features/comic/types";

type ComicTaskPanelProps = {
  tasks: ComicTask[];
  isLoading: boolean;
  onRetryTask: (taskId: string) => Promise<void>;
};

function getTaskVariant(status: ComicTask["status"]) {
  if (status === "completed") {
    return "success";
  }
  if (status === "completed_with_errors") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "running") {
    return "info";
  }
  return "outline";
}

export function ComicTaskPanel({
  tasks,
  isLoading,
  onRetryTask,
}: ComicTaskPanelProps) {
  return (
    <Card className="border-stone-200/80 bg-white/85">
      <CardHeader>
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">Tasks</p>
        <CardTitle className="mt-1 text-lg">任务面板</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-stone-50/80 px-4 py-6 text-sm text-stone-500">
            正在加载任务列表…
          </div>
        ) : null}
        {!isLoading && tasks.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-stone-50/80 px-4 py-6 text-sm text-stone-500">
            暂无后台任务。导入、生成脚本和渲染都会在这里持续更新进度。
          </div>
        ) : null}
        {tasks.map((task) => (
          <article key={task.id} className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={getTaskVariant(task.status)}>{task.status}</Badge>
                  <span className="text-sm font-semibold tracking-tight text-stone-900">{task.kind}</span>
                </div>
                <p className="text-xs text-stone-500">target: {task.target_id}</p>
              </div>
              {(task.status === "failed" || task.status === "completed_with_errors") ? (
                <Button onClick={() => void onRetryTask(task.id)} size="sm" type="button" variant="outline">
                  <RotateCcw className="size-4" />
                  重试
                </Button>
              ) : null}
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-stone-200">
              <div className="h-full rounded-full bg-stone-900 transition-all" style={{ width: `${task.progress}%` }} />
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-stone-500">
              <span>进度 {task.progress}%</span>
              <span>{new Date(task.updated_at).toLocaleString("zh-CN")}</span>
            </div>
            {task.error ? <p className="mt-3 rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{task.error}</p> : null}
          </article>
        ))}
      </CardContent>
    </Card>
  );
}
