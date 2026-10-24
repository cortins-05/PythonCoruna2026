"""Lectura de OfiHotel (SOLO LECTURA).

OfiHotel no tiene API, así que leemos su base SQL Server en solo lectura, con los datos del día
anterior. `leer_instantanea` devuelve siempre la misma forma normalizada, venga de la instantánea de
ejemplo (modo "fixture", por defecto) o de la base real (modo "sql"). El modo sale del argumento o de
la variable OFIHOTEL_MODO. Nunca se escribe en OfiHotel.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "ofihotel_ayer.json"
ESTADOS_OCUPAN = ("reservada", "en_casa")


def _como_datetime(ahora):
    if ahora is None:
        return None
    return ahora if isinstance(ahora, datetime) else datetime.fromisoformat(str(ahora))


def _derivar_ocupaciones(estancias: list[dict]) -> list[dict]:
    return [{"habitacion": e["habitacion"], "tipo": e["tipo"], "desde": e["entrada"], "hasta": e["salida"],
             "huesped": e["huesped"], "ref_externa": e["ref_externa"]}
            for e in estancias if e["estado"] in ESTADOS_OCUPAN]


def leer_instantanea(ahora=None, modo=None) -> dict:
    modo = (modo or os.environ.get("OFIHOTEL_MODO") or "fixture").strip().lower()
    if modo not in ("fixture", "sql"):
        raise ValueError(f"Modo de lectura desconocido: {modo}")
    reloj = _como_datetime(ahora)
    if modo == "sql":
        from . import ofihotel_sql
        estancias = ofihotel_sql.leer_estancias()
        reloj = reloj or datetime.now()
        base = {}
    else:
        base = json.loads(FIXTURE.read_text(encoding="utf-8"))
        estancias = base["estancias"]
    datos_hasta = os.environ.get("OFIHOTEL_DATOS_HASTA")
    if not datos_hasta:
        if reloj is not None:
            datos_hasta = (reloj - timedelta(days=1)).strftime("%Y-%m-%dT23:59")
        else:
            datos_hasta = base["datos_hasta"]
    leido_el = reloj.strftime("%Y-%m-%dT%H:%M") if reloj else base["leido_el"]
    return {"fuente": modo, "leido_el": leido_el, "datos_hasta": datos_hasta,
            "estancias": estancias, "ocupaciones": _derivar_ocupaciones(estancias)}
