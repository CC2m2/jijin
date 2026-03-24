#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="jijin-backend"
SERVICE_SRC="/opt/jijin/backend/deploy/jijin-backend.service.example"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "service file not found: $SERVICE_SRC" >&2
  exit 1
fi

sudo cp "$SERVICE_SRC" "$SERVICE_DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "systemd service installed: $SERVICE_DST"
