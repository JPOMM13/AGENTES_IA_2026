from __future__ import annotations

"""Resolucion determinista de fechas escritas en espanol (Peru).

PRINCIPIO DE DISENO: "determinismo antes que LLM". Un cotizador no puede
depender de que el modelo adivine que "el proximo sabado" es el 17/10: la
fecha condiciona la regla de 72 h, el calendario y el stock. Por eso toda la
resolucion vive aqui, en funciones puras que reciben `hoy` como parametro
(nunca llaman a date.today() dentro de la logica), para poder probarlas con
cualquier fecha de referencia y reproducir evals en el futuro.

Convenciones:
- Entrada: texto libre del usuario (con o sin tildes, mayusculas, etc.).
- Salida: `ResultadoFecha` con fecha ISO completa, fecha parcial (dia/mes/anio
  sueltos), si necesita confirmacion del cliente, el fragmento detectado, una
  nota explicable y un error cuando la fecha es imposible o ya paso.
"""

import calendar
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta


# VOCABULARIO: nombres en espanol que entiende el resolutor (sin tildes porque
# el texto se normaliza antes de comparar).
DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}
NOMBRES_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
NOMBRES_MES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

# VOCABULARIO NUMERICO: para "en dos semanas", "en quince dias", "cincuenta personas".
UNIDADES = {
    "cero": 0,
    "un": 1,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiuno": 21,
    "veintiun": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
}
DECENAS = {
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
}
CENTENAS = {
    "cien": 100,
    "ciento": 100,
    "doscientos": 200,
    "doscientas": 200,
    "trescientos": 300,
    "trescientas": 300,
    "cuatrocientos": 400,
    "cuatrocientas": 400,
    "quinientos": 500,
    "quinientas": 500,
    "seiscientos": 600,
    "seiscientas": 600,
    "setecientos": 700,
    "setecientas": 700,
    "ochocientos": 800,
    "ochocientas": 800,
    "novecientos": 900,
    "novecientas": 900,
}
PALABRAS_NUMERO = {**UNIDADES, **DECENAS, **CENTENAS, "mil": 1000}


@dataclass(frozen=True)
class ResultadoFecha:
    """Resultado explicable de interpretar una fecha escrita por el usuario.

    - fecha_iso: fecha completa lista para el estado (YYYY-MM-DD) o None.
    - fecha_parcial: dia/mes/anio sueltos cuando el usuario no dio todo.
    - necesita_confirmacion: True cuando hubo una suposicion (por ejemplo
      "la proxima semana" o un dia sin anio que ya paso este anio).
    - texto_detectado: fragmento original que origino la interpretacion.
    - nota: explicacion en lenguaje natural para mostrar al cliente.
    - error: mensaje cuando la fecha es imposible (31/02) o ya paso.
    - rango_sugerido: (inicio, fin) ISO cuando la expresion describe un rango
      ("la proxima semana", "a fin de mes") y el bot debe pedir el dia exacto.
    """

    fecha_iso: str | None = None
    fecha_parcial: dict[str, int | None] | None = None
    necesita_confirmacion: bool = False
    texto_detectado: str | None = None
    nota: str | None = None
    error: str | None = None
    rango_sugerido: tuple[str, str] | None = None

    @property
    def encontro_algo(self) -> bool:
        """Indica si el texto contenia alguna senal de fecha."""
        return bool(self.fecha_iso or self.fecha_parcial or self.error or self.rango_sugerido)


# RELOJ UNICO DEL SISTEMA: toda regla que dependa de "hoy" pasa por aqui.
def obtener_hoy() -> date:
    """Devuelve la fecha de referencia del sistema.

    Por que: las reglas de 72 h y la resolucion de fechas relativas dependen
    de "hoy". Centralizarlo permite fijar la fecha con COTIZADOR_FECHA_HOY
    (formato YYYY-MM-DD) para evals y demos reproducibles sin tocar codigo.
    """
    fijada = os.getenv("COTIZADOR_FECHA_HOY", "").strip()
    if fijada:
        try:
            return date.fromisoformat(fijada)
        except ValueError:
            pass
    return date.today()


# NORMALIZACION: compara siempre sin tildes ni mayusculas ("Sábado" == "sabado").
def normalizar_texto(texto: str) -> str:
    """Pasa a minusculas, quita tildes/dieresis y colapsa espacios."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(caracter for caracter in descompuesto if not unicodedata.combining(caracter))
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


# NUMEROS EN PALABRAS: "cincuenta" -> 50, "ciento veinte" -> 120, "treinta y cinco" -> 35.
def palabras_a_numero(texto: str) -> int | None:
    """Convierte un numero escrito en palabras (hasta 999) a entero; None si no lo es."""
    tokens = [token for token in normalizar_texto(texto).split() if token != "y"]
    if not tokens or any(token not in PALABRAS_NUMERO for token in tokens):
        return None
    total = 0
    for token in tokens:
        valor = PALABRAS_NUMERO[token]
        if valor == 1000:
            total = (total or 1) * 1000
        else:
            total += valor
    return total


# NUMEROS MIXTOS: acepta "50" o "cincuenta" con la misma funcion.
def interpretar_numero(texto: str) -> int | None:
    """Devuelve un entero desde digitos o palabras."""
    limpio = normalizar_texto(texto)
    if limpio.isdigit():
        return int(limpio)
    return palabras_a_numero(limpio)


# FORMATO LEGIBLE: "sabado 17 de octubre de 2026" para confirmar con el cliente.
def describir_fecha(fecha_iso: str | None) -> str:
    """Convierte una fecha ISO en texto natural con dia de semana."""
    if not fecha_iso:
        return "fecha pendiente"
    try:
        valor = date.fromisoformat(fecha_iso)
    except ValueError:
        return fecha_iso
    return f"{NOMBRES_DIA[valor.weekday()]} {valor.day} de {NOMBRES_MES[valor.month - 1]} de {valor.year}"


# RESOLUTOR PRINCIPAL: una sola entrada para fechas absolutas, relativas y parciales.
def resolver_fecha_relativa(texto: str, hoy: date) -> ResultadoFecha:
    """Interpreta la fecha del evento a partir del texto y de la fecha de referencia.

    Orden de prioridad (del mas explicito al mas ambiguo), porque una fecha
    explicita nunca debe ser pisada por una expresion relativa que aparezca en
    la misma frase ("el 25 de octubre, no mañana"):
    1. ISO y dd/mm[/aaaa].
    2. "15 de noviembre [de 2026]" o "noviembre 15".
    3. Relativas con aritmetica exacta: hoy, mañana, pasado mañana, en N dias,
       en N semanas, dia de la semana (este/el/proximo X), fin de semana.
    4. Rangos ambiguos: la proxima semana, a fin de mes (se pide el dia exacto).
    5. Parciales: solo dia ("el 3"), solo mes ("diciembre"), solo anio.
    """
    normalizado = normalizar_texto(texto)

    for resolutor in (
        _resolver_iso,
        _resolver_numerica,
        _resolver_dia_mes,
        _resolver_mes_dia,
        _resolver_relativa_exacta,
        _resolver_rango_ambiguo,
    ):
        resultado = resolutor(normalizado, hoy)
        if resultado is not None:
            return resultado

    parcial = _resolver_parcial(normalizado, hoy)
    if parcial is not None:
        return parcial
    return ResultadoFecha()


# --- Resolutores especificos -------------------------------------------------


def _resolver_iso(texto: str, hoy: date) -> ResultadoFecha | None:
    """YYYY-MM-DD o YYYY/MM/DD: siempre con anio explicito."""
    match = re.search(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)", texto)
    if not match:
        return None
    anio, mes, dia = (int(parte) for parte in match.groups())
    return _construir_resultado(hoy, dia, mes, anio, match.group(0), anio_explicito=True)


def _resolver_numerica(texto: str, hoy: date) -> ResultadoFecha | None:
    """dd/mm, dd-mm, dd/mm/aaaa o dd/mm/aa. Los lookarounds evitan telefonos."""
    match = re.search(r"(?<!\d)(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2}|\d{4}))?(?!\d)", texto)
    if not match:
        return None
    dia, mes, anio_texto = match.groups()
    anio = None
    if anio_texto:
        anio = int(anio_texto) if len(anio_texto) == 4 else 2000 + int(anio_texto)
    return _construir_resultado(hoy, int(dia), int(mes), anio, match.group(0), anio_explicito=anio is not None)


def _resolver_dia_mes(texto: str, hoy: date) -> ResultadoFecha | None:
    """'15 de noviembre', '15 noviembre', '15 de noviembre del 2026'."""
    patron_mes = "|".join(MESES)
    match = re.search(rf"(?<!\d)(\d{{1,2}})\s*(?:de\s+)?({patron_mes})\b(?:\s*(?:de|del)?\s*(20\d{{2}}))?", texto)
    if not match:
        return None
    dia, nombre_mes, anio_texto = match.groups()
    anio = int(anio_texto) if anio_texto else None
    return _construir_resultado(hoy, int(dia), MESES[nombre_mes], anio, match.group(0), anio_explicito=anio is not None)


def _resolver_mes_dia(texto: str, hoy: date) -> ResultadoFecha | None:
    """'noviembre 15' (estilo informal). Excluye 'diciembre 50 personas' y anios."""
    patron_mes = "|".join(MESES)
    match = re.search(
        rf"\b({patron_mes})\s+(\d{{1,2}})(?!\d)(?!\s*(?:personas|pax|invitados|asistentes|horas|hrs|am|pm|:))",
        texto,
    )
    if not match:
        return None
    nombre_mes, dia = match.groups()
    return _construir_resultado(hoy, int(dia), MESES[nombre_mes], None, match.group(0), anio_explicito=False)


def _resolver_relativa_exacta(texto: str, hoy: date) -> ResultadoFecha | None:
    """Expresiones relativas que se resuelven con aritmetica de calendario."""
    # "por la manana" es hora del dia, no el dia de manana: se descarta antes de buscar.
    texto_sin_horas = re.sub(r"\b(?:en|por|de|a)\s+la\s+manana\b", " ", texto)

    if re.search(r"\bpasado\s+manana\b", texto_sin_horas):
        return _resultado_exacto(hoy + timedelta(days=2), "pasado manana", confirmar=False)
    if re.search(r"\bmanana\b", texto_sin_horas):
        return _resultado_exacto(hoy + timedelta(days=1), "manana", confirmar=False)
    if re.search(r"\bhoy\b(?!\s+(?:en\s+dia|por\s+hoy))", texto_sin_horas) and re.search(
        r"\b(?:para|es|seria|sera|evento)\s+hoy\b|\bhoy\s+(?:mismo|en\s+la\s+noche|a\s+las)", texto_sin_horas
    ):
        return _resultado_exacto(hoy, "hoy", confirmar=False)

    # "en 15 dias", "dentro de dos semanas", "en un mes".
    patron_cantidad = r"(\d{1,3}|" + "|".join(sorted(PALABRAS_NUMERO, key=len, reverse=True)) + r"(?:\s+y\s+\w+)?)"
    match = re.search(rf"\b(?:en|dentro\s+de)\s+{patron_cantidad}\s+(dias?|semanas?|mes(?:es)?)\b", texto_sin_horas)
    if match:
        cantidad = interpretar_numero(match.group(1))
        unidad = match.group(2)
        if cantidad is not None:
            if unidad.startswith("dia"):
                return _resultado_exacto(hoy + timedelta(days=cantidad), match.group(0), confirmar=False)
            if unidad.startswith("semana"):
                return _resultado_exacto(
                    hoy + timedelta(weeks=cantidad),
                    match.group(0),
                    confirmar=True,
                    nota=f"Asumi {NOMBRES_DIA[hoy.weekday()]} {_fecha_corta(hoy + timedelta(weeks=cantidad))}, el mismo dia de la semana que hoy.",
                )
            if unidad.startswith("mes"):
                return _resultado_exacto(_sumar_meses(hoy, cantidad), match.group(0), confirmar=True, nota="Asumi el mismo dia del mes.")

    # "fin de semana" antes que "sabado/domingo" para no capturar solo una parte.
    match = re.search(r"\b(este|el\s+proximo|proximo|el\s+siguiente|siguiente|el)?\s*fin\s+de\s+semana(\s+que\s+viene)?\b", texto_sin_horas)
    if match:
        sabado = _proximo_dia_semana(hoy, 5, incluir_hoy=(match.group(1) == "este"))
        if match.group(1) in {"el proximo", "proximo", "el siguiente", "siguiente"} or match.group(2):
            # "el proximo fin de semana" dicho un sabado/domingo se refiere al siguiente.
            if hoy.weekday() >= 5:
                sabado = _proximo_dia_semana(hoy + timedelta(days=1), 5, incluir_hoy=False)
        return _resultado_exacto(
            sabado,
            match.group(0).strip(),
            confirmar=True,
            nota=f"Entendi el fin de semana del sabado {_fecha_corta(sabado)}; si es domingo u otra fecha, dimelo.",
        )

    patron_dias = "|".join(DIAS_SEMANA)
    # "el sabado 24": dia de la semana + numero de dia -> manda el numero (proximo 24 desde hoy); si el dia de la
    # semana no calza con ese numero, se registra el numero y se pide confirmacion en vez de adivinar.
    match = re.search(rf"\b({patron_dias})\s+(\d{{1,2}})\b(?!\s*(?:de|/|-)\s*\w)", texto_sin_horas)
    if match:
        objetivo = DIAS_SEMANA[match.group(1)]
        dia = int(match.group(2))
        if 1 <= dia <= 31:
            candidato = None
            anio, mes = hoy.year, hoy.month
            for _ in range(3):
                try:
                    posible = date(anio, mes, dia)
                except ValueError:
                    posible = None
                if posible and posible >= hoy:
                    candidato = posible
                    break
                mes += 1
                if mes > 12:
                    mes, anio = 1, anio + 1
            if candidato:
                calza = candidato.weekday() == objetivo
                nota = None if calza else f"El {dia} de {NOMBRES_MES[candidato.month]} cae {NOMBRES_DIA[candidato.weekday()]}, no {NOMBRES_DIA[objetivo]}; registre el {_fecha_corta(candidato)}, confirmame si es correcto."
                return _resultado_exacto(candidato, match.group(0).strip(), confirmar=not calza, nota=nota)

    match = re.search(rf"\b(este|el\s+proximo|proximo|el\s+siguiente|siguiente|el)?\s*({patron_dias})\b(\s+que\s+viene|\s+siguiente|\s+proximo)?", texto_sin_horas)
    if match:
        modificador = (match.group(1) or "").strip()
        sufijo = (match.group(3) or "").strip()
        objetivo = DIAS_SEMANA[match.group(2)]
        incluir_hoy = modificador == "este"
        fecha = _proximo_dia_semana(hoy, objetivo, incluir_hoy=incluir_hoy)
        es_proximo = modificador in {"el proximo", "proximo", "el siguiente", "siguiente"} or bool(sufijo)
        nota = f"Entendi {NOMBRES_DIA[objetivo]} {_fecha_corta(fecha)}; si te refieres a otra fecha, dimelo."
        # "proximo X" es ambiguo en espanol (puede ser el de esta semana o el de la siguiente):
        # se toma el mas cercano y se pide confirmacion en lugar de adivinar.
        return _resultado_exacto(fecha, match.group(0).strip(), confirmar=es_proximo, nota=nota if es_proximo else None)
    return None


def _resolver_rango_ambiguo(texto: str, hoy: date) -> ResultadoFecha | None:
    """Rangos ("la proxima semana", "a fin de mes"): no se adivina el dia, se pregunta."""
    match = re.search(r"\b(?:la\s+)?(?:proxima|siguiente)\s+semana\b|\b(?:la\s+)?semana\s+(?:que\s+viene|entrante|siguiente)\b", texto)
    if match:
        lunes = hoy + timedelta(days=(7 - hoy.weekday()))
        domingo = lunes + timedelta(days=6)
        sabado = lunes + timedelta(days=5)
        return ResultadoFecha(
            fecha_iso=None,
            necesita_confirmacion=True,
            texto_detectado=match.group(0).strip(),
            rango_sugerido=(lunes.isoformat(), domingo.isoformat()),
            nota=(
                f"La proxima semana va del lunes {_fecha_corta(lunes)} al domingo {_fecha_corta(domingo)}. "
                f"Que dia exacto seria el evento? Si es un sabado, seria el {_fecha_corta(sabado)}."
            ),
        )

    match = re.search(r"\b(?:a\s+)?(?:fin|fines|finales)\s+de(?:l)?\s+mes\b", texto)
    if match:
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        fin_mes = date(hoy.year, hoy.month, ultimo_dia)
        # Si ya estamos en la ultima semana, "fin de mes" suele referirse al mes siguiente.
        if (fin_mes - hoy).days < 7:
            siguiente = _sumar_meses(date(hoy.year, hoy.month, 1), 1)
            fin_mes = date(siguiente.year, siguiente.month, calendar.monthrange(siguiente.year, siguiente.month)[1])
        inicio = fin_mes - timedelta(days=6)
        return ResultadoFecha(
            fecha_iso=None,
            necesita_confirmacion=True,
            texto_detectado=match.group(0).strip(),
            rango_sugerido=(inicio.isoformat(), fin_mes.isoformat()),
            nota=f"Fin de mes seria entre el {_fecha_corta(inicio)} y el {_fecha_corta(fin_mes)}. Que dia exacto seria el evento?",
        )
    return None


def _resolver_parcial(texto: str, hoy: date) -> ResultadoFecha | None:
    """Dia suelto ("el 3"), mes suelto ("diciembre") o anio suelto."""
    parcial: dict[str, int | None] = {"dia": None, "mes": None, "anio": None}
    for nombre_mes, numero in MESES.items():
        if re.search(rf"\b{nombre_mes}\b", texto):
            parcial["mes"] = numero
            break

    match_dia = re.search(r"\b(?:para\s+el|el\s+dia|el|dia)\s+(\d{1,2})(?!\d)(?!\s*(?:personas|pax|invitados|asistentes|%|soles|:))", texto)
    if match_dia and 1 <= int(match_dia.group(1)) <= 31:
        parcial["dia"] = int(match_dia.group(1))

    match_anio = re.search(r"\b(20\d{2})\b", texto)
    if match_anio:
        parcial["anio"] = int(match_anio.group(1))
    elif parcial["mes"] is not None:
        # Un mes sin anio se interpreta como el proximo en ocurrir (diciembre dicho en octubre = este anio;
        # febrero dicho en octubre = el anio siguiente).
        parcial["anio"] = hoy.year if parcial["mes"] >= hoy.month else hoy.year + 1

    if all(valor is None for valor in parcial.values()):
        return None
    texto_detectado = (match_dia.group(0) if match_dia else None) or (match_anio.group(0) if match_anio else None)
    return ResultadoFecha(fecha_parcial=parcial, texto_detectado=texto_detectado)


# --- Ayudantes ---------------------------------------------------------------


def _construir_resultado(hoy: date, dia: int, mes: int, anio: int | None, texto_detectado: str, anio_explicito: bool) -> ResultadoFecha:
    """Valida calendario real y decide anio cuando el usuario no lo dio."""
    anio_base = anio if anio is not None else hoy.year
    try:
        fecha = date(anio_base, mes, dia)
    except ValueError:
        return ResultadoFecha(
            texto_detectado=texto_detectado,
            error=f"La fecha indicada no es valida: {dia:02d}/{mes:02d}/{anio_base}.",
        )
    if fecha < hoy:
        if anio_explicito:
            return ResultadoFecha(
                texto_detectado=texto_detectado,
                error=f"La fecha {fecha.strftime('%d/%m/%Y')} ya paso (hoy es {hoy.strftime('%d/%m/%Y')}). Indicame una fecha futura.",
            )
        # Sin anio explicito y ya pasada: el cliente casi siempre habla del proximo anio.
        try:
            fecha_siguiente = date(anio_base + 1, mes, dia)
        except ValueError:
            return ResultadoFecha(texto_detectado=texto_detectado, error=f"La fecha indicada no es valida: {dia:02d}/{mes:02d}/{anio_base + 1}.")
        return ResultadoFecha(
            fecha_iso=fecha_siguiente.isoformat(),
            necesita_confirmacion=True,
            texto_detectado=texto_detectado,
            nota=f"Como el {dia} de {NOMBRES_MES[mes - 1]} de {anio_base} ya paso, lo registre para {anio_base + 1}. Confirmame si es correcto.",
        )
    return ResultadoFecha(fecha_iso=fecha.isoformat(), texto_detectado=texto_detectado)


def _resultado_exacto(fecha: date, texto_detectado: str, confirmar: bool, nota: str | None = None) -> ResultadoFecha:
    """Empaqueta una fecha calculada con aritmetica (nunca es invalida)."""
    return ResultadoFecha(
        fecha_iso=fecha.isoformat(),
        necesita_confirmacion=confirmar,
        texto_detectado=texto_detectado,
        nota=nota,
    )


def _proximo_dia_semana(hoy: date, objetivo: int, incluir_hoy: bool) -> date:
    """Siguiente ocurrencia del dia de semana `objetivo` (0=lunes ... 6=domingo)."""
    delta = (objetivo - hoy.weekday()) % 7
    if delta == 0 and not incluir_hoy:
        delta = 7
    return hoy + timedelta(days=delta)


def _sumar_meses(fecha: date, meses: int) -> date:
    """Suma meses manteniendo el dia (recortado al ultimo dia si no existe)."""
    mes_indice = fecha.month - 1 + meses
    anio = fecha.year + mes_indice // 12
    mes = mes_indice % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _fecha_corta(fecha: date) -> str:
    """dd/mm/aaaa para notas al cliente."""
    return fecha.strftime("%d/%m/%Y")
