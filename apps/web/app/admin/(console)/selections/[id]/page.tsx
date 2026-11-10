"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, downloadFile } from "@/lib/api";
import { formatWhen, selectionStatus } from "@/lib/money";
import { ADMIN_TOKEN, useToken } from "@/lib/session";
import { QuoteLines } from "@/components/ui";
import type { ExportTicket, Selection } from "@/lib/types";

const ScenePreview = dynamic(() => import("@/components/ScenePreview"), { ssr: false });

export default function HouseholdPage() {
  const params = useParams<{ id: string }>();
  const { token } = useToken(ADMIN_TOKEN);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    api<Selection>(`/api/selections/${params.id}`, { token })
      .then(setSelection)
      .catch((err) => setError(err instanceof ApiError ? err.message : "档案不存在"));
  }, [token, params.id]);

  async function exportKind(kind: "quote_pdf" | "image_pack") {
    if (!token || !selection) return;
    const ticket = await api<ExportTicket>(`/api/selections/${selection.id}/exports`, {
      method: "POST",
      token,
      body: JSON.stringify({ kind }),
    });
    await downloadFile(`/api/exports/${ticket.id}/file`, token, ticket.filename);
  }

  if (!selection) return <p className="muted">{error || "正在打开档案…"}</p>;

  return (
    <div className="stack">
      <p className="kicker">一户一档 · {selection.id}</p>
      <h1 style={{ marginBottom: 0 }}>
        {selection.customer_name} · {selection.unit.name}
      </h1>
      <p className="muted">
        {selection.customer_phone} · {selection.project.name}（{selection.project.code}）· {selectionStatus(selection.status)} ·
        更新于 {formatWhen(selection.updated_at)}
      </p>
      <p>
        <Link href={`/admin/projects/${selection.project.id}`}>回到项目</Link>
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="grid-2">
        <div className="stack">
          {selection.style && selection.ceiling && selection.floor && selection.wall ? (
            <ScenePreview
              styleId={selection.style.id}
              ceiling={selection.ceiling.material}
              floor={selection.floor.material}
              wall={selection.wall.material}
            />
          ) : (
            <p className="card">客户还没有选定风格。</p>
          )}
          <article className="card">
            <strong>当前选择</strong>
            <p>风格：{selection.style?.name || "未选"}</p>
            <p>天花：{selection.ceiling?.name || "未选"}</p>
            <p>地面：{selection.floor?.name || "未选"}</p>
            <p>墙面：{selection.wall?.name || "未选"}</p>
            {(selection.lines || [])
              .filter((line) => !["ceiling", "floor", "wall"].includes(line.part_id))
              .map((line) => (
                <p key={line.id}>
                  {line.part_name}：{line.scheme_name || "未选"}
                  {line.brand_tier === "import" ? "（进口）" : line.brand_tier === "domestic" ? "（国产）" : ""}
                </p>
              ))}
            <h2 style={{ fontSize: 16 }}>房间 × 件数</h2>
            <table className="data">
              <thead>
                <tr>
                  <th>房间</th>
                  <th>件</th>
                  <th>要不要</th>
                  <th>数量</th>
                  <th>品牌</th>
                </tr>
              </thead>
              <tbody>
                {(selection.lines || []).flatMap((line) =>
                  (line.picks || []).map((pick) => (
                    <tr key={pick.id}>
                      <td>{pick.room_name || "整户"}</td>
                      <td>{pick.group_label || pick.name}</td>
                      <td>{pick.included ? "要" : "不要"}</td>
                      <td>{pick.quantity}</td>
                      <td>{pick.brand_tier === "import" ? "进口" : "国产"}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </article>
        </div>
        <div className="stack">
          <article className="card">
            <QuoteLines quote={selection.quote} />
          </article>
          <div className="row-actions">
            <button type="button" onClick={() => exportKind("quote_pdf").catch((err) => setError(err.message))}>
              下载报价 PDF
            </button>
            <button className="secondary" type="button" onClick={() => exportKind("image_pack").catch((err) => setError(err.message))}>
              下载图册占位
            </button>
          </div>
        </div>
      </div>
      <h2>分房面积</h2>
      <table className="data">
        <tbody>
          {selection.unit.rooms.map((room) => (
            <tr key={room.id}>
              <td>{room.name}</td>
              <td>{room.area_m2} ㎡</td>
              <td>{room.counts_toward_finish ? "计入部位报价" : "不计入"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>相关文件</h2>
      <table className="data">
        <thead>
          <tr>
            <th>类型</th>
            <th>文件</th>
            <th>状态</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {selection.unit.assets.map((asset) => (
            <tr key={asset.id}>
              <td>{asset.kind_label}</td>
              <td>{asset.filename}</td>
              <td>{asset.status === "stored" ? "已上传" : "占位"}</td>
              <td>{asset.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
