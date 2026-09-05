"""Recuperador RAG: consulta la coleccion 'conocimiento' de ChromaDB (Fase 1)."""
from dataclasses import dataclass, field
from pathlib import Path

from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

RAIZ = Path(__file__).resolve().parents[1]
DIR_CHROMA = RAIZ / "chroma_db"
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass
class Fragmento:
    id: str
    texto: str
    tipo: str
    fuente: str
    metadata: dict = field(default_factory=dict)


class Recuperador:
    def __init__(self, coleccion: str = "conocimiento", dir_chroma: Path | None = None):
        ruta = dir_chroma or DIR_CHROMA
        ef = SentenceTransformerEmbeddingFunction(model_name=MODELO_EMBEDDINGS)
        self._col = PersistentClient(path=str(ruta)).get_collection(coleccion, embedding_function=ef)

    def buscar(self, consulta: str, k: int = 4, filtro: dict | None = None) -> list[Fragmento]:
        r = self._col.query(
            query_texts=[consulta],
            n_results=k,
            where=filtro,
            include=["documents", "metadatas"],
        )
        fragmentos: list[Fragmento] = []
        for doc, meta in zip(r["documents"][0], r["metadatas"][0]):
            fuente = meta.get("paciente_id") or meta.get("entrada_id") or meta.get("nombre", "?")
            fragmentos.append(
                Fragmento(
                    id=str(meta.get("id", "?")),
                    texto=doc,
                    tipo=meta.get("tipo", "?"),
                    fuente=fuente,
                    metadata=dict(meta),
                )
            )
        return fragmentos
