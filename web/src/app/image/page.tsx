"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { ImageComposer } from "@/app/image/components/image-composer";
import { ImageResults } from "@/app/image/components/image-results";
import { ImageSidebar } from "@/app/image/components/image-sidebar";
import { ImageStudioHeader } from "@/app/image/components/image-studio-header";
import {
  IMAGE_RETRY_DELAY_MS,
  clampImageCount,
  createId,
  createLoadingConversation,
  DEFAULT_IMAGE_AUTO_RETRY_TIMES,
  DEFAULT_IMAGE_COUNT,
  DEFAULT_MAX_IMAGE_COUNT,
  formatAvailableQuota,
  formatConversationTime,
  getImageSrc,
  inferImageMode,
  readFileAsDataUrl,
  referenceImagesToFiles,
  toErrorMessage,
} from "@/app/image/lib/image-studio";
import { ImageLightbox } from "@/components/image-lightbox";
import {
  editImage,
  fetchAccounts,
  fetchImageSettings,
  generateImage,
  type ImageModel,
  type ImageRuntimeSettings,
} from "@/lib/api";
import {
  clearImageConversations,
  deleteImageConversation,
  listImageConversations,
  saveImageConversation,
  type ImageConversation,
  type StoredImage,
  type StoredReferenceImage,
} from "@/store/image-conversations";

const imageModelOptions: Array<{ label: string; value: ImageModel }> = [
  { label: "gpt-image-1", value: "gpt-image-1" },
  { label: "gpt-image-2", value: "gpt-image-2" },
];

async function normalizeConversationHistory(items: ImageConversation[]) {
  const normalized = items.map((item) =>
    item.status === "generating"
      ? {
          ...item,
          status: "error" as const,
          error: item.images.some((image) => image.status === "success")
            ? item.error || "生成已中断"
            : "页面已刷新，生成已中断",
          images: item.images.map((image) =>
            image.status === "loading"
              ? {
                  ...image,
                  status: "error" as const,
                  error: "页面已刷新，生成已中断",
                }
              : image,
          ),
        }
      : item,
  );

  await Promise.all(
    normalized
      .filter((item, index) => item !== items[index])
      .map((item) => saveImageConversation(item)),
  );

  return normalized;
}

export default function ImagePage() {
  const didLoadQuotaRef = useRef(false);
  const didApplySettingsRef = useRef(false);
  const didWarnQuotaRef = useRef(false);
  const resultsViewportRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [imagePrompt, setImagePrompt] = useState("");
  const [imageCount, setImageCount] = useState(String(DEFAULT_IMAGE_COUNT));
  const [imageModel, setImageModel] = useState<ImageModel>("gpt-image-2");
  const [imageSettings, setImageSettings] = useState<ImageRuntimeSettings | null>(null);
  const [referenceImageFiles, setReferenceImageFiles] = useState<File[]>([]);
  const [referenceImages, setReferenceImages] = useState<StoredReferenceImage[]>([]);
  const [conversations, setConversations] = useState<ImageConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(new Set());
  const [availableQuota, setAvailableQuota] = useState("加载中");
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  );
  const maxImageCount = imageSettings?.max_count_per_request ?? DEFAULT_MAX_IMAGE_COUNT;
  const autoRetryTimes = imageSettings?.auto_retry_times ?? DEFAULT_IMAGE_AUTO_RETRY_TIMES;
  const composerMode = useMemo(() => inferImageMode(referenceImages), [referenceImages]);
  const parsedCount = useMemo(
    () => clampImageCount(Number(imageCount) || DEFAULT_IMAGE_COUNT, maxImageCount),
    [imageCount, maxImageCount],
  );
  const isSelectedGenerating = selectedConversationId !== null && generatingIds.has(selectedConversationId);
  const hasAnyGenerating = generatingIds.size > 0;

  const addGeneratingId = useCallback((id: string) => {
    setGeneratingIds((prev) => new Set(prev).add(id));
  }, []);

  const removeGeneratingId = useCallback((id: string) => {
    setGeneratingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const lightboxImages = useMemo(
    () =>
      (selectedConversation?.images ?? [])
        .filter((img) => img.status === "success")
        .map((img) => ({ id: img.id, src: getImageSrc(img) }))
        .filter((img) => !!img.src),
    [selectedConversation],
  );

  const openLightbox = useCallback(
    (imageId: string) => {
      const nextIndex = lightboxImages.findIndex((img) => img.id === imageId);
      if (nextIndex < 0) {
        return;
      }
      setLightboxIndex(nextIndex);
      setLightboxOpen(true);
    },
    [lightboxImages],
  );

  const persistConversation = useCallback(async (conversation: ImageConversation) => {
    setConversations((prev) => {
      const next = [conversation, ...prev.filter((item) => item.id !== conversation.id)];
      return next.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    });
    await saveImageConversation(conversation);
  }, []);

  const updateConversation = useCallback(
    async (conversationId: string, updater: (current: ImageConversation | null) => ImageConversation) => {
      let nextConversation: ImageConversation | null = null;

      setConversations((prev) => {
        const current = prev.find((item) => item.id === conversationId) ?? null;
        nextConversation = updater(current);
        const next = [nextConversation, ...prev.filter((item) => item.id !== conversationId)];
        return next.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
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
        if (cancelled) {
          return;
        }
        setConversations(normalizedItems);
      } catch (error) {
        toast.error(toErrorMessage(error, "读取会话记录失败"));
      } finally {
        if (!cancelled) {
          setIsLoadingHistory(false);
        }
      }
    };

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadImageRuntimeSettings = useCallback(async () => {
    try {
      const settings = await fetchImageSettings();
      setImageSettings(settings);
      if (didApplySettingsRef.current) {
        return;
      }
      didApplySettingsRef.current = true;
      setImageModel(settings.default_model);
      setImageCount((prev) => String(clampImageCount(Number(prev) || DEFAULT_IMAGE_COUNT, settings.max_count_per_request)));
    } catch (error) {
      toast.error(toErrorMessage(error, "读取图片设置失败"));
      if (!didApplySettingsRef.current) {
        didApplySettingsRef.current = true;
      }
    }
  }, []);

  const loadQuota = useCallback(async () => {
    try {
      const data = await fetchAccounts();
      didWarnQuotaRef.current = false;
      setAvailableQuota(formatAvailableQuota(data.items));
    } catch (error) {
      if (!didWarnQuotaRef.current) {
        didWarnQuotaRef.current = true;
        toast.error(toErrorMessage(error, "读取剩余额度失败"));
      }
      setAvailableQuota((prev) => (prev === "加载中" ? "—" : prev));
    }
  }, []);

  useEffect(() => {
    void loadImageRuntimeSettings();
  }, [loadImageRuntimeSettings]);

  useEffect(() => {
    if (didLoadQuotaRef.current) {
      return;
    }
    didLoadQuotaRef.current = true;

    const syncQuota = async () => {
      await loadQuota();
    };

    const handleFocus = () => {
      void syncQuota();
    };

    void syncQuota();
    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("focus", handleFocus);
    };
  }, [loadQuota]);

  useEffect(() => {
    setImageCount((prev) => String(clampImageCount(Number(prev) || DEFAULT_IMAGE_COUNT, maxImageCount)));
  }, [maxImageCount]);

  useEffect(() => {
    if (!selectedConversation && !isSelectedGenerating) {
      return;
    }

    resultsViewportRef.current?.scrollTo({
      top: resultsViewportRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [selectedConversation, isSelectedGenerating]);

  const resetComposer = useCallback(() => {
    setImagePrompt("");
    setImageCount(String(DEFAULT_IMAGE_COUNT));
    setReferenceImageFiles([]);
    setReferenceImages([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const handleCreateDraft = useCallback(() => {
    setSelectedConversationId(null);
    resetComposer();
    textareaRef.current?.focus();
  }, [resetComposer]);

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      setConversations((prev) => prev.filter((item) => item.id !== id));
      setSelectedConversationId((prev) => (prev === id ? null : prev));
      removeGeneratingId(id);

      try {
        await deleteImageConversation(id);
      } catch (error) {
        toast.error(toErrorMessage(error, "删除会话失败"));
        const items = await listImageConversations();
        setConversations(items);
      }
    },
    [removeGeneratingId],
  );

  const handleClearHistory = useCallback(async () => {
    try {
      await clearImageConversations();
      setConversations([]);
      setSelectedConversationId(null);
      setGeneratingIds(new Set());
      toast.success("已清空历史记录");
    } catch (error) {
      toast.error(toErrorMessage(error, "清空历史记录失败"));
    }
  }, []);

  const appendReferenceImages = useCallback(async (files: File[]) => {
    if (files.length === 0) {
      return;
    }

    try {
      const previews = await Promise.all(
        files.map(async (file) => ({
          name: file.name,
          type: file.type || "image/png",
          dataUrl: await readFileAsDataUrl(file),
        })),
      );
      setReferenceImageFiles((prev) => [...prev, ...files]);
      setReferenceImages((prev) => [...prev, ...previews]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      toast.error(toErrorMessage(error, "读取参考图失败"));
    }
  }, []);

  const handleReferenceImageChange = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }
      await appendReferenceImages(files);
    },
    [appendReferenceImages],
  );

  const handleRemoveReferenceImage = useCallback((index: number) => {
    setReferenceImageFiles((prev) => {
      const next = prev.filter((_, currentIndex) => currentIndex !== index);
      if (next.length === 0 && fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return next;
    });
    setReferenceImages((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
  }, []);

  const requestImageWithRetry = useCallback(
    async (prompt: string, model: ImageModel, files: File[]) => {
      let attempt = 0;

      while (true) {
        try {
          return files.length > 0 ? await editImage(files, prompt, model) : await generateImage(prompt, model);
        } catch (error) {
          if (attempt >= autoRetryTimes) {
            throw error;
          }
          attempt += 1;
          await new Promise<void>((resolve) => {
            window.setTimeout(resolve, IMAGE_RETRY_DELAY_MS * attempt);
          });
        }
      }
    },
    [autoRetryTimes],
  );

  const runConversation = useCallback(
    async (options: {
      conversationId: string;
      prompt: string;
      model: ImageModel;
      count: number;
      referenceImages: StoredReferenceImage[];
      referenceFiles: File[];
    }) => {
      const { conversationId, prompt, model, count, referenceImages: storedReferenceImages, referenceFiles } = options;
      const draftConversation = createLoadingConversation(
        conversationId,
        prompt,
        model,
        count,
        new Date().toISOString(),
        storedReferenceImages,
      );
      const mode = inferImageMode(storedReferenceImages);

      addGeneratingId(conversationId);
      setSelectedConversationId(conversationId);

      try {
        await persistConversation(draftConversation);

        const tasks = Array.from({ length: count }, (_, index) =>
          (async () => {
            try {
              const data = await requestImageWithRetry(prompt, model, referenceFiles);
              const first = data.data?.[0];
              const imageSrc = first ? getImageSrc(first) : "";
              if (!imageSrc) {
                throw new Error(`第 ${index + 1} 张没有返回图片数据`);
              }

              const nextImage: StoredImage = {
                id: `${conversationId}-${index}`,
                status: "success",
                url: first?.url,
                b64_json: first?.b64_json,
              };

              await updateConversation(conversationId, (current) => ({
                ...(current ?? draftConversation),
                images: (current?.images ?? draftConversation.images).map((image) =>
                  image.id === nextImage.id ? nextImage : image,
                ),
              }));

              return nextImage;
            } catch (error) {
              const message = toErrorMessage(error, `第 ${index + 1} 张${mode === "edit" ? "编辑" : "生成"}失败`);
              const failedImage: StoredImage = {
                id: `${conversationId}-${index}`,
                status: "error",
                error: message,
              };

              await updateConversation(conversationId, (current) => ({
                ...(current ?? draftConversation),
                images: (current?.images ?? draftConversation.images).map((image) =>
                  image.id === failedImage.id ? failedImage : image,
                ),
              }));

              throw error;
            }
          })(),
        );

        const settled = await Promise.allSettled(tasks);
        const successCount = settled.filter(
          (item): item is PromiseFulfilledResult<StoredImage> => item.status === "fulfilled",
        ).length;
        const failedCount = settled.length - successCount;

        if (successCount === 0) {
          const firstError = settled.find((item) => item.status === "rejected");
          throw new Error(
            firstError?.status === "rejected"
              ? toErrorMessage(firstError.reason, mode === "edit" ? "编辑图片失败" : "生成图片失败")
              : mode === "edit"
                ? "编辑图片失败"
                : "生成图片失败",
          );
        }

        await updateConversation(conversationId, (current) => ({
          ...(current ?? draftConversation),
          status: failedCount > 0 ? "error" : "success",
          error: failedCount > 0 ? `其中 ${failedCount} 张生成失败` : undefined,
        }));

        if (failedCount > 0) {
          toast.error(`已完成 ${successCount} 张，另有 ${failedCount} 张未生成成功`);
        } else {
          toast.success(mode === "edit" ? `已完成 ${successCount} 张图片编辑` : `已生成 ${successCount} 张图片`);
        }
      } catch (error) {
        const message = toErrorMessage(error, mode === "edit" ? "编辑图片失败" : "生成图片失败");
        await persistConversation({
          ...draftConversation,
          status: "error",
          error: message,
          images: draftConversation.images.map((image) =>
            image.status === "loading"
              ? {
                  ...image,
                  status: "error",
                  error: message,
                }
              : image,
          ),
        });
        toast.error(message);
      } finally {
        removeGeneratingId(conversationId);
        await loadQuota();
      }
    },
    [addGeneratingId, loadQuota, persistConversation, removeGeneratingId, requestImageWithRetry, updateConversation],
  );

  const handleGenerateImage = useCallback(async () => {
    const prompt = imagePrompt.trim();
    if (!prompt) {
      toast.error("请输入提示词");
      return;
    }

    const conversationId = createId();
    const nextReferenceFiles = [...referenceImageFiles];
    const nextReferenceImages = [...referenceImages];

    resetComposer();
    await runConversation({
      conversationId,
      prompt,
      model: imageModel,
      count: parsedCount,
      referenceImages: nextReferenceImages,
      referenceFiles: nextReferenceFiles,
    });
  }, [imageModel, imagePrompt, parsedCount, referenceImageFiles, referenceImages, resetComposer, runConversation]);

  const handleRegenerateConversation = useCallback(async () => {
    if (!selectedConversation || generatingIds.has(selectedConversation.id)) {
      return;
    }

    try {
      const nextReferenceImages = [...(selectedConversation.referenceImages ?? [])];
      const nextReferenceFiles = await referenceImagesToFiles(nextReferenceImages);
      await runConversation({
        conversationId: selectedConversation.id,
        prompt: selectedConversation.prompt,
        model: selectedConversation.model,
        count: clampImageCount(selectedConversation.count, maxImageCount),
        referenceImages: nextReferenceImages,
        referenceFiles: nextReferenceFiles,
      });
    } catch (error) {
      toast.error(toErrorMessage(error, "重新生成失败"));
    }
  }, [generatingIds, maxImageCount, runConversation, selectedConversation]);

  return (
    <>
      <ImageStudioHeader
        model={imageModel}
        availableQuota={availableQuota}
        hasAnyGenerating={hasAnyGenerating}
        generatingCount={generatingIds.size}
      />

      <section className="mx-auto grid min-h-0 w-full max-w-[1380px] grid-cols-1 gap-3 px-3 pb-6 lg:h-[calc(100vh-14rem)] lg:grid-cols-[240px_minmax(0,1fr)]">
        <ImageSidebar
          conversations={conversations}
          isLoadingHistory={isLoadingHistory}
          generatingIds={generatingIds}
          selectedConversationId={selectedConversationId}
          onCreateDraft={handleCreateDraft}
          onClearHistory={handleClearHistory}
          onSelectConversation={setSelectedConversationId}
          onDeleteConversation={handleDeleteConversation}
          formatConversationTime={formatConversationTime}
        />

        <div className="flex min-h-0 flex-col gap-4">
          <div
            ref={resultsViewportRef}
            className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-2 py-3 sm:px-4 sm:py-4"
          >
            <ImageResults
              selectedConversation={selectedConversation}
              isSelectedGenerating={isSelectedGenerating}
              isRegenerating={isSelectedGenerating}
              openLightbox={openLightbox}
              formatConversationTime={formatConversationTime}
              onRegenerate={handleRegenerateConversation}
            />
          </div>

          <ImageComposer
            mode={composerMode}
            prompt={imagePrompt}
            model={imageModel}
            imageCount={imageCount}
            maxImageCount={maxImageCount}
            referenceImages={referenceImages}
            textareaRef={textareaRef}
            fileInputRef={fileInputRef}
            imageModelOptions={imageModelOptions}
            onPromptChange={setImagePrompt}
            onModelChange={setImageModel}
            onImageCountChange={setImageCount}
            onSubmit={handleGenerateImage}
            onPickReferenceImage={() => fileInputRef.current?.click()}
            onReferenceImageChange={handleReferenceImageChange}
            onRemoveReferenceImage={handleRemoveReferenceImage}
          />
        </div>
      </section>

      <ImageLightbox
        images={lightboxImages}
        currentIndex={lightboxIndex}
        open={lightboxOpen}
        onOpenChange={setLightboxOpen}
        onIndexChange={setLightboxIndex}
      />
    </>
  );
}
