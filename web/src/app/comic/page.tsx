import { redirect } from "next/navigation";

import ComicPageClient from "@/features/comic/comic-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function ComicPage() {
  if (!isStudioVariant()) {
    redirect("/accounts");
  }

  return <ComicPageClient />;
}
