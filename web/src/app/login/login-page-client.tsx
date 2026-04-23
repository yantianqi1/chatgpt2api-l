"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, LoaderCircle, LockKeyhole } from "lucide-react";
import { toast } from "sonner";

import { PublicAuthPanel } from "@/app/login/components/public-auth-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { login } from "@/lib/api";
import { isStudioVariant } from "@/lib/app-variant";
import { fetchPublicMe, logoutPublicUser } from "@/lib/public-auth-api";
import { setStoredAuthKey } from "@/store/auth";

export default function LoginPage() {
  const router = useRouter();
  const [authKey, setAuthKey] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCheckingSession, setIsCheckingSession] = useState(isStudioVariant());
  const [initialMode, setInitialMode] = useState<"login" | "register">("login");

  useEffect(() => {
    if (!isStudioVariant()) {
      return;
    }

    let cancelled = false;
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("mode") === "register") {
      setInitialMode("register");
    }
    void fetchPublicMe()
      .then(() => {
        if (!cancelled) {
          router.replace("/");
        }
      })
      .catch(async (error) => {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : "读取登录状态失败";
        if (message === "login required") {
          await logoutPublicUser().catch(() => undefined);
        } else {
          toast.error(message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsCheckingSession(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleLogin = async () => {
    const normalizedAuthKey = authKey.trim();
    if (!normalizedAuthKey) {
      toast.error("请输入 密钥");
      return;
    }

    setIsSubmitting(true);
    try {
      await login(normalizedAuthKey);
      await setStoredAuthKey(normalizedAuthKey);
      router.replace("/accounts");
    } catch (error) {
      const message = error instanceof Error ? error.message : "登录失败";
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isStudioVariant()) {
    return (
      <div className="min-h-[calc(100vh-1rem)] px-4 py-6">
        <div className="mx-auto grid max-w-[1220px] gap-6 lg:grid-cols-[minmax(0,1fr)_540px]">
          <section className="overflow-hidden rounded-[34px] border border-white/75 bg-[linear-gradient(135deg,rgba(255,255,255,0.72),rgba(244,237,228,0.95)_55%,rgba(240,232,220,0.92))] p-7 shadow-[0_28px_90px_rgba(28,25,23,0.08)] sm:p-9">
            <div className="flex h-full flex-col justify-between gap-8">
              <div className="space-y-5">
                <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/85 bg-white/75 px-4 py-1.5 text-[11px] font-medium tracking-[0.24em] text-stone-700 uppercase">
                  Public Studio
                </div>
                <div className="space-y-4">
                  <h1
                    className="max-w-2xl text-4xl font-semibold tracking-tight text-stone-950 md:text-5xl"
                    style={{ fontFamily: '"Palatino Linotype","Book Antiqua","URW Palladio L","Times New Roman",serif' }}
                  >
                    把一次公开试用，变成可持续的个人创作入口。
                  </h1>
                  <p className="max-w-2xl text-[15px] leading-7 text-stone-600">
                    登录后，你的生图会直接使用个人余额；激活码兑换成功会立即补入账户。匿名访客仍然可以直接创作，但会员账号让额度、权益和续费关系更清晰。
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-[26px] border border-white/80 bg-white/72 p-5">
                  <div className="text-2xl font-semibold text-stone-950">1.00</div>
                  <div className="mt-2 text-sm font-medium text-stone-800">注册即得初始余额</div>
                  <p className="mt-1 text-xs leading-5 text-stone-500">新用户创建后即可进入公开工作室，无需再向管理员申请密钥。</p>
                </div>
                <div className="rounded-[26px] border border-white/80 bg-white/72 p-5">
                  <div className="text-2xl font-semibold text-stone-950">Code</div>
                  <div className="mt-2 text-sm font-medium text-stone-800">激活码可直接充值</div>
                  <p className="mt-1 text-xs leading-5 text-stone-500">适合会员卡、赠送额度、分发私域权益，兑换后即时刷新面板状态。</p>
                </div>
                <div className="rounded-[26px] border border-white/80 bg-white/72 p-5">
                  <div className="text-2xl font-semibold text-stone-950">Anon</div>
                  <div className="mt-2 text-sm font-medium text-stone-800">匿名也能先体验</div>
                  <p className="mt-1 text-xs leading-5 text-stone-500">先看画面，再决定是否登录，不把公开入口做成后台式密钥验证页。</p>
                </div>
              </div>
            </div>
          </section>

          {isCheckingSession ? (
            <Card className="min-h-[620px] items-center justify-center border-white/85 bg-white/92">
              <CardContent className="flex items-center gap-3 p-8 text-sm text-stone-500">
                <LoaderCircle className="size-4 animate-spin" />
                正在检查登录状态
              </CardContent>
            </Card>
          ) : (
            <PublicAuthPanel initialMode={initialMode} onSuccess={() => router.replace("/")} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-[calc(100vh-1rem)] w-full place-items-center px-4 py-6">
      <Card className="w-full max-w-[505px] rounded-[30px] border-white/80 bg-white/95 shadow-[0_28px_90px_rgba(28,25,23,0.10)]">
        <CardContent className="space-y-7 p-6 sm:p-8">
          <div className="space-y-4 text-center">
            <div className="mx-auto inline-flex size-14 items-center justify-center rounded-[18px] bg-stone-950 text-white shadow-sm">
              <LockKeyhole className="size-5" />
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight text-stone-950">欢迎回来</h1>
              <p className="text-sm leading-6 text-stone-500">输入密钥后继续使用账号管理和图片生成功能。</p>
            </div>
          </div>

          <div className="space-y-3">
            <label htmlFor="auth-key" className="block text-sm font-medium text-stone-700">
              密钥
            </label>
            <Input
              id="auth-key"
              type="password"
              value={authKey}
              onChange={(event) => setAuthKey(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleLogin();
                }
              }}
              placeholder="请输入密钥"
              className="h-13 rounded-2xl border-stone-200 bg-white px-4"
            />
          </div>

          <Button
            className="h-13 w-full rounded-2xl bg-stone-950 text-white hover:bg-stone-800"
            onClick={() => void handleLogin()}
            disabled={isSubmitting}
          >
            {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
            登录
          </Button>

          <div className="flex items-center justify-center text-xs text-stone-400">
            管理员入口
            <ArrowRight className="size-3" />
            继续使用账号池与后台配置
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
