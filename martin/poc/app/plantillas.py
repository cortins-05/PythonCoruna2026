"""Plantillas cerradas: lo único que el sistema puede proponer enviar o ejecutar.

Cada variable se valida contra un formato estricto antes de rellenar la plantilla. Así un texto
malicioso que llegue en un nombre o en un mensaje no puede colar enlaces, instrucciones ni tipos
de habitación inexistentes en lo que ve y aprueba recepción.
"""
import re
from datetime import date

from .disponibilidad import capacidad

NOMBRE = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.\- ]{0,39}$")
MOTIVOS = {"cancelacion", "cambio_fechas", "documento_recibido", "otro"}
HORAS = {"hora_checkin": "14:00", "hora_checkout": "12:00"}  # valores de demo, configurables por hotel

PLANTILLAS = {
    "confirmar_reserva": {"destino": "whatsapp", "slots": {"nombre": "nombre", "entrada": "fecha", "salida": "fecha"},
                          "texto": "Hola {nombre}, confirmamos tu reserva del {entrada} al {salida}. ¡Te esperamos!"},
    "pedir_documentos": {"destino": "whatsapp", "slots": {"nombre": "nombre"},
                         "texto": "Hola {nombre}, para agilizar tu llegada, ¿puedes enviarnos una foto de tu documento de identidad?"},
    "info_llegada": {"destino": "whatsapp", "slots": {"nombre": "nombre"},
                     "texto": "Hola {nombre}, el check-in empieza a las {hora_checkin} y el check-out termina a las {hora_checkout}. ¿A qué hora prevés llegar?"},
    "cerrar_disponibilidad": {"destino": "roomcloud", "slots": {"tipo": "tipo", "entrada": "fecha", "salida": "fecha"},
                              "texto": "Cerrar la venta de {tipo} del {entrada} al {salida} en RoomCloud"},
    "revision_humana": {"destino": "interno", "slots": {"motivo": "motivo"}, "texto": "Revisar a mano: {motivo}"},
}


def _valido(formato: str, valor: str) -> bool:
    if formato == "nombre":
        return bool(NOMBRE.match(valor))
    if formato == "fecha":
        try:
            return date.fromisoformat(valor).isoformat() == valor
        except ValueError:
            return False
    if formato == "tipo":
        return valor in capacidad()
    if formato == "motivo":
        return valor in MOTIVOS
    return False


def renderizar(plantilla: str, slots: dict) -> str:
    """Devuelve el texto final o lanza ValueError si falta una variable, sobra otra o no cumple su formato."""
    if plantilla not in PLANTILLAS:
        raise ValueError(f"Plantilla desconocida: {plantilla}")
    definicion = PLANTILLAS[plantilla]
    if set(slots) != set(definicion["slots"]):
        raise ValueError("Las variables no coinciden con la plantilla")
    for nombre, formato in definicion["slots"].items():
        if not _valido(formato, str(slots[nombre])):
            raise ValueError(f"Valor no válido para '{nombre}'")
    return definicion["texto"].format(**slots, **HORAS)
