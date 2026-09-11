"""Loop razonamiento-accion del agente veterinario (Fase 3).

Flujo por caso clinico:
1. Validación pre-loop bloqueante (especie, peso, fármaco, coherencia ficha-vs-input).
2. Recuperar la ficha del paciente (RAG interno).
3. Recuperar la entrada de dosificacion especie/farmaco (RAG externo curado).
4. Calcular el rango mg/kg x peso (tool).
5. Verificar interacciones farmaco propuesto vs medicamentos actuales (tool).
6. LLM redacta la recomendacion citando [F#] y [T#].
7. Guardrails en codigo post-LLM (Fase 4): negativa sin fuente y alerta severa.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from agent.llm_client import ClienteLLM
from agent.observabilidad import traceable
from agent.prompts import SISTEMA_BASE, armar_usuario
from agent.retriever import Fragmento, Recuperador
from agent.trace import Trazador
from agent.validacion import ValidacionEntrada
from tools.dose_calculator import (
    DosisCalculada,
    calcular_dosis,
    cargar_entrada,
    describir_dosis,
)
from tools.interaction_checker import (
    NOMBRE_FUENTE as NOMBRE_FUENTE_CHECKER,
    Interaccion,
    describir_interacciones,
    verificar_interaccion,
)

RAIZ = Path(__file__).resolve().parents[1]
REGEX_FUENTES = re.compile(r"\[(?:F|T)\d+\]")

TEXTO_SIN_INFORMACION = (
    "No tengo informacion suficiente en la guia de dosificacion para esta "
    "combinacion de especie y farmaco, por lo que no se entrega ninguna cifra "
    "de dosis. Consulte la guia oficial vigente o a un profesional veterinario."
)


def _aplicar_guardrails(
    texto: str,
    sin_informacion: bool,
    alerta_severa: bool,
    interacciones: list[Interaccion],
    farmaco: str,
) -> tuple[str, list[str]]:
    """Guardrails en codigo post-LLM (Fase 4): no se confia solo en el prompt.

    - interacciones severas -> encabezado de alerta antepuesto.
    - interacciones moderadas/leves -> aviso antepuesto (tambien cuando hay
      negativa, para no perder la advertencia al reemplazar el texto del LLM).
    - sin_informacion -> reemplaza el texto por una negativa sin cifras.
    """
    aplicados: list[str] = []
    severas = [i for i in interacciones if i.severidad == "severa"]
    no_severas = [i for i in interacciones if i.severidad != "severa"]
    bloques: list[str] = []
    if alerta_severa and severas:
        notas = " ".join(
            f"{i.farmaco_propuesto} + {i.farmaco_actual}: {i.nota}" for i in severas
        )
        bloques.append(
            f"ALERTA DE INTERACCION SEVERA entre {farmaco} y los medicamentos "
            f"actuales del paciente. {notas} No administrar sin supervision "
            "veterinaria directa."
        )
        aplicados.append("alerta_severa_anteponida")
    if no_severas:
        notas = " ".join(
            f"{i.farmaco_propuesto} + {i.farmaco_actual} ({i.severidad}): {i.nota}"
            for i in no_severas
        )
        bloques.append(
            f"INTERACCIONES A VIGILAR entre {farmaco} y los medicamentos actuales "
            f"del paciente. {notas}"
        )
        aplicados.append("interacciones_no_severas_antepuestas")
    encabezado = ("\n\n".join(bloques) + "\n\n") if bloques else ""
    if sin_informacion:
        aplicados.append("negativa_sin_informacion")
        return encabezado + TEXTO_SIN_INFORMACION, aplicados
    return encabezado + texto, aplicados


@dataclass
class RespuestaVet:
    texto: str
    ficha_id: str | None = None
    entrada_id: str | None = None
    sin_informacion: bool = False
    alertas: list[str] = field(default_factory=list)
    alerta_severa: bool = False
    guardrails: list[str] = field(default_factory=list)
    dosis: DosisCalculada | None = None
    fuentes_citadas: list[str] = field(default_factory=list)
    archivo_trace: Path | None = None


def _buscar_ficha(recuperador: Recuperador, consulta: str, paciente: str) -> tuple[Fragmento | None, str]:
    condiciones = [{"tipo": "ficha"}]
    if paciente:
        condiciones.append({"paciente_id": paciente})
    # Chroma exige >=2 expresiones en $and: con una sola se pasa directa.
    filtro: dict = {"$and": condiciones} if len(condiciones) > 1 else condiciones[0]
    resultados = recuperador.buscar(consulta, k=3, filtro=filtro)
    if paciente:
        for f in resultados:
            if f.metadata.get("paciente_id") == paciente:
                return f, paciente
    return (resultados[0] if resultados else None), (resultados[0].metadata.get("paciente_id") if resultados else None)


def _buscar_dosificacion(recuperador: Recuperador, especie: str, farmaco: str) -> Fragmento | None:
    farmaco_norm = farmaco.strip().lower()
    # El filtro por metadata exige la coincidencia exacta especie/farmaco antes
    # de rankear: sin el, un farmaco fuera del top-k devolvia una negativa falsa.
    filtro = {
        "$and": [
            {"tipo": "dosificacion"},
            {"especie": especie.lower()},
            {"farmaco": farmaco_norm},
        ]
    }
    for f in recuperador.buscar(f"{especie} {farmaco} dosis mg por kg", k=4, filtro=filtro):
        if f.metadata.get("farmaco", "").lower() == farmaco_norm:
            return f
    return None


class AgenteVeterinario:
    def __init__(
        self,
        llm: ClienteLLM,
        trazador: Trazador,
        recuperador: Recuperador | None = None,
        k: int = 5,
    ):
        self.llm = llm
        self.trazador = trazador
        self.recuperador = recuperador or Recuperador()
        self.k = k

    def _extraer_fuentes(self, texto: str) -> list[str]:
        return sorted(set(REGEX_FUENTES.findall(texto)), key=lambda m: (m[1], int(m[2:-1])))

    @traceable("planificar")
    def planificar(
        self,
        consulta: str,
        especie: str,
        peso_kg: float,
        farmaco: str,
        paciente: str = "",
        medicamentos: list[str] | None = None,
    ) -> RespuestaVet:
        medicamentos = list(medicamentos or [])

        # Validación pre-loop bloqueante
        rechazo = ValidacionEntrada.validar(
            self, consulta, especie, peso_kg, farmaco, paciente, medicamentos
        )
        if rechazo is not None:
            return rechazo

        # Normalizar tras validar (la validación ya garantizó los rangos/formatos)
        especie = (especie or "").strip().lower()
        farmaco = (farmaco or "").strip()
        paciente = (paciente or "").strip().upper()
        peso_kg = float(peso_kg)  # type: ignore[arg-type]

        fragmentos: list[Fragmento] = []
        resultados_tools: list[tuple[str, str]] = []
        ficha_id = None
        entrada_id = None
        dosis: DosisCalculada | None = None
        interacciones: list[Interaccion] = []
        sin_informacion = False

        # Paso 1: ficha del paciente
        self.trazador.registrar(
            "busqueda_ficha", consulta=consulta, paciente=paciente or "(no indicado)"
        )
        ficha, ficha_id = _buscar_ficha(
            self.recuperador, f"{especie} {consulta} ficha del paciente", paciente
        )
        if ficha:
            fragmentos.append(ficha)
            ficha_id = ficha.metadata.get("paciente_id", ficha_id)
            meds_meta = ficha.metadata.get("medicamentos") or ""
            meds_de_ficha = [m.strip() for m in meds_meta.split(",") if m.strip()]
            medicamentos = list(dict.fromkeys(meds_de_ficha + medicamentos))
            self.trazador.registrar(
                "ficha_encontrada", paciente_id=ficha_id, fuente=ficha.fuente
            )
        else:
            self.trazador.registrar("ficha_no_encontrada", paciente=paciente or None)

        # Paso 2: dosificacion especie/farmaco
        self.trazador.registrar(
            "busqueda_dosificacion", especie=especie, farmaco=farmaco
        )
        entrada = _buscar_dosificacion(self.recuperador, especie, farmaco)
        if entrada:
            datos = cargar_entrada(entrada.metadata.get("entrada_id", ""))
            if datos:
                fragmentos.append(entrada)
                entrada_id = datos["id"]
                self.trazador.registrar(
                    "dosificacion_encontrada", entrada_id=entrada_id, fuente=entrada.fuente
                )
                # Paso 3: calculo de dosis
                dosis = calcular_dosis(datos, peso_kg)
                resultados_tools.append((dosis.fuente, describir_dosis(dosis)))
                self.trazador.registrar(
                    "calculo_dosis",
                    entrada_id=entrada_id,
                    peso_kg=peso_kg,
                    disponible=dosis.disponible,
                    rango=f"{dosis.dosis_min_mg}-{dosis.dosis_max_mg} mg" if dosis.disponible else None,
                )
                if not dosis.disponible:
                    sin_informacion = True
            else:
                self.trazador.registrar(
                    "dosificacion_entrada_no_cargada", entrada_id=entrada.metadata.get("entrada_id")
                )
        if entrada_id is None:
            sin_informacion = True
            self.trazador.registrar(
                "sin_dosificacion", especie=especie, farmaco=farmaco,
                motivo="la guia no tiene entrada exacta para esta combinacion",
            )

        # Paso 4: interacciones
        medicamentos_totales = medicamentos
        interacciones = verificar_interaccion(farmaco, medicamentos_totales)
        resultados_tools.append(
            (NOMBRE_FUENTE_CHECKER, describir_interacciones(interacciones, farmaco))
        )
        self.trazador.registrar(
            "verificacion_interacciones",
            farmaco=farmaco,
            medicamentos_actuales=medicamentos_totales,
            hallazgos=len(interacciones),
            severidades=[i.severidad for i in interacciones],
        )

        # Paso 5: redaccion con citas
        caso = (
            f"{consulta}\nPaciente: {paciente or 'sin identificar'} | Especie: {especie} | "
            f"Peso: {peso_kg} kg | Farmaco propuesto: {farmaco} | "
            f"Medicamentos actuales: {', '.join(medicamentos_totales) or 'ninguno'}"
        )
        prompt = armar_usuario(caso, fragmentos, resultados_tools)
        r = self.llm.completar(SISTEMA_BASE, prompt)
        fuentes = self._extraer_fuentes(r.texto)
        alertas = [i.nota for i in interacciones]
        alerta_severa = any(i.severidad == "severa" for i in interacciones)
        texto_final, guardrails_aplicados = _aplicar_guardrails(
            r.texto, sin_informacion, alerta_severa, interacciones, farmaco
        )
        if guardrails_aplicados:
            self.trazador.registrar(
                "guardrails_aplicados", reglas=guardrails_aplicados
            )
        self.trazador.registrar(
            "respuesta_final",
            modelo=r.modelo,
            sin_informacion=sin_informacion,
            alerta_severa=alerta_severa,
            guardrails=guardrails_aplicados,
            citas=fuentes,
        )
        fuentes_resueltas = []
        for marcador in fuentes:
            idx = int(marcador[2:-1])
            prefijo = marcador[1]
            if prefijo == "F" and idx <= len(fragmentos):
                fuentes_resueltas.append(fragmentos[idx - 1].fuente)
            elif prefijo == "T" and idx <= len(resultados_tools):
                fuentes_resueltas.append(resultados_tools[idx - 1][0])
        return RespuestaVet(
            texto=texto_final,
            ficha_id=ficha_id,
            entrada_id=entrada_id,
            sin_informacion=sin_informacion,
            alertas=alertas,
            alerta_severa=alerta_severa,
            guardrails=guardrails_aplicados,
            dosis=dosis,
            fuentes_citadas=fuentes_resueltas or [f.fuente for f in fragmentos],
            archivo_trace=self.trazador.archivo,
        )
