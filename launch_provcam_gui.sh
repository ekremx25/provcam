#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_SCRIPT="${ROOT_DIR}/setup_provcam.sh"
INSTALLER_SCRIPT="${ROOT_DIR}/launch_provcam_installer.sh"

runtime_ready() {
  [[ -x "${ROOT_DIR}/.venv/bin/python" ]] || return 1
  "${ROOT_DIR}/.venv/bin/python" - <<'PY' >/dev/null 2>&1
import cv2
import numpy
import torch
import tkinter
PY
}

if ! runtime_ready; then
  if command -v zenity >/dev/null 2>&1; then
    zenity --info \
      --title="ProVCam" \
      --width=420 \
      --text="Ilk kurulum veya runtime onarimi gerekiyor.\nInstaller aciliyor." >/dev/null 2>&1 || true
  fi

  if [[ -x "${INSTALLER_SCRIPT}" ]]; then
    exec "${INSTALLER_SCRIPT}"
  fi

  if [[ -x "${SETUP_SCRIPT}" ]]; then
    exec "${SETUP_SCRIPT}"
  fi
fi

if runtime_ready; then
  exec "${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/python/provcam_gui.py"
fi

exec python3 "${ROOT_DIR}/python/provcam_gui.py"
