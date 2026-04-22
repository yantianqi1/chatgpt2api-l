import { notFound } from "next/navigation";

import AccountsPageClient from "@/app/accounts/accounts-page-client";
import { isStudioVariant } from "@/lib/app-variant";

export default function AccountsPage() {
  if (isStudioVariant()) {
    notFound();
  }

  return <AccountsPageClient />;
}
