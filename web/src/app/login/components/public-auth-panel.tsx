"use client";

import { LoaderCircle, Sparkles, Ticket, Wallet } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  loginPublicUser,
  registerPublicUser,
  type PublicUser,
} from "@/lib/public-auth-api";
import { cn } from "@/lib/utils";

type AuthMode = "login" | "register";

type PublicAuthPanelProps = {
  initialMode?: AuthMode;
  onSuccess?: (user: PublicUser) => Promise<void> | void;
};

const modeCopy: Record<AuthMode, { title: string; subtitle: string; action: string }> = {
  login: {
    title: "继续你的创作会话",
    subtitle: "登录后可查看个人余额、兑换激活码，并让每次生成都直接从个人额度扣减。",
    action: "登录并进入工作室",
  },
  register: {
    title: "创建你的公开工作室账号",
    subtitle: "只需要用户名和密码。注册后立即获得初始余额，后续可用激活码补充创作额度。",
    action: "注册并进入工作室",
  },
};

export function PublicAuthPanel({ initialMode = "login", onSuccess }: PublicAuthPanelProps) {
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    const normalizedUsername = username.trim();
    const normalizedPassword = password.trim();
    if (!normalizedUsername) {
      toast.error("请输入用户名");
      return;
    }
    if (!normalizedPassword) {
      toast.error("请输入密码");
      return;
    }

    setIsSubmitting(true);
    try {
      const response =
        mode === "login"
          ? await loginPublicUser(normalizedUsername, normalizedPassword)
          : await registerPublicUser(normalizedUsername, normalizedPassword);
      toast.success(mode === "login" ? "已登录" : "注册成功");
      await onSuccess?.(response.user);
    } catch (error) {
      const message = error instanceof Error ? error.message : mode === "login" ? "登录失败" : "注册失败";
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const copy = modeCopy[mode];

  return (
    <Card className="overflow-hidden border-white/85 bg-[linear-gradient(180deg,rgba(255,255,255,0.97),rgba(249,245,238,0.96))] shadow-[0_32px_100px_rgba(28,25,23,0.12)]">
      <CardContent className="space-y-6 p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3">
            <Badge variant="secondary" className="rounded-full bg-stone-900 px-3 py-1 text-[11px] tracking-[0.24em] text-white uppercase">
              Studio Access
            </Badge>
            <div className="space-y-2">
              <h2 className="text-3xl font-semibold tracking-tight text-stone-950">{copy.title}</h2>
              <p className="max-w-lg text-sm leading-6 text-stone-500">{copy.subtitle}</p>
            </div>
          </div>
          <div className="hidden rounded-[22px] border border-stone-200/80 bg-white/80 p-3 text-stone-900 shadow-sm sm:block">
            <Sparkles className="size-5" />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {(["login", "register"] as AuthMode[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              className={cn(
                "rounded-[22px] border px-4 py-3 text-left transition",
                mode === value
                  ? "border-stone-900 bg-stone-900 text-white shadow-sm"
                  : "border-stone-200 bg-white/75 text-stone-600 hover:border-stone-300 hover:bg-white",
              )}
            >
              <div className="text-sm font-medium">{value === "login" ? "已有账号" : "新用户注册"}</div>
              <div className={cn("mt-1 text-xs leading-5", mode === value ? "text-stone-300" : "text-stone-500")}>
                {value === "login" ? "回到个人创作空间" : "领取初始余额并激活作品额度"}
              </div>
            </button>
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-[24px] border border-white/80 bg-white/70 p-4">
            <Wallet className="size-4 text-stone-900" />
            <div className="mt-3 text-sm font-medium text-stone-900">个人余额</div>
            <p className="mt-1 text-xs leading-5 text-stone-500">登录后优先使用你的个人额度，不受公开池剩余额度影响。</p>
          </div>
          <div className="rounded-[24px] border border-white/80 bg-white/70 p-4">
            <Ticket className="size-4 text-stone-900" />
            <div className="mt-3 text-sm font-medium text-stone-900">激活码兑换</div>
            <p className="mt-1 text-xs leading-5 text-stone-500">兑换成功后立即刷新余额，适合发放会员权益或创作点数。</p>
          </div>
          <div className="rounded-[24px] border border-white/80 bg-white/70 p-4">
            <Sparkles className="size-4 text-stone-900" />
            <div className="mt-3 text-sm font-medium text-stone-900">匿名仍可试用</div>
            <p className="mt-1 text-xs leading-5 text-stone-500">不登录也能先体验公开生图，账号体系主要用于沉淀余额和兑换权益。</p>
          </div>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <label htmlFor="public-username" className="block text-sm font-medium text-stone-700">
              用户名
            </label>
            <Input
              id="public-username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleSubmit();
                }
              }}
              placeholder="例如：atelier-neo"
              className="h-12 border-stone-200/90 bg-white"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="public-password" className="block text-sm font-medium text-stone-700">
              密码
            </label>
            <Input
              id="public-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleSubmit();
                }
              }}
              placeholder="请输入密码"
              className="h-12 border-stone-200/90 bg-white"
            />
          </div>
        </div>

        <Button
          className="h-12 w-full rounded-2xl bg-stone-950 text-white hover:bg-stone-800"
          onClick={() => void handleSubmit()}
          disabled={isSubmitting}
        >
          {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
          {copy.action}
        </Button>
      </CardContent>
    </Card>
  );
}
