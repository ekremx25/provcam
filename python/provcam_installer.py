#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import shutil


ROOT_DIR = Path(__file__).resolve().parent.parent
SETUP_SCRIPT = ROOT_DIR / "setup_provcam.sh"
BOOT_SCRIPT = ROOT_DIR / "setup_boot_autostart.sh"
GUI_SCRIPT = ROOT_DIR / "launch_provcam_gui.sh"
LOG_DIR = Path.home() / ".cache" / "provcam"
SETUP_LOG = LOG_DIR / "setup.log"
TERMINAL_CANDIDATES = ["kitty", "gnome-terminal", "konsole", "xterm"]


def find_terminal() -> tuple[str, str]:
    """Return (terminal_bin, mode) where mode is 'kitty', 'gnome-terminal', or 'xterm-like'."""
    for name in TERMINAL_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path, name
    return "", ""


def runtime_ready() -> bool:
    python_bin = ROOT_DIR / ".venv" / "bin" / "python"
    if not python_bin.exists():
        return False
    result = subprocess.run(
        [
            str(python_bin),
            "-c",
            "import cv2, numpy, torch, tkinter",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def boot_ready() -> bool:
    return Path("/etc/modules-load.d/provcam-v4l2loopback.conf").exists() and Path(
        "/etc/modprobe.d/provcam-v4l2loopback.conf"
    ).exists()


class InstallerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ProVCam Installer")
        self.root.geometry("720x420")
        self.root.minsize(640, 360)
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

        main = ttk.Frame(root, style="Root.TFrame", padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="ProVCam Installer", style="Title.TLabel").pack(anchor="w")

        card = ttk.Frame(main, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True, pady=(14, 0))

        ttk.Label(
            card,
            text="Tek tikla kurulum. Python ortamını hazırlar, masaüstü kısayollarını kurar ve istersen reboot sonrası otomatik loopback/Iriun başlatmayı ayarlar.",
            style="Body.TLabel",
            wraplength=620,
            justify="left",
        ).pack(anchor="w")

        self.runtime_var = tk.StringVar()
        self.boot_var = tk.StringVar()
        ttk.Label(card, textvariable=self.runtime_var, style="Status.TLabel").pack(anchor="w", pady=(14, 2))
        ttk.Label(card, textvariable=self.boot_var, style="Muted.TLabel").pack(anchor="w")
        ttk.Label(card, text=f"Log: {SETUP_LOG}", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        button_row = ttk.Frame(card, style="Card.TFrame")
        button_row.pack(fill="x", pady=(8, 10))

        ttk.Button(button_row, text="Temel Kurulum", style="Action.TButton", command=self.run_basic_setup).pack(
            side="left"
        )
        ttk.Button(
            button_row,
            text="Tam Kurulum",
            style="Action.TButton",
            command=self.run_full_setup,
        ).pack(side="left", padx=(10, 0))
        ttk.Button(button_row, text="Log Ac", style="Action.TButton", command=self.open_log).pack(side="left", padx=(10, 0))
        ttk.Button(button_row, text="ProVCam Ac", style="Action.TButton", command=self.open_app).pack(
            side="right"
        )

        ttk.Label(
            card,
            text="Temel Kurulum: .venv, PyTorch ROCm, GUI ve masaüstü girişleri.\nTam Kurulum: üsttekilere ek olarak reboot sonrası loopback ve Iriun otomatik başlatma.",
            style="Muted.TLabel",
            justify="left",
        ).pack(anchor="w")

        self.refresh_status()
        self.root.after(2000, self.poll_status)

    def refresh_status(self) -> None:
        self.runtime_var.set("Uygulama hazir" if runtime_ready() else "Uygulama kurulmamış")
        self.boot_var.set(
            "Boot/autostart ayari hazir" if boot_ready() else "Boot/autostart ayari henuz kurulmamış"
        )

    def poll_status(self) -> None:
        self.refresh_status()
        self.root.after(2000, self.poll_status)

    def launch_terminal(self, command: str) -> None:
        term_path, term_name = find_terminal()
        if not term_path:
            messagebox.showerror(
                "ProVCam Installer",
                "Desteklenen terminal bulunamadi (kitty, gnome-terminal, konsole, xterm).",
            )
            return
        shell_cmd = f"{command}; echo; echo 'Kapatmak icin Enter'; read -r"
        if term_name == "kitty":
            args = [term_path, "--title", "ProVCam Installer", "bash", "-lc", shell_cmd]
        elif term_name == "gnome-terminal":
            args = [term_path, "--title", "ProVCam Installer", "--", "bash", "-lc", shell_cmd]
        elif term_name == "konsole":
            args = [term_path, "--title", "ProVCam Installer", "-e", "bash", "-lc", shell_cmd]
        else:  # xterm
            args = [term_path, "-title", "ProVCam Installer", "-e", "bash", "-lc", shell_cmd]
        subprocess.Popen(args)

    def run_basic_setup(self) -> None:
        self.launch_terminal(f"cd '{ROOT_DIR}' && '{SETUP_SCRIPT}'")

    def run_full_setup(self) -> None:
        self.launch_terminal(f"cd '{ROOT_DIR}' && '{SETUP_SCRIPT}' && '{BOOT_SCRIPT}'")

    def open_log(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        SETUP_LOG.touch(exist_ok=True)
        for command in (["xdg-open", str(SETUP_LOG)], ["gio", "open", str(SETUP_LOG)]):
            try:
                subprocess.Popen(command)
                return
            except Exception:
                continue
        messagebox.showinfo("ProVCam Installer", str(SETUP_LOG))

    def open_app(self) -> None:
        subprocess.Popen([str(GUI_SCRIPT)])


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
