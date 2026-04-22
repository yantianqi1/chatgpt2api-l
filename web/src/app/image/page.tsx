import { notFound } from "next/navigation";

import ImagePageClient from "@/app/image/image-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function ImagePage() {
  if (isStudioVariant()) {
    notFound();
  }

  return <ImagePageClient />;
}
