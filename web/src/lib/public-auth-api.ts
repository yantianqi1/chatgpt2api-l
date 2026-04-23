import { httpRequest } from "@/lib/request";

export type PublicUser = {
  id: string;
  username: string;
  balance: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type PublicUserResponse = {
  user: PublicUser;
};

const publicAuthRequest = <T>(path: string, options?: { method?: string; body?: unknown }) =>
  httpRequest<T>(path, {
    method: options?.method,
    body: options?.body,
    redirectOnUnauthorized: false,
    skipAuth: true,
    withCredentials: true,
  });

export async function registerPublicUser(username: string, password: string) {
  return publicAuthRequest<PublicUserResponse>("/api/public-auth/register", {
    method: "POST",
    body: { username, password },
  });
}

export async function loginPublicUser(username: string, password: string) {
  return publicAuthRequest<PublicUserResponse>("/api/public-auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export async function logoutPublicUser() {
  return publicAuthRequest<{ ok: boolean }>("/api/public-auth/logout", {
    method: "POST",
  });
}

export async function fetchPublicMe() {
  return publicAuthRequest<PublicUserResponse>("/api/public-auth/me");
}

export async function redeemActivationCode(code: string) {
  return publicAuthRequest<Record<string, unknown>>("/api/public-auth/redeem", {
    method: "POST",
    body: { code },
  });
}
