"""Lectura de OfiHotel (SOLO LECTURA, supuesta).

No sabemos todavía cómo se lee OfiHotel: SQL Server en solo lectura, sus exportaciones
integradas o la pantalla. La demo lee una instantánea de ejemplo (`fixtures/ofihotel_lectura.json`).
Quien implemente la lectura real solo tiene que devolver la misma estructura.
"""
import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "ofihotel_lectura.json"


def leer_instantanea() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
