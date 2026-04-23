"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ComicProjectCreateInput } from "@/features/comic/types";

type ComicProjectFormProps = {
  initialValues?: ComicProjectCreateInput;
  submitLabel: string;
  onSubmit: (payload: ComicProjectCreateInput) => Promise<void>;
};

export function ComicProjectForm({
  initialValues,
  submitLabel,
  onSubmit,
}: ComicProjectFormProps) {
  const [title, setTitle] = useState(initialValues?.title ?? "");
  const [sourceText, setSourceText] = useState(initialValues?.source_text ?? "");
  const [stylePrompt, setStylePrompt] = useState(initialValues?.style_prompt ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setTitle(initialValues?.title ?? "");
    setSourceText(initialValues?.source_text ?? "");
    setStylePrompt(initialValues?.style_prompt ?? "");
  }, [initialValues]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim()) {
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit({
        title: title.trim(),
        source_text: sourceText.trim(),
        style_prompt: stylePrompt.trim(),
      });
      if (!initialValues) {
        setTitle("");
        setSourceText("");
        setStylePrompt("");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">项目标题</label>
        <Input
          placeholder="例如：银河列车"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">全局画风提示</label>
        <Input
          placeholder="例如：冷色调赛博都市漫画，电影镜头感"
          value={stylePrompt}
          onChange={(event) => setStylePrompt(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">源文片段</label>
        <Textarea
          placeholder="可以先粘贴项目摘要，后续在工作台继续补全文本。"
          value={sourceText}
          onChange={(event) => setSourceText(event.target.value)}
        />
      </div>
      <Button className="w-full rounded-2xl" disabled={isSubmitting || !title.trim()} type="submit">
        {isSubmitting ? "提交中..." : submitLabel}
      </Button>
    </form>
  );
}
