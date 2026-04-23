"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ComicProjectForm } from "@/features/comic/components/comic-project-form";
import type { ComicProjectCreateInput, ComicProjectSummary } from "@/features/comic/types";
import { cn } from "@/lib/utils";

type ComicProjectListProps = {
  projects: ComicProjectSummary[];
  selectedProjectId: string | null;
  isLoading: boolean;
  onSelectProject: (projectId: string) => void;
  onCreateProject: (payload: ComicProjectCreateInput) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
};

function formatProjectTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间未知";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function ComicProjectList({
  projects,
  selectedProjectId,
  isLoading,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
}: ComicProjectListProps) {
  const [open, setOpen] = useState(false);

  const handleCreate = async (payload: ComicProjectCreateInput) => {
    await onCreateProject(payload);
    setOpen(false);
  };

  const handleDelete = async (projectId: string) => {
    if (!window.confirm("删除项目会清空项目目录和任务文件，确认继续？")) {
      return;
    }
    await onDeleteProject(projectId);
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">Projects</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-stone-950">漫创项目</h2>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-2xl">
              <Plus className="size-4" />
              新建项目
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建漫画项目</DialogTitle>
              <DialogDescription>先落标题、画风和源文片段，后续在工作台继续补完。</DialogDescription>
            </DialogHeader>
            <ComicProjectForm submitLabel="创建项目" onSubmit={handleCreate} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-white/70 px-4 py-6 text-sm text-stone-500">
            正在加载项目列表…
          </div>
        ) : null}
        {!isLoading && projects.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-white/70 px-4 py-6 text-sm leading-6 text-stone-500">
            还没有漫画项目。先创建一个项目，再导入全文或章节文本。
          </div>
        ) : null}
        {projects.map((project) => {
          const active = project.id === selectedProjectId;
          return (
            <article
              key={project.id}
              className={cn(
                "rounded-[24px] border px-4 py-4 transition",
                active
                  ? "border-stone-900 bg-stone-950 text-stone-50 shadow-[0_18px_45px_rgba(28,25,23,0.18)]"
                  : "border-stone-200 bg-white/80 text-stone-800 hover:border-stone-300",
              )}
            >
              <button className="w-full text-left" onClick={() => onSelectProject(project.id)} type="button">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <h3 className="text-base font-semibold tracking-tight">{project.title || "未命名项目"}</h3>
                    <p className={cn("line-clamp-2 text-sm leading-6", active ? "text-stone-300" : "text-stone-500")}>
                      {project.style_prompt || "尚未设置全局画风提示。"}
                    </p>
                    <p className={cn("text-xs", active ? "text-stone-400" : "text-stone-400")}>
                      更新于 {formatProjectTime(project.updated_at)}
                    </p>
                  </div>
                  <Button
                    className={cn(active ? "border-white/15 bg-white/10 text-white hover:bg-white/15" : "")}
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDelete(project.id);
                    }}
                    size="icon"
                    type="button"
                    variant={active ? "secondary" : "outline"}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
