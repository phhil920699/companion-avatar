import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const canvas = document.getElementById("canvas");
const viewer = document.getElementById("viewer");
const statsEl = document.getElementById("stats");
const emptyEl = document.getElementById("empty");
const tiersEl = document.getElementById("tiers");
const deleteBtn = document.getElementById("delete-btn");
const jobsEl = document.getElementById("jobs");
const avatarsEl = document.getElementById("avatars");

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.35;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f1216);

const camera = new THREE.PerspectiveCamera(35, 1, 0.001, 100);
camera.position.set(0, 0.16, 0.5);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.autoRotate = true;
controls.autoRotateSpeed = 1.2;

scene.add(new THREE.HemisphereLight(0xffffff, 0x2a3442, 2.4));
const key = new THREE.DirectionalLight(0xffffff, 3.2);
key.position.set(0.6, 0.8, 0.9);
scene.add(key);
const fill = new THREE.DirectionalLight(0x9fc4ff, 1.0);
fill.position.set(-0.8, 0.2, -0.6);
scene.add(fill);
const rim = new THREE.DirectionalLight(0xffe6c8, 1.0);
rim.position.set(0, 0.4, -1);
scene.add(rim);

const grid = new THREE.GridHelper(1.2, 24, 0x2c3846, 0x1c242e);
grid.position.y = 0;
scene.add(grid);

const loader = new GLTFLoader();
const state = { object: null, meta: null, avatarId: null, tier: null, loading: false };

function resize() {
  const w = viewer.clientWidth;
  const h = viewer.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewer);
resize();

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

function clearObject() {
  if (!state.object) return;
  scene.remove(state.object);
  state.object.traverse((n) => {
    if (n.geometry) n.geometry.dispose();
    if (n.material) {
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      mats.forEach((m) => m.dispose());
    }
  });
  state.object = null;
}

function frameObject(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  controls.target.copy(center);
  const maxDim = Math.max(size.x, size.y, size.z);
  const distance = maxDim / Math.tan((camera.fov * Math.PI) / 360) * 0.9;
  camera.position.set(center.x, center.y + size.y * 0.05, center.z + distance);
  camera.near = Math.max(distance / 100, 0.001);
  camera.far = distance * 20;
  camera.updateProjectionMatrix();
  controls.update();
}

async function loadTier(tier) {
  if (!state.meta || state.loading) return;
  const tierMeta = state.meta.tiers[tier];
  if (!tierMeta) return;
  state.loading = true;
  emptyEl.hidden = true;
  try {
    const url = `/api/avatars/${state.avatarId}/files/${tierMeta.file}?t=${Date.now()}`;
    const gltf = await loader.loadAsync(url);
    clearObject();
    const obj = gltf.scene;
    obj.traverse((n) => {
      if (n.isMesh && n.material) {
        n.material.side = THREE.DoubleSide;  // 单图人脸是开放曲面，双面渲染避免露黑
        if (n.material.map) {
          n.material.map.colorSpace = THREE.SRGBColorSpace;
        } else {
          // glTF 默认 metallicFactor=1，顶点色模型会发黑
          n.material.metalness = 0.0;
          n.material.roughness = 0.85;
        }
      }
    });
    scene.add(obj);
    state.object = obj;
    state.tier = tier;
    frameObject(obj);
    renderTiers();
    const mb = (tierMeta.bytes / 1024 / 1024).toFixed(2);
    statsEl.textContent = `${tier.toUpperCase()} · ${tierMeta.tris.toLocaleString()} 面 · ${mb} MB · 高度 ${state.meta.height_m ?? "-"} m`;
  } catch (err) {
    statsEl.textContent = `加载失败：${err.message}`;
  } finally {
    state.loading = false;
  }
}

function renderTiers() {
  tiersEl.innerHTML = "";
  if (!state.meta) return;
  Object.keys(state.meta.tiers).forEach((tier) => {
    const btn = document.createElement("button");
    btn.textContent = tier;
    btn.className = tier === state.tier ? "active" : "";
    btn.onclick = () => loadTier(tier);
    tiersEl.appendChild(btn);
  });
}

async function selectAvatar(id, preferred = "standard") {
  const meta = await api(`/api/avatars/${id}`);
  state.avatarId = id;
  state.meta = meta;
  emptyEl.hidden = true;
  deleteBtn.hidden = false;
  document.querySelectorAll("#avatars li").forEach((li) => {
    li.classList.toggle("active", li.dataset.id === id);
  });
  const tier = meta.tiers[preferred] ? preferred : Object.keys(meta.tiers)[0];
  await loadTier(tier);
}

async function refreshAvatars() {
  const items = await api("/api/avatars");
  avatarsEl.innerHTML = "";
  if (!items.length) {
    avatarsEl.innerHTML = '<li class="tag">还没有资产</li>';
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.dataset.id = item.avatar_id;
    const tiers = Object.keys(item.tiers || {}).join(" / ");
    li.innerHTML = `<b>${item.engine || "unknown"}</b> · ${item.source_kind || ""}<br>
      <span class="tag">${tiers} · ${item.quality || ""}</span>`;
    li.onclick = () => selectAvatar(item.avatar_id).catch((e) => (statsEl.textContent = e.message));
    if (item.avatar_id === state.avatarId) li.classList.add("active");
    avatarsEl.appendChild(li);
  });
  if (!state.avatarId && items.length) {
    const wanted = new URLSearchParams(location.search).get("avatar");
    const target = items.find((i) => i.avatar_id === wanted) || items[0];
    selectAvatar(target.avatar_id).catch(() => {});
  }
}

async function refreshCapabilities() {
  const data = await api("/api/capabilities");
  const capsEl = document.getElementById("capabilities");
  const parts = data.adapters.map(
    (a) =>
      `<span class="${a.available ? "ok" : "bad"}">${a.available ? "●" : "○"} ${a.id}</span>`
  );
  capsEl.innerHTML = `${parts.join(" ")} <span>磁盘 ${data.free_gb} GB · ${data.profile}</span>`;
}

function addJobRow(id, label) {
  const li = document.createElement("li");
  li.dataset.id = id;
  li.innerHTML = `<b>${label}</b><br><span class="tag">排队中…</span>`;
  jobsEl.prepend(li);
  return li;
}

async function submitJob(kind, input, button, label) {
  const file = input.files?.[0];
  if (!file) return;
  button.disabled = true;
  const form = new FormData();
  form.append("kind", kind);
  form.append("files", file);
  let job;
  try {
    job = await api("/api/jobs", { method: "POST", body: form });
  } catch (err) {
    alert(`提交失败：${err.message}`);
    button.disabled = false;
    return;
  }
  const row = addJobRow(job.id, label);
  const started = Date.now();
  const timer = setInterval(async () => {
    try {
      const j = await api(`/api/jobs/${job.id}`);
      const secs = ((Date.now() - started) / 1000).toFixed(0);
      const status = j.status;
      const color = status === "failed" ? "err" : "";
      row.innerHTML = `<b>${label}</b> · ${secs}s<br><span class="${color}">${status} ${j.stage || ""}</span>`;
      if (["succeeded", "failed", "canceled"].includes(status)) {
        clearInterval(timer);
        button.disabled = false;
        if (status === "succeeded") {
          await refreshAvatars();
          await selectAvatar(j.id);
        } else if (j.error) {
          row.innerHTML += `<br><span class="err">${j.error}</span>`;
        }
      }
    } catch {
      clearInterval(timer);
      button.disabled = false;
    }
  }, 1000);
}

document.getElementById("photo-btn").onclick = () =>
  submitJob("photo", document.getElementById("photo-file"), document.getElementById("photo-btn"), "照片");

document.getElementById("scan-btn").onclick = () =>
  submitJob("scan_upload", document.getElementById("scan-file"), document.getElementById("scan-btn"), "扫描件");

document.getElementById("video-btn").onclick = () =>
  submitJob("scan_video", document.getElementById("video-file"), document.getElementById("video-btn"), "环绕视频");

document.getElementById("autorotate").onchange = (e) => {
  controls.autoRotate = e.target.checked;
};

deleteBtn.onclick = async () => {
  if (!state.avatarId || !confirm("删除该资产？")) return;
  await fetch(`/api/avatars/${state.avatarId}`, { method: "DELETE" });
  clearObject();
  state.avatarId = null;
  state.meta = null;
  state.tier = null;
  tiersEl.innerHTML = "";
  deleteBtn.hidden = true;
  emptyEl.hidden = false;
  statsEl.textContent = "未加载模型";
  refreshAvatars();
};

refreshCapabilities().catch((e) => {
  document.getElementById("capabilities").textContent = `服务未连接：${e.message}`;
});
refreshAvatars().catch(() => {});
