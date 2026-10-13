#!/usr/bin/env bash
set -euo pipefail

IP_PUBLICA="${IP_PUBLICA:-190.43.231.168}"
IP_BACKEND_LOCAL="${IP_BACKEND_LOCAL:-192.168.1.74}"
PUERTO_FRONTEND="${PUERTO_FRONTEND:-8000}"
PUERTO_PUBLICO_BACKEND="${PUERTO_PUBLICO_BACKEND:-9090}"
COTIZADOR_API_URL="${COTIZADOR_API_URL:-http://${IP_BACKEND_LOCAL}:${PUERTO_PUBLICO_BACKEND}}"
IMAGEN="${IMAGEN:-localhost/eventos-frontend:1.0.0}"
CONTENEDOR="${CONTENEDOR:-eventos-frontend}"

podman build -t "${IMAGEN}" -f Containerfile.frontend .
podman rm -f "${CONTENEDOR}" >/dev/null 2>&1 || true
podman run -d \
  --name "${CONTENEDOR}" \
  -p "${PUERTO_FRONTEND}:8504" \
  -e COTIZADOR_API_URL="${COTIZADOR_API_URL}" \
  "${IMAGEN}"

echo "Frontend Streamlit: http://${IP_PUBLICA}:${PUERTO_FRONTEND}"
echo "Backend consumido por Streamlit: ${COTIZADOR_API_URL}"
