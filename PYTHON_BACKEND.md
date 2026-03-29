# Python ROCm Backend

This backend keeps the same rough CLI shape as `ProVCam`, but runs inference with PyTorch instead of ONNX Runtime.

This is now the only supported product path.
The older C++/ONNX implementation has been removed from the repo.

## Why

- Current system `onnxruntime` build does not expose `ROCmExecutionProvider`.
- `MIGraphX` is unstable with the current RVM ONNX model.
- PyTorch ROCm is the most practical AMD GPU path here.

## Install

Create a virtual environment:

```bash
cd /home/ekrem/code/linux-vcam-pro
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-python-rocm.txt
```

Install a ROCm-enabled PyTorch build that matches your system. Example:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.3
```

If your installed ROCm stack is different, use the matching official PyTorch ROCm index instead.

## Run

Balanced:

```bash
/home/ekrem/code/linux-vcam-pro/run_provcam_rocm.sh \
  --camera-id 0 \
  --width 960 --height 540 \
  --fps 30 \
  --output-fps 60 \
  --output-device /dev/video2 \
  --background image \
  --background-image /home/ekrem/Pictures/wallpapers/Linux-user-Room.png
```

Lower CPU pressure:

```bash
/home/ekrem/code/linux-vcam-pro/run_provcam_rocm.sh \
  --camera-id 0 \
  --width 640 --height 360 \
  --fps 20 \
  --output-fps 60 \
  --output-device /dev/video2 \
  --background image \
  --background-image /home/ekrem/Pictures/wallpapers/Linux-user-Room.png
```

## Notes

- The model is loaded through TorchHub from the official RVM repository:
  [PeterL1n/RobustVideoMatting](https://github.com/PeterL1n/RobustVideoMatting)
- Output to the virtual camera is handled with `ffmpeg` into `/dev/videoN`.
- If `/dev/video2` does not exist, recreate the loopback device first.
- If ROCm PyTorch is unavailable, the script falls back to CPU.
