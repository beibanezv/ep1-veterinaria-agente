# agents.md — Memoria de decisiones y avance del semestre

**Proyecto:** ep1-veterinaria-agente
**Curso:** ISY0101 Ingeniería de Soluciones con IA — Evaluación Parcial 1 (30%)
**GitHub:** https://github.com/beibanezv
**Última actualización:** 2026-09-10

> Memoria técnica del proyecto. Se actualiza en cada sesión para preservar
> decisiones, tradeoffs y avance entre entregas. Sirve de bitácora para el
> docente (IE7/IE8: justificar decisiones) y para el equipo.

## 1. Contexto del semestre

- EP1 = 1 caso organizacional + informe de 5 páginas APA (IE1–IE9, pauta en
  `../EP1_ISY0101_Estudiante.pdf`). Se desarrolla en parejas, 5 semanas.
- Estrategia del equipo: construir DOS prototipos con arquitectura base común
  (este y `../ep1-ecoturismo-agente`), elegir el mejor como entregable
  único; el otro se descarta o se menciona en la presentación explicando por
  qué se eligió uno sobre el otro.
- Regla del stack: **≥50% con tecnologías vistas en clase es concepto guía,
  no requisito literal.** El profesor alienta la exploración. Toda tecnología
  fuera del curso debe quedar justificada aquí y en el informe.

## 2. Decisiones cerradas

| # | Decisión | Elección | Justificación | Alternativa descartada |
|---|---|---|---|---|
| D1 | Proveedor LLM | Groq: `openai/gpt-oss-120b` (respuesta final) / `gpt-oss-20b` (loops y dev), detrás de `agent/llm_client.py` intercambiable | Único proveedor del curso (CLAUDE.md del repo de materiales); cuota gratis 200k tokens/día | Stub sin proveedor por defecto |
| D2 | Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` local (384d) | Contenido en español; convención del curso; costo 0 y privado | `all-MiniLM-L6-v2` (enfoque inglés, propuesto inicialmente) |
| D3 | Vector store | **ChromaDB** persistente en `chroma_db/` | Filtro nativo por metadata (`especie`, `tipo_fuente`); API simple. Exploración alentada por el profesor | FAISS (lo que enseña RA1/IL1.3). Tradeoff para el informe: curso usa FAISS por velocidad en índices pequeños; Chroma gana en filtrado por metadata |
| D4 | Chunking | Documentos cortos casi sin chunking; `RecursiveCharacterTextSplitter`-style 500/50 para lo largo | Visto en RA1/IL1.3 (`2-text-chunking.py`); fichas y entradas de dosificación son pequeñas y deben recuperarse completas (seguridad) | Chunk grande genérico |
| D5 | Gestor de deps | uv + Python 3.13 | Convención del curso (uv.lock en repo materiales) | pip |
| D6 | Repos | Dos repos independientes | Superficie común ~100 líneas (`llm_client` + logger); entrega académica es por repo | Paquete `shared/`, monorepo |
| D7 | Nombres | `ep1-veterinaria-agente` | Distintivo en GitHub beibanezv (decenas de archivos similares); describe la función (dosis seguras) | `EP1-Veterinaria` |
| D8 | Orquestación | Loop razonamiento-acción propio (sin LangGraph/CrewAI) | Control total del logging de trazabilidad y de los guardrails de seguridad; la pauta pide mostrar el loop explícito | LangGraph (visto en curso; capa extra innecesaria para 1 agente) |
| D9 | Interfaz demo | CLI + notebook + Streamlit `app.py` (solo demo) | La pauta no exige UI; Streamlit es formulario delgado sobre `planificar()` con los 2 casos del guion, modo `--falso` por defecto y peso máximo dinámico por especie | Solo CLI |
| D10 | LangChain / LangSmith | `ClienteLangChain` (ChatGroq vía langchain-groq) por defecto + `agent/observabilidad.py` activo | Mismo contrato `completar()`; `planificar()` con `@traceable`; tracing al proyecto `ep1-veterinaria` si hay `LANGSMITH_API_KEY` en `.env`, si no es no-op; tests/evals con tracing apagado | LangGraph / tracing obligatorio |

Convencion de commits: mensajes simples y en espanol durante todo el semestre.

## 3. Requisitos funcionales (encargo)

Clínica veterinaria pequeña, sin especialista de respaldo, necesita apoyo para
calcular dosis seguras y detectar interacciones antes de recetar. Dado un caso
(especie, peso, medicamento propuesto, medicamentos actuales del paciente):

1. RAG interno: recuperar la ficha del paciente del historial clínico.
2. RAG externo: recuperar la guía de dosificación especie/fármaco de un
   formulario veterinario (dataset curado de referencia, ver limitaciones).
3. Calcular el rango de dosis seguro según peso (mg/kg × peso).
4. Verificar interacción con los medicamentos actuales del paciente.
5. Responder con recomendación, rango calculado y cita de la guía exacta.

**Regla de seguridad no negociable:** el agente NUNCA entrega una dosis si la
fuente RAG no tiene el dato exacto para esa especie/fármaco → responde "no
tengo información suficiente" en vez de estimar. Fuera de margen seguro o
interacción detectada → alerta explícita, nunca un número inventado.
Implementado como guardrail en código (verificación post-LLM), no solo en el
prompt.

## 4. Estructura

```
ep1-veterinaria-agente/
├── data/
│   ├── internal/fichas/          (12 fichas clínicas .json: FIC-001..012)
│   ├── external/dosificacion/    (18 entradas .json: DOS-001..018 con
│   │                              mg/kg, rango seguro, fuente bibliográfica)
│   └── external/interacciones.json (8 pares fármaco con severidad y nota)
├── ingestion/ingest.py           carga → chunk → embed → Chroma (30 docs)
├── agent/
│   ├── llm_client.py             ClienteGroq + ClienteFalso + ClienteLangChain
│   ├── reasoning_loop.py         loop razonamiento-acción + guardrails post-LLM
│   ├── prompts.py
│   ├── retriever.py              lee EMBEDDING_MODEL del .env, error amable si falta colección
│   ├── validacion.py             validación pre-loop (especie/peso/ficha/fármaco)
│   ├── observabilidad.py         init_langsmith opt-in + decorador traceable no-op
│   └── trace.py                  log JSONL de trazabilidad
├── tools/
│   ├── dose_calculator.py        mg/kg × peso → rango, validado vs fuente
│   └── interaction_checker.py    cruza medicamento propuesto vs actuales
├── main.py                       CLI: caso → recomendación con cita o alerta
├── app.py                        Streamlit demo (peso máx dinámico por especie)
├── notebooks/demo.ipynb          4 casos de demostración con ClienteFalso
├── tests/
│   ├── conftest.py               sys.path raíz (pytest desde cualquier cwd)
│   ├── eval_dataset.json         14 casos con resultado esperado
│   └── eval_agent.py             corre evals y reporta % de aciertos
└── docs/                         informe y diagramas (Fase 6)
```

## 5. Plan de fases

- [x] Fase 0 — Scaffold: uv, pyproject, .env.example, verify_groq.py, git init
- [x] Fase 1 — Datos simulados (12 fichas + 18 entradas dosificación + 8 interacciones) + ingesta + índice Chroma (30 docs, verificación 6/6)
- [x] Fase 2 — llm_client.py + prompts veterinarios + respuesta base con citas [F#]/[T#]
- [x] Fase 3 — Tools dosis/interacciones + loop razonamiento-acción + trace.jsonl (tests 7/7)
- [x] Fase 4 — Guardrails en código: negativa sin fuente reemplaza texto del LLM; alerta severa anteponida (tests de guardrails 4/4)
- [x] Fase 4b — Validación pre-loop bloqueante (especie/peso/ficha/fármaco) + interacciones moderadas/leves antepuestas al texto final (suite total 13/13)
- [x] Fase 5 — Evals: 14 casos (4 alertas, 4 sin información suficiente), 14/14 = 100% ≥ meta 85%
- [x] Fase 6 — README completo + diagrama Mermaid + CLI + notebooks/demo.ipynb

## 6. Limitaciones conocidas

- La base de dosificación es un dataset de referencia armado para el prototipo
  a partir de formularios veterinarios estándar conocidos; NO es una fuente en
  vivo ni sustituye a Plumb's Veterinary Drug Handbook. Documentar en
  README/informe.
- Cuota Groq (200k tokens/día): usar `GROQ_MODEL_FAST` (20b) en dev y evals.

## 7. Historial de decisiones

- **2026-09-03** — Plan aprobado por el equipo (estructura, fases, stack).
  ChromaDB elegido sobre FAISS (D3) tras relajar la regla del 50% a concepto
  guía. Guardrail de seguridad definido como código, no solo prompt. Scaffold
  completado (Fase 0).
- **2026-09-04** — Fases 1–6 completadas en una sesión. Datos con huecos
  deliberados (carprofeno-gato, amoxicilina-conejo) para probar el guardrail
  de negativa. Guardrails implementados post-LLM en código (Fase 4): la
  negativa REEMPLAZA la salida del LLM (cero riesgo de cifra inventada) y la
  alerta severa se antepone al texto final. Metadata de Chroma guarda
  medicamentos como string CSV (Chroma no acepta listas). Evals 14/14 (100%)
  con ClienteFalso para reproducibilidad sin cuota. Decisiones del prototipo
  gemelo (`ep1-ecoturismo-agente`) compartidas D1–D8.

- **2026-09-04** — Informe de 5 páginas APA entregado (`docs/EP1_ISY0101_Informe.docx`,
  también en el repo ecoturismo y en la raíz del workspace; portada con
  placeholders `[Integrante 1/2]` y `[Nombre del docente]` pendientes).
- **2026-09-05 (2)** — UI básica Streamlit `app.py` solo para demo/presentación
  (excepción a D9: CLI+notebook siguen siendo la entrega; la UI es un formulario
  sobre `AgenteVeterinario.planificar()` con los 2 casos del guion precargados,
  modo `--falso` por defecto y trazabilidad visible). Verificado: caso1 severa
  49.0-107.8 mg, caso2 negativa sin información.
- **2026-09-05** — Guion de demo para la presentación (probado en desarrollo).
  Todo con `--falso` (ClienteFalso determinista, sin cuota ni API key):
  1. `& ".venv\Scripts\python.exe" main.py "perro con dolor articular" --especie perro --peso 24.5 --farmaco carprofeno --paciente FIC-001 --pasos --falso` → ALERTA DE INTERACCION SEVERA (carprofeno+meloxicam) + dosis 49.0-107.8 mg.
  2. `& ".venv\Scripts\python.exe" main.py "gato con dolor" --especie gato --peso 5.8 --farmaco carprofeno --paciente FIC-005 --pasos --falso` → negativa "No tengo informacion suficiente" (guardrail; carprofeno-gato no existe en la guía).
  3. `& ".venv\Scripts\python.exe" -m pytest -q` → 11/11 y `& ".venv\Scripts\python.exe" -m tests.eval_agent` → 14/14 (100%) como evidencia cuantitativa.
  `--pasos` muestra el trace de la corrida (trazabilidad en vivo). Los casos del
  prototipo ecoturismo están en el agents.md del repo gemelo.
- **2026-09-10** — Corrección pre-entrega: `retriever.py` lee
  `EMBEDDING_MODEL` del `.env` (antes hardcodeado) con error amable que pide
  re-correr ingesta; `tests/conftest.py` agregado (pytest desde cualquier
  cwd); `app.py` con peso máximo dinámico por especie y dropdown solo con
  fármacos con guía DOS; `agent/observabilidad.py` (LangSmith opt-in, no-op
  sin key) + `ClienteLangChain` alternativo en `llm_client.py` (D10).
  Re-verificado: pytest 11/11, evals 14/14.
- **2026-09-10 (2)** — Revisión externa + fixes: `_buscar_dosificacion`
  filtra por `farmaco` en metadata (antes post-filtraba el top-4 y podía
  devolver una negativa falsa); las interacciones moderadas/leves ahora se
  anteponen al texto final incluso en la negativa (antes se perdían al
  reemplazar la salida del LLM); la validación pre-loop rechaza fichas
  `FIC-xxx` inexistentes (antes pasaban y el agente calculaba sin historial).
  Tests nuevos: 13/13. Evals 14/14.
- **2026-09-11** — Cableado LangSmith: `ClienteLangChain` por defecto en
  `main.py`/`app.py` (`--falso` y `--groq-directo` como escapes),
  `@traceable("planificar")` en el loop, `init_langsmith()` al inicio;
  tracing apagado en tests/evals (conftest + scripts). Primera corrida real
  trazada al proyecto `ep1-veterinaria`. Re-verificado: pytest 13/13,
  evals 14/14.

- **2026-09-11 (2)** — Estrictez de contexto (D11 espejo): sondas probaron que ni distancia ni overlap lexico separan consultas validas de ajenas (E03/E06/E12/E14 caen del lado lejano); puerta por score de ficha > 0,68 (14 validos <= 0,65; perritos/torta/poema >= 0,71) + regla 7 del prompt reforzada en la plantilla. main.py con stdout UTF-8 (Windows). Tests nuevos (test_dominio.py): 17/17. Evals 14/14.
