#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root." >&2
  exit 1
fi

/usr/bin/pkill -f "python.*provcam_rocm.py" >/dev/null 2>&1 || true
/usr/bin/pkill -f "python.*provcam_output_writer.py" >/dev/null 2>&1 || true
/usr/bin/pkill -f "python.*provcam_capture_proxy.py" >/dev/null 2>&1 || true
/usr/bin/pkill -f "scripts/provcam_supervisor.sh" >/dev/null 2>&1 || true

/usr/bin/modprobe -r v4l2loopback >/dev/null 2>&1 || true
/usr/bin/modprobe v4l2loopback \
  devices=2 \
  video_nr=0,2 \
  card_label="Iriun Webcam,ProVCam Output" \
  exclusive_caps=1,0

/usr/bin/udevadm settle
