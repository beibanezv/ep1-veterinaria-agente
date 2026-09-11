# Agente de Dosis Seguras — Clínica Veterinaria

**ISY0101 · Ingeniería de Soluciones con IA · Evaluación Parcial 1**

Programa que apoya a una clínica veterinaria pequeña a calcular dosis seguras
y detectar interacciones antes de recetar. Dada una consulta (especie, peso,
fármaco propuesto y paciente), el agente busca la ficha del paciente y la guía
de dosificación, calcula el rango seguro según el peso, revisa interacciones
con los medicamentos actuales y responde citando la fuente exacta.

Regla principal: **si el dato no existe para esa especie y fármaco, dice que
no tiene información suficiente en vez de inventar una cifra**. Si detecta una
interacción, muestra una alerta explícita.

## Cómo funciona

1. Valida la entrada (especie, peso, ficha del paciente, fármaco).
2. Recupera la ficha del paciente y la entrada de dosificación (búsqueda
   semántica sobre base local ChromaDB).
3. Calcula el rango de dosis (mg/kg × peso) y verifica interacciones.
4. Responde con la recomendación, el rango calculado y la cita de la guía.
5. Todo queda registrado en `logs/trace.jsonl` para trazabilidad.

Si la consulta no tiene relación con veterinaria, el programa lo indica y no
entrega dosis.

## Datos

- `data/internal/fichas/`: 12 fichas clínicas (perro, gato, conejo).
- `data/external/dosificacion/`: 18 entradas de guía (mg/kg, frecuencia, vía).
- `data/external/interacciones.json`: 8 pares de fármacos con severidad.

## Cómo ejecutarlo

Requisitos: Python 3.13, [uv](https://docs.astral.sh/uv/) y una API key
gratuita de [Groq](https://console.groq.com).

```bash
uv sync
cp .env.example .env   # pegar la GROQ_API_KEY dentro del .env

# 1. Cargar los datos a la base local
uv run python -m ingestion.ingest

# 2. Consultar (usa el modelo de Groq)
uv run python main.py "perro con dolor articular que ya toma meloxicam" \
    --especie perro --peso 24.5 --farmaco carprofeno --paciente FIC-001

# 3. Modo demo (respuestas fijas, sin gastar API)
uv run python main.py "gato con dolor" \
    --especie gato --peso 5.8 --farmaco carprofeno --paciente FIC-005 --falso

# 4. Correr las pruebas
uv run python -m pytest -q
uv run python -m tests.eval_agent
```

Interfaz web simple para la demostración:

```bash
uv run streamlit run app.py
```

Cuaderno con ejemplos paso a paso: `notebooks/demo.ipynb`.

## Pruebas

- 17 pruebas automatizadas (`tests/`), todas pasando.
- 14 casos de evaluación (`tests/eval_dataset.json`): cálculo de dosis,
  alertas por interacción, casos sin información y citas. Resultado: 14/14.

## Notas

- La guía de dosificación es un conjunto de referencia armado para este
  prototipo; no reemplaza un formulario oficial ni la ficha técnica vigente.
  La salida es apoyo para un veterinario, no una prescripción.
- Informe del proyecto en `docs/EP1_ISY0101_Informe.docx`.
