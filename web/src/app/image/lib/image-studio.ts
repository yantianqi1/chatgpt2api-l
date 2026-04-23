import type { Account, GeneratedImageData, ImageModel } from "@/lib/api";
import type { ImageConversation, ImageConversationMode, StoredReferenceImage } from "@/store/image-conversations";
import { saveImageConversation } from "@/store/image-conversations";

export const DEFAULT_IMAGE_COUNT = 1;
export const DEFAULT_MAX_IMAGE_COUNT = 4;
export const DEFAULT_IMAGE_AUTO_RETRY_TIMES = 1;
export const IMAGE_RETRY_DELAY_MS = 800;

export function buildConversationTitle(prompt: string) {
  const trimmed = prompt.trim();
  if (trimmed.length <= 5) {
    return trimmed;
  }
  return `${trimmed.slice(0, 5)}...`;
}

export function formatConversationTime(value: string) {
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

export function formatAvailableQuota(accounts: Account[]) {
  const availableAccounts = accounts.filter((account) => account.status !== "禁用");
  return String(availableAccounts.reduce((sum, account) => sum + Math.max(0, account.quota), 0));
}

export function formatPlatformTitle(model: ImageModel) {
  return `${model.replace(/^gpt/i, "GPT")}:共享平台`;
}

export function inferImageMode(referenceImages: ArrayLike<unknown>): ImageConversationMode {
  return referenceImages.length > 0 ? "edit" : "generate";
}

export function clampImageCount(value: number, maxCount: number) {
  return Math.max(1, Math.min(maxCount, Number.isFinite(value) ? value : DEFAULT_IMAGE_COUNT));
}

export function createId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createLoadingConversation(
  id: string,
  prompt: string,
  model: ImageModel,
  count: number,
  createdAt: string,
  referenceImages: StoredReferenceImage[],
): ImageConversation {
  return {
    id,
    title: buildConversationTitle(prompt),
    prompt,
    model,
    mode: inferImageMode(referenceImages),
    referenceImages,
    count,
    images: Array.from({ length: count }, (_, index) => ({
      id: `${id}-${index}`,
      status: "loading",
    })),
    createdAt,
    status: "generating",
  };
}

export function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("读取参考图失败"));
    reader.readAsDataURL(file);
  });
}

export async function referenceImagesToFiles(referenceImages: StoredReferenceImage[]) {
  return Promise.all(
    referenceImages.map(async (image, index) => {
      const response = await fetch(image.dataUrl);
      const blob = await response.blob();
      return new File([blob], image.name || `reference-${index + 1}.png`, {
        type: blob.type || image.type || "image/png",
      });
    }),
  );
}

export function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  return fallback;
}

export function getImageSrc(image: Pick<GeneratedImageData, "url" | "b64_json">) {
  if (image.url?.trim()) {
    return image.url.trim();
  }
  if (image.b64_json?.trim()) {
    return `data:image/png;base64,${image.b64_json}`;
  }
  return "";
}

export async function normalizeConversationHistory(items: ImageConversation[]) {
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
