#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  exec "${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/python/provcam_installer.py"
fi

exec python3 "${ROOT_DIR}/python/provcam_installer.py"
