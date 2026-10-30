// 纯渲染页：固定相机、按 yaw 环绕，用于生成 COLMAP 多视角测试图。
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const params = new URLSearchParams(location.search);
const avatar = params.get("avatar");
const yaw = Number(params.get("yaw") || 0) * Math.PI / 180;
const unlit = params.get("unlit") === "1";

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("c"), antialias: true });
renderer.setSize(innerWidth, innerHeight, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.3;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101418);
const camera = new THREE.PerspectiveCamera(30, innerWidth / innerHeight, 0.001, 100);

scene.add(new THREE.HemisphereLight(0xffffff, 0x333a44, 2.4));
const key = new THREE.DirectionalLight(0xffffff, 3.0);
key.position.set(1, 1.4, 1.2);
scene.add(key);
const fill = new THREE.DirectionalLight(0xaac4ff, 1.2);
fill.position.set(-1, 0.4, -1);
scene.add(fill);

const loader = new GLTFLoader();
loader.load(`/api/avatars/${avatar}/files/standard.glb`, (gltf) => {
  const obj = gltf.scene;
  obj.traverse((n) => {
    if (!n.isMesh || !n.material) return;
    if (unlit) {
      n.material = new THREE.MeshBasicMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
        map: n.material.map || null,
      });
    } else {
      n.material.side = THREE.DoubleSide;
      // glTF 默认 metallicFactor=1，无环境贴图时顶点色模型会发黑
      if (!n.material.map) {
        n.material.metalness = 0.0;
        n.material.roughness = 0.85;
      }
    }
  });
  scene.add(obj);

  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z);
  const dist = radius / Math.tan((camera.fov * Math.PI) / 360) * 1.02;
  camera.position.set(center.x + Math.sin(yaw) * dist, center.y, center.z + Math.cos(yaw) * dist);
  camera.lookAt(center);
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  window.__ready = true;
});
