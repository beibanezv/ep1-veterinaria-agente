"""Tests de Fase 3: tools de dosis/interacciones y loop razonamiento-accion."""
import json
from pathlib import Path

from agent.llm_client import ClienteFalso
from agent.reasoning_loop import AgenteVeterinario
from agent.trace import Trazador
from agent.retriever import Recuperador
from tools.dose_calculator import calcular_dosis, cargar_entrada
from tools.interaction_checker import verificar_interaccion


def _agente(tmp_path: Path) -> AgenteVeterinario:
    trazador = Trazador(Path(tmp_path) / "trace_fase3.jsonl")
    return AgenteVeterinario(llm=ClienteFalso(), trazador=trazador)


def test_calcula_dosis_desde_entrada(tmp_path):
    entrada = cargar_entrada("DOS-001")
    assert entrada is not None and entrada["especie"] == "perro"
    dosis = calcular_dosis(entrada, peso_kg=24.5)
    assert dosis.disponible
    assert dosis.dosis_min_mg == 49.0
    assert dosis.dosis_max_mg == 107.8


def test_loop_responde_dosis_con_fuentes(tmp_path):
    r = _agente(tmp_path).planificar(
        "perro con dolor articular", especie="perro", peso_kg=24.5,
        farmaco="carprofeno", paciente="FIC-001",
    )
    assert r.ficha_id == "FIC-001"
    assert r.entrada_id == "DOS-001"
    assert r.dosis is not None and r.dosis.disponible
    assert r.dosis.dosis_min_mg == 49.0
    assert r.dosis.dosis_max_mg == 107.8
    assert not r.sin_informacion
    assert r.alerta_severa, "FIC-001 toma meloxicam: carprofeno debe alertar (severa)"
    assert r.fuentes_citadas, "debe citar fuentes"


def test_gato_con_carprofeno_no_tiene_dato(tmp_path):
    r = _agente(tmp_path).planificar(
        "gata con dolor, proponen carprofeno", especie="gato", peso_kg=5.8,
        farmaco="carprofeno", paciente="FIC-005",
    )
    assert r.sin_informacion
    assert r.entrada_id is None
    assert r.dosis is None or not r.dosis.disponible


def test_alerta_severa_por_interaccion(tmp_path):
    r = _agente(tmp_path).planificar(
        "perro con artrosis que ya toma meloxicam", especie="perro",
        peso_kg=24.5, farmaco="carprofeno", paciente="FIC-001",
    )
    assert r.alerta_severa
    assert r.alertas


def test_sin_interaccion_conocida_no_alerta(tmp_path):
    r = _agente(tmp_path).planificar(
        "perro con hipotiroidismo", especie="perro", peso_kg=12.3,
        farmaco="carprofeno", paciente="FIC-011",
    )
    assert not r.alerta_severa


def test_checker_interaccion_ambos_sentidos():
    severa = verificar_interaccion("carprofeno", ["meloxicam"])
    inversa = verificar_interaccion("meloxicam", ["carprofeno"])
    assert severa and severa[0].hay and severa[0].severidad == "severa"
    assert inversa and inversa[0].hay


def test_trace_registra_pasos(tmp_path):
    archivo = Path(tmp_path) / "trace_fase3.jsonl"
    _agente(tmp_path).planificar(
        "perro con dolor articular", especie="perro", peso_kg=24.5,
        farmaco="carprofeno", paciente="FIC-001",
    )
    pasos = [json.loads(line)["tipo"] for line in archivo.read_text(encoding="utf-8").splitlines()]
    assert "busqueda_ficha" in pasos
    assert "busqueda_dosificacion" in pasos
    assert "calculo_dosis" in pasos
    assert "verificacion_interacciones" in pasos
    assert "respuesta_final" in pasos
