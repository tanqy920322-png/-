"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, downloadFile } from "@/lib/api";
import { selectionStatus } from "@/lib/money";
import { CUSTOMER_TOKEN, useQueryParam, useToken } from "@/lib/session";
import { ChineseFile, PhoneHeader, QuoteLines, Steps } from "@/components/ui";
import type { AiJob, ExportTicket, Selection } from "@/lib/types";

const ScenePreview = dynamic(() => import("@/components/ScenePreview"), { ssr: false });

export default function SchemePage() {
  const router = useRouter();
  const sid = useQueryParam("sid");
  const { token, ready } = useToken(CUSTOMER_TOKEN);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && !token) router.replace("/c/login");
  }, [ready, token, router]);

  useEffect(() => {
    if (!token || !sid) return;
    api<Selection>(`/api/selections/${sid}`, { token })
      .then(setSelection)
      .catch((err) => setError(err instanceof ApiError ? err.message : "方案加载失败"));
  }, [token, sid]);

  async function submit() {
    if (!token || !sid) return;
    setBusy(true);
    setError("");
    try {
      setSelection(await api<Selection>(`/api/selections/${sid}/submit`, { method: "POST", token }));
      setNote("方案已提交，后台可以在一户一档里打开。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function exportKind(kind: "quote_pdf" | "image_pack") {
    if (!token || !sid) return;
    setBusy(true);
    setError("");
    try {
      const ticket = await api<ExportTicket>(`/api/selections/${sid}/exports`, {
        method: "POST",
        token,
        body: JSON.stringify({ kind }),
      });
      await downloadFile(`/api/exports/${ticket.id}/file`, token, ticket.filename);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "导出失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadFurniture(file: File | undefined) {
    if (!file || !token || !sid) return;
    setBusy(true);
    setError("");
    const body = new FormData();
    body.set("selection_id", sid);
    body.set("file", file);
    try {
      const job = await api<AiJob>("/api/ai/scene", { method: "POST", token, body });
      setNote(job.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <PhoneHeader title="我的方案" back={sid ? `/c/configure?sid=${sid}` : "/c/configure"} />
      <Steps current={4} />
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}
      {!selection?.style || !selection.ceiling || !selection.floor || !selection.wall ? (
        <p className="muted">这个方案还没选风格。</p>
      ) : (
        <>
          <p className="kicker">
            {selection.project.name} · {selection.unit.name} · {selectionStatus(selection.status)}
          </p>
          <h2 style={{ margin: 0 }}>
            {selection.style.name} · {selection.customer_name}
          </h2>
          <ScenePreview
            styleId={selection.style.id}
            ceiling={selection.ceiling.material}
            floor={selection.floor.material}
            wall={selection.wall.material}
          />
          <QuoteLines quote={selection.quote} />
          <table className="room-table">
            <tbody>
              {selection.unit.rooms.map((room) => (
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
          <div className="row-actions">
            <button type="button" disabled={busy} onClick={submit}>
              提交给开发商
            </button>
            <button className="secondary" type="button" disabled={busy} onClick={() => exportKind("quote_pdf")}>
              下载报价 PDF
            </button>
            <button className="secondary" type="button" disabled={busy} onClick={() => exportKind("image_pack")}>
              下载图册占位
            </button>
          </div>
          <label className="field">
            上传一张家具照片（场景生成占位）
            <ChineseFile accept="image/png,image/jpeg,image/webp" onFile={(file) => file && uploadFurniture(file)} />
          </label>
          <p className="fine">
            要在房间里看照片效果，请回到九类选配，用「用照片看效果」。那里的示意件不进报价。这一处仍只是收下照片，不会生成模型。
          </p>
          {(selection.substitutes || []).length ? (
            <p className="effect-banner">仅用于效果展示，不列入采购。外形接近、能看出来是同一类、同一款式方向。</p>
          ) : null}
        </>
      )}
    </div>
  );
}
