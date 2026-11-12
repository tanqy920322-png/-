"use client";

import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ChineseFile } from "@/components/ui";
import type { Selection, VisualSubstitute } from "@/lib/types";

const PARTS = [
  { id: "sanitary", name: "洁具 / 马桶", slot: "马桶", room: "公卫" },
  { id: "sofa", name: "软装沙发", slot: "沙发", room: "客厅" },
  { id: "switch_socket", name: "开关插座", slot: "开关插座", room: "客厅" },
  { id: "cabinetry", name: "全屋定制", slot: "柜体", room: "主卧" },
  { id: "lighting", name: "灯具", slot: "灯具", room: "客厅" },
  { id: "entry_door", name: "入户门", slot: "入户门", room: "玄关" },
  { id: "kitchen_appliance", name: "厨房电器", slot: "厨电", room: "厨房" },
];

export type StandPreset = { part_id: string; room_name: string; slot_label: string };

export default function PhotoStandIn({
  token,
  selectionId,
  selection,
  rooms,
  preset,
  photos,
  onChange,
}: {
  token: string;
  selectionId: string;
  selection: Selection;
  rooms: string[];
  preset?: StandPreset | null;
  photos: Record<string, { front: string; back?: string }>;
  onChange: (next: Selection) => void;
}) {
  const initial = preset?.part_id || "sanitary";
  const [partId, setPartId] = useState(initial);
  const [roomName, setRoomName] = useState(preset?.room_name || PARTS.find((item) => item.id === initial)?.room || rooms[0] || "客厅");
  const [slotLabel, setSlotLabel] = useState(preset?.slot_label || PARTS.find((item) => item.id === initial)?.slot || "马桶");
  const [width, setWidth] = useState("");
  const [depth, setDepth] = useState("");
  const [height, setHeight] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [extra, setExtra] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const activePart = preset?.part_id || partId;
  const activeRoom = preset?.room_name || roomName;
  const activeSlot = preset?.slot_label || slotLabel;
  const rows = selection.substitutes || [];
  const visible = useMemo(
    () => (preset ? rows.filter((item) => item.part_id === preset.part_id && item.room_name === preset.room_name) : rows),
    [preset, rows],
  );

  function choosePart(next: string) {
    const found = PARTS.find((item) => item.id === next);
    setPartId(next);
    if (found) {
      setSlotLabel(found.slot);
      if (rooms.includes(found.room)) setRoomName(found.room);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("请先选择一张产品照片");
      return;
    }
    const before = selection.quote.total;
    const body = new FormData();
    body.set("part_id", activePart);
    body.set("room_name", activeRoom);
    body.set("slot_label", activeSlot);
    body.set("file", file);
    if (extra) body.set("file_extra", extra);
    if (width.trim()) body.set("width_mm", width.trim());
    if (depth.trim()) body.set("depth_mm", depth.trim());
    if (height.trim()) body.set("height_mm", height.trim());
    setBusy(true);
    setError("");
    setNote("");
    try {
      const saved = await api<Selection>(`/api/selections/${selectionId}/substitutes`, { method: "POST", token, body });
      onChange(saved);
      if (saved.quote.total !== before) {
        setError("效果替代不应改变报价，请刷新后再看。");
      } else {
        setNote("已放进这个房间。部位合计没有变，也不能下单。");
      }
      setFile(null);
      setExtra(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没有生成示意件");
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: VisualSubstitute) {
    setBusy(true);
    setError("");
    try {
      onChange(await api<Selection>(`/api/selections/${selectionId}/substitutes/${item.id}`, { method: "DELETE", token }));
      setNote("已撤下这张效果。报价仍不变。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "撤下失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card stack" id="photo-stand-in">
      <strong>{preset ? "也可以上传照片看这一件" : "用照片看效果"}</strong>
      <p className="effect-banner">
        仅用于效果展示，不列入采购。
        <br />
        外形接近、能看出来是同一类、同一款式方向。
        <br />
        照片贴在这一类的常用外形上，不重建细部。
        <br />
        单张照片可能看不清背面和细部。
        <br />
        这不是付费图生三维的质量。
      </p>
      {visible.length ? (
        <div className="stack">
          {visible.map((item) => (
            <article key={item.id} className="quote-line">
              <div>
                {photos[item.id]?.front ? <img className="effect-thumb" src={photos[item.id].front} alt={item.slot_label} /> : null}
                <strong>
                  {item.room_name} · {item.slot_label}
                </strong>
                <span>
                  {item.label}
                  {item.demo ? (
                    <>
                      <br />
                      演示示意图，不是品牌实拍
                    </>
                  ) : null}
                  <br />
                  {item.width_mm} × {item.depth_mm} × {item.height_mm} mm
                  <br />
                  {item.extra_photo_path ? "第二张贴在背面" : "背面仍是常用外形"}
                </span>
              </div>
              <button className="ghost" type="button" disabled={busy} onClick={() => remove(item)}>
                撤下
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p className="fine">还没有照片。库里的选择可以保留，上传后只替换看到的效果。</p>
      )}
      <form className="stack" onSubmit={submit}>
        {preset ? (
          <p className="fine">
            确认品类：{PARTS.find((item) => item.id === activePart)?.name || activePart} · {activeRoom} · {activeSlot}
          </p>
        ) : (
          <>
            <label className="field">
              确认品类
              <select value={partId} onChange={(event) => choosePart(event.target.value)}>
                {PARTS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              放到哪个房间
              <select value={roomName} onChange={(event) => setRoomName(event.target.value)}>
                {(rooms.length ? rooms : ["客厅"]).map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              这一件
              <input value={slotLabel} onChange={(event) => setSlotLabel(event.target.value)} />
            </label>
          </>
        )}
        <div className="grid-2">
          <label className="field">
            宽 mm（可空，用常用尺寸）
            <input inputMode="numeric" value={width} onChange={(event) => setWidth(event.target.value)} />
          </label>
          <label className="field">
            深 mm
            <input inputMode="numeric" value={depth} onChange={(event) => setDepth(event.target.value)} />
          </label>
        </div>
        <label className="field">
          高 mm
          <input inputMode="numeric" value={height} onChange={(event) => setHeight(event.target.value)} />
        </label>
        <label className="field">
          产品照片
          <ChineseFile key={note} accept="image/png,image/jpeg,image/webp" onFile={setFile} />
        </label>
        <label className="field">
          第二张（可选，侧面或背面）
          <ChineseFile key={`${note}-extra`} accept="image/png,image/jpeg,image/webp" onFile={setExtra} />
        </label>
        {error ? <p className="error">{error}</p> : null}
        {note ? <p className="ok">{note}</p> : null}
        <button type="submit" disabled={busy || !file}>
          {busy ? "正在生成示意件" : "确认品类并生成示意件"}
        </button>
      </form>
      <p className="fine">示意件会留在这套方案里，刷新后还在。这一轮只用照片贴在常用外形上。</p>
    </section>
  );
}
