"""Asegura que la raiz del repo este en sys.path para importar agent/ y tools/."""
import os
import sys
from pathlib import Path

# Los tests usan ClienteFalso: tracing LangSmith desactivado para que la suite
# sea rapida, offline y no contamine el proyecto de observabilidad.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
