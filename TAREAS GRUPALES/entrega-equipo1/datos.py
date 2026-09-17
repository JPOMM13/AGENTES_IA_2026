"""Capa de acceso a datos del Agente de Eventos — Grupo 5.

Este módulo es el ÚNICO punto por el que el agente toca la base de datos.
Las tools de LangChain/LangGraph envuelven estas funciones; ninguna redacta SQL
por su cuenta. Es el mismo patrón del repo de la S25: una función por intención,
con parámetros tipados, y la consulta armada aquí adentro.

Portabilidad: solo depende de `DATABASE_URL` (una URL estándar de PostgreSQL).
Funciona igual en una laptop, en Azure, en Cloud Run o en Colab — ver §"Entornos".

Instalación:
    pip install "psycopg[binary,pool]" python-dotenv
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Iterable, Sequence

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

# ---------------------------------------------------------------------------
# 1. POOL DE CONEXIONES
#    La instancia es pequeña (db-g1-small) y su límite de conexiones también.
#    Un pool acotado evita que cinco integrantes más el agente lo agoten; y
#    reutilizar conexiones ahorra el handshake TLS, que con certificados de
#    cliente no es gratis (importa si el agente corre fuera de GCP).
# ---------------------------------------------------------------------------
_POOL: ConnectionPool | None = None


def _pool() -> ConnectionPool:
    global _POOL
    if _POOL is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "Falta DATABASE_URL. Copia credenciales-equipo.env.example a .env "
                "y completa los datos que te entregó el administrador."
            )
        _POOL = ConnectionPool(
            url,
            min_size=1,      # una conexión viva: evita reconectar en cada turno
            max_size=5,      # techo por proceso, para no agotar la instancia
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _POOL


@contextmanager
def _cursor():
    with _pool().connection() as conn, conn.cursor() as cur:
        yield cur


# ---------------------------------------------------------------------------
# 2. CATÁLOGO, COBERTURA Y DISPONIBILIDAD  (esquema core — solo lectura)
#    Estas tres se consultan SIEMPRE antes de recomendar o cotizar (RAG-050).
# ---------------------------------------------------------------------------

def consultar_catalogo(servicio: str | None = None) -> list[dict[str, Any]]:
    """Productos activos del catálogo oficial. Única fuente válida de precios."""
    with _cursor() as cur:
        cur.execute(
            """SELECT sku, servicio, nombre, capacidad_l, unidades, precio_base, moneda
                 FROM core.productos
                WHERE activo AND (%s IS NULL OR servicio = %s)
                ORDER BY servicio, precio_base""",
            (servicio, servicio),
        )
        return cur.fetchall()


def verificar_cobertura(distrito: str, servicio: str) -> bool:
    """¿Se atiende ese distrito para ese servicio? Que aparezca en la
    conversación no implica que tenga cobertura: solo esta función lo confirma."""
    with _cursor() as cur:
        cur.execute(
            """SELECT 1 FROM core.cobertura
                WHERE lower(distrito) = lower(%s) AND servicio = %s AND activo""",
            (distrito, servicio),
        )
        return cur.fetchone() is not None


def consultar_disponibilidad(sku: str, fecha: str) -> bool:
    """Disponibilidad real para una fecha. Si no hay registro, NO se asume
    disponible: preferimos derivar antes que prometer lo que no se puede cumplir."""
    with _cursor() as cur:
        cur.execute(
            """SELECT d.cupos_total - d.cupos_usados AS libres
                 FROM core.disponibilidad d
                 JOIN core.productos p ON p.id = d.producto_id
                WHERE p.sku = %s AND d.fecha = %s""",
            (sku, fecha),
        )
        fila = cur.fetchone()
        return bool(fila and fila["libres"] > 0)


# ---------------------------------------------------------------------------
# 3. SOLICITUD Y COTIZACIÓN  (esquema core — escritura acotada)
#    El importe NO se calcula aquí ni en el modelo: se arma con los precios del
#    catálogo y los parámetros vigentes, y la base valida las reglas duras
#    mediante un trigger. Si la solicitud no es cotizable, el INSERT falla.
# ---------------------------------------------------------------------------

def registrar_solicitud(
    celular: str, servicio: str, fecha_evento: str, distrito: str,
    piso: int = 1, tiene_ascensor: bool = True, asistentes: int | None = None,
    thread_id: str | None = None,
) -> int:
    """Registra la necesidad del cliente y devuelve su id.

    Se registra TODA solicitud, incluso la que no podrá cotizarse (un quinto
    piso sin ascensor): hay que dejar constancia para poder derivarla.
    """
    with _cursor() as cur:
        cur.execute(
            """INSERT INTO core.clientes (celular_hash, celular_ultimos4)
               VALUES (core.fn_hash_celular(%s), right(%s, 4))
               ON CONFLICT (celular_hash) DO UPDATE SET nombre = core.clientes.nombre
               RETURNING id""",
            (celular, celular),
        )
        cliente_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO core.solicitudes
                 (cliente_id, servicio, fecha_evento, distrito, piso, tiene_ascensor,
                  asistentes, thread_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (cliente_id, servicio, fecha_evento, distrito, piso, tiene_ascensor,
             asistentes, thread_id),
        )
        return cur.fetchone()["id"]


def motivo_no_cotizable(solicitud_id: int) -> str | None:
    """Devuelve el motivo por el que NO se puede cotizar, o None si todo cumple.

    Permite al agente explicar la razón y derivar ANTES de intentar la
    cotización, en vez de mostrarle al cliente un error de base de datos.
    """
    with _cursor() as cur:
        cur.execute("SELECT core.fn_motivo_no_cotizable(%s) AS motivo", (solicitud_id,))
        return cur.fetchone()["motivo"]


def emitir_cotizacion(solicitud_id: int, items: Sequence[tuple[str, int]]) -> dict[str, Any]:
    """Emite la cotización oficial. `items` son pares (sku, cantidad).

    Todos los importes salen del catálogo y de core.parametros. El modelo nunca
    calcula, redondea ni ajusta: solo presenta lo que devuelve esta función.
    Si la solicitud viola una regla dura, el trigger de la base aborta el INSERT.
    """
    with _pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT s.*, core.fn_parametro('igv') AS igv,
                      core.fn_parametro('recargo_piso_3_sin_ascensor') AS recargo_piso,
                      core.fn_parametro('recargo_unidad_adicional')    AS recargo_unidad,
                      core.fn_parametro('vigencia_cotizacion_horas')   AS vigencia_h
                 FROM core.solicitudes s WHERE s.id = %s""",
            (solicitud_id,),
        )
        sol = cur.fetchone()
        if sol is None:
            raise ValueError(f"La solicitud {solicitud_id} no existe")

        # --- Composición de líneas con precios oficiales ---
        lineas: list[dict[str, Any]] = []
        subtotal = Decimal("0")
        for sku, cantidad in items:
            cur.execute(
                "SELECT id, nombre, precio_base, servicio FROM core.productos WHERE sku=%s AND activo",
                (sku,),
            )
            prod = cur.fetchone()
            if prod is None:
                raise ValueError(f"El SKU {sku} no está activo en el catálogo")
            importe = prod["precio_base"] * cantidad
            lineas.append({"producto_id": prod["id"], "concepto": prod["nombre"],
                           "cantidad": cantidad, "precio_unitario": prod["precio_base"],
                           "subtotal": importe})
            subtotal += importe
            # Recargo por unidad adicional de barril (parámetro vigente, no constante)
            if prod["servicio"] == "barril" and cantidad > 1:
                extra = sol["recargo_unidad"] * (cantidad - 1)
                lineas.append({"producto_id": None, "concepto": "Recargo por unidad adicional",
                               "cantidad": cantidad - 1,
                               "precio_unitario": sol["recargo_unidad"], "subtotal": extra})
                subtotal += extra

        # Recargo por acceso: solo aplica en el piso 3 sin ascensor. El piso 4 o
        # superior no llega hasta aquí — el trigger lo habrá rechazado antes.
        if not sol["tiene_ascensor"] and sol["piso"] == 3:
            lineas.append({"producto_id": None, "concepto": "Recargo piso 3 sin ascensor",
                           "cantidad": 1, "precio_unitario": sol["recargo_piso"],
                           "subtotal": sol["recargo_piso"]})
            subtotal += sol["recargo_piso"]

        impuestos = (subtotal * sol["igv"]).quantize(Decimal("0.01"))
        total = subtotal + impuestos

        # El trigger valida cobertura, anticipación y acceso antes de permitir
        # esta inserción. Si falla, psycopg levanta la excepción con el motivo.
        cur.execute(
            """INSERT INTO core.cotizaciones
                 (solicitud_id, subtotal, impuestos, total, vigencia_hasta)
               VALUES (%s,%s,%s,%s, now() + (%s || ' hours')::interval)
               RETURNING id, vigencia_hasta""",
            (solicitud_id, subtotal, impuestos, total, int(sol["vigencia_h"])),
        )
        cot = cur.fetchone()
        for ln in lineas:
            cur.execute(
                """INSERT INTO core.cotizacion_detalle
                     (cotizacion_id, producto_id, concepto, cantidad, precio_unitario, subtotal)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (cot["id"], ln["producto_id"], ln["concepto"], ln["cantidad"],
                 ln["precio_unitario"], ln["subtotal"]),
            )
        cur.execute("UPDATE core.solicitudes SET estado='cotizada' WHERE id=%s", (solicitud_id,))
        conn.commit()
        return {"cotizacion_id": cot["id"], "moneda": "PEN", "detalle": lineas,
                "subtotal": subtotal, "impuestos": impuestos, "total": total,
                "vigencia_hasta": cot["vigencia_hasta"]}


def derivar(cliente_id: int, motivo: str, contexto: dict[str, Any],
            solicitud_id: int | None = None, prioridad: str = "normal") -> int:
    """Deriva a un asesor humano con el paquete completo que exige RAG-080.

    La base valida que el contexto traiga los campos obligatorios: si falta
    'intencion', 'datos_capturados' o 'resumen', el INSERT se rechaza. Así el
    asesor nunca recibe una derivación incompleta.
    """
    import json
    with _pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO core.derivaciones
                 (solicitud_id, cliente_id, motivo, prioridad, contexto)
               VALUES (%s,%s,%s,%s,%s) RETURNING id""",
            (solicitud_id, cliente_id, motivo, prioridad, json.dumps(contexto)),
        )
        derivacion_id = cur.fetchone()["id"]
        if solicitud_id:
            cur.execute("UPDATE core.solicitudes SET estado='derivada' WHERE id=%s", (solicitud_id,))
        conn.commit()
        return derivacion_id


# ---------------------------------------------------------------------------
# 4. CONOCIMIENTO  (esquema rag)
#    El filtro por servicio ocurre ANTES de la similitud, como pide RAG-130 §4.
# ---------------------------------------------------------------------------

def buscar_conocimiento(embedding: Iterable[float], servicio: str = "general",
                        top_k: int = 3) -> list[dict[str, Any]]:
    """Recupera los chunks más relevantes para el servicio en cuestión."""
    with _cursor() as cur:
        cur.execute("SELECT * FROM rag.fn_buscar(%s::vector, %s, %s)",
                    (list(embedding), servicio, top_k))
        return cur.fetchall()


# ---------------------------------------------------------------------------
# 5. MEMORIA DE LARGO PLAZO  (esquema memory)
#    El aislamiento por cliente es una condición booleana en la consulta, no una
#    cuestión de qué tan parecidos resulten los vectores.
# ---------------------------------------------------------------------------

def recordar(cliente_id: int, embedding: Iterable[float], top_k: int = 5) -> list[dict[str, Any]]:
    """Preferencias vigentes del cliente, ordenadas por relevancia semántica."""
    with _cursor() as cur:
        cur.execute("SELECT * FROM memory.fn_recordar(%s, %s::vector, %s)",
                    (cliente_id, list(embedding), top_k))
        return cur.fetchall()


def guardar_preferencia(cliente_id: int, categoria: str, contenido: str,
                        embedding: Iterable[float], confianza: str = "media",
                        umbral_duplicado: float = 0.05) -> int | None:
    """Persiste una preferencia, solo si hay consentimiento y no es duplicada.

    Dos guardas antes de escribir, siguiendo las lecciones de la S20:
      1. Sin consentimiento vigente no se guarda nada (además, la llave foránea
         lo haría imposible).
      2. Si ya existe algo casi idéntico (distancia < umbral), no se duplica.
    Devuelve el id creado, o None si no correspondía guardar.
    """
    with _pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id FROM memory.consentimientos
                WHERE cliente_id=%s AND tipo='obligatorio' AND otorgado
                  AND revocado_en IS NULL
                ORDER BY creado_en DESC LIMIT 1""",
            (cliente_id,),
        )
        consent = cur.fetchone()
        if consent is None:
            return None     # sin consentimiento explícito, no hay memoria

        cur.execute(
            """SELECT id FROM memory.preferencias_cliente
                WHERE cliente_id=%s AND vigente AND (embedding <=> %s::vector) < %s
                LIMIT 1""",
            (cliente_id, list(embedding), umbral_duplicado),
        )
        if cur.fetchone():
            return None     # ya lo sabíamos

        cur.execute(
            """INSERT INTO memory.preferencias_cliente
                 (cliente_id, consent_id, categoria, contenido, embedding, confianza)
               VALUES (%s,%s,%s,%s,%s::vector,%s) RETURNING id""",
            (cliente_id, consent["id"], categoria, contenido, list(embedding), confianza),
        )
        nuevo = cur.fetchone()["id"]
        conn.commit()
        return nuevo


def registrar_episodio(cliente_id: int | None, thread_id: str, etapa: str,
                       desenlace: str, resumen: str | None = None) -> None:
    """Deja constancia de dónde terminó la conversación (RAG-110).

    Alimenta el análisis de abandono: en qué etapa se cae la gente. Es el insumo
    para las métricas de evaluación del proyecto.
    """
    with _pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO memory.episodios (cliente_id, thread_id, etapa, desenlace, resumen)
               VALUES (%s,%s,%s,%s,%s)""",
            (cliente_id, thread_id, etapa, desenlace, resumen),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# 6. ENTORNOS — cómo se conecta esto desde donde el equipo trabaje
#
#   LOCAL (laptop)
#       .env con DATABASE_URL y la carpeta certs/ al lado. Nada más.
#
#   GOOGLE COLAB
#       Subir los .pem a /content/certs/ (o montarlos desde Drive) y definir
#       DATABASE_URL con esas rutas. Guardar la URL en los "Secrets" de Colab
#       para no dejarla escrita en el notebook.
#
#   AZURE CONTAINER APPS / CLOUD RUN / CUALQUIER CONTENEDOR
#       Los .pem como secretos montados en un volumen, y DATABASE_URL como
#       variable de entorno apuntando a esas rutas. El código no cambia.
#
#   CI (GitHub Actions)
#       Certificados en secrets del repositorio, escritos a disco en un paso
#       previo. Útil para correr los tests de evaluación contra datos reales.
#
#   El módulo no importa ninguna librería de Google: si mañana el servicio se
#   mueve a otra nube, solo cambia DATABASE_URL.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Prueba de humo: verifica conectividad y que el modelo esté cargado.
    with _cursor() as cur:
        cur.execute("SELECT current_user, current_database()")
        print("Conectado:", cur.fetchone())
        cur.execute("""SELECT table_schema, count(*) AS tablas
                         FROM information_schema.tables
                        WHERE table_schema IN ('core','rag','memory')
                        GROUP BY table_schema ORDER BY table_schema""")
        for fila in cur.fetchall():
            print(f"  {fila['table_schema']}: {fila['tablas']} tablas")
    print("Catálogo activo:", len(consultar_catalogo()), "productos")
