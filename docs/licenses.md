# 许可证与合规

## 1. 组件矩阵

| 组件 | 许可证 | 可商用 | 备注 |
|---|---|---|---|
| 3DDFA-V3 代码 | MIT | ✅ | 依赖的 BFM 数据默认研究授权 |
| 3DDFA-V2 代码 | MIT | ✅ | 同上 |
| COLMAP | BSD-3-Clause | ✅ | GitHub 未自动识别，以仓库 LICENSE 为准 |
| Open3D | MIT | ✅ | |
| trimesh | MIT | ✅ | |
| three.js / three-vrm | MIT | ✅ | |
| pymeshlab | GPL-3.0 | ⚠️ | 原型用；商用建议换 Open3D 减面或独立进程+法务评估 |
| Meshroom | MPL-2.0 | ✅ | 文件级 copyleft |
| OpenMVS | AGPL-3.0 | ❌ | 网络分发即触发源码义务 |
| DECA | 仅非商用科研 | ❌ | Max-Planck 许可 |
| EMOCA | 仅非商用科研 | ❌ | 同上 |
| pixel3dmm | CC BY-NC 4.0 | ❌ | |
| PIFuHD | CC BY-NC 4.0 | ❌ | 仓库已归档 |
| FaceLift 权重 | Adobe Research License | ❌ | 代码 Apache-2.0，权重另算 |
| LAM | Apache-2.0 | ✅ | 依赖的第三方模型需逐个核对 |
| LivePortrait | MIT（代码） | ⚠️ | InsightFace 检测模型非商用，需替换 |
| Duix-Mobile | Duix 社区许可 | ⚠️ | ≤1000 MAU，且需 “Powered by Duix.com” |
| Hunyuan3D-2 | 腾讯混元社区许可 | ⚠️ | 有地域/规模条件，需读原文 |
| GPT-SoVITS | MIT | ✅ | 训练音色需获得声音授权 |

## 2. 数据与模型许可

- **BFM（Basel Face Model）**：3DDFA 系列使用的三维人脸基模型，学术用途免费，商用需另行授权。
- **FLAME**：需在官网注册并同意研究条款；DECA/EMOCA/pixel3dmm 都受此约束。
- 本项目的 `meta.json` 会写入 `licenses` 字段，资产流转时可追溯。

## 3. 闸门机制

`COMPANION_PROFILE` 环境变量：

- `prototype`（默认）：加载全部适配器。
- `commercial`：只加载 manifest 中 `commercial_ok=true` 的适配器。

```powershell
$env:COMPANION_PROFILE="commercial"
python -m app.cli doctor
```

## 4. 人脸数据

- 上传件保存在 `data/uploads/<job>/`，资产在 `data/avatars/<id>/`，任务结束不自动删除。
- 运行期无外网请求；首次下载权重/二进制除外。
- 删除资产会同时清理 uploads 与 tmp；建议在产品化时增加「一键清除人脸数据」与保留期限。
- 若对外提供服务，需补充人脸信息处理告知与授权（《个人信息保护法》敏感个人信息条款）。
