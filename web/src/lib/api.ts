import { httpRequest } from "@/lib/request";

export type AccountType = "Free" | "Plus" | "Pro" | "Team";
export type AccountStatus = "正常" | "限流" | "异常" | "禁用";
export type ImageModel = "gpt-image-1" | "gpt-image-2";
export type ImageRuntimeSettings = {
  default_model: ImageModel;
  max_count_per_request: number;
  auto_retry_times: number;
  request_timeout_seconds: number;
};
export type GeneratedImageData = {
  url?: string;
  b64_json?: string;
  revised_prompt?: string;
};
export type PublicPanelMode = "daily" | "fixed";
export type PublicPanelConfig = {
  enabled: boolean;
  title: string;
  description: string;
  mode: PublicPanelMode;
  daily_limit: number;
  daily_used: number;
  daily_reset_date: string;
  fixed_quota: number;
  available_quota: number;
  quota: number;
  disabled_reason: "disabled" | "quota_exhausted" | null;
  updated_at: string;
};

export type Account = {
  id: string;
  access_token: string;
  type: AccountType;
  status: AccountStatus;
  quota: number;
  email?: string | null;
  user_id?: string | null;
  limits_progress?: Array<{
    feature_name?: string;
    remaining?: number;
    reset_after?: string;
  }>;
  default_model_slug?: string | null;
  restoreAt?: string | null;
  success: number;
  fail: number;
  lastUsedAt: string | null;
};

type AccountListResponse = {
  items: Account[];
};

type AccountMutationResponse = {
  items: Account[];
  added?: number;
  skipped?: number;
  removed?: number;
  refreshed?: number;
  errors?: Array<{ access_token: string; error: string }>;
};

type AccountRefreshResponse = {
  items: Account[];
  refreshed: number;
  errors: Array<{ access_token: string; error: string }>;
};

type AccountUpdateResponse = {
  item: Account;
  items: Account[];
};

export async function login(authKey: string) {
  const normalizedAuthKey = String(authKey || "").trim();
  return httpRequest<{ ok: boolean }>("/auth/login", {
    method: "POST",
    body: {},
    headers: {
      Authorization: `Bearer ${normalizedAuthKey}`,
    },
    redirectOnUnauthorized: false,
  });
}

export async function fetchAccounts() {
  return httpRequest<AccountListResponse>("/api/accounts");
}

export async function fetchImageSettings() {
  return httpRequest<ImageRuntimeSettings>("/api/image/settings");
}

export async function updateImageSettings(updates: Partial<ImageRuntimeSettings>) {
  return httpRequest<ImageRuntimeSettings>("/api/image/settings", {
    method: "POST",
    body: updates,
  });
}

export async function createAccounts(tokens: string[]) {
  return httpRequest<AccountMutationResponse>("/api/accounts", {
    method: "POST",
    body: { tokens },
  });
}

export async function deleteAccounts(tokens: string[]) {
  return httpRequest<AccountMutationResponse>("/api/accounts", {
    method: "DELETE",
    body: { tokens },
  });
}

export async function refreshAccounts(accessTokens: string[]) {
  return httpRequest<AccountRefreshResponse>("/api/accounts/refresh", {
    method: "POST",
    body: { access_tokens: accessTokens },
  });
}

export async function updateAccount(
  accessToken: string,
  updates: {
    type?: AccountType;
    status?: AccountStatus;
    quota?: number;
  },
) {
  return httpRequest<AccountUpdateResponse>("/api/accounts/update", {
    method: "POST",
    body: {
      access_token: accessToken,
      ...updates,
    },
  });
}

export async function generateImage(prompt: string, model: ImageModel = "gpt-image-2") {
  return httpRequest<{ created: number; data: GeneratedImageData[] }>(
    "/v1/images/generations",
    {
      method: "POST",
      body: {
        prompt,
        model,
        n: 1,
        response_format: "url",
      },
    },
  );
}

export async function editImage(files: File | File[], prompt: string, model: ImageModel = "gpt-image-2") {
  const formData = new FormData();
  const uploadFiles = Array.isArray(files) ? files : [files];

  uploadFiles.forEach((file) => {
    formData.append("image", file);
  });
  formData.append("prompt", prompt);
  formData.append("model", model);
  formData.append("n", "1");

  formData.append("response_format", "url");

  return httpRequest<{ created: number; data: GeneratedImageData[] }>(
    "/v1/images/edits",
    {
      method: "POST",
      body: formData,
    },
  );
}

export async function fetchPublicPanelConfig() {
  return httpRequest<PublicPanelConfig>("/api/public-panel/config");
}

export async function fetchPublicPanelStatus() {
  return httpRequest<PublicPanelConfig>("/api/public-panel/status", {
    redirectOnUnauthorized: false,
    skipAuth: true,
  });
}

export async function updatePublicPanelConfig(
  payload: Pick<PublicPanelConfig, "enabled" | "title" | "description" | "mode" | "daily_limit" | "fixed_quota">,
) {
  return httpRequest<PublicPanelConfig>("/api/public-panel/config", {
    method: "POST",
    body: payload,
  });
}

export async function addPublicPanelQuota(amount: number) {
  return httpRequest<PublicPanelConfig>("/api/public-panel/quota/add", {
    method: "POST",
    body: { amount },
  });
}

export async function generatePublicImage(prompt: string, model: ImageModel = "gpt-image-2") {
  return httpRequest<{ created: number; data: GeneratedImageData[] }>(
    "/api/public-panel/images/generations",
    {
      method: "POST",
      body: {
        prompt,
        model,
        n: 1,
        response_format: "url",
      },
      redirectOnUnauthorized: false,
      skipAuth: true,
    },
  );
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

  return httpRequest<{ created: number; data: GeneratedImageData[] }>(
    "/api/public-panel/images/edits",
    {
      method: "POST",
      body: formData,
      redirectOnUnauthorized: false,
      skipAuth: true,
    },
  );
}

// ── CPA (CLIProxyAPI) ──────────────────────────────────────────────

export type CPAPool = {
  id: string;
  name: string;
  base_url: string;
  import_job?: CPAImportJob | null;
};

export type CPARemoteFile = {
  name: string;
  email: string;
};

export type CPAImportJob = {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  total: number;
  completed: number;
  added: number;
  skipped: number;
  refreshed: number;
  failed: number;
  errors: Array<{ name: string; error: string }>;
};

export async function fetchCPAPools() {
  return httpRequest<{ pools: CPAPool[] }>("/api/cpa/pools");
}

export async function createCPAPool(pool: { name: string; base_url: string; secret_key: string }) {
  return httpRequest<{ pool: CPAPool; pools: CPAPool[] }>("/api/cpa/pools", {
    method: "POST",
    body: pool,
  });
}

export async function updateCPAPool(
  poolId: string,
  updates: { name?: string; base_url?: string; secret_key?: string },
) {
  return httpRequest<{ pool: CPAPool; pools: CPAPool[] }>(`/api/cpa/pools/${poolId}`, {
    method: "POST",
    body: updates,
  });
}

export async function deleteCPAPool(poolId: string) {
  return httpRequest<{ pools: CPAPool[] }>(`/api/cpa/pools/${poolId}`, {
    method: "DELETE",
  });
}

export async function fetchCPAPoolFiles(poolId: string) {
  return httpRequest<{ pool_id: string; files: CPARemoteFile[] }>(`/api/cpa/pools/${poolId}/files`);
}

export async function startCPAImport(poolId: string, names: string[]) {
  return httpRequest<{ import_job: CPAImportJob | null }>(`/api/cpa/pools/${poolId}/import`, {
    method: "POST",
    body: { names },
  });
}

export async function fetchCPAPoolImportJob(poolId: string) {
  return httpRequest<{ import_job: CPAImportJob | null }>(`/api/cpa/pools/${poolId}/import`);
}
