"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { CUSTOMER_TOKEN, useToken } from "@/lib/session";
import { PhoneHeader, Steps } from "@/components/ui";
import type { Project, Selection, SelectionListItem, UnitType } from "@/lib/types";

export default function MatchPage() {
  const router = useRouter();
  const { token, ready } = useToken(CUSTOMER_TOKEN);
  const [projects, setProjects] = useState<Project[]>([]);
  const [mine, setMine] = useState<SelectionListItem[]>([]);
  const [code, setCode] = useState("GZ2019-003");
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && !token) router.replace("/c/login");
  }, [ready, token, router]);

  useEffect(() => {
    if (!token) return;
    api<Project[]>("/api/projects").then((rows) => {
      setProjects(rows);
      if (rows[0]) setProject(rows[0]);
    });
    api<SelectionListItem[]>("/api/selections/mine", { token }).then(setMine).catch(() => setMine([]));
  }, [token]);

  async function lookup() {
    setError("");
    setBusy(true);
    try {
      const found = await api<Project>(`/api/projects/${encodeURIComponent(code.trim())}`);
      setProject(found);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有找到项目");
    } finally {
      setBusy(false);
    }
  }

  async function choose(unit: UnitType) {
    if (!token || !project) return;
    setBusy(true);
    setError("");
    try {
      const selection = await api<Selection>("/api/selections", {
        method: "POST",
        token,
        body: JSON.stringify({ project_code: project.code, unit_type_id: unit.id }),
      });
      router.push(selection.style ? `/c/configure?sid=${selection.id}` : `/c/style?sid=${selection.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "创建方案失败");
      setBusy(false);
    }
  }

  return (
    <div>
      <PhoneHeader title="选择项目" />
      <Steps current={1} />
      {mine.length > 0 ? (
        <div className="stack" style={{ marginBottom: 16 }}>
          <p className="muted">继续已有方案</p>
          {mine.map((item) => (
            <button key={item.id} className="choice" type="button" onClick={() => router.push(`/c/configure?sid=${item.id}`)}>
              <strong>
                {item.project_name} · {item.unit_name}
              </strong>
              <span className="muted">
                {item.style_name || "尚未选风格"} · {item.status === "submitted" ? "已提交" : "选配中"}
              </span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="stack">
        <label className="field">
          项目编号
          <input value={code} onChange={(event) => setCode(event.target.value)} />
        </label>
        <button className="secondary" type="button" disabled={busy} onClick={lookup}>
          查找项目
        </button>
        {error ? <p className="error">{error}</p> : null}
        {project ? (
          <article className="card">
            <p className="kicker">{project.developer}</p>
            <h2 style={{ margin: "4px 0" }}>{project.name}</h2>
            <p className="muted">
              {project.city}
              {project.district} · {project.code}
            </p>
            <p>{project.description}</p>
          </article>
        ) : null}
        {project?.unit_types.map((unit) => (
          <button key={unit.id} className="choice" type="button" disabled={busy} onClick={() => choose(unit)}>
            <strong>
              {unit.name} · {unit.summary}
            </strong>
            <span className="muted">
              建筑面积 {unit.building_area_m2} ㎡ · 部位计价 {unit.finish_area_m2} ㎡
            </span>
          </button>
        ))}
        {projects.length === 0 ? <p className="muted">还没有已发布的项目。</p> : null}
      </div>
    </div>
  );
}
