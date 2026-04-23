"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ComicCharacterProfile, ComicCharactersSaveInput } from "@/features/comic/types";

type CharacterDraft = ComicCharactersSaveInput["characters"][number];

type ComicCharacterPanelProps = {
  characters: ComicCharacterProfile[];
  disabled?: boolean;
  onSave: (payload: ComicCharactersSaveInput) => Promise<void>;
};

function createCharacterDraft(): CharacterDraft {
  return {
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `char-${Date.now()}`,
    name: "",
    description: "",
    appearance: "",
    personality: "",
  };
}

export function ComicCharacterPanel({
  characters,
  disabled = false,
  onSave,
}: ComicCharacterPanelProps) {
  const [drafts, setDrafts] = useState<CharacterDraft[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setDrafts(
      characters.map((character) => ({
        id: character.id,
        name: character.name,
        description: character.description,
        appearance: character.appearance,
        personality: character.personality,
      })),
    );
  }, [characters]);

  const updateDraft = (id: string, field: keyof CharacterDraft, value: string) => {
    setDrafts((current) =>
      current.map((draft) => (draft.id === id ? { ...draft, [field]: value } : draft)),
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave({
        characters: drafts.filter((draft) => draft.name.trim() || draft.description?.trim() || draft.appearance?.trim()),
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="border-stone-200/80 bg-white/85">
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-400">Characters</p>
          <CardTitle className="mt-1 text-lg">角色卡编辑</CardTitle>
        </div>
        <div className="flex gap-2">
          <Button disabled={disabled} onClick={() => setDrafts((current) => [...current, createCharacterDraft()])} type="button" variant="outline">
            <Plus className="size-4" />
            添加角色
          </Button>
          <Button disabled={disabled || isSaving} onClick={() => void handleSave()} type="button">
            <Save className="size-4" />
            {isSaving ? "保存中..." : "保存角色"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {drafts.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-stone-200 bg-stone-50/80 px-4 py-6 text-sm text-stone-500">
            暂无角色。先补主角和关键配角，后面的分镜 prompt 会按角色 appearance 拼接。
          </div>
        ) : null}
        {drafts.map((draft) => (
          <article key={draft.id} className="rounded-[24px] border border-stone-200 bg-stone-50/80 p-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr),minmax(0,1fr),auto]">
              <Input
                placeholder="角色名"
                value={draft.name}
                onChange={(event) => updateDraft(draft.id, "name", event.target.value)}
              />
              <Input
                placeholder="外观关键词"
                value={draft.appearance || ""}
                onChange={(event) => updateDraft(draft.id, "appearance", event.target.value)}
              />
              <Button
                onClick={() => setDrafts((current) => current.filter((item) => item.id !== draft.id))}
                size="icon"
                type="button"
                variant="outline"
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Textarea
                className="min-h-24"
                placeholder="角色描述"
                value={draft.description || ""}
                onChange={(event) => updateDraft(draft.id, "description", event.target.value)}
              />
              <Textarea
                className="min-h-24"
                placeholder="性格和语言风格"
                value={draft.personality || ""}
                onChange={(event) => updateDraft(draft.id, "personality", event.target.value)}
              />
            </div>
          </article>
        ))}
      </CardContent>
    </Card>
  );
}
