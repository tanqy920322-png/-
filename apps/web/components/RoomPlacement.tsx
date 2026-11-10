"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export type Placement = {
  room: string;
  label: string;
  kind: string;
  width_mm: number;
  depth_mm: number;
  height_mm: number;
};

function material(color: string, roughness = 0.62) {
  return new THREE.MeshStandardMaterial({ color, roughness });
}

function addBox(group: THREE.Group, width: number, height: number, depth: number, x: number, y: number, z: number, color: string) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material(color));
  mesh.position.set(x, y, z);
  group.add(mesh);
}

function standIn(item: Placement, width: number, depth: number, height: number) {
  const group = new THREE.Group();
  const text = `${item.kind} ${item.label}`;
  const w = Math.max(width, 0.18);
  const d = Math.max(depth, 0.12);
  const h = Math.max(height, 0.16);
  if (text.includes("花洒")) {
    addBox(group, 0.04, 0.7, 0.04, -w * 0.2, 1.5, 0, "#c5ccd0");
    addBox(group, w * 0.7, 0.05, 0.06, 0, 1.82, 0, "#b7c0c4");
    const head = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.04, 20), material("#e8eef0", 0.35));
    head.rotation.z = Math.PI / 2;
    head.position.set(w * 0.25, 1.82, 0);
    group.add(head);
    return { group, lift: 0 };
  }
  if (text.includes("马桶") || (item.kind === "sanitary" && !text.includes("龙头") && !text.includes("菜盆"))) {
    addBox(group, w * 0.62, h * 0.34, d * 0.34, 0, h * 0.78, -d * 0.22, "#f4f6f6");
    addBox(group, w * 0.92, h * 0.32, d * 0.78, 0, h * 0.18, d * 0.08, "#fbfbfb");
    addBox(group, w * 0.7, h * 0.07, d * 0.5, 0, h * 0.38, d * 0.1, "#d5dee2");
    return { group, lift: 0 };
  }
  if (text.includes("龙头") || text.includes("面盆") || text.includes("菜盆")) {
    addBox(group, w, h * 0.35, d, 0, h * 0.2, 0, "#f3f1ec");
    addBox(group, w * 0.55, 0.06, d * 0.45, 0, h * 0.42, 0, "#d5e6ea");
    addBox(group, 0.04, h * 0.45, 0.04, 0, h * 0.7, -d * 0.1, "#c5ccd0");
    return { group, lift: 0 };
  }
  if (item.kind === "lighting" || text.includes("灯")) {
    const canopy = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.03, 16), material("#d9d3c6"));
    canopy.position.y = 0.12;
    group.add(canopy);
    const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.05, Math.max(w, 0.16) / 2, Math.max(h, 0.18), 20), material("#f4d7a2", 0.4));
    shade.position.y = 0;
    group.add(shade);
    return { group, lift: 2.25 };
  }
  if (item.kind === "cabinetry" || text.includes("柜")) {
    addBox(group, w, h * 0.92, d, 0, h * 0.5, 0, "#d7b88a");
    addBox(group, w * 0.46, h * 0.78, 0.02, -w * 0.24, h * 0.52, d * 0.52, "#f0e2c8");
    addBox(group, w * 0.46, h * 0.78, 0.02, w * 0.24, h * 0.52, d * 0.52, "#e7d3b0");
    addBox(group, w, h * 0.06, d * 1.02, 0, h * 0.04, 0, "#8c6239");
    return { group, lift: 0 };
  }
  if (item.kind === "sofa" || text.includes("沙发")) {
    addBox(group, w, h * 0.42, d, 0, h * 0.24, 0, "#f4efe8");
    addBox(group, w, h * 0.55, d * 0.22, 0, h * 0.62, -d * 0.38, "#e7d7c8");
    addBox(group, w * 0.12, h * 0.48, d * 0.9, -w * 0.46, h * 0.4, 0, "#efe4d6");
    addBox(group, w * 0.12, h * 0.48, d * 0.9, w * 0.46, h * 0.4, 0, "#efe4d6");
    return { group, lift: 0 };
  }
  if (item.kind === "entry_door" || text.includes("入户门") || text.includes("门扇")) {
    addBox(group, w, h, 0.06, 0, h / 2, 0, "#6e4b2a");
    addBox(group, w * 0.78, h * 0.9, 0.05, 0, h * 0.48, 0.04, "#a87445");
    addBox(group, 0.03, 0.12, 0.04, w * 0.28, h * 0.48, 0.08, "#f0e2c8");
    return { group, lift: 0 };
  }
  if (text.includes("烟机")) {
    addBox(group, w * 0.2, h * 0.4, d * 0.2, 0, h * 0.8, 0, "#d5d7d8");
    addBox(group, w, h * 0.18, d, 0, h * 0.5, 0, "#eceeef");
    return { group, lift: 1.5 };
  }
  if (item.kind === "kitchen_appliance") {
    addBox(group, w, h, d, 0, h / 2, 0, "#e6e7e8");
    addBox(group, w * 0.7, h * 0.35, 0.02, 0, h * 0.62, d * 0.52, "#2c3338");
    return { group, lift: 0 };
  }
  if (item.kind === "switch_socket") {
    addBox(group, Math.max(w, 0.12), Math.max(h, 0.16), 0.03, 0, 0, 0, "#f7f4ee");
    return { group, lift: 1.15 };
  }
  addBox(group, w, h, d, 0, h / 2, 0, "#e7d3b0");
  return { group, lift: 0 };
}

export default function RoomPlacement({
  rooms,
  placements,
}: {
  rooms: { name: string; area_m2: number }[];
  placements: Placement[];
}) {
  const host = useRef<HTMLDivElement>(null);
  const signature = `${rooms.map((room) => room.name).join(",")}|${placements
    .map((item) => `${item.room}:${item.label}:${item.width_mm}`)
    .join(",")}`;

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0xe7e0d4, 1);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
    camera.position.set(8, 9, 10);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(2, 0.4, 2);
    controls.enableDamping = true;
    scene.add(new THREE.AmbientLight(0xfff4e6, 1.1));
    const sun = new THREE.DirectionalLight(0xfff0dc, 1.4);
    sun.position.set(4, 8, 2);
    scene.add(sun);
    const root = new THREE.Group();
    scene.add(root);
    element.appendChild(renderer.domElement);

    const resize = () => {
      const width = element.clientWidth || 360;
      const height = element.clientHeight || 320;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    resize();

    const draw = () => {
      root.traverse((child) => {
        const mesh = child as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else material?.dispose?.();
      });
      root.clear();
      const list = rooms.length ? rooms : [{ name: "客厅", area_m2: 14 }];
      const columns = 4;
      list.forEach((room, index) => {
        const col = index % columns;
        const row = Math.floor(index / columns);
        const span = Math.max(1.3, Math.sqrt(room.area_m2) * 0.55);
        const x = col * 2.4;
        const z = row * 2.4;
        const slab = new THREE.Mesh(
          new THREE.BoxGeometry(span, 0.06, span),
          new THREE.MeshStandardMaterial({ color: "#f6f1ea", roughness: 0.9 }),
        );
        slab.position.set(x, 0, z);
        root.add(slab);
        const items = placements.filter((piece) => piece.room === room.name);
        items.slice(0, 6).forEach((item, piece) => {
          const w = Math.min(span * 0.72, Math.max(0.22, item.width_mm / 1000));
          const d = Math.min(span * 0.62, Math.max(0.16, item.depth_mm / 1000));
          const h = Math.min(2.4, Math.max(0.2, item.height_mm / 1000));
          const { group, lift } = standIn(item, w, d, h);
          group.position.set(x - span * 0.22 + (piece % 3) * (span / 3.2), lift, z - span * 0.12 + Math.floor(piece / 3) * 0.42);
          root.add(group);
        });
      });
    };
    draw();
    let frame = 0;
    const loop = () => {
      frame = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();
    const observer = new ResizeObserver(() => resize());
    observer.observe(element);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      element.removeChild(renderer.domElement);
    };
    // signature changes when the selected pieces change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  return <div ref={host} className="scene-host" />;
}
