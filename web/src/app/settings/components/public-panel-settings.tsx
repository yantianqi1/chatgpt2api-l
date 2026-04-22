"use client";

import { useEffect, useState } from "react";
import { GalleryVerticalEnd, LoaderCircle, Plus, Save } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  addPublicPanelQuota,
  fetchPublicPanelConfig,
  updatePublicPanelConfig,
  type PublicPanelConfig,
  type PublicPanelMode,
} from "@/lib/api";

type PublicPanelDraft = {
  enabled: boolean;
  title: string;
  description: string;
  mode: PublicPanelMode;
  daily_limit: string;
  fixed_quota: string;
};

function createDraft(config: PublicPanelConfig): PublicPanelDraft {
  return {
    enabled: config.enabled,
    title: config.title,
    description: config.description,
    mode: config.mode,
    daily_limit: String(config.daily_limit),
    fixed_quota: String(config.fixed_quota),
  };
}

function getDisabledLabel(reason: PublicPanelConfig["disabled_reason"]) {
  if (reason === "disabled") {
    return "已关闭";
  }
  if (reason === "quota_exhausted") {
    return "额度耗尽";
  }
  return "运行中";
}

export function PublicPanelSettings() {
  const [config, setConfig] = useState<PublicPanelConfig | null>(null);
  const [draft, setDraft] = useState<PublicPanelDraft | null>(null);
  const [quotaIncrement, setQuotaIncrement] = useState("10");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isAddingQuota, setIsAddingQuota] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadConfig = async () => {
      setIsLoading(true);
      try {
        const nextConfig = await fetchPublicPanelConfig();
        if (cancelled) {
          return;
        }
        setConfig(nextConfig);
        setDraft(createDraft(nextConfig));
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "读取公共面板配置失败");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = async () => {
    if (!draft) {
      return;
    }
    setIsSaving(true);
    try {
      const nextConfig = await updatePublicPanelConfig({
        enabled: draft.enabled,
        title: draft.title.trim(),
        description: draft.description.trim(),
        mode: draft.mode,
        daily_limit: Math.max(0, Number(draft.daily_limit) || 0),
        fixed_quota: Math.max(0, Number(draft.fixed_quota) || 0),
      });
      setConfig(nextConfig);
      setDraft(createDraft(nextConfig));
      toast.success("公共生图面板配置已保存");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存公共面板配置失败");
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddQuota = async () => {
    const amount = Math.max(0, Number(quotaIncrement) || 0);
    if (amount <= 0) {
      toast.error("请输入大于 0 的补充额度");
      return;
    }
    setIsAddingQuota(true);
    try {
      const nextConfig = await addPublicPanelQuota(amount);
      setConfig(nextConfig);
      setDraft(createDraft(nextConfig));
      toast.success(`已补充 ${amount} 次固定额度`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "补充额度失败");
    } finally {
      setIsAddingQuota(false);
    }
  };

  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-6 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-stone-100">
              <GalleryVerticalEnd className="size-5 text-stone-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-tight">公共生图面板</h2>
              <p className="text-sm text-stone-500">独立域名匿名可用，只提供图片生成和图片编辑能力。</p>
            </div>
          </div>
          {config ? (
            <Badge variant={config.disabled_reason ? "warning" : "success"} className="rounded-md px-2.5 py-1">
              {getDisabledLabel(config.disabled_reason)}
            </Badge>
          ) : null}
        </div>

        {isLoading || !draft || !config ? (
          <div className="flex items-center justify-center py-10">
            <LoaderCircle className="size-5 animate-spin text-stone-400" />
          </div>
        ) : (
          <>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,0.8fr)]">
              <div className="space-y-4">
                <div className="flex items-center gap-3 rounded-xl bg-stone-50 px-4 py-3">
                  <Checkbox
                    checked={draft.enabled}
                    onCheckedChange={(checked) =>
                      setDraft((prev) => (prev ? { ...prev, enabled: Boolean(checked) } : prev))
                    }
                  />
                  <div>
                    <p className="text-sm font-medium text-stone-700">启用匿名公共生图面板</p>
                    <p className="text-xs text-stone-500">关闭后公开站仍可访问，但提交按钮禁用。</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-stone-700">标题</label>
                  <Input
                    value={draft.title}
                    onChange={(event) => setDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                    placeholder="例如：匿名公共生图面板"
                    className="h-11 rounded-xl border-stone-200 bg-white"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-stone-700">说明</label>
                  <Textarea
                    value={draft.description}
                    onChange={(event) =>
                      setDraft((prev) => (prev ? { ...prev, description: event.target.value } : prev))
                    }
                    placeholder="例如：无需登录，直接生成图片"
                    className="min-h-28 rounded-2xl border-stone-200"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-stone-700">额度方案</label>
                  <Select
                    value={draft.mode}
                    onValueChange={(value) => setDraft((prev) => (prev ? { ...prev, mode: value as PublicPanelMode } : prev))}
                  >
                    <SelectTrigger className="h-11 rounded-xl border-stone-200 bg-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">每日额度</SelectItem>
                      <SelectItem value="fixed">固定额度</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {draft.mode === "daily" ? (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-stone-700">每日上限</label>
                    <Input
                      type="number"
                      min="0"
                      value={draft.daily_limit}
                      onChange={(event) =>
                        setDraft((prev) => (prev ? { ...prev, daily_limit: event.target.value } : prev))
                      }
                      className="h-11 rounded-xl border-stone-200 bg-white"
                    />
                  </div>
                ) : (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-stone-700">固定额度</label>
                    <Input
                      type="number"
                      min="0"
                      value={draft.fixed_quota}
                      onChange={(event) =>
                        setDraft((prev) => (prev ? { ...prev, fixed_quota: event.target.value } : prev))
                      }
                      className="h-11 rounded-xl border-stone-200 bg-white"
                    />
                  </div>
                )}
              </div>

              <div className="space-y-4 rounded-2xl bg-stone-50 p-5">
                <div className="space-y-1">
                  <div className="text-xs font-semibold tracking-[0.18em] text-stone-400 uppercase">运行状态</div>
                  <div className="text-sm text-stone-600">可用额度 {config.available_quota}</div>
                  <div className="text-sm text-stone-600">更新时间 {config.updated_at}</div>
                </div>

                {draft.mode === "daily" ? (
                  <div className="rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-600">
                    今日已使用 {config.daily_used} / {config.daily_limit}
                  </div>
                ) : (
                  <div className="space-y-3 rounded-xl border border-stone-200 bg-white p-4">
                    <div className="text-sm text-stone-600">当前固定额度 {config.fixed_quota}</div>
                    <div className="flex gap-2">
                      <Input
                        type="number"
                        min="1"
                        value={quotaIncrement}
                        onChange={(event) => setQuotaIncrement(event.target.value)}
                        className="h-10 rounded-xl border-stone-200 bg-white"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        className="h-10 rounded-xl border-stone-200 bg-white"
                        onClick={() => void handleAddQuota()}
                        disabled={isAddingQuota}
                      >
                        {isAddingQuota ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}
                        补充
                      </Button>
                    </div>
                  </div>
                )}

                <Button
                  className="h-11 w-full rounded-xl bg-stone-950 text-white hover:bg-stone-800"
                  onClick={() => void handleSave()}
                  disabled={isSaving}
                >
                  {isSaving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
                  保存公共面板配置
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
