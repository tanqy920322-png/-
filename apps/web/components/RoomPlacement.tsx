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

const KIND_COLOR: Record<string, string> = {
  sofa: "#e7d7c8",
  cabinetry: "#c4a574",
  sanitary: "#d5e4ea",
  entry_door: "#8c6239",
  kitchen_appliance: "#c5c7ca",
  lighting: "#f0d7a4",
  switch_socket: "#f7f4ee",
  ceiling: "#f3ead8",
  wall: "#efe4d4",
  floor: "#d9c4a4",
};

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
        const items = placements.filter((item) => item.room === room.name);
        items.slice(0, 6).forEach((item, piece) => {
          const w = Math.min(span * 0.8, Math.max(0.08, item.width_mm / 1000));
          const d = Math.min(span * 0.7, Math.max(0.05, item.depth_mm / 1000));
          const h = Math.min(2.5, Math.max(0.04, item.height_mm / 1000));
          const mesh = new THREE.Mesh(
            new THREE.BoxGeometry(w, h, d),
            new THREE.MeshStandardMaterial({ color: KIND_COLOR[item.kind] || "#ddd2c3", roughness: 0.72 }),
          );
          mesh.position.set(x - span / 2 + 0.2 + (piece % 3) * (span / 3), h / 2, z - span / 4 + Math.floor(piece / 3) * 0.45);
          root.add(mesh);
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
