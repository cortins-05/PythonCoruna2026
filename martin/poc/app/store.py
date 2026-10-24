"""Almacén en un JSON y reloj de demo. Basta para una demo de un solo proceso."""
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "data" / "db.json"
INICIO_DEMO = datetime.fromisoformat(os.environ.get("DEMO_START", "2026-10-24T09:00:00"))


class Store:
    def __init__(self, ruta: Path = RUTA):
        self.ruta = ruta
        self.lock = threading.RLock()
        self.db = {"expedientes": {}, "reloj_h": 0}
        if ruta.exists():
            self.db = json.loads(ruta.read_text(encoding="utf-8"))

    def ahora(self) -> datetime:
        return INICIO_DEMO + timedelta(hours=self.db["reloj_h"])

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(self.db, ensure_ascii=False, indent=2), encoding="utf-8")

    def reiniciar(self) -> None:
        self.db = {"expedientes": {}, "reloj_h": 0}
        self.guardar()
