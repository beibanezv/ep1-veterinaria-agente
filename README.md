# EP1 — Agente de Dosis Seguras para Clínica Veterinaria

**ISY0101 · Ingeniería de Soluciones con IA · Evaluación Parcial 1 (30%)**

Agente LLM + RAG que asiste a una clínica veterinaria pequeña (sin
especialista de respaldo): recupera la ficha del paciente y la guía de
dosificación, calcula el rango seguro según peso, verifica interacciones con
los medicamentos actuales y responde citando la fuente exacta. **Nunca
sugiere una dosis sin fuente**: si el dato no existe para esa especie/fármaco,
responde "no tengo información suficiente"; si hay interacción, emite alerta
explícita.

> **Estado:** Fases 0–6 completas. Suite de tests 13/13, evals 14/14 casos
> (100%, meta ≥85%). Decisiones técnicas y bitácora en
> [`agents.md`](agents.md).

## Pipeline (loop razonamiento-acción)

```mermaid
flowchart TD
    A[Consulta clínica<br/>especie + peso + fármaco + paciente] --> V[Validación pre-loop<br/>especie/peso/ficha/fármaco]
    V --> B[Recuperador RAG<br/>ficha del paciente]
    B --> C[Recuperador RAG<br/>entrada de dosificación especie/fármaco]
    C --> D{¿Entrada exacta<br/>en la guía?}
    D -- "no" --> G[Guardrail: negativa<br/>sin información suficiente]
    D -- sí --> E[Tool: dose_calculator<br/>mg/kg × peso → rango]
    E --> F[Tool: interaction_checker<br/>fármaco propuesto vs actuales]
    F --> H{¿Interacción?}
    H -- sí --> I[Alerta explícita<br/>severa/moderada/leve]
    H -- no --> J[LLM con contexto<br/>+ citas F# / T#]
    I --> J
    J --> K[Guardrails post-LLM<br/>en código]
    G --> K
    K --> L[Respuesta final<br/>+ trace.jsonl]
```

Cada paso queda registrado en `logs/trace.jsonl` (JSONL con paso, tipo de
evento y hora UTC): trazabilidad completa de qué fuente se usó y qué
herramienta se ejecutó.

## Datos

| Colección | Origen | Contenido |
|---|---|---|
| Interna (RAG 1) | `data/internal/fichas/` | 12 fichas clínicas FIC-001..012 (5 perro, 4 gato, 3 conejo): peso, edad, medicamentos actuales, alergias |
| Externa (RAG 2) | `data/external/dosificacion/` | 18 entradas DOS-001..018 (7 perro, 6 gato, 5 conejo): mg/kg min-max, frecuencia, vía, fuente bibliográfica |
| Tools | `data/external/interacciones.json` | 8 pares de fármacos con severidad (severa/moderada/leve) y nota clínica |

Incluye **huecos deliberados** (p. ej. carprofeno-gato, amoxicilina-conejo) para
probar el guardrail de negativa: el agente debe decir "no tengo información
suficiente" en vez de inventar una cifra.

## Cómo correr

```bash
uv sync
cp .env.example .env   # pegar GROQ_API_KEY (gratis) de https://console.groq.com

# 1. Ingesta a ChromaDB (30 documentos, verificación semántica incluida)
uv run python -m ingestion.ingest

# 2. CLI con el LLM real (LangChain/ChatGroq por defecto, con tracing LangSmith)
uv run python main.py "perro con dolor articular que ya toma meloxicam" \
    --especie perro --peso 24.5 --farmaco carprofeno --paciente FIC-001 --pasos
# variante SDK crudo: agregar --groq-directo

# 3. CLI determinista (ClienteFalso, sin API key) para demo/CI
uv run python main.py "gata que ya toma carprofeno" \
    --especie gato --peso 5.8 --farmaco carprofeno --paciente FIC-005 --falso

# 4. Tests y evals
uv run python -m pytest -q
uv run python -m tests.eval_agent
```

Notebook de demostración con 4 casos (alerta severa, dosis normal, negativa
sin fuente, alerta moderada): `notebooks/demo.ipynb`.

Interfaz web básica (Streamlit, solo para demo/presentación):

```bash
uv run streamlit run app.py
# Marca "Modo demo determinista" para no usar API key; incluye los 2 casos
# del guion (alerta severa FIC-001 y negativa gato+carprofeno) como botones.
# El peso máximo se ajusta por especie (perro 200 / gato 50 / conejo 10 kg).
```

## Observabilidad (LangChain / LangSmith, activo)

- `agent/llm_client.py` incluye `ClienteLangChain` (ChatGroq vía
  `langchain-groq`) con el mismo contrato `completar()`; el CLI y la UI
  lo usan por defecto (`--falso` = ClienteFalso, `--groq-directo` = SDK crudo).
- `agent/observabilidad.py` activa LangSmith si `.env` tiene
  `LANGSMITH_API_KEY` (proyecto `ep1-veterinaria`, ver en
  https://smith.langchain.com/); sin key es no-op. Tests/evals llevan
  tracing apagado (conftest + scripts) para no contaminar el proyecto.

## Guardrails de seguridad (Fase 4, en código)

Verificación post-LLM en `agent/reasoning_loop.py`, no solo en el prompt:

1. **Negativa sin fuente:** si no existe entrada exacta especie/fármaco en la
   guía, el texto del LLM se **reemplaza** por una negativa estándar sin
   cifras (`negativa_sin_informacion` en trace).
2. **Alerta severa anteponida:** si hay interacción severa, se antepone un
   encabezado `ALERTA DE INTERACCION SEVERA...` con la nota clínica y la
   advertencia de no administrar sin supervisión (`alerta_severa_anteponida`).
3. **Interacciones moderadas/leves antepuestas:** se agrega un aviso
   `INTERACCIONES A VIGILAR...` con severidad y nota
   (`interacciones_no_severas_antepuestas`), incluso cuando la respuesta se
   reemplaza por la negativa, para no perder la advertencia.

## Validación pre-loop (Fase 4b, bloqueante)

Validación de entrada en `agent/validacion.py` que se ejecuta **antes** de
cualquier RAG o llamada al LLM:

1. **Especies permitidas:** `perro`, `gato`, `conejo`. Cualquier otro valor es
   rechazado de inmediato.
2. **Rangos de peso por especie (kg):**
   - perro: `[0.1, 200.0]`
   - gato: `[0.1, 50.0]`
   - conejo: `[0.1, 10.0]`
   Los pesos fuera del rango son rechazados.
3. **Existencia y coherencia ficha-vs-input:** un ID de ficha `FIC-xxx`
   inexistente se rechaza, y si corresponde a otra especie también (p. ej.
   FIC-001 es perro y no gato); así el agente nunca calcula sin historial.
4. **Fármaco obligatorio:** un farmaco vacío o nulo es rechazado.
5. **Salida:** el agente devuelve un `RespuestaVet` con `sin_informacion=True`,
   `guardrails=["validacion_pre_loop"]` y un mensaje de texto de rechazo sin
   ejecutar RAG ni LLM. Esto evita costos innecesarios y protege contra
   entradas que el agente no podría manejar con seguridad.

La validación registra `entrada_rechazada` en el trace.jsonl para auditoría
y permite diagnóstico inmediato sin lanzar herramientas.

## Evals (Fase 5)

`tests/eval_dataset.json` con 14 casos: cálculo de dosis por especie/peso,
alertas severas (AINE+AINE, AINE+corticosteroide), moderadas y leves,
negativas por dato inexistente y verificación de citas. Corre con
`ClienteFalso` (reproducible, sin cuota de API):

```
Evals: 14/14 casos OK (100%) | meta >= 85%
```

## Limitaciones

- La guía de dosificación es un dataset curado de referencia para el prototipo
  (fuente citada en cada entrada); NO sustituye a Plumb's Veterinary Drug
  Handbook ni a la ficha técnica vigente. La salida es apoyo para un
  veterinario, no una prescripción.
- Cuota Groq (200k tokens/día): usar `GROQ_MODEL_FAST` (20b) en dev y evals.
- La validación pre-loop no reemplaza la supervisión veterinaria; evita que
  el agente procese casos que no tiene datos para responder, pero el
  profesional debe confirmar siempre la dosis.
