"""Inventario: el sistema central sabe qué está ocupado.

Ocupación = expedientes del sistema (reservas de canal y walk-ins) + instantánea de solo lectura de
OfiHotel, sin contar dos veces lo que ya está en un expediente (se compara por `ref_externa`).
"""
import json
from datetime import date, timedelta
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "habitaciones.json"


def capacidad() -> dict[str, int]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["capacidad"]


def _dias(desde: str, hasta: str):
    dia, fin = date.fromisoformat(desde), date.fromisoformat(hasta)
    while dia < fin:
        yield dia.isoformat()
        dia += timedelta(days=1)


def ocupaciones(db: dict) -> list[dict]:
    filas, refs = [], set()
    for exp in db["expedientes"].values():
        refs.add(exp["referencia"])  # también las canceladas: si RoomCloud (prioridad 1) la dio de baja, su fila vieja de OfiHotel no cuenta
        if exp["estado"] in ("cancelada", "cerrado"):
            continue
        for h in exp["habitaciones"]:
            filas.append({"tipo": h["tipo"], "desde": exp["checkin_prevista"], "hasta": exp["checkout_prevista"],
                          "quien": exp["id"], "fuente": exp["origen"]})
    for f in db.get("ofihotel", {}).get("ocupaciones", []):
        if f.get("ref_externa") and f["ref_externa"] in refs:
            continue
        filas.append({"tipo": f["tipo"], "desde": f["desde"], "hasta": f["hasta"], "quien": f["huesped"], "fuente": "ofihotel"})
    return filas


def mapa(db: dict, desde: str, dias: int = 7) -> dict:
    fechas = [(date.fromisoformat(desde) + timedelta(days=i)).isoformat() for i in range(dias)]
    filas, cierres = ocupaciones(db), db.get("cierres", [])
    tipos = {}
    for tipo, cap in capacidad().items():
        casillas = []
        for f in fechas:
            ocupadas = sum(1 for o in filas if o["tipo"] == tipo and o["desde"] <= f < o["hasta"])
            cerrado = any(c["tipo"] == tipo and c["entrada"] <= f < c["salida"] for c in cierres)
            casillas.append({"fecha": f, "ocupadas": ocupadas, "libres": cap - ocupadas, "cerrado_en_roomcloud": cerrado})
        tipos[tipo] = {"capacidad": cap, "dias": casillas}
    return {"fechas": fechas, "tipos": tipos}


def conflictos(db: dict, desde: str, dias: int = 7) -> list[dict]:
    salida = []
    for tipo, datos in mapa(db, desde, dias)["tipos"].items():
        for c in datos["dias"]:
            if c["ocupadas"] >= datos["capacidad"]:
                salida.append({"tipo": tipo, "fecha": c["fecha"], "ocupadas": c["ocupadas"], "capacidad": datos["capacidad"],
                               "nivel": "overbooking" if c["ocupadas"] > datos["capacidad"] else "lleno"})
    return salida
