"use client";

import { LoaderCircle, Save, SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ImageModel } from "@/lib/api";

export type ImageRuntimeSettingsDraft = {
  defaultModel: ImageModel;
  maxCountPerRequest: string;
  autoRetryTimes: string;
  requestTimeoutSeconds: string;
};

type ImageRuntimeSettingsCardProps = {
  draft: ImageRuntimeSettingsDraft;
  isLoading: boolean;
  isSaving: boolean;
  onDraftChange: (updates: Partial<ImageRuntimeSettingsDraft>) => void;
  onSave: () => void | Promise<void>;
};

export function ImageRuntimeSettingsCard({
  draft,
  isLoading,
  isSaving,
  onDraftChange,
  onSave,
}: ImageRuntimeSettingsCardProps) {
  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-6 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-stone-100">
              <SlidersHorizontal className="size-5 text-stone-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-tight">图片生成设置</h2>
              <p className="text-sm text-stone-500">管理默认模型、单次最多产图张数、失败自动重试次数和接口等待超时。</p>
            </div>
          </div>

          <Button
            className="h-9 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
            onClick={() => void onSave()}
            disabled={isLoading || isSaving}
          >
            {isSaving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
            保存设置
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <LoaderCircle className="size-5 animate-spin text-stone-400" />
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-700">默认模型</label>
              <Select
                value={draft.defaultModel}
                onValueChange={(value) => onDraftChange({ defaultModel: value as ImageModel })}
              >
                <SelectTrigger className="h-11 rounded-xl border-stone-200 bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt-image-1">gpt-image-1</SelectItem>
                  <SelectItem value="gpt-image-2">gpt-image-2</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-700">单次最多生成张数</label>
              <Input
                type="number"
                min="1"
                max="10"
                step="1"
                value={draft.maxCountPerRequest}
                onChange={(event) => onDraftChange({ maxCountPerRequest: event.target.value })}
                className="h-11 rounded-xl border-stone-200 bg-white"
              />
              <p className="text-xs leading-5 text-stone-400">图像页张数输入框会按这里的上限进行约束。</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-700">失败自动重试次数</label>
              <Input
                type="number"
                min="0"
                max="3"
                step="1"
                value={draft.autoRetryTimes}
                onChange={(event) => onDraftChange({ autoRetryTimes: event.target.value })}
                className="h-11 rounded-xl border-stone-200 bg-white"
              />
              <p className="text-xs leading-5 text-stone-400">前端单张失败后会按此次数自动重试，再展示真实报错。</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-700">请求超时秒数</label>
              <Input
                type="number"
                min="0"
                max="600"
                step="1"
                value={draft.requestTimeoutSeconds}
                onChange={(event) => onDraftChange({ requestTimeoutSeconds: event.target.value })}
                className="h-11 rounded-xl border-stone-200 bg-white"
              />
              <p className="text-xs leading-5 text-stone-400">后端会在外层代理超时前主动返回错误，填 0 表示关闭该超时。</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
