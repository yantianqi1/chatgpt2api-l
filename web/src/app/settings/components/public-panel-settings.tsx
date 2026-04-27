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

function formatQuotaValue(value: number) {
  return String(Math.max(0, Math.floor(value)));
}

function parseQuotaValue(value: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return Math.max(0, Math.floor(parsed));
}

function createDraft(config: PublicPanelConfig): PublicPanelDraft {
  return {
    enabled: config.enabled,
    title: config.title,
    description: config.description,
    mode: config.mode,
    daily_limit: formatQuotaValue(config.daily_limit),
    fixed_quota: formatQuotaValue(config.fixed_quota),
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
        daily_limit: parseQuotaValue(draft.daily_limit),
        fixed_quota: parseQuotaValue(draft.fixed_quota),
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
    const amount = parseQuotaValue(quotaIncrement);
    if (amount <= 0) {
      toast.error("请输入大于 0 的额度点数");
      return;
    }
    setIsAddingQuota(true);
    try {
      const nextConfig = await addPublicPanelQuota(amount);
      setConfig(nextConfig);
      setDraft(createDraft(nextConfig));
      toast.success(`已补充 ${amount} 点额度`);
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
              <p className="text-sm text-stone-500">独立域名匿名可用，只提供图片生成和图片编辑能力，匿名额度每张图片扣 1 点。</p>
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
                    onCheckedChange={(checked) => setDraft((prev) => (prev ? { ...prev, enabled: Boolean(checked) } : prev))}
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
                    onChange={(event) => setDraft((prev) => (prev ? { ...prev, description: event.target.value } : prev))}
                    placeholder="例如：无需登录，直接生成图片"
                    className="min-h-28 rounded-2xl border-stone-200"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-stone-700">匿名额度方案</label>
                  <Select
                    value={draft.mode}
                    onValueChange={(value) =>
                      setDraft((prev) => (prev ? { ...prev, mode: value as PublicPanelMode } : prev))
                    }
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
                    <label className="text-sm font-medium text-stone-700">每日额度点数</label>
                    <Input
                      type="number"
                      min="0"
                      step="1"
                      value={draft.daily_limit}
                      onChange={(event) =>
                        setDraft((prev) => (prev ? { ...prev, daily_limit: event.target.value } : prev))
                      }
                      className="h-11 rounded-xl border-stone-200 bg-white"
                    />
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-stone-700">当前固定额度点数</label>
                      <Input
                        type="number"
                        min="0"
                        step="1"
                        value={draft.fixed_quota}
                        onChange={(event) =>
                          setDraft((prev) => (prev ? { ...prev, fixed_quota: event.target.value } : prev))
                        }
                        className="h-11 rounded-xl border-stone-200 bg-white"
                      />
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Input
                        type="number"
                        min="1"
                        step="1"
                        value={quotaIncrement}
                        onChange={(event) => setQuotaIncrement(event.target.value)}
                        className="h-11 rounded-xl border-stone-200 bg-white"
                      />
                      <Button
                        variant="outline"
                        className="h-11 rounded-xl border-stone-200 bg-white px-4 text-stone-700"
                        onClick={() => void handleAddQuota()}
                        disabled={isAddingQuota}
                      >
                        {isAddingQuota ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}
                        补充点数
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-3 rounded-2xl bg-stone-50 p-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-white px-4 py-3">
                    <div className="text-xs tracking-[0.16em] text-stone-400 uppercase">可用额度点数</div>
                    <div className="mt-2 text-2xl font-semibold text-stone-900">{formatQuotaValue(config.available_quota)}</div>
                  </div>
                  <div className="rounded-xl bg-white px-4 py-3">
                    <div className="text-xs tracking-[0.16em] text-stone-400 uppercase">当前模式</div>
                    <div className="mt-2 text-2xl font-semibold text-stone-900">{config.mode === "daily" ? "每日" : "固定"}</div>
                  </div>
                </div>

                {config.mode === "daily" ? (
                  <div className="rounded-xl bg-white px-4 py-3 text-sm text-stone-600">
                    <div>今日已用：{formatQuotaValue(config.daily_used)}</div>
                    <div>今日上限：{formatQuotaValue(config.daily_limit)}</div>
                    <div>下次重置：北京时间次日 00:00</div>
                  </div>
                ) : (
                  <div className="rounded-xl bg-white px-4 py-3 text-sm text-stone-600">
                    <div>当前固定额度：{formatQuotaValue(config.fixed_quota)}</div>
                    <div>可通过“直接修改点数”或“补充点数”调整。</div>
                  </div>
                )}

                <div className="rounded-xl bg-white px-4 py-3 text-sm text-stone-600">
                  {config.disabled_reason === "disabled" ? "当前公开站已关闭。用户仍能打开页面，但不能提交图片请求。" : null}
                  {config.disabled_reason === "quota_exhausted" ? "当前公开站额度已耗尽。用户仍能打开页面，但不能继续提交。" : null}
                  {config.disabled_reason === null ? "当前公开站可匿名使用。图片生成和编辑每张图片扣 1 点公共额度。" : null}
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
                onClick={() => void handleSave()}
                disabled={isSaving}
              >
                {isSaving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
                保存公共面板配置
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
