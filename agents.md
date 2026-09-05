# agents.md — Memoria de decisiones y avance del semestre

**Proyecto:** ep1-veterinaria-agente
**Curso:** ISY0101 Ingeniería de Soluciones con IA — Evaluación Parcial 1 (30%)
**GitHub:** https://github.com/beibanezv
**Última actualización:** 2026-09-04

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
│   ├── llm_client.py             interfaz intercambiable, Groq default
│   ├── reasoning_loop.py         loop razonamiento-acción + guardrails post-LLM
│   ├── prompts.py
│   └── trace.py                  log JSONL de trazabilidad
├── tools/
│   ├── dose_calculator.py        mg/kg × peso → rango, validado vs fuente
│   └── interaction_checker.py    cruza medicamento propuesto vs actuales
├── main.py                       CLI: caso → recomendación con cita o alerta
├── notebooks/demo.ipynb          4 casos de demostración con ClienteFalso
├── tests/
│   ├── eval_dataset.json         14 casos con resultado esperado
│   └── eval_agent.py             corre evals y reporta % de aciertos
└── docs/                         informe y diagramas (Fase 6)
```

## 5. Plan de fases

- [x] Fase 0 — Scaffold: uv, pyproject, .env.example, verify_groq.py, git init
- [x] Fase 1 — Datos simulados (12 fichas + 18 entradas dosificación + 8 interacciones) + ingesta + índice Chroma (30 docs, verificación 6/6)
- [x] Fase 2 — llm_client.py + prompts veterinarios + respuesta base con citas [F#]/[T#]
- [x] Fase 3 — Tools dosis/interacciones + loop razonamiento-acción + trace.jsonl (tests 7/7)
- [x] Fase 4 — Guardrails en código: negativa sin fuente reemplaza texto del LLM; alerta severa anteponida (tests 11/11)
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
