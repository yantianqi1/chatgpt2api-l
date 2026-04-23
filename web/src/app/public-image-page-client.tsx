"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LoaderCircle, LogOut, Sparkles, Ticket, UserRound } from "lucide-react";
import { toast } from "sonner";

import { ImageComposer } from "@/app/image/components/image-composer";
import { ImageResults } from "@/app/image/components/image-results";
import { ImageSidebar } from "@/app/image/components/image-sidebar";
import { ImageLightbox } from "@/components/image-lightbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ImageModel, PublicPanelConfig } from "@/lib/api";
import {
  fetchPublicMe,
  logoutPublicUser,
  redeemActivationCode,
  type PublicUser,
} from "@/lib/public-auth-api";
import { editPublicImage, fetchPublicPanelStatus, generatePublicImage } from "@/lib/public-panel-api";
import {
  clearImageConversations,
  deleteImageConversation,
  listImageConversations,
  saveImageConversation,
  type ImageConversation,
  type ImageConversationMode,
  type StoredImage,
  type StoredReferenceImage,
} from "@/store/image-conversations";

const imageModelOptions: Array<{ label: string; value: ImageModel }> = [
  { label: "gpt-image-1", value: "gpt-image-1" },
  { label: "gpt-image-2", value: "gpt-image-2" },
];

function buildConversationTitle(prompt: string) {
  const trimmed = prompt.trim();
  return trimmed.length <= 5 ? trimmed : `${trimmed.slice(0, 5)}...`;
}

function formatConversationTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

async function normalizeConversationHistory(items: ImageConversation[]) {
  const normalized = items.map((item) =>
    item.status === "generating"
      ? {
          ...item,
          status: "error" as const,
          error: item.images.some((image) => image.status === "success") ? item.error || "生成已中断" : "页面已刷新，生成已中断",
          images: item.images.map((image) =>
            image.status === "loading" ? { ...image, status: "error" as const, error: "页面已刷新，生成已中断" } : image,
          ),
        }
      : item,
  );
  await Promise.all(normalized.filter((item, index) => item !== items[index]).map((item) => saveImageConversation(item)));
  return normalized;
}

function createId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("读取参考图失败"));
    reader.readAsDataURL(file);
  });
}

function getAnonymousStatusHint(status: PublicPanelConfig | null, statusError: string | null) {
  if (statusError) {
    return statusError;
  }
  if (!status) {
    return null;
  }
  if (status.disabled_reason === "disabled") {
    return "公开面板已关闭";
  }
  if (status.disabled_reason === "quota_exhausted") {
    return "公开额度已用尽";
  }
  return null;
}

async function resolvePublicUser(setter: (value: PublicUser | null) => void) {
  try {
    const response = await fetchPublicMe();
    setter(response.user);
    return response.user;
  } catch (error) {
    const message = error instanceof Error ? error.message : "读取登录状态失败";
    if (message === "login required") {
      await logoutPublicUser().catch(() => undefined);
      setter(null);
      return null;
    }
    throw error;
  }
}

export default function PublicImagePageClient() {
  const resultsViewportRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [imagePrompt, setImagePrompt] = useState("");
  const [imageCount, setImageCount] = useState("1");
  const [imageMode, setImageMode] = useState<ImageConversationMode>("generate");
  const [imageModel, setImageModel] = useState<ImageModel>("gpt-image-1");
  const [referenceImageFiles, setReferenceImageFiles] = useState<File[]>([]);
  const [referenceImages, setReferenceImages] = useState<StoredReferenceImage[]>([]);
  const [conversations, setConversations] = useState<ImageConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(new Set());
  const [panelStatus, setPanelStatus] = useState<PublicPanelConfig | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [publicUser, setPublicUser] = useState<PublicUser | null>(null);
  const [isLoadingPublicUser, setIsLoadingPublicUser] = useState(true);
  const [redeemCode, setRedeemCode] = useState("");
  const [isRedeeming, setIsRedeeming] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  );
  const parsedCount = useMemo(() => Math.max(1, Math.min(10, Number(imageCount) || 1)), [imageCount]);
  const isSelectedGenerating = selectedConversationId !== null && generatingIds.has(selectedConversationId);
  const lightboxImages = useMemo(
    () =>
      (selectedConversation?.images ?? [])
        .filter((img): img is StoredImage & { b64_json: string } => img.status === "success" && !!img.b64_json)
        .map((img) => ({ id: img.id, src: `data:image/png;base64,${img.b64_json}` })),
    [selectedConversation],
  );
  const composerQuotaLabel = publicUser ? publicUser.balance : panelStatus ? String(panelStatus.available_quota) : statusError ? "—" : "加载中";
  const composerStatusHint = publicUser ? null : getAnonymousStatusHint(panelStatus, statusError);

  const loadStatus = useCallback(async () => {
    try {
      const nextStatus = await fetchPublicPanelStatus();
      setPanelStatus(nextStatus);
      setStatusError(null);
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "读取公共面板状态失败");
    }
  }, []);

  const loadPublicUser = useCallback(async (options?: { silent?: boolean }) => {
    try {
      return await resolvePublicUser(setPublicUser);
    } catch (error) {
      setPublicUser(null);
      if (!options?.silent) {
        toast.error(error instanceof Error ? error.message : "读取登录状态失败");
      }
      return null;
    } finally {
      setIsLoadingPublicUser(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void listImageConversations()
      .then(normalizeConversationHistory)
      .then((items) => {
        if (!cancelled) {
          setConversations(items);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "读取会话记录失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingHistory(false);
        }
      });
    void loadStatus();
    void loadPublicUser({ silent: true });
    const handleFocus = () => {
      void loadStatus();
      void loadPublicUser({ silent: true });
    };
    window.addEventListener("focus", handleFocus);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", handleFocus);
    };
  }, [loadPublicUser, loadStatus]);

  useEffect(() => {
    if (selectedConversation || isSelectedGenerating) {
      resultsViewportRef.current?.scrollTo({ top: resultsViewportRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [selectedConversation, isSelectedGenerating]);

  const openLightbox = useCallback((imageId: string) => {
    const nextIndex = lightboxImages.findIndex((img) => img.id === imageId);
    if (nextIndex >= 0) {
      setLightboxIndex(nextIndex);
      setLightboxOpen(true);
    }
  }, [lightboxImages]);

  const persistConversation = async (conversation: ImageConversation) => {
    setConversations((prev) => [conversation, ...prev.filter((item) => item.id !== conversation.id)].sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
    await saveImageConversation(conversation);
  };

  const updateConversation = async (conversationId: string, updater: (current: ImageConversation | null) => ImageConversation) => {
    let nextConversation: ImageConversation | null = null;
    setConversations((prev) => {
      const current = prev.find((item) => item.id === conversationId) ?? null;
      nextConversation = updater(current);
      return [nextConversation, ...prev.filter((item) => item.id !== conversationId)].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    });
    if (nextConversation) {
      await saveImageConversation(nextConversation);
    }
  };

  const resetComposer = () => {
    setImagePrompt("");
    setImageCount("1");
    setReferenceImageFiles([]);
    setReferenceImages([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const appendReferenceImages = useCallback(async (files: File[]) => {
    if (files.length === 0) {
      return;
    }
    const previews = await Promise.all(files.map(async (file) => ({ name: file.name, type: file.type || "image/png", dataUrl: await readFileAsDataUrl(file) })));
    setReferenceImageFiles((prev) => [...prev, ...files]);
    setReferenceImages((prev) => [...prev, ...previews]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const handleGenerateImage = async () => {
    const blockedReason = composerStatusHint;
    if (blockedReason) {
      toast.error(blockedReason);
      return;
    }
    const prompt = imagePrompt.trim();
    if (!prompt) {
      toast.error("请输入提示词");
      return;
    }
    if (imageMode === "edit" && referenceImageFiles.length === 0) {
      toast.error("请先上传参考图");
      return;
    }

    const conversationId = createId();
    const draftConversation: ImageConversation = {
      id: conversationId,
      title: buildConversationTitle(prompt),
      prompt,
      model: imageModel,
      mode: imageMode,
      referenceImages: imageMode === "edit" ? referenceImages : [],
      count: parsedCount,
      images: Array.from({ length: parsedCount }, (_, index) => ({ id: `${conversationId}-${index}`, status: "loading" })),
      createdAt: new Date().toISOString(),
      status: "generating",
    };

    setGeneratingIds((prev) => new Set(prev).add(conversationId));
    setSelectedConversationId(conversationId);
    resetComposer();

    try {
      await persistConversation(draftConversation);
      const tasks = Array.from({ length: parsedCount }, async (_, index) => {
        const data = imageMode === "edit" && referenceImageFiles.length > 0
          ? await editPublicImage(referenceImageFiles, prompt, imageModel)
          : await generatePublicImage(prompt, imageModel);
        const first = data.data?.[0];
        if (!first?.b64_json) {
          throw new Error(`第 ${index + 1} 张没有返回图片数据`);
        }
        const nextImage: StoredImage = { id: `${conversationId}-${index}`, status: "success", b64_json: first.b64_json };
        await updateConversation(conversationId, (current) => ({
          ...(current ?? draftConversation),
          images: (current?.images ?? draftConversation.images).map((image) => (image.id === nextImage.id ? nextImage : image)),
        }));
        return nextImage;
      });
      const settled = await Promise.allSettled(tasks);
      const successCount = settled.filter((item): item is PromiseFulfilledResult<StoredImage> => item.status === "fulfilled").length;
      const failedCount = settled.length - successCount;
      if (successCount === 0) {
        const firstError = settled.find((item) => item.status === "rejected");
        throw new Error(firstError?.status === "rejected" ? String(firstError.reason) : "生成图片失败");
      }
      await updateConversation(conversationId, (current) => ({
        ...(current ?? draftConversation),
        status: failedCount > 0 ? "error" : "success",
        error: failedCount > 0 ? `其中 ${failedCount} 张生成失败` : undefined,
      }));
      await Promise.all([loadStatus(), loadPublicUser({ silent: true })]);
      toast[failedCount > 0 ? "error" : "success"](failedCount > 0 ? `已完成 ${successCount} 张，另有 ${failedCount} 张未生成成功` : imageMode === "edit" ? `已完成 ${successCount} 张图片编辑` : `已生成 ${successCount} 张图片`);
    } catch (error) {
      const message = error instanceof Error ? error.message : imageMode === "edit" ? "编辑图片失败" : "生成图片失败";
      await persistConversation({ ...draftConversation, status: "error", error: message, images: draftConversation.images.map((image) => ({ ...image, status: "error", error: message })) });
      toast.error(message);
      await Promise.all([loadStatus(), loadPublicUser({ silent: true })]);
    } finally {
      setGeneratingIds((prev) => {
        const next = new Set(prev);
        next.delete(conversationId);
        return next;
      });
    }
  };

  const handleRedeem = async () => {
    const normalizedCode = redeemCode.trim();
    if (!normalizedCode) {
      toast.error("请输入激活码");
      return;
    }

    setIsRedeeming(true);
    try {
      await redeemActivationCode(normalizedCode);
      setRedeemCode("");
      await Promise.all([loadStatus(), loadPublicUser()]);
      toast.success("激活码兑换成功");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "兑换激活码失败");
    } finally {
      setIsRedeeming(false);
    }
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logoutPublicUser();
      setPublicUser(null);
      setRedeemCode("");
      toast.success("已退出登录");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "退出登录失败");
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <>
      <section className="px-3 pt-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="rounded-[32px] border border-white/80 bg-white/90 px-6 py-6 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="flex size-12 items-center justify-center rounded-2xl bg-stone-950 text-white"><Sparkles className="size-5" /></div>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-stone-950">{panelStatus?.title || "匿名公共生图面板"}</h1>
                <p className="max-w-3xl text-sm leading-6 text-stone-500">{panelStatus?.description || "无需登录，直接生成图片或上传参考图进行编辑。"}</p>
              </div>
            </div>
          </div>

          <div className="rounded-[32px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(246,240,232,0.92))] p-5 shadow-sm">
            {isLoadingPublicUser ? (
              <div className="flex min-h-[204px] items-center justify-center gap-3 text-sm text-stone-500">
                <LoaderCircle className="size-4 animate-spin" />
                正在读取账户状态
              </div>
            ) : publicUser ? (
              <div className="space-y-4">
                <div className="space-y-3">
                  <Badge variant="secondary" className="rounded-full bg-stone-950 px-3 py-1 text-[11px] tracking-[0.22em] text-white uppercase">
                    Member
                  </Badge>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-stone-900">
                        <UserRound className="size-4" />
                        <span className="text-sm font-medium">{publicUser.username}</span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-stone-500">已登录。当前生图会优先使用你的个人余额，不占用匿名公共池。</p>
                    </div>
                    <div className="rounded-[20px] border border-stone-200/80 bg-white/85 px-4 py-3 text-right">
                      <div className="text-xs text-stone-500">个人余额</div>
                      <div className="mt-1 text-2xl font-semibold text-stone-950">{publicUser.balance}</div>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="activation-code" className="text-sm font-medium text-stone-700">
                    兑换激活码
                  </label>
                  <div className="flex gap-2">
                    <Input
                      id="activation-code"
                      value={redeemCode}
                      onChange={(event) => setRedeemCode(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          void handleRedeem();
                        }
                      }}
                      placeholder="输入激活码"
                      className="h-11 border-stone-200 bg-white"
                    />
                    <Button
                      className="h-11 rounded-2xl bg-stone-950 px-4 text-white hover:bg-stone-800"
                      onClick={() => void handleRedeem()}
                      disabled={isRedeeming}
                    >
                      {isRedeeming ? <LoaderCircle className="size-4 animate-spin" /> : <Ticket className="size-4" />}
                      兑换
                    </Button>
                  </div>
                </div>

                <Button
                  variant="outline"
                  className="h-11 w-full rounded-2xl border-stone-200 bg-white/80 text-stone-700 hover:bg-white"
                  onClick={() => void handleLogout()}
                  disabled={isLoggingOut}
                >
                  {isLoggingOut ? <LoaderCircle className="size-4 animate-spin" /> : <LogOut className="size-4" />}
                  退出登录
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-3">
                  <Badge variant="secondary" className="rounded-full bg-white px-3 py-1 text-[11px] tracking-[0.22em] text-stone-700 uppercase">
                    Guest Access
                  </Badge>
                  <div className="space-y-2">
                    <h2 className="text-xl font-semibold tracking-tight text-stone-950">匿名可直接创作，登录后可沉淀个人权益。</h2>
                    <p className="text-sm leading-6 text-stone-500">注册后可以查看个人余额、兑换激活码，并把公开生图切换到你的会员账户。</p>
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-2">
                  <Button asChild className="h-11 rounded-2xl bg-stone-950 text-white hover:bg-stone-800">
                    <Link href="/login">登录</Link>
                  </Button>
                  <Button asChild variant="outline" className="h-11 rounded-2xl border-stone-200 bg-white/80 text-stone-700 hover:bg-white">
                    <Link href="/login?mode=register">注册</Link>
                  </Button>
                </div>

                <div className="rounded-[24px] border border-white/80 bg-white/70 p-4 text-sm leading-6 text-stone-600">
                  匿名模式继续可用。登录只是为了绑定个人余额与激活码，不会打断现在的公开试用流程。
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="mx-auto grid h-[calc(100vh-12rem)] min-h-0 w-full max-w-[1380px] grid-cols-1 gap-3 px-3 pb-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <ImageSidebar conversations={conversations} isLoadingHistory={isLoadingHistory} generatingIds={generatingIds} selectedConversationId={selectedConversationId} onCreateDraft={() => { setSelectedConversationId(null); resetComposer(); textareaRef.current?.focus(); }} onClearHistory={() => void clearImageConversations().then(() => { setConversations([]); setSelectedConversationId(null); toast.success("已清空历史记录"); }).catch((error) => { toast.error(error instanceof Error ? error.message : "清空历史记录失败"); })} onSelectConversation={setSelectedConversationId} onDeleteConversation={(id) => void deleteImageConversation(id).then(() => { setConversations((prev) => prev.filter((item) => item.id !== id)); setSelectedConversationId((prev) => (prev === id ? null : prev)); }).catch((error) => { toast.error(error instanceof Error ? error.message : "删除会话失败"); })} formatConversationTime={formatConversationTime} />

        <div className="flex min-h-0 flex-col gap-4">
          <div ref={resultsViewportRef} className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-2 py-3 sm:px-4 sm:py-4">
            <ImageResults selectedConversation={selectedConversation} isSelectedGenerating={isSelectedGenerating} openLightbox={openLightbox} formatConversationTime={formatConversationTime} />
          </div>

          <ImageComposer
            mode={imageMode}
            prompt={imagePrompt}
            model={imageModel}
            imageCount={imageCount}
            availableQuota={composerQuotaLabel}
            statusHint={composerStatusHint}
            hasAnyGenerating={generatingIds.size > 0}
            generatingCount={generatingIds.size}
            referenceImages={referenceImages}
            textareaRef={textareaRef}
            fileInputRef={fileInputRef}
            imageModelOptions={imageModelOptions}
            onModeChange={setImageMode}
            onPromptChange={setImagePrompt}
            onModelChange={setImageModel}
            onImageCountChange={setImageCount}
            onSubmit={handleGenerateImage}
            onPickReferenceImage={() => fileInputRef.current?.click()}
            onReferenceImageChange={(files) => void (files.length === 0 ? Promise.resolve().then(() => { setReferenceImageFiles([]); setReferenceImages([]); }) : appendReferenceImages(files))}
            onRemoveReferenceImage={(index) => {
              setReferenceImageFiles((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
              setReferenceImages((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
            }}
            submitBlocked={Boolean(composerStatusHint)}
          />
        </div>
      </section>

      <ImageLightbox images={lightboxImages} currentIndex={lightboxIndex} open={lightboxOpen} onOpenChange={setLightboxOpen} onIndexChange={setLightboxIndex} />
    </>
  );
}
