import Link from "next/link";
import type { Quote } from "@/lib/types";
import { yuan } from "@/lib/money";

export function Steps({ current }: { current: number }) {
  const items = ["项目", "风格", "部位", "方案"];
  return (
    <ol className="steps">
      {items.map((label, index) => (
        <li key={label} className={index + 1 === current ? "on" : index + 1 < current ? "done" : ""}>
          <span>{index + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  );
}

export function PhoneHeader({ title, back }: { title: string; back?: string }) {
  return (
    <header className="phone-bar">
      {back ? (
        <Link href={back} className="back">
          返回
        </Link>
      ) : (
        <span />
      )}
      <h1>{title}</h1>
      <span />
    </header>
  );
}

export function QuoteLines({ quote }: { quote: Quote }) {
  return (
    <div className="quote-lines">
      <p className="muted">{quote.area_note}</p>
      {quote.lines.length === 0 ? <p>选定风格后，这里会按方案 1 算出第一版报价。</p> : null}
      {quote.lines.map((line) => (
        <div className="quote-line" key={line.part_id}>
          <div>
            <strong>{line.part_name}</strong>
            <span>{line.scheme_name || "未选"}</span>
          </div>
          <div className="nums">
            <span>
              {line.unit_price ?? "—"} 元/㎡ × {quote.finish_area_m2} ㎡
            </span>
            <b>{yuan(line.amount)}</b>
          </div>
        </div>
      ))}
      <div className="quote-total-row">
        <span>部位合计</span>
        <strong>{yuan(quote.total)}</strong>
      </div>
      <p className="fine">
        样板房参考：硬装 {yuan(quote.reference.hard_cost_per_m2)}/㎡，软装 {yuan(quote.reference.soft_cost_per_m2)}
        /㎡，按建筑面积 {quote.reference.building_area_m2} ㎡估算，不计入上面的合计。
      </p>
    </div>
  );
}
