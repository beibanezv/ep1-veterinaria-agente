"""Observabilidad opcional con LangSmith (sin romper tests si no hay key).

Activa con .env:
    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=lsv2_...
    LANGSMITH_PROJECT=ep1-veterinaria
"""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")


def init_langsmith() -> bool:
    """Activa tracing de LangSmith solo si hay API key. Retorna True si quedó activo."""
    if not os.getenv("LANGSMITH_API_KEY"):
        return False
    os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGSMITH_TRACING", "true")
    os.environ["LANGCHAIN_PROJECT"] = os.getenv(
        "LANGSMITH_PROJECT", "ep1-veterinaria"
    )
    return True


def traceable(nombre: str):
    """Decorador @traceable de LangSmith si está instalado; si no, no-op."""
    try:
        from langsmith import traceable as _traceable

        return _traceable(name=nombre)
    except ImportError:
        def _noop(fn):
            return fn

        return _noop
