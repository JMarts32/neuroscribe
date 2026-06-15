#!/usr/bin/env bash
# Remove the NEUROSCRIBE systemd user service (leaves the Docker image intact).
set -uo pipefail
cd "$(dirname "$0")"

UNIT_NAME="neuroscribe.service"

systemctl --user disable --now "${UNIT_NAME}" 2>/dev/null || true
docker compose down 2>/dev/null || true
rm -f "${HOME}/.config/systemd/user/${UNIT_NAME}"
systemctl --user daemon-reload

echo "✓ Service removed. (Image 'neuroscribe:latest' kept — 'docker rmi neuroscribe' to delete.)"
echo "  To stop auto-start at boot entirely: loginctl disable-linger $USER"
