"""Evals del agente veterinario: corre el dataset y reporta la meta de aciertos.

Uso:  python -m tests.eval_agent
"""
import os
import sys
from dataclasses import dataclass
import json
from pathlib import Path

# Evals deterministas con ClienteFalso: sin tracing LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from agent.reasoning_loop import AgenteVeterinario  # noqa: E402
from agent.llm_client import ClienteFalso  # noqa: E402
from agent.trace import Trazador  # noqa: E402

DATASET = RAIZ / "tests" / "eval_dataset.json"
TRACE_EVALS = RAIZ / "logs" / "trace_evals.jsonl"


@dataclass
class Veredicto:
    id: str
    ok: bool
    fallos: list[str]


def _registrar_fallo(fallos, campo, esperado, obtenido):
    fallos.append(f"{campo}: esperado={esperado!r} obtenido={obtenido!r}")


def _revisar_caso(caso, r):
    fallos = []
    esp = caso.get("esperado", {})
    pares = [
        ("ficha_id", r.ficha_id),
        ("entrada_id", r.entrada_id),
        ("sin_informacion", r.sin_informacion),
        ("alerta_severa", r.alerta_severa),
    ]
    for campo, obtenido in pares:
        if campo in esp and obtenido != esp[campo]:
            _registrar_fallo(fallos, campo, esp[campo], obtenido)
    if "dosis_min_mg" in esp:
        if r.dosis is None:
            _registrar_fallo(fallos, "dosis", "calculada", None)
        else:
            if r.dosis.dosis_min_mg != esp["dosis_min_mg"]:
                _registrar_fallo(fallos, "dosis_min_mg", esp["dosis_min_mg"], r.dosis.dosis_min_mg)
            if "dosis_max_mg" in esp and r.dosis.dosis_max_mg != esp["dosis_max_mg"]:
                _registrar_fallo(fallos, "dosis_max_mg", esp["dosis_max_mg"], r.dosis.dosis_max_mg)
    for sub in esp.get("guardrails_contiene", []):
        if sub not in (r.guardrails or []):
            _registrar_fallo(fallos, "guardrails_contiene", sub, r.guardrails)
    for sub in esp.get("citas_contiene", []):
        if sub not in (r.fuentes_citadas or []):
            _registrar_fallo(fallos, "citas_contiene", sub, r.fuentes_citadas)
    for sub in esp.get("texto_contiene", []):
        if sub not in (r.texto or ""):
            _registrar_fallo(fallos, "texto_contiene", sub, r.texto)
    if "alertas_minimo" in esp and len(r.alertas or []) < esp["alertas_minimo"]:
        _registrar_fallo(fallos, "alertas_minimo", esp["alertas_minimo"], len(r.alertas or []))
    return Veredicto(caso["id"], not fallos, fallos)


def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    meta = dataset.get("meta", 0.85)
    trazador = Trazador(TRACE_EVALS)
    agente = AgenteVeterinario(llm=ClienteFalso(), trazador=trazador)

    aciertos = 0
    veredictos = []
    for caso in dataset["casos"]:
        r = agente.planificar(
            caso["consulta"],
            especie=caso["especie"],
            peso_kg=caso["peso_kg"],
            farmaco=caso["farmaco"],
            paciente=caso.get("paciente", ""),
        )
        v = _revisar_caso(caso, r)
        veredictos.append(v)
        aciertos += 1 if v.ok else 0

    total = len(veredictos)
    tasa = aciertos / total if total else 0.0
    print(f"Evals: {aciertos}/{total} casos OK ({tasa:.0%}) | meta >= {meta:.0%}")
    for v in veredictos:
        marca = "OK  " if v.ok else "FALLA"
        print(f"  [{marca}] {v.id}")
        for f in v.fallos:
            print(f"         {f}")
    if tasa < meta:
        print("Por debajo de la meta.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
