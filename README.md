# ProVCam

<p align="center">
  <img src="assets/provcam.svg" width="128" alt="ProVCam">
</p>

<p align="center">
  <strong>Virtual Camera with AI Background Replacement for Linux</strong>
</p>

<p align="center">
  <a href="https://github.com/ekremx25/provcam/releases">Download AppImage</a>
</p>

---

## Demo

<p align="center">
  <video src="https://github.com/ekremx25/provcam/releases/download/v0.1.0/provcam-demo-720p.mp4" width="720" controls>
    Your browser does not support the video tag.
  </video>
</p>

https://github.com/user-attachments/assets/provcam-demo

https://github.com/ekremx25/provcam/releases/download/v0.1.0/provcam-demo-720p.mp4

---

## What is this?

ProVCam is a virtual camera application for Linux that uses **AI-powered real-time background removal** and replacement. It works with any video conferencing app (Zoom, Google Meet, Discord, OBS, etc.) by creating a virtual `/dev/video` device.

Powered by [RobustVideoMatting](https://github.com/PeterL1n/RobustVideoMatting) with **AMD ROCm GPU acceleration** via PyTorch.

## Features

- **Real-time AI background removal** using RobustVideoMatting model
- **Background modes**: Image, blur, solid color, transparent
- **AMD ROCm GPU acceleration** via PyTorch (falls back to CPU)
- **Virtual camera output** via v4l2loopback (`/dev/videoN`)
- **GUI control panel** with resolution, FPS, background settings
- **Multiple resolutions**: 640x360 to 1920x1080
- **Configurable FPS**: Input and output FPS control
- **Auto-start on boot** option
- **AppImage packaging** - single file, no install needed

## How It Works

```
Physical Camera → AI Model (ROCm GPU) → Background Replacement → Virtual Camera
   /dev/video0      RobustVideoMatting        Image/Blur/Color      /dev/video2
                                                                         ↓
                                                                  Zoom / Meet / OBS
```

## Installation

### AppImage (Recommended)

1. Download `ProVCam-x86_64.AppImage` from [Releases](https://github.com/ekremx25/provcam/releases)
2. Make executable and run:
   ```bash
   chmod +x ProVCam-x86_64.AppImage
   ./ProVCam-x86_64.AppImage
   ```

### Requirements

- **Linux** (x86_64)
- **v4l2loopback** kernel module (for virtual camera device)
- **ffmpeg** (for video output)
- **Python 3** with PyTorch ROCm (for GPU acceleration)

#### Setup v4l2loopback

```bash
# Install
sudo pacman -S v4l2loopback-dkms  # Arch
# sudo apt install v4l2loopback-dkms  # Ubuntu

# Load module
sudo modprobe v4l2loopback devices=1 video_nr=2 card_label="ProVCam" exclusive_caps=1
```

### Build from Source

```bash
git clone https://github.com/ekremx25/provcam.git
cd provcam

# Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-python-rocm.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.3

# Run
./launch_provcam_gui.sh
```

## Usage

### GUI Mode
```bash
./launch_provcam_gui.sh
```
Opens a control panel where you can:
- Select camera and resolution
- Choose background mode (image/blur/color)
- Pick background image
- Start/stop the virtual camera
- Monitor status and logs

### CLI Mode
```bash
./run_provcam_rocm.sh \
  --camera-id 0 \
  --width 960 --height 540 \
  --fps 30 \
  --output-fps 60 \
  --output-device /dev/video2 \
  --background image \
  --background-image ~/Pictures/background.png
```

## Project Structure

```
├── python/
│   ├── provcam_capture_proxy.py   # Camera capture
│   ├── provcam_gui.py             # Tkinter GUI
│   ├── provcam_installer.py       # Setup helper
│   ├── provcam_io.py              # I/O handling
│   ├── provcam_output_writer.py   # Virtual camera output
│   ├── provcam_reset_output.py    # Reset output device
│   └── provcam_rocm.py            # ROCm GPU inference
├── scripts/
│   ├── provcam_appimage_launcher.sh
│   ├── provcam_reload_loopback_root.sh
│   └── provcam_supervisor.sh
├── assets/
│   ├── provcam.svg                # App icon
│   └── provcam.appdata.xml        # AppStream metadata
├── launch_provcam_app.sh          # Start virtual camera
├── launch_provcam_gui.sh          # Start GUI
├── stop_provcam_app.sh            # Stop virtual camera
├── setup_provcam.sh               # Initial setup
├── build_appimage.sh              # Build AppImage
└── PYTHON_BACKEND.md              # ROCm backend docs
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Model | RobustVideoMatting (TorchHub) |
| GPU Acceleration | AMD ROCm + PyTorch |
| Virtual Camera | v4l2loopback + ffmpeg |
| GUI | Python Tkinter |
| Packaging | AppImage |

## License

MIT
