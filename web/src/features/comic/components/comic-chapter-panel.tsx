"use client";

import { FileStack, Plus, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ComicChapter, ComicChapterSaveInput } from "@/features/comic/types";
import { cn } from "@/lib/utils";

type ChapterDraft = ComicChapterSaveInput & { id: string };

type ComicChapterPanelProps = {
  chapters: ComicChapter[];
  selectedChapterId: string | null;
  disabled?: boolean;
  onSelectChapter: (chapterId: string) => void;
  onSaveChapter: (chapterId: string, payload: ComicChapterSaveInput) => Promise<void>;
  onGenerateScript: (chapterId: string) => Promise<void>;
};

function createChapterDraft(): ChapterDraft {
  return {
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `chapter-${Date.now()}`,
    title: "",
    source_text: "",
    summary: "",
    order: 1,
  };
}

export function ComicChapterPanel({
  chapters,
  selectedChapterId,
  disabled = false,
  onSelectChapter,
  onSaveChapter,
  onGenerateScript,
}: ComicChapterPanelProps) {
  const [drafts, setDrafts] = useState<ChapterDraft[]>([]);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(
      chapters.map((chapter) => ({
        id: chapter.id,
        title: chapter.title,
        source_text: chapter.source_text,
        summary: chapter.summary,
        order: chapter.order,
      })),
    );
  }, [chapters]);

  const updateDraft = (id: string, field: keyof ChapterDraft, value: string | number) => {
    setDrafts((current) =>
      current.map((draft) => (draft.id === id ? { ...draft, [field]: value } : draft)),
    );
  };

  const handleSave = async (draft: ChapterDraft) => {
    setSavingId(draft.id);
    try {
      await onSaveChapter(draft.id, {
        title: draft.title.trim(),
        source_text: draft.source_text.trim(),
        summary: draft.summary.trim(),
        order: draft.order,
      });
    } finally {
      setSavingId(null);
    }
  };

  const handleGenerate = async (chapterId: string) => {
    setGeneratingId(chapterId);
    try {
      await onGenerateScript(chapterId);
    } finally {
      setGeneratingId(null);
    }
  };

  return (
    <Card className="border-stone-200/80 bg-white/85">
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">Chapters</p>
          <CardTitle className="mt-1 text-lg">章节工作台</CardTitle>
        </div>
        <Button disabled={disabled} onClick={() => setDrafts((current) => [...current, createChapterDraft()])} type="button" variant="outline">
          <Plus className="size-4" />
          添加章节
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {drafts.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-stone-50/80 px-4 py-6 text-sm text-stone-500">
            还没有章节。可以先手动录入章节，再触发“生成分镜脚本”。
          </div>
        ) : null}
        {drafts.map((draft) => {
          const active = draft.id === selectedChapterId;
          return (
            <article
              key={draft.id}
              className={cn(
                "rounded-[24px] border p-4 transition",
                active ? "border-stone-900 bg-stone-950 text-white" : "border-stone-200 bg-stone-50/80",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Badge variant={active ? "warning" : "outline"}>章节 #{draft.order}</Badge>
                  <button className="text-left" onClick={() => onSelectChapter(draft.id)} type="button">
                    <span className={cn("text-sm font-semibold tracking-tight", active ? "text-white" : "text-stone-900")}>
                      {draft.title || "未命名章节"}
                    </span>
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    className={active ? "border-white/15 bg-white/10 text-white hover:bg-white/15" : ""}
                    disabled={disabled || savingId === draft.id}
                    onClick={() => void handleSave(draft)}
                    type="button"
                    variant={active ? "secondary" : "outline"}
                  >
                    <Save className="size-4" />
                    {savingId === draft.id ? "保存中..." : "保存章节"}
                  </Button>
                  <Button
                    disabled={disabled || generatingId === draft.id}
                    onClick={() => void handleGenerate(draft.id)}
                    type="button"
                  >
                    <FileStack className="size-4" />
                    {generatingId === draft.id ? "排队中..." : "生成分镜脚本"}
                  </Button>
                </div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-[1.2fr,140px]">
                <Input
                  className={active ? "border-white/15 bg-white/10 text-white placeholder:text-stone-400" : ""}
                  placeholder="章节标题"
                  value={draft.title}
                  onChange={(event) => updateDraft(draft.id, "title", event.target.value)}
                />
                <Input
                  className={active ? "border-white/15 bg-white/10 text-white placeholder:text-stone-400" : ""}
                  min={1}
                  placeholder="顺序"
                  type="number"
                  value={String(draft.order)}
                  onChange={(event) => updateDraft(draft.id, "order", Number(event.target.value) || 1)}
                />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <Textarea
                  className={cn("min-h-28", active ? "border-white/15 bg-white/10 text-white placeholder:text-stone-400" : "")}
                  placeholder="章节原文"
                  value={draft.source_text}
                  onChange={(event) => updateDraft(draft.id, "source_text", event.target.value)}
                />
                <Textarea
                  className={cn("min-h-28", active ? "border-white/15 bg-white/10 text-white placeholder:text-stone-400" : "")}
                  placeholder="章节摘要"
                  value={draft.summary}
                  onChange={(event) => updateDraft(draft.id, "summary", event.target.value)}
                />
              </div>
            </article>
          );
        })}
      </CardContent>
    </Card>
  );
}
