import Link from "next/link";
import { useState } from "react";
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

export function PhoneHeader({ title, back, onBack }: { title: string; back?: string; onBack?: () => void }) {
  return (
    <header className="phone-bar">
      {back ? (
        <Link href={back} className="back">
          返回
        </Link>
      ) : onBack ? (
        <button type="button" className="ghost" onClick={onBack}>
          返回
        </button>
      ) : (
        <span />
      )}
      <h1>{title}</h1>
      <span />
    </header>
  );
}

export function ChineseFile({
  accept,
  name,
  required,
  onFile,
}: {
  accept: string;
  name?: string;
  required?: boolean;
  onFile?: (file: File | null) => void;
}) {
  const [filename, setFilename] = useState("");
  return (
    <div className="file-pick">
      <label className="secondary">
        选择文件
        <input
          name={name}
          type="file"
          accept={accept}
          required={required}
          onChange={(event) => {
            const file = event.target.files?.[0] || null;
            setFilename(file?.name || "");
            onFile?.(file);
          }}
        />
      </label>
      <span>{filename || "尚未选择文件"}</span>
    </div>
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
              {line.pricing === "each"
                ? `${line.unit_price ?? "—"} 元 × ${line.quantity ?? 1}${line.brand_tier === "import" ? " · 进口" : line.brand_tier === "domestic" ? " · 国产" : ""}`
                : `${line.unit_price ?? "—"} 元/㎡ × ${quote.finish_area_m2} ㎡`}
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
