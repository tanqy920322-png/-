import * as THREE from "three";

export type OfficialMaps = {
  ceiling?: string | null;
  wall?: string | null;
  floor?: string | null;
};

export function applyOfficialMap(
  material: THREE.MeshStandardMaterial,
  url: string | null | undefined,
  repeatX: number,
  repeatY: number,
) {
  if (!url) return;
  const loader = new THREE.TextureLoader();
  loader.load(url, (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(repeatX, repeatY);
    texture.anisotropy = 8;
    const previous = material.userData.officialMap as THREE.Texture | undefined;
    if (previous && previous !== texture) previous.dispose();
    material.map = texture;
    material.color.set("#ffffff");
    material.roughness = Math.min(material.roughness, 0.72);
    material.userData.officialMap = texture;
    material.needsUpdate = true;
  });
}
