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

  async function saveLine(partId: string, schemeId: string | null, brandTier: "domestic" | "import" | null) {
    if (!token || !sid || !schemeId) return;
    setSaving(true);
    setError("");
    try {
      const saved = await api<Selection>(`/api/selections/${sid}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          lines: [{ part_id: partId, scheme_id: schemeId, brand_tier: brandTier }],
        }),
      });
      setSelection(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

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
          <section className="stack">
            <h2 style={{ margin: "8px 0 0", fontSize: 16 }}>其他类目</h2>
            <p className="fine">这六类计入报价，三维仍只表现天花、地面和墙面。</p>
            {(selection.parts || []).filter((item) => !item.visual).map((item) => {
              const current = (selection.lines || []).find((line) => line.part_id === item.id);
              return (
                <div key={item.id} className="card stack">
                  <strong>{item.name}</strong>
                  {item.allows_brand_tier ? (
                    <label className="field">
                      品牌档
                      <select
                        value={current?.brand_tier || "domestic"}
                        onChange={(event) =>
                          saveLine(item.id, current?.scheme_id || item.schemes[0]?.id || null, event.target.value as "domestic" | "import")
                        }
                      >
                        <option value="domestic">国产</option>
                        <option value="import">进口</option>
                      </select>
                    </label>
                  ) : null}
                  {item.schemes.map((scheme) => (
                    <button
                      key={scheme.id}
                      type="button"
                      className={current?.scheme_id === scheme.id ? "scheme on" : "scheme"}
                      onClick={() => saveLine(scheme.part_id, scheme.id, current?.brand_tier || (item.allows_brand_tier ? "domestic" : null))}
                    >
                      <span className="scheme-head">
                        <strong>{scheme.name}</strong>
                        <b>{scheme.unit_price} 元</b>
                      </span>
                      <span className="muted">{scheme.summary}</span>
                    </button>
                  ))}
                </div>
              );
            })}
          </section>
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
