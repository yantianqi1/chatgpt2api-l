import axios, {AxiosError, type AxiosRequestConfig} from "axios";

import webConfig from "@/constants/common-env";
import {clearStoredAuthKey, getStoredAuthKey} from "@/store/auth";

type RequestConfig = AxiosRequestConfig & {
  redirectOnUnauthorized?: boolean;
  skipAuth?: boolean;
  withCredentials?: boolean;
};

type ErrorPayload = {
    detail?: {
        error?: string | { message?: string };
    };
    error?: string | {
        message?: string;
    };
    message?: string;
};

function extractErrorMessage(payload: ErrorPayload | undefined) {
    const detailError = payload?.detail?.error;
    if (typeof detailError === "string" && detailError.trim()) {
        return detailError;
    }
    if (detailError && typeof detailError === "object" && typeof detailError.message === "string" && detailError.message.trim()) {
        return detailError.message;
    }

    const error = payload?.error;
    if (typeof error === "string" && error.trim()) {
        return error;
    }
    if (error && typeof error === "object" && typeof error.message === "string" && error.message.trim()) {
        return error.message;
    }

    if (typeof payload?.message === "string" && payload.message.trim()) {
        return payload.message;
    }
    return "";
}

const request = axios.create({
    baseURL: webConfig.apiUrl.replace(/\/$/, ""),
});

request.interceptors.request.use(async (config) => {
    const nextConfig = {...config};
    const authKey = await getStoredAuthKey();
    const headers = {...(nextConfig.headers || {})} as Record<string, string>;
    if (authKey && !headers.Authorization && !(nextConfig as RequestConfig).skipAuth) {
        headers.Authorization = `Bearer ${authKey}`;
    }
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    nextConfig.headers = headers;
    return nextConfig;
});

request.interceptors.response.use(
    (response) => response,
    async (error: AxiosError<ErrorPayload>) => {
        const status = error.response?.status;
        const shouldRedirect = (error.config as RequestConfig | undefined)?.redirectOnUnauthorized !== false;
        if (status === 401 && shouldRedirect && typeof window !== "undefined") {
            // Avoid redirect loop — only redirect if not already on /login
            if (!window.location.pathname.startsWith("/login")) {
                await clearStoredAuthKey();
                window.location.replace("/login");
                // Return a never-resolving promise to prevent further error handling
                // while the browser navigates away
                return new Promise(() => {});
            }
        }

        const payload = error.response?.data;
        const message = extractErrorMessage(payload) || error.message || `请求失败 (${status || 500})`;
        return Promise.reject(new Error(message));
    },
);

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  redirectOnUnauthorized?: boolean;
  skipAuth?: boolean;
  withCredentials?: boolean;
};

export async function httpRequest<T>(path: string, options: RequestOptions = {}) {
  const {
    method = "GET",
    body,
    headers,
    redirectOnUnauthorized = true,
    skipAuth = false,
    withCredentials = false,
  } = options;
  const config: RequestConfig = {
    url: path,
    method,
    data: body,
    headers,
    redirectOnUnauthorized,
    skipAuth,
    withCredentials,
  };
  const response = await request.request<T>(config);
  return response.data;
}
