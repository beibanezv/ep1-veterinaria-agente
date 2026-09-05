"""Verificador de interacciones: par farmaco propuesto vs medicamentos actuales del paciente.

Fuente: data/external/interacciones.json (interna curada, formato {farmaco_a, farmaco_b, severidad, nota}).
El par se busca en ambos sentidos.
"""
import json
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO = RAIZ / "data" / "external" / "interacciones.json"
NOMBRE_FUENTE = "interacciones.json (interno)"


@dataclass
class Interaccion:
    hay: bool
    farmaco_propuesto: str
    farmaco_actual: str
    severidad: str = ""
    nota: str = ""
    fuente: str = NOMBRE_FUENTE


def cargar_interacciones() -> list[dict]:
    with open(ARCHIVO, encoding="utf-8") as f:
        return json.load(f)


def verificar_interaccion(farmaco_propuesto: str, medicamentos_actuales: list[str]) -> list[Interaccion]:
    """Devuelve TODAS las interacciones encontradas (puede haber mas de una)."""
    if not farmaco_propuesto:
        return []
    propuesto = farmaco_propuesto.strip().lower()
    hallazgos = []
    for par in cargar_interacciones():
        a, b = par["farmaco_a"].lower(), par["farmaco_b"].lower()
        for actual in medicamentos_actuales:
            actual_l = actual.strip().lower()
            if (propuesto == a and actual_l == b) or (propuesto == b and actual_l == a):
                hallazgos.append(
                    Interaccion(
                        hay=True,
                        farmaco_propuesto=farmaco_propuesto,
                        farmaco_actual=actual,
                        severidad=par.get("severidad", "?"),
                        nota=par.get("nota", ""),
                    )
                )
    return hallazgos


def describir_interacciones(hallazgos: list[Interaccion], farmaco: str) -> str:
    """Texto para el bloque [T#] del prompt."""
    if not hallazgos:
        return (
            f"Verificacion de interacciones: no se encontraron interacciones registradas "
            f"entre {farmaco} y los medicamentos actuales del paciente."
        )
    partes = [
        f"ALERTA DE INTERACCION ({h.severidad.upper()}): {farmaco} + {h.farmaco_actual}. {h.nota}"
        for h in hallazgos
    ]
    return "\n".join(partes)
