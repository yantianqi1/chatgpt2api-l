"use client";

import { CheckCircle2, Copy, Gift, LoaderCircle, ReceiptText, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { AdminActivationCode, AdminActivationCodeStatus } from "@/lib/api";

const STATUS_OPTIONS = [
  { label: "全部状态", value: "all" },
  { label: "未兑换", value: "unused" },
  { label: "已兑换", value: "redeemed" },
] as const;

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getCodeStatusVariant(status: AdminActivationCodeStatus) {
  return status === "redeemed" ? "secondary" : "success";
}

function getCodeStatusLabel(status: AdminActivationCodeStatus) {
  return status === "redeemed" ? "已兑换" : "未兑换";
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-stone-700">{label}</label>
      {children}
    </div>
  );
}

export function GeneratorSection({
  count,
  amount,
  batchNote,
  generatedCodes,
  isCreating,
  onCountChange,
  onAmountChange,
  onBatchNoteChange,
  onCreate,
  onCopy,
}: {
  count: string;
  amount: string;
  batchNote: string;
  generatedCodes: AdminActivationCode[];
  isCreating: boolean;
  onCountChange: (value: string) => void;
  onAmountChange: (value: string) => void;
  onBatchNoteChange: (value: string) => void;
  onCreate: () => void;
  onCopy: () => void;
}) {
  return (
    <Card className="border-white/80 bg-white/72">
      <CardContent className="p-6">
        <div className="flex items-center gap-3">
          <div className="inline-flex size-11 items-center justify-center rounded-2xl bg-stone-950 text-white">
            <Gift className="size-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-950">激活码批量生成</h2>
            <p className="mt-1 text-sm text-stone-500">设定数量、面额和批次备注，生成后可直接复制发放。</p>
          </div>
        </div>
        <div className="mt-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="生成数量"><Input value={count} onChange={(event) => onCountChange(event.target.value)} inputMode="numeric" /></Field>
            <Field label="单张额度（元）"><Input value={amount} onChange={(event) => onAmountChange(event.target.value)} inputMode="decimal" /></Field>
          </div>
          <Field label="批次备注">
            <Input value={batchNote} onChange={(event) => onBatchNoteChange(event.target.value)} placeholder="例如 五一活动 / 渠道合作 / 私域发放" />
          </Field>
          <Button className="h-11 w-full rounded-2xl bg-stone-950 text-white hover:bg-stone-800" onClick={onCreate} disabled={isCreating}>
            {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <ReceiptText className="size-4" />}
            生成激活码
          </Button>
        </div>
        <div className="mt-6 rounded-[24px] border border-stone-200/80 bg-stone-50/80 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-stone-900">本次生成结果</div>
              <div className="mt-1 text-xs text-stone-500">{generatedCodes.length > 0 ? `最近生成 ${generatedCodes.length} 个，面额 ${generatedCodes[0]?.amount ?? "—"} 元` : "生成后会在这里展示，可直接复制"}</div>
            </div>
            <Button variant="outline" className="rounded-2xl" onClick={onCopy}>
              <Copy className="size-4" />
              复制
            </Button>
          </div>
          <div className="mt-4 space-y-2">
            {generatedCodes.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-stone-200 bg-white/80 px-4 py-5 text-sm text-stone-400">暂无生成记录</div>
            ) : (
              generatedCodes.slice(0, 6).map((item) => (
                <div key={item.id} className="rounded-2xl border border-white/80 bg-white/85 px-4 py-3">
                  <div className="font-mono text-sm text-stone-900">{item.code}</div>
                  <div className="mt-1 text-xs text-stone-500">{item.amount} 元 · {item.batch_note || "未填写批次备注"}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function ActivationCodeTable({
  items,
  statusFilter,
  batchNoteFilter,
  redeemedUsernameFilter,
  isListLoading,
  redeemedCount,
  onStatusChange,
  onBatchNoteChange,
  onRedeemedUsernameChange,
  onApplyFilters,
  onResetFilters,
}: {
  items: AdminActivationCode[];
  statusFilter: "all" | AdminActivationCodeStatus;
  batchNoteFilter: string;
  redeemedUsernameFilter: string;
  isListLoading: boolean;
  redeemedCount: number;
  onStatusChange: (value: "all" | AdminActivationCodeStatus) => void;
  onBatchNoteChange: (value: string) => void;
  onRedeemedUsernameChange: (value: string) => void;
  onApplyFilters: () => void;
  onResetFilters: () => void;
}) {
  return (
    <Card className="border-white/80 bg-white/72">
      <CardContent className="p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-stone-950">激活码列表</h2>
            <p className="mt-1 text-sm text-stone-500">按状态、批次备注、兑换用户名筛选。已兑换记录显示兑换用户 ID 与时间。</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-stone-500">
            <CheckCircle2 className="size-4 text-emerald-600" />
            已兑换 {redeemedCount}
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-[180px_1fr_1fr_auto_auto]">
          <Select value={statusFilter} onValueChange={(value) => onStatusChange(value as "all" | AdminActivationCodeStatus)}>
            <SelectTrigger className="bg-white"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input value={batchNoteFilter} onChange={(event) => onBatchNoteChange(event.target.value)} placeholder="批次备注" />
          <Input value={redeemedUsernameFilter} onChange={(event) => onRedeemedUsernameChange(event.target.value)} placeholder="兑换用户名" />
          <Button className="rounded-2xl bg-stone-950 text-white hover:bg-stone-800" onClick={onApplyFilters}>
            {isListLoading ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            筛选
          </Button>
          <Button variant="outline" className="rounded-2xl" onClick={onResetFilters}>重置</Button>
        </div>
        <div className="mt-5 overflow-hidden rounded-[28px] border border-stone-200/80 bg-white/85">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-stone-50/90 text-stone-500">
                <tr>
                  <th className="px-4 py-3 font-medium">激活码</th>
                  <th className="px-4 py-3 font-medium">额度</th>
                  <th className="px-4 py-3 font-medium">批次</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">创建时间</th>
                  <th className="px-4 py-3 font-medium">兑换信息</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-12 text-center text-stone-400">当前筛选条件下没有激活码</td></tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id} className="border-t border-stone-100 text-stone-700">
                      <td className="px-4 py-3 font-mono text-[13px] text-stone-900">{item.code}</td>
                      <td className="px-4 py-3">{item.amount}</td>
                      <td className="px-4 py-3">{item.batch_note || "—"}</td>
                      <td className="px-4 py-3"><Badge variant={getCodeStatusVariant(item.status)}>{getCodeStatusLabel(item.status)}</Badge></td>
                      <td className="px-4 py-3">{formatDateTime(item.created_at)}</td>
                      <td className="px-4 py-3 text-xs leading-6 text-stone-500">{item.redeemed_by_user_id ? `用户 ID ${item.redeemed_by_user_id}` : "未兑换"}<br />{formatDateTime(item.redeemed_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
