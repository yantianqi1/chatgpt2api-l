"use client";

import { FileUp, FolderInput, Sparkles } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ComicCharacterPanel } from "@/features/comic/components/comic-character-panel";
import { ComicChapterPanel } from "@/features/comic/components/comic-chapter-panel";
import { ComicProjectList } from "@/features/comic/components/comic-project-list";
import { ComicSceneBoard } from "@/features/comic/components/comic-scene-board";
import { ComicTaskPanel } from "@/features/comic/components/comic-task-panel";
import { useComicProjects } from "@/features/comic/use-comic-projects";
import { useComicTasks } from "@/features/comic/use-comic-tasks";

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <article className="rounded-[24px] border border-stone-200 bg-white/80 p-4 shadow-[0_12px_30px_rgba(120,113,108,0.08)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">{value}</p>
      <p className="mt-2 text-sm leading-6 text-stone-500">{hint}</p>
    </article>
  );
}

export default function ComicPageClient() {
  const {
    projects,
    selectedProjectId,
    selectedProject,
    isLoading,
    isProjectLoading,
    error,
    setSelectedProjectId,
    createProject,
    updateProject,
    removeProject,
    importSource,
    persistCharacters,
    persistChapter,
    persistScene,
  } = useComicProjects();
  const deferredProject = useDeferredValue(selectedProject);
  const { tasks, isLoading: isTasksLoading, refreshTasks, triggerChapterScript, triggerSceneRender, triggerBatchRender, retryTask } = useComicTasks(selectedProjectId);
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [importMode, setImportMode] = useState("full_text");
  const [projectTitle, setProjectTitle] = useState("");
  const [stylePrompt, setStylePrompt] = useState("");
  const [importText, setImportText] = useState("");
  const [importFileName, setImportFileName] = useState("");
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  useEffect(() => {
    setProjectTitle(deferredProject?.project.title ?? "");
    setStylePrompt(deferredProject?.project.style_prompt ?? "");
    setImportText(deferredProject?.project.source_text ?? "");
    setImportFileName("");
  }, [deferredProject?.project.id, deferredProject?.project.source_text, deferredProject?.project.style_prompt, deferredProject?.project.title]);

  useEffect(() => {
    const chapters = deferredProject?.chapters ?? [];
    if (chapters.length === 0) {
      setActiveChapterId(null);
      return;
    }
    setActiveChapterId((current) => (current && chapters.some((chapter) => chapter.id === current) ? current : chapters[0].id));
  }, [deferredProject?.chapters]);

  const handleCreateProject = async (payload: { title: string; source_text: string; style_prompt: string }) => {
    await createProject(payload);
    toast.success(`已创建项目：${payload.title}`);
  };

  const handleDeleteProject = async (projectId: string) => {
    await removeProject(projectId);
    toast.success("项目目录已删除");
  };

  const handleSaveProject = async () => {
    if (!selectedProjectId) {
      return;
    }
    setIsSavingProject(true);
    try {
      await updateProject(selectedProjectId, {
        title: projectTitle,
        style_prompt: stylePrompt,
        source_text: importText,
      });
      toast.success("项目基础信息已保存");
    } finally {
      setIsSavingProject(false);
    }
  };

  const handleImport = async () => {
    if (!selectedProjectId || !importText.trim()) {
      toast.error("请先选择项目并准备导入文本");
      return;
    }
    setIsImporting(true);
    try {
      const response = await importSource(selectedProjectId, {
        source_text: importText,
        import_mode: importMode,
      });
      await refreshTasks();
      toast.success(`导入任务已创建：${response.task_id.slice(0, 8)}`);
    } finally {
      setIsImporting(false);
    }
  };

  const handleImportFile = async (file: File | null) => {
    if (!file) {
      return;
    }
    const text = await file.text();
    setImportFileName(file.name);
    setImportText(text);
    toast.success(`已读取文件：${file.name}`);
  };

  const guardProjectAction = <T,>(handler: (projectId: string) => Promise<T>) => {
    if (!selectedProjectId) {
      toast.error("请先选择一个项目");
      return Promise.resolve(null);
    }
    return handler(selectedProjectId);
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[320px,minmax(0,1fr)]">
      <aside className="space-y-5">
        <ComicProjectList
          isLoading={isLoading}
          onCreateProject={handleCreateProject}
          onDeleteProject={handleDeleteProject}
          onSelectProject={setSelectedProjectId}
          projects={projects}
          selectedProjectId={selectedProjectId}
        />
        <ComicTaskPanel
          isLoading={isTasksLoading}
          onRetryTask={async (taskId) => {
            await retryTask(taskId);
            toast.success("已重新排队任务");
          }}
          tasks={tasks}
        />
      </aside>

      <div className="space-y-5">
        <section className="grid gap-3 md:grid-cols-3">
          <MetricCard label="项目" value={String(projects.length)} hint="所有项目都持久化在 data/comic-projects 下。" />
          <MetricCard label="章节" value={String(deferredProject?.chapters.length ?? 0)} hint="章节既可手动录入，也可从源文导入后继续拆分。" />
          <MetricCard label="分镜任务" value={String(tasks.filter((task) => task.status === "queued" || task.status === "running").length)} hint="worker 已接入 FastAPI 生命周期，任务状态可跨刷新保持。" />
        </section>

        <Card className="border-stone-200/80 bg-white/85">
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">Overview</p>
              <CardTitle className="mt-1 text-xl">项目总览与导入入口</CardTitle>
            </div>
            {selectedProjectId ? <Badge variant="info">当前项目 {selectedProjectId.slice(0, 8)}</Badge> : <Badge variant="outline">未选择项目</Badge>}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <Input placeholder="项目标题" value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} />
              <Input placeholder="全局画风提示" value={stylePrompt} onChange={(event) => setStylePrompt(event.target.value)} />
            </div>
            <div className="grid gap-3 md:grid-cols-[200px,minmax(0,1fr),auto]">
              <Select value={importMode} onValueChange={setImportMode}>
                <SelectTrigger>
                  <SelectValue placeholder="导入模式" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_text">全文导入</SelectItem>
                  <SelectItem value="chapter_text">章节导入</SelectItem>
                </SelectContent>
              </Select>
              <Input readOnly value={importFileName || "可上传 txt / md / 任意纯文本文件"} />
              <label className="inline-flex">
                <input className="hidden" onChange={(event) => void handleImportFile(event.target.files?.[0] ?? null)} type="file" />
                <Button asChild type="button" variant="outline">
                  <span>
                    <FileUp className="size-4" />
                    读取文件
                  </span>
                </Button>
              </label>
            </div>
            <Textarea
              className="min-h-44"
              placeholder="在这里粘贴全文或章节文本。导入任务会后台排队，不阻塞页面。"
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
            />
            <div className="flex flex-wrap gap-3">
              <Button disabled={!selectedProjectId || isSavingProject} onClick={() => void handleSaveProject()} type="button" variant="outline">
                <FolderInput className="size-4" />
                {isSavingProject ? "保存中..." : "保存项目基础信息"}
              </Button>
              <Button disabled={!selectedProjectId || !importText.trim() || isImporting} onClick={() => void handleImport()} type="button">
                <Sparkles className="size-4" />
                {isImporting ? "创建任务中..." : "创建导入任务"}
              </Button>
            </div>
            {isProjectLoading ? <p className="text-sm text-stone-500">项目详情正在刷新…</p> : null}
            {error ? <p className="text-sm text-rose-600">错误：{error}</p> : null}
          </CardContent>
        </Card>

        <ComicCharacterPanel
          characters={deferredProject?.characters ?? []}
          disabled={!selectedProjectId}
          onSave={async (payload) => {
            await guardProjectAction(async (projectId) => {
              await persistCharacters(projectId, payload);
              toast.success("角色卡已保存");
            });
          }}
        />
        <ComicChapterPanel
          chapters={deferredProject?.chapters ?? []}
          disabled={!selectedProjectId}
          onGenerateScript={async (chapterId) => {
            await guardProjectAction(async (projectId) => {
              const response = await triggerChapterScript(projectId, chapterId);
              toast.success(`脚本任务已排队：${response.task_id.slice(0, 8)}`);
            });
          }}
          onSaveChapter={async (chapterId, payload) => {
            await guardProjectAction(async (projectId) => {
              await persistChapter(projectId, chapterId, payload);
              toast.success("章节已保存");
            });
          }}
          onSelectChapter={setActiveChapterId}
          selectedChapterId={activeChapterId}
        />
        <ComicSceneBoard
          disabled={!selectedProjectId}
          fallbackChapterId={deferredProject?.chapters[0]?.id ?? null}
          onBatchRender={async (chapterId) => {
            await guardProjectAction(async (projectId) => {
              const response = await triggerBatchRender(projectId, chapterId);
              toast.success(`批量渲染任务已排队：${response.task_id.slice(0, 8)}`);
            });
          }}
          onRenderScene={async (sceneId) => {
            await guardProjectAction(async (projectId) => {
              const response = await triggerSceneRender(projectId, sceneId);
              toast.success(`单镜渲染任务已排队：${response.task_id.slice(0, 8)}`);
            });
          }}
          onSaveScene={async (sceneId, payload) => {
            await guardProjectAction(async (projectId) => {
              await persistScene(projectId, sceneId, payload);
              toast.success("分镜草稿已保存");
            });
          }}
          projectId={selectedProjectId}
          scenes={deferredProject?.scenes ?? []}
          selectedChapterId={activeChapterId}
        />
      </div>
    </div>
  );
}
