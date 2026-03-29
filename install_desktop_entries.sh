#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${HOME}/.local/share/applications"
DESKTOP_DIR="${HOME}/Desktop"
APP_FILE="${APP_DIR}/provcam-gpu.desktop"
STOP_FILE="${APP_DIR}/provcam-gpu-stop.desktop"
INSTALLER_FILE="${APP_DIR}/provcam-gpu-installer.desktop"
DESKTOP_FILE="${DESKTOP_DIR}/ProVCam GPU.desktop"
INSTALLER_DESKTOP_FILE="${DESKTOP_DIR}/ProVCam Installer.desktop"

mkdir -p "${APP_DIR}" "${DESKTOP_DIR}"

cat > "${APP_FILE}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ProVCam GPU
Comment=Open the ProVCam GPU control app
Exec=${ROOT_DIR}/launch_provcam_gui.sh
Icon=camera-web
Terminal=false
Categories=AudioVideo;Video;
StartupNotify=true
EOF

cat > "${STOP_FILE}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ProVCam GPU Stop
Comment=Stop the ProVCam GPU backend
Exec=${ROOT_DIR}/stop_provcam_app.sh
Icon=media-playback-stop
Terminal=false
Categories=AudioVideo;Video;
StartupNotify=false
EOF

cat > "${INSTALLER_FILE}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ProVCam Installer
Comment=Install and configure ProVCam GPU
Exec=${ROOT_DIR}/launch_provcam_installer.sh
Icon=system-software-install
Terminal=false
Categories=AudioVideo;Video;Settings;
StartupNotify=true
EOF

cp "${APP_FILE}" "${DESKTOP_FILE}"
cp "${INSTALLER_FILE}" "${INSTALLER_DESKTOP_FILE}"

chmod +x "${APP_FILE}" "${STOP_FILE}" "${INSTALLER_FILE}" "${DESKTOP_FILE}" "${INSTALLER_DESKTOP_FILE}"

update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true

echo "Installed:"
echo "  ${APP_FILE}"
echo "  ${STOP_FILE}"
echo "  ${INSTALLER_FILE}"
echo "  ${DESKTOP_FILE}"
echo "  ${INSTALLER_DESKTOP_FILE}"
