"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import type { Project } from "@/lib/types";

export default function NewProjectPage() {
  const router = useRouter();
  const { token } = useToken(ADMIN_TOKEN);
  const [form, setForm] = useState({
    code: "",
    name: "",
    developer: "",
    city: "",
    district: "",
    address: "",
    description: "",
    hard_cost_per_m2: "2500",
    soft_cost_per_m2: "3500",
    publish: false,
  });
  const [error, setError] = useState("");

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError("");
    try {
      const project = await api<Project>("/api/admin/projects", {
        method: "POST",
        token,
        body: JSON.stringify({
          ...form,
          hard_cost_per_m2: Number(form.hard_cost_per_m2),
          soft_cost_per_m2: Number(form.soft_cost_per_m2),
        }),
      });
      router.push(`/admin/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "创建失败");
    }
  }

  return (
    <div>
      <h1>新建项目</h1>
      <form className="stack" onSubmit={submit} style={{ maxWidth: 640 }}>
        <label className="field">
          项目编号
          <input value={form.code} onChange={(event) => set("code", event.target.value)} required />
        </label>
        <label className="field">
          项目名称
          <input value={form.name} onChange={(event) => set("name", event.target.value)} required />
        </label>
        <label className="field">
          开发商
          <input value={form.developer} onChange={(event) => set("developer", event.target.value)} />
        </label>
        <div className="grid-2">
          <label className="field">
            城市
            <input value={form.city} onChange={(event) => set("city", event.target.value)} />
          </label>
          <label className="field">
            区县
            <input value={form.district} onChange={(event) => set("district", event.target.value)} />
          </label>
        </div>
        <label className="field">
          地址
          <input value={form.address} onChange={(event) => set("address", event.target.value)} />
        </label>
        <label className="field">
          简介
          <textarea rows={4} value={form.description} onChange={(event) => set("description", event.target.value)} />
        </label>
        <div className="grid-2">
          <label className="field">
            硬装参考单价（元/㎡）
            <input value={form.hard_cost_per_m2} onChange={(event) => set("hard_cost_per_m2", event.target.value)} />
          </label>
          <label className="field">
            软装参考单价（元/㎡）
            <input value={form.soft_cost_per_m2} onChange={(event) => set("soft_cost_per_m2", event.target.value)} />
          </label>
        </div>
        <label>
          <input type="checkbox" checked={form.publish} onChange={(event) => set("publish", event.target.checked)} /> 创建后直接发布
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">保存项目</button>
      </form>
    </div>
  );
}
