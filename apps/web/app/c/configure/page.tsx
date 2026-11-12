"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE, api, ApiError } from "@/lib/api";
import { yuan, withScheme } from "@/lib/money";
import { CUSTOMER_TOKEN, useQueryParam, useToken } from "@/lib/session";
import { DEFAULT_MM } from "@/lib/sizes";
import { PhoneHeader, QuoteLines, Steps } from "@/components/ui";
import PhotoStandIn, { type StandPreset } from "@/components/PhotoStandIn";
import type { OfficialMaps } from "@/components/officialTexture";
import type { Placement } from "@/components/RoomPlacement";
import type { CatalogProduct as Product, ItemPick, Scheme, SchemeItem, Selection } from "@/lib/types";

const PLACEABLE = new Set(["sanitary", "switch_socket", "cabinetry", "lighting", "entry_door", "kitchen_appliance"]);
const SURFACE_NAME: Record<string, string> = { ceiling: "天花", wall: "墙面", floor: "地面" };

type FinishTexture = {
  id: string;
  part_id: string;
  brand: string;
  model_code: string | null;
  origin: string;
  texture_url: string | null;
};

const ScenePreview = dynamic(() => import("@/components/ScenePreview"), { ssr: false });
const RoomPlacement = dynamic(() => import("@/components/RoomPlacement"), { ssr: false });

type BrandTier = "domestic" | "import";
type ItemDraft = {
  item_id: string;
  included: boolean;
  quantity: number;
  brand_tier: BrandTier;
  product_id?: string | null;
};
type Level = "home" | "schemes" | "pieces";

function thumb(partId: string, label: string, productId?: string | null) {
  if (productId) return `${API_BASE}/api/products/${productId}/image.svg`;
  return `${API_BASE}/api/products/placeholder.svg?part=${encodeURIComponent(partId)}&label=${encodeURIComponent(label)}`;
}

function placementsFor(selection: Selection, photos: Record<string, { front: string; back?: string }>): Placement[] {
  const subs = selection.substitutes || [];
  const marks = selection.plan?.marks || [];
  const used = new Set<string>();
  if (marks.length) {
    const rows: Placement[] = [];
    for (const mark of marks) {
      const sub =
        subs.find((item) => item.room_name === mark.room_name && item.slot_label === mark.slot_label && !used.has(item.id)) ||
        subs.find((item) => item.room_name === mark.room_name && item.part_id === mark.part_id && !used.has(item.id));
      if (sub) used.add(sub.id);
      const fallback = DEFAULT_MM[mark.part_id] || [600, 600, 600];
      rows.push({
        room: mark.room_name,
        label: sub?.slot_label || mark.slot_label || mark.product_name || mark.part_id,
        kind: mark.part_id,
        width_mm: sub?.width_mm || mark.width_mm || fallback[0],
        depth_mm: sub?.depth_mm || mark.depth_mm || fallback[1],
        height_mm: sub?.height_mm || mark.height_mm || fallback[2],
        photoUrl: sub ? photos[sub.id]?.front : undefined,
        photoBackUrl: sub ? photos[sub.id]?.back : undefined,
        substitute: Boolean(sub),
        x: mark.x,
        y: mark.y,
      });
    }
    return rows;
  }
  const rows: Placement[] = [{ room: "客厅", label: "示例沙发", kind: "sofa", width_mm: 2200, depth_mm: 900, height_mm: 780 }];
  for (const sub of subs) {
    const fallback = DEFAULT_MM[sub.part_id] || [600, 600, 600];
    rows.push({
      room: sub.room_name || "客厅",
      label: sub.slot_label,
      kind: sub.part_id,
      width_mm: sub.width_mm || fallback[0],
      depth_mm: sub.depth_mm || fallback[1],
      height_mm: sub.height_mm || fallback[2],
      photoUrl: photos[sub.id]?.front,
      photoBackUrl: photos[sub.id]?.back,
      substitute: true,
    });
  }
  for (const line of selection.lines || []) {
    for (const pick of line.picks || []) {
      if (!pick.included) continue;
      const kind = pick.display_part_id || line.part_id;
      const fallback = DEFAULT_MM[kind] || [600, 600, 600];
      rows.push({
        room: pick.room_name || "玄关",
        label: pick.group_label || pick.name,
        kind,
        width_mm: pick.width_mm || fallback[0],
        depth_mm: pick.depth_mm || fallback[1],
        height_mm: pick.height_mm || fallback[2],
      });
    }
  }
  return rows;
}

export default function ConfigurePage() {
  const router = useRouter();
  const sid = useQueryParam("sid");
  const { token, ready } = useToken(CUSTOMER_TOKEN);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [level, setLevel] = useState<Level>("home");
  const [partId, setPartId] = useState("ceiling");
  const [schemeId, setSchemeId] = useState<string | null>(null);
  const [room, setRoom] = useState("");
  const [view, setView] = useState<"finish" | "rooms">("finish");
  const [libraryFor, setLibraryFor] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState<{ src: string; title: string } | null>(null);
  const [photos, setPhotos] = useState<Record<string, { front: string; back?: string }>>({});
  const [standPreset, setStandPreset] = useState<StandPreset | null>(null);
  const [finishTextures, setFinishTextures] = useState<FinishTexture[]>([]);
  const [textureChoice, setTextureChoice] = useState<Record<string, string>>({});

  useEffect(() => {
    if (ready && !token) router.replace("/c/login");
  }, [ready, token, router]);

  useEffect(() => {
    api<{ items: FinishTexture[] }>("/api/finish-textures")
      .then((pack) => {
        setFinishTextures(pack.items);
        setTextureChoice((current) => {
          if (Object.keys(current).length) return current;
          const next: Record<string, string> = {};
          for (const part of ["ceiling", "wall", "floor"]) {
            const domestic = pack.items.find((item) => item.part_id === part && item.origin === "domestic" && item.texture_url);
            if (domestic) next[part] = domestic.id;
          }
          return next;
        });
      })
      .catch(() => setFinishTextures([]));
  }, []);

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

  useEffect(() => {
    if (!token || !selection) return;
    let stop = false;
    const created: string[] = [];
    const rows = selection.substitutes || [];
    (async () => {
      const next: Record<string, { front: string; back?: string }> = {};
      for (const item of rows) {
        const front = await fetch(`${API_BASE}${item.photo_path}`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (!front.ok || stop) continue;
        const frontUrl = URL.createObjectURL(await front.blob());
        if (stop) {
          URL.revokeObjectURL(frontUrl);
          break;
        }
        created.push(frontUrl);
        let backUrl: string | undefined;
        if (item.extra_photo_path) {
          const back = await fetch(`${API_BASE}${item.extra_photo_path}`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          });
          if (back.ok) {
            backUrl = URL.createObjectURL(await back.blob());
            created.push(backUrl);
          }
        }
        next[item.id] = { front: frontUrl, back: backUrl };
      }
      if (!stop) setPhotos(next);
    })();
    return () => {
      stop = true;
      created.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [token, selection?.updated_at, (selection?.substitutes || []).map((item) => `${item.id}:${item.photo_path}:${item.extra_photo_path || ""}`).join("|")]);

  async function saveLine(targetPart: string, targetScheme: string, items?: ItemDraft[]) {
    if (!token || !sid) return null;
    setSaving(true);
    setError("");
    try {
      const saved = await api<Selection>(`/api/selections/${sid}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ lines: [{ part_id: targetPart, scheme_id: targetScheme, items }] }),
      });
      setSelection(saved);
      return saved;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
      return null;
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

  async function openLibrary(itemPart: string) {
    setProducts(await api<Product[]>(`/api/products?part_id=${itemPart}`).catch(() => []));
  }

  if (!selection || !selection.style || !selection.ceiling || !selection.floor || !selection.wall) {
    return (
      <div>
        <PhoneHeader title="部位选配" back={sid ? `/c/style?sid=${sid}` : "/c/style"} />
        <Steps current={3} />
        <p className="muted">{error || "正在读取方案…"}</p>
      </div>
    );
  }

  const ceilingScheme = selection.ceiling;
  const floorScheme = selection.floor;
  const wallScheme = selection.wall;
  const parts = selection.parts || [];
  const currentPart = parts.find((item) => item.id === partId);
  const visualScheme =
    partId === "floor" ? floorScheme : partId === "wall" ? wallScheme : ceilingScheme;
  const activeScheme =
    partId === "lighting"
      ? ceilingScheme
      : currentPart?.visual
        ? (selection.style.parts.find((item) => item.id === partId)?.schemes.find((item) => item.id === schemeId) ?? visualScheme)
        : currentPart?.schemes.find((item) => item.id === schemeId);
  const linePart = partId === "lighting" ? "ceiling" : partId;
  const line = (selection.lines || []).find((item) => item.part_id === linePart && item.scheme_id === activeScheme?.id);
  const showBrand = partId === "lighting" || partId === "switch_socket";
  const pieceItems = (activeScheme?.items || []).filter((item) => {
    const shown = (item.display_part_id || activeScheme?.part_id) === partId;
    if (!shown) return false;
    if (room && (item.room_name || "整户") !== room) return false;
    return true;
  });
  const allRooms = Array.from(
    new Set((activeScheme?.items || []).filter((item) => (item.display_part_id || activeScheme?.part_id) === partId).map((item) => item.room_name || "整户")),
  );

  function drafts(items: SchemeItem[], picks: ItemPick[] | undefined, patch?: Partial<ItemDraft> & { item_id: string }): ItemDraft[] {
    return items.map((item) => {
      const pick = picks?.find((row) => row.scheme_item_id === item.id);
      const current: ItemDraft = {
        item_id: item.id,
        included: pick?.included ?? false,
        quantity: pick?.quantity ?? item.default_quantity,
        brand_tier: pick?.brand_tier === "import" ? "import" : "domestic",
        product_id: pick?.product_id,
      };
      return patch && patch.item_id === item.id ? { ...current, ...patch } : current;
    });
  }

  async function commit(item: SchemeItem, patch: Partial<ItemDraft>) {
    if (!activeScheme) return;
    const next = drafts(pieceItems, line?.picks, { item_id: item.id, ...patch });
    await saveLine(linePart, activeScheme.id, next);
  }

  const bound = (selection.bindings || []).find((item) => item.part_id === partId && (item.room_name || "整户") === (room || item.room_name || "整户"));
  const officialMaps: OfficialMaps = {};
  for (const part of ["ceiling", "wall", "floor"] as const) {
    const row = finishTextures.find((item) => item.id === textureChoice[part]);
    officialMaps[part] = row?.texture_url ? `${API_BASE}${row.texture_url}` : null;
  }
  const sofaPhoto = (selection.substitutes || [])
    .filter((item) => item.part_id === "sofa")
    .map((item) => photos[item.id]?.front)
    .find(Boolean);
  const switchPhoto = (selection.substitutes || [])
    .filter((item) => item.part_id === "switch_socket")
    .map((item) => photos[item.id]?.front)
    .find(Boolean);
  const roomNames = selection.unit.rooms.map((item) => item.name);

  return (
    <div>
      <PhoneHeader
        title={level === "home" ? "九类选配" : currentPart?.name || "选配"}
        back={level === "home" ? (sid ? `/c/style?sid=${sid}` : "/c/style") : undefined}
        onBack={
          level === "pieces"
            ? () => {
                setLevel("schemes");
                setLibraryFor(null);
              }
            : level === "schemes"
              ? () => setLevel("home")
              : undefined
        }
      />
      <Steps current={3} />
      {error ? <p className="error">{error}</p> : null}
      <div className="stack">
        <div className="row-actions" style={{ justifyContent: "space-between" }}>
          <strong>{selection.style.name}</strong>
          <span className="muted">{saving ? "正在保存" : selection.style.tagline}</span>
        </div>
        {level === "home" ? (
          <>
            <div className="row-actions">
              <button type="button" className={view === "finish" ? "" : "secondary"} onClick={() => setView("finish")}>
                材质
              </button>
              <button type="button" className={view === "rooms" ? "" : "secondary"} onClick={() => setView("rooms")}>
                房间落位
              </button>
            </div>
            {view === "finish" ? (
              <ScenePreview
                styleId={selection.style.id}
                ceiling={ceilingScheme.material}
                floor={floorScheme.material}
                wall={wallScheme.material}
                sofaPhoto={sofaPhoto}
                switchPhoto={switchPhoto}
                officialMaps={officialMaps}
              />
            ) : (
              <RoomPlacement
                rooms={selection.unit.rooms}
                placements={placementsFor(selection, photos)}
                vectors={selection.plan?.vectors}
                officialMaps={officialMaps}
                finish={{
                  floor: floorScheme.material,
                  wall: wallScheme.material,
                  ceiling: ceilingScheme.material,
                  styleId: selection.style.id,
                }}
              />
            )}
            {finishTextures.length ? (
              <div className="stack">
                <p className="fine">示意贴图，不是品牌实拍，也不改变报价。</p>
                {(["ceiling", "wall", "floor"] as const).map((part) => (
                  <div key={part} className="row-actions">
                    <span className="fine">{SURFACE_NAME[part]}</span>
                    {finishTextures
                      .filter((item) => item.part_id === part)
                      .map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          className={textureChoice[part] === item.id ? "" : "secondary"}
                          onClick={() => setTextureChoice({ ...textureChoice, [part]: item.id })}
                        >
                          {item.brand} {item.model_code}
                        </button>
                      ))}
                  </div>
                ))}
              </div>
            ) : null}
            {(selection.substitutes || []).length ? (
              <p className="effect-banner">
                仅用于效果展示，不列入采购。
                <br />
                外形接近、能看出来是同一类、同一款式方向。
                <br />
                这不是付费重建的质量。
                <br />
                单张照片可能看不清背面和细部。
                <br />
                部位合计不含这些照片。
              </p>
            ) : null}
            {sofaPhoto && view === "finish" ? (
              <p className="fine">客餐厅里的沙发贴了照片。右侧墙上的开关示意只在上传开关照片后出现，为了看清会比常用面板大一点。房间落位可以靠近看常用尺寸。</p>
            ) : null}
            <p className="fine">
              九类并列。先点大项，再选方案或房间，最后逐件看示例图、数量和价格。示例图不是品牌实拍；只有上传的照片会贴到效果件上。三维仍是示意，不是施工图对齐。
              {selection.plan ? selection.plan.honesty : ""}
            </p>
            <div className="cat-grid">
              {parts.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="cat-card"
                  onClick={() => {
                    setPartId(item.id);
                    setSchemeId(item.visual ? (item.id === "floor" ? floorScheme.id : item.id === "wall" ? wallScheme.id : ceilingScheme.id) : null);
                    setRoom("");
                    setLevel("schemes");
                  }}
                >
                  <strong>{item.name}</strong>
                  <span className="fine">{item.visual ? "先选方案" : item.id === "lighting" ? "跟着天花" : "按房间"}</span>
                </button>
              ))}
            </div>
            {token && sid ? (
              <PhotoStandIn
                token={token}
                selectionId={sid}
                selection={selection}
                rooms={roomNames}
                photos={photos}
                onChange={setSelection}
              />
            ) : null}
          </>
        ) : null}

        {level === "schemes" && partId === "lighting" ? (
          <div className="stack">
            <p className="fine">灯具来自天花方案「{ceilingScheme.name}」。点一个房间，再改这一组灯。</p>
            {Array.from(
              new Set(
                (ceilingScheme.items || [])
                  .filter((item) => item.display_part_id === "lighting")
                  .map((item) => item.room_name || "整户"),
              ),
            ).map((name) => (
              <button
                key={name}
                type="button"
                className="scheme"
                onClick={() => {
                  setSchemeId(ceilingScheme.id);
                  setRoom(name);
                  setLevel("pieces");
                }}
              >
                <strong>{name}</strong>
                <span className="muted">
                  {(ceilingScheme.items || []).find((item) => item.display_part_id === "lighting" && (item.room_name || "整户") === name)?.group_label}
                </span>
              </button>
            ))}
          </div>
        ) : null}

        {level === "schemes" && partId !== "lighting" ? (
          <div className="stack">
            <p className="fine">{currentPart?.visual ? "选一套硬装方案，下面再点件。" : "选一套方案，再进房间逐件点。"}</p>
            {(currentPart?.visual ? selection.style.parts.find((item) => item.id === partId)?.schemes : currentPart?.schemes)?.map((scheme) => (
              <button
                key={scheme.id}
                type="button"
                className={scheme.id === (currentPart?.visual ? visualScheme.id : schemeId) ? "scheme on" : "scheme"}
                onClick={async () => {
                  if (currentPart?.visual) await choose(scheme);
                  else await saveLine(partId, scheme.id);
                  const names = Array.from(new Set((scheme.items || []).filter((item) => !item.display_part_id || item.display_part_id === partId).map((item) => item.room_name || "整户")));
                  setSchemeId(scheme.id);
                  setRoom(names[0] || "");
                  setLevel("pieces");
                }}
              >
                <span className="scheme-head">
                  <strong>{scheme.name}</strong>
                  <b>{currentPart?.visual ? `${scheme.unit_price} 元/㎡` : `${scheme.unit_price} 元`}</b>
                </span>
                <span className="muted">{scheme.summary}</span>
              </button>
            ))}
          </div>
        ) : null}

        {level === "pieces" && activeScheme ? (
          <div className="stack">
            {currentPart?.visual && partId !== "lighting" ? (
              <ScenePreview
                styleId={selection.style.id}
                ceiling={ceilingScheme.material}
                floor={floorScheme.material}
                wall={wallScheme.material}
                sofaPhoto={sofaPhoto}
                switchPhoto={switchPhoto}
                officialMaps={officialMaps}
              />
            ) : null}
            <p className="fine">
              {activeScheme.name}
              {bound ? ` · 本项目已挂 ${bound.product_name}` : ""}。示例图不是品牌实拍。
            </p>
            {allRooms.length > 1 ? (
              <div className="tabs">
                {allRooms.map((name) => (
                  <button key={name} type="button" className={name === (room || allRooms[0]) ? "on" : ""} onClick={() => setRoom(name)}>
                    {name}
                  </button>
                ))}
              </div>
            ) : null}
            {(room ? pieceItems : pieceItems).map((item) => {
              const pick = line?.picks?.find((row) => row.scheme_item_id === item.id);
              const included = pick?.included ?? false;
              const imagePart = item.display_part_id || partId;
              return (
                <article key={item.id} className="card piece">
                  <button
                    type="button"
                    className="piece-photo"
                    onClick={() => setZoom({ src: thumb(imagePart, item.name, pick?.product_id), title: item.group_label || item.name })}
                  >
                    <img src={thumb(imagePart, item.name, pick?.product_id)} alt={item.group_label || item.name} />
                  </button>
                  <div className="piece-meta">
                    <label className="row-actions">
                      <input type="checkbox" checked={included} onChange={(event) => commit(item, { included: event.target.checked })} />
                      <strong>{item.group_label || item.name}</strong>
                    </label>
                    <span className="fine">{pick?.product_name || "示意图，不是品牌实拍"} · {item.unit_price} 元起</span>
                    <div className="piece-controls">
                      <label className="field">
                        数量
                        <input
                          type="number"
                          min={1}
                          value={pick?.quantity ?? item.default_quantity}
                          onChange={(event) => commit(item, { quantity: Math.max(1, Number(event.target.value) || 1) })}
                        />
                      </label>
                      {showBrand ? (
                        <label className="field">
                          国产/进口
                          <select
                            value={pick?.brand_tier === "import" ? "import" : "domestic"}
                            onChange={(event) => commit(item, { brand_tier: event.target.value as BrandTier })}
                          >
                            <option value="domestic">国产</option>
                            <option value="import">进口</option>
                          </select>
                        </label>
                      ) : null}
                    </div>
                    <button
                      className="secondary"
                      type="button"
                      onClick={() => {
                        const next = libraryFor === item.id ? null : item.id;
                        setLibraryFor(next);
                        if (next) openLibrary(imagePart);
                      }}
                    >
                      从示例库换这一件
                    </button>
                    {libraryFor === item.id ? (
                      <div className="sku-grid">
                        {products.map((product) => (
                          <button
                            key={product.id}
                            type="button"
                            className={pick?.product_id === product.id ? "scheme on sku-card" : "scheme sku-card"}
                            onClick={() => commit(item, { included: true, product_id: product.id })}
                          >
                            <img src={`${API_BASE}${product.image_url}`} alt={product.name} />
                            <strong>{product.name}</strong>
                            <span className="fine">
                              {product.spec}
                              <br />
                              国产 {product.domestic_price} 元 · 进口 {product.import_price} 元
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {PLACEABLE.has(imagePart) ? (
                      <button
                        className="ghost"
                        type="button"
                        onClick={() => {
                          setStandPreset({
                            part_id: imagePart,
                            room_name: item.room_name || room || "客厅",
                            slot_label: item.name,
                          });
                          document.getElementById("photo-stand-in")?.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        上传照片看效果
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
            <QuoteLines quote={selection.quote} />
            {token && sid ? (
              <PhotoStandIn
                token={token}
                selectionId={sid}
                selection={selection}
                rooms={roomNames}
                preset={standPreset}
                photos={photos}
                onChange={setSelection}
              />
            ) : null}
          </div>
        ) : null}

        {zoom ? (
          <button type="button" className="lightbox" onClick={() => setZoom(null)} aria-label="关闭大图">
            <img src={zoom.src} alt={zoom.title} />
          </button>
        ) : null}
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
    </div>
  );
}
