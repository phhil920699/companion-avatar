# 引擎补丁说明

第三方引擎保持上游代码，只做最小兼容性修改。所有改动都记录在此，便于升级时重放。

## 3DDFA-V3（`wang-zidu/3DDFA-V3`）

用 `engines/patches/3ddfa_v3.patch` 重放：

```bash
git clone --depth 1 https://github.com/wang-zidu/3DDFA-V3 engines/3ddfa_v3
git -C engines/3ddfa_v3 apply ../patches/3ddfa_v3.patch
```

改动内容：

1. `demo.py`：输出子目录与文件名改用 `os.path.basename` + `os.path.splitext`，修复 Windows 反斜杠路径被 `split('/')` 切错的问题。
2. `face_box/__init__.py`：`mtcnn` 改为可选导入，避免为了 retinaface 强行安装 TensorFlow。
3. `util/preprocess.py`：`np.VisibleDeprecationWarning` 改为 `getattr(..., DeprecationWarning)`，兼容 NumPy 2。
4. 全部 `torch.load(...)` 增加 `weights_only=False`，兼容 PyTorch ≥2.6 的新默认值（权重来自官方 HF 仓库，可信）。

## 3DDFA_V2（`cleardusk/3DDFA_V2`）

未打补丁。当前离线包缺少 `FaceBoxesProd.pth`，适配器在 `probe()` 阶段返回不可用。
