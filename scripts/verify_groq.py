"""Verifica GROQ_API_KEY, embeddings locales y ChromaDB antes de correr el agente."""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


def main() -> int:
    key = os.getenv("GROQ_API_KEY", "")
    print(f"GROQ_API_KEY configurada: {bool(key)} (empieza con {key[:4] if key else '?'})")
    print(f"GROQ_MODEL={os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')}")
    print(f"EMBEDDING_MODEL={EMBEDDING_MODEL}")

    if not key:
        print("✗ Falta GROQ_API_KEY - copia .env.example a .env y edítala")
        return 1

    try:
        from groq import Groq

        cliente = Groq()
        modelo = os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")
        respuesta = cliente.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": "Responde solo: OK"}],
            max_completion_tokens=100,
            reasoning_effort="low",
        )
        contenido = respuesta.choices[0].message.content.strip()
        print(f"✓ Groq responde ({modelo}): {contenido!r}")
    except Exception as e:
        print(f"✗ Groq error: {e}")
        return 1

    try:
        print("[..] Cargando embeddings locales (primera vez descarga ~470MB)...")
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        dim = len(ef(["prueba"])[0])
        print(f"✓ Embeddings locales OK: dim={dim}")
    except Exception as e:
        print(f"✗ Embeddings error: {e}")
        return 1

    try:
        import chromadb

        ef_st = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        cliente_chroma = chromadb.EphemeralClient()
        col = cliente_chroma.get_or_create_collection("verify", embedding_function=ef_st)
        col.add(ids=["1"], documents=["prueba de ingesta"])
        res = col.query(query_texts=["prueba"], n_results=1)
        print(f"✓ ChromaDB OK (recuperado: {res['documents'][0][0]!r})")
    except Exception as e:
        print(f"✗ ChromaDB error: {e}")
        return 1

    print("Listo: Groq, embeddings y ChromaDB funcionan correctamente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
