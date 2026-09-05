"""Calculadora de dosis: rango mg/kg x peso a partir de una entrada de dosificacion recuperada.

Regla de seguridad: solo calcula si la entrada tiene ambos limites del rango.
Nunca inventa: si falta dato, devuelve disponible=False.
"""
from dataclasses import dataclass
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_DOSIFICACION = RAIZ / "data" / "external" / "dosificacion"

RAIZ_NOMBRE = "dosis_mg_por_kg (guia interna curada)"


def cargar_entrada(entrada_id: str) -> dict | None:
    """Carga la entrada DOS completa (mg/kg min/max, frecuencia, via) por id."""
    for archivo in DIR_DOSIFICACION.glob("*.json"):
        with open(archivo, encoding="utf-8") as f:
            datos = json.load(f)
        if datos.get("id") == entrada_id:
            return datos
    return None


@dataclass
class DosisCalculada:
    disponible: bool
    farmaco: str
    especie: str
    peso_kg: float
    mg_por_kg_min: float | None = None
    mg_por_kg_max: float | None = None
    dosis_min_mg: float | None = None
    dosis_max_mg: float | None = None
    frecuencia_horas: int | None = None
    via: str | None = None
    nota: str | None = None
    fuente: str = RAIZ_NOMBRE
    motivo: str = ""


def calcular_dosis(entrada: dict, peso_kg: float) -> DosisCalculada:
    """entrada: dict con los campos de la entrada DOS (dosis_mg_por_kg_min/max, frecuencia_horas, via)."""
    farmaco = entrada.get("farmaco", "?")
    especie = entrada.get("especie", "?")
    minimo = entrada.get("dosis_mg_por_kg_min")
    maximo = entrada.get("dosis_mg_por_kg_max")
    if minimo is None or maximo is None or peso_kg <= 0:
        return DosisCalculada(
            disponible=False,
            farmaco=farmaco,
            especie=especie,
            peso_kg=peso_kg,
            motivo="la guia de dosificacion no tiene rango exacto para esta combinacion especie/farmaco",
        )
    return DosisCalculada(
        disponible=True,
        farmaco=farmaco,
        especie=especie,
        peso_kg=peso_kg,
        mg_por_kg_min=float(minimo),
        mg_por_kg_max=float(maximo),
        dosis_min_mg=round(float(minimo) * peso_kg, 1),
        dosis_max_mg=round(float(maximo) * peso_kg, 1),
        frecuencia_horas=entrada.get("frecuencia_horas"),
        via=entrada.get("via"),
        nota=entrada.get("nota"),
    )


def describir_dosis(d: DosisCalculada) -> str:
    """Texto para el bloque [T#] del prompt."""
    if not d.disponible:
        return (
            f"SIN DATO DE DOSIFICACION para {d.farmaco} en {d.especie}: {d.motivo}. "
            "No se entrega ninguna cifra."
        )
    return (
        f"Dosis calculada: {d.farmaco} ({d.especie}, {d.peso_kg} kg) = "
        f"{d.mg_por_kg_min}-{d.mg_por_kg_max} mg/kg x {d.peso_kg} kg = "
        f"{d.dosis_min_mg}-{d.dosis_max_mg} mg por administracion, "
        f"cada {d.frecuencia_horas} h via {d.via}. Nota: {d.nota}"
    )
