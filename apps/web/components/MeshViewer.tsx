"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";

export default function MeshViewer({ url, format }: { url: string; format: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [meshes, setMeshes] = useState<string[]>([]);
  const [error, setError] = useState("");
  const picked = useRef<THREE.Mesh | null>(null);
  const materials = useRef<THREE.Mesh[]>([]);

  useEffect(() => {
    const element = host.current;
    if (!element || !url) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0xe7e0d4, 1);
    const scene = new THREE.Scene();
    scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3);
    sun.position.set(2, 4, 3);
    scene.add(sun);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
    camera.position.set(1.6, 1.4, 2.2);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    element.appendChild(renderer.domElement);
    const found: THREE.Mesh[] = [];
    const add = (object: THREE.Object3D) => {
      object.traverse((child) => {
        const mesh = child as THREE.Mesh;
        if (!mesh.isMesh) return;
        mesh.geometry.computeVertexNormals();
        if (Array.isArray(mesh.material)) {
          mesh.material = mesh.material.map((item) => item.clone());
        } else {
          mesh.material = mesh.material.clone();
        }
        found.push(mesh);
      });
      const box = new THREE.Box3().setFromObject(object);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      object.position.sub(center);
      const scale = 1.6 / Math.max(size.x, size.y, size.z, 0.001);
      object.scale.setScalar(scale);
      scene.add(object);
      materials.current = found;
      setMeshes(found.map((mesh, index) => mesh.name || `网格 ${index + 1}`));
    };
    const kind = format.toLowerCase();
    const fail = () => setError("这个文件没有加载出来。请换 glTF、GLB、FBX 或 OBJ。");
    if (kind === "obj") new OBJLoader().load(url, add, undefined, fail);
    else if (kind === "fbx") new FBXLoader().load(url, add, undefined, fail);
    else new GLTFLoader().load(url, (gltf) => add(gltf.scene), undefined, fail);
    const resize = () => {
      const width = element.clientWidth || 360;
      const height = element.clientHeight || 320;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    resize();
    let frame = 0;
    const loop = () => {
      frame = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();
    return () => {
      cancelAnimationFrame(frame);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === element) element.removeChild(renderer.domElement);
    };
  }, [url, format]);

  function paint(index: number, color: string) {
    const mesh = materials.current[index];
    if (!mesh) return;
    picked.current = mesh;
    const apply = (material: THREE.Material) => {
      const standard = material as THREE.MeshStandardMaterial;
      if (standard.color) standard.color.set(color);
    };
    if (Array.isArray(mesh.material)) mesh.material.forEach(apply);
    else apply(mesh.material);
  }

  return (
    <div className="stack">
      <div ref={host} className="scene-host" />
      {error ? <p className="error">{error}</p> : null}
      {meshes.length ? <p className="fine">点开的网格可以单独换颜色。示例模型不是品牌实物。</p> : null}
      {meshes.map((name, index) => (
        <label key={`${name}-${index}`} className="row-actions">
          {name}
          <input type="color" defaultValue="#c4a574" onChange={(event) => paint(index, event.target.value)} />
        </label>
      ))}
    </div>
  );
}
