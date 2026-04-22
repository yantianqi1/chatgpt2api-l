import { notFound } from "next/navigation";

import SettingsPageClient from "@/app/settings/settings-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function SettingsPage() {
  if (isStudioVariant()) {
    notFound();
  }

  return <SettingsPageClient />;
}
