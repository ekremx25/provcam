#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${HOME}/.cache/provcam"
PID_FILE="${LOG_DIR}/provcam_gpu.pid"
CHILD_PID_FILE="${LOG_DIR}/provcam_gpu_child.pid"
WRITER_PID_FILE="${LOG_DIR}/provcam_writer.pid"
CAPTURE_PID_FILE="${LOG_DIR}/provcam_capture.pid"
STOP_FILE="${LOG_DIR}/provcam_gpu.stop"
FRAME_STORE="${LOG_DIR}/provcam_frame_store.bin"
RAW_FRAME_STORE="${LOG_DIR}/provcam_raw_frame_store.bin"

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

stopped=0
touch "${STOP_FILE}"

if [[ -f "${CHILD_PID_FILE}" ]]; then
  child_pid="$(cat "${CHILD_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${child_pid}" ]] && kill -0 "${child_pid}" 2>/dev/null; then
    terminate_pid "${child_pid}"
    stopped=1
  fi
  rm -f "${CHILD_PID_FILE}"
fi

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    terminate_pid "${pid}"
    stopped=1
  fi
  rm -f "${PID_FILE}"
fi

if [[ -f "${WRITER_PID_FILE}" ]]; then
  writer_pid="$(cat "${WRITER_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${writer_pid}" ]] && kill -0 "${writer_pid}" 2>/dev/null; then
    terminate_pid "${writer_pid}"
    stopped=1
  fi
  rm -f "${WRITER_PID_FILE}"
fi

if [[ -f "${CAPTURE_PID_FILE}" ]]; then
  capture_pid="$(cat "${CAPTURE_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${capture_pid}" ]] && kill -0 "${capture_pid}" 2>/dev/null; then
    terminate_pid "${capture_pid}"
    stopped=1
  fi
  rm -f "${CAPTURE_PID_FILE}"
fi

if pkill -f "python.*provcam_rocm.py" >/dev/null 2>&1; then
  stopped=1
fi

if pkill -f "python.*provcam_output_writer.py" >/dev/null 2>&1; then
  stopped=1
fi

if pkill -f "python.*provcam_capture_proxy.py" >/dev/null 2>&1; then
  stopped=1
fi

if pkill -f "scripts/provcam_supervisor.sh" >/dev/null 2>&1; then
  stopped=1
fi

if [[ "${stopped}" -eq 1 ]]; then
  notify "Durduruldu."
else
  notify "Zaten calismiyordu."
fi

rm -f "${STOP_FILE}"
rm -f "${FRAME_STORE}"
rm -f "${RAW_FRAME_STORE}"
