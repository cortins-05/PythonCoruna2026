"""Almacén en un JSON y reloj de demo. Basta para una demo de un solo proceso."""
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "data" / "db.json"
INICIO_DEMO = datetime.fromisoformat(os.environ.get("DEMO_START", "2026-10-24T09:00:00"))


def _vacia() -> dict:
    return {"expedientes": {}, "reloj_h": 0, "seq": 0, "eventos": [], "propuestas": [], "cierres": [], "ofihotel": {}}


class Store:
    def __init__(self, ruta: Path = RUTA):
        self.ruta = ruta
        self.lock = threading.RLock()
        self.db = _vacia()
        if ruta.exists():
            self.db.update(json.loads(ruta.read_text(encoding="utf-8")))

    def ahora(self) -> datetime:
        return INICIO_DEMO + timedelta(hours=self.db["reloj_h"])

    def siguiente_id(self, prefijo: str) -> str:
        self.db["seq"] += 1
        return f"{prefijo}-{self.db['seq']:04d}"

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self.db, ensure_ascii=False, indent=2), encoding="utf-8")

    def reiniciar(self) -> None:
        self.db = _vacia()
        self.guardar()
