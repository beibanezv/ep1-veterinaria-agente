"""Ingesta RAG: fichas internas + guia de dosificacion externa -> ChromaDB persistente."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
DIR_FICHAS = RAIZ / "data" / "internal" / "fichas"
DIR_DOSIFICACION = RAIZ / "data" / "external" / "dosificacion"
DIR_CHROMA = RAIZ / "chroma_db"

MAX_CHARS = 500
OVERLAP = 50


def cargar_fichas() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR_FICHAS.glob("*.json"))]


def cargar_dosificacion() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR_DOSIFICACION.glob("*.json"))]


def texto_ficha(f: dict) -> str:
    partes = [
        f"Ficha clinica: {f['paciente']} (id {f['id']}).",
        f"Especie: {f['especie']}. Raza: {f['raza']}. Peso: {f['peso_kg']} kg. Edad: {f['edad_anios']} anos.",
        f"Medicamentos actuales: {', '.join(f['medicamentos_actuales']) or 'ninguno'}.",
        f"Alergias registradas: {', '.join(f['alergias']) or 'ninguna'}.",
        f"Resumen: {f['resumen']}",
    ]
    return "\n".join(partes)


def texto_dosificacion(e: dict) -> str:
    frec = f"cada {e['frecuencia_horas']} horas" if e["frecuencia_horas"] > 0 else "dosis unica"
    partes = [
        f"Entrada de dosificacion (id {e['id']}).",
        f"Especie: {e['especie']}. Farmaco: {e['farmaco']}. Via: {e['via']}.",
        f"Dosis: {e['dosis_mg_por_kg_min']} a {e['dosis_mg_por_kg_max']} mg por kg, {frec}.",
        f"Nota: {e['nota']}",
        f"Fuente: {e['fuente_bibliografica']}",
    ]
    return "\n".join(partes)


def chunk_texto(texto: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    parrafos = [p.strip() for p in texto.split("\n") if p.strip()]
    chunks: list[str] = []
    actual = ""
    for p in parrafos:
        while len(p) > max_chars:
            if actual:
                chunks.append(actual)
                actual = ""
            chunks.append(p[:max_chars])
            p = p[max_chars - overlap:]
        if not actual:
            actual = p
        elif len(actual) + 1 + len(p) <= max_chars:
            actual = f"{actual}\n{p}"
        else:
            chunks.append(actual)
            actual = p
    if actual:
        chunks.append(actual)
    return chunks


def construir_indice() -> tuple[int, int]:
    from chromadb import PersistentClient
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    modelo = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    ef = SentenceTransformerEmbeddingFunction(model_name=modelo)
    cliente = PersistentClient(path=str(DIR_CHROMA))
    try:
        cliente.delete_collection("conocimiento")
    except Exception:
        pass
    col = cliente.get_or_create_collection("conocimiento", embedding_function=ef)

    ids: list[str] = []
    documentos: list[str] = []
    metadatas: list[dict] = []

    for f in cargar_fichas():
        for i, chunk in enumerate(chunk_texto(texto_ficha(f))):
            ids.append(f"{f['id']}::c{i}")
            documentos.append(chunk)
            metadatas.append({
                "tipo": "ficha",
                "paciente_id": f["id"],
                "nombre": f["paciente"],
                "especie": f["especie"],
                "raza": f["raza"],
                "peso_kg": f["peso_kg"],
                "medicamentos": ",".join(f["medicamentos_actuales"]),
                "chunk_index": i,
            })

    for e in cargar_dosificacion():
        for i, chunk in enumerate(chunk_texto(texto_dosificacion(e))):
            ids.append(f"{e['id']}::c{i}")
            documentos.append(chunk)
            metadatas.append({
                "tipo": "dosificacion",
                "entrada_id": e["id"],
                "especie": e["especie"],
                "farmaco": e["farmaco"],
                "via": e["via"],
                "chunk_index": i,
            })

    col.add(ids=ids, documents=documentos, metadatas=metadatas)
    return len(documentos), col.count()


def verificar() -> bool:
    from chromadb import PersistentClient
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    ef = SentenceTransformerEmbeddingFunction(model_name=os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ))
    col = PersistentClient(path=str(DIR_CHROMA)).get_collection("conocimiento", embedding_function=ef)

    casos = [
        ("historial clinico de Firulais", {"tipo": "ficha"}, {"FIC-001"}),
        ("gato con artrosis en tratamiento", {"tipo": "ficha"}, {"FIC-005"}),
        ("perro con hipotiroidismo", {"tipo": "ficha"}, {"FIC-011"}),
        ("dosis de carprofeno para perro", {"$and": [{"tipo": "dosificacion"}, {"especie": "perro"}]}, {"DOS-001"}),
        ("dosificacion de meloxicam en gato", {"$and": [{"tipo": "dosificacion"}, {"especie": "gato"}]}, {"DOS-008"}),
        ("antibiotico para conejo", {"$and": [{"tipo": "dosificacion"}, {"especie": "conejo"}]}, {"DOS-014", "DOS-016"}),
    ]
    ok = True
    for consulta, filtro, esperados in casos:
        r = col.query(query_texts=[consulta], n_results=1, where=filtro)
        meta = r["metadatas"][0][0]
        hit = meta.get("paciente_id") or meta.get("entrada_id", "?")
        paso = hit in esperados
        ok = ok and paso
        print(f"{'MATCH ' if paso else 'MISS  '} '{consulta}' -> {hit} (esperado: {sorted(esperados)})")
    return ok


if __name__ == "__main__":
    load_dotenv()
    chunks, total = construir_indice()
    print(f"Ingesta OK: {chunks} documentos indexados (total en coleccion: {total})")
    raise SystemExit(0 if verificar() else 1)
