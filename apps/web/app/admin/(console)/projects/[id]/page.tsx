"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ChineseFile } from "@/components/ui";
import { projectStatus } from "@/lib/money";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import ProjectBindings from "@/components/ProjectBindings";
import PlanMarks from "@/components/PlanMarks";
import type { AiJob, Project } from "@/lib/types";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { token } = useToken(ADMIN_TOKEN);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [unit, setUnit] = useState({ code: "", name: "", building_area_m2: "", finish_area_m2: "", summary: "" });
  const [upload, setUpload] = useState({ kind: "floor_plan", unit_type_id: "", replace_asset_id: "", file: null as File | null });

  async function reload(auth: string) {
    setProject(await api<Project>(`/api/admin/projects/${params.id}`, { token: auth }));
  }

  useEffect(() => {
    if (!token) return;
    reload(token).catch((err) => setError(err.message));
  }, [token, params.id]);

  async function publish(status: "published" | "draft") {
    if (!token) return;
    setError("");
    try {
      setProject(await api<Project>(`/api/admin/projects/${params.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ status }),
      }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "更新失败");
    }
  }

  async function addUnit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError("");
    try {
      setProject(
        await api<Project>(`/api/admin/projects/${params.id}/units`, {
          method: "POST",
          token,
          body: JSON.stringify({
            code: unit.code,
            name: unit.name,
            building_area_m2: Number(unit.building_area_m2),
            finish_area_m2: unit.finish_area_m2 ? Number(unit.finish_area_m2) : null,
            summary: unit.summary,
          }),
        }),
      );
      setUnit({ code: "", name: "", building_area_m2: "", finish_area_m2: "", summary: "" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "添加户型失败");
    }
  }

  async function sendFile(event: React.FormEvent) {
    event.preventDefault();
    if (!token || !upload.file) return;
    const body = new FormData();
    body.set("file", upload.file);
    body.set("kind", upload.kind);
    if (upload.unit_type_id) body.set("unit_type_id", upload.unit_type_id);
    if (upload.replace_asset_id) body.set("replace_asset_id", upload.replace_asset_id);
    setError("");
    try {
      setProject(await api<Project>(`/api/admin/projects/${params.id}/assets`, { method: "POST", token, body }));
      setNote("文件已保存。");
      setUpload({ ...upload, file: null, replace_asset_id: "" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败");
    }
  }

  async function recognize(assetId: string) {
    if (!token) return;
    const body = new FormData();
    body.set("asset_id", assetId);
    try {
      const job = await api<AiJob>("/api/ai/floorplan", { method: "POST", token, body });
      setNote(job.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "识别失败");
    }
  }

  if (!project) return <p className="muted">{error || "正在读取项目…"}</p>;

  return (
    <div className="stack">
      <p className="kicker">{project.code}</p>
      <div className="row-actions" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>{project.name}</h1>
        <span className={project.status === "published" ? "badge on" : "badge"}>{projectStatus(project.status)}</span>
      </div>
      <p>{project.description}</p>
      <p className="muted">
        {project.developer} · {project.city}
        {project.district} · 硬装参考 {project.hard_cost_per_m2} 元/㎡ · 软装参考 {project.soft_cost_per_m2} 元/㎡
      </p>
      <div className="row-actions">
        {project.status === "published" ? (
          <button className="secondary" type="button" onClick={() => publish("draft")}>
            撤回为草稿
          </button>
        ) : (
          <button type="button" onClick={() => publish("published")}>
            发布给客户
          </button>
        )}
        <Link className="btn secondary" href={`/admin/selections?project=${project.id}`}>
          本项目方案
        </Link>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}

      <h2>户型</h2>
      {project.unit_types.map((item) => (
        <article key={item.id} className="card">
          <strong>
            {item.name} · {item.summary}
          </strong>
          <p className="muted">
            建筑面积 {item.building_area_m2} ㎡ · 计价面积 {item.finish_area_m2} ㎡ · {item.area_note}
          </p>
          {item.rooms.length > 0 ? (
            <table className="room-table">
              <tbody>
                {item.rooms.map((room) => (
                  <tr key={room.id}>
                    <td>
                      {room.name}
                      {room.counts_toward_finish ? "" : "（不计）"}
                    </td>
                    <td>{room.area_m2} ㎡</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <h3>图纸</h3>
          {item.assets.length === 0 ? <p className="muted">还没有图纸。</p> : null}
          {item.assets.map((asset) => (
            <div key={asset.id} className="quote-line">
              <div>
                <strong>
                  {asset.kind_label} · {asset.filename}
                </strong>
                <span>
                  {asset.status === "stored" ? "已上传" : "占位"} · {asset.note}
                </span>
              </div>
              <div className="row-actions">
                <button
                  className="secondary"
                  type="button"
                  onClick={() => setUpload({ ...upload, replace_asset_id: asset.id, unit_type_id: item.id, kind: asset.kind })}
                >
                  替换
                </button>
                <button className="ghost" type="button" onClick={() => recognize(asset.id)}>
                  识别户型
                </button>
              </div>
            </div>
          ))}
        </article>
      ))}

      <form className="card stack" onSubmit={addUnit}>
        <strong>添加户型</strong>
        <div className="grid-2">
          <label className="field">
            编号
            <input value={unit.code} onChange={(event) => setUnit({ ...unit, code: event.target.value })} required />
          </label>
          <label className="field">
            名称
            <input value={unit.name} onChange={(event) => setUnit({ ...unit, name: event.target.value })} required />
          </label>
        </div>
        <div className="grid-2">
          <label className="field">
            建筑面积
            <input value={unit.building_area_m2} onChange={(event) => setUnit({ ...unit, building_area_m2: event.target.value })} required />
          </label>
          <label className="field">
            计价面积（可选）
            <input value={unit.finish_area_m2} onChange={(event) => setUnit({ ...unit, finish_area_m2: event.target.value })} />
          </label>
        </div>
        <label className="field">
          户型简述
          <input value={unit.summary} onChange={(event) => setUnit({ ...unit, summary: event.target.value })} />
        </label>
        <button type="submit">添加</button>
      </form>

      {token ? <ProjectBindings projectId={project.id} units={project.unit_types} token={token} /> : null}
      {token ? <PlanMarks projectId={project.id} units={project.unit_types} token={token} /> : null}

      <form className="card stack" onSubmit={sendFile}>
        <strong>上传图纸</strong>
        <p className="fine">支持 DWG、PDF、PNG、JPG、WEBP。可新建，也可替换上面的占位记录。</p>
        <label className="field">
          类型
          <select value={upload.kind} onChange={(event) => setUpload({ ...upload, kind: event.target.value })}>
            <option value="floor_plan">平面图</option>
            <option value="usage_drawing">用量图</option>
            <option value="render">效果图</option>
            <option value="other">其他</option>
          </select>
        </label>
        <label className="field">
          户型
          <select value={upload.unit_type_id} onChange={(event) => setUpload({ ...upload, unit_type_id: event.target.value })}>
            <option value="">不指定</option>
            {project.unit_types.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        {upload.replace_asset_id ? <p className="fine">将替换：{upload.replace_asset_id}</p> : null}
        <ChineseFile accept=".dwg,.pdf,.png,.jpg,.jpeg,.webp" onFile={(file) => setUpload({ ...upload, file })} />
        <button type="submit" disabled={!upload.file}>
          上传
        </button>
      </form>
    </div>
  );
}
