"""Tests Fase 4: guardrails en codigo post-LLM."""
from pathlib import Path
import json

from agent.llm_client import ClienteFalso
from agent.reasoning_loop import AgenteVeterinario
from agent.trace import Trazador


def _agente(tmp_path: Path) -> AgenteVeterinario:
    return AgenteVeterinario(
        llm=ClienteFalso(),
        trazador=Trazador(Path(tmp_path) / "trace_fase4.jsonl"),
    )


def dosis_esta_presenta(r) -> bool:
    return r.dosis is not None and r.dosis.disponible and r.dosis.dosis_max_mg > 0


def test_guardrail_negativa_sin_informacion(tmp_path):
    r = _agente(tmp_path).planificar(
        "gato con dolor postoperatorio", especie="gato", peso_kg=5.8,
        farmaco="carprofeno", paciente="FIC-005",
    )
    assert r.sin_informacion
    assert "negativa_sin_informacion" in r.guardrails
    assert "No tengo informacion suficiente" in r.texto
    assert "mg" not in r.texto.lower()


def test_guardrail_alerta_severa_anteponida(tmp_path):
    r = _agente(tmp_path).planificar(
        "perro con artrosis que ya toma meloxicam", especie="perro", peso_kg=24.5,
        farmaco="carprofeno", paciente="FIC-001",
    )
    assert r.alerta_severa
    assert "alerta_severa_anteponida" in r.guardrails
    assert r.texto.startswith("ALERTA DE INTERACCION SEVERA")
    assert "carprofeno + meloxicam" in r.texto
    assert dosis_esta_presenta(r)


def test_guardrail_no_interviene_caso_normal(tmp_path):
    r = _agente(tmp_path).planificar(
        "perro con dolor articular", especie="perro", peso_kg=12.3,
        farmaco="carprofeno", paciente="FIC-011",
    )
    assert not r.sin_informacion
    assert not r.alerta_severa
    assert r.guardrails == []
    assert not r.texto.startswith("ALERTA")
    assert r.dosis is not None and r.dosis.disponible
    assert r.dosis.dosis_min_mg > 0


def test_guardrails_registrados_en_trace(tmp_path):
    _agente(tmp_path).planificar(
        "perro con artrosis que ya toma meloxicam", especie="perro", peso_kg=24.5,
        farmaco="carprofeno", paciente="FIC-001",
    )
    archivo = Path(tmp_path) / "trace_fase4.jsonl"
    eventos = [json.loads(l) for l in archivo.read_text(encoding="utf-8").splitlines() if l.strip()]
    guardrail = [e for e in eventos if e["tipo"] == "guardrails_aplicados"]
    assert guardrail
    assert "alerta_severa_anteponida" in guardrail[0]["reglas"]
