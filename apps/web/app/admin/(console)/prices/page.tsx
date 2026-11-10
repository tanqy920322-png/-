"use client";

import { useEffect, useState } from "react";
import { api, ApiError, downloadFile } from "@/lib/api";
import { ChineseFile } from "@/components/ui";
import { yuan } from "@/lib/money";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import type { Meta, ProcurementTable, Project } from "@/lib/types";

export default function PricesPage() {
  const { token } = useToken(ADMIN_TOKEN);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tables, setTables] = useState<ProcurementTable[]>([]);
  const [open, setOpen] = useState<ProcurementTable | null>(null);
  const [category, setCategory] = useState("sanitary");
  const [projectId, setProjectId] = useState("gz2019-003");
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  async function load(auth: string) {
    const [nextMeta, nextProjects, nextTables] = await Promise.all([
      api<Meta>("/api/meta"),
      api<Project[]>("/api/admin/projects", { token: auth }),
      api<ProcurementTable[]>("/api/admin/procurement/tables", { token: auth }),
    ]);
    setMeta(nextMeta);
    setProjects(nextProjects);
    setTables(nextTables);
  }

  useEffect(() => {
    if (!token) return;
    load(token).catch((err) => setError(err.message));
  }, [token]);

  async function importFile(file: File | undefined) {
    if (!file || !token) return;
    const body = new FormData();
    body.set("file", file);
    body.set("category", category);
    body.set("title", title || file.name);
    if (projectId) body.set("project_id", projectId);
    setError("");
    try {
      const created = await api<ProcurementTable>("/api/admin/procurement/import", { method: "POST", token, body });
      setOpen(created);
      await load(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "导入失败");
    }
  }

  return (
    <div className="stack">
      <h1>集采价表</h1>
      <p className="muted">
        价表品类与九类选配对齐：天花、墙面、地面、全屋定制、洁具、入户门、厨房电器、灯具、开关插座。
        表内「品类」列可以覆盖整表品类。客户报价仍来自所选方案，不自动读取集采价。
      </p>
      {error ? <p className="error">{error}</p> : null}
      <form
        className="card stack"
        onSubmit={(event) => {
          event.preventDefault();
          const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement;
          importFile(input.files?.[0]);
        }}
      >
        <label className="field">
          品类
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {(meta?.procurement_categories || [{ id: "sanitary", name: "洁具" }]).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          关联项目
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">不关联</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          标题
          <input value={title} placeholder="可留空，默认用文件名" onChange={(event) => setTitle(event.target.value)} />
        </label>
        <ChineseFile name="file" accept=".csv,.xlsx" required />
        <div className="row-actions">
          <button type="submit">导入 CSV / Excel</button>
          <button
            className="secondary"
            type="button"
            onClick={() => token && downloadFile("/api/admin/procurement/sample.csv", token, "sample_sanitary.csv")}
          >
            下载示例洁具表
          </button>
        </div>
      </form>
      <table className="data">
        <thead>
          <tr>
            <th>标题</th>
            <th>品类</th>
            <th>行数</th>
            <th>文件</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tables.map((table) => (
            <tr key={table.id}>
              <td>{table.title}</td>
              <td>{table.category_label}</td>
              <td>{table.row_count}</td>
              <td>{table.original_filename}</td>
              <td>
                <button
                  className="ghost"
                  type="button"
                  onClick={() => token && api<ProcurementTable>(`/api/admin/procurement/tables/${table.id}`, { token }).then(setOpen)}
                >
                  查看
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {open?.items ? (
        <table className="data">
          <thead>
            <tr>
              <th>SKU</th>
              <th>名称</th>
              <th>规格</th>
              <th>单位</th>
              <th>单价</th>
            </tr>
          </thead>
          <tbody>
            {open.items.map((item) => (
              <tr key={item.id}>
                <td>{item.sku_code}</td>
                <td>{item.name}</td>
                <td>{item.spec}</td>
                <td>{item.unit}</td>
                <td>{yuan(item.unit_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
