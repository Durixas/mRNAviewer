#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-4}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
PYTHON_COMMAND="${MRNAVIEWER_BACKEND_PYTHON:-python3}"
exec "$PYTHON_COMMAND" -m gunicorn --bind "${MRNAVIEWER_BIND:-127.0.0.1:5000}" \
    --workers 1 --threads 4 --timeout 120 backend_server:app
