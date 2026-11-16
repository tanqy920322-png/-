"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatWhen, selectionStatus, yuan } from "@/lib/money";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import type { Overview } from "@/lib/types";

export default function AdminHomePage() {
  const { token } = useToken(ADMIN_TOKEN);
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    api<Overview>("/api/admin/overview", { token })
      .then(setData)
      .catch((err) => setError(err.message));
  }, [token]);

  return (
    <div>
      <h1>概览</h1>
      <p className="muted">试点项目、客户方案和集采价表都从这里进。</p>
      <p className="fine">
        设计师工具：在 <Link href="/admin/library#generation">产品库</Link> 上传图册或产品图可以发起生模。
        <Link href="/admin/samples">内部样板</Link> 里能看到已确认的 5 件生成件。免费额度已用尽，后付费未开通，新的发起会停住，不会调用付费接口。
      </p>
      {error ? <p className="error">{error}</p> : null}
      {data ? (
        <>
          <div className="stats">
            <div className="stat">
              <b>{data.projects}</b>项目
            </div>
            <div className="stat">
              <b>{data.published_projects}</b>已发布
            </div>
            <div className="stat">
              <b>{data.selections}</b>客户方案
            </div>
            <div className="stat">
              <b>{data.placeholder_drawings}</b>图纸占位
            </div>
          </div>
          <h2>最近方案</h2>
          <table className="data">
            <thead>
              <tr>
                <th>客户</th>
                <th>项目 / 户型</th>
                <th>风格</th>
                <th>报价</th>
                <th>状态</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.recent_selections.map((item) => (
                <tr key={item.id}>
                  <td>{item.customer_phone}</td>
                  <td>
                    {item.project_name} · {item.unit_name}
                  </td>
                  <td>{item.style_name || "未选"}</td>
                  <td>{yuan(item.total)}</td>
                  <td>{selectionStatus(item.status)}</td>
                  <td>
                    <Link href={`/admin/selections/${item.id}`}>打开档案</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="fine">更新时间示例：{data.recent_selections[0] ? formatWhen(data.recent_selections[0].updated_at) : "—"}</p>
        </>
      ) : (
        <p className="muted">正在读取…</p>
      )}
    </div>
  );
}
