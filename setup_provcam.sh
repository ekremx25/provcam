#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"
TORCH_INDEX_URL="${PROVCAM_TORCH_INDEX_URL:-https://download.pytorch.org/whl/rocm6.3}"
LOG_DIR="${HOME}/.cache/provcam"
SETUP_LOG="${LOG_DIR}/setup.log"
TARGET_ROOT="${HOME}/.local/share/provcam"
FLAG_FILE="${TARGET_ROOT}/.installed"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${SETUP_LOG}") 2>&1

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "ProVCam GPU" "$1"
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_system_packages() {
  local missing=()
  for cmd in python3 v4l2-ctl ffplay; do
    if ! need_cmd "${cmd}"; then
      missing+=("${cmd}")
    fi
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    return 0
  fi

  echo "Missing system commands: ${missing[*]}"

  if need_cmd pacman && need_cmd sudo; then
    echo "Installing system packages via pacman..."
    sudo pacman -Sy --needed python ffmpeg v4l-utils
  else
    echo "Please install system packages manually: python, ffmpeg, v4l-utils"
    return 1
  fi
}

ensure_venv() {
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
  fi
}

python_ready() {
  [[ -x "${PYTHON_BIN}" ]] || return 1
  "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import cv2
import numpy
import torch
import tkinter
PY
}

install_python_packages() {
  echo "Installing Python packages..."
  "${PIP_BIN}" install -U pip
  "${PIP_BIN}" install -r "${ROOT_DIR}/requirements-python-rocm.txt"
  "${PIP_BIN}" install torch torchvision --index-url "${TORCH_INDEX_URL}"
  echo "Precaching AI models for offline usage..."
  "${PYTHON_BIN}" -c "import torch; torch.hub.load('PeterL1n/RobustVideoMatting', 'mobilenetv3', trust_repo=True); torch.hub.load('PeterL1n/RobustVideoMatting', 'resnet50', trust_repo=True)" || true
}

write_default_settings() {
  local config_dir="${HOME}/.config/provcam"
  local config_file="${config_dir}/settings.json"
  mkdir -p "${config_dir}"

  if [[ -f "${config_file}" ]]; then
    return 0
  fi

  cat > "${config_file}" <<EOF
{
  "camera_id": "0",
  "camera_device": "/dev/video0",
  "width": "640",
  "height": "360",
  "resolution": "640x360",
  "fps": "20",
  "output_fps": "24",
  "output_device": "/dev/video2",
  "preset": "eco_image",
  "backbone": "mobilenetv3",
  "matte_mode": "balanced",
  "background_mode": "blur",
  "background_image": "${HOME}/Pictures/wallpapers/Linux-user-Room.png",
  "auto_preview": false
}
EOF
}

main() {
  install_system_packages
  ensure_venv

  if ! python_ready; then
    install_python_packages
  fi

  "${ROOT_DIR}/install_desktop_entries.sh"
  write_default_settings
  mkdir -p "${TARGET_ROOT}"
  touch "${FLAG_FILE}"

  notify "Kurulum hazir. ProVCam GPU kullanilabilir."
  echo "Setup completed."
}

main "$@"
