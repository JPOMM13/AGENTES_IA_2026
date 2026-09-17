# Conexión a la base del proyecto — john

## 1. Instalar
```
pip install "psycopg[binary,pool]" python-dotenv
```

## 2. Preparar el archivo de credenciales ⚠️
En esta carpeta hay un archivo **`RENOMBRAR-A-.env.txt`**. Renómbralo a **`.env`**:
```bash
mv "RENOMBRAR-A-.env.txt" .env      # macOS / Linux
ren "RENOMBRAR-A-.env.txt" .env     # Windows
```
> Los archivos que empiezan con punto están **ocultos**. En macOS los ves con
> `Cmd + Shift + .` · En Windows, activando "Elementos ocultos".

## 3. Colocar los archivos
```
tu-proyecto/
├── .env
├── datos.py
└── certs/  (server-ca.pem · client-cert.pem · client-key.pem)
```

## 4. Permisos (obligatorio)
```
chmod 600 certs/*.pem
```

## 5. Probar
```
python datos.py
```
Debe listar los esquemas y los 6 productos del catálogo.

---
- **Lees** todo; **escribes** en `core` y `rag`; en `memory` solo lectura (ahí escribe el agente).
- Antes del primer commit agrega a `.gitignore`: `.env`, `certs/`, `RENOMBRAR-A-.env.txt`
- La instancia se **apaga fuera de horario**. Si no conecta, consulta al grupo.
- El detalle completo está en **GUIA-CONEXION-EQUIPO.pdf**.
