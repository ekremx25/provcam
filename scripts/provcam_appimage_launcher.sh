#!/usr/bin/env bash
set -euo pipefail

APPDIR="${APPDIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PAYLOAD_DIR="${APPDIR}/usr/lib/provcam"
TARGET_ROOT="${HOME}/.local/share/provcam"
TARGET_APP="${TARGET_ROOT}/app"
FLAG_FILE="${TARGET_ROOT}/.installed"

mkdir -p "${TARGET_ROOT}"

copy_payload() {
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "${PAYLOAD_DIR}/" "${TARGET_APP}/"
  else
    rm -rf "${TARGET_APP}"
    mkdir -p "${TARGET_APP}"
    cp -a "${PAYLOAD_DIR}/." "${TARGET_APP}/"
  fi
}

copy_payload

if [[ ! -f "${FLAG_FILE}" ]]; then
  if command -v zenity >/dev/null 2>&1; then
    zenity --info \
      --title="ProVCam" \
      --width=420 \
      --text="Ilk calistirma algilandi.\nKurulum penceresi aciliyor." >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "ProVCam" "Ilk calistirma algilandi. Kurulum penceresi aciliyor."
  fi
  exec "${TARGET_APP}/launch_provcam_installer.sh"
fi

exec "${TARGET_APP}/launch_provcam_gui.sh"
