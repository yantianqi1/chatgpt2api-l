"use client";

import { ImagePlus, Layers3, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ComicAsset, ComicScene, ComicSceneSaveInput } from "@/features/comic/types";
import { buildComicAssetUrl } from "@/lib/comic-api";

type SceneDraft = {
  id: string;
  chapter_id: string;
  title: string;
  description: string;
  prompt: string;
  character_ids: string;
  order: number;
  assets: ComicAsset[];
};

type ComicSceneBoardProps = {
  projectId: string | null;
  scenes: ComicScene[];
  selectedChapterId: string | null;
  fallbackChapterId: string | null;
  disabled?: boolean;
  onSaveScene: (sceneId: string, payload: ComicSceneSaveInput) => Promise<void>;
  onRenderScene: (sceneId: string) => Promise<void>;
  onBatchRender: (chapterId: string) => Promise<void>;
};

function createSceneDraft(chapterId: string): SceneDraft {
  return {
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `scene-${Date.now()}`,
    chapter_id: chapterId,
    title: "",
    description: "",
    prompt: "",
    character_ids: "",
    order: 1,
    assets: [],
  };
}

export function ComicSceneBoard({
  projectId,
  scenes,
  selectedChapterId,
  fallbackChapterId,
  disabled = false,
  onSaveScene,
  onRenderScene,
  onBatchRender,
}: ComicSceneBoardProps) {
  const [drafts, setDrafts] = useState<SceneDraft[]>([]);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [renderingId, setRenderingId] = useState<string | null>(null);
  const [batchChapterId, setBatchChapterId] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(
      scenes.map((scene) => ({
        id: scene.id,
        chapter_id: scene.chapter_id,
        title: scene.title,
        description: scene.description,
        prompt: scene.prompt,
        character_ids: scene.character_ids.join(", "),
        order: scene.order,
        assets: scene.assets,
      })),
    );
  }, [scenes]);

  const visibleDrafts = drafts.filter((draft) => (selectedChapterId ? draft.chapter_id === selectedChapterId : true));

  const updateDraft = (id: string, field: keyof SceneDraft, value: string | number | ComicAsset[]) => {
    setDrafts((current) =>
      current.map((draft) => (draft.id === id ? { ...draft, [field]: value } : draft)),
    );
  };

  const handleSave = async (draft: SceneDraft) => {
    setSavingId(draft.id);
    try {
      await onSaveScene(draft.id, {
        chapter_id: draft.chapter_id,
        title: draft.title.trim(),
        description: draft.description.trim(),
        prompt: draft.prompt.trim(),
        character_ids: draft.character_ids.split(",").map((item) => item.trim()).filter(Boolean),
        order: draft.order,
        assets: draft.assets,
      });
    } finally {
      setSavingId(null);
    }
  };

  const handleRender = async (sceneId: string) => {
    setRenderingId(sceneId);
    try {
      await onRenderScene(sceneId);
    } finally {
      setRenderingId(null);
    }
  };

  const handleBatchRender = async () => {
    const chapterId = selectedChapterId || fallbackChapterId;
    if (!chapterId) {
      return;
    }
    setBatchChapterId(chapterId);
    try {
      await onBatchRender(chapterId);
    } finally {
      setBatchChapterId(null);
    }
  };

  return (
    <Card className="border-stone-200/80 bg-white/85">
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">Scenes</p>
          <CardTitle className="mt-1 text-lg">分镜画板</CardTitle>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={disabled || !(selectedChapterId || fallbackChapterId)}
            onClick={() => setDrafts((current) => [...current, createSceneDraft(selectedChapterId || fallbackChapterId || "")])}
            type="button"
            variant="outline"
          >
            <Layers3 className="size-4" />
            添加分镜
          </Button>
          <Button
            disabled={disabled || !(selectedChapterId || fallbackChapterId) || batchChapterId !== null}
            onClick={() => void handleBatchRender()}
            type="button"
          >
            <ImagePlus className="size-4" />
            {batchChapterId ? "批量任务已排队..." : "批量出图"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {visibleDrafts.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-stone-50/80 px-4 py-6 text-sm text-stone-500">
            当前章节还没有分镜。先在章节面板生成脚本，或手动补一条分镜草稿。
          </div>
        ) : null}
        {visibleDrafts.map((draft) => (
          <article key={draft.id} className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Badge variant="info">镜头 #{draft.order}</Badge>
                <span className="text-sm font-semibold tracking-tight text-stone-900">{draft.title || "未命名分镜"}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={disabled || savingId === draft.id} onClick={() => void handleSave(draft)} type="button" variant="outline">
                  <Save className="size-4" />
                  {savingId === draft.id ? "保存中..." : "保存分镜"}
                </Button>
                <Button disabled={disabled || renderingId === draft.id} onClick={() => void handleRender(draft.id)} type="button">
                  <ImagePlus className="size-4" />
                  {renderingId === draft.id ? "排队中..." : "单镜出图"}
                </Button>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr),130px]">
              <Input
                placeholder="分镜标题"
                value={draft.title}
                onChange={(event) => updateDraft(draft.id, "title", event.target.value)}
              />
              <Input
                min={1}
                type="number"
                value={String(draft.order)}
                onChange={(event) => updateDraft(draft.id, "order", Number(event.target.value) || 1)}
              />
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-[1.1fr,1.1fr,0.8fr]">
              <Textarea
                className="min-h-28"
                placeholder="分镜描述"
                value={draft.description}
                onChange={(event) => updateDraft(draft.id, "description", event.target.value)}
              />
              <Textarea
                className="min-h-28"
                placeholder="出图 prompt"
                value={draft.prompt}
                onChange={(event) => updateDraft(draft.id, "prompt", event.target.value)}
              />
              <Textarea
                className="min-h-28"
                placeholder="角色 ID，逗号分隔"
                value={draft.character_ids}
                onChange={(event) => updateDraft(draft.id, "character_ids", event.target.value)}
              />
            </div>
            {draft.assets.length > 0 && projectId ? (
              <div className="mt-4 flex flex-wrap gap-3">
                {draft.assets.map((asset) => (
                  <a
                    key={asset.id}
                    className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm"
                    href={buildComicAssetUrl(projectId, asset.relative_path)}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <img
                      alt={asset.prompt || draft.title || "comic asset"}
                      className="h-24 w-24 object-cover"
                      src={buildComicAssetUrl(projectId, asset.relative_path)}
                    />
                  </a>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </CardContent>
    </Card>
  );
}
