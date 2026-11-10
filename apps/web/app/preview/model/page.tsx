"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

const MeshViewer = dynamic(() => import("@/components/MeshViewer"), { ssr: false });

export default function ModelPreviewPage() {
  const [which, setWhich] = useState<"door" | "cabinet">("door");
  const url = which === "door" ? "/models/door-sample.glb" : "/models/cabinet-sample.glb";
  return (
    <main className="shell stack">
      <p className="kicker">自制简模 · 不是品牌模型</p>
      <h1>模型导入预览</h1>
      <p className="lead">示例门有门框和门扇两块网格，可以分别上色。拖动可以旋转。后台产品库也可以上传 glTF、GLB、FBX、OBJ。</p>
      <div className="row-actions">
        <button type="button" className={which === "door" ? "" : "secondary"} onClick={() => setWhich("door")}>
          示例门
        </button>
        <button type="button" className={which === "cabinet" ? "" : "secondary"} onClick={() => setWhich("cabinet")}>
          示例柜
        </button>
      </div>
      <MeshViewer url={url} format="glb" />
    </main>
  );
}
