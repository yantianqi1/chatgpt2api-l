"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { ImageComposer } from "@/app/image/components/image-composer";
import { ImageResults } from "@/app/image/components/image-results";
import { ImageSidebar } from "@/app/image/components/image-sidebar";
import { ImageStudioHeader } from "@/app/image/components/image-studio-header";
import {
  clampImageCount,
  createId,
  createLoadingConversation,
  DEFAULT_IMAGE_AUTO_RETRY_TIMES,
  DEFAULT_IMAGE_COUNT,
  DEFAULT_MAX_IMAGE_COUNT,
  formatConversationTime,
  getImageSrc,
  inferImageMode,
  normalizeConversationHistory,
  readFileAsDataUrl,
  referenceImagesToFiles,
  toErrorMessage,
} from "@/app/image/lib/image-studio";
import { ImageLightbox } from "@/components/image-lightbox";
import {
  clearImageConversations,
  deleteImageConversation,
  listImageConversations,
  saveImageConversation,
  type ImageConversation,
  type StoredImage,
  type StoredReferenceImage,
} from "@/store/image-conversations";
import {
  editPublicImage,
  fetchPublicPanelStatus,
  generatePublicImage,
  type ImageModel,
  type PublicPanelConfig,
} from "@/lib/api";

const imageModelOptions: Array<{ label: string; value: ImageModel }> = [
  { label: "gpt-image-1", value: "gpt-image-1" },
  { label: "gpt-image-2", value: "gpt-image-2" },
];

function getStatusHint(status: PublicPanelConfig | null, statusError: string | null) {
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

export default function PublicImagePageClient() {
  const resultsViewportRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [imagePrompt, setImagePrompt] = useState("");
  const [imageCount, setImageCount] = useState(String(DEFAULT_IMAGE_COUNT));
  const [imageModel, setImageModel] = useState<ImageModel>("gpt-image-2");
  const [referenceImageFiles, setReferenceImageFiles] = useState<File[]>([]);
  const [referenceImages, setReferenceImages] = useState<StoredReferenceImage[]>([]);
  const [conversations, setConversations] = useState<ImageConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(new Set());
  const [panelStatus, setPanelStatus] = useState<PublicPanelConfig | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  );
  const composerMode = useMemo(() => inferImageMode(referenceImages), [referenceImages]);
  const parsedCount = useMemo(
    () => clampImageCount(Number(imageCount) || DEFAULT_IMAGE_COUNT, DEFAULT_MAX_IMAGE_COUNT),
    [imageCount],
  );
  const isSelectedGenerating = selectedConversationId !== null && generatingIds.has(selectedConversationId);
  const statusHint = useMemo(() => getStatusHint(panelStatus, statusError), [panelStatus, statusError]);
  const lightboxImages = useMemo(
    () =>
      (selectedConversation?.images ?? [])
        .filter((img) => img.status === "success")
        .map((img) => ({ id: img.id, src: getImageSrc(img) }))
        .filter((img) => !!img.src),
    [selectedConversation],
  );

  const loadStatus = useCallback(async () => {
    try {
      const nextStatus = await fetchPublicPanelStatus();
      setPanelStatus(nextStatus);
      setStatusError(null);
    } catch (error) {
      setStatusError(toErrorMessage(error, "读取公共面板状态失败"));
    }
  }, []);

  const persistConversation = useCallback(async (conversation: ImageConversation) => {
    setConversations((prev) => [conversation, ...prev.filter((item) => item.id !== conversation.id)]);
    await saveImageConversation(conversation);
  }, []);

  const updateConversation = useCallback(
    async (conversationId: string, updater: (current: ImageConversation | null) => ImageConversation) => {
      let nextConversation: ImageConversation | null = null;
      setConversations((prev) => {
        const current = prev.find((item) => item.id === conversationId) ?? null;
        nextConversation = updater(current);
        return [nextConversation, ...prev.filter((item) => item.id !== conversationId)];
      });
      if (nextConversation) {
        await saveImageConversation(nextConversation);
      }
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    const loadHistory = async () => {
      try {
        const items = await listImageConversations();
        const normalizedItems = await normalizeConversationHistory(items);
        if (!cancelled) {
          setConversations(normalizedItems);
        }
      } catch (error) {
        if (!cancelled) {
          toast.error(toErrorMessage(error, "读取会话记录失败"));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingHistory(false);
        }
      }
    };

    void loadHistory();
    void loadStatus();
    window.addEventListener("focus", loadStatus);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", loadStatus);
    };
  }, [loadStatus]);

  useEffect(() => {
    if (selectedConversation || isSelectedGenerating) {
      resultsViewportRef.current?.scrollTo({ top: resultsViewportRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [selectedConversation, isSelectedGenerating]);

  const openLightbox = useCallback(
    (imageId: string) => {
      const nextIndex = lightboxImages.findIndex((img) => img.id === imageId);
      if (nextIndex >= 0) {
        setLightboxIndex(nextIndex);
        setLightboxOpen(true);
      }
    },
    [lightboxImages],
  );

  const resetComposer = useCallback(() => {
    setImagePrompt("");
    setImageCount(String(DEFAULT_IMAGE_COUNT));
    setReferenceImageFiles([]);
    setReferenceImages([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const appendReferenceImages = useCallback(async (files: File[]) => {
    const previews = await Promise.all(
      files.map(async (file) => ({ name: file.name, type: file.type || "image/png", dataUrl: await readFileAsDataUrl(file) })),
    );
    setReferenceImageFiles((prev) => [...prev, ...files]);
    setReferenceImages((prev) => [...prev, ...previews]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const requestPublicImage = useCallback(
    async (prompt: string, model: ImageModel, files: File[]) => {
      let retries = 0;
      while (true) {
        try {
          return files.length > 0 ? await editPublicImage(files, prompt, model) : await generatePublicImage(prompt, model);
        } catch (error) {
          if (retries >= DEFAULT_IMAGE_AUTO_RETRY_TIMES) {
            throw error;
          }
          retries += 1;
        }
      }
    },
    [],
  );

  const runConversation = useCallback(async (conversationId: string, prompt: string, count: number, files: File[], images: StoredReferenceImage[]) => {
    const draftConversation = createLoadingConversation(conversationId, prompt, imageModel, count, new Date().toISOString(), images);
    const mode = inferImageMode(images);
    setGeneratingIds((prev) => new Set(prev).add(conversationId));
    setSelectedConversationId(conversationId);

    try {
      await persistConversation(draftConversation);
      const tasks = Array.from({ length: count }, (_, index) => requestPublicImage(prompt, imageModel, files)
        .then(async (data) => {
          const first = data.data?.[0];
          const imageSrc = first ? getImageSrc(first) : "";
          if (!imageSrc) {
            throw new Error(`第 ${index + 1} 张没有返回图片数据`);
          }
          const nextImage: StoredImage = { id: `${conversationId}-${index}`, status: "success", url: first?.url, b64_json: first?.b64_json };
          await updateConversation(conversationId, (current) => ({
            ...(current ?? draftConversation),
            images: (current?.images ?? draftConversation.images).map((image) => (image.id === nextImage.id ? nextImage : image)),
          }));
          return nextImage;
        })
        .catch(async (error) => {
          const failedImage: StoredImage = { id: `${conversationId}-${index}`, status: "error", error: toErrorMessage(error, "生成失败") };
          await updateConversation(conversationId, (current) => ({
            ...(current ?? draftConversation),
            images: (current?.images ?? draftConversation.images).map((image) => (image.id === failedImage.id ? failedImage : image)),
          }));
          throw error;
        }));
      const settled = await Promise.allSettled(tasks);
      const successCount = settled.filter((item): item is PromiseFulfilledResult<StoredImage> => item.status === "fulfilled").length;
      const failedCount = settled.length - successCount;
      if (successCount === 0) {
        throw new Error(toErrorMessage(settled.find((item) => item.status === "rejected"), `${mode === "edit" ? "编辑" : "生成"}图片失败`));
      }
      await updateConversation(conversationId, (current) => ({
        ...(current ?? draftConversation),
        status: failedCount > 0 ? "error" : "success",
        error: failedCount > 0 ? `其中 ${failedCount} 张生成失败` : undefined,
      }));
      toast[failedCount > 0 ? "error" : "success"](
        failedCount > 0 ? `已完成 ${successCount} 张，另有 ${failedCount} 张未生成成功` : mode === "edit" ? `已完成 ${successCount} 张图片编辑` : `已生成 ${successCount} 张图片`,
      );
    } catch (error) {
      const message = toErrorMessage(error, mode === "edit" ? "编辑图片失败" : "生成图片失败");
      await persistConversation({ ...draftConversation, status: "error", error: message, images: draftConversation.images.map((image) => ({ ...image, status: "error", error: message })) });
      toast.error(message);
    } finally {
      setGeneratingIds((prev) => {
        const next = new Set(prev);
        next.delete(conversationId);
        return next;
      });
      await loadStatus();
    }
  }, [imageModel, loadStatus, persistConversation, requestPublicImage, updateConversation]);

  const handleGenerateImage = useCallback(async () => {
    if (statusHint) {
      toast.error(statusHint);
      return;
    }
    const prompt = imagePrompt.trim();
    if (!prompt) {
      toast.error("请输入提示词");
      return;
    }
    const conversationId = createId();
    const nextFiles = [...referenceImageFiles];
    const nextImages = [...referenceImages];
    resetComposer();
    await runConversation(conversationId, prompt, parsedCount, nextFiles, nextImages);
  }, [imagePrompt, parsedCount, referenceImageFiles, referenceImages, resetComposer, runConversation, statusHint]);

  const handleRegenerateConversation = useCallback(async () => {
    if (!selectedConversation || generatingIds.has(selectedConversation.id)) {
      return;
    }
    const nextImages = [...(selectedConversation.referenceImages ?? [])];
    const nextFiles = await referenceImagesToFiles(nextImages);
    await runConversation(selectedConversation.id, selectedConversation.prompt, clampImageCount(selectedConversation.count, DEFAULT_MAX_IMAGE_COUNT), nextFiles, nextImages);
  }, [generatingIds, runConversation, selectedConversation]);

  return (
    <>
      <ImageStudioHeader
        model={imageModel}
        availableQuota={panelStatus ? String(panelStatus.available_quota) : statusError ? "—" : "加载中"}
        hasAnyGenerating={generatingIds.size > 0}
        generatingCount={generatingIds.size}
        title={panelStatus?.title || "匿名公共生图面板"}
        description={panelStatus?.description || "无需登录，直接生成图片或上传参考图进行编辑。"}
        statusHint={statusHint}
        compact
      />

      <section className="mx-auto grid min-h-0 w-full max-w-[1380px] grid-cols-1 gap-3 px-3 pb-6 lg:h-[calc(100vh-14rem)] lg:grid-cols-[240px_minmax(0,1fr)]">
        <ImageSidebar
          conversations={conversations}
          isLoadingHistory={isLoadingHistory}
          generatingIds={generatingIds}
          selectedConversationId={selectedConversationId}
          onCreateDraft={() => { setSelectedConversationId(null); resetComposer(); textareaRef.current?.focus(); }}
          onClearHistory={async () => {
            try {
              await clearImageConversations();
              setConversations([]);
              setSelectedConversationId(null);
              toast.success("已清空历史记录");
            } catch (error) {
              toast.error(toErrorMessage(error, "清空历史记录失败"));
            }
          }}
          onSelectConversation={setSelectedConversationId}
          onDeleteConversation={async (id) => {
            try {
              await deleteImageConversation(id);
              setConversations((prev) => prev.filter((item) => item.id !== id));
              setSelectedConversationId((prev) => (prev === id ? null : prev));
            } catch (error) {
              toast.error(toErrorMessage(error, "删除会话失败"));
            }
          }}
          formatConversationTime={formatConversationTime}
        />

        <div className="flex min-h-0 flex-col gap-4">
          <div ref={resultsViewportRef} className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-2 py-3 sm:px-4 sm:py-4">
            <ImageResults selectedConversation={selectedConversation} isSelectedGenerating={isSelectedGenerating} isRegenerating={isSelectedGenerating} openLightbox={openLightbox} formatConversationTime={formatConversationTime} onRegenerate={handleRegenerateConversation} />
          </div>

          <ImageComposer
            mode={composerMode}
            prompt={imagePrompt}
            model={imageModel}
            imageCount={imageCount}
            maxImageCount={DEFAULT_MAX_IMAGE_COUNT}
            referenceImages={referenceImages}
            textareaRef={textareaRef}
            fileInputRef={fileInputRef}
            imageModelOptions={imageModelOptions}
            onPromptChange={setImagePrompt}
            onModelChange={setImageModel}
            onImageCountChange={setImageCount}
            onSubmit={handleGenerateImage}
            onPickReferenceImage={() => fileInputRef.current?.click()}
            onReferenceImageChange={(files) => files.length > 0 ? appendReferenceImages(files) : Promise.resolve()}
            onRemoveReferenceImage={(index) => {
              setReferenceImageFiles((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
              setReferenceImages((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
            }}
          />
        </div>
      </section>

      <ImageLightbox images={lightboxImages} currentIndex={lightboxIndex} open={lightboxOpen} onOpenChange={setLightboxOpen} onIndexChange={setLightboxIndex} />
    </>
  );
}
