"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { GenerationDesk } from "@/components/GenerationDesk";
import { API_BASE, api, ApiError } from "@/lib/api";
import { ADMIN_TOKEN, useToken } from "@/lib/session";

const MeshViewer = dynamic(() => import("@/components/MeshViewer"), { ssr: false });

type Sample = {
  id: string;
  part_id: string;
  category_zh: string;
  brand: string;
  brand_label?: string;
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
  confirmed?: boolean;
  priority?: number | null;
  mesh_ready?: boolean;
  mesh_note?: string;
  mesh_url?: string | null;
  priced: boolean;
  orderable: boolean;
};

type SampleList = {
  disclaimer: string;
  count: number;
  pack_count: number;
  verified_count: number;
  generated_count: number;
  items: Sample[];
};

type Review = {
  priority: number;
  part: string;
  brand: string;
  brand_label?: string;
  model_code: string;
  status: string;
  note?: string;
};

type Attempt = {
  id: string;
  status: string;
  filename: string;
  brand: string;
  model_code: string;
  message: string;
  paid_api_called: boolean;
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
  postpaid_enabled: boolean;
  free_pack_exhausted: boolean;
  quota_message: string;
  queue: QueueItem[];
  review: Review[];
  attempts: Attempt[];
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
  const [meshUrls, setMeshUrls] = useState<Record<string, string>>({});
  const [openMesh, setOpenMesh] = useState("");
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

  async function showMesh(item: Sample) {
    if (!token || !item.mesh_url || !item.mesh_ready) return;
    if (meshUrls[item.id]) {
      setOpenMesh(item.id);
      return;
    }
    const response = await fetch(`${API_BASE}${item.mesh_url}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) {
      setError("网格没有读出来。请看这件下面的说明。");
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    setMeshUrls((current) => ({ ...current, [item.id]: url }));
    setOpenMesh(item.id);
  }

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
  const packItems = pack.items.filter((item) => item.source !== "generated");
  const generated = pack.items
    .filter((item) => item.source === "generated")
    .sort((left, right) => (left.priority || 99) - (right.priority || 99));
  const materials = packItems.filter((item) => item.kind === "material");
  const forms = packItems.filter((item) => item.kind !== "material");

  return (
    <div className="stack">
      <p className="kicker">祺盛</p>
      <h1 style={{ marginBottom: 0 }}>内部样板</h1>
      <p className="effect-banner">{pack.disclaimer}</p>
      <p className="fine">
        评测资料包 {pack.pack_count} 条，其中 {pack.verified_count} 条已核验到型号。另有 {pack.generated_count}{" "}
        件已确认入库的生成件，不给客户看，不计价，不能下单。价格没有录入，也不会挂到客户报价上。
      </p>
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}

      <h2>已确认入库的生成件</h2>
      <p className="fine">
        这 {generated.length} 件来自混元图生三维，已确认进入内部样板。标成生成件，不给客户看。原来的 20 条评测资料仍在下面，生成件不替换它们。
        Nobilia U60 没有产品图，没有做。
      </p>
      <div className="sample-grid">
        {generated.map((item) => (
          <article key={item.id}>
            {photos[item.id] ? (
              <img src={photos[item.id]} alt={`${item.brand_label || item.brand} ${item.model_code || ""} 生成预览`} />
            ) : (
              <p className="fine">预览图缺失</p>
            )}
            <strong>
              {item.category_zh} · {item.brand_label || item.brand} {item.model_code}
            </strong>
            <p className="fine">生成件 · 已确认 · 不给客户看</p>
            <p className="fine">{item.priced || item.orderable ? "计价异常" : "不计价，不能下单"}</p>
            <p className="mesh-note fine">{item.mesh_note}</p>
            {item.mesh_ready ? (
              <button type="button" onClick={() => showMesh(item).catch(() => setError("网格没有读出来。"))}>
                查看本地网格
              </button>
            ) : null}
            {openMesh === item.id && meshUrls[item.id] ? <MeshViewer url={meshUrls[item.id]} format="glb" /> : null}
          </article>
        ))}
      </div>

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
              <td>{item.brand_label || item.brand}</td>
              <td>{item.model_code}</td>
              <td>
                {item.status}
                {item.note ? (
                  <>
                    <br />
                    <span className="fine">{item.note}</span>
                  </>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <GenerationDesk token={token} onStarted={() => token && reload(token).catch(() => setError("生模记录没有刷新"))} />

      <h2>发起后停住的记录</h2>
      {generation.attempts.length === 0 ? (
        <p className="muted">还没有新的发起。在上面或产品库上传图册、产品图后点「发起生模」。额度不足时，记录会停在这里。</p>
      ) : (
        generation.attempts.map((item) => (
          <article key={item.id} className="card">
            <strong>{item.filename || "未命名文件"}</strong>
            <p className="fine">
              {item.brand} {item.model_code} · 额度不足 · 未调用付费接口
            </p>
            <p>{item.message}</p>
          </article>
        ))
      )}

      <h2>生成件确认入库</h2>
      {generation.queue.length === 0 ? (
        <p className="muted">没有新的待确认生成件。上面五件已经确认入库。确认前的件不会出现在客户选配里。</p>
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
