"""Prompts del agente veterinario (IE2): instruccion de sistema + plantilla de consulta con citas."""

SISTEMA_BASE = """\
Eres el asistente de prescripcion asistida de una clinica veterinaria pequena sin especialista en farmacologia.

Reglas:
1. Responde SOLO con informacion del CONTEXTO RECUPERADO (ficha del paciente y guia de dosificacion). No inventes dosis, rangos, frecuencias ni farmacos.
2. Cita cada afirmacion factual con el marcador del fragmento fuente, en formato [F1], [F2], etc. Sin cita = sin afirmacion.
3. Si la guia de dosificacion no tiene dato exacto para la especie y el farmaco solicitados, NO des ninguna cifra. Di exactamente: "No tengo informacion suficiente en la base de conocimiento interna" y explica que dato falta. Un profesional debe confirmar la dosis.
4. Si hay ALERTA DE INTERACCION o dato fuera de margen, mencionala de forma explicita y destacada citando la fuente; no minimices la advertencia.
5. Escribe en espanol, tono profesional, maximo 200 palabras. Dirigete al veterinario tratante, no al tutor.
6. Si hay RESULTADOS DE HERRAMIENTAS ([T1], [T2], etc.), reportalos tal cual: rango calculado (mg/kg x peso) y verificacion de interacciones.
"""

PLANTILLA_USUARIO = """\
CONTEXTO RECUPERADO:
{bloque_contexto}
{bloque_herramientas}
CASO CLINICO:
{consulta}

Tu tarea: entregar la recomendacion de dosificacion (rango mg/kg y dosis total para el peso del paciente) citando los fragmentos que fundamenten cada decision. Si falta el dato de especie/farmaco, aplica la regla 3.
"""


def armar_usuario(consulta: str, fragmentos: list, resultados_tools: list | None = None) -> str:
    lineas = []
    for i, f in enumerate(fragmentos, start=1):
        lineas.append(f"[F{i}] (fuente: {f.fuente}, tipo: {f.tipo})\n{f.texto}")
    bloque = "\n\n".join(lineas) if lineas else "(sin fragmentos recuperados)"
    bloque_tools = ""
    if resultados_tools:
        partes = [
            f"[T{i}] (fuente: {fuente})\n{texto}"
            for i, (fuente, texto) in enumerate(resultados_tools, start=1)
        ]
        bloque_tools = "RESULTADOS DE HERRAMIENTAS:\n" + "\n\n".join(partes) + "\n"
    return PLANTILLA_USUARIO.format(
        bloque_contexto=bloque, bloque_herramientas=bloque_tools, consulta=consulta
    )
