"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { yuan } from "@/lib/money";
import { useToken } from "@/lib/session";
import type { TakeoffLine, TakeoffSheet } from "@/lib/types";

function qty(value: number | null): string {
  if (value == null) return "";
  return value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function price(value: number | null): string {
  if (value == null) return "";
  return yuan(value);
}

function LineTable({ lines }: { lines: TakeoffLine[] }) {
  return (
    <table className="quote-table">
      <thead>
        <tr>
          <th>序号</th>
          <th>项目</th>
          <th>单位</th>
          <th>数量</th>
          <th>品牌型号/工艺</th>
          <th>单价</th>
          <th>合价</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line, index) => (
          <tr key={`${line.seq || index}-${line.item}`}>
            <td>{line.seq || index + 1}</td>
            <td>{line.item}</td>
            <td>{line.unit}</td>
            <td>{qty(line.quantity)}</td>
            <td>{line.craft}</td>
            <td>{price(line.unit_price)}</td>
            <td>{price(line.amount)}</td>
            <td>{line.remark}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function QuotePrintLoader({
  tokenKey,
  selectionId,
  loginHref,
}: {
  tokenKey: string;
  selectionId: string;
  loginHref: string;
}) {
  const { token, ready } = useToken(tokenKey);
  const [sheet, setSheet] = useState<TakeoffSheet | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready || !token || !selectionId) return;
    api<TakeoffSheet>(`/api/selections/${selectionId}/takeoff`, { token })
      .then(setSheet)
      .catch((err) => setError(err instanceof ApiError ? err.message : "报价单没有打开"));
  }, [ready, token, selectionId]);

  if (!ready) return <p className="muted">正在打开报价单…</p>;
  if (!token) {
    return (
      <p className="muted">
        请先登录，再打开打印报价单。<Link href={loginHref}>去登录</Link>
      </p>
    );
  }
  if (!selectionId) return <p className="muted">缺少档案编号。</p>;
  if (error) return <p className="error">{error}</p>;
  if (!sheet) return <p className="muted">正在整理报价单…</p>;

  const total = sheet.selection_quote?.total;

  return (
    <div className="quote-sheet">
      <div className="no-print row-actions">
        <button type="button" onClick={() => window.print()}>
          打印
        </button>
        <Link className="btn secondary" href={loginHref.startsWith("/admin") ? `/admin/selections/${selectionId}` : `/c/scheme?sid=${selectionId}`}>
          返回
        </Link>
      </div>
      <p className="quote-brand">{sheet.institution}</p>
      <h1>{sheet.title}</h1>
      <p className="quote-meta">
        {sheet.project_name}（{sheet.project_code}） · {sheet.unit_name} · {sheet.style_name || "未选风格"}
        <br />
        {sheet.customer_name} {sheet.customer_phone} · 档案 {sheet.selection_id}
      </p>
      <p>{sheet.selection_note}</p>
      <p className="quote-total">
        部位合计 <strong>{yuan(total)}</strong>
      </p>
      <p className="fine">{sheet.selection_quote?.area_note}</p>
      <p>{sheet.geometry_note}</p>
      <p className="fine">{sheet.mapping.honesty}</p>
      {sheet.sections.map((section) => (
        <section key={section.id}>
          <h2>{section.title}</h2>
          <LineTable lines={section.lines} />
          <p className="fine">
            {section.lines.some((line) => line.priced) ? `本段小计 ${yuan(section.subtotal)}` : "本段没有计入小计的金额。"}
          </p>
        </section>
      ))}
      <section>
        <h2>以下不包含</h2>
        <LineTable lines={sheet.exclusions.map((line, index) => ({ ...line, seq: index + 1 }))} />
        <p className="fine">水电改造、人工、管理费、税金这四行是不含。它们不进算量小计，也不进部位合计。</p>
      </section>
      {sheet.unpriced.length ? (
        <section>
          <h2>不计价</h2>
          <ul>
            {sheet.unpriced.map((row) => (
              <li key={`${row.item}-${row.remark}`}>
                {row.item} · {row.remark}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <p className="quote-total">
        算量小计 <strong>{yuan(sheet.part_subtotal)}</strong>
      </p>
      <p className="fine">算量小计只加已算出数量、并且写了单价的行。数量留空、按米未计价、安装工费和「不含」都不加进去。</p>
      <h2>量法</h2>
      <ol>
        {sheet.rules.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ol>
    </div>
  );
}
