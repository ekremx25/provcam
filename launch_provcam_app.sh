#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.cache/provcam"
PID_FILE="${LOG_DIR}/provcam_gpu.pid"
CHILD_PID_FILE="${LOG_DIR}/provcam_gpu_child.pid"
WRITER_PID_FILE="${LOG_DIR}/provcam_writer.pid"
CAPTURE_PID_FILE="${LOG_DIR}/provcam_capture.pid"
STOP_FILE="${LOG_DIR}/provcam_gpu.stop"
LOG_FILE="${LOG_DIR}/provcam_gpu.log"
FRAME_STORE="${LOG_DIR}/provcam_frame_store.bin"
RAW_FRAME_STORE="${LOG_DIR}/provcam_raw_frame_store.bin"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
CAMERA_ID="${PROVCAM_CAMERA_ID:-0}"
CAMERA_DEVICE="${PROVCAM_CAMERA_DEVICE:-}"
WIDTH="${PROVCAM_WIDTH:-960}"
HEIGHT="${PROVCAM_HEIGHT:-540}"
FPS="${PROVCAM_FPS:-20}"
OUTPUT_FPS="${PROVCAM_OUTPUT_FPS:-60}"
OUTPUT_DEVICE="${PROVCAM_OUTPUT_DEVICE:-/dev/video2}"
BACKBONE="${PROVCAM_BACKBONE:-mobilenetv3}"
MATTE_MODE="${PROVCAM_MATTE_MODE:-balanced}"
BACKGROUND_MODE="${PROVCAM_BACKGROUND_MODE:-blur}"
BACKGROUND_IMAGE="${PROVCAM_BACKGROUND_IMAGE:-${HOME}/Pictures/wallpapers/Linux-user-Room.png}"

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "ProVCam GPU" "$1"
  fi
}

terminate_pid() {
  local pid="$1"
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  kill "${pid}" 2>/dev/null || true
  for _ in {1..30}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      return 0
    fi
    sleep 0.1
  done
  kill -9 "${pid}" 2>/dev/null || true
}

WRITER_WIDTH="${WIDTH}"
WRITER_HEIGHT="${HEIGHT}"
WRITER_FPS="${OUTPUT_FPS}"
OUTPUT_FORMAT_LOCKED=0

resolve_output_layout() {
  if ! command -v fuser >/dev/null 2>&1; then
    return 0
  fi

  if ! fuser "${OUTPUT_DEVICE}" >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v v4l2-ctl >/dev/null 2>&1; then
    OUTPUT_FORMAT_LOCKED=1
    return 0
  fi

  local all_info current_dims current_fps
  all_info="$(v4l2-ctl -d "${OUTPUT_DEVICE}" --all 2>/dev/null || true)"
  current_dims="$(printf '%s\n' "${all_info}" | awk -F':' '/Width\/Height/ {gsub(/[ \t]/, "", $2); print $2; exit}')"
  current_fps="$(v4l2-ctl -d "${OUTPUT_DEVICE}" --get-parm 2>/dev/null | awk -F': ' '/Frames per second/ {print $2; exit}' | awk '{print $1}' | cut -d. -f1)"

  if [[ "${current_dims}" == */* ]]; then
    local current_width="${current_dims%%/*}"
    local current_height="${current_dims##*/}"
    if [[ "${current_width}" =~ ^[0-9]+$ && "${current_height}" =~ ^[0-9]+$ ]]; then
      WRITER_WIDTH="${current_width}"
      WRITER_HEIGHT="${current_height}"
      OUTPUT_FORMAT_LOCKED=1
    fi
  fi

  if [[ "${current_fps}" =~ ^[0-9]+$ && "${current_fps}" -gt 0 ]]; then
    WRITER_FPS="${current_fps}"
    OUTPUT_FORMAT_LOCKED=1
  fi
}

mkdir -p "${LOG_DIR}"
rm -f "${STOP_FILE}"

# Rotate log if it exceeds 10 MB
if [[ -f "${LOG_FILE}" && $(stat -c%s "${LOG_FILE}" 2>/dev/null || echo 0) -gt 10485760 ]]; then
  mv "${LOG_FILE}" "${LOG_FILE}.1"
fi

if [[ -f "${PID_FILE}" ]]; then
  old_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  terminate_pid "${old_pid}"
  rm -f "${PID_FILE}"
fi

if [[ -f "${CHILD_PID_FILE}" ]]; then
  old_child_pid="$(cat "${CHILD_PID_FILE}" 2>/dev/null || true)"
  terminate_pid "${old_child_pid}"
  rm -f "${CHILD_PID_FILE}"
fi

if [[ -f "${WRITER_PID_FILE}" ]]; then
  old_writer_pid="$(cat "${WRITER_PID_FILE}" 2>/dev/null || true)"
  terminate_pid "${old_writer_pid}"
  rm -f "${WRITER_PID_FILE}"
fi

if [[ -f "${CAPTURE_PID_FILE}" ]]; then
  old_capture_pid="$(cat "${CAPTURE_PID_FILE}" 2>/dev/null || true)"
  terminate_pid "${old_capture_pid}"
  rm -f "${CAPTURE_PID_FILE}"
fi

pkill -f "python.*provcam_rocm.py" >/dev/null 2>&1 || true
pkill -f "python.*provcam_output_writer.py" >/dev/null 2>&1 || true
pkill -f "python.*provcam_capture_proxy.py" >/dev/null 2>&1 || true
pkill -f "scripts/provcam_supervisor.sh" >/dev/null 2>&1 || true

sleep 1

rm -f "${FRAME_STORE}" "${RAW_FRAME_STORE}"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  notify ".venv bulunamadi. Once Python backend kurulumunu tamamla."
  exit 1
fi

if [[ ! -e "${OUTPUT_DEVICE}" ]]; then
  notify "${OUTPUT_DEVICE} bulunamadi. Bir kez ${ROOT_DIR}/setup_boot_autostart.sh calistir."
  exit 1
fi

if [[ -n "${CAMERA_DEVICE}" && ! -e "${CAMERA_DEVICE}" ]]; then
  notify "${CAMERA_DEVICE} bulunamadi. Iriun Webcam acik mi kontrol et."
  exit 1
fi

if [[ "${BACKGROUND_MODE}" == "image" && ! -f "${BACKGROUND_IMAGE}" ]]; then
  notify "Arka plan resmi bulunamadi: ${BACKGROUND_IMAGE}"
  exit 1
fi

cd "${ROOT_DIR}"

resolve_output_layout

PROVCAM_OUTPUT_DEVICE="${OUTPUT_DEVICE}" \
PROVCAM_WIDTH="${WRITER_WIDTH}" \
PROVCAM_HEIGHT="${WRITER_HEIGHT}" \
PROVCAM_OUTPUT_FPS="${WRITER_FPS}" \
"${ROOT_DIR}/repair_provcam_output.sh" >/dev/null 2>&1 || true

export PROVCAM_CAMERA_ID="${CAMERA_ID}"
export PROVCAM_CAMERA_DEVICE="${CAMERA_DEVICE}"
export PROVCAM_WIDTH="${WIDTH}"
export PROVCAM_HEIGHT="${HEIGHT}"
export PROVCAM_FPS="${FPS}"
export PROVCAM_OUTPUT_FPS="${OUTPUT_FPS}"
export PROVCAM_OUTPUT_DEVICE="${OUTPUT_DEVICE}"
export PROVCAM_BACKBONE="${BACKBONE}"
export PROVCAM_MATTE_MODE="${MATTE_MODE}"
export PROVCAM_BACKGROUND_MODE="${BACKGROUND_MODE}"
export PROVCAM_BACKGROUND_IMAGE="${BACKGROUND_IMAGE}"
export PROVCAM_FRAME_STORE="${FRAME_STORE}"
export PROVCAM_CAPTURE_STORE="${RAW_FRAME_STORE}"

nohup "${VENV_PYTHON}" "${ROOT_DIR}/python/provcam_capture_proxy.py" \
  --camera-id "${CAMERA_ID}" \
  --camera-device "${CAMERA_DEVICE}" \
  --width "${WIDTH}" \
  --height "${HEIGHT}" \
  --fps "${FPS}" \
  --frame-store "${RAW_FRAME_STORE}" >>"${LOG_FILE}" 2>&1 &

capture_pid=$!
echo "${capture_pid}" > "${CAPTURE_PID_FILE}"
sleep 1

if ! kill -0 "${capture_pid}" 2>/dev/null; then
  rm -f "${CAPTURE_PID_FILE}"
  notify "Capture proxy baslatma basarisiz. Log: ${LOG_FILE}"
  exit 1
fi

nohup "${VENV_PYTHON}" "${ROOT_DIR}/python/provcam_output_writer.py" \
  --frame-store "${FRAME_STORE}" \
  --output-device "${OUTPUT_DEVICE}" \
  --width "${WRITER_WIDTH}" \
  --height "${WRITER_HEIGHT}" \
  --fps "${WRITER_FPS}" >>"${LOG_FILE}" 2>&1 &

writer_pid=$!
echo "${writer_pid}" > "${WRITER_PID_FILE}"
sleep 1

if ! kill -0 "${writer_pid}" 2>/dev/null; then
  rm -f "${WRITER_PID_FILE}"
  notify "Output writer baslatma basarisiz. Log: ${LOG_FILE}"
  exit 1
fi

nohup "${ROOT_DIR}/scripts/provcam_supervisor.sh" >>"${LOG_FILE}" 2>&1 &

new_pid=$!
echo "${new_pid}" > "${PID_FILE}"
sleep 2

if kill -0 "${new_pid}" 2>/dev/null; then
  if [[ -f "${CHILD_PID_FILE}" ]]; then
    if [[ "${OUTPUT_FORMAT_LOCKED}" -eq 1 ]]; then
      notify "Baslatildi. OBS acik oldugu icin output formati korunuyor."
    else
      notify "Baslatildi. Kamera: ProVCam Output"
    fi
  else
    notify "Supervisor basladi. Backend ilk denemeyi yapiyor."
  fi
  exit 0
fi

rm -f "${PID_FILE}"
rm -f "${CAPTURE_PID_FILE}"
rm -f "${WRITER_PID_FILE}"
rm -f "${STOP_FILE}"
notify "Baslatma basarisiz. Log: ${LOG_FILE}"
exit 1
