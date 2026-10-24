"""Vuelca a design/muestras/*.json las respuestas reales de la API con la semilla `completa`, para que el front se escriba contra datos reales.

Uso: python scripts/volcar_muestras.py   (desde martin/poc). No llama a ningún servicio externo.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.store import Store  # noqa: E402

DESTINO = RAIZ / "design" / "muestras"
RUTAS = {
    "prioridades": "/api/prioridades",
    "fuente-unica": "/api/fuente-unica",
    "comunicaciones": "/api/comunicaciones",
    "estancias": "/api/estancias",
    "conflictos": "/api/conflictos",
    "ocupacion": "/api/ocupacion?dias=14",
    "insignias": "/api/insignias",
    "estado": "/api/estado",
    "propuestas": "/api/propuestas",
}


def main_volcado() -> None:
    main.store = Store(Path(tempfile.mkdtemp()) / "db.json")
    cliente = TestClient(main.app)
    assert cliente.post("/api/demo/semilla", params={"nivel": "completa"}).status_code == 200
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre, ruta in RUTAS.items():
        datos = cliente.get(ruta).json()
        (DESTINO / f"{nombre}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{nombre}.json  {(DESTINO / f'{nombre}.json').stat().st_size // 1024} KB")
    uno = cliente.get("/api/comunicaciones").json()["comunicaciones"][0]
    (DESTINO / "comunicacion.json").write_text(json.dumps(uno, ensure_ascii=False, indent=1), encoding="utf-8")
    exp = cliente.get("/api/estancias").json()["estancias"][0]["id"]
    detalle = cliente.get(f"/api/expedientes/{exp}").json()
    (DESTINO / "expediente.json").write_text(json.dumps(detalle, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main_volcado()
