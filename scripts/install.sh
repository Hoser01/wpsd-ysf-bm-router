#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ysf-bm-router}"
SERVICE_NAME="ysf-bm-router.service"
ADMIN_SERVICE_NAME="ysf-bm-router-admin.service"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/install.sh" >&2
  exit 1
fi

install -d -m 0755 "${APP_DIR}"
install -d -m 0755 "${APP_DIR}/config"

rm -rf "${APP_DIR}/src"
cp -a "${SOURCE_ROOT}/src" "${APP_DIR}/src"

for path in README.md INSTALL-WPSD.md THIRD_PARTY.md pyproject.toml; do
  if [[ -f "${SOURCE_ROOT}/${path}" ]]; then
    install -m 0644 "${SOURCE_ROOT}/${path}" "${APP_DIR}/${path}"
  fi
done

if [[ -d "${SOURCE_ROOT}/docs" ]]; then
  rm -rf "${APP_DIR}/docs"
  cp -a "${SOURCE_ROOT}/docs" "${APP_DIR}/docs"
fi

if [[ -d "${SOURCE_ROOT}/scripts" ]]; then
  rm -rf "${APP_DIR}/scripts"
  cp -a "${SOURCE_ROOT}/scripts" "${APP_DIR}/scripts"
fi

if [[ ! -f "${APP_DIR}/config/ysf-bm-router.toml" ]]; then
  install -m 0640 "${SOURCE_ROOT}/config/ysf-bm-router.toml" "${APP_DIR}/config/ysf-bm-router.toml"
  chown pi-star:pi-star "${APP_DIR}/config/ysf-bm-router.toml" || true
else
  echo "Preserved existing ${APP_DIR}/config/ysf-bm-router.toml"
fi

install -m 0644 "${SOURCE_ROOT}/deploy/systemd/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
install -m 0644 "${SOURCE_ROOT}/deploy/systemd/${ADMIN_SERVICE_NAME}" "/etc/systemd/system/${ADMIN_SERVICE_NAME}"
systemctl daemon-reload

chown -R pi-star:pi-star "${APP_DIR}/src" "${APP_DIR}/docs" "${APP_DIR}/scripts" 2>/dev/null || true
systemctl enable --now "${ADMIN_SERVICE_NAME}"

echo "Installed ${SERVICE_NAME}."
echo "Installed ${ADMIN_SERVICE_NAME}."
echo "YSF host entry:"
echo "01234;YSF-BM-TEST;YSF-BM-TEST;127.0.0.1;42002;001;"
echo
echo "Admin UI:"
echo "  http://<hotspot-hostname-or-ip>:8092/"
echo
echo "Before testing, confirm simplex hotspot TX and RX both match the radio,"
echo "or use the correct inverse split for duplex."
echo
echo "To run:"
echo "  sudo systemctl stop ysf2dmr.service ysf2dmr.timer"
echo "  sudo systemctl enable --now ${SERVICE_NAME}"
echo
echo "The admin service has already been enabled and started by this installer."
echo
echo "Installer guide: ${APP_DIR}/INSTALL-WPSD.md"
echo "Tester guide: ${APP_DIR}/docs/TESTER-QUICKSTART.md"
