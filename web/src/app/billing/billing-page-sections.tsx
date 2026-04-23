"use client";

import { BadgeDollarSign, LoaderCircle, Save, Sparkles, Ticket } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { AdminModelPricing } from "@/lib/api";

export function BillingHero({
  pricingCount,
  enabledModels,
  unusedCodes,
}: {
  pricingCount: number;
  enabledModels: number;
  unusedCodes: number;
}) {
  return (
    <Card className="overflow-hidden border-white/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.88),rgba(250,247,242,0.9))]">
      <CardContent className="grid gap-5 p-7 lg:grid-cols-[1.35fr_0.9fr]">
        <div>
          <Badge variant="secondary" className="rounded-full bg-stone-900 px-3 py-1 text-[11px] tracking-[0.22em] text-white uppercase">Billing Ops</Badge>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-stone-950">商业化配置</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">统一维护模型定价和激活码发行。上半区处理价格与发码，下半区追踪批次和兑换状态，适合运营日常直接维护。</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
          <SummaryTile icon={<BadgeDollarSign className="size-5 text-stone-900" />} label="已配置模型" value={pricingCount} />
          <SummaryTile icon={<Sparkles className="size-5 text-emerald-600" />} label="当前启用" value={enabledModels} />
          <SummaryTile icon={<Ticket className="size-5 text-amber-600" />} label="待兑换激活码" value={unusedCodes} />
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-[26px] border border-white/80 bg-white/72 p-4">
      {icon}
      <div className="mt-5 text-2xl font-semibold text-stone-950">{value}</div>
      <div className="mt-1 text-sm text-stone-600">{label}</div>
    </div>
  );
}

export function PricingSection({
  items,
  drafts,
  savingModel,
  onPriceChange,
  onEnabledChange,
  onSave,
}: {
  items: AdminModelPricing[];
  drafts: Record<string, { price: string; enabled: boolean }>;
  savingModel: string | null;
  onPriceChange: (model: string, value: string) => void;
  onEnabledChange: (model: string, checked: boolean) => void;
  onSave: (model: string) => void;
}) {
  const enabledCount = items.filter((item) => item.enabled === "1").length;
  return (
    <Card className="border-white/80 bg-white/72">
      <CardContent className="p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-stone-950">模型价格区</h2>
            <p className="mt-1 text-sm text-stone-500">每张卡片独立保存，适合逐个模型快速调价与启停。</p>
          </div>
          <Badge variant="outline" className="rounded-full border-stone-200 px-3 py-1 text-stone-600">{enabledCount}/{items.length} 已启用</Badge>
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {items.map((item) => (
            <PricingCard
              key={item.model}
              item={item}
              draft={drafts[item.model] ?? { price: item.price, enabled: item.enabled === "1" }}
              saving={savingModel === item.model}
              onPriceChange={(value) => onPriceChange(item.model, value)}
              onEnabledChange={(checked) => onEnabledChange(item.model, checked)}
              onSave={() => onSave(item.model)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function PricingCard({
  item,
  draft,
  saving,
  onPriceChange,
  onEnabledChange,
  onSave,
}: {
  item: AdminModelPricing;
  draft: { price: string; enabled: boolean };
  saving: boolean;
  onPriceChange: (value: string) => void;
  onEnabledChange: (checked: boolean) => void;
  onSave: () => void;
}) {
  return (
    <div className="rounded-[28px] border border-white/80 bg-white/80 p-5 shadow-[0_16px_40px_-28px_rgba(28,25,23,0.35)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-stone-950">{item.model}</div>
          <div className="mt-1 text-xs text-stone-500">单次调用价格，运营端可直接调整对外结算策略。</div>
        </div>
        <Badge variant={draft.enabled ? "success" : "secondary"}>{draft.enabled ? "已启用" : "已停用"}</Badge>
      </div>
      <div className="mt-5 space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-stone-700">价格（元）</label>
          <Input value={draft.price} onChange={(event) => onPriceChange(event.target.value)} placeholder="例如 1.00" />
        </div>
        <label className="flex items-center gap-3 rounded-2xl border border-stone-200/80 bg-stone-50/80 px-4 py-3">
          <Checkbox checked={draft.enabled} onCheckedChange={(checked) => onEnabledChange(checked === true)} />
          <span className="text-sm text-stone-700">允许前台用户消耗余额调用这个模型</span>
        </label>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <span className="text-xs text-stone-400">当前配置 {item.price} / {item.enabled === "1" ? "启用" : "停用"}</span>
        <Button className="rounded-2xl bg-stone-950 text-white hover:bg-stone-800" onClick={onSave} disabled={saving}>
          {saving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
          保存
        </Button>
      </div>
    </div>
  );
}
