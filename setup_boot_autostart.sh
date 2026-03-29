#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_FILE="/etc/modules-load.d/provcam-v4l2loopback.conf"
MODPROBE_FILE="/etc/modprobe.d/provcam-v4l2loopback.conf"
AUTOSTART_DIR="${HOME}/.config/autostart"
AUTOSTART_FILE="${AUTOSTART_DIR}/iriunwebcam.desktop"

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required."
  exit 1
fi

mkdir -p "${AUTOSTART_DIR}"

sudo tee "${MODULES_FILE}" >/dev/null <<'EOF'
v4l2loopback
EOF

sudo tee "${MODPROBE_FILE}" >/dev/null <<'EOF'
options v4l2loopback devices=2 video_nr=0,2 card_label="Iriun Webcam,ProVCam Output" exclusive_caps=1,0
EOF

cat > "${AUTOSTART_FILE}" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Iriun Webcam
Comment=Start Iriun Webcam on login for ProVCam
Exec=$(command -v iriunwebcam)
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

sudo modprobe -r v4l2loopback >/dev/null 2>&1 || true
sudo modprobe v4l2loopback

if ! pgrep -x iriunwebcam >/dev/null 2>&1; then
  nohup iriunwebcam >/dev/null 2>&1 &
fi

echo "Installed boot config:"
echo "  ${MODULES_FILE}"
echo "  ${MODPROBE_FILE}"
echo "Installed login autostart:"
echo "  ${AUTOSTART_FILE}"
echo
echo "After reboot, /dev/video0 and /dev/video2 should come back automatically."
