"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { CatalogProduct, ProjectBinding, UnitType } from "@/lib/types";

const PARTS = [
  ["ceiling", "天花"],
  ["wall", "墙面"],
  ["floor", "地面"],
  ["cabinetry", "全屋定制"],
  ["sanitary", "洁具"],
  ["entry_door", "入户门"],
  ["kitchen_appliance", "厨房电器"],
  ["lighting", "灯具"],
  ["switch_socket", "开关插座"],
];

export default function ProjectBindings({
  projectId,
  units,
  token,
}: {
  projectId: string;
  units: UnitType[];
  token: string;
}) {
  const [bindings, setBindings] = useState<ProjectBinding[]>([]);
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [form, setForm] = useState({ unit_type_id: units[0]?.id || "", room_name: units[0]?.rooms[0]?.name || "", part_id: "ceiling", product_id: "" });
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  async function reload() {
    setBindings(await api<ProjectBinding[]>(`/api/projects/${projectId}/bindings`, { token }));
  }

  useEffect(() => {
    reload().catch((err) => setError(err.message));
  }, [projectId, token]);

  useEffect(() => {
    api<CatalogProduct[]>(`/api/products?part_id=${form.part_id}`, { token })
      .then((rows) => {
        setProducts(rows);
        setForm((current) => ({ ...current, product_id: rows[0]?.id || "" }));
      })
      .catch((err) => setError(err.message));
  }, [form.part_id, token]);

  const unit = units.find((item) => item.id === form.unit_type_id);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/api/admin/projects/${projectId}/bindings`, {
        method: "POST",
        token,
        body: JSON.stringify(form),
      });
      setNote("已挂到这个项目。客户选到对应房间时能看到这张示例图和价格。");
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有挂上");
    }
  }

  return (
    <section className="stack">
      <h2>部位挂品</h2>
      <p className="fine">在房间清单里把天花、墙面、地面或其他品类，绑到产品库里已经确认的示例型号。这不是在效果图上描点，房间名字来自户型。</p>
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}
      {bindings.length ? (
        <table className="data">
          <tbody>
            {bindings.map((row) => (
              <tr key={row.id}>
                <td>{row.room_name || "整户"}</td>
                <td>{PARTS.find((item) => item[0] === row.part_id)?.[1] || row.part_id}</td>
                <td>{row.product_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">还没有挂品。</p>
      )}
      <form className="card stack" onSubmit={save}>
        <label className="field">
          户型
          <select value={form.unit_type_id} onChange={(event) => setForm({ ...form, unit_type_id: event.target.value, room_name: "" })}>
            {units.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          房间
          <select value={form.room_name} onChange={(event) => setForm({ ...form, room_name: event.target.value })}>
            <option value="">整户</option>
            {(unit?.rooms || []).map((room) => (
              <option key={room.id} value={room.name}>
                {room.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          部位
          <select value={form.part_id} onChange={(event) => setForm({ ...form, part_id: event.target.value })}>
            {PARTS.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          示例产品
          <select value={form.product_id} onChange={(event) => setForm({ ...form, product_id: event.target.value })}>
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.brand} {item.name} · 国产 {item.domestic_price} / 进口 {item.import_price}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!form.product_id}>
          挂到项目
        </button>
      </form>
    </section>
  );
}
