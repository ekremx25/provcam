#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = Path.home() / ".cache" / "provcam"
CONFIG_DIR = Path.home() / ".config" / "provcam"
CONFIG_FILE = CONFIG_DIR / "settings.json"
PID_FILE = LOG_DIR / "provcam_gpu.pid"
LOG_FILE = LOG_DIR / "provcam_gpu.log"
START_SCRIPT = ROOT_DIR / "launch_provcam_app.sh"
STOP_SCRIPT = ROOT_DIR / "stop_provcam_app.sh"
REPAIR_SCRIPT = ROOT_DIR / "repair_provcam_output.sh"
HARD_REPAIR_SCRIPT = ROOT_DIR / "repair_provcam_hard.sh"
RESOLUTION_OPTIONS = (
    "640x360",
    "768x432",
    "960x540",
    "1024x576",
    "1280x720",
    "1600x900",
    "1920x1080",
)


class ProVCamApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ProVCam GPU")
        self.root.geometry("620x540")
        self.root.minsize(580, 500)
        self.root.configure(bg="#111318")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#111318")
        style.configure("Card.TFrame", background="#171b22")
        style.configure("Title.TLabel", background="#111318", foreground="#f5f7fb", font=("DejaVu Sans", 18, "bold"))
        style.configure("Body.TLabel", background="#171b22", foreground="#d4d8e1", font=("DejaVu Sans", 10))
        style.configure("Status.TLabel", background="#171b22", foreground="#8ce99a", font=("DejaVu Sans", 10, "bold"))
        style.configure("Muted.TLabel", background="#171b22", foreground="#97a0af", font=("DejaVu Sans", 9))
        style.configure("Action.TButton", font=("DejaVu Sans", 10, "bold"), padding=8)
        style.configure("Field.TLabel", background="#171b22", foreground="#cfd5df", font=("DejaVu Sans", 10, "bold"))

        main = ttk.Frame(root, style="Root.TFrame", padding=18)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="ProVCam GPU", style="Title.TLabel").pack(anchor="w")

        card = ttk.Frame(main, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True, pady=(14, 0))

        ttk.Label(
            card,
            text="Virtual camera with AMD GPU backend. When started, it streams ProVCam Output through /dev/video2.",
            style="Body.TLabel",
            wraplength=440,
            justify="left",
        ).pack(anchor="w")

        self.status_var = tk.StringVar(value="Checking status...")
        self.detail_var = tk.StringVar(value="")
        self.camera_id_var = tk.StringVar(value="0")
        self.camera_device_var = tk.StringVar(value="/dev/video0")
        self.width_var = tk.StringVar(value="960")
        self.height_var = tk.StringVar(value="540")
        self.resolution_var = tk.StringVar(value="960x540")
        self.fps_var = tk.StringVar(value="20")
        self.output_fps_var = tk.StringVar(value="60")
        self.output_device_var = tk.StringVar(value="/dev/video2")
        self.backbone_var = tk.StringVar(value="mobilenetv3")
        self.matte_mode_var = tk.StringVar(value="balanced")
        self.preset_var = tk.StringVar(value="custom")
        self.background_mode_var = tk.StringVar(value="blur")
        self.background_image_var = tk.StringVar(value=str(Path.home() / "Pictures" / "wallpapers" / "Linux-user-Room.png"))
        self.auto_preview_var = tk.BooleanVar(value=True)
        self.preview_process: subprocess.Popen | None = None

        self.load_settings()

        ttk.Label(card, textvariable=self.status_var, style="Status.TLabel").pack(anchor="w", pady=(14, 2))
        ttk.Label(card, textvariable=self.detail_var, style="Muted.TLabel", wraplength=440, justify="left").pack(anchor="w")

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x", pady=(16, 8))

        self.add_labeled_entry(form, "Camera ID", self.camera_id_var, 0, 0)
        self.add_labeled_entry(form, "Camera Device", self.camera_device_var, 0, 1)
        self.add_labeled_entry(form, "Output Device", self.output_device_var, 2, 2)
        ttk.Label(form, text="Resolution", style="Field.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 4))
        resolution_box = ttk.Combobox(
            form,
            textvariable=self.resolution_var,
            values=RESOLUTION_OPTIONS,
            state="readonly",
            width=18,
        )
        resolution_box.grid(row=3, column=0, sticky="ew", padx=(0, 10))
        resolution_box.bind("<<ComboboxSelected>>", self.apply_resolution)

        self.add_labeled_entry(form, "Width", self.width_var, 2, 1)
        self.add_labeled_entry(form, "Height", self.height_var, 4, 1)
        self.add_labeled_entry(form, "AI FPS", self.fps_var, 4, 0)
        self.add_labeled_entry(form, "Output FPS", self.output_fps_var, 4, 2)
        ttk.Label(
            form,
            text="(in failure mode the supervisor caps this at 30)",
            style="Muted.TLabel",
        ).grid(row=6, column=2, sticky="w", pady=(0, 4))

        ttk.Label(form, text="Preset", style="Field.TLabel").grid(row=6, column=0, sticky="w", pady=(10, 4))
        preset_box = ttk.Combobox(
            form,
            textvariable=self.preset_var,
            values=("custom", "720p_quality", "720p_hybrid", "540p_balanced", "540p_fast", "eco_image"),
            state="readonly",
            width=18,
        )
        preset_box.grid(row=7, column=0, sticky="ew", padx=(0, 10))
        preset_box.bind("<<ComboboxSelected>>", self.apply_preset)

        ttk.Label(form, text="Model", style="Field.TLabel").grid(row=6, column=1, sticky="w", pady=(10, 4))
        backbone_box = ttk.Combobox(
            form,
            textvariable=self.backbone_var,
            values=("mobilenetv3", "hybrid", "resnet50"),
            state="readonly",
            width=18,
        )
        backbone_box.grid(row=7, column=1, sticky="ew", padx=(0, 10))

        ttk.Label(form, text="Edge Mode", style="Field.TLabel").grid(row=6, column=2, sticky="w", pady=(10, 4))
        matte_box = ttk.Combobox(
            form,
            textvariable=self.matte_mode_var,
            values=("balanced", "clean", "soft"),
            state="readonly",
            width=18,
        )
        matte_box.grid(row=7, column=2, sticky="ew")

        ttk.Label(form, text="Background Mode", style="Field.TLabel").grid(row=8, column=0, sticky="w", pady=(10, 4))
        mode_box = ttk.Combobox(
            form,
            textvariable=self.background_mode_var,
            values=("image", "blur", "black", "green"),
            state="readonly",
            width=18,
        )
        mode_box.grid(row=9, column=0, sticky="ew", padx=(0, 10))

        ttk.Label(form, text="Background Image", style="Field.TLabel").grid(row=8, column=1, columnspan=2, sticky="w", pady=(10, 4))
        image_row = ttk.Frame(form, style="Card.TFrame")
        image_row.grid(row=9, column=1, columnspan=2, sticky="ew")
        ttk.Entry(image_row, textvariable=self.background_image_var).pack(side="left", fill="x", expand=True)
        ttk.Button(image_row, text="Browse", command=self.browse_background).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(form, text="Open test preview on start", variable=self.auto_preview_var).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=1)

        button_row = ttk.Frame(card, style="Card.TFrame")
        button_row.pack(fill="x", pady=(12, 10))

        self.start_button = ttk.Button(button_row, text="Start", style="Action.TButton", command=self.start_backend)
        self.start_button.pack(side="left")

        self.stop_button = ttk.Button(button_row, text="Stop", style="Action.TButton", command=self.stop_backend)
        self.stop_button.pack(side="left", padx=(10, 0))

        self.repair_button = ttk.Button(button_row, text="Hard Repair", style="Action.TButton", command=self.repair_backend)
        self.repair_button.pack(side="left", padx=(10, 0))

        ttk.Button(button_row, text="Open Log", style="Action.TButton", command=self.open_log).pack(side="left", padx=(10, 0))
        ttk.Button(button_row, text="Close", style="Action.TButton", command=self.root.destroy).pack(side="right")

        ttk.Separator(card).pack(fill="x", pady=10)

        ttk.Label(
            card,
            text="Change the settings and click Start. You can use Browse to choose a background image.",
            style="Muted.TLabel",
            justify="left",
        ).pack(anchor="w")

        self.refresh_status()
        self.root.after(1500, self.poll_status)

    def add_labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int, column: int) -> None:
        ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=column, sticky="w", pady=(8, 4))
        ttk.Entry(parent, textvariable=variable).grid(row=row + 1, column=column, sticky="ew", padx=(0, 10 if column == 0 else 0))

    def browse_background(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose Background Image",
            initialdir=str(Path.home() / "Pictures"),
            filetypes=(
                ("Image files", "*.png *.jpg *.jpeg *.webp"),
                ("All files", "*.*"),
            ),
        )
        if filename:
            self.background_image_var.set(filename)

    def load_settings(self) -> None:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            self.resolution_var.set(f"{self.width_var.get()}x{self.height_var.get()}")
            return
        self.camera_id_var.set(str(data.get("camera_id", self.camera_id_var.get())))
        self.camera_device_var.set(str(data.get("camera_device", self.camera_device_var.get())))
        self.width_var.set(str(data.get("width", self.width_var.get())))
        self.height_var.set(str(data.get("height", self.height_var.get())))
        self.resolution_var.set(str(data.get("resolution", f"{self.width_var.get()}x{self.height_var.get()}")))
        self.fps_var.set(str(data.get("fps", self.fps_var.get())))
        self.output_fps_var.set(str(data.get("output_fps", self.output_fps_var.get())))
        self.output_device_var.set(str(data.get("output_device", self.output_device_var.get())))
        self.preset_var.set(str(data.get("preset", self.preset_var.get())))
        self.backbone_var.set(str(data.get("backbone", self.backbone_var.get())))
        self.matte_mode_var.set(str(data.get("matte_mode", self.matte_mode_var.get())))
        self.background_mode_var.set(str(data.get("background_mode", self.background_mode_var.get())))
        self.background_image_var.set(str(data.get("background_image", self.background_image_var.get())))
        self.auto_preview_var.set(bool(data.get("auto_preview", self.auto_preview_var.get())))

    def save_settings(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "camera_id": self.camera_id_var.get().strip(),
            "camera_device": self.camera_device_var.get().strip(),
            "width": self.width_var.get().strip(),
            "height": self.height_var.get().strip(),
            "resolution": self.resolution_var.get().strip(),
            "fps": self.fps_var.get().strip(),
            "output_fps": self.output_fps_var.get().strip(),
            "output_device": self.output_device_var.get().strip(),
            "preset": self.preset_var.get().strip(),
            "backbone": self.backbone_var.get().strip(),
            "matte_mode": self.matte_mode_var.get().strip(),
            "background_mode": self.background_mode_var.get().strip(),
            "background_image": self.background_image_var.get().strip(),
            "auto_preview": bool(self.auto_preview_var.get()),
        }
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    def apply_resolution(self, _event=None) -> None:
        value = self.resolution_var.get().strip().lower()
        if "x" not in value:
            return
        width, height = value.split("x", 1)
        self.width_var.set(width)
        self.height_var.set(height)

    def apply_preset(self, _event=None) -> None:
        preset = self.preset_var.get().strip()
        if preset == "720p_quality":
            self.resolution_var.set("1280x720")
            self.apply_resolution()
            self.fps_var.set("20")
            self.output_fps_var.set("30")
            self.backbone_var.set("resnet50")
            self.matte_mode_var.set("clean")
        elif preset == "720p_hybrid":
            self.resolution_var.set("1280x720")
            self.apply_resolution()
            self.fps_var.set("20")
            self.output_fps_var.set("30")
            self.backbone_var.set("hybrid")
            self.matte_mode_var.set("clean")
        elif preset == "540p_balanced":
            self.resolution_var.set("960x540")
            self.apply_resolution()
            self.fps_var.set("20")
            self.output_fps_var.set("30")
            self.backbone_var.set("mobilenetv3")
            self.matte_mode_var.set("balanced")
        elif preset == "540p_fast":
            self.resolution_var.set("960x540")
            self.apply_resolution()
            self.fps_var.set("20")
            self.output_fps_var.set("30")
            self.backbone_var.set("mobilenetv3")
            self.matte_mode_var.set("clean")
        elif preset == "eco_image":
            self.resolution_var.set("640x360")
            self.apply_resolution()
            self.fps_var.set("18")
            self.output_fps_var.set("24")
            self.backbone_var.set("mobilenetv3")
            self.matte_mode_var.set("balanced")

    def build_launch_env(self) -> dict[str, str] | None:
        values = {
            "PROVCAM_CAMERA_ID": self.camera_id_var.get().strip(),
            "PROVCAM_CAMERA_DEVICE": self.camera_device_var.get().strip(),
            "PROVCAM_WIDTH": self.width_var.get().strip(),
            "PROVCAM_HEIGHT": self.height_var.get().strip(),
            "PROVCAM_FPS": self.fps_var.get().strip(),
            "PROVCAM_OUTPUT_FPS": self.output_fps_var.get().strip(),
            "PROVCAM_OUTPUT_DEVICE": self.output_device_var.get().strip(),
            "PROVCAM_BACKBONE": self.backbone_var.get().strip(),
            "PROVCAM_MATTE_MODE": self.matte_mode_var.get().strip(),
            "PROVCAM_BACKGROUND_MODE": self.background_mode_var.get().strip(),
            "PROVCAM_BACKGROUND_IMAGE": self.background_image_var.get().strip(),
        }

        for key in ("PROVCAM_CAMERA_ID", "PROVCAM_WIDTH", "PROVCAM_HEIGHT", "PROVCAM_FPS", "PROVCAM_OUTPUT_FPS"):
            try:
                int(values[key])
            except ValueError:
                messagebox.showerror("ProVCam GPU", f"Invalid numeric field: {key}")
                return None

        if values["PROVCAM_CAMERA_DEVICE"] and not Path(values["PROVCAM_CAMERA_DEVICE"]).exists():
            messagebox.showerror("ProVCam GPU", "Camera device was not found.")
            return None

        if values["PROVCAM_BACKGROUND_MODE"] == "image" and not Path(values["PROVCAM_BACKGROUND_IMAGE"]).is_file():
            messagebox.showerror("ProVCam GPU", "Background image was not found.")
            return None

        env = os.environ.copy()
        env.update(values)
        return env

    def read_pid(self) -> int | None:
        try:
            value = PID_FILE.read_text(encoding="utf-8").strip()
            if not value:
                return None
            return int(value)
        except Exception:
            return None

    def is_running(self) -> tuple[bool, str]:
        pid = self.read_pid()
        if pid is None:
            return False, "No PID file found."
        try:
            os.kill(pid, 0)
            return True, f"Running. PID: {pid}"
        except OSError:
            return False, "PID file exists, but the process is not running."

    def refresh_status(self) -> None:
        running, detail = self.is_running()
        if running:
            self.status_var.set("Backend active")
            self.detail_var.set(detail)
            self.start_button.state(["disabled"])
            self.stop_button.state(["!disabled"])
            self.repair_button.state(["!disabled"])
        else:
            self.status_var.set("Backend stopped")
            self.detail_var.set(detail)
            self.start_button.state(["!disabled"])
            self.stop_button.state(["disabled"])
            self.repair_button.state(["!disabled"])

    def poll_status(self) -> None:
        self.refresh_status()
        self.root.after(1500, self.poll_status)

    def start_backend(self) -> None:
        if not START_SCRIPT.exists():
            messagebox.showerror("ProVCam GPU", f"Start script not found:\n{START_SCRIPT}")
            return
        env = self.build_launch_env()
        if env is None:
            return
        self.save_settings()
        
        self.start_button.state(["disabled"])
        self.status_var.set("Starting...")
        
        def run_start():
            result = subprocess.run([str(START_SCRIPT)], capture_output=True, text=True, env=env)
            self.root.after(0, self._on_start_finished, result)
            
        import threading
        threading.Thread(target=run_start, daemon=True).start()

    def _on_start_finished(self, result) -> None:
        self.refresh_status()
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or f"Start failed. Log: {LOG_FILE}"
            messagebox.showerror("ProVCam GPU", message)
            self.start_button.state(["!disabled"])
        else:
            if self.auto_preview_var.get():
                self.launch_preview()
            messagebox.showinfo("ProVCam GPU", "Started. Select ProVCam Output as your camera.")

    def stop_backend(self) -> None:
        if not STOP_SCRIPT.exists():
            messagebox.showerror("ProVCam GPU", f"Stop script not found:\n{STOP_SCRIPT}")
            return
        self.stop_button.state(["disabled"])
        self.status_var.set("Stopping...")
        self.stop_preview()

        def run_stop() -> None:
            subprocess.run([str(STOP_SCRIPT)], capture_output=True, text=True)
            self.root.after(0, self.refresh_status)

        import threading
        threading.Thread(target=run_stop, daemon=True).start()

    def repair_backend(self) -> None:
        if not HARD_REPAIR_SCRIPT.exists():
            messagebox.showerror("ProVCam GPU", f"Hard repair script not found:\n{HARD_REPAIR_SCRIPT}")
            return

        env = self.build_launch_env()
        if env is None:
            return

        self.save_settings()
        was_running, _ = self.is_running()
        self.stop_preview()
        self.start_button.state(["disabled"])
        self.stop_button.state(["disabled"])
        self.repair_button.state(["disabled"])
        self.status_var.set("Repairing...")
        self.detail_var.set("Resetting the virtual camera driver. It may ask for administrator approval.")

        def run_repair() -> None:
            subprocess.run([str(STOP_SCRIPT)], capture_output=True, text=True)
            repair_result = subprocess.run([str(HARD_REPAIR_SCRIPT)], capture_output=True, text=True, env=env)
            start_result = None
            if repair_result.returncode == 0 and was_running:
                start_result = subprocess.run([str(START_SCRIPT)], capture_output=True, text=True, env=env)
            self.root.after(0, self._on_repair_finished, repair_result, start_result, was_running)

        import threading
        threading.Thread(target=run_repair, daemon=True).start()

    def _on_repair_finished(self, repair_result, start_result, was_running: bool) -> None:
        self.refresh_status()
        if repair_result.returncode != 0:
            message = repair_result.stderr.strip() or repair_result.stdout.strip() or "Output repair failed."
            messagebox.showerror("ProVCam GPU", message)
            return

        if start_result is not None and start_result.returncode != 0:
            message = start_result.stderr.strip() or start_result.stdout.strip() or f"Start failed. Log: {LOG_FILE}"
            messagebox.showerror("ProVCam GPU", message)
            return

        if was_running and self.auto_preview_var.get():
            self.launch_preview()

        message = "Output repaired."
        if was_running:
            message += " The backend was restarted."
        else:
            message += " You can click Start now if needed."
        messagebox.showinfo("ProVCam GPU", message)

    def open_log(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.touch(exist_ok=True)
        for command in (
            ["xdg-open", str(LOG_FILE)],
            ["gio", "open", str(LOG_FILE)],
        ):
            try:
                subprocess.Popen(command)
                return
            except Exception:
                continue
        messagebox.showinfo("ProVCam GPU", f"Log file:\n{LOG_FILE}")

    def stop_preview(self) -> None:
        if self.preview_process is not None and self.preview_process.poll() is None:
            self.preview_process.terminate()
        self.preview_process = None

    def launch_preview(self) -> None:
        self.stop_preview()
        try:
            width = int(self.width_var.get().strip())
            height = int(self.height_var.get().strip())
            output_fps = int(self.output_fps_var.get().strip())
        except ValueError:
            return

        output_device = self.output_device_var.get().strip()
        try:
            self.preview_process = subprocess.Popen(
                [
                    "ffplay",
                    "-f",
                    "v4l2",
                    "-framerate",
                    str(output_fps),
                    "-video_size",
                    f"{width}x{height}",
                    output_device,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            messagebox.showerror("ProVCam GPU", f"Could not open preview: {exc}")


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = ProVCamApp(root)
    _ = app
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
