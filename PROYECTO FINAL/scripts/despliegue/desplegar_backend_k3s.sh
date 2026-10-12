#!/usr/bin/env bash
set -euo pipefail

IMAGEN="${IMAGEN:-localhost/eventos-backend:1.0.0}"
ARCHIVO_IMAGEN="${ARCHIVO_IMAGEN:-eventos-backend.tar}"

podman build -t "${IMAGEN}" -f Containerfile.backend .
podman save -o "${ARCHIVO_IMAGEN}" "${IMAGEN}"
sudo k3s ctr images import "${ARCHIVO_IMAGEN}"
sudo k3s kubectl apply -k k8s/backend
sudo k3s kubectl -n eventos rollout status deployment/eventos-backend

echo "Backend FastAPI publicado en: http://190.238.16.227:9090/api/salud"
