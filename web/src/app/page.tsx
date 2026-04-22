import { redirect } from "next/navigation";

import PublicImagePageClient from "@/app/public-image-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function HomePage() {
  if (isStudioVariant()) {
    return <PublicImagePageClient />;
  }

  redirect("/accounts");
}
