"""CLI de demostracion (D9): caso clinico -> recomendacion justificada.

Uso:
    python main.py "perro con dolor articular" --especie perro --peso 24.5 --farmaco carprofeno --paciente FIC-001
    python main.py "gato con dolor" --especie gato --peso 5.8 --farmaco carprofeno --pasos
    python main.py "perro con dolor" --especie perro --peso 12.3 --farmaco carprofeno --falso

Con --falso usa ClienteFalso (determinista, sin cuota Groq) para probar el
pipeline completo; por defecto usa ClienteLangChain (ChatGroq via LangChain,
openai/gpt-oss-120b) con tracing LangSmith si hay LANGSMITH_API_KEY en .env.
"""
import argparse
import json
import sys
from pathlib import Path

from agent.llm_client import ClienteFalso, ClienteGroq, ClienteLangChain
from agent.observabilidad import init_langsmith
from agent.reasoning_loop import AgenteVeterinario
from agent.trace import Trazador

RAIZ = Path(__file__).resolve().parent


def mostrar_trace(archivo: str, omitir: int = 0) -> None:
    if not archivo:
        return
    lineas = Path(archivo).read_text(encoding="utf-8").strip().split("\n")
    print("\n--- TRAZABILIDAD (trace.jsonl) ---")
    for linea in lineas[omitir:]:
        e = json.loads(linea)
        partes = [f"[{e['paso']:02d}] {e['tipo']}"]
        for clave, valor in e.items():
            if clave in ("paso", "tipo", "hora_utc"):
                continue
            partes.append(f"{clave}={valor}")
        print(" | ".join(partes))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agente de apoyo clinico veterinario: caso -> dosis justificada con citas y guardrails.",
        epilog='Ejemplo: python main.py "perro con dolor articular" --especie perro --peso 24.5 --farmaco carprofeno --pasos',
    )
    parser.add_argument("consulta", help="motivo de consulta (entre comillas)")
    parser.add_argument("--especie", required=True, help="especie del paciente (perro, gato o conejo)")
    parser.add_argument("--peso", required=True, type=float, help="peso del paciente en kg")
    parser.add_argument("--farmaco", required=True, help="farmaco propuesto")
    parser.add_argument("--paciente", default="", help="id de ficha interna (ej: FIC-001)")
    parser.add_argument("--meds", default=None, help="medicamentos actuales separados por coma")
    parser.add_argument("--pasos", action="store_true", help="mostrar cada paso del loop (trace.jsonl)")
    parser.add_argument("--falso", action="store_true", help="usar ClienteFalso determinista (sin cuota Groq)")
    parser.add_argument("--groq-directo", action="store_true", help="usar ClienteGroq (SDK crudo) en vez de ClienteLangChain")
    args = parser.parse_args()

    init_langsmith()
    if args.falso:
        llm = ClienteFalso()
    elif args.groq_directo:
        llm = ClienteGroq()
    else:
        llm = ClienteLangChain()
    agente = AgenteVeterinario(llm=llm, trazador=Trazador(None))
    medicamentos = [m.strip() for m in args.meds.split(",") if m.strip()] if args.meds else None

    archivo_trace = RAIZ / "logs" / "trace.jsonl"
    lineas_previas = len(archivo_trace.read_text(encoding="utf-8").strip().split("\n")) if archivo_trace.exists() else 0

    print(f"Consulta: {args.consulta}")
    print(f"Paciente: {args.paciente or '(sin ficha especifica)'} | {args.especie} | {args.peso} kg")
    print(f"Farmaco propuesto: {args.farmaco}")
    if medicamentos:
        print(f"Medicamentos actuales: {', '.join(medicamentos)}")
    print(f"LLM: {type(llm).__name__}\n")

    r = agente.planificar(
        args.consulta,
        especie=args.especie,
        peso_kg=args.peso,
        farmaco=args.farmaco,
        paciente=args.paciente,
        medicamentos=medicamentos,
    )

    es_rechazo = "validacion_pre_loop" in (r.guardrails or [])
    print("--- ENTRADA RECHAZADA (validación pre-loop, sin RAG/LLM) ---" if es_rechazo else "--- RESPUESTA ---")
    print(r.texto)
    print()
    print(f"Ficha:             {r.ficha_id or '(no recuperada)'}")
    print(f"Entrada dosis:     {r.entrada_id or '(sin dato en la guia)'}")
    if r.dosis:
        print(f"Dosis calculada:   {r.dosis.dosis_min_mg} - {r.dosis.dosis_max_mg} mg por administracion")
    print(f"Sin informacion:   {'si' if r.sin_informacion else 'no'}")
    print(f"Alerta severa:     {'si' if r.alerta_severa else 'no'}")
    for a in r.alertas:
        print(f"Alerta:            {a}")
    if r.guardrails:
        print(f"Guardrails:        {', '.join(r.guardrails)}")
    print(f"Fuentes citadas:   {', '.join(r.fuentes_citadas) if r.fuentes_citadas else '(ninguna)'}")
    print(f"Trace:             {r.archivo_trace}")

    if args.pasos:
        mostrar_trace(r.archivo_trace, omitir=lineas_previas)
    return 2 if "validacion_pre_loop" in (r.guardrails or []) else 0


if __name__ == "__main__":
    sys.exit(main())
