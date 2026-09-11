"""
app.py - Demo Streamlit EP1 Veterinaria (ISY0101).

UI basica para presentar al docente: caso clinico -> dosis justificada.
Ejecuta: uv run streamlit run app.py
"""

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

from agent.llm_client import ClienteFalso, ClienteGroq, ClienteLangChain
from agent.observabilidad import init_langsmith
from agent.reasoning_loop import AgenteVeterinario
from agent.trace import Trazador

init_langsmith()

DIR_FICHAS = RAIZ / "data" / "internal" / "fichas"
DIR_DOSIS = RAIZ / "data" / "external" / "dosificacion"


@st.cache_data
def listar_fichas() -> list[str]:
    ids = []
    for f in sorted(DIR_FICHAS.glob("*.json")):
        try:
            ids.append(json.loads(f.read_text(encoding="utf-8"))["id"])
        except (KeyError, json.JSONDecodeError):
            continue
    return ids


@st.cache_data
def listar_farmacos() -> list[str]:
    farmacos = set()
    for f in sorted(DIR_DOSIS.glob("*.json")):
        try:
            farmacos.add(json.loads(f.read_text(encoding="utf-8"))["farmaco"])
        except (KeyError, json.JSONDecodeError):
            continue
    return sorted(farmacos)


@st.cache_data
def cargar_ficha(paciente_id: str) -> dict:
    if not paciente_id or paciente_id == "(sin ficha)":
        return {}
    candidatos = sorted(DIR_FICHAS.glob(f"{paciente_id}-*.json"))
    if not candidatos:
        exacto = DIR_FICHAS / f"{paciente_id}.json"
        if exacto.exists():
            candidatos = [exacto]
    if not candidatos:
        return {}
    try:
        return json.loads(candidatos[0].read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


PESO_MAX = {"perro": 200.0, "gato": 50.0, "conejo": 10.0}
CASO_ALERTA = {
    "consulta": "perro con dolor articular",
    "especie": "perro",
    "peso": 24.5,
    "farmaco": "carprofeno",
    "paciente": "FIC-001",
    "meds": "",
}
CASO_NEGATIVA = {
    "consulta": "gato con dolor",
    "especie": "gato",
    "peso": 5.8,
    "farmaco": "carprofeno",
    "paciente": "FIC-005",
    "meds": "",
}


st.set_page_config(page_title="Veterinaria - Dosis seguras", page_icon="🐾", layout="wide")
st.title("🐾 Clínica Veterinaria — Apoyo de dosis seguras")
st.caption("ISY0101 EP1 · LangChain (ChatGroq) + Chroma + loop propio · Apoyo clínico, no prescripción · Tracing en LangSmith (proyecto ep1-veterinaria)")

with st.sidebar:
    st.header("Configuración")
    modo_falso = st.checkbox("Modo demo determinista (sin API key)", value=True,
                             help="Usa ClienteFalso: reproducible, sin cuota Groq. Desmárcalo para usar Groq real.")
    ver_trace = st.checkbox("Mostrar trazabilidad del caso", value=True)
    usar_rapido = st.checkbox("Modelo rápido en Groq real (20b)", value=True)
    if st.button("Verificar Groq"):
        try:
            llm = ClienteLangChain(usar_modelo_rapido=True)
            st.success(f"✓ Groq configurado ({llm.modelo})")
        except Exception as e:
            st.error(f"✗ {e}")
    st.divider()
    st.markdown("**Fuentes:**")
    st.markdown("- `data/internal/fichas/` 12 fichas (FIC-001..012)\n- `data/external/dosificacion/` 18 entradas + interacciones\n- Guía curada de referencia, no sustituye Plumb's")
    st.markdown("**Docs:** `agents.md` + `docs/`")

st.subheader("Casos de demostración")
c1, c2 = st.columns(2)
if c1.button("🚨 Caso 1: alerta severa (FIC-001 + carprofeno)", use_container_width=True):
    st.session_state.update(CASO_ALERTA)
if c2.button("🚫 Caso 2: negativa sin información (gato + carprofeno)", use_container_width=True):
    st.session_state.update(CASO_NEGATIVA)

fichas = ["(sin ficha)"] + listar_fichas()
farmacos = listar_farmacos() or ["carprofeno"]

col_a, col_b = st.columns(2)
with col_a:
    consulta = st.text_area("Motivo de consulta",
                            value=st.session_state.get("consulta", CASO_ALERTA["consulta"]),
                            height=80, placeholder="Ej: perro con dolor articular")
    paciente = st.selectbox("Ficha del paciente", fichas,
                            index=fichas.index(st.session_state.get("paciente", "FIC-001"))
                            if st.session_state.get("paciente", "FIC-001") in fichas else 0)
with col_b:
    ficha = cargar_ficha(paciente)
    ficha_especie = str(ficha.get("especie", "")).strip().lower() if ficha else ""
    peso_def = float(st.session_state.get("peso") or ficha.get("peso_kg", 10.0)) if ficha else float(st.session_state.get("peso") or 10.0)
    farmaco_def = st.session_state.get("farmaco", "carprofeno")
    if ficha_especie in ("perro", "gato", "conejo"):
        # La especie viene de la ficha y se bloquea: no se puede mezclar.
        especie = ficha_especie
        st.selectbox("Especie (de la ficha, bloqueada)", ["perro", "gato", "conejo"],
                     index=["perro", "gato", "conejo"].index(especie), disabled=True,
                     help="Se toma de la ficha para evitar mezclas ficha-vs-especie.")
    else:
        # Sin ficha: la especie sí se pide manual (caso sin historial).
        especie_def = st.session_state.get("especie") or "perro"
        especie = st.selectbox("Especie", ["perro", "gato", "conejo"],
                               index=["perro", "gato", "conejo"].index(especie_def)
                               if especie_def in ("perro", "gato", "conejo") else 0)
    peso = st.number_input("Peso (kg)", min_value=0.1,
                               max_value=PESO_MAX.get(especie, 200.0),
                               value=min(peso_def, PESO_MAX.get(especie, 200.0)), step=0.1)
    farmaco = st.selectbox("Fármaco propuesto (solo con guía DOS)", farmacos,
                           index=farmacos.index(farmaco_def) if farmaco_def in farmacos else 0)
    meds_txt = st.text_input("Medicamentos actuales extra (coma)",
                             value=st.session_state.get("meds", ""),
                             placeholder="Opcional: la ficha ya aporta los registrados")

if ficha:
    with st.expander(f"Ficha {paciente} recuperada (RAG interno)"):
        st.json({k: ficha.get(k) for k in ("paciente", "especie", "raza", "peso_kg",
                                           "medicamentos_actuales", "resumen") if k in ficha})

if st.button("🔍 Consultar agente", type="primary", use_container_width=True):
    if not modo_falso and not os.getenv("GROQ_API_KEY"):
        st.error("Falta GROQ_API_KEY en .env (o activa el modo demo determinista en la barra lateral).")
        st.stop()
    archivo_trace = RAIZ / "logs" / "trace.jsonl"
    lineas_previas = len(archivo_trace.read_text(encoding="utf-8").strip().split("\n")) if archivo_trace.exists() else 0
    with st.spinner("Recuperando ficha + dosificación, calculando y verificando..."):
        try:
            llm = ClienteFalso() if modo_falso else ClienteLangChain(usar_modelo_rapido=usar_rapido)
            agente = AgenteVeterinario(llm=llm, trazador=Trazador(None))
            meds = [m.strip() for m in meds_txt.split(",") if m.strip()] or None
            r = agente.planificar(consulta, especie=especie, peso_kg=peso,
                                  farmaco=farmaco,
                                  paciente="" if paciente == "(sin ficha)" else paciente,
                                  medicamentos=meds)
            st.subheader("Respuesta")
            if "validacion_pre_loop" in (r.guardrails or []):
                st.error("⛔ Entrada inválida — rechazada antes de RAG/LLM. Corregir los datos e intentar de nuevo.")
            elif r.alerta_severa:
                st.error("🚨 ALERTA DE INTERACCIÓN SEVERA — no administrar sin supervisión veterinaria directa.")
            if r.sin_informacion and "validacion_pre_loop" not in (r.guardrails or []):
                st.warning("Sin información suficiente en la guía para esta combinación especie/fármaco: no se entrega dosis.")
            st.markdown(r.texto)
            st.divider()
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Ficha", r.ficha_id or "(no recuperada)")
                st.metric("Entrada dosis", r.entrada_id or "(sin dato en guía)")
            with m2:
                if r.dosis and r.dosis.disponible:
                    st.metric("Dosis calculada (mg)",
                              f"{r.dosis.dosis_min_mg} – {r.dosis.dosis_max_mg}")
                else:
                    st.metric("Dosis calculada", "no disponible")
                st.write(f"**Sin información:** {'sí' if r.sin_informacion else 'no'} · "
                         f"**Alerta severa:** {'sí' if r.alerta_severa else 'no'}")
            with m3:
                st.markdown("**Fuentes citadas:**")
                st.write(", ".join(r.fuentes_citadas) if r.fuentes_citadas else "(ninguna)")
                if r.guardrails:
                    st.markdown("**Guardrails aplicados:**")
                    st.code(", ".join(r.guardrails))
            if r.alertas:
                with st.expander("Interacciones detectadas"):
                    for a in r.alertas:
                        st.write(f"- {a}")
            if ver_trace and r.archivo_trace:
                with st.expander("Trazabilidad del caso (trace.jsonl)"):
                    try:
                        lineas = Path(r.archivo_trace).read_text(encoding="utf-8").strip().split("\n")
                        for linea in lineas[lineas_previas:]:
                            e = json.loads(linea)
                            st.code(f"[{e['paso']:02d}] {e['tipo']} | " + " | ".join(
                                f"{k}={v}" for k, v in e.items() if k not in ("paso", "tipo", "hora_utc")))
                    except FileNotFoundError:
                        st.info("Aún no hay trace para esta corrida.")
            st.caption(f"LLM: {type(llm).__name__} · Ficha: {r.ficha_id or '-'} · Entrada: {r.entrada_id or '-'}")
        except Exception as e:
            st.error(f"Error: {e}")
            st.exception(e)

st.divider()
st.caption("Apoyo clínico, no prescripción. Guía curada de referencia — no sustituye Plumb's ni criterio veterinario. Uso de IA declarado en el informe.")
