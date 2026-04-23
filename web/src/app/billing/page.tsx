import { notFound } from "next/navigation";

import BillingPageClient from "@/app/billing/billing-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function BillingPage() {
  if (isStudioVariant()) {
    notFound();
  }

  return <BillingPageClient />;
}
