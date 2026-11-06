import * as THREE from "three";
import type { MaterialSpec } from "@/lib/types";

function hex(color: string): [number, number, number] {
  const value = color.replace("#", "");
  return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)];
}

export function mix(a: string, b: string, t: number): string {
  const pa = hex(a);
  const pb = hex(b);
  return `#${pa
    .map((channel, index) => Math.max(0, Math.min(255, Math.round(channel + (pb[index] - channel) * t))).toString(16).padStart(2, "0"))
    .join("")}`;
}

export function shade(color: string, factor: number): string {
  return `#${hex(color)
    .map((channel) => Math.max(0, Math.min(255, Math.round(channel * factor))).toString(16).padStart(2, "0"))
    .join("")}`;
}

function rand(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function canvasTexture(draw: (ctx: CanvasRenderingContext2D, size: number) => void, repeatX: number, repeatY: number) {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  draw(ctx, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(repeatX, repeatY);
  texture.anisotropy = 8;
  return texture;
}

function paintFloor(spec: MaterialSpec, styleId: string) {
  const { feature, color, accent } = spec;
  const noise = rand(feature.length * 17 + color.charCodeAt(1) + styleId.length);
  if (feature === "wood") {
    return canvasTexture((ctx, size) => {
      const rows = 8;
      const rowH = size / rows;
      for (let i = 0; i < rows; i += 1) {
        ctx.fillStyle = i % 2 === 0 ? color : mix(color, accent, 0.35);
        ctx.fillRect(0, i * rowH, size, rowH - 3);
        ctx.fillStyle = shade(accent, 0.75);
        ctx.fillRect(0, i * rowH + rowH - 3, size, 3);
        ctx.globalAlpha = 0.35;
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, i * rowH + rowH * 0.45);
        ctx.bezierCurveTo(size * 0.3, i * rowH + 8, size * 0.6, i * rowH + rowH * 0.7, size, i * rowH + rowH * 0.35);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }, 2.4, 4.6);
  }
  if (feature === "parquet") {
    return canvasTexture((ctx, size) => {
      ctx.fillStyle = shade(color, 0.92);
      ctx.fillRect(0, 0, size, size);
      const w = 36;
      const h = 120;
      for (let row = 0; row < 14; row += 1) {
        for (let col = 0; col < 10; col += 1) {
          ctx.save();
          ctx.translate(col * 52 + (row % 2) * 26, row * 36);
          ctx.rotate(row % 2 === 0 ? 0.55 : -0.55);
          ctx.fillStyle = (col + row) % 2 === 0 ? color : mix(color, accent, 0.45);
          ctx.fillRect(0, 0, h, w);
          ctx.strokeStyle = shade(accent, 0.7);
          ctx.lineWidth = 2;
          ctx.strokeRect(0, 0, h, w);
          ctx.restore();
        }
      }
    }, 3.2, 4.4);
  }
  if (feature === "marble_border" || feature === "stone") {
    return canvasTexture((ctx, size) => {
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, size, size);
      for (let i = 0; i < 9; i += 1) {
        ctx.globalAlpha = 0.18 + noise() * 0.2;
        ctx.fillStyle = i % 2 ? "#ffffff" : accent;
        ctx.beginPath();
        ctx.ellipse(noise() * size, noise() * size, 40 + noise() * 90, 18 + noise() * 30, noise(), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 0.55;
      ctx.strokeStyle = accent;
      ctx.lineWidth = feature === "stone" ? 3 : 2;
      for (let i = 0; i < 7; i += 1) {
        ctx.beginPath();
        ctx.moveTo(noise() * size, noise() * size);
        ctx.bezierCurveTo(noise() * size, noise() * size, noise() * size, noise() * size, noise() * size, noise() * size);
        ctx.stroke();
      }
      if (feature === "stone") {
        ctx.globalAlpha = 0.7;
        ctx.fillStyle = accent;
        ctx.fillRect(0, 0, size, 8);
        ctx.fillRect(0, 0, 8, size);
      }
      ctx.globalAlpha = 1;
    }, feature === "stone" ? 2.6 : 2.2, feature === "stone" ? 3.4 : 3);
  }
  const large = feature === "metal_grout" || (feature === "tile" && styleId === "light_luxury");
  const grout = feature === "metal_grout" ? 20 : 8;
  return canvasTexture((ctx, size) => {
    ctx.fillStyle = feature === "metal_grout" ? accent : mix(accent, "#888888", 0.4);
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = color;
    ctx.fillRect(grout, grout, size - grout * 2, size - grout * 2);
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(grout + 16, grout + 18, size * 0.45, size * 0.28);
    ctx.globalAlpha = 1;
  }, large ? 2.6 : 4.8, large ? 3.6 : 6.6);
}

export function applyFloor(material: THREE.MeshStandardMaterial, spec: MaterialSpec, styleId: string) {
  const next = paintFloor(spec, styleId);
  if (material.map) material.map.dispose();
  material.map = next;
  material.color.set("#ffffff");
  material.roughness = spec.roughness;
  material.metalness = spec.feature === "metal_grout" ? Math.max(spec.metalness, 0.12) : spec.metalness;
  material.needsUpdate = true;
}

export function applyPaint(material: THREE.MeshStandardMaterial, spec: MaterialSpec, grain: "flat" | "wall" | "leather" | "stone") {
  const next = canvasTexture((ctx, size) => {
    ctx.fillStyle = spec.color;
    ctx.fillRect(0, 0, size, size);
    const noise = rand(spec.feature.length * 13 + spec.color.charCodeAt(2));
    if (grain === "wall") {
      ctx.globalAlpha = 0.05;
      for (let i = 0; i < 1800; i += 1) {
        ctx.fillStyle = noise() > 0.5 ? "#ffffff" : "#000000";
        ctx.fillRect(noise() * size, noise() * size, 2, 2);
      }
    } else if (grain === "leather") {
      ctx.fillStyle = spec.accent;
      for (let y = 40; y < size; y += 86) {
        ctx.globalAlpha = 0.45;
        ctx.fillRect(18, y, size - 36, 2);
        ctx.fillRect(18, y, 2, 70);
        ctx.fillRect(size - 20, y, 2, 70);
      }
      ctx.globalAlpha = 0.15;
      for (let i = 0; i < 700; i += 1) ctx.fillRect(noise() * size, noise() * size, 2, 2);
    } else if (grain === "stone") {
      ctx.globalAlpha = 0.22;
      ctx.fillStyle = spec.accent;
      for (let i = 0; i < 8; i += 1) {
        ctx.beginPath();
        ctx.ellipse(noise() * size, noise() * size, 30 + noise() * 80, 12 + noise() * 24, noise(), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
  }, grain === "leather" ? 1.2 : 2.5, grain === "leather" ? 1.4 : 2.5);
  if (material.map) material.map.dispose();
  material.map = next;
  material.color.set("#ffffff");
  material.roughness = spec.roughness;
  material.metalness = spec.metalness;
  material.needsUpdate = true;
}
