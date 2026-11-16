"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ChineseFile } from "@/components/ui";

const PARTS: Array<[string, string]> = [
  ["", "图册未指定单一品类"],
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

type StartResult = {
  status: string;
  message: string;
  paid_api_called: boolean;
  postpaid_enabled: boolean;
  free_pack_exhausted: boolean;
};

export function GenerationDesk({ token, onStarted }: { token: string | null; onStarted?: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [partId, setPartId] = useState("");
  const [brand, setBrand] = useState("");
  const [modelCode, setModelCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<StartResult | null>(null);
  const [pending, setPending] = useState(false);

  async function start() {
    if (!token || !file) {
      setError("请先选择图册或产品图。");
      return;
    }
    const body = new FormData();
    body.set("file", file);
    body.set("part_id", partId);
    body.set("brand", brand);
    body.set("model_code", modelCode);
    body.set("name", name);
    setPending(true);
    setError("");
    setResult(null);
    try {
      const started = await api<StartResult>("/api/admin/generation/start", { method: "POST", token, body });
      setResult(started);
      onStarted?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "生模入口没有走通");
    } finally {
      setPending(false);
    }
  }

  return (
    <section id="generation" className="card stack">
      <h2>生模入口</h2>
      <p className="effect-banner">
        设计师上传图册或产品图后，从这里发起生模。免费资源包已经用尽，后付费没有开通。发起后会停在额度不足，不会生成新网格。没有调用付费接口，也不能开通后付费、购买积分包、充值或绑定支付。
      </p>
      <ChineseFile
        accept=".pdf,.zip,.png,.jpg,.jpeg,.webp,application/pdf,application/zip,image/png,image/jpeg,image/webp"
        onFile={setFile}
      />
      <label className="field">
        品类
        <select value={partId} onChange={(event) => setPartId(event.target.value)}>
          {PARTS.map(([value, label]) => (
            <option key={value || "any"} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        品牌（可空）
        <input value={brand} onChange={(event) => setBrand(event.target.value)} />
      </label>
      <label className="field">
        型号（可空）
        <input value={modelCode} onChange={(event) => setModelCode(event.target.value)} />
      </label>
      <label className="field">
        名称（可空）
        <input value={name} onChange={(event) => setName(event.target.value)} />
      </label>
      <button type="button" disabled={pending} onClick={() => start()}>
        {pending ? "正在记下这次发起…" : "发起生模"}
      </button>
      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <div className="effect-banner">
          <strong>停在额度不足</strong>
          <p>{result.message}</p>
          <p className="fine">
            状态：{result.status}。没有调用付费接口（paid_api_called 为 {result.paid_api_called ? "true" : "false"}）。
            后付费{result.postpaid_enabled ? "已开通" : "未开通"}。
            {result.free_pack_exhausted ? "免费资源包已用尽。" : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
