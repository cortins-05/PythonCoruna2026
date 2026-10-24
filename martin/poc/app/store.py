"""Almacén en un JSON y reloj de demo. Basta para una demo de un solo proceso.

La ruta del JSON sale de la variable de entorno `HOTEL_DB` si existe, así que cada proceso (o cada agente que
trabaje en paralelo) puede usar el suyo sin pisar el de los demás. Un JSON antiguo al que le falten claves
nuevas se carga igualmente y se completa con los valores por defecto.
"""
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "data" / "db.json"
INICIO_DEMO = datetime.fromisoformat(os.environ.get("DEMO_START", "2026-10-24T09:00:00"))
SERIES = ("factura", "albaran")


def ruta_db() -> Path:
    """Ruta del JSON de datos: `HOTEL_DB` si está definida y, si no, `data/db.json` junto al código."""
    valor = os.environ.get("HOTEL_DB", "").strip()
    return Path(valor).expanduser() if valor else RUTA_POR_DEFECTO


RUTA = ruta_db()  # se conserva el nombre antiguo por si alguien lo importa


def _vacia() -> dict:
    return {"expedientes": {}, "reloj_h": 0, "seq": 0, "eventos": [], "propuestas": [], "cierres": [], "ofihotel": {},
            "documentos": {}, "outbox": [], "series": {tipo: 0 for tipo in SERIES}}


def _completar(db: dict) -> dict:
    """Rellena lo que falte en un JSON antiguo sin tocar lo que ya trae, y corrige tipos que no cuadran."""
    for clave, valor in _vacia().items():
        db.setdefault(clave, valor)
    if not isinstance(db["documentos"], dict):
        db["documentos"] = {}
    if not isinstance(db["outbox"], list):
        db["outbox"] = []
    if not isinstance(db["series"], dict):
        db["series"] = {}
    for tipo in SERIES:
        db["series"].setdefault(tipo, 0)
    return db


class Store:
    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta) if ruta is not None else ruta_db()
        self.lock = threading.RLock()
        self.db = _vacia()
        if self.ruta.exists():
            self.db.update(json.loads(self.ruta.read_text(encoding="utf-8")))
        _completar(self.db)

    def ahora(self) -> datetime:
        return INICIO_DEMO + timedelta(hours=self.db["reloj_h"])

    def siguiente_id(self, prefijo: str) -> str:
        with self.lock:
            self.db["seq"] += 1
            return f"{prefijo}-{self.db['seq']:04d}"

    def guardar(self) -> None:
        with self.lock:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.write_text(json.dumps(self.db, ensure_ascii=False, indent=2), encoding="utf-8")

    def reiniciar(self) -> None:
        with self.lock:
            self.db = _vacia()
            self.guardar()
