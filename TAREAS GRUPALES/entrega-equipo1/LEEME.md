# Conexión a la base del proyecto — equipo1

## 1. Instalar
    pip install "psycopg[binary,pool]" python-dotenv

## 2. Colocar los archivos
    tu-proyecto/
    ├── .env              ← el de esta carpeta
    ├── datos.py          ← lo comparte Javier
    └── certs/
        ├── server-ca.pem
        ├── client-cert.pem
        └── client-key.pem

## 3. Permisos (obligatorio, si no PostgreSQL los rechaza)
    chmod 600 certs/*.pem

## 4. Probar
    python datos.py
Debe listar los esquemas y los 6 productos del catálogo.

## Qué puedes hacer
- Leer todo: catálogo, cobertura, disponibilidad, corpus y memoria.
- Escribir en `core` y `rag` (cargar datos de prueba, ingestar chunks).
- En `memory` solo lectura: ahí escribe el agente.

## Notas
- La instancia se apaga fuera de horario para ahorrar costo. Si no conecta,
  consulta al grupo antes de asumir que algo se rompió.
- Tu usuario y certificado son personales: hay trazabilidad por persona.
