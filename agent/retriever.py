"""Recuperador RAG: consulta la coleccion 'conocimiento' de ChromaDB (Fase 1)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")
DIR_CHROMA = RAIZ / "chroma_db"
MODELO_EMBEDDINGS = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


@dataclass
class Fragmento:
    id: str
    texto: str
    tipo: str
    fuente: str
    metadata: dict = field(default_factory=dict)
    # Distancia del embedding a la consulta (menor = mas similar).
    # None si Chroma no la devolvio. Puerta fuera-de-dominio (D11).
    score: float | None = None


class Recuperador:
    def __init__(self, coleccion: str = "conocimiento", dir_chroma: Path | None = None):
        ruta = dir_chroma or DIR_CHROMA
        ef = SentenceTransformerEmbeddingFunction(model_name=MODELO_EMBEDDINGS)
        try:
            self._col = PersistentClient(path=str(ruta)).get_collection(coleccion, embedding_function=ef)
        except Exception as e:
            raise RuntimeError(
                f"No se encontró la colección '{coleccion}' en {ruta} "
                f"(modelo={MODELO_EMBEDDINGS}). Ejecuta: uv run python -m ingestion.ingest"
            ) from e

    def buscar(self, consulta: str, k: int = 4, filtro: dict | None = None) -> list[Fragmento]:
        r = self._col.query(
            query_texts=[consulta],
            n_results=k,
            where=filtro,
            include=["documents", "metadatas", "distances"],
        )
        distancias = r.get("distances", [[None] * len(r["documents"][0])])[0]
        fragmentos: list[Fragmento] = []
        for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], distancias):
            fuente = meta.get("paciente_id") or meta.get("entrada_id") or meta.get("nombre", "?")
            fragmentos.append(
                Fragmento(
                    id=str(meta.get("id", "?")),
                    texto=doc,
                    tipo=meta.get("tipo", "?"),
                    fuente=fuente,
                    metadata=dict(meta),
                    score=float(dist) if dist is not None else None,
                )
            )
        return fragmentos
