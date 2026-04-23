import { httpRequest } from "@/lib/request";
import type { GeneratedImageData, ImageModel, PublicPanelConfig } from "@/lib/api";

type GenerationResponse = {
  created: number;
  data: GeneratedImageData[];
};

export async function fetchPublicPanelStatus() {
  return httpRequest<PublicPanelConfig>("/api/public-panel/status", {
    redirectOnUnauthorized: false,
    skipAuth: true,
    withCredentials: true,
  });
}

export async function generatePublicImage(prompt: string, model: ImageModel = "gpt-image-2") {
  return httpRequest<GenerationResponse>("/api/public-panel/images/generations", {
    method: "POST",
    body: {
      prompt,
      model,
      n: 1,
      response_format: "url",
    },
    redirectOnUnauthorized: false,
    skipAuth: true,
    withCredentials: true,
  });
}

export async function editPublicImage(files: File | File[], prompt: string, model: ImageModel = "gpt-image-2") {
  const formData = new FormData();
  const uploadFiles = Array.isArray(files) ? files : [files];

  uploadFiles.forEach((file) => {
    formData.append("image", file);
  });
  formData.append("prompt", prompt);
  formData.append("model", model);
  formData.append("n", "1");
  formData.append("response_format", "url");

  return httpRequest<GenerationResponse>("/api/public-panel/images/edits", {
    method: "POST",
    body: formData,
    redirectOnUnauthorized: false,
    skipAuth: true,
    withCredentials: true,
  });
}
