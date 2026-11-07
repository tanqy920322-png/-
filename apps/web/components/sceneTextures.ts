import * as THREE from "three";
import type { MaterialSpec } from "@/lib/types";

export function mix(a: string, b: string, t: number): string {
  const parse = (color: string) => {
    const value = color.replace("#", "");
    return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)];
  };
  const from = parse(a);
  const to = parse(b);
  return `#${from
    .map((channel, index) => Math.max(0, Math.min(255, Math.round(channel + (to[index] - channel) * t))).toString(16).padStart(2, "0"))
    .join("")}`;
}

export function shade(color: string, factor: number): string {
  const value = color.replace("#", "");
  const channels = [value.slice(0, 2), value.slice(2, 4), value.slice(4, 6)].map((part) =>
    Math.max(0, Math.min(255, Math.round(parseInt(part, 16) * factor))),
  );
  return `#${channels.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

type Family = "paint" | "wood" | "parquet" | "tile" | "grout" | "stone" | "leather";

type MapSet = {
  albedo: THREE.Texture;
  roughness: THREE.Texture;
  normal: THREE.Texture;
};

const library: Partial<Record<Family, MapSet>> = {};
let loading: Promise<void> | null = null;

function configure(texture: THREE.Texture, colorSpace: THREE.ColorSpace) {
  texture.colorSpace = colorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = 8;
  texture.needsUpdate = true;
}

function loadSet(family: Family): Promise<MapSet> {
  const loader = new THREE.TextureLoader();
  const load = (file: string, colorSpace: THREE.ColorSpace) =>
    new Promise<THREE.Texture>((resolve, reject) => {
      loader.load(
        `/textures/${file}`,
        (texture) => {
          configure(texture, colorSpace);
          resolve(texture);
        },
        undefined,
        () => reject(new Error(file)),
      );
    });
  return Promise.all([
    load(`${family}-albedo.png`, THREE.SRGBColorSpace),
    load(`${family}-roughness.png`, THREE.NoColorSpace),
    load(`${family}-normal.png`, THREE.NoColorSpace),
  ]).then(([albedo, roughness, normal]) => ({ albedo, roughness, normal }));
}

export function preloadFinishTextures(): Promise<void> {
  if (!loading) {
    const families: Family[] = ["paint", "wood", "parquet", "tile", "grout", "stone", "leather"];
    loading = Promise.all(families.map((family) => loadSet(family).then((set) => {
      library[family] = set;
    }))).then(() => undefined);
  }
  return loading;
}

function floorFamily(feature: string): Family {
  if (feature === "wood") return "wood";
  if (feature === "parquet") return "parquet";
  if (feature === "metal_grout") return "grout";
  if (feature === "stone" || feature === "marble_border") return "stone";
  return "tile";
}

function featureFamily(feature: string): Family {
  if (feature === "leather" || feature === "upholstered" || feature === "fabric_accent") return "leather";
  if (feature === "stone_full" || feature === "sintered") return "stone";
  if (feature === "wainscot" || feature === "veneer") return "wood";
  return "paint";
}

function repeats(role: "floor" | "wall" | "ceiling" | "feature", family: Family, styleId: string): [number, number] {
  if (role === "floor") {
    if (family === "wood") return [1.6, 3.2];
    if (family === "parquet") return [2.4, 3.2];
    if (family === "grout") return [2.2, 3.1];
    if (family === "stone") return [1.8, 2.4];
    return styleId === "light_luxury" ? [2.2, 3.2] : [4.6, 6.4];
  }
  if (family === "leather") return [1.4, 1.6];
  if (family === "wood") return [1.2, 2.2];
  if (family === "stone") return [1.1, 1.4];
  return role === "ceiling" ? [1.6, 2.2] : [1.8, 2.4];
}

function contrastColor(hex: string): THREE.Color {
  const color = new THREE.Color(hex);
  const hsl = { h: 0, s: 0, l: 0 };
  color.getHSL(hsl);
  hsl.s = Math.min(1, hsl.s * 1.45 + 0.04);
  if (hsl.l >= 0.72) hsl.l = Math.min(0.9, hsl.l + 0.03);
  else if (hsl.l <= 0.55) hsl.l = Math.max(0.1, hsl.l - 0.14);
  color.setHSL(hsl.h, hsl.s, hsl.l);
  return color;
}

function releaseOwned(material: THREE.MeshStandardMaterial) {
  const owned = material.userData.ownedMaps as THREE.Texture[] | undefined;
  owned?.forEach((texture) => texture.dispose());
  material.userData.ownedMaps = [];
}

export function applyFinish(
  material: THREE.MeshStandardMaterial,
  role: "floor" | "wall" | "ceiling" | "feature",
  spec: MaterialSpec,
  styleId: string,
) {
  const family = role === "floor" ? floorFamily(spec.feature) : role === "feature" ? featureFamily(spec.feature) : "paint";
  const source = library[family];
  material.color.copy(contrastColor(spec.color));
  material.metalness =
    spec.feature === "mirror_edge" ? 0.94 : spec.feature === "metal_grout" ? 0.42 : spec.feature === "gloss_panel" ? 0.22 : spec.metalness;
  if (!source) {
    material.roughness = spec.roughness;
    material.needsUpdate = true;
    return;
  }
  const [repeatX, repeatY] = repeats(role, family, styleId);
  const clone = (texture: THREE.Texture, colorSpace: THREE.ColorSpace) => {
    const copy = texture.clone();
    configure(copy, colorSpace);
    copy.repeat.set(repeatX, repeatY);
    return copy;
  };
  releaseOwned(material);
  const albedo = clone(source.albedo, THREE.SRGBColorSpace);
  const roughness = clone(source.roughness, THREE.NoColorSpace);
  const normal = clone(source.normal, THREE.NoColorSpace);
  material.userData.ownedMaps = [albedo, roughness, normal];
  material.map = albedo;
  material.roughnessMap = roughness;
  material.normalMap = normal;
  material.roughness =
    spec.feature === "mirror_edge"
      ? 0.07
      : spec.feature === "gloss" || spec.feature === "gloss_panel"
        ? 0.18
        : spec.feature === "tile" || spec.feature === "metal_grout"
          ? 0.28
          : spec.feature === "wood" || spec.feature === "parquet" || spec.feature === "veneer" || spec.feature === "wainscot"
            ? 0.78
            : spec.feature === "stone" || spec.feature === "stone_full" || spec.feature === "marble_border" || spec.feature === "sintered"
              ? 0.42
              : 1;
  material.envMapIntensity = material.metalness > 0.5 || material.roughness < 0.35 ? 1.6 : 0.35;
  const normalScale = family === "paint" ? 0.12 : family === "stone" ? 0.85 : family === "tile" || family === "grout" ? 1.15 : family === "parquet" ? 1.05 : 1.25;
  material.normalScale.set(normalScale, normalScale);
  material.needsUpdate = true;
}
