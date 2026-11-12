"use client";

import { useEffect, useState } from "react";
import { API_BASE, api, ApiError } from "@/lib/api";
import { ADMIN_TOKEN, useToken } from "@/lib/session";

type Sample = {
  id: string;
  part_id: string;
  category_zh: string;
  brand: string;
  origin: string;
  name: string | null;
  model_code: string | null;
  spec: string | null;
  width_mm: number | null;
  depth_mm: number | null;
  height_mm: number | null;
  kind: string;
  verified: boolean;
  offer_mode: string;
  data_status: string;
  has_image: boolean;
  image_url: string | null;
  notes: string;
  source: string;
  priced: boolean;
  orderable: boolean;
};

type SampleList = {
  disclaimer: string;
  count: number;
  verified_count: number;
  items: Sample[];
};

type Review = {
  priority: number;
  part: string;
  brand: string;
  model_code: string;
  status: string;
  note?: string;
};

type QueueItem = {
  id: string;
  label: string;
  brand: string;
  model_code: string | null;
  status: string;
};

type Generation = {
  status: string;
  note: string;
  paid_api_called: boolean;
  queue: QueueItem[];
  review: Review[];
};

function sizeText(item: Sample) {
  if (item.width_mm == null && item.depth_mm == null && item.height_mm == null) return "尺寸未核验";
  const cell = (value: number | null) => (value == null ? "—" : String(value));
  return `${cell(item.width_mm)} × ${cell(item.depth_mm)} × ${cell(item.height_mm)} mm`;
}

export default function SamplesPage() {
  const { token } = useToken(ADMIN_TOKEN);
  const [pack, setPack] = useState<SampleList | null>(null);
  const [photos, setPhotos] = useState<Record<string, string>>({});
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  async function reload(auth: string) {
    const [rows, review] = await Promise.all([
      api<SampleList>("/api/admin/internal-samples", { token: auth }),
      api<Generation>("/api/admin/generation", { token: auth }),
    ]);
    setPack(rows);
    setGeneration(review);
    const next: Record<string, string> = {};
    await Promise.all(
      rows.items
        .filter((item) => item.has_image && item.image_url)
        .map(async (item) => {
          const response = await fetch(`${API_BASE}${item.image_url}`, { headers: { Authorization: `Bearer ${auth}` } });
          if (!response.ok) return;
          next[item.id] = URL.createObjectURL(await response.blob());
        }),
    );
    setPhotos(next);
  }

  useEffect(() => {
    if (!token) return;
    reload(token).catch((err) => setError(err instanceof ApiError ? err.message : "内部样板没有读到"));
  }, [token]);

  async function decide(id: string, action: "confirm" | "reject") {
    if (!token) return;
    setError("");
    try {
      await api(`/api/admin/generation/${id}/${action}`, { method: "POST", token });
      setNote(action === "confirm" ? "已放入内部样板。客户选配看不到，也不计价。" : "已退回，不入库。");
      await reload(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有处理这条");
    }
  }

  if (!pack || !generation) return <p className="muted">{error || "正在读取内部样板…"}</p>;
  const materials = pack.items.filter((item) => item.kind === "material");
  const forms = pack.items.filter((item) => item.kind !== "material");

  return (
    <div className="stack">
      <p className="kicker">祺盛</p>
      <h1 style={{ marginBottom: 0 }}>内部样板</h1>
      <p className="effect-banner">{pack.disclaimer}</p>
      <p className="fine">
        共 {pack.count} 条，其中 {pack.verified_count} 条已核验到型号。价格没有录入。不会挂到客户报价上。
      </p>
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}

      <h2>材质示意贴图</h2>
      <p className="fine">天花、墙面、地面用资料包里的官方图作房间示意贴图。不是品牌实拍级效果，也不占用生模。</p>
      <div className="sample-grid">
        {materials.map((item) => (
          <article key={item.id}>
            {photos[item.id] ? <img src={photos[item.id]} alt={`${item.brand} ${item.model_code || ""}`} /> : <p className="fine">无图</p>}
            <strong>
              {item.category_zh} · {item.brand} {item.model_code}
            </strong>
            <p className="fine">示意贴图 · {sizeText(item)}</p>
          </article>
        ))}
      </div>

      <h2>全屋定制 · 按实际尺寸定制</h2>
      <p className="fine">这一类按现场尺寸做，一般没有单一零售型号。不补型号。欧派按量尺定制列出。Nobilia 只保留官方类型表里的模块尺寸，供对照。</p>
      <div className="stack">
        {forms
          .filter((item) => item.offer_mode === "made_to_measure")
          .map((item) => (
            <article key={item.id} className="card quote-line">
              <div>
                <strong>
                  {item.category_zh} · {item.brand}
                  {item.model_code ? ` · 类型表模块 ${item.model_code}` : " · 量尺定制"}
                </strong>
                <span>
                  {item.model_code ? (
                    <>
                      {sizeText(item)}
                      <br />
                      {item.data_status}
                    </>
                  ) : (
                    <>
                      量尺定制
                      <br />
                      按实际尺寸定制。不补型号，不补尺寸。
                    </>
                  )}
                  {!item.has_image ? " · 无官方单品图" : ""}
                </span>
              </div>
            </article>
          ))}
      </div>

      <h2>形体样板</h2>
      <div className="stack">
        {forms
          .filter((item) => item.offer_mode !== "made_to_measure")
          .map((item) => (
          <article key={item.id} className="card quote-line">
            <div>
              {photos[item.id] ? <img className="effect-thumb" src={photos[item.id]} alt={item.brand} /> : null}
              <strong>
                {item.category_zh} · {item.brand}
                {item.model_code ? ` ${item.model_code}` : ""}
              </strong>
              <span>
                {item.verified ? item.name : item.data_status}
                <br />
                {item.verified ? sizeText(item) : "不补型号，不补尺寸"}
                {!item.has_image ? " · 无官方单品图" : ""}
              </span>
            </div>
          </article>
        ))}
      </div>

      <h2>生模 · {generation.status}</h2>
      <p className="effect-banner">{generation.note}</p>
      <table className="data">
        <thead>
          <tr>
            <th>顺序</th>
            <th>品类</th>
            <th>品牌</th>
            <th>型号</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {generation.review.map((item) => (
            <tr key={item.model_code}>
              <td>{item.priority}</td>
              <td>{item.part}</td>
              <td>{item.brand}</td>
              <td>{item.model_code}</td>
              <td>
                {item.status}
                {item.note ? <span className="fine">{item.note}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>生成件确认入库</h2>
      {generation.queue.length === 0 ? (
        <p className="muted">本轮没有待确认的生成件。确认前不会进入内部样板，也不会出现在客户选配里。</p>
      ) : (
        generation.queue.map((item) => (
          <article key={item.id} className="card row-actions" style={{ justifyContent: "space-between" }}>
            <div>
              <strong>{item.label}</strong>
              <p className="fine">
                {item.brand} {item.model_code || ""} · 待确认 · 不计价
              </p>
            </div>
            <div className="row-actions">
              <button type="button" onClick={() => decide(item.id, "confirm")}>
                确认放入内部样板
              </button>
              <button className="secondary" type="button" onClick={() => decide(item.id, "reject")}>
                退回
              </button>
            </div>
          </article>
        ))
      )}
    </div>
  );
}
