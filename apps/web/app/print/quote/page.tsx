"use client";

import { QuotePrintLoader } from "@/components/QuotePrintSheet";
import { CUSTOMER_TOKEN, useQueryParam } from "@/lib/session";

export default function CustomerQuotePrintPage() {
  const sid = useQueryParam("sid");
  return <QuotePrintLoader tokenKey={CUSTOMER_TOKEN} selectionId={sid || ""} loginHref="/c/login" />;
}
