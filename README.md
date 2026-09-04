# EP1 — Agente de Dosis Seguras para Clínica Veterinaria

**ISY0101 · Ingeniería de Soluciones con IA · Evaluación Parcial 1 (30%)**

Agente LLM + RAG que asiste a una clínica veterinaria pequeña (sin
especialista de respaldo): recupera la ficha del paciente y la guía de
dosificación, calcula el rango seguro según peso, verifica interacciones con
los medicamentos actuales y responde citando la fuente exacta. **Nunca
sugiere una dosis sin fuente**: si el dato no existe para esa especie/fármaco,
responde "no tengo información suficiente"; si está fuera de margen o hay
interacción, emite alerta explícita.

> **Estado:** Fase 0 (scaffold). Decisiones técnicas y avance del semestre en
> [`agents.md`](agents.md).

## Cómo correr

```bash
uv sync
cp .env.example .env   # pegar GROQ_API_KEY (gratis) de https://console.groq.com
uv run python scripts/verify_groq.py
```

Documentación completa (arquitectura, fuentes internas/externas, evaluación,
limitaciones) se completa en la Fase 6 del plan.
