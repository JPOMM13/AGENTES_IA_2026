# Despliegue en servidor 192.168.1.74 / IP publica 190.238.16.227

## Puertos y URLs definidas

- Backend FastAPI en Kubernetes/k3s:
  - Contenedor: `8000`
  - Service LoadBalancer: `9090 -> 8000`
  - Publicacion: `http://190.238.16.227:9090/api`
  - Salud: `http://190.238.16.227:9090/api/salud`

- Frontend Streamlit en Podman:
  - Contenedor: `8504`
  - Host: `8000`
  - URL publica: `http://190.238.16.227:8000`

- Variable del frontend:

```bash
COTIZADOR_API_URL=http://190.238.16.227:9090
```

No se coloca `/api` en `COTIZADOR_API_URL` porque el frontend ya agrega rutas
como `/api/chat` y `/api/sesiones`.

## Backend en Kubernetes

El backend se construye con Podman, se importa al containerd de k3s y se publica
con un Service `LoadBalancer` de k3s en el puerto `9090`.

## Firewall del servidor

Como el router ya redirige `8000` y `9090` hacia `192.168.1.74`, el servidor
tambien debe permitir esos puertos.

Si usas `ufw`, ejecuta:

```bash
sudo ufw allow 2222/tcp comment 'SSH'
sudo ufw allow 8000/tcp comment 'Streamlit AGENTE'
sudo ufw allow 9090/tcp comment 'FastAPI AGENTE'
sudo ufw reload
sudo ufw status numbered
```

Si `ufw` esta inactivo y quieres activarlo, primero confirma que SSH quede
permitido por el puerto correcto:

```bash
sudo ufw allow 2222/tcp comment 'SSH'
sudo ufw allow 8000/tcp comment 'Streamlit AGENTE'
sudo ufw allow 9090/tcp comment 'FastAPI AGENTE'
sudo ufw enable
sudo ufw status numbered
```

Antes de desplegar, desde la raiz del proyecto en el servidor, crea los secrets:

```bash
bash scripts/despliegue/crear_secrets_backend.sh
```

Ese script toma como fuente el archivo `.env` que existe en la raiz de
`PROYECTO FINAL` en el servidor. No mete `.env` dentro de la imagen.

El script crea:

- `eventos-backend-config` con variables no sensibles tomadas desde `.env`
- `eventos-backend-secret` desde `.env`
- `eventos-postgres-certificados` desde `certs/`
- `eventos-rag-env` desde `entrega-john/.env`
- `eventos-rag-certificados` desde `entrega-john/certs/`

Las rutas SSL de PostgreSQL se ajustan automaticamente a las rutas internas del
contenedor:

```text
POSTGRES_SSLROOTCERT=/app/certs/server-ca.pem
POSTGRES_SSLCERT=/app/certs/client-cert.pem
POSTGRES_SSLKEY=/app/certs/client-key.pem
```

Luego despliega:

```bash
bash scripts/despliegue/desplegar_backend_k3s.sh
```

Verifica:

```bash
sudo k3s kubectl -n eventos get pods
sudo k3s kubectl -n eventos get svc
sudo k3s kubectl -n eventos get ingress
curl -i http://190.238.16.227:9090/api/salud
```

Logs:

```bash
sudo k3s kubectl -n eventos logs -f deployment/eventos-backend
```

## Frontend Streamlit en Podman

El frontend se ejecuta fuera del cluster, con Podman rootless, y consume el
backend por la IP publica.

```bash
bash scripts/despliegue/desplegar_frontend_podman.sh
```

Verifica:

```bash
podman ps
podman logs -f eventos-frontend
curl -I http://190.238.16.227:8000
```

## Comandos utiles

Reiniciar backend:

```bash
sudo k3s kubectl -n eventos rollout restart deployment/eventos-backend
```

Reiniciar frontend:

```bash
podman restart eventos-frontend
```

Eliminar frontend:

```bash
podman rm -f eventos-frontend
```

Ver configuracion aplicada:

```bash
sudo k3s kubectl -n eventos describe deployment eventos-backend
sudo k3s kubectl -n eventos describe ingress eventos-backend
```
