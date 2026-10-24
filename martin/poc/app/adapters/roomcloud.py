"""Adaptador de entrada desde RoomCloud.

La demo lee un XML grabado (`fixtures/roomcloud_reservations.xml`). Ese fichero está
reconstruido a partir de los nombres de campo de `docs/02-investigacion.md`, no es una
respuesta real de RoomCloud, y el parser acepta cada campo como atributo o como elemento hijo
porque no hemos visto la especificación completa.

Contra la API real hay que llamar a `reservations` con `useDLM="false"` y fechas, nunca con
`useDLM="true"`: ese cursor es compartido por cuenta y le robaría reservas a otra integración.
"""
from pathlib import Path
from xml.etree import ElementTree as ET

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "roomcloud_reservations.xml"
ESTADOS_CANCELADOS = {"3", "7"}
MEDIOS_PAGO = {"1": "TRANSFERENCIA", "2": "GIRO", "3": "PAYPAL", "4": "TARJETA"}


def _campo(nodo: ET.Element, nombre: str) -> str:
    valor = nodo.get(nombre)
    if valor is not None:
        return valor.strip()
    for hijo in nodo.iter():
        if hijo.tag == nombre:
            return (hijo.text or hijo.get("value") or "").strip()
        if hijo is not nodo and hijo.get(nombre) is not None:
            return hijo.get(nombre).strip()
    return ""


def parsear(xml: str) -> list[dict]:
    """Convierte la respuesta en reservas. `ccData` se descarta aquí y no sale del parser."""
    raiz = ET.fromstring(xml)
    reservas = []
    for r in raiz.iter("reservation"):
        habitaciones = [
            {"tipo": _campo(h, "roomId") or _campo(h, "name"), "tarifa": _campo(h, "rateId"),
             "adultos": _campo(h, "adults"), "ninos": _campo(h, "children")}
            for h in r.iter("room")
        ]
        reservas.append({
            "portal_id": _campo(r, "portalId"),
            "id_canal": _campo(r, "id"),
            "dlm": _campo(r, "dlm"),
            "estado_rc": _campo(r, "status"),
            "checkin": _campo(r, "checkin"),
            "checkout": _campo(r, "checkout"),
            "nombre": _campo(r, "firstName"),
            "apellidos": _campo(r, "lastName"),
            "telefono": _campo(r, "telephone"),
            "email": _campo(r, "email"),
            "pais": _campo(r, "country"),
            "importe": _campo(r, "price"),
            "medio_pago": MEDIOS_PAGO.get(_campo(r, "paymentType"), ""),
            "notas": _campo(r, "notes"),
            "habitaciones": habitaciones,
        })
    return reservas


def leer_reservas() -> list[dict]:
    return parsear(FIXTURE.read_text(encoding="utf-8"))
