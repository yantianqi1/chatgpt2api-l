"use client";

import { LoaderCircle, Sparkles } from "lucide-react";

import { formatPlatformTitle } from "@/app/image/lib/image-studio";
import type { ImageModel } from "@/lib/api";

type ImageStudioHeaderProps = {
  model: ImageModel;
  availableQuota: string;
  hasAnyGenerating: boolean;
  generatingCount: number;
  title?: string;
  description?: string;
  statusHint?: string | null;
  compact?: boolean;
};

export function ImageStudioHeader({
  model,
  availableQuota,
  hasAnyGenerating,
  generatingCount,
  title,
  description,
  statusHint,
  compact = false,
}: ImageStudioHeaderProps) {
  const widthClass = compact ? "max-w-[1080px]" : "max-w-[1380px]";
  const shellClass = compact
    ? "rounded-[24px] border border-stone-200/70 bg-white/92 shadow-[0_18px_54px_-36px_rgba(33,25,10,0.22)]"
    : "rounded-[28px] border border-stone-200/80 bg-white/90 shadow-[0_22px_70px_-42px_rgba(33,25,10,0.32)]";
  const innerClass = compact
    ? "flex flex-col gap-3 px-5 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between"
    : "flex flex-col gap-5 px-5 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between";
  const badgeClass = compact
    ? "inline-flex items-center gap-2 rounded-full bg-stone-100 px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] text-stone-500 uppercase"
    : "inline-flex items-center gap-2 rounded-full bg-stone-100 px-3 py-1 text-[11px] font-semibold tracking-[0.16em] text-stone-500 uppercase";
  const titleClass = compact ? "text-xl font-semibold tracking-tight text-stone-950" : "text-2xl font-semibold tracking-tight text-stone-950";
  const quotaClass = compact
    ? "rounded-full border border-emerald-200/80 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-800"
    : "rounded-2xl border border-emerald-200/80 bg-emerald-50 px-4 py-2 text-sm text-emerald-800";
  const descClass = compact ? "max-w-2xl text-[13px] leading-5 text-stone-500" : "text-sm leading-6 text-stone-500";
  const sideClass = compact ? "flex flex-wrap items-center gap-2" : "flex flex-wrap items-center gap-3";
  const statusClass = compact
    ? "rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700"
    : "rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700";
  const runningClass = compact
    ? "flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700"
    : "flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-700";
  const idleClass = compact
    ? "rounded-full border border-stone-200 bg-stone-50 px-3 py-1.5 text-xs text-stone-500"
    : "rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-500";

  return (
    <section className={`mx-auto w-full px-3 ${widthClass}`}>
      <div className={`overflow-hidden ${shellClass}`}>
        <div className={innerClass}>
          <div className={compact ? "space-y-1.5" : "space-y-2"}>
            <div className={badgeClass}>
              <Sparkles className="size-3.5" />
              Image Studio
            </div>
            <div className={compact ? "flex flex-wrap items-center gap-2.5" : "flex flex-wrap items-center gap-3"}>
              <h1 className={titleClass}>{title || formatPlatformTitle(model)}</h1>
              <div className={quotaClass}>
                <div className="text-[11px] font-semibold tracking-[0.14em] uppercase text-emerald-600">剩余额度</div>
                <div className={compact ? "mt-0.5 text-base font-semibold leading-none" : "mt-1 text-lg font-semibold leading-none"}>
                  {availableQuota}
                </div>
              </div>
            </div>
            <p className={descClass}>
              {description || "不上传图片时自动走文生图，上传图片后自动切到编辑图。"}
            </p>
          </div>

          <div className={sideClass}>
            {statusHint ? (
              <div className={statusClass}>
                {statusHint}
              </div>
            ) : null}
            {hasAnyGenerating ? (
              <div className={runningClass}>
                <LoaderCircle className="size-4 animate-spin" />
                当前有 {generatingCount} 个任务正在生成
              </div>
            ) : (
              <div className={idleClass}>
                当前没有进行中的生成任务
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
