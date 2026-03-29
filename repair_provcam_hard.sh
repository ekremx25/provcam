#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_HELPER="${ROOT_DIR}/scripts/provcam_reload_loopback_root.sh"

if [[ ! -x "${ROOT_HELPER}" ]]; then
  echo "Root helper not found or not executable: ${ROOT_HELPER}" >&2
  exit 1
fi

if command -v pkexec >/dev/null 2>&1; then
  pkexec env DISPLAY="${DISPLAY:-}" XAUTHORITY="${XAUTHORITY:-}" XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" \
    /usr/bin/bash "${ROOT_HELPER}"
else
  echo "pkexec bulunamadi. Hard reset icin terminalde sudo gerekli." >&2
  exit 1
fi

if command -v iriunwebcam >/dev/null 2>&1 && ! pgrep -x iriunwebcam >/dev/null 2>&1; then
  nohup iriunwebcam >/dev/null 2>&1 &
fi

sleep 2
