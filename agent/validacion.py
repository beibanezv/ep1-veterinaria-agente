"""
Validación pre-loop bloqueante (Fase 4b).

Rechaza entradas inválidas ANTES del RAG y del LLM:
- Especies permitidas: perro, gato, conejo
- Rangos de peso por especie (kg)
- Existencia y coherencia ficha-vs-input (lee especie real del JSON)
- Fármaco no vacío + consulta no vacía
- Registra entrada_rechazada y devuelve RespuestaVet sin retriever/LLM
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.reasoning_loop import AgenteVeterinario, RespuestaVet

ESPECIES_PERMITIDAS = {"perro", "gato", "conejo"}
RANGOS_PESO = {"perro": (0.1, 200.0), "gato": (0.1, 50.0), "conejo": (0.1, 10.0)}
REGEX_FICHA = re.compile(r"FIC-\d{3}")


@lru_cache(maxsize=32)
def _especie_de_ficha(paciente_id: str) -> str | None:
    """Lee la especie real desde data/internal/fichas/FIC-XXX-*.json (cacheado)."""
    if not REGEX_FICHA.fullmatch(paciente_id or ""):
        return None
    raiz = Path(__file__).resolve().parents[1]
    candidatos = list((raiz / "data" / "internal" / "fichas").glob(f"{paciente_id}-*.json"))
    if not candidatos:
        # Fallback: FIC-XXX.json exacto
        exacto = raiz / "data" / "internal" / "fichas" / f"{paciente_id}.json"
        if exacto.exists():
            candidatos = [exacto]
    if not candidatos:
        return None
    try:
        return str(json.loads(candidatos[0].read_text(encoding="utf-8")).get("especie", "")).lower() or None
    except (OSError, ValueError, AttributeError):
        return None


@dataclass
class ValidacionEntrada:
    """Reglas de negocio que rechazan casos inválidos antes de RAG/LLM."""

    @staticmethod
    def validar(
        agente: AgenteVeterinario,
        consulta: str,
        especie: str,
        peso_kg: float,
        farmaco: str,
        paciente: str = "",
        medicamentos: list[str] | None = None,
    ) -> RespuestaVet | None:
        """Validate entrada y abort early si es inválida.

        Returns a RespuestaVet with rejection trace and no retriever/LLM calls,
        o None si la entrada es válida.
        """
        _ = medicamentos  # reservado para futuras reglas, no interviene hoy
        especie_norm = (especie or "").strip().lower()
        farmaco_norm = (farmaco or "").strip()
        paciente_norm = (paciente or "").strip().upper()
        consulta_ok = bool((consulta or "").strip())

        agente.trazador.registrar(
            "validacion_pre_loop_inicio", especie=especie_norm, peso_kg=peso_kg, farmaco=farmaco_norm
        )

        errores: list[str] = []

        if not consulta_ok:
            errores.append("consulta es obligatoria")

        especie_valida = especie_norm in ESPECIES_PERMITIDAS
        if not especie_valida:
            errores.append(f"especie '{especie}' no permitida. Usar: perro, gato, conejo")

        # Peso: acepta str/num, rechaza NaN/inf/no-numérico y fuera de rango
        if especie_valida:
            try:
                peso_val = float(peso_kg)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                errores.append(f"peso '{peso_kg}' inválido: debe ser un número en kg")
            else:
                if math.isnan(peso_val) or math.isinf(peso_val):
                    errores.append(f"peso '{peso_kg}' inválido: debe ser un número en kg")
                else:
                    min_p, max_p = RANGOS_PESO[especie_norm]
                    if peso_val < min_p or peso_val > max_p:
                        errores.append(
                            f"peso {peso_val} kg fuera de rango [{min_p}-{max_p}] para {especie_norm}"
                        )

        # Fármaco no vacío
        if not farmaco_norm:
            errores.append("farmaco propuesto es obligatorio")

        # Existencia + coherencia ficha-vs-input (solo si especie válida para no encadenar errores)
        if paciente_norm:
            if not REGEX_FICHA.fullmatch(paciente_norm):
                errores.append(f"ficha '{paciente}' con formato inválido. Usar: FIC-XXX (ej: FIC-001)")
            elif especie_valida:
                especie_ficha = _especie_de_ficha(paciente_norm)
                if especie_ficha is None:
                    # Sin este chequeo el agente seguía sin historial y podía
                    # omitir interacciones/alertas del paciente real.
                    errores.append(
                        f"ficha {paciente_norm} no existe en el historial clínico interno"
                    )
                elif especie_ficha != especie_norm:
                    errores.append(
                        f"ficha {paciente_norm} corresponde a {especie_ficha}, no a {especie_norm}"
                    )

        if errores:
            from agent.reasoning_loop import RespuestaVet

            agente.trazador.registrar(
                "entrada_rechazada", errores=errores, razon="validacion_pre_loop"
            )
            texto = "Solicitud rechazada por entrada inválida:\n"
            for e in errores:
                texto += f"• {e}\n"
            texto += "\nCorrige los errores e intenta de nuevo."
            return RespuestaVet(
                texto=texto,
                ficha_id=paciente_norm or None,
                sin_informacion=True,
                alertas=[],
                alerta_severa=False,
                guardrails=["validacion_pre_loop"],
                fuentes_citadas=[],
                archivo_trace=agente.trazador.archivo,
            )

        agente.trazador.registrar("validacion_pre_loop_ok", especie=especie_norm)
        return None
