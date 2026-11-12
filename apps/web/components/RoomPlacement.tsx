"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { applyFinish, preloadFinishTextures } from "@/components/sceneTextures";
import { applyOfficialMap, type OfficialMaps } from "@/components/officialTexture";
import type { MaterialSpec } from "@/lib/types";

export type Placement = {
  room: string;
  label: string;
  kind: string;
  width_mm: number;
  depth_mm: number;
  height_mm: number;
  photoUrl?: string;
  photoBackUrl?: string;
  substitute?: boolean;
  x?: number;
  y?: number;
};

type Finish = {
  floor: MaterialSpec;
  wall: MaterialSpec;
  ceiling: MaterialSpec;
  styleId: string;
};

type Shot = { key: string; label: string; x: number; y: number; span: number };

type Aim = { x: number; y: number; span?: number };

const PLAN_W = 10;
const PLAN_D = 6.4;

function toWorld(nx: number, ny: number) {
  return { x: (nx - 0.5) * PLAN_W, z: (ny - 0.5) * PLAN_D };
}

function sprite(text: string, width = 256) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = 72;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, width, 72);
    ctx.fillStyle = "rgba(255,250,243,0.94)";
    ctx.fillRect(8, 8, width - 16, 56);
    ctx.fillStyle = "#2c2924";
    ctx.font = "600 32px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, width / 2, 38);
  }
  const tag = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true }));
  tag.scale.set(0.42, 0.12, 1);
  return tag;
}

type RoomRect = { minX: number; maxX: number; minZ: number; maxZ: number };

function rectOf(line: number[][]): RoomRect | null {
  if (line.length < 4) return null;
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  line.forEach(([nx, ny]) => {
    const world = toWorld(nx, ny);
    minX = Math.min(minX, world.x);
    maxX = Math.max(maxX, world.x);
    minZ = Math.min(minZ, world.z);
    maxZ = Math.max(maxZ, world.z);
  });
  if (maxX - minX < 0.35 || maxZ - minZ < 0.35) return null;
  return { minX, maxX, minZ, maxZ };
}

function rectContains(rect: RoomRect, x: number, z: number) {
  return x > rect.minX + 0.04 && x < rect.maxX - 0.04 && z > rect.minZ + 0.04 && z < rect.maxZ - 0.04;
}

function smallestRoom(rects: RoomRect[], x: number, z: number) {
  return rects
    .filter((rect) => rectContains(rect, x, z))
    .sort((a, b) => (a.maxX - a.minX) * (a.maxZ - a.minZ) - (b.maxX - b.minX) * (b.maxZ - b.minZ))[0];
}

function cameraInsideRoom(rect: RoomRect, world: { x: number; z: number }) {
  const inset = 0.28;
  const minX = rect.minX + inset;
  const maxX = rect.maxX - inset;
  const minZ = rect.minZ + inset;
  const maxZ = rect.maxZ - inset;
  const space = {
    px: maxX - world.x,
    nx: world.x - minX,
    pz: maxZ - world.z,
    nz: world.z - minZ,
  };
  const pick: { dir: keyof typeof space } = { dir: "pz" };
  if (space.pz < 0.7) {
    (Object.keys(space) as (keyof typeof space)[]).forEach((key) => {
      if (space[key] > space[pick.dir]) pick.dir = key;
    });
  }
  const dir = pick.dir;
  const step = Math.min(1.35, Math.max(0.72, space[dir] * 0.78));
  let camX = world.x;
  let camZ = world.z;
  if (dir === "pz") camZ = Math.min(maxZ, world.z + step);
  if (dir === "nz") camZ = Math.max(minZ, world.z - step);
  if (dir === "px") camX = Math.min(maxX, world.x + step);
  if (dir === "nx") camX = Math.max(minX, world.x - step);
  if (dir === "pz" || dir === "nz") {
    const lateral = space.px >= space.nx ? Math.min(0.32, Math.max(0, space.px) * 0.45) : -Math.min(0.32, Math.max(0, space.nx) * 0.45);
    camX = Math.min(maxX, Math.max(minX, world.x + lateral));
  } else {
    const lateral = space.pz >= space.nz ? Math.min(0.32, Math.max(0, space.pz) * 0.45) : -Math.min(0.32, Math.max(0, space.nz) * 0.45);
    camZ = Math.min(maxZ, Math.max(minZ, world.z + lateral));
  }
  return {
    x: Math.min(maxX, Math.max(minX, camX)),
    y: 1.08,
    z: Math.min(maxZ, Math.max(minZ, camZ)),
  };
}

function cameraForLargePiece(rect: RoomRect, world: { x: number; z: number }, span: number) {
  const inset = 0.42;
  const minX = rect.minX + inset;
  const maxX = rect.maxX - inset;
  const minZ = rect.minZ + inset;
  const maxZ = rect.maxZ - inset;
  const space = {
    px: Math.max(0, maxX - world.x),
    nx: Math.max(0, world.x - minX),
    pz: Math.max(0, maxZ - world.z),
    nz: Math.max(0, world.z - minZ),
  };
  const options = [
    { key: "px" as const, axis: "x" as const, sign: 1 },
    { key: "nx" as const, axis: "x" as const, sign: -1 },
    { key: "pz" as const, axis: "z" as const, sign: 1 },
    { key: "nz" as const, axis: "z" as const, sign: -1 },
  ].sort((a, b) => space[b.key] - space[a.key]);
  const primary = options[0];
  const secondary = options.find((item) => item.axis !== primary.axis) ?? options[1];
  const want = Math.min(3.6, Math.max(2.6, span * 1.45));
  const primaryStep = Math.min(space[primary.key] * 0.9, want);
  const secondaryStep = Math.min(space[secondary.key] * 0.72, want * 0.62);
  let camX = world.x;
  let camZ = world.z;
  if (primary.axis === "x") camX += primary.sign * primaryStep;
  else camZ += primary.sign * primaryStep;
  if (secondary.axis === "x") camX += secondary.sign * secondaryStep;
  else camZ += secondary.sign * secondaryStep;
  camX = Math.min(maxX, Math.max(minX, camX));
  camZ = Math.min(maxZ, Math.max(minZ, camZ));
  const dist = Math.hypot(camX - world.x, camZ - world.z);
  return { x: camX, y: Math.min(2.7, Math.max(1.7, dist * 0.72)), z: camZ };
}

function paint(color: string, roughness = 0.62) {
  return new THREE.MeshStandardMaterial({ color, roughness });
}

function addBox(
  group: THREE.Group,
  width: number,
  height: number,
  depth: number,
  x: number,
  y: number,
  z: number,
  color: string,
) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), paint(color));
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
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
    const head = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.04, 20), paint("#e8eef0", 0.35));
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
    const canopy = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.03, 16), paint("#d9d3c6"));
    canopy.position.y = 0.12;
    group.add(canopy);
    const shade = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, Math.max(w, 0.16) / 2, Math.max(h, 0.18), 20),
      paint("#f4d7a2", 0.4),
    );
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
    addBox(group, Math.max(w, 0.12), Math.max(h, 0.16), 0.03, 0, Math.max(h, 0.16) / 2, 0, "#f7f4ee");
    return { group, lift: 1.05 };
  }
  addBox(group, w, h, d, 0, h / 2, 0, "#e7d3b0");
  return { group, lift: 0 };
}

function photoCard(texture: THREE.Texture, width: number, height: number, z: number) {
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.MeshStandardMaterial({
    map: texture,
    color: "#ffffff",
    roughness: 0.55,
    metalness: 0.02,
    side: THREE.DoubleSide,
  });
  material.userData.photoMap = texture;
  const card = new THREE.Mesh(
    new THREE.PlaneGeometry(Math.max(width * 0.82, 0.16), Math.max(height * 0.7, 0.16)),
    material,
  );
  card.position.set(0, Math.max(height * 0.48, 0.2), z);
  card.castShadow = true;
  return card;
}

function decorate(item: Placement, width: number, depth: number, height: number, textures: Map<string, THREE.Texture>) {
  const { group, lift } = standIn(item, width, depth, height);
  const front = item.photoUrl ? textures.get(item.photoUrl) : undefined;
  const back = item.photoBackUrl ? textures.get(item.photoBackUrl) : undefined;
  if (front) {
    group.add(photoCard(front, width, height, depth * 0.5 + 0.02));
    const top = photoCard(front, Math.max(width, 0.2), Math.max(depth, 0.16), 0);
    top.rotation.x = -Math.PI / 2;
    top.position.set(0, Math.max(height * 0.72, 0.22), 0);
    group.add(top);
  }
  if (back) {
    const card = photoCard(back, width, height, -depth * 0.5 - 0.02);
    card.rotation.y = Math.PI;
    group.add(card);
  }
  if (item.substitute) {
    const tag = sprite("效果展示", 220);
    tag.scale.set(0.34, 0.1, 1);
    tag.position.set(Math.max(width * 0.46, 0.2), Math.max(height, 0.32) + 0.14, -Math.max(depth, 0.12) * 0.15);
    group.add(tag);
  }
  group.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.isMesh) {
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    }
  });
  return { group, lift };
}

async function loadTextures(urls: string[]) {
  const loader = new THREE.TextureLoader();
  const unique = [...new Set(urls.filter(Boolean))];
  const map = new Map<string, THREE.Texture>();
  await Promise.all(
    unique.map(
      (url) =>
        new Promise<void>((resolve) => {
          loader.load(
            url,
            (texture) => {
              texture.colorSpace = THREE.SRGBColorSpace;
              texture.anisotropy = 8;
              map.set(url, texture);
              resolve();
            },
            undefined,
            () => resolve(),
          );
        }),
    ),
  );
  return map;
}

type CameraApi = {
  frame: (kind: string, norm?: Aim) => void;
};

export default function RoomPlacement({
  rooms,
  placements,
  vectors,
  finish,
  officialMaps,
}: {
  rooms: { name: string; area_m2: number }[];
  placements: Placement[];
  vectors?: number[][][];
  finish?: Finish | null;
  officialMaps?: OfficialMaps;
}) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<CameraApi | null>(null);
  const shotRef = useRef<Aim | null>(null);
  const modeRef = useRef("angle");
  const [mode, setMode] = useState("angle");
  const planned = Boolean(vectors?.length || placements.some((item) => item.x != null && item.y != null));
  const signature = [
    rooms.map((room) => room.name).join(","),
    placements
      .map((item) => `${item.room}:${item.label}:${item.width_mm}:${item.x ?? ""}:${item.y ?? ""}:${item.photoUrl ?? ""}:${item.substitute ? 1 : 0}`)
      .join(","),
    vectors?.length || 0,
    finish?.styleId || "",
    finish?.floor.color || "",
    finish?.wall.feature || "",
    finish?.ceiling.feature || "",
    officialMaps?.ceiling || "",
    officialMaps?.wall || "",
    officialMaps?.floor || "",
  ].join("|");

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
    renderer.setClearColor(0xd9d2c6, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.08, 80);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0.6, 0);
    const hemi = new THREE.HemisphereLight(0xfff4e8, 0xc3b4a2, 0.62);
    const sun = new THREE.DirectionalLight(0xfff1df, 1.55);
    sun.position.set(4.5, 8.5, 3.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near = 0.4;
    sun.shadow.camera.far = 28;
    sun.shadow.camera.left = -8;
    sun.shadow.camera.right = 8;
    sun.shadow.camera.top = 8;
    sun.shadow.camera.bottom = -8;
    sun.shadow.bias = -0.0004;
    const fill = new THREE.DirectionalLight(0xd7e4ee, 0.38);
    fill.position.set(-4, 3.2, -2);
    scene.add(hemi, sun, fill, new THREE.AmbientLight(0xfff6ee, 0.28));
    const root = new THREE.Group();
    scene.add(root);
    element.appendChild(renderer.domElement);
    const floorMat = new THREE.MeshStandardMaterial({ color: "#e6d3b4", roughness: 0.55 });
    const wallMat = new THREE.MeshStandardMaterial({ color: "#f3eee6", roughness: 0.82 });
    const ceilingMat = new THREE.MeshStandardMaterial({ color: "#f7f4ee", roughness: 0.7 });
    const look = finish;
    const dress = () => {
      if (!look) return;
      applyFinish(floorMat, "floor", look.floor, look.styleId);
      applyFinish(wallMat, "wall", look.wall, look.styleId);
      applyFinish(ceilingMat, "ceiling", look.ceiling, look.styleId);
      if (floorMat.map && !officialMaps?.floor) floorMat.map.repeat.set(5.5, 3.6);
      applyOfficialMap(floorMat, officialMaps?.floor, 3.2, 3.2);
      applyOfficialMap(wallMat, officialMaps?.wall, 1.4, 1.8);
      applyOfficialMap(ceilingMat, officialMaps?.ceiling, 2, 2);
    };
    preloadFinishTextures().then(dress);
    dress();

    const resize = () => {
      const width = element.clientWidth || 360;
      const height = element.clientHeight || 320;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    resize();

    let stopped = false;
    const roomTags: THREE.Sprite[] = [];
    let roomRects: RoomRect[] = [];
    const texturesPromise = loadTextures(placements.flatMap((item) => [item.photoUrl || "", item.photoBackUrl || ""]));

    const draw = (textures: Map<string, THREE.Texture>) => {
      if (stopped) return;
      roomTags.length = 0;
      roomRects = (vectors || []).map(rectOf).filter((rect): rect is RoomRect => rect !== null);
      root.traverse((child) => {
        const mesh = child as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        const list = Array.isArray(material) ? material : material ? [material] : [];
        list.forEach((item) => {
          if (item instanceof THREE.MeshStandardMaterial && item.userData.photoMap) {
            (item.userData.photoMap as THREE.Texture).dispose();
          }
          if (item !== floorMat && item !== wallMat && item !== ceilingMat) item.dispose();
        });
      });
      root.clear();
      const usePlan = Boolean(vectors?.length || placements.some((item) => item.x != null));
      const put = (item: Placement, x: number, y: number, z: number) => {
        const displayW = item.kind === "switch_socket" ? Math.max(item.width_mm, 120) : item.width_mm;
        const displayH = item.kind === "switch_socket" ? Math.max(item.height_mm, 160) : item.height_mm;
        const w = Math.min(usePlan ? 2.4 : 1.6, Math.max(0.16, displayW / 1000));
        const d = Math.min(usePlan ? 1.6 : 1.2, Math.max(0.12, item.depth_mm / 1000));
        const h = Math.min(2.4, Math.max(0.16, displayH / 1000));
        const { group, lift } = decorate(item, w, d, h, textures);
        const hung = usePlan && item.kind === "lighting" ? 1.02 : lift;
        group.position.set(x, hung, z);
        root.add(group);
      };
      if (usePlan) {
        const slab = new THREE.Mesh(new THREE.BoxGeometry(PLAN_W, 0.08, PLAN_D), floorMat);
        slab.position.y = -0.04;
        slab.receiveShadow = true;
        root.add(slab);
        (vectors || []).forEach((line) => {
          for (let index = 0; index < line.length - 1; index += 1) {
            const [x1, y1] = line[index];
            const [x2, y2] = line[index + 1];
            const a = toWorld(x1, y1);
            const b = toWorld(x2, y2);
            const dx = b.x - a.x;
            const dz = b.z - a.z;
            const length = Math.hypot(dx, dz);
            if (length < 0.18) continue;
            const wall = new THREE.Mesh(new THREE.BoxGeometry(length, 1.15, 0.07), wallMat);
            wall.position.set((a.x + b.x) / 2, 0.575, (a.z + b.z) / 2);
            wall.rotation.y = -Math.atan2(dz, dx);
            wall.castShadow = true;
            wall.receiveShadow = true;
            root.add(wall);
          }
        });
        const cove = new THREE.MeshStandardMaterial({
          color: look?.ceiling.accent || "#e7c48a",
          emissive: look?.ceiling.accent || "#e7c48a",
          emissiveIntensity: 0.85,
          roughness: 0.42,
        });
        [
          [PLAN_W - 0.3, 0.08, 0, -PLAN_D / 2 + 0.12],
          [PLAN_W - 0.3, 0.08, 0, PLAN_D / 2 - 0.12],
          [0.08, PLAN_D - 0.3, -PLAN_W / 2 + 0.12, 0],
          [0.08, PLAN_D - 0.3, PLAN_W / 2 - 0.12, 0],
        ].forEach(([w, d, x, z]) => {
          const strip = new THREE.Mesh(new THREE.BoxGeometry(w, 0.05, d), ceilingMat);
          strip.position.set(x, 1.22, z);
          root.add(strip);
          const glow = new THREE.Mesh(new THREE.BoxGeometry(w, 0.03, Math.min(d, 0.06)), cove);
          glow.position.set(x, 1.16, z);
          root.add(glow);
        });
        placements.forEach((item) => {
          if (item.x == null || item.y == null) return;
          if (item.kind === "ceiling" || item.kind === "wall" || item.kind === "floor") {
            const spot = toWorld(item.x, item.y);
            const tag = sprite(item.label || item.room);
            tag.position.set(spot.x, item.kind === "ceiling" ? 1.28 : 0.35, spot.z);
            root.add(tag);
            return;
          }
          const spot = toWorld(item.x, item.y);
          put(item, spot.x, 0, spot.z);
          if (item.kind === "lighting") {
            const lamp = new THREE.PointLight("#ffd8aa", 4.2, 3.6, 2);
            lamp.position.set(spot.x, 1.35, spot.z);
            root.add(lamp);
          }
        });
        const labeled = new Set<string>();
        placements.forEach((item) => {
          if (item.x == null || item.y == null || labeled.has(item.room)) return;
          const spot = toWorld(item.x, item.y);
          const room = smallestRoom(roomRects, spot.x, spot.z);
          if (!room) return;
          labeled.add(item.room);
          const tag = sprite(item.room, 180);
          tag.scale.set(0.58, 0.16, 1);
          tag.position.set((room.minX + room.maxX) / 2, 1.42, room.minZ + 0.42);
          tag.userData.roomTag = true;
          root.add(tag);
          roomTags.push(tag);
        });
        const living = placements.find((item) => item.room === "客厅" && item.x != null && item.y != null);
        const anchor = living ? toWorld(living.x || 0.3, living.y || 0.4) : { x: -1.2, z: -0.4 };
        const lamp = new THREE.PointLight("#ffe0bf", 3.5, 6, 2);
        lamp.position.set(anchor.x, 1.45, anchor.z);
        root.add(lamp);
      } else {
        const list = rooms.length ? rooms : [{ name: "客厅", area_m2: 14 }];
        const columns = 4;
        list.forEach((room, index) => {
          const col = index % columns;
          const row = Math.floor(index / columns);
          const span = Math.max(1.5, Math.sqrt(room.area_m2) * 0.62);
          const x = col * 2.6;
          const z = row * 2.6;
          const slab = new THREE.Mesh(new THREE.BoxGeometry(span, 0.07, span), floorMat);
          slab.position.set(x, 0, z);
          slab.receiveShadow = true;
          root.add(slab);
          const wallH = 0.42;
          [
            [span, wallH, 0.05, x, wallH / 2, z - span / 2],
            [span, wallH, 0.05, x, wallH / 2, z + span / 2],
            [0.05, wallH, span, x - span / 2, wallH / 2, z],
            [0.05, wallH, span, x + span / 2, wallH / 2, z],
          ].forEach(([w, h, d, px, py, pz]) => {
            const wall = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wallMat);
            wall.position.set(px, py, pz);
            wall.castShadow = true;
            wall.receiveShadow = true;
            root.add(wall);
          });
          const tag = sprite(room.name);
          tag.scale.set(0.9, 0.26, 1);
          tag.position.set(x, 0.72, z);
          root.add(tag);
          const items = placements.filter((piece) => piece.room === room.name);
          const dressed = [...items];
          if (room.name === "客厅" && !dressed.some((piece) => piece.kind === "lighting" || piece.label.includes("灯"))) {
            dressed.unshift({ room: room.name, label: "示意吊灯", kind: "lighting", width_mm: 320, depth_mm: 320, height_mm: 280 });
          }
          if (room.name === "玄关" && !dressed.some((piece) => piece.kind === "entry_door" || piece.label.includes("入户门"))) {
            dressed.unshift({ room: room.name, label: "示意入户门", kind: "entry_door", width_mm: 900, depth_mm: 80, height_mm: 2100 });
          }
          if (room.name === "客厅" && !dressed.some((piece) => piece.kind === "sofa")) {
            dressed.unshift({ room: room.name, label: "示例沙发", kind: "sofa", width_mm: 2200, depth_mm: 900, height_mm: 780 });
          }
          dressed.slice(0, 6).forEach((item, piece) => {
            put(item, x - span * 0.22 + (piece % 3) * (span / 3.2), 0, z - span * 0.12 + Math.floor(piece / 3) * 0.42);
          });
        });
      }
      api.current?.frame(modeRef.current, shotRef.current || undefined);
    };

    const snap = (kind: string, place: () => void) => {
      controls.enabled = kind === "orbit";
      controls.enableDamping = false;
      controls.update();
      place();
      camera.lookAt(controls.target);
      camera.updateProjectionMatrix();
      controls.update();
      roomTags.forEach((tag) => {
        tag.visible = kind !== "piece";
      });
    };
    api.current = {
      frame(kind, norm) {
        if (kind === "front") {
          snap(kind, () => {
            camera.fov = 48;
            camera.position.set(0.15, 7.6, 3.6);
            controls.target.set(-0.35, 0.05, -1.05);
          });
        } else if (kind === "piece" && norm) {
          snap(kind, () => {
            const world = toWorld(norm.x, norm.y);
            const room = smallestRoom(roomRects, world.x, world.z);
            const large = (norm.span ?? 0) >= 1.15;
            camera.fov = large ? 50 : 42;
            const eye = room
              ? large
                ? cameraForLargePiece(room, world, norm.span ?? 1.2)
                : cameraInsideRoom(room, world)
              : { x: world.x, y: 2.2, z: world.z + 1.1 };
            camera.position.set(eye.x, eye.y, eye.z);
            controls.target.set(world.x, large ? 0.42 : 0.32, world.z);
          });
        } else if (kind === "orbit") {
          snap(kind, () => {
            camera.fov = 42;
            camera.position.set(1.6, 5.4, 4.2);
            controls.target.set(-0.5, 0.35, -0.6);
          });
          controls.enabled = true;
          controls.enableDamping = true;
        } else {
          snap(kind, () => {
            camera.fov = 42;
            camera.position.set(1.8, 5.2, 4.4);
            controls.target.set(-0.7, 0.3, -0.8);
          });
        }
      },
    };

    draw(new Map());
    texturesPromise.then((textures) => {
      if (!stopped) draw(textures);
    });

    let frameId = 0;
    const loop = () => {
      frameId = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();
    const observer = new ResizeObserver(() => resize());
    observer.observe(element);
    return () => {
      stopped = true;
      cancelAnimationFrame(frameId);
      observer.disconnect();
      controls.dispose();
      scene.environment?.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === element) element.removeChild(renderer.domElement);
      api.current = null;
    };
    // signature already folds the inputs that should rebuild the room
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  function frame(kind: string, norm?: Aim) {
    modeRef.current = kind;
    shotRef.current = norm || null;
    setMode(kind === "piece" ? `piece:${norm?.x}:${norm?.y}` : kind);
    api.current?.frame(kind, norm);
  }

  const shots: Shot[] = [];
  placements.forEach((item) => {
    if (!item.substitute || item.x == null || item.y == null) return;
    const key = `${item.room}-${item.label}`;
    if (shots.some((shot) => shot.key === key)) return;
    shots.push({
      key,
      label: item.label,
      x: item.x,
      y: item.y,
      span: Math.max(item.width_mm, item.depth_mm, item.height_mm) / 1000,
    });
  });

  return (
    <div className="scene-wrap">
      <div className="row-actions">
        <button type="button" className={mode === "front" ? "" : "secondary"} onClick={() => frame("front")}>
          正视
        </button>
        <button type="button" className={mode === "angle" ? "" : "secondary"} onClick={() => frame("angle")}>
          斜向
        </button>
        {shots.map((shot) => (
          <button
            key={shot.key}
            type="button"
            className={mode === `piece:${shot.x}:${shot.y}` ? "" : "secondary"}
            onClick={() => frame("piece", { x: shot.x, y: shot.y, span: shot.span })}
          >
            看{shot.label}
          </button>
        ))}
        <button type="button" className={mode === "orbit" ? "" : "secondary"} onClick={() => frame("orbit")}>
          旋转
        </button>
      </div>
      <div ref={host} className="scene-host" aria-label="可切换固定视角和旋转的示意房间" />
      <p className="fine">
        {planned ? (
          <>
            正视和斜向是固定视角，旋转可以拖动。
            <br />
            墙和地面按人工点的简化平面摆，不是施工图对齐。
            <br />
            天花留了灯槽，方便看见房间里的件。
          </>
        ) : (
          <>
            还没有人工点选的平面时，按房间格子示意。
            <br />
            材质和光线比单纯色块更接近样板，仍然不是施工图。
          </>
        )}
        <br />
        带「效果展示」的件只贴了照片。
        <br />
        背面没有第二张时，仍是常用外形。
        <br />
        开关这类小件会略放大，方便看清照片。
      </p>
    </div>
  );
}
