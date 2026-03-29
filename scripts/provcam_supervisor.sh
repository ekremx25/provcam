#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
LOG_DIR="${HOME}/.cache/provcam"
STOP_FILE="${LOG_DIR}/provcam_gpu.stop"
CHILD_PID_FILE="${LOG_DIR}/provcam_gpu_child.pid"

mkdir -p "${LOG_DIR}"
rm -f "${CHILD_PID_FILE}"
ulimit -c 0 || true

child_pid=""
stability_level=0
last_runtime=0
requested_width="${PROVCAM_WIDTH:-960}"
requested_height="${PROVCAM_HEIGHT:-540}"
requested_fps="${PROVCAM_FPS:-20}"
requested_output_fps="${PROVCAM_OUTPUT_FPS:-30}"
requested_backbone="${PROVCAM_BACKBONE:-mobilenetv3}"
requested_matte_mode="${PROVCAM_MATTE_MODE:-balanced}"
requested_frame_store="${PROVCAM_FRAME_STORE:-}"
requested_capture_store="${PROVCAM_CAPTURE_STORE:-}"

clamp_down() {
  local value="$1"
  local maximum="$2"
  if (( value > maximum )); then
    echo "${maximum}"
  else
    echo "${value}"
  fi
}

cleanup() {
  if [[ -n "${child_pid}" ]] && kill -0 "${child_pid}" 2>/dev/null; then
    kill "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
  rm -f "${CHILD_PID_FILE}"
}

trap 'touch "${STOP_FILE}"; cleanup; exit 0' INT TERM

restart_count=0

while [[ ! -f "${STOP_FILE}" ]]; do
  selected_width="${requested_width}"
  selected_height="${requested_height}"
  selected_fps="${requested_fps}"
  selected_output_fps="${requested_output_fps}"
  selected_backbone="${requested_backbone}"
  selected_matte_mode="${requested_matte_mode}"

  if (( stability_level >= 1 )); then
    selected_backbone="mobilenetv3"
    selected_fps="$(clamp_down "${selected_fps}" 18)"
    selected_output_fps="$(clamp_down "${selected_output_fps}" 30)"
  fi

  if (( stability_level >= 2 )); then
    if (( selected_width > 960 || selected_height > 540 )); then
      selected_width=960
      selected_height=540
    fi
    selected_fps="$(clamp_down "${selected_fps}" 16)"
    selected_output_fps="$(clamp_down "${selected_output_fps}" 24)"
    selected_matte_mode="balanced"
  fi

  cmd=(
    "${ROOT_DIR}/run_provcam_rocm.sh"
    --camera-id "${PROVCAM_CAMERA_ID:-0}"
    --width "${selected_width}"
    --height "${selected_height}"
    --fps "${selected_fps}"
    --output-fps "${selected_output_fps}"
    --output-device "${PROVCAM_OUTPUT_DEVICE:-/dev/video2}"
    --backbone "${selected_backbone}"
    --matte-mode "${selected_matte_mode}"
    --background "${PROVCAM_BACKGROUND_MODE:-blur}"
    --background-image "${PROVCAM_BACKGROUND_IMAGE:-${HOME}/Pictures/wallpapers/Linux-user-Room.png}"
    --no-preview
  )

  if [[ -n "${PROVCAM_CAMERA_DEVICE:-}" ]]; then
    cmd+=(--camera-device "${PROVCAM_CAMERA_DEVICE}")
  fi

  if [[ -n "${requested_frame_store}" ]]; then
    cmd+=(--frame-store "${requested_frame_store}")
  fi

  if [[ -n "${requested_capture_store}" ]]; then
    cmd+=(--capture-store "${requested_capture_store}")
  fi

  start_ts="$(date +%s)"
  echo "[supervisor] Starting backend attempt $((restart_count + 1)) at $(date '+%F %T') (stability=${stability_level}, ${selected_width}x${selected_height}, fps=${selected_fps}, out=${selected_output_fps}, backbone=${selected_backbone}, matte=${selected_matte_mode})."
  "${cmd[@]}" &
  child_pid=$!
  echo "${child_pid}" > "${CHILD_PID_FILE}"

  set +e
  wait "${child_pid}"
  exit_code=$?
  set -e
  end_ts="$(date +%s)"
  last_runtime=$(( end_ts - start_ts ))
  rm -f "${CHILD_PID_FILE}"
  child_pid=""

  if [[ -f "${STOP_FILE}" ]]; then
    break
  fi

  if (( last_runtime >= 120 )); then
    stability_level=0
    restart_count=0
  elif (( last_runtime >= 45 )); then
    if (( stability_level > 0 )); then
      stability_level=$((stability_level - 1))
    fi
  else
    stability_level=$((stability_level + 1))
    if (( stability_level > 2 )); then
      stability_level=2
    fi
  fi

  restart_count=$((restart_count + 1))
  backoff=$(( restart_count < 5 ? restart_count + 1 : 5 ))
  echo "[supervisor] Backend exited with code ${exit_code} after ${last_runtime}s. Restarting in ${backoff}s with stability level ${stability_level}."
  sleep "${backoff}"
done

cleanup
