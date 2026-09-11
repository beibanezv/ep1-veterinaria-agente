"""Genera docs/figura1_arquitectura.png (Figura 1 del informe) sin dependencias externas.

Uso: python scripts/render_diagramas.py
Reemplaza el bloque Mermaid pegado como texto en el informe por un PNG real.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "figura1_arquitectura.png"

TITULO = "Figura 1. Arquitectura del agente de dosis seguras (loop razonamiento-accion)"

# (texto, tipo, texto_desvio, etiqueta_desvio, tipo_desvio)
# tipo: "box" | "decision"; tipo_desvio: "guard" (alerta/rechazo) | "ok" (camino alterno)
FILAS = [
    ("Consulta clinica: especie + peso + farmaco + paciente", "box", None, None, None),
    ("Validacion pre-loop (bloqueante): especie / peso / ficha / farmaco", "box",
     "Rechaza la entrada sin ejecutar RAG ni LLM", "no valida", "guard"),
    ("Recuperador RAG (Chroma): ficha del paciente", "box", None, None, None),
    ("Recuperador RAG (Chroma): entrada de dosificacion especie/farmaco", "box", None, None, None),
    ("Decision: existe entrada exacta en la guia?", "decision",
     "Guardrail: negativa sin informacion suficiente", "no", "guard"),
    ("Tool dose_calculator: mg/kg x peso = rango (mg)", "box", None, None, None),
    ("Tool interaction_checker: farmaco propuesto vs medicamentos actuales", "box", None, None, None),
    ("Decision: hay interaccion farmacologica?", "decision",
     "Alerta explicita (severa / moderada / leve)", "si", "guard"),
    ("LLM (Groq gpt-oss) + SISTEMA_BASE: redacta con citas [F#] / [T#]", "box", None, None, None),
    ("Guardrails post-LLM en codigo: negativa y alertas", "box", None, None, None),
    ("Respuesta final + logs/trace.jsonl", "box", None, None, None),
]

COL = {
    "box": ((220, 233, 247), (46, 90, 138)),
    "decision": ((252, 232, 200), (176, 122, 30)),
    "guard": ((251, 227, 229), (176, 42, 55)),
    "ok": ((221, 243, 225), (46, 125, 50)),
}
W = 1120
MX0, MX1 = 40, 700
SX0, SX1 = 745, 1080
PAD = 14


def _fuente(size: int, bold: bool = False):
    nombres = ("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")
    for nombre in nombres:
        try:
            return ImageFont.truetype(nombre, size)
        except OSError:
            continue
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, texto, font, max_ancho):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=font) <= max_ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def main() -> None:
    f_titulo = _fuente(24, True)
    f_texto = _fuente(19)
    f_label = _fuente(16, True)
    lh_t, lh_x, lh_l = 30, 24, 20

    tmp = Image.new("RGB", (10, 10))
    med = ImageDraw.Draw(tmp)

    alturas = []
    for texto, tipo, desvio, etiqueta, _ in FILAS:
        main_n = len(_wrap(med, texto, f_texto, MX1 - MX0 - 2 * PAD))
        side_n = len(_wrap(med, desvio, f_texto, SX1 - SX0 - 2 * PAD)) if desvio else 0
        alturas.append(max(main_n * lh_x, side_n * lh_x) + 2 * PAD)

    y = 28 + lh_t + 26
    total = y + sum(alturas) + (len(FILAS) - 1) * 34 + 40
    img = Image.new("RGB", (W, total), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((MX0, 24), TITULO, font=f_titulo, fill=(30, 30, 30))

    centros = []
    for i, ((texto, tipo, desvio, etiqueta, tipo_desvio), alto) in enumerate(zip(FILAS, alturas)):
        relleno, borde = COL[tipo]
        d.rounded_rectangle([MX0, y, MX1, y + alto], radius=10, fill=relleno, outline=borde, width=2)
        ty = y + PAD
        for linea in _wrap(d, texto, f_texto, MX1 - MX0 - 2 * PAD):
            d.text((MX0 + PAD, ty), linea, font=f_texto, fill=(20, 20, 20))
            ty += lh_x
        centros.append((MX0 + MX1) // 2)

        if desvio:
            r_fill, r_borde = COL[tipo_desvio]
            sa = max(len(_wrap(d, desvio, f_texto, SX1 - SX0 - 2 * PAD)) * lh_x + 2 * PAD, alto)
            ym = y + (alto - sa) / 2
            d.rounded_rectangle([SX0, ym, SX1, ym + sa], radius=10, fill=r_fill, outline=r_borde, width=2)
            ty = ym + PAD
            for linea in _wrap(d, desvio, f_texto, SX1 - SX0 - 2 * PAD):
                d.text((SX0 + PAD, ty), linea, font=f_texto, fill=(20, 20, 20))
                ty += lh_x
            yn = y + alto / 2
            ys = ym + sa / 2
            d.line([(MX1, yn), (SX0, yn)], fill=borde, width=2)
            d.line([(SX0, yn), (SX0, ys)], fill=borde, width=2)
            d.line([(SX0, ys), (SX0 + 12, ys - 5)], fill=r_borde, width=2)
            d.line([(SX0, ys), (SX0 + 12, ys + 5)], fill=r_borde, width=2)
            if etiqueta:
                d.text((MX1 + 8, yn - lh_l), etiqueta, font=f_label, fill=r_borde)

        if i < len(FILAS) - 1:
            xc = centros[-1]
            d.line([(xc, y + alto), (xc, y + alto + 34)], fill=(60, 60, 60), width=2)
            d.polygon([(xc - 6, y + alto + 24), (xc + 6, y + alto + 24), (xc, y + alto + 34)], fill=(60, 60, 60))
        y += alto + 34

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    img.save(SALIDA)
    print(f"OK -> {SALIDA} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
