"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { yuan, withScheme } from "@/lib/money";
import { CUSTOMER_TOKEN, useQueryParam, useToken } from "@/lib/session";
import { PhoneHeader, QuoteLines, Steps } from "@/components/ui";
import type { Scheme, Selection } from "@/lib/types";

const ScenePreview = dynamic(() => import("@/components/ScenePreview"), { ssr: false });

export default function ConfigurePage() {
  const router = useRouter();
  const sid = useQueryParam("sid");
  const { token, ready } = useToken(CUSTOMER_TOKEN);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [part, setPart] = useState("ceiling");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (ready && !token) router.replace("/c/login");
  }, [ready, token, router]);

  useEffect(() => {
    if (!token || !sid) return;
    api<Selection>(`/api/selections/${sid}`, { token })
      .then((row) => {
        if (!row.style) {
          router.replace(`/c/style?sid=${sid}`);
          return;
        }
        setSelection(row);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "方案加载失败"));
  }, [token, sid, router]);

  async function choose(scheme: Scheme) {
    if (!selection || !token || !sid) return;
    const previous = selection;
    setSelection(withScheme(selection, scheme));
    setSaving(true);
    setError("");
    try {
      const saved = await api<Selection>(`/api/selections/${sid}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ [`${scheme.part_id}_scheme_id`]: scheme.id }),
      });
      setSelection(saved);
    } catch (err) {
      setSelection(previous);
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const style = selection?.style;
  const group = style?.parts.find((item) => item.id === part);
  const selectedId =
    part === "ceiling" ? selection?.ceiling?.id : part === "floor" ? selection?.floor?.id : selection?.wall?.id;

  return (
    <div>
      <PhoneHeader title="部位选配" back={sid ? `/c/style?sid=${sid}` : "/c/style"} />
      <Steps current={3} />
      {error ? <p className="error">{error}</p> : null}
      {!selection || !style || !selection.ceiling || !selection.floor || !selection.wall ? (
        <p className="muted">正在读取方案…</p>
      ) : (
        <div className="stack">
          <div className="row-actions" style={{ justifyContent: "space-between" }}>
            <strong>{style.name}</strong>
            <span className="muted">{saving ? "正在保存" : style.tagline}</span>
          </div>
          <ScenePreview
            styleId={style.id}
            ceiling={selection.ceiling.material}
            floor={selection.floor.material}
            wall={selection.wall.material}
          />
          <p className="fine">按住画面拖动可以旋转。换方案后，天花、地面、墙面的颜色和造型会变。</p>
          <div className="tabs">
            {style.parts.map((item) => (
              <button key={item.id} type="button" className={item.id === part ? "on" : ""} onClick={() => setPart(item.id)}>
                {item.name}
              </button>
            ))}
          </div>
          {group?.schemes.map((scheme) => (
            <button
              key={scheme.id}
              type="button"
              className={scheme.id === selectedId ? "scheme on" : "scheme"}
              onClick={() => choose(scheme)}
            >
              <span className="scheme-head">
                <strong>
                  方案 {scheme.index} · {scheme.name}
                </strong>
                <b>{scheme.unit_price} 元/㎡</b>
              </span>
              <span className="muted">{scheme.summary}</span>
            </button>
          ))}
          <QuoteLines quote={selection.quote} />
          <div className="sticky-total">
            <div>
              <div className="fine">部位合计</div>
              <strong>{yuan(selection.quote.total)}</strong>
            </div>
            <button type="button" onClick={() => router.push(`/c/scheme?sid=${sid}`)}>
              查看方案
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
