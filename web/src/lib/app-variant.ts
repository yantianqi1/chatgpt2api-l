export type AppVariant = "admin" | "studio";

export function getAppVariant(): AppVariant {
  return process.env.NEXT_PUBLIC_APP_VARIANT === "studio" ? "studio" : "admin";
}

export function isStudioVariant(): boolean {
  return getAppVariant() === "studio";
}
