"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { API_BASE, api, ApiError, downloadFile } from "@/lib/api";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import type { CatalogProduct } from "@/lib/types";

const MeshViewer = dynamic(() => import("@/components/MeshViewer"), { ssr: false });

export default function LibraryPage() {
  const { token } = useToken(ADMIN_TOKEN);
  const [pending, setPending] = useState<CatalogProduct[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [modelUrl, setModelUrl] = useState("/models/door-sample.glb");
  const [modelFormat, setModelFormat] = useState("glb");
  const [jobName, setJobName] = useState("示例通用衣柜");

  async function reload(auth: string) {
    const [waiting, all] = await Promise.all([
      api<CatalogProduct[]>("/api/admin/products?status=pending", { token: auth }),
      api<CatalogProduct[]>("/api/products", { token: auth }),
    ]);
    setPending(waiting);
    const next: Record<string, number> = {};
    all.forEach((item) => {
      next[item.part_id] = (next[item.part_id] || 0) + 1;
    });
    setCounts(next);
  }

  useEffect(() => {
    if (!token) return;
    reload(token).catch((err) => setError(err.message));
  }, [token]);

  async function uploadPack(file: File) {
    if (!token) return;
    const body = new FormData();
    body.set("file", file);
    setError("");
    try {
      const result = await api<{ imported: number }>("/api/admin/products/import", { method: "POST", token, body });
      setNote(`读入 ${result.imported} 条，先放在待确认。`);
      await reload(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "导入失败");
    }
  }

  async function confirm(id: string) {
    if (!token) return;
    await api(`/api/admin/products/${id}/confirm`, { method: "POST", token });
    setNote("已入库，客户可以从示例库里选到。");
    await reload(token);
  }

  async function uploadModel(file: File) {
    if (!token) return;
    const body = new FormData();
    body.set("file", file);
    const saved = await api<{ id: string; format: string; file_url: string }>("/api/admin/models", { method: "POST", token, body });
    const blob = await fetch(`${API_BASE}${saved.file_url}`, { headers: { Authorization: `Bearer ${token}` } }).then((res) => res.blob());
    setModelUrl(URL.createObjectURL(blob));
    setModelFormat(saved.format);
    setNote("模型已保存。拖动画布可以旋转；有多个网格时可以分别上色。");
  }

  async function fallbackModel() {
    if (!token) return;
    const job = await api<{ message: string }>("/api/model-jobs", {
      method: "POST",
      token,
      body: JSON.stringify({ part_id: "cabinetry", name: jobName, image_names: ["front.png", "side.png"] }),
    });
    setNote(job.message);
    await reload(token);
  }

  return (
    <div className="stack">
      <h1>示例产品库</h1>
      <p className="muted">品牌名和图片都是本原型自绘的示例，不是商业实拍，也不要拿去冒充在售商品。</p>
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}
      <div className="stats">
        {Object.entries(counts).map(([part, count]) => (
          <div key={part} className="stat">
            <b>{count}</b>
            {{
              ceiling: "天花",
              wall: "墙面",
              floor: "地面",
              cabinetry: "全屋定制",
              sanitary: "洁具",
              entry_door: "入户门",
              kitchen_appliance: "厨房电器",
              lighting: "灯具",
              switch_socket: "开关插座",
            }[part] || part}
          </div>
        ))}
      </div>
      <section className="card stack">
        <strong>导入手册或图包</strong>
        <p className="fine">PDF 手册或 zip 图包会进入待确认。确认之后客户才看得到。</p>
        <div className="row-actions">
          <button className="secondary" type="button" onClick={() => token && downloadFile("/api/admin/samples/manual", token, "示例手册.pdf")}>
            下载示例手册
          </button>
          <button className="secondary" type="button" onClick={() => token && downloadFile("/api/admin/samples/pack", token, "示例图包.zip")}>
            下载示例图包
          </button>
        </div>
        <input
          type="file"
          accept=".pdf,.zip,application/pdf,application/zip"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) uploadPack(file);
          }}
        />
      </section>
      <section className="stack">
        <h2>待人工确认</h2>
        {pending.length === 0 ? <p className="muted">现在没有待确认的型号。</p> : null}
        {pending.map((item) => (
          <article key={item.id} className="card pending-card">
            <img src={`${API_BASE}${item.image_url}`} alt={item.name} />
            <div>
              <strong>
                {item.model_code} · {item.name}
              </strong>
              <p className="fine">
                {item.spec}
                <br />
                国产 {item.domestic_price} 元 · 进口 {item.import_price} 元
              </p>
              <button type="button" onClick={() => confirm(item.id)}>
                确认入库
              </button>
            </div>
          </article>
        ))}
      </section>
      <section className="card stack">
        <strong>通用件</strong>
        <p className="fine">这里不连接付费生模。填写名称后，按品类默认尺寸做一件通用模型并入库。</p>
        <label className="field">
          名称
          <input value={jobName} onChange={(event) => setJobName(event.target.value)} />
        </label>
        <button type="button" onClick={() => fallbackModel().catch((err) => setError(err.message))}>
          按尺寸入库
        </button>
      </section>
      <section className="stack">
        <h2>导入模型</h2>
        <p className="fine">接收 SketchUp 导出的 glTF、GLB、FBX、OBJ。仓库里有两件自制示例：门（门框和门扇分开）和柜。</p>
        <div className="row-actions">
          <button className="secondary" type="button" onClick={() => { setModelUrl("/models/door-sample.glb"); setModelFormat("glb"); }}>
            看示例门
          </button>
          <button className="secondary" type="button" onClick={() => { setModelUrl("/models/cabinet-sample.glb"); setModelFormat("glb"); }}>
            看示例柜
          </button>
        </div>
        <input
          type="file"
          accept=".glb,.gltf,.fbx,.obj"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) uploadModel(file).catch((err) => setError(err.message));
          }}
        />
        <MeshViewer url={modelUrl} format={modelFormat} />
      </section>
    </div>
  );
}
