"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { CUSTOMER_TOKEN, useQueryParam, useToken } from "@/lib/session";
import { PhoneHeader, Steps } from "@/components/ui";
import type { Selection, Style } from "@/lib/types";

export default function StylePage() {
  const router = useRouter();
  const sid = useQueryParam("sid");
  const { token, ready } = useToken(CUSTOMER_TOKEN);
  const [styles, setStyles] = useState<Style[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && !token) router.replace("/c/login");
  }, [ready, token, router]);

  useEffect(() => {
    api<Style[]>("/api/styles").then(setStyles).catch(() => setError("风格目录加载失败"));
  }, []);

  useEffect(() => {
    if (!token || !sid) return;
    api<Selection>(`/api/selections/${sid}`, { token })
      .then((selection) => setCurrent(selection.style?.id ?? null))
      .catch((err) => setError(err instanceof ApiError ? err.message : "方案不存在"));
  }, [token, sid]);

  async function pick(styleId: string) {
    if (!token || !sid) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/selections/${sid}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ style_id: styleId }),
      });
      router.push(`/c/configure?sid=${sid}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存风格失败");
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <PhoneHeader title="选择风格" back="/c/match" />
      <Steps current={2} />
      <p className="muted">先定一种风格。天花、地面、墙面会从各自的方案 1 开始，之后再换。</p>
      {error ? <p className="error">{error}</p> : null}
      {styles.map((style) => (
        <button
          key={style.id}
          className={current === style.id ? "choice on" : "choice"}
          type="button"
          disabled={busy}
          onClick={() => pick(style.id)}
        >
          <strong>{style.name}</strong>
          <span className="muted">{style.tagline}</span>
          <span className="swatches" aria-hidden>
            {style.palette.map((color) => (
              <i key={color} style={{ background: color }} />
            ))}
          </span>
          <span className="choice-copy">{style.description}</span>
        </button>
      ))}
    </div>
  );
}
