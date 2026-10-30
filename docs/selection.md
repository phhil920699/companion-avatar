# 开源选型与实测记录

环境：Windows 10/11，RTX 5060 Laptop 8GB（本原型全程 CPU），Python 3.10，Node 24。
数据抓取/实测日期：2026-10-19。

## 1. 选型表

| 环节 | 项目 | 星标 | 许可证 | 结论 |
|---|---|---|---|---|
| 照片→网格 | [wang-zidu/3DDFA-V3](https://github.com/wang-zidu/3DDFA-V3) | 400 | MIT | **采用**，CPU 12s，输出带顶点色 OBJ |
| 照片→网格（回退） | [cleardusk/3DDFA_V2](https://github.com/cleardusk/3DDFA_V2) | 3.2k | MIT | 保留代码；缺 FaceBoxes 权重，暂不可用 |
| 照片（研究） | [yfeng95/DECA](https://github.com/yfeng95/DECA) | 2.5k | 仅非商用 | 参考细节重建，不集成 |
| 照片（研究） | [SimonGiebenhain/pixel3dmm](https://github.com/SimonGiebenhain/pixel3dmm) | 532 | CC BY-NC | 参考精度方案，不集成 |
| 照片（高保真） | [aigc3d/LAM](https://github.com/aigc3d/LAM) | 1.1k | Apache-2.0 | 二期可动高斯头候选 |
| 照片（头发） | [weijielyu/FaceLift](https://github.com/weijielyu/FaceLift) | 566 | 代码 Apache-2.0 / 权重 Adobe Research | 二期候选 |
| 扫描 SfM/MVS | [colmap/colmap](https://github.com/colmap/colmap) | 13.0k | BSD-3 | **采用**（Windows 预编译包） |
| 扫描点云→网格 | [isl-org/Open3D](https://github.com/isl-org/Open3D) | 14k | MIT | **采用**，Poisson 重建 |
| 扫描备选 | [alicevision/Meshroom](https://github.com/alicevision/Meshroom) | 13k | MPL-2.0 | 备选，未集成 |
| 扫描（AGPL） | [cdcseacave/openMVS](https://github.com/cdcseacave/openMVS) | 4.2k | AGPL-3.0 | 不进入可商用组合 |
| 资产编译 | [mikedh/trimesh](https://github.com/mikedh/trimesh) | — | MIT | **采用** |
| 减面 | pymeshlab | — | GPL-3.0 | 原型采用；商用需替换 |
| 预览 | [pixiv/three-vrm](https://github.com/pixiv/three-vrm) | 2.2k | MIT | 二期 VRM 运行时 |
| 交互（二期） | [OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat) | 3.8k | Apache-2.0 | 语音对话 + 数字人参考架构 |
| 交互（二期） | [lipku/metahuman-stream](https://github.com/lipku/metahuman-stream) | 10k | Apache-2.0 | 实时推流参考 |
| 交互（二期） | [KwaiVGI/LivePortrait](https://github.com/KwaiVGI/LivePortrait) | 19k | MIT（InsightFace 模型非商用） | 驱动算法参考 |
| 语音（二期） | [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) / [FunASR](https://github.com/modelscope/FunASR) | 24k / 21k | Apache-2.0 / MIT | TTS / ASR |

## 2. 实测结果

### 3DDFA-V3（照片）

命令：

```powershell
python demo.py --inputpath test_in --savepath test_out --device cpu `
  --extractTex 1 --useTex 0 --ldm68 0 --ldm106 0 --ldm106_2d 0 --ldm134 0 `
  --seg 0 --seg_visible 0 --backbone resnet50
```

- 输入：`emma.jpg`（612×612）
- 输出：`emma_extractTex.obj` 5.6MB，35,709 顶点 / 70,789 三角面
- 全链路（含归一化、减面、GLB 导出）：**12.1 秒**（CPU）
- 资产：`low.glb` 0.39MB / 20k 面，`standard.glb` 1.36MB / 70,789 面

### 扫描件导入

- 输入：`head.glb`（LeePerrySmith，17,684 面，无贴图）
- 输出：三档 GLB 各 0.38MB，头高归一化到 0.24m
- 贴图保留验证：自建带 UV 的测试 GLB，输出仍含 1 张 image + 1 个 texture

### COLMAP / pycolmap（视频或多图）

- COLMAP 4.2.1（`colmap-x64-windows-nocuda`）已下载并解压到 `engines/colmap/`，可直接调用 `bin/colmap.exe`。
- 适配器 `scan_colmap` 实现 `feature_extractor → exhaustive_matcher → mapper → model_converter → Open3D Poisson`；完整模式额外走 `image_undistorter → patch_match_stereo → stereo_fusion`。
- COLMAP 的 Windows 包依赖 Qt 平台插件：适配器会设置 `PATH`（bin）与 `QT_PLUGIN_PATH`（plugins），与官方 `COLMAP.bat` 一致，否则会报 “Could not find the Qt platform plugin windows”。
- `pycolmap 4.2.1`（pip）作为免安装后端 `scan_pycolmap`，独立子进程执行，避免 C++ abort 带崩服务。
- 实测：three.js 环绕渲染 24 张 800×800 视图（纹理头模）→ **COLMAP 只注册 3 帧、120 点，建图失败**（图像偏暗、纹理重复）；自动回退 pycolmap 后注册 17 张、587 点 → Poisson 6,102 面，整体 **18.7 秒**，`quality=preview`。
- 结论：扫描链路具备 COLMAP → pycolmap 顺序回退；快速模式几何精度有限，正式产品建议用 COLMAP 完整 MVS 或手机 LiDAR 扫描件。

## 3. 采用的引擎补丁

见 [engines/patches/README.md](../engines/patches/README.md)，补丁文件 `engines/patches/3ddfa_v3.patch`。核心是四类：Windows 路径、mtcnn 可选导入、NumPy 2 兼容、PyTorch 2.6+ 的 `weights_only`。

## 4. 为什么不用其它方案

- **DECA / EMOCA / pixel3dmm / PIFuHD**：许可证仅限非商用，且多数依赖 FLAME 注册；原型可用，产品不可直接分发。
- **LAM / FaceLift**：质量明显更高（带头发、可动），但需要 GPU 与更大显存/磁盘；本机 8GB 先留给第二期。
- **Hunyuan3D-2 / TRELLIS**：通用图生 3D 很强，但人脸结构易变形、拓扑不适合绑定，适合当「静态手办」而非陪伴数字人。
- **OpenMVS**：AGPL-3.0，商用分发成本高。
- **Meshroom**：一条龙体验好，但 CUDA 版本与 50 系显卡兼容需现场验证，先以 COLMAP 为准。
