import { notFound } from "next/navigation";

import LoginPageClient from "@/app/login/login-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function LoginPage() {
  if (isStudioVariant()) {
    notFound();
  }

  return <LoginPageClient />;
}
