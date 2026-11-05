"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { MaterialSpec } from "@/lib/types";

type Look = {
  ceiling: MaterialSpec;
  floor: MaterialSpec;
  wall: MaterialSpec;
  styleId: string;
};

function rand(seed: number) {
  return function next() {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function floorTexture(feature: string, color: string, accent: string) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 512, 512);
  const noise = rand(feature.length * 97 + color.charCodeAt(1));
  if (feature === "tile" || feature === "metal_grout") {
    ctx.strokeStyle = accent;
    ctx.lineWidth = feature === "metal_grout" ? 10 : 5;
    const step = feature === "metal_grout" ? 256 : 128;
    for (let i = 0; i <= 512; i += step) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, 512);
      ctx.moveTo(0, i);
      ctx.lineTo(512, i);
      ctx.stroke();
    }
  } else if (feature === "wood") {
    for (let y = 0; y < 512; y += 46) {
      ctx.globalAlpha = 0.28;
      ctx.fillStyle = accent;
      ctx.fillRect(0, y, 512, 8);
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.moveTo(0, y + 22);
      ctx.bezierCurveTo(140, y + 8, 280, y + 34, 512, y + 16);
      ctx.strokeStyle = accent;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  } else if (feature === "parquet") {
    ctx.strokeStyle = accent;
    ctx.lineWidth = 3;
    const size = 72;
    for (let y = 0; y < 512; y += size) {
      for (let x = 0; x < 512; x += size) {
        ctx.save();
        ctx.translate(x + size / 2, y + size / 2);
        ctx.rotate(Math.PI / 4);
        ctx.strokeRect(-22, -22, 44, 44);
        ctx.restore();
      }
    }
  } else if (feature === "marble_border" || feature === "stone") {
    ctx.strokeStyle = accent;
    ctx.globalAlpha = 0.45;
    ctx.lineWidth = 2;
    for (let i = 0; i < 16; i += 1) {
      ctx.beginPath();
      ctx.moveTo(noise() * 512, noise() * 512);
      ctx.bezierCurveTo(noise() * 512, noise() * 512, noise() * 512, noise() * 512, noise() * 512, noise() * 512);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(feature === "tile" || feature === "metal_grout" ? 2 : 1.6, 2.2);
  texture.anisotropy = 4;
  return texture;
}

function paintMaterial(material: THREE.MeshStandardMaterial, spec: MaterialSpec, textured: boolean) {
  material.roughness = spec.roughness;
  material.metalness = spec.metalness;
  if (textured) {
    const next = floorTexture(spec.feature, spec.color, spec.accent);
    if (material.map) material.map.dispose();
    material.map = next;
    material.color.set("#ffffff");
  } else {
    if (material.map) {
      material.map.dispose();
      material.map = null;
    }
    material.color.set(spec.color);
  }
  material.needsUpdate = true;
}

export default function ScenePreview({ ceiling, floor, wall, styleId }: Look) {
  const host = useRef<HTMLDivElement>(null);
  const applyRef = useRef<(() => void) | null>(null);
  const lookRef = useRef<Look>({ ceiling, floor, wall, styleId });
  lookRef.current = { ceiling, floor, wall, styleId };

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
    renderer.setClearColor(0xe7e1d8, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    element.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 40);
    camera.position.set(3.55, 2.2, 4.9);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minPolarAngle = 0.42;
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controls.minDistance = 3.1;
    controls.maxDistance = 8.6;
    controls.target.set(0, 1.12, 0.15);

    const hemi = new THREE.HemisphereLight(0xfff3e4, 0xd9d1c6, 1.15);
    const dir = new THREE.DirectionalLight(0xfff6ea, 1.35);
    dir.position.set(3.2, 5.4, 2.4);
    const fill = new THREE.DirectionalLight(0xd5e4ea, 0.35);
    fill.position.set(-3, 2, 1);
    scene.add(hemi, dir, fill, new THREE.AmbientLight(0xffffff, 0.25));

    const floorMat = new THREE.MeshStandardMaterial({ roughness: 0.4 });
    const ceilingMat = new THREE.MeshStandardMaterial({ roughness: 0.8, side: THREE.DoubleSide });
    const wallMat = new THREE.MeshStandardMaterial({ roughness: 0.75, side: THREE.DoubleSide });
    const glassMat = new THREE.MeshStandardMaterial({
      color: "#c9dbe3",
      roughness: 0.05,
      metalness: 0.05,
      transparent: true,
      opacity: 0.28,
    });
    const frameMat = new THREE.MeshStandardMaterial({ color: "#c6a36a", metalness: 0.55, roughness: 0.3 });
    const lampMat = new THREE.MeshStandardMaterial({
      color: "#e8c99a",
      emissive: "#e8c99a",
      emissiveIntensity: 0.45,
      roughness: 0.35,
    });
    const featureMat = new THREE.MeshStandardMaterial({ roughness: 0.6 });
    const featureMat2 = new THREE.MeshStandardMaterial({ roughness: 0.5 });
    const floorFeatureMat = new THREE.MeshStandardMaterial({ roughness: 0.35 });

    const floorMesh = new THREE.Mesh(new THREE.PlaneGeometry(4.8, 6.4), floorMat);
    floorMesh.rotation.x = -Math.PI / 2;
    scene.add(floorMesh);
    const ceilingMesh = new THREE.Mesh(new THREE.PlaneGeometry(4.8, 6.4), ceilingMat);
    ceilingMesh.rotation.x = Math.PI / 2;
    ceilingMesh.position.y = 2.6;
    scene.add(ceilingMesh);
    const backWall = new THREE.Mesh(new THREE.PlaneGeometry(4.8, 2.6), wallMat);
    backWall.position.set(0, 1.3, -3.2);
    const leftWall = new THREE.Mesh(new THREE.PlaneGeometry(6.4, 2.6), wallMat);
    leftWall.position.set(-2.4, 1.3, 0);
    leftWall.rotation.y = Math.PI / 2;
    scene.add(backWall, leftWall);
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 1.9), glassMat);
    glass.position.set(2.39, 1.45, 0.2);
    glass.rotation.y = -Math.PI / 2;
    scene.add(glass);

    function frameBox(width: number, height: number, depth: number, x: number, y: number, z: number) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), frameMat);
      mesh.position.set(x, y, z);
      return mesh;
    }
    scene.add(
      frameBox(0.06, 2.05, 0.06, 2.36, 1.45, -1.4),
      frameBox(0.06, 2.05, 0.06, 2.36, 1.45, 1.8),
      frameBox(0.06, 0.06, 3.3, 2.36, 2.45, 0.2),
      frameBox(0.06, 0.06, 3.3, 2.36, 0.48, 0.2),
    );

    const groups: Record<string, THREE.Object3D> = {};
    function addGroup(name: string, meshes: THREE.Object3D[]) {
      const group = new THREE.Group();
      meshes.forEach((mesh) => group.add(mesh));
      group.visible = false;
      scene.add(group);
      groups[name] = group;
    }
    const box = (w: number, h: number, d: number, x: number, y: number, z: number, material = featureMat) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
      mesh.position.set(x, y, z);
      return mesh;
    };
    addGroup("cove", [
      box(4.3, 0.04, 0.08, 0, 2.5, -3.0, featureMat2),
      box(4.3, 0.04, 0.08, 0, 2.5, 3.0, featureMat2),
      box(0.08, 0.04, 6.0, -2.2, 2.5, 0, featureMat2),
      box(0.08, 0.04, 6.0, 2.2, 2.5, 0, featureMat2),
    ]);
    addGroup("tray", [box(3.3, 0.05, 4.6, 0, 2.46, 0, featureMat2)]);
    addGroup("veneer", [0, 1, 2, 3, 4].map((index) => box(0.34, 0.03, 5.6, -1.5 + index * 0.72, 2.54, 0, featureMat2)));
    addGroup("cornice", [
      box(4.8, 0.12, 0.1, 0, 2.48, -3.15, featureMat2),
      box(4.8, 0.12, 0.1, 0, 2.48, 3.15, featureMat2),
      box(0.1, 0.12, 6.4, -2.35, 2.48, 0, featureMat2),
      box(0.1, 0.12, 6.4, 2.35, 2.48, 0, featureMat2),
    ]);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.035, 12, 40), featureMat2);
    ring.rotation.x = Math.PI / 2;
    ring.position.set(0, 2.52, 0.2);
    const medallion = new THREE.Mesh(new THREE.CircleGeometry(0.28, 28), featureMat2);
    medallion.rotation.x = Math.PI / 2;
    medallion.position.set(0, 2.5, 0.2);
    addGroup("lightwell", [ring]);
    addGroup("medallion", [medallion]);
    addGroup("gold_trough", [
      box(3.8, 0.045, 0.07, 0, 2.5, -2.55, featureMat2),
      box(3.8, 0.045, 0.07, 0, 2.5, 2.55, featureMat2),
      box(0.07, 0.045, 5.1, -1.85, 2.5, 0, featureMat2),
      box(0.07, 0.045, 5.1, 1.85, 2.5, 0, featureMat2),
    ]);
    const panel = new THREE.Mesh(new THREE.BoxGeometry(3.5, 0.04, 4.4), featureMat2);
    panel.position.set(0, 2.42, 0);
    addGroup("gloss_panel", [panel]);
    addGroup("mirror_edge", [
      box(3.62, 0.05, 0.05, 0, 2.4, -2.2, featureMat2),
      box(3.62, 0.05, 0.05, 0, 2.4, 2.2, featureMat2),
      box(0.05, 0.05, 4.5, -1.78, 2.4, 0, featureMat2),
      box(0.05, 0.05, 4.5, 1.78, 2.4, 0, featureMat2),
    ]);
    addGroup("marble_border", [
      box(4.2, 0.015, 0.12, 0, 0.012, -2.85, floorFeatureMat),
      box(4.2, 0.015, 0.12, 0, 0.012, 2.85, floorFeatureMat),
      box(0.12, 0.015, 5.6, -2.05, 0.012, 0, floorFeatureMat),
      box(0.12, 0.015, 5.6, 2.05, 0.012, 0, floorFeatureMat),
    ]);
    addGroup("metal_grout", [box(0.04, 0.012, 5.8, 0.35, 0.012, 0, floorFeatureMat)]);

    const accentPanel = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.2), featureMat);
    accentPanel.position.set(0.15, 1.45, -3.16);
    addGroup("fabric_accent", [accentPanel]);
    addGroup("wainscot", [
      box(4.75, 1.05, 0.04, 0, 0.55, -3.16),
      box(0.04, 1.05, 6.3, -2.36, 0.55, 0),
      box(4.7, 0.04, 0.05, 0, 1.08, -3.14),
    ]);
    addGroup("moulding", [
      box(1.5, 0.04, 0.04, -0.9, 1.9, -3.15),
      box(1.5, 0.04, 0.04, -0.9, 0.7, -3.15),
      box(0.04, 1.2, 0.04, -1.65, 1.3, -3.15),
      box(0.04, 1.2, 0.04, -0.15, 1.3, -3.15),
      box(1.5, 0.04, 0.04, 0.95, 1.9, -3.15),
      box(1.5, 0.04, 0.04, 0.95, 0.7, -3.15),
      box(0.04, 1.2, 0.04, 0.2, 1.3, -3.15),
      box(0.04, 1.2, 0.04, 1.7, 1.3, -3.15),
    ]);
    addGroup("upholstered", [-0.95, 0.15, 1.25].map((x) => box(0.85, 1.25, 0.08, x, 1.35, -3.12)));
    const stone = new THREE.Mesh(new THREE.PlaneGeometry(2.7, 2.35), featureMat);
    stone.position.set(0.2, 1.25, -3.15);
    addGroup("stone_full", [stone]);
    addGroup("sintered", [
      box(3.1, 2.15, 0.05, 0.1, 1.25, -3.14),
      box(0.025, 2.05, 0.02, -0.9, 1.25, -3.1, featureMat2),
      box(0.025, 2.05, 0.02, 1.05, 1.25, -3.1, featureMat2),
      box(2.9, 0.025, 0.02, 0.1, 0.45, -3.1, featureMat2),
    ]);
    addGroup(
      "leather",
      [-1.15, -0.35, 0.45, 1.25].map((x) => box(0.7, 1.55, 0.07, x, 1.25, -3.13)),
    );

    const fabric = new THREE.MeshStandardMaterial({ color: "#d5cec4", roughness: 0.86 });
    const seat = new THREE.Mesh(new THREE.BoxGeometry(1.65, 0.36, 0.7), fabric);
    seat.position.set(0.85, 0.28, -2.2);
    const back = new THREE.Mesh(new THREE.BoxGeometry(1.65, 0.48, 0.12), fabric);
    back.position.set(0.85, 0.62, -2.5);
    const table = new THREE.Mesh(
      new THREE.CylinderGeometry(0.38, 0.38, 0.06, 28),
      new THREE.MeshStandardMaterial({ color: "#2c2c2c", roughness: 0.35, metalness: 0.2 }),
    );
    table.position.set(0.75, 0.36, -1.15);
    const dining = new THREE.Mesh(
      new THREE.BoxGeometry(0.7, 0.05, 0.7),
      new THREE.MeshStandardMaterial({ color: "#3a3632", roughness: 0.45 }),
    );
    dining.position.set(-1.25, 0.72, 0.55);
    const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.45, 8), lampMat);
    cord.position.set(-0.15, 2.25, 0.35);
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.09, 18, 12), lampMat);
    bulb.position.set(-0.15, 1.98, 0.35);
    scene.add(seat, back, table, dining, cord, bulb);

    const show: Record<string, string[]> = {
      cove: ["cove"],
      tray: ["tray"],
      veneer: ["veneer"],
      cornice: ["cornice"],
      lightwell: ["cornice", "lightwell"],
      medallion: ["cornice", "lightwell", "medallion"],
      gold_trough: ["gold_trough"],
      gloss_panel: ["gloss_panel"],
      mirror_edge: ["gloss_panel", "mirror_edge"],
      marble_border: ["marble_border"],
      metal_grout: ["metal_grout"],
      fabric_accent: ["fabric_accent"],
      wainscot: ["wainscot"],
      moulding: ["moulding"],
      upholstered: ["upholstered"],
      stone_full: ["stone_full"],
      sintered: ["sintered"],
      leather: ["leather"],
    };

    const apply = () => {
      const look = lookRef.current;
      paintMaterial(floorMat, look.floor, true);
      paintMaterial(ceilingMat, look.ceiling, false);
      paintMaterial(wallMat, look.wall, false);
      featureMat.color.set(look.wall.accent);
      featureMat.roughness = Math.min(1, look.wall.roughness + 0.05);
      featureMat.metalness = look.wall.feature === "sintered" || look.wall.feature === "mirror_edge" ? 0.45 : 0.04;
      featureMat2.color.set(look.ceiling.accent);
      const glow = look.ceiling.feature === "gold_trough" || look.ceiling.feature === "cove";
      featureMat2.emissive.set(glow ? look.ceiling.accent : "#000000");
      featureMat2.emissiveIntensity = glow ? 0.35 : 0;
      featureMat2.metalness = look.ceiling.feature === "mirror_edge" ? 0.85 : look.ceiling.metalness;
      featureMat2.roughness = look.ceiling.roughness;
      floorFeatureMat.color.set(look.floor.accent);
      floorFeatureMat.metalness = look.floor.feature === "metal_grout" ? 0.7 : 0.05;
      floorFeatureMat.roughness = look.floor.feature === "metal_grout" ? 0.25 : 0.4;
      const active = new Set([...(show[look.ceiling.feature] || []), ...(show[look.floor.feature] || []), ...(show[look.wall.feature] || [])]);
      Object.entries(groups).forEach(([name, group]) => {
        group.visible = active.has(name);
      });
      frameMat.color.set(look.ceiling.accent);
      frameMat.metalness = look.styleId === "light_luxury" ? 0.75 : 0.35;
      lampMat.color.set(look.ceiling.accent);
      lampMat.emissive.set(look.ceiling.accent);
      hemi.color.set(look.styleId === "light_luxury" ? "#f2f4f6" : "#fff1df");
      dir.color.set(look.styleId === "cream" ? "#ffe3b8" : "#fff7ea");
      renderer.toneMappingExposure = look.styleId === "light_luxury" ? 0.98 : 1.08;
    };
    applyRef.current = apply;
    apply();

    const resize = () => {
      const width = element.clientWidth || 320;
      const height = element.clientHeight || 300;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    let frame = 0;
    const loop = () => {
      frame = window.requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();

    return () => {
      applyRef.current = null;
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      const disposed = new Set<THREE.Material>();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => {
            if (disposed.has(material)) return;
            disposed.add(material);
            if (material.map) material.map.dispose();
            material.dispose();
          });
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  const signature = JSON.stringify({ ceiling, floor, wall, styleId });
  useEffect(() => {
    applyRef.current?.();
  }, [signature]);

  return <div ref={host} className="scene-host" aria-label="拖动可旋转房间，材质随所选方案变化" />;
}
