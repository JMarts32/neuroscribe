#!/usr/bin/env bash
# Install NEUROSCRIBE as a systemd *user* service that starts at boot.
set -euo pipefail
cd "$(dirname "$0")"

UNIT_DIR="${HOME}/.config/systemd/user"
UNIT_NAME="neuroscribe.service"
REPO_DIR="$(pwd)"

echo "▚ Building the Docker image (first time pulls Python + deps)…"
docker compose build

echo "▚ Installing user service → ${UNIT_DIR}/${UNIT_NAME}  (WorkingDirectory=${REPO_DIR})"
mkdir -p "${UNIT_DIR}"
# Bake this repo's absolute path into the unit so it works wherever it's cloned.
sed "s|__WORKDIR__|${REPO_DIR}|g" "${UNIT_NAME}" > "${UNIT_DIR}/${UNIT_NAME}"

echo "▚ Enabling linger so the service runs at boot (before you log in)…"
# Allows your user services to start at boot without an active session.
loginctl enable-linger "$USER" || \
  echo "  ! Could not enable linger automatically. Run: sudo loginctl enable-linger $USER"

echo "▚ Enabling + starting the service…"
systemctl --user daemon-reload
systemctl --user enable --now "${UNIT_NAME}"

echo ""
echo "✓ Done. NEUROSCRIBE is running at  http://127.0.0.1:8000"
echo "  Status : systemctl --user status neuroscribe.service"
echo "  Logs   : docker compose logs -f   (in $(pwd))"
echo "  Stop   : systemctl --user stop neuroscribe.service"
