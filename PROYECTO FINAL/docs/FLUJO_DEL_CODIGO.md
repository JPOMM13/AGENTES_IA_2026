# Flujo del codigo del cotizador

Este proyecto usa un workflow agentico secuencial con LangGraph. No es un
multiagente puro: el grafo ordena nodos fijos y dentro de algunos nodos se usa
`create_agent` para interpretar lenguaje natural o decidir una accion.

## Entrada desde frontend

1. `frontend/main.py` muestra la interfaz Streamlit.
2. `frontend/cliente_api.py` envia HTTP al backend:
   - `POST /api/sesiones` crea o recupera sesion.
   - `POST /api/chat` envia el mensaje del usuario.
   - `GET /api/sesiones/{id_sesion}` consulta estado.
   - `POST /api/sesiones/{id_sesion}/reiniciar` reinicia conversacion.

## Entrada desde backend

1. `app/api.py` recibe `POST /api/chat` en `conversar_con_agente`.
2. El endpoint recupera el `EstadoCotizacion` desde `RepositorioSesionActiva`.
3. Luego llama a `manejar_mensaje` en `app/flujo.py`.
4. `manejar_mensaje` llama a `ejecutar_grafo_cotizador` en `app/grafo_cotizador.py`.

## Ruta LangGraph

El grafo se define en `app/grafo_cotizador.py`, dentro de
`obtener_grafo_cotizador`.

Ruta productiva:

```text
validar_entrada
-> extraer_y_enrutar_intencion
-> gestionar_memoria_persistente
-> decidir_accion_agentica
-> ejecutar_tools_negocio
-> evaluar_salida_guardrail
```

`validar_entrada` puede cortar el flujo si el mensaje no pasa el guardrail de
entrada. `gestionar_memoria_persistente` tambien puede responder antes del
decisor si el turno se resuelve recuperando memoria o una eleccion pendiente.

## System prompt y create_agent

Los prompts del sistema estan centralizados en `app/prompts_agenticos.py`.

- `PROMPT_SISTEMA_EXTRACTOR`: reglas para extraer datos explicitos del usuario.
- `PROMPT_SISTEMA_DECISOR`: reglas para elegir la siguiente accion del workflow.

El extractor se crea en `app/extractor_agentico.py`, metodo
`crear_agente_extractor`. Ahi se conecta:

```text
modelo configurado -> PROMPT_SISTEMA_EXTRACTOR -> registrar_campos_extraidos -> middleware guardrail
```

El decisor se crea en `app/decisor_agentico.py`, metodo
`crear_agente_decisor`. Ahi se conecta:

```text
modelo configurado -> PROMPT_SISTEMA_DECISOR -> elegir_accion_workflow -> middleware guardrail
```

## Guardrails y validaciones

- Entrada: `app/guardrails/entrada.py`, llamado desde el nodo `validar_entrada`.
- Decision: `app/guardrails/decision.py`, llamado desde
  `decidir_accion_agentica_turno` en `app/flujo.py`.
- Salida: `app/guardrails/salida.py`, llamado desde el nodo
  `evaluar_salida_guardrail`.
- Middleware LangChain: `app/guardrails/capa_intermedia.py`, usado al invocar los
  agentes con `create_agent`.

## Tools y negocio

Las tools de negocio se ejecutan desde `ejecutar_decision_negocio` en
`app/flujo.py`. Ese metodo decide si corresponde pedir campos, revisar pedido,
consultar politica por RAG, validar cobertura, validar calendario, validar
catalogo/stock, generar cotizacion o derivar.

## Memoria

- Memoria de sesion activa: se accede mediante `RepositorioSesionActiva`.
- Memoria persistente de cotizacion: se accede mediante
  `RepositorioMemoriaCotizacion`.
- La recuperacion de conversaciones previas ocurre antes del decisor, en el nodo
  `gestionar_memoria_persistente`.

## Respuesta final

1. `ejecutar_tools_negocio` produce `respuesta_base`.
2. `evaluar_salida_guardrail` valida esa respuesta.
3. `finalizar_turno_cotizador` en `app/flujo.py` persiste memoria, agrega
   contexto visible y devuelve la respuesta final.
4. `app/api.py` empaqueta el estado con `construir_respuesta_sesion`.
5. `frontend/main.py` renderiza mensajes, cotizacion e imagen si existen.
