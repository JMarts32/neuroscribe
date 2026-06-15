#!/usr/bin/env bash
# Launch NEUROSCRIBE (faster-whisper transcription app).
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

# CTranslate2 / OpenMP threading tuned for AMD Ryzen 7 PRO 8840U (8 physical cores)
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"

echo "▚ NEUROSCRIBE  →  http://127.0.0.1:${PORT}"
exec .venv/bin/python -m uvicorn main:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port "${PORT}"
