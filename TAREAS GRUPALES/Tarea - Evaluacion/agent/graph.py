"""Monoagente LangGraph. Sesiones aisladas, extracción inyectable para tests."""
import json
import re
import unicodedata
from copy import deepcopy
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from agent.state import AgentState, Extraction
from agent.prompts import EXTRACT_PROMPT, OPENINGS
from agent import tools

REQUIRED = ("event_type", "attendees", "event_date", "location")


# Oculta patrones comunes de correo y teléfono antes de enviar el mensaje al grafo y las trazas.
def redact(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    return re.sub(r"(?<!\d)(?:\+?\d[ -]?){9,15}(?!\d)", "[PHONE]", text)


# Busca expresiones que requieren atención humana y devuelve el motivo, o None si no encuentra ninguna.
def guard(message):
    text = ''.join(c for c in unicodedata.normalize('NFD', message.lower()) if unicodedata.category(c) != 'Mn')
    for reason, pattern in [
        ("human_support", r"\b(asesor|humano|persona real)\b"),
        ("discount", r"\b(descuento|rebaja)\b"),
        ("payment", r"\b(pagar|pago|tarjeta|transferencia)\b"),
        ("purchase", r"\b(comprar|compra|reservar|reserva)\b"),
        ("complaint", r"\b(reclamo|queja)\b"),
        ("privacy", r"\b(ignora|inventa|inventado|contrasena|datos de otro|sin consentimiento)\b"),
        ("exception", r"\b(excepcion|saltate)\b")]:
        if re.search(pattern, text):
            return reason
    return None

class Opening(BaseModel):
    choice: Literal[0, 1, 2]

class OpenAIInterpreter:
    # Configura el único LLM del agente y exige que la extracción respete el esquema Extraction.
    def __init__(self, settings):
        from config import require_key
        from langchain_openai import ChatOpenAI
        require_key("OPENAI_API_KEY")
        self.llm = ChatOpenAI(model=settings.model, max_retries=0, timeout=45)
        self.extractor = self.llm.with_structured_output(Extraction)

    # Envía al LLM el mensaje, los datos previos y el reloj para extraer intención y campos estructurados.
    def extract(self, message, state, now, event_types):
        context = {k: state.get(k) for k in REQUIRED + ("budget", "product_categories")}
        result = self.extractor.invoke([
            ("system", EXTRACT_PROMPT),
            ("human", json.dumps({"reference_datetime": now.isoformat(), "event_types": event_types,
                                  "previous_state": context, "message": message}, ensure_ascii=False))])
        return result

    # Pide al LLM elegir una apertura aprobada; no le permite redactar ni modificar los importes.
    def opening(self, response):
        result = self.llm.with_structured_output(Opening).invoke([
            ("system", "Selecciona la apertura más natural para esta respuesta; devuelve únicamente su índice. " + str(OPENINGS)),
            ("human", response)])
        return OPENINGS[result.choice]

class QuoteAgent:
    # Recibe repositorio, intérprete y reloj opcional; construye el grafo que procesará cada turno.
    def __init__(self, repo, interpreter, now=None):
        self.repo, self.interpreter = repo, interpreter
        self._fixed_now = now
        self.now = now or datetime.now(ZoneInfo("America/Lima"))
        self.graph = self._build()

    # Registra una operación y sus intentos; reintenta únicamente fallos de conexión o timeout hasta seis intentos totales.
    def _call(self, state, name, fn):
        state["tools_called"].append(name)
        # Un intento inicial + hasta cinco reintentos; no reintentar errores permanentes.
        for attempt in range(1, 7):
            state["attempts"][name] = attempt
            try:
                return fn()
            except (TimeoutError, ConnectionError):
                if attempt == 6:
                    raise

    # Marca la necesidad de un asesor, guarda el motivo y elimina cualquier recomendación o cotización vigente.
    def _handoff(self, state, reason):
        state.update(needs_human=True, handoff_reason=reason, quote=None, recommended_option=None)

    # Aplica primero el filtro de derivación; si permite continuar, interpreta el mensaje y valida la extracción.
    def _understand(self, s):
        reason = guard(s["message"])
        if reason:
            s["intent"] = "human_support" if reason == "human_support" else "quotation"
            self._handoff(s, reason)
            return s
        try:
            extracted = self._call(s, "understand_request", lambda: self.interpreter.extract(
                s["message"], s, self.now, self.repo.get_event_types()))
            s["extracted"] = Extraction.model_validate(extracted).model_dump()
        except Exception:
            self._handoff(s, "persistent_failure")
        return s

    # Incorpora los campos extraídos al estado, retira los solicitados y procesa los riesgos detectados por el LLM.
    def _extract(self, s):
        data = s["extracted"]
        for key in REQUIRED + ("budget", "product_categories", "intent"):
            if data.get(key) is not None:
                s[key] = data[key]
        for key in data["clear_fields"]:
            s[key] = [] if key == "product_categories" else None
        if data["intent"] == "human_support":
            self._handoff(s, "human_support")
        elif data["risk"] != "none":
            self._handoff(s, data["risk"])
        return s

    # Calcula la lista de datos obligatorios que todavía no están presentes en el estado.
    def _required(self, s):
        s["missing_fields"] = [k for k in REQUIRED if s.get(k) is None or s.get(k) == ""]
        return s

    # Construye una pregunta solo por los datos faltantes y deja la sesión esperando la siguiente respuesta.
    def _ask(self, s):
        names = {"event_type": "tipo de evento", "attendees": "cantidad de asistentes",
                 "event_date": "fecha del evento", "location": "ubicación"}
        s["response"] = "Para continuar, indícame: " + ", ".join(names[k] for k in s["missing_fields"]) + "."
        s["current_stage"] = "awaiting_data"
        return s

    # Valida fecha, asistentes, anticipación y tipo de evento; calcula entrega y recojo o marca una derivación.
    def _business(self, s):
        try:
            event = datetime.fromisoformat(s["event_date"])
            if event.tzinfo is None or s["attendees"] <= 0:
                raise ValueError()
            if (event - self.now).total_seconds() < 72 * 3600:
                self._handoff(s, "lead_time")
            elif s["event_type"] not in self.repo.get_event_types():
                self._handoff(s, "unsupported_event")
            else:
                s["delivery_date"], s["pickup_date"] = tools.schedule(self.repo, s["event_date"])
                if datetime.fromisoformat(s["delivery_date"]).date() < self.now.date():
                    self._handoff(s, "lead_time")
        except (ValueError, TypeError):
            self._handoff(s, "ambiguity")
        return s

    # Busca opciones activas y compatibles con evento, capacidad y categoría; deriva si no encuentra ninguna.
    def _catalog(self, s):
        s["options"] = self._call(s, "search_catalog", lambda: tools.search_catalog(self.repo, s))
        if not s["options"]:
            self._handoff(s, "no_catalog_option")
        return s

    # Descarta las opciones sin cobertura en la ubicación y registra si quedan alternativas válidas.
    def _coverage(self, s):
        s["options"] = self._call(s, "check_coverage", lambda: tools.check_coverage(self.repo, s["options"], s["location"]))
        s["validated_coverage"] = bool(s["options"])
        if not s["options"]:
            self._handoff(s, "no_coverage")
        return s

    # Filtra las opciones por stock durante todo el intervalo de ocupación; deriva si ninguna está disponible.
    def _availability(self, s):
        s["options"] = self._call(s, "check_availability", lambda: tools.check_availability(
            self.repo, s["options"], s["event_date"], s["delivery_date"], s["pickup_date"]))
        s["validated_availability"] = bool(s["options"])
        if not s["options"]:
            self._handoff(s, "no_availability")
        return s

    # Ordena las opciones que cumplen el presupuesto y selecciona la primera según las prioridades determinísticas.
    def _rank(self, s):
        s["options"], s["preferences_used"] = self._call(s, "rank_options", lambda: tools.rank_options(self.repo, s["options"], s))
        if not s["options"]:
            self._handoff(s, "budget")
        else:
            s["recommended_option"] = s["options"][0]
        return s

    # Genera importes mediante la tool solo para cotización o modificación; una recomendación no emite cotización.
    def _quote(self, s):
        if s["intent"] in ("quotation", "modify_request"):
            s["quote"] = self._call(s, "get_quote", lambda: tools.get_quote(self.repo, s["recommended_option"], s, self.now))
        return s

    # Revisa la opción seleccionada y recalcula la cotización para detectar diferencias antes de presentarla.
    def _validate(self, s):
        p = s["recommended_option"]
        valid = p and p["active"] and p["capacity"] >= s["attendees"] and s["validated_coverage"] and s["validated_availability"]
        if s["quote"]:
            valid = valid and s["quote"] == tools.get_quote(self.repo, p, s, self.now)
        if not valid:
            self._handoff(s, "invalid_quote")
        return s

    # Presenta la recomendación y los importes con una plantilla controlada, incluyendo condiciones y apertura.
    def _compose(self, s):
        p, q = s["recommended_option"], s["quote"]
        text = f"Recomiendo {p['name']} para {s['attendees']} asistentes; capacidad de {p['capacity']}."
        if q:
            text += (f"\nPrecio unitario: {q['currency']} {q['unit_price']}; cantidad: {q['quantity']}."
                     f"\nSubtotal: {q['currency']} {q['subtotal']}; impuestos: {q['currency']} {q['tax']}; total: {q['currency']} {q['total']}."
                     f"\nEntrega: {q['delivery_date']}; recojo: {q['pickup_date']}; vigencia: {q['valid_until']}.")
        text += "\n" + tools.DISCLAIMER
        # Salida del LLM limitada por esquema a aperturas aprobadas: no puede alterar hechos.
        try:
            opening = self.interpreter.opening(text)
            if opening not in OPENINGS:
                opening = OPENINGS[1]
        except Exception:
            opening = OPENINGS[1]
        s.update(response=opening + "\n" + text, current_stage="quoted" if q else "recommended")
        return s

    # Prepara el resumen de derivación y una respuesta explicativa; el contacto con el asesor sigue pendiente.
    def _human(self, s):
        s["tools_called"].append("human_handoff")
        s["handoff"] = tools.human_handoff(s)
        reasons = {"human_support": "solicitaste un asesor", "discount": "los descuentos requieren revisión humana",
                   "lead_time": "se requieren al menos 72 horas de anticipación", "no_coverage": "no hay cobertura registrada",
                   "no_availability": "no hay disponibilidad confirmada para todo el período",
                   "no_catalog_option": "no hay productos activos compatibles con la capacidad solicitada",
                   "budget": "no hay opciones dentro del presupuesto", "privacy": "la solicitud afecta las reglas de seguridad o privacidad"}
        s["response"] = "Se requiere atención humana: " + reasons.get(s["handoff_reason"], "el caso requiere revisión") + ". No se generó una cotización. Resumen preparado para un asesor; contacto pendiente, no enviado automáticamente."
        s["current_stage"] = "handoff"
        return s

    # Responde consultas informativas generales sin exigir los datos necesarios para cotizar.
    def _information(self, s):
        s.update(response="Puedo recomendar opciones y preparar cotizaciones mock. Se requieren tipo de evento, asistentes, fecha y ubicación; la anticipación mínima es de 72 horas.", current_stage="information")
        return s

    # Define los nodos y rutas del workflow y compila el grafo ejecutable de un único agente.
    def _build(self):
        # AgentState define los datos que circulan entre los nodos; cada nodo actualiza ese estado.
        g = StateGraph(AgentState)
        nodes = {"understand_request": self._understand, "extract_and_update_state": self._extract,
                 "check_required_data": self._required, "ask_missing_data": self._ask,
                 "validate_business_rules": self._business, "find_catalog_options": self._catalog,
                 "check_coverage": self._coverage, "check_availability": self._availability,
                 "rank_options": self._rank, "generate_quote": self._quote, "validate_quote": self._validate,
                 "compose_response": self._compose, "human_handoff": self._human, "information_response": self._information}
        # Crea una envoltura para que los errores inesperados de un nodo marquen una derivación.
        def safe(fn):
            # Ejecuta el nodo recibido; si falla, actualiza el estado para gestionar el caso con atención humana.
            def node(s):
                try:
                    return fn(s)
                except Exception:
                    self._handoff(s, "persistent_failure")
                    return self._human(s) if fn == self._compose else s
            return node
        for name, fn in nodes.items():
            g.add_node(name, safe(fn))
        g.add_edge(START, "understand_request")
        flow = ["understand_request", "extract_and_update_state", "check_required_data", "validate_business_rules",
                "find_catalog_options", "check_coverage", "check_availability", "rank_options", "generate_quote", "validate_quote", "compose_response"]
        # Conecta cada paso con el siguiente, permitiendo interrumpir el flujo para pedir datos o derivar.
        for current, following in zip(flow, flow[1:]):
            # Decide si avanzar, pedir datos, informar o derivar según el estado después del nodo actual.
            def route(s, nxt=following, current=current):
                if s.get("needs_human"):
                    return "human_handoff"
                if current == "check_required_data":
                    if s["intent"] == "information":
                        return "information_response"
                    if s["missing_fields"]:
                        return "ask_missing_data"
                return nxt
            g.add_conditional_edges(current, route, list(nodes))
        for name in ("compose_response", "ask_missing_data", "human_handoff", "information_response"):
            g.add_edge(name, END)
        return g.compile()

    # Procesa un mensaje conservando los datos de la sesión, reinicia resultados derivados y devuelve el nuevo estado.
    def respond(self, message, previous=None, *, trusted_customer_id=None):
        self.now = self._fixed_now or datetime.now(ZoneInfo("America/Lima"))
        s = deepcopy(previous or {})
        # Invalida resultados anteriores en CADA turno, incluidos cambios y derivaciones.
        s.update(message=redact(message), quote=None, recommended_option=None, needs_human=False,
                 handoff_reason=None, handoff=None, validated_coverage=False, validated_availability=False,
                 options=[], tools_called=[], attempts={}, preferences_used=[], missing_fields=[],
                 response="", extracted={}, current_stage="understanding", trusted_customer_id=trusted_customer_id,
                 customer_email=None, customer_phone=None)
        s.setdefault("messages", [])
        for key in REQUIRED + ("budget",):
            s.setdefault(key, None)
        s.setdefault("product_categories", [])
        s["messages"].append({"role": "user", "content": s["message"]})
        # Esta llamada ejecuta los nodos del agente; con tracing habilitado se registra su recorrido.
        result = self.graph.invoke(s)
        result["messages"].append({"role": "assistant", "content": result["response"]})
        return result
