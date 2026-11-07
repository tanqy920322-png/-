"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useQueryParam } from "@/lib/session";
import type { MaterialSpec, Style } from "@/lib/types";

const ScenePreview = dynamic(() => import("@/components/ScenePreview"), { ssr: false });

function schemeMaterial(style: Style, partId: string): MaterialSpec | null {
  const part = style.parts.find((item) => item.id === partId);
  return part?.schemes[0]?.material || null;
}

export default function FinishShotsPage() {
  const requested = useQueryParam("style");
  const [styles, setStyles] = useState<Style[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Style[]>("/api/styles")
      .then(setStyles)
      .catch(() => setError("风格列表没有读到。先启动 API，再刷新这一页。"));
  }, []);

  const shown = requested ? styles.filter((style) => style.id === requested) : styles;

  return (
    <main className="shell stack">
      <p className="kicker">程序贴图 · 不是品牌实拍</p>
      <h1>材质样张</h1>
      <p className="lead">
        奶油、欧式、轻奢各用方案 1。整页对比打开 /preview/finishes。单套截图加上 ?style=cream、?style=european 或
        ?style=light_luxury。
      </p>
      {error ? <p className="error">{error}</p> : null}
      {!styles.length && !error ? <p className="muted">正在读取风格…</p> : null}
      {shown.map((style) => {
        const ceiling = schemeMaterial(style, "ceiling");
        const floor = schemeMaterial(style, "floor");
        const wall = schemeMaterial(style, "wall");
        const names = ["ceiling", "floor", "wall"].map((partId) => style.parts.find((item) => item.id === partId)?.schemes[0]?.name);
        if (!ceiling || !floor || !wall) return null;
        return (
          <section key={style.id} className="stack">
            <h2>
              {style.name}
              <span className="muted"> · {style.tagline}</span>
            </h2>
            <p className="fine">
              天花 {names[0]} · 地面 {names[1]} · 墙面 {names[2]}
            </p>
            <ScenePreview styleId={style.id} ceiling={ceiling} floor={floor} wall={wall} />
          </section>
        );
      })}
    </main>
  );
}
