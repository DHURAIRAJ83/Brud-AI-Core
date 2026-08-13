#!/usr/bin/env bash
set -euo pipefail

sudo cp deploy/systemd/brud-*.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "Installed:"
systemctl list-unit-files | grep brud-
