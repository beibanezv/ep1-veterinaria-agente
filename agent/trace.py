"""Trazabilidad: cada paso del loop queda registrado en logs/trace.jsonl (requisito 5 del encargo)."""
import json
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_LOGS = RAIZ / "logs"


class Trazador:
    def __init__(self, archivo: Path | None = None):
        self.archivo = archivo or (DIR_LOGS / "trace.jsonl")
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        self.paso = 0

    def registrar(self, tipo: str, **detalle) -> dict:
        self.paso += 1
        evento = {
            "paso": self.paso,
            "tipo": tipo,
            "hora_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **detalle,
        }
        with self.archivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        return evento
