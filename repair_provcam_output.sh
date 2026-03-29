#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
OUTPUT_DEVICE="${PROVCAM_OUTPUT_DEVICE:-/dev/video2}"
WIDTH="${PROVCAM_WIDTH:-960}"
HEIGHT="${PROVCAM_HEIGHT:-540}"
FPS="${PROVCAM_OUTPUT_FPS:-30}"

if [[ ! -e "${OUTPUT_DEVICE}" ]]; then
  echo "Output device not found: ${OUTPUT_DEVICE}" >&2
  exit 1
fi

if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl -d "${OUTPUT_DEVICE}" --set-ctrl keep_format=0 >/dev/null 2>&1 || true
  v4l2-ctl -d "${OUTPUT_DEVICE}" --set-ctrl sustain_framerate=0 >/dev/null 2>&1 || true
  v4l2-ctl -d "${OUTPUT_DEVICE}" --set-ctrl timeout=0 >/dev/null 2>&1 || true
  v4l2-ctl -d "${OUTPUT_DEVICE}" \
    --set-fmt-video-out "width=${WIDTH},height=${HEIGHT},pixelformat=YU12,field=none,colorspace=srgb" >/dev/null 2>&1 || true
  v4l2-ctl -d "${OUTPUT_DEVICE}" \
    --set-fmt-video-capture "width=${WIDTH},height=${HEIGHT},pixelformat=YU12,field=none,colorspace=srgb" >/dev/null 2>&1 || true
  v4l2-ctl -d "${OUTPUT_DEVICE}" --set-ctrl keep_format=1 >/dev/null 2>&1 || true
  v4l2-ctl -d "${OUTPUT_DEVICE}" --set-ctrl sustain_framerate=1 >/dev/null 2>&1 || true
fi

if [[ -x "${VENV_PYTHON}" ]]; then
  "${VENV_PYTHON}" "${ROOT_DIR}/python/provcam_reset_output.py" \
    --output-device "${OUTPUT_DEVICE}" \
    --width "${WIDTH}" \
    --height "${HEIGHT}" \
    --fps "${FPS}" \
    --seconds 1.0 >/dev/null 2>&1 || true
fi
