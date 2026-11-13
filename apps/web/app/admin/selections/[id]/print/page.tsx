"use client";

import { useParams } from "next/navigation";
import { QuotePrintLoader } from "@/components/QuotePrintSheet";
import { ADMIN_TOKEN } from "@/lib/session";

export default function AdminQuotePrintPage() {
  const params = useParams<{ id: string }>();
  return <QuotePrintLoader tokenKey={ADMIN_TOKEN} selectionId={params.id} loginHref="/admin/login" />;
}
