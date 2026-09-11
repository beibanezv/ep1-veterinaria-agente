"""D11 (espejo vet): estrictez de contexto clinico.

Evidencia por sondas: ni la distancia de embeddings ni el overlap lexico
separan consultas validas de fuera-de-dominio en este corpus (casos E03, E06,
E12, E14 caen del lado 'lejano'), asi que la puerta es la regla 7 de
SISTEMA_BASE (redirigir sin cifras) mas el guardrail de negativa cuando el
farmaco no tiene guia. Estos tests fijan ese contrato con ClienteFalso.
"""
from pathlib import Path

from agent.llm_client import ClienteFalso
from agent.prompts import SISTEMA_BASE
from agent.reasoning_loop import AgenteVeterinario
from agent.trace import Trazador


class ClienteContador(ClienteFalso):
    def __init__(self):
        super().__init__()
        self.llamadas = 0

    def completar(self, sistema, usuario):
        self.llamadas += 1
        return super().completar(sistema, usuario)


def _agente(tmp_path: Path) -> AgenteVeterinario:
    trazador = Trazador(Path(tmp_path) / "trace_dominio.jsonl")
    return AgenteVeterinario(llm=ClienteFalso(), trazador=trazador)


def test_regla_fuera_de_dominio_existe_en_prompt():
    # La regla 7 ordena redirigir sin cifras ante motivo no clinico.
    assert "MOTIVO DE CONSULTA" in SISTEMA_BASE
    assert "NO entregues cifras de dosis" in SISTEMA_BASE


def test_farmaco_sin_guia_no_entrega_cifras(tmp_path):
    # Consulta clinica valida + farmaco inexistente en la guia -> la puerta no
    # dispara (hay ficha pertinente) y el guardrail niega sin numeros.
    r = _agente(tmp_path).planificar(
        "perro con dolor articular", especie="perro", peso_kg=24.5,
        farmaco="torta de chocolate", paciente="FIC-001",
    )
    assert r.sin_informacion
    assert r.dosis is None or not r.dosis.disponible
    assert "mg" not in r.texto
    assert "negativa_sin_informacion" in r.guardrails


def test_puerta_redirige_sin_llamar_llm(tmp_path):
    # Caso reportado: con farmaco valido igual se redirige (puerta por score).
    llm = ClienteContador()
    trazador = Trazador(Path(tmp_path) / "trace_dominio.jsonl")
    agente = AgenteVeterinario(llm=llm, trazador=trazador)
    r = agente.planificar(
        "que prefieres perritos o gatitos", especie="perro", peso_kg=10.0,
        farmaco="carprofeno", paciente="FIC-001",
    )
    assert r.dosis is None
    assert "mg" not in r.texto
    assert "clinica veterinaria" in r.texto
    assert r.guardrails == ["fuera_de_dominio"]
    assert llm.llamadas == 0


def test_caso_borde_valido_pasa_la_puerta(tmp_path):
    # E08 es el valido mas cercano al umbral (0.65): no debe redirigir.
    r = _agente(tmp_path).planificar(
        "gato con dolor articular", especie="gato", peso_kg=5.8,
        farmaco="carprofeno", paciente="FIC-005",
    )
    assert "fuera_de_dominio" not in r.guardrails
