"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import type { MaterialSpec } from "@/lib/types";
import { applyFinish, preloadFinishTextures, shade } from "@/components/sceneTextures";
import { applyOfficialMap, type OfficialMaps } from "@/components/officialTexture";

type Look = {
  ceiling: MaterialSpec;
  floor: MaterialSpec;
  wall: MaterialSpec;
  styleId: string;
};

type SceneExtras = {
  sofaSeat: THREE.MeshStandardMaterial;
  sofaFabric: THREE.MeshStandardMaterial;
  switchMat: THREE.MeshStandardMaterial;
  switchPlate: THREE.Mesh;
};

const IX = 1.95;
const IZ = 2.7;
const H = 2.7;
const T = 0.16;

export default function ScenePreview({
  ceiling,
  floor,
  wall,
  styleId,
  sofaPhoto,
  switchPhoto,
  officialMaps,
}: Look & { sofaPhoto?: string | null; switchPhoto?: string | null; officialMaps?: OfficialMaps }) {
  const host = useRef<HTMLDivElement>(null);
  const applyRef = useRef<(() => void) | null>(null);
  const extrasRef = useRef<SceneExtras | null>(null);
  const lookRef = useRef<Look>({ ceiling, floor, wall, styleId });
  const mapsRef = useRef<OfficialMaps | undefined>(officialMaps);
  lookRef.current = { ceiling, floor, wall, styleId };
  mapsRef.current = officialMaps;

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
    renderer.setClearColor(0xd5cfc4, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.02;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    element.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    const camera = new THREE.PerspectiveCamera(56, 1, 0.08, 40);
    // Entry view: dining to the left, sofa and window to the right, ceiling in the upper frame.
    camera.position.set(-0.2, 2.02, 2.32);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minPolarAngle = 0.35;
    controls.maxPolarAngle = Math.PI / 2 - 0.02;
    controls.minDistance = 0.9;
    controls.maxDistance = 7.2;
    controls.target.set(0.35, 1.2, -0.45);

    const hemi = new THREE.HemisphereLight(0xfff4e6, 0xc8bfb2, 0.95);
    const sun = new THREE.DirectionalLight(0xfff1df, 2.35);
    sun.position.set(4.4, 5.2, -0.2);
    sun.target.position.set(-0.2, 1.1, -0.6);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near = 0.4;
    sun.shadow.camera.far = 14;
    sun.shadow.camera.left = -4.5;
    sun.shadow.camera.right = 4.5;
    sun.shadow.camera.top = 4.5;
    sun.shadow.camera.bottom = -4.5;
    sun.shadow.bias = -0.00035;
    const fill = new THREE.DirectionalLight(0xe7eef2, 0.45);
    fill.position.set(-3.2, 2.4, 2.2);
    const ambient = new THREE.AmbientLight(0xfff6ee, 0.38);
    scene.add(hemi, sun, sun.target, fill, ambient);

    const coveLights = [
      [-1.15, -1.7],
      [1.15, -1.7],
      [-1.15, 1.15],
      [1.15, 1.15],
    ].map(([x, z]) => {
      const light = new THREE.PointLight("#ffd2a0", 0, 3.4, 2);
      light.position.set(x, 2.52, z);
      scene.add(light);
      return light;
    });
    const pendantLight = new THREE.PointLight("#ffc98a", 28, 6.5, 2);
    pendantLight.position.set(-1.05, 1.95, 0.85);
    scene.add(pendantLight);

    const floorMat = new THREE.MeshStandardMaterial({ roughness: 0.45 });
    const ceilingMat = new THREE.MeshStandardMaterial({ roughness: 0.86, side: THREE.DoubleSide });
    const soffitMat = new THREE.MeshStandardMaterial({ roughness: 0.9 });
    const wallMat = new THREE.MeshStandardMaterial({ roughness: 0.82 });
    const trimMat = new THREE.MeshStandardMaterial({ roughness: 0.7 });
    const featureMat = new THREE.MeshStandardMaterial({ roughness: 0.7 });
    const metalMat = new THREE.MeshStandardMaterial({ color: "#c6a36a", metalness: 0.82, roughness: 0.28 });
    const coveMat = new THREE.MeshStandardMaterial({ color: "#f3d7a4", emissive: "#f3d7a4", emissiveIntensity: 0.8, roughness: 0.4 });
    const veneerMat = new THREE.MeshStandardMaterial({ roughness: 0.55 });
    const inlayMat = new THREE.MeshStandardMaterial({ roughness: 0.35 });
    const shellMat = new THREE.MeshStandardMaterial({ color: "#cfc6ba", roughness: 0.9 });

    const furnWood = new THREE.MeshStandardMaterial({ color: "#6a5344", roughness: 0.48 });
    const furnDark = new THREE.MeshStandardMaterial({ color: "#2a2928", roughness: 0.4, metalness: 0.08 });
    const sofaFabric = new THREE.MeshStandardMaterial({ color: "#b7aa9c", roughness: 0.9 });
    const sofaSeat = new THREE.MeshStandardMaterial({ color: "#ddd4c8", roughness: 0.86 });
    const chairSeat = new THREE.MeshStandardMaterial({ color: "#ece7df", roughness: 0.8 });
    const brass = new THREE.MeshStandardMaterial({
      color: "#c6a36a",
      metalness: 0.72,
      roughness: 0.32,
      emissive: "#8a6230",
      emissiveIntensity: 0.18,
    });
    const curtainMat = new THREE.MeshStandardMaterial({ color: "#efeae2", roughness: 0.95, side: THREE.DoubleSide });
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: "#d5e6ee",
      roughness: 0.06,
      metalness: 0,
      transmission: 0.86,
      thickness: 0.02,
      transparent: true,
      opacity: 1,
      side: THREE.DoubleSide,
    });
    const tvMat = new THREE.MeshStandardMaterial({ color: "#121417", roughness: 0.25, metalness: 0.4 });

    const groups: Record<string, THREE.Group> = {};
    const track = (name: string) => {
      const group = new THREE.Group();
      group.visible = false;
      scene.add(group);
      groups[name] = group;
      return group;
    };

    function box(
      w: number,
      h: number,
      d: number,
      x: number,
      y: number,
      z: number,
      material: THREE.Material,
      opts?: { cast?: boolean; receive?: boolean },
    ) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
      mesh.position.set(x, y, z);
      mesh.castShadow = opts?.cast ?? false;
      mesh.receiveShadow = opts?.receive ?? true;
      return mesh;
    }

    const shell = new THREE.Group();
    scene.add(shell);
    const addShell = (mesh: THREE.Mesh) => {
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      shell.add(mesh);
    };

    addShell(box(IX * 2 + T * 2, 0.14, IZ * 2 + T * 2, 0, -0.07, 0, floorMat, { receive: true }));
    addShell(box(IX * 2 + T * 2, 0.18, IZ * 2 + T * 2, 0, H + 0.09, 0, ceilingMat));

    const wallX = (length: number, height: number, cx: number, cy: number, cz: number, side: 1 | -1) =>
      box(T, height, length, side * (IX + T / 2), cy, cz, wallMat);
    const wallZ = (length: number, height: number, cx: number, cy: number, cz: number, side: 1 | -1) =>
      box(length, height, T, cx, cy, side * (IZ + T / 2), wallMat);

    const sideDoorZ0 = 0.35;
    const sideDoorZ1 = 1.45;
    const sideDoorH = 2.1;
    addShell(wallX(IZ + sideDoorZ0, H, 0, H / 2, (-IZ + sideDoorZ0) / 2, -1));
    addShell(wallX(IZ - sideDoorZ1, H, 0, H / 2, (sideDoorZ1 + IZ) / 2, -1));
    addShell(wallX(sideDoorZ1 - sideDoorZ0, H - sideDoorH, 0, (sideDoorH + H) / 2, (sideDoorZ0 + sideDoorZ1) / 2, -1));
    addShell(wallZ(IX * 2 + T * 2, H, 0, H / 2, 0, -1));

    const winZ0 = -2.2;
    const winZ1 = 0.15;
    const winY0 = 0.18;
    const winY1 = 2.48;
    addShell(wallX(IZ + winZ0, H, 0, H / 2, ( -IZ + winZ0) / 2, 1));
    addShell(wallX(IZ - winZ1, H, 0, H / 2, (winZ1 + IZ) / 2, 1));
    addShell(wallX(winZ1 - winZ0, winY0, 0, winY0 / 2, (winZ0 + winZ1) / 2, 1));
    addShell(wallX(winZ1 - winZ0, H - winY1, 0, (winY1 + H) / 2, (winZ0 + winZ1) / 2, 1));

    const doorX0 = -1.35;
    const doorX1 = -0.42;
    const doorH = 2.12;
    addShell(wallZ(IX + doorX0, H, (-IX + doorX0) / 2, H / 2, 0, 1));
    addShell(wallZ(IX - doorX1, H, (doorX1 + IX) / 2, H / 2, 0, 1));
    addShell(wallZ(doorX1 - doorX0, H - doorH, (doorX0 + doorX1) / 2, (doorH + H) / 2, 0, 1));

    const glass = new THREE.Mesh(new THREE.PlaneGeometry(winZ1 - winZ0 - 0.08, winY1 - winY0 - 0.08), glassMat);
    glass.position.set(IX - 0.02, (winY0 + winY1) / 2, (winZ0 + winZ1) / 2);
    glass.rotation.y = -Math.PI / 2;
    scene.add(glass);
    const frameMat = metalMat;
    const fz = (winZ0 + winZ1) / 2;
    scene.add(
      box(0.04, winY1 - winY0, 0.045, IX - 0.01, (winY0 + winY1) / 2, winZ0, frameMat),
      box(0.04, winY1 - winY0, 0.045, IX - 0.01, (winY0 + winY1) / 2, winZ1, frameMat),
      box(0.04, 0.045, winZ1 - winZ0, IX - 0.01, winY1, fz, frameMat),
      box(0.04, 0.045, winZ1 - winZ0, IX - 0.01, winY0, fz, frameMat),
    );
    scene.add(
      box(0.04, 2.35, 0.22, IX - 0.05, 1.28, winZ0 + 0.16, curtainMat),
      box(0.04, 2.35, 0.28, IX - 0.05, 1.28, winZ1 - 0.2, curtainMat),
    );

    const jamb = trimMat;
    scene.add(
      box(T + 0.03, doorH, 0.04, doorX0, doorH / 2, IZ - 0.01, jamb),
      box(T + 0.03, doorH, 0.04, doorX1, doorH / 2, IZ - 0.01, jamb),
      box(doorX1 - doorX0, 0.06, 0.04, (doorX0 + doorX1) / 2, doorH, IZ - 0.01, jamb),
    );

    const base = (w: number, d: number, x: number, z: number) => box(w, 0.09, d, x, 0.045, z, trimMat);
    scene.add(
      base(0.025, IZ * 2 - 0.1, -IX + 0.02, 0),
      base(0.025, IZ + winZ0 - 0.05, IX - 0.02, (-IZ + winZ0) / 2),
      base(0.025, IZ - winZ1 - 0.05, IX - 0.02, (winZ1 + IZ) / 2),
      base(IX * 2 - 0.08, 0.025, 0, -IZ + 0.02),
      base(IX + doorX0 - 0.04, 0.025, (-IX + doorX0) / 2, IZ - 0.02),
      base(IX - doorX1 - 0.04, 0.025, (doorX1 + IX) / 2, IZ - 0.02),
    );

    const cove = track("cove");
    const trough = (w: number, d: number, x: number, z: number) => box(w, 0.07, d, x, H - 0.16, z, coveMat);
    cove.add(trough(IX * 2 - 0.45, 0.07, 0, -IZ + 0.22), trough(IX * 2 - 0.45, 0.07, 0, IZ - 0.28));
    cove.add(trough(0.07, IZ * 2 - 0.55, -IX + 0.22, 0), trough(0.07, IZ * 2 - 0.55, IX - 0.28, 0));

    const tray = track("tray");
    const lip = 0.42;
    tray.add(
      box(IX * 2 - 0.2, 0.1, lip, 0, H - 0.05, -IZ + lip / 2 + 0.08, soffitMat),
      box(IX * 2 - 0.2, 0.1, lip, 0, H - 0.05, IZ - lip / 2 - 0.08, soffitMat),
      box(lip, 0.1, IZ * 2 - lip * 2, -IX + lip / 2 + 0.08, H - 0.05, 0, soffitMat),
      box(lip, 0.1, IZ * 2 - lip * 2, IX - lip / 2 - 0.08, H - 0.05, 0, soffitMat),
    );

    const veneer = track("veneer");
    for (let i = 0; i < 5; i += 1) {
      veneer.add(box(0.16, 0.02, 2.3, 0.15 + i * 0.32, H - 0.02, -0.85, veneerMat));
    }

    const cornice = track("cornice");
    const runX = (z: number, depth: number, drop: number) => box(IX * 2, drop, depth, 0, H - drop / 2, z, metalMat);
    const runZ = (x: number, depth: number, drop: number) => box(depth, drop, IZ * 2, x, H - drop / 2, 0, metalMat);
    cornice.add(runX(-IZ + 0.06, 0.1, 0.08), runX(IZ - 0.06, 0.1, 0.08), runZ(-IX + 0.06, 0.1, 0.08), runZ(IX - 0.06, 0.1, 0.08));
    cornice.add(runX(-IZ + 0.14, 0.06, 0.05), runX(IZ - 0.14, 0.06, 0.05), runZ(-IX + 0.14, 0.06, 0.05), runZ(IX - 0.14, 0.06, 0.05));

    const lightwell = track("lightwell");
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.035, 12, 48), metalMat);
    ring.rotation.x = Math.PI / 2;
    ring.position.set(0.45, H - 0.04, -0.7);
    lightwell.add(ring);

    const medallion = track("medallion");
    const disc = new THREE.Mesh(new THREE.CircleGeometry(0.28, 32), soffitMat);
    disc.rotation.x = Math.PI / 2;
    disc.position.set(0.45, H - 0.025, -0.7);
    const discRing = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.02, 10, 40), metalMat);
    discRing.rotation.x = Math.PI / 2;
    discRing.position.set(0.45, H - 0.03, -0.7);
    medallion.add(disc, discRing);

    const gold = track("gold_trough");
    gold.add(trough(IX * 2 - 0.7, 0.045, 0, -IZ + 0.28), trough(IX * 2 - 0.7, 0.045, 0, IZ - 0.34));
    gold.add(trough(0.045, IZ * 2 - 0.7, -IX + 0.28, 0), trough(0.045, IZ * 2 - 0.7, IX - 0.34, 0));

    const glossPanel = track("gloss_panel");
    glossPanel.add(box(2.15, 0.06, 1.55, 0.55, H - 0.42, 0.05, ceilingMat));
    const mirrorEdge = track("mirror_edge");
    mirrorEdge.add(
      box(2.28, 0.05, 0.06, 0.55, H - 0.42, -0.72, metalMat),
      box(2.28, 0.05, 0.06, 0.55, H - 0.42, 0.82, metalMat),
      box(0.06, 0.05, 1.6, -0.55, H - 0.42, 0.05, metalMat),
      box(0.06, 0.05, 1.6, 1.65, H - 0.42, 0.05, metalMat),
    );

    const border = track("marble_border");
    const yb = 0.012;
    border.add(
      box(IX * 2 - 0.55, 0.014, 0.16, 0, yb, -IZ + 0.38, inlayMat),
      box(IX * 2 - 0.55, 0.014, 0.16, 0, yb, IZ - 0.38, inlayMat),
      box(0.16, 0.014, IZ * 2 - 0.7, -IX + 0.38, yb, 0, inlayMat),
      box(0.16, 0.014, IZ * 2 - 0.7, IX - 0.38, yb, 0, inlayMat),
    );
    const groutLine = track("metal_grout");
    groutLine.add(box(0.035, 0.01, IZ * 2 - 0.5, 0.15, 0.01, -0.2, inlayMat));

    const tvZ = -IZ + 0.045;
    const feature = (name: string) => track(name);
    const fabric = feature("fabric_accent");
    fabric.add(box(2.15, 1.35, 0.03, 0.5, 1.45, tvZ, featureMat));
    const wainscot = feature("wainscot");
    wainscot.add(
      box(IX * 2 - 0.12, 2.35, 0.03, 0, 1.18, tvZ, featureMat),
      box(0.03, 2.35, IZ * 2 - 0.2, -IX + 0.03, 1.18, 0, featureMat),
      box(0.03, 2.35, (IZ + winZ0) - 0.1, IX - 0.03, 1.18, (-IZ + winZ0) / 2, featureMat),
      box(IX * 2 - 0.16, 0.035, 0.04, 0, 2.36, tvZ + 0.01, trimMat),
    );
    const mould = feature("moulding");
    const picture = (w: number, h: number, x: number, y: number) => {
      const t = 0.045;
      mould.add(
        box(w, t, 0.03, x, y + h / 2, tvZ, trimMat),
        box(w, t, 0.03, x, y - h / 2, tvZ, trimMat),
        box(t, h, 0.03, x - w / 2, y, tvZ, trimMat),
        box(t, h, 0.03, x + w / 2, y, tvZ, trimMat),
      );
    };
    picture(1.15, 1.7, -0.15, 1.4);
    picture(1.15, 1.7, 1.2, 1.4);
    const upholstered = feature("upholstered");
    [-0.55, 0.35, 1.25].forEach((x) => upholstered.add(box(0.72, 1.55, 0.06, x, 1.35, tvZ, featureMat)));
    const stone = feature("stone_full");
    stone.add(box(2.35, 2.45, 0.045, 0.5, 1.28, tvZ, featureMat));
    const sintered = feature("sintered");
    sintered.add(box(2.4, 2.25, 0.04, 0.5, 1.25, tvZ, featureMat));
    sintered.add(box(0.02, 2.1, 0.015, -0.45, 1.25, tvZ + 0.03, metalMat));
    sintered.add(box(0.02, 2.1, 0.015, 1.4, 1.25, tvZ + 0.03, metalMat));
    sintered.add(box(2.2, 0.02, 0.015, 0.5, 0.28, tvZ + 0.03, metalMat));
    const leather = feature("leather");
    [-0.7, 0.15, 1.0].forEach((x) => leather.add(box(0.72, 1.7, 0.05, x, 1.35, tvZ, featureMat)));

    const furniture = new THREE.Group();
    scene.add(furniture);
    const addFurn = (mesh: THREE.Object3D) => {
      mesh.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true;
          child.receiveShadow = true;
        }
      });
      furniture.add(mesh);
    };

    function chair(x: number, z: number, rotation: number) {
      const group = new THREE.Group();
      const leg = new THREE.BoxGeometry(0.04, 0.42, 0.04);
      [
        [-0.16, -0.16],
        [0.16, -0.16],
        [-0.16, 0.16],
        [0.16, 0.16],
      ].forEach(([lx, lz]) => {
        const mesh = new THREE.Mesh(leg, furnWood);
        mesh.position.set(lx, 0.21, lz);
        group.add(mesh);
      });
      const seat = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.045, 0.42), chairSeat);
      seat.position.y = 0.44;
      group.add(seat);
      const back = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.46, 0.04), furnWood);
      back.position.set(0, 0.7, -0.19);
      group.add(back);
      group.position.set(x, 0, z);
      group.rotation.y = rotation;
      return group;
    }

    const tableTop = box(1.4, 0.05, 0.8, -1.05, 0.76, 0.85, furnWood, { cast: true, receive: true });
    addFurn(tableTop);
    [
      [-1.62, 0.55],
      [-0.48, 0.55],
      [-1.62, 1.15],
      [-0.48, 1.15],
    ].forEach(([x, z]) => addFurn(box(0.055, 0.74, 0.055, x, 0.37, z, furnWood, { cast: true })));
    addFurn(chair(-1.9, 0.85, -Math.PI / 2));
    addFurn(chair(-0.2, 0.85, Math.PI / 2));
    addFurn(chair(-1.05, 0.28, 0));
    addFurn(chair(-1.05, 1.42, Math.PI));

    const sofa = new THREE.Group();
    sofa.add(box(2.05, 0.32, 0.78, 0, 0.32, 0, sofaSeat));
    sofa.add(box(2.05, 0.48, 0.14, 0, 0.66, -0.32, sofaFabric));
    sofa.add(box(0.14, 0.5, 0.78, -0.96, 0.42, 0, sofaFabric));
    sofa.add(box(0.14, 0.5, 0.78, 0.96, 0.42, 0, sofaFabric));
    sofa.add(box(0.62, 0.16, 0.2, -0.38, 0.56, -0.22, sofaFabric));
    sofa.add(box(0.62, 0.16, 0.2, 0.38, 0.56, -0.22, sofaFabric));
    sofa.position.set(0.48, 0, -0.25);
    addFurn(sofa);
    const switchMat = new THREE.MeshStandardMaterial({ color: "#f4f1ea", roughness: 0.46 });
    const switchPlate = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.3, 0.02), switchMat);
    switchPlate.position.set(1.42, 1.12, -2.52);
    switchPlate.visible = false;
    addFurn(switchPlate);
    sofaSeat.userData.baseColor = "#ddd4c8";
    sofaFabric.userData.baseColor = "#b7aa9c";
    switchMat.userData.baseColor = "#f4f1ea";
    extrasRef.current = { sofaSeat, sofaFabric, switchMat, switchPlate };
    addFurn(box(1.05, 0.035, 0.55, 0.48, 0.38, -1.05, furnDark, { cast: true, receive: true }));
    addFurn(box(0.08, 0.36, 0.08, 0.1, 0.18, -1.22, furnDark));
    addFurn(box(0.08, 0.36, 0.08, 0.86, 0.18, -1.22, furnDark));
    addFurn(box(0.08, 0.36, 0.08, 0.1, 0.18, -0.88, furnDark));
    addFurn(box(0.08, 0.36, 0.08, 0.86, 0.18, -0.88, furnDark));

    addFurn(box(1.7, 0.36, 0.38, 0.5, 0.2, -2.42, furnDark, { cast: true, receive: true }));
    const screen = box(1.28, 0.74, 0.03, 0.5, 1.28, -2.6, tvMat, { cast: false, receive: false });
    addFurn(screen);

    const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.7, 8), brass);
    cord.position.set(-1.05, H - 0.35, 0.85);
    const pendantShade = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.12, 0.18, 24), brass);
    pendantShade.position.set(-1.05, H - 0.78, 0.85);
    addFurn(cord);
    addFurn(pendantShade);

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
      applyFinish(floorMat, "floor", look.floor, look.styleId);
      applyFinish(ceilingMat, "ceiling", look.ceiling, look.styleId);
      applyFinish(wallMat, "wall", look.wall, look.styleId);
      const maps = mapsRef.current;
      applyOfficialMap(floorMat, maps?.floor, 3.2, 3.2);
      applyOfficialMap(wallMat, maps?.wall, 1.6, 2.2);
      applyOfficialMap(ceilingMat, maps?.ceiling, 2.2, 2.2);
      const featureSpec = {
        ...look.wall,
        color: look.wall.feature === "paint" || look.wall.feature === "gloss" ? look.wall.color : look.wall.accent,
        feature: look.wall.feature === "veneer" ? "wainscot" : look.wall.feature,
      };
      applyFinish(featureMat, "feature", featureSpec, look.styleId);
      applyFinish(
        veneerMat,
        "feature",
        { ...look.ceiling, color: look.ceiling.accent, feature: "veneer" },
        look.styleId,
      );
      soffitMat.color.set(shade(look.ceiling.color, 0.9));
      soffitMat.roughness = 0.88;
      trimMat.color.set(shade(look.wall.color, 0.78));
      trimMat.roughness = 0.62;

      const metalColor = look.styleId === "light_luxury" ? "#c6a36a" : look.ceiling.accent;
      metalMat.color.set(look.ceiling.feature === "mirror_edge" ? "#1a1a1a" : metalColor);
      metalMat.metalness = look.ceiling.feature === "mirror_edge" ? 0.96 : 0.78;
      metalMat.roughness = look.ceiling.feature === "mirror_edge" ? 0.08 : 0.22;
      metalMat.envMapIntensity = 1.4;
      metalMat.emissive.set("#000000");

      const glow = look.ceiling.feature === "cove" || look.ceiling.feature === "gold_trough";
      coveMat.color.set(look.ceiling.accent);
      coveMat.emissive.set(look.ceiling.accent);
      coveMat.emissiveIntensity = look.ceiling.feature === "gold_trough" ? 1.35 : 1.05;
      coveMat.metalness = look.ceiling.feature === "gold_trough" ? 0.7 : 0.04;
      coveLights.forEach((light) => {
        light.intensity = glow ? (look.ceiling.feature === "gold_trough" ? 7 : 10) : 0;
        light.color.set(look.ceiling.accent);
      });
      veneerMat.color.set(look.ceiling.accent);
      veneerMat.roughness = 0.5;
      veneerMat.metalness = 0.02;
      inlayMat.color.set(look.floor.feature === "marble_border" ? "#14110f" : look.floor.accent);
      inlayMat.metalness = look.floor.feature === "metal_grout" ? 0.75 : 0.08;
      inlayMat.roughness = look.floor.feature === "metal_grout" ? 0.25 : 0.4;

      const active = new Set([
        ...(show[look.ceiling.feature] || []),
        ...(show[look.floor.feature] || []),
        ...(show[look.wall.feature] || []),
      ]);
      Object.entries(groups).forEach(([name, group]) => {
        group.visible = active.has(name);
      });

      if (look.styleId === "cream") {
        hemi.color.set("#ffe4bc");
        hemi.groundColor.set("#e4b27a");
        hemi.intensity = 1.05;
        sun.color.set("#ffc98a");
        sun.intensity = 2.7;
        renderer.toneMappingExposure = 1.14;
        pendantLight.color.set("#ff9f3a");
        pendantLight.intensity = 20;
      } else if (look.styleId === "european") {
        hemi.color.set("#fff1d2");
        hemi.groundColor.set("#b88848");
        hemi.intensity = 0.92;
        sun.color.set("#ffe0a8");
        sun.intensity = 2.45;
        renderer.toneMappingExposure = 1.06;
        pendantLight.color.set("#d4923a");
        pendantLight.intensity = 16;
      } else {
        hemi.color.set("#d5dee6");
        hemi.groundColor.set("#5e656c");
        hemi.intensity = 0.82;
        sun.color.set("#e4edf2");
        sun.intensity = 2.05;
        renderer.toneMappingExposure = 0.94;
        pendantLight.color.set("#e4c27a");
        pendantLight.intensity = 12;
      }
    };
    applyRef.current = apply;
    preloadFinishTextures().then(() => {
      if (applyRef.current) applyRef.current();
    });
    apply();

    const resize = () => {
      const width = element.clientWidth || 360;
      const height = element.clientHeight || 420;
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
      const disposedMaterials = new Set<THREE.Material>();
      const disposedGeometries = new Set<THREE.BufferGeometry>();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          if (!disposedGeometries.has(object.geometry)) {
            disposedGeometries.add(object.geometry);
            object.geometry.dispose();
          }
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => {
            if (disposedMaterials.has(material)) return;
            disposedMaterials.add(material);
            if (material instanceof THREE.MeshStandardMaterial) {
              const owned = material.userData.ownedMaps as THREE.Texture[] | undefined;
              owned?.forEach((texture) => texture.dispose());
              const photo = material.userData.photoMap as THREE.Texture | undefined;
              photo?.dispose();
              const official = material.userData.officialMap as THREE.Texture | undefined;
              if (official && official !== photo) official.dispose();
            }
            material.dispose();
          });
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  const signature = JSON.stringify({ ceiling, floor, wall, styleId, officialMaps });
  useEffect(() => {
    applyRef.current?.();
  }, [signature]);

  useEffect(() => {
    const extras = extrasRef.current;
    if (!extras) return;
    let cancelled = false;
    const loader = new THREE.TextureLoader();
    const paintPhoto = (url: string | null | undefined, materials: THREE.MeshStandardMaterial[], mesh?: THREE.Mesh) => {
      const previous = materials[0]?.userData.photoMap as THREE.Texture | undefined;
      if (!url) {
        previous?.dispose();
        materials.forEach((material) => {
          material.map = null;
          material.userData.photoMap = null;
          material.color.set(material.userData.baseColor || "#dddddd");
          material.needsUpdate = true;
        });
        if (mesh) mesh.visible = false;
        return;
      }
      loader.load(url, (texture) => {
        if (cancelled) {
          texture.dispose();
          return;
        }
        if (previous && previous !== texture) previous.dispose();
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = 8;
        materials.forEach((material) => {
          material.map = texture;
          material.color.set("#ffffff");
          material.roughness = 0.58;
          material.userData.photoMap = texture;
          material.needsUpdate = true;
        });
        if (mesh) mesh.visible = true;
      });
    };
    paintPhoto(sofaPhoto, [extras.sofaSeat, extras.sofaFabric]);
    paintPhoto(switchPhoto, [extras.switchMat], extras.switchPlate);
    return () => {
      cancelled = true;
    };
  }, [sofaPhoto, switchPhoto]);

  return <div ref={host} className="scene-host" aria-label="拖动可旋转的客餐厅，天花、地面和墙面材质随方案变化" />;
}
