#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-eventos}"

if [ ! -f ".env" ]; then
  echo "Falta .env en la raiz del proyecto."
  exit 1
fi

if [ ! -f "certs/server-ca.pem" ] || [ ! -f "certs/client-cert.pem" ] || [ ! -f "certs/client-key.pem" ]; then
  echo "Faltan certificados PostgreSQL en certs/."
  exit 1
fi

sudo k3s kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | sudo k3s kubectl apply -f -

ARCHIVO_SECRET_BACKEND="$(mktemp)"
ARCHIVO_CONFIG_BACKEND="$(mktemp)"
trap 'rm -f "${ARCHIVO_SECRET_BACKEND}" "${ARCHIVO_CONFIG_BACKEND}"' EXIT
grep -E '^(LLM_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|IMAGE_API_KEY|LANGSMITH_API_KEY|POSTGRES_USER|POSTGRES_PASSWORD|REDIS_URL|SUPABASE_URL|SUPABASE_KEY)=' .env > "${ARCHIVO_SECRET_BACKEND}" || true
grep -Ev '^(LLM_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|IMAGE_API_KEY|LANGSMITH_API_KEY|POSTGRES_USER|POSTGRES_PASSWORD|REDIS_URL|SUPABASE_URL|SUPABASE_KEY|POSTGRES_SSLROOTCERT|POSTGRES_SSLCERT|POSTGRES_SSLKEY)=' .env > "${ARCHIVO_CONFIG_BACKEND}" || true
cat >> "${ARCHIVO_CONFIG_BACKEND}" <<'EOF'
COTIZADOR_NO_SOBRESCRIBIR_ENV=true
POSTGRES_SSLROOTCERT=/app/certs/server-ca.pem
POSTGRES_SSLCERT=/app/certs/client-cert.pem
POSTGRES_SSLKEY=/app/certs/client-key.pem
EOF

# CONFIG BACKEND: toma variables no sensibles desde .env y ajusta rutas SSL al contenedor.
sudo k3s kubectl -n "${NAMESPACE}" create configmap eventos-backend-config \
  --from-env-file="${ARCHIVO_CONFIG_BACKEND}" \
  --dry-run=client -o yaml | sudo k3s kubectl apply -f -

# SECRETS BACKEND: toma solo credenciales desde .env sin pisar rutas productivas del ConfigMap.
sudo k3s kubectl -n "${NAMESPACE}" create secret generic eventos-backend-secret \
  --from-env-file="${ARCHIVO_SECRET_BACKEND}" \
  --dry-run=client -o yaml | sudo k3s kubectl apply -f -

# SECRETS POSTGRES: certificados cliente para conectar a PostgreSQL con SSL.
sudo k3s kubectl -n "${NAMESPACE}" create secret generic eventos-postgres-certificados \
  --from-file=server-ca.pem=certs/server-ca.pem \
  --from-file=client-cert.pem=certs/client-cert.pem \
  --from-file=client-key.pem=certs/client-key.pem \
  --dry-run=client -o yaml | sudo k3s kubectl apply -f -

if [ -f "entrega-john/.env" ]; then
  # SECRETS RAG: .env especifico del retriever GCP usado por entrega-john/datos.py.
  sudo k3s kubectl -n "${NAMESPACE}" create secret generic eventos-rag-env \
    --from-file=.env=entrega-john/.env \
    --dry-run=client -o yaml | sudo k3s kubectl apply -f -
else
  echo "Falta entrega-john/.env para RAG. Crea el archivo o ajusta el Deployment si no usaras RAG."
  exit 1
fi

if [ -d "entrega-john/certs" ]; then
  # SECRETS RAG: certificados usados por la URL DATABASE_URL del retriever.
  sudo k3s kubectl -n "${NAMESPACE}" create secret generic eventos-rag-certificados \
    --from-file=server-ca.pem=entrega-john/certs/server-ca.pem \
    --from-file=client-cert.pem=entrega-john/certs/client-cert.pem \
    --from-file=client-key.pem=entrega-john/certs/client-key.pem \
    --dry-run=client -o yaml | sudo k3s kubectl apply -f -
else
  echo "Falta entrega-john/certs para RAG. Crea la carpeta o ajusta el Deployment si no usaras RAG."
  exit 1
fi

echo "Secrets del backend creados/actualizados en namespace ${NAMESPACE}."
