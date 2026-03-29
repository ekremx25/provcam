#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
APPDIR="${DIST_DIR}/ProVCam.AppDir"
PAYLOAD_DIR="${APPDIR}/usr/lib/provcam"
BIN_DIR="${APPDIR}/usr/bin"
APPLICATIONS_DIR="${APPDIR}/usr/share/applications"
METAINFO_DIR="${APPDIR}/usr/share/metainfo"
DESKTOP_FILE="${APPDIR}/provcam.desktop"
ICON_FILE="${APPDIR}/provcam.svg"
APPIMAGE_TOOL="${APPIMAGE_TOOL:-}"

mkdir -p "${DIST_DIR}"
rm -rf "${APPDIR}"
mkdir -p "${PAYLOAD_DIR}" "${BIN_DIR}" "${APPLICATIONS_DIR}" "${METAINFO_DIR}"

if [[ -z "${APPIMAGE_TOOL}" ]]; then
  if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGE_TOOL="$(command -v appimagetool)"
  else
    APPIMAGE_TOOL="${DIST_DIR}/appimagetool-x86_64.AppImage"
    if [[ ! -x "${APPIMAGE_TOOL}" ]]; then
      curl -L \
        -o "${APPIMAGE_TOOL}" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
      chmod +x "${APPIMAGE_TOOL}"
    fi
  fi
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required to build the AppImage."
  exit 1
fi

rsync -a \
  --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'build' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'gpucore.*' \
  --exclude '*.core' \
  --exclude '*.log' \
  --exclude 'linux-vcam-pro-backup-*' \
  --exclude 'linux-vcam-pro-gpu-stable-*' \
  "${ROOT_DIR}/" "${PAYLOAD_DIR}/"

install -m 0755 "${ROOT_DIR}/scripts/provcam_appimage_launcher.sh" "${BIN_DIR}/provcam"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ProVCam
Comment=AMD GPU virtual camera with one-click installer
Exec=provcam
Icon=provcam
StartupWMClass=ProVCam
X-AppImage-Name=ProVCam
X-AppImage-Version=1.0.0
X-AppImage-Arch=x86_64
Terminal=false
Categories=AudioVideo;Video;
StartupNotify=true
MimeType=x-scheme-handler/provcam;
EOF

cp "${ROOT_DIR}/assets/provcam.svg" "${ICON_FILE}"
cp "${DESKTOP_FILE}" "${APPLICATIONS_DIR}/io.github.ekrem.provcam.desktop"
cp "${ROOT_DIR}/assets/provcam.appdata.xml" "${METAINFO_DIR}/io.github.ekrem.provcam.appdata.xml"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR="${HERE}"
exec "${HERE}/usr/bin/provcam" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

ARCH=x86_64 "${APPIMAGE_TOOL}" --no-appstream "${APPDIR}" "${DIST_DIR}/ProVCam-x86_64.AppImage"
echo "Built: ${DIST_DIR}/ProVCam-x86_64.AppImage"
