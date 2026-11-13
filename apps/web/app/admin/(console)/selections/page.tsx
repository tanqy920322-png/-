"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatWhen, selectionStatus, yuan } from "@/lib/money";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import type { SelectionListItem } from "@/lib/types";

export default function SelectionsPage() {
  const { token } = useToken(ADMIN_TOKEN);
  const [rows, setRows] = useState<SelectionListItem[]>([]);
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("project") || "";
    setProjectId(query);
  }, []);

  useEffect(() => {
    if (!token) return;
    const path = projectId ? `/api/admin/selections?project_id=${encodeURIComponent(projectId)}` : "/api/admin/selections";
    api<SelectionListItem[]>(path, { token }).then(setRows);
  }, [token, projectId]);

  return (
    <div>
      <h1>客户方案</h1>
      <p className="muted">一户一档从这里打开。演示客户 13800138000 的档案编号是 sel_demo。</p>
      <table className="data">
        <thead>
          <tr>
            <th>客户</th>
            <th>项目</th>
            <th>户型</th>
            <th>风格</th>
            <th>报价</th>
            <th>状态</th>
            <th>更新</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <tr key={item.id}>
              <td>
                {item.customer_name}
                <div className="fine">{item.customer_phone}</div>
              </td>
              <td>{item.project_code}</td>
              <td>{item.unit_name}</td>
              <td>{item.style_name || "未选"}</td>
              <td>{yuan(item.total)}</td>
              <td>{selectionStatus(item.status)}</td>
              <td>{formatWhen(item.updated_at)}</td>
              <td>
                <Link href={`/admin/selections/${item.id}`}>档案</Link>
                {" · "}
                <Link href={`/admin/selections/${item.id}/print`}>打印报价单</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
