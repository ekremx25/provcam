# ProVCam - AI Virtual Camera for Linux
<p align="center">
  <img src="assets/provcam.svg" width="128" alt="ProVCam">
</p>

<p align="center">
  <strong>AI virtual camera for Linux with real-time background replacement</strong>
</p>

<p align="center">
  <em>Runs on AMD Radeon (ROCm) · drops straight into OBS / Zoom / Google Meet / Discord</em>
</p>

ProVCam is an AI virtual camera for Linux that provides real-time background replacement, blur, green screen, and webcam output through `v4l2loopback`. It is designed for Wayland and X11 desktops, ships as AppImage builds, and works with OBS, Zoom, Google Meet, Discord, and other webcam-enabled apps.


---

## Keywords

`linux` · `virtual-camera` · `webcam` · `v4l2loopback` · `background-replacement` · `ai-background-removal` · `rocm` · `amd` · `appimage` · `obs` · `zoom` · `wayland` · `python` · `rust` · `video`

---

## Demo

https://github.com/user-attachments/assets/03c9a519-4ffa-466f-a032-6c5f26cd01f5

---

## Download

Two editions ship side-by-side. Pick one, make it executable, run it.

| Edition | File | Size | Backend | When to pick |
|---|---|---|---|---|
| **Rust** (recommended) | [`ProVCam-Rust-x86_64.AppImage`](ProVCam-Rust-x86_64.AppImage) | ~1.1 MB | Rust inference + Python fallback | Faster startup, lower RAM, single binary |
| **Python** | [`ProVCam-Python-x86_64.AppImage`](ProVCam-Python-x86_64.AppImage) | ~230 KB | Pure Python / PyTorch | Easier to modify and extend |

```bash
# Rust edition (recommended)
chmod +x ProVCam-Rust-x86_64.AppImage
./ProVCam-Rust-x86_64.AppImage
```

First run copies the payload to `~/.local/share/provcam/` and opens the installer (creates the `.venv`, installs PyTorch ROCm, pre-caches the AI model). Later runs go straight to the GUI.

---

## What is it

ProVCam takes your physical webcam (or a phone camera via Iriun), runs [RobustVideoMatting](https://github.com/PeterL1n/RobustVideoMatting) to remove the background, composites the foreground onto a blurred / green / black / custom image, and pipes the result into a `v4l2loopback` device that any Linux app can treat as a regular webcam.

Built for **AMD Radeon** cards where ONNX Runtime's ROCm support is missing. Falls back to CPU when ROCm isn't available.

### Features

- 🎭 AI background removal — RVM models, cached for offline use
- 🖼 Background modes: blur, custom image, green, black
- 🎚 Matte profiles: `clean`, `balanced`, `soft`
- ⚡ AMD GPU acceleration via PyTorch ROCm (FP16 when supported)
- 🛡 Supervisor with automatic fps/resolution downgrade on failures
- 🧩 Zero-copy IPC (`mmap` seqlock) between capture / inference / output processes
- 🖱 CustomTkinter GUI with live preview
- 📦 Self-contained AppImage — no manual install required

---

## Requirements

- Linux with **Wayland or X11**
- **AMD Radeon** GPU with ROCm support (or any GPU for CPU fallback)
- **`v4l2loopback`** kernel module — the first-run installer sets it up for you
- **Python 3.9+**
- **`tk`** — Tkinter runtime for the GUI. Install once:

  ```bash
  # Arch / Manjaro
  yay -S tk            # or: sudo pacman -S tk

  # Debian / Ubuntu
  sudo apt install python3-tk

  # Fedora
  sudo dnf install python3-tkinter
  ```

  All other Python dependencies (PyTorch ROCm, OpenCV, CustomTkinter, numpy) are installed automatically into the app's own venv on first run.

---

## Troubleshooting

The installer covers the common cases (venv, PyTorch ROCm, `v4l2loopback`, Iriun autostart). If something goes wrong:

- **No `ProVCam Output` in Zoom/OBS** — `v4l2loopback` isn't loaded. Run `setup_boot_autostart.sh` from `~/.local/share/provcam/app/` once.
- **Permission denied on `/dev/video2`** — add your user to the `video` group: `sudo usermod -aG video "$USER"` (log out & back in).
- **GPU not detected** — verify `rocminfo` shows your GPU; reinstall the matching PyTorch ROCm wheel.

Logs live at `~/.cache/provcam/provcam_gpu.log`.

---

## Source code

This repository ships the **prebuilt AppImages only**. The source tree (Python backend, shell launchers, Rust inference crate, build scripts) lives at **`~/.local/share/provcam/app/`** on any machine that has run the AppImage once — it's self-extracting. From there:

```bash
cd ~/.local/share/provcam/app
./build_appimage.sh        # rebuild your own AppImage
pytest tests/              # run the test suite
```

---

## Links

- YouTube tutorials and Linux desktop videos: [@linuxlifex](https://www.youtube.com/@linuxlifex)
- GitHub profile: [ekremx25](https://github.com/ekremx25)

---

## Licence

[MIT](LICENSE) — do what you want, just don't claim warranty.
