"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE, api, ApiError } from "@/lib/api";
import { ChineseFile } from "@/components/ui";
import type { PlanView, UnitType } from "@/lib/types";

type Requirements = {
  title: string;
  intro: string;
  items: string[];
  not_this_round: string;
  how_it_places: string;
};

const PARTS = [
  { id: "floor", name: "地面", slot: "地面" },
  { id: "wall", name: "墙面", slot: "墙面" },
  { id: "ceiling", name: "天花", slot: "天花" },
  { id: "sanitary", name: "洁具", slot: "马桶" },
  { id: "sofa", name: "软装沙发", slot: "沙发" },
  { id: "switch_socket", name: "开关插座", slot: "开关插座" },
  { id: "lighting", name: "灯具", slot: "灯具" },
  { id: "entry_door", name: "入户门", slot: "入户门" },
  { id: "cabinetry", name: "全屋定制", slot: "柜体" },
  { id: "kitchen_appliance", name: "厨房电器", slot: "厨电" },
];

function dotStyle(x: number, y: number): React.CSSProperties {
  const cx = Math.min(0.96, Math.max(0.04, x));
  const cy = Math.min(0.96, Math.max(0.05, y));
  let transform = "translate(-50%, -120%)";
  if (x > 0.8) transform = "translate(-100%, -120%)";
  else if (x < 0.14) transform = "translate(0, -120%)";
  return { left: `${cx * 100}%`, top: `${cy * 100}%`, transform };
}

function PlanCanvas({ vectors }: { vectors: number[][][] }) {
  const width = 1000;
  const height = 640;
  const lines = vectors
    .map((line) =>
      line
        .map(([x, y]) => `${x * width},${y * height}`)
        .join(" "),
    )
    .filter(Boolean);
  return (
    <svg className="plan-canvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="抽出的墙线">
      <rect width={width} height={height} fill="#f6f1ea" />
      {lines.map((points, index) => (
        <polyline key={index} points={points} fill="none" stroke="#2c2924" strokeWidth="6" />
      ))}
    </svg>
  );
}

export default function PlanMarks({
  projectId,
  units,
  token,
}: {
  projectId: string;
  units: UnitType[];
  token: string;
}) {
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [plans, setPlans] = useState<PlanView[]>([]);
  const [unitId, setUnitId] = useState(units.find((item) => item.code === "A")?.id || units[0]?.id || "");
  const [planId, setPlanId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [pending, setPending] = useState<{ x: number; y: number } | null>(null);
  const [scaleText, setScaleText] = useState("");
  const [heightText, setHeightText] = useState("");
  const [room, setRoom] = useState("客厅");
  const [partId, setPartId] = useState("sanitary");
  const [slot, setSlot] = useState("马桶");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const unit = units.find((item) => item.id === unitId);
  const unitPlans = plans.filter((item) => item.unit_type_id === unitId);
  const plan = unitPlans.find((item) => item.id === planId) || unitPlans.find((item) => item.active) || unitPlans[0];

  async function reload() {
    const rows = await api<PlanView[]>(`/api/admin/projects/${projectId}/plans`, { token });
    setPlans(rows);
  }

  useEffect(() => {
    api<Requirements>("/api/admin/delivery-requirements", { token })
      .then(setRequirements)
      .catch((err) => setError(err instanceof ApiError ? err.message : "交付要求没有读到"));
    reload().catch((err) => setError(err instanceof ApiError ? err.message : "简化平面没有读到"));
    // token and project are stable for this page
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, token]);

  useEffect(() => {
    setScaleText(plan?.scale_m_per_unit == null ? "" : String(plan.scale_m_per_unit));
    setHeightText(plan?.wall_height_m == null ? "" : String(plan.wall_height_m));
  }, [plan?.id, plan?.scale_m_per_unit, plan?.wall_height_m]);

  useEffect(() => {
    if (!plan) return;
    setPlanId(plan.id);
    const names = unit?.rooms.map((item) => item.name) || [];
    setRoom((current) => (names.includes(current) ? current : names.includes("客厅") ? "客厅" : names[0] || "客厅"));
  }, [plan?.id, unit?.id, unit?.rooms]);

  useEffect(() => {
    if (!plan || plan.media === "pdf" || plan.media === "dxf") {
      setPreview("");
      return;
    }
    let url = "";
    let stop = false;
    fetch(`${API_BASE}${plan.preview_path}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => (response.ok ? response.blob() : Promise.reject(new Error("底图没有打开"))))
      .then((blob) => {
        if (stop) return;
        url = URL.createObjectURL(blob);
        setPreview(url);
      })
      .catch(() => {
        if (!stop) setPreview("");
      });
    return () => {
      stop = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [plan?.id, plan?.media, plan?.preview_path, token]);

  const placed = useMemo(() => plan?.marks || [], [plan]);

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file || !unitId) return;
    const body = new FormData();
    body.set("file", file);
    body.set("unit_type_id", unitId);
    setBusy(true);
    setError("");
    try {
      const saved = await api<PlanView>(`/api/admin/projects/${projectId}/plans`, { method: "POST", token, body });
      await reload();
      setPlanId(saved.id);
      setNote(saved.note || "简化平面已保存。请在图上点选。");
      setFile(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function activate() {
    if (!plan) return;
    setBusy(true);
    try {
      await api(`/api/admin/projects/${projectId}/plans/${plan.id}/activate`, { method: "POST", token });
      await reload();
      setNote("客户房间会按这张图上的点摆放。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有切换");
    } finally {
      setBusy(false);
    }
  }

  async function saveMeasure(event: React.FormEvent) {
    event.preventDefault();
    if (!plan) return;
    const scale = scaleText.trim() === "" ? null : Number(scaleText);
    const height = heightText.trim() === "" ? null : Number(heightText);
    if (scale != null && !(scale > 0)) {
      setError("比例要大于 0。图纸没写就留空，不要填估计值。");
      return;
    }
    if (height != null && !(height > 0)) {
      setError("层高要大于 0。图纸没写就留空，不要填估计值。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const saved = await api<PlanView>(`/api/admin/projects/${projectId}/plans/${plan.id}/measure`, {
        method: "PUT",
        token,
        body: JSON.stringify({ scale_m_per_unit: scale, wall_height_m: height }),
      });
      setPlans((current) => current.map((item) => (item.id === saved.id ? { ...saved, preview_path: item.preview_path } : item)));
      setNote("已记下这张图上的比例和层高。没填的项仍然留空，打印时不会估一个数。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有记下比例");
    } finally {
      setBusy(false);
    }
  }

  async function saveMark() {
    if (!plan || !pending) {
      setError("请先在图上点一个位置");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const saved = await api<PlanView>(`/api/admin/projects/${projectId}/plans/${plan.id}/marks`, {
        method: "POST",
        token,
        body: JSON.stringify({
          room_name: room,
          part_id: partId,
          slot_label: slot,
          x: Math.round(pending.x * 10000) / 10000,
          y: Math.round(pending.y * 10000) / 10000,
        }),
      });
      setPlans((current) => current.map((item) => (item.id === saved.id ? { ...saved, preview_path: item.preview_path } : item)));
      setPending(null);
      setNote("已记下这个点。下面会按已挂的产品或材料摆上。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有记下这个点");
    } finally {
      setBusy(false);
    }
  }

  async function removeMark(markId: string) {
    if (!plan) return;
    const saved = await api<PlanView>(`/api/admin/projects/${projectId}/plans/${plan.id}/marks/${markId}`, {
      method: "DELETE",
      token,
    });
    setPlans((current) => current.map((item) => (item.id === saved.id ? { ...saved, preview_path: item.preview_path } : item)));
  }

  return (
    <section className="stack" id="plan-marks">
      <h2>施工图落位</h2>
      {requirements ? (
        <article className="card stack">
          <strong>{requirements.title}</strong>
          <p>{requirements.intro}</p>
          <ol className="req-list">
            {requirements.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
          <p className="fine">{requirements.not_this_round}</p>
          <p className="fine">{requirements.how_it_places}</p>
        </article>
      ) : null}
      <p className="fine">户型图上的「识别户型」仍然不读图。这里是人点、系统摆，不是自动识别施工图。</p>
      {error ? <p className="error">{error}</p> : null}
      {note ? <p className="ok">{note}</p> : null}
      <form className="card stack" onSubmit={upload}>
        <strong>上传简化平面</strong>
        <label className="field">
          户型
          <select value={unitId} onChange={(event) => setUnitId(event.target.value)}>
            {units.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <ChineseFile accept=".pdf,.png,.jpg,.jpeg,.webp,.svg,.dxf" onFile={setFile} />
        <button type="submit" disabled={busy || !file}>
          上传
        </button>
      </form>
      {unitPlans.length > 1 ? (
        <label className="field">
          选用哪张图
          <select value={plan?.id || ""} onChange={(event) => setPlanId(event.target.value)}>
            {unitPlans.map((item) => (
              <option key={item.id} value={item.id}>
                {item.filename}
                {item.active ? " · 当前用于摆放" : ""}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {plan ? (
        <article className="card stack">
          <div className="row-actions" style={{ justifyContent: "space-between" }}>
            <strong>{plan.filename}</strong>
            {plan.active ? (
              <span className="badge on">当前用于摆放</span>
            ) : (
              <button className="secondary" type="button" disabled={busy} onClick={activate}>
                改用这张图摆放
              </button>
            )}
          </div>
          <p className="fine">{plan.note}</p>
          <p className="fine">{plan.honesty}</p>
          <form className="stack" onSubmit={saveMeasure}>
            <strong>图上写明的比例和层高</strong>
            <p className="fine">只填写图纸已经写明的数。不知道就留空。留空时打印报价单的数量也留空，不会估。</p>
            <div className="grid-2">
              <label className="field">
                每图面单位多少米
                <input value={scaleText} onChange={(event) => setScaleText(event.target.value)} inputMode="decimal" placeholder="留空" />
              </label>
              <label className="field">
                层高（米）
                <input value={heightText} onChange={(event) => setHeightText(event.target.value)} inputMode="decimal" placeholder="留空" />
              </label>
            </div>
            <button className="secondary" type="submit" disabled={busy}>
              记下比例和层高
            </button>
          </form>
          <div
            className="plan-board"
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              setPending({
                x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
                y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
              });
            }}
          >
            {preview && (plan.media === "svg" || plan.media === "image") ? <img src={preview} alt={plan.filename} /> : null}
            {plan.media === "dxf" ? <PlanCanvas vectors={plan.vectors} /> : null}
            {plan.media === "pdf" ? (
              <p className="plan-empty">PDF 已保存。这一轮不把 PDF 转成底图。请在这张空白底上点选，或改传图片、SVG、DXF。</p>
            ) : null}
            {!preview && plan.media !== "pdf" && plan.media !== "dxf" && !plan.vectors.length ? (
              <p className="plan-empty">底图还在读取。</p>
            ) : null}
            {placed.map((mark) => (
              <span
                key={mark.id}
                className={`plan-dot ${mark.role}`}
                style={dotStyle(mark.x, mark.y)}
                onClick={(event) => event.stopPropagation()}
              >
                {mark.slot_label}
                {mark.role === "empty" ? " · 未挂" : ""}
              </span>
            ))}
            {pending ? (
              <span className="plan-dot pending" style={dotStyle(pending.x, pending.y)}>
                新的点
              </span>
            ) : null}
          </div>
          <div className="grid-2">
            <label className="field">
              房间
              <select value={room} onChange={(event) => setRoom(event.target.value)}>
                {(unit?.rooms.length ? unit.rooms : [{ id: "living", name: "客厅" }]).map((item) => (
                  <option key={item.id} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              部位
              <select
                value={partId}
                onChange={(event) => {
                  const next = event.target.value;
                  setPartId(next);
                  const found = PARTS.find((item) => item.id === next);
                  if (found) setSlot(found.slot);
                }}
              >
                {PARTS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="field">
            点上的名称（马桶位、哪面墙、哪面地）
            <input value={slot} onChange={(event) => setSlot(event.target.value)} />
          </label>
          <button type="button" disabled={busy || !pending} onClick={saveMark}>
            记下这个点
          </button>
          <h3>按这些点摆上的产品和材料</h3>
          {placed.length === 0 ? <p className="muted">还没有点。在图上点一下，再选房间和部位。</p> : null}
          {placed.map((mark) => (
            <div key={mark.id} className="quote-line">
              <div>
                <strong>
                  {mark.room_name} · {mark.slot_label}
                </strong>
                <span>
                  {mark.role === "material"
                    ? `材料 · ${mark.product_name || "按客户选的方案"}`
                    : mark.role === "product"
                      ? `产品 · ${mark.product_name}`
                      : "这个点还没有挂产品，只记下位置。"}
                  {` · ${mark.width_mm}×${mark.depth_mm}×${mark.height_mm} mm`}
                </span>
              </div>
              <button className="ghost" type="button" onClick={() => removeMark(mark.id).catch((err) => setError(err.message))}>
                撤下
              </button>
            </div>
          ))}
          <p className="fine">
            客户上传的效果照片不进报价，会盖在同房间、同名称的点上，只在客户房间里看。整张 DWG 分层这一轮不读。
          </p>
        </article>
      ) : (
        <p className="muted">这个户型还没有简化平面。A 户型演示项目里已经放了一张，可以直接点。</p>
      )}
    </section>
  );
}
