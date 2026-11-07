"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { yuan, withScheme } from "@/lib/money";
import { CUSTOMER_TOKEN, useQueryParam, useToken } from "@/lib/session";
import { PhoneHeader, QuoteLines, Steps } from "@/components/ui";
import type { ItemPick, Scheme, Selection } from "@/lib/types";

type BrandTier = "domestic" | "import";
type ItemDraft = { item_id: string; included: boolean; quantity: number; brand_tier: BrandTier };

const ScenePreview = dynamic(() => import("@/components/ScenePreview"), { ssr: false });

function ItemKit({
  scheme,
  picks,
  onChange,
}: {
  scheme?: Scheme;
  picks?: ItemPick[];
  onChange: (drafts: ItemDraft[]) => void;
}) {
  if (!scheme?.items?.length) return null;
  const drafts = (scheme.items || []).map((item) => {
    const pick = picks?.find((row) => row.scheme_item_id === item.id);
    return {
      item_id: item.id,
      included: pick?.included ?? false,
      quantity: pick?.quantity ?? item.default_quantity,
      brand_tier: (pick?.brand_tier === "import" ? "import" : "domestic") as BrandTier,
      item,
    };
  });
  function commit(itemId: string, patch: Partial<ItemDraft>) {
    onChange(
      drafts.map((row) =>
        row.item_id === itemId ? { item_id: row.item_id, included: row.included, quantity: row.quantity, brand_tier: row.brand_tier, ...patch } : {
          item_id: row.item_id,
          included: row.included,
          quantity: row.quantity,
          brand_tier: row.brand_tier,
        },
      ),
    );
  }
  return (
    <div className="stack">
      <p className="fine">件组：每件选品牌、要不要、数量。入户门如果只有一件，也在这里勾。</p>
      {drafts.map((row) => (
        <div key={row.item_id} className="card">
          <label className="row-actions">
            <input type="checkbox" checked={row.included} onChange={(event) => commit(row.item_id, { included: event.target.checked })} />
            <strong>{row.item.name}</strong>
            <span>{row.item.unit_price} 元</span>
          </label>
          <div className="row-actions">
            <label className="field">
              数量
              <input
                type="number"
                min={1}
                value={row.quantity}
                onChange={(event) => commit(row.item_id, { quantity: Math.max(1, Number(event.target.value) || 1) })}
              />
            </label>
            <label className="field">
              品牌
              <select value={row.brand_tier} onChange={(event) => commit(row.item_id, { brand_tier: event.target.value as BrandTier })}>
                <option value="domestic">国产</option>
                <option value="import">进口</option>
              </select>
            </label>
          </div>
        </div>
      ))}
    </div>
  );
}

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

  async function saveLine(partId: string, schemeId: string, items?: ItemDraft[]) {
    if (!token || !sid) return;
    setSaving(true);
    setError("");
    try {
      const saved = await api<Selection>(`/api/selections/${sid}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          lines: [{ part_id: partId, scheme_id: schemeId, items }],
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
          <p className="fine">三维只表现天花、地面、墙面的方案材质。九类都是先选方案，再在件组里逐件定品牌、要不要和数量。</p>
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
          {group && selectedId ? (
            <ItemKit
              scheme={group.schemes.find((scheme) => scheme.id === selectedId)}
              picks={(selection.lines || []).find((line) => line.part_id === group.id && line.scheme_id === selectedId)?.picks}
              onChange={(drafts) => saveLine(group.id, selectedId, drafts)}
            />
          ) : null}
          {(selection.parts || [])
            .filter((item) => !item.visual)
            .map((item) => {
              const current = (selection.lines || []).find((line) => line.part_id === item.id);
              return (
                <div key={item.id} className="card stack">
                  <strong>{item.name}</strong>
                  {item.schemes.map((scheme) => (
                    <button
                      key={scheme.id}
                      type="button"
                      className={current?.scheme_id === scheme.id ? "scheme on" : "scheme"}
                      onClick={() => saveLine(item.id, scheme.id)}
                    >
                      <span className="scheme-head">
                        <strong>{scheme.name}</strong>
                        <b>{scheme.unit_price} 元</b>
                      </span>
                      <span className="muted">{scheme.summary}</span>
                    </button>
                  ))}
                  {current?.scheme_id ? (
                    <ItemKit
                      scheme={item.schemes.find((scheme) => scheme.id === current.scheme_id)}
                      picks={current.picks}
                      onChange={(drafts) => saveLine(item.id, current.scheme_id || "", drafts)}
                    />
                  ) : null}
                </div>
              );
            })}
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
