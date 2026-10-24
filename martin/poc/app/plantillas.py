"""Plantillas cerradas: lo único que el sistema puede proponer enviar o ejecutar.

Cada variable se valida contra un formato estricto antes de rellenar la plantilla. Así un texto
malicioso que llegue en un nombre, en un correo o en un mensaje no puede colar enlaces, instrucciones,
cabeceras de correo ni tipos de habitación inexistentes en lo que ve y aprueba recepción.

Todos los formatos se comprueban con `fullmatch` y exigen que el valor sea un `str`: un `$` al final de un patrón
deja pasar un salto de línea final, y eso bastaría para colar una cabecera en un correo.
"""
import re
from datetime import date

from .disponibilidad import capacidad

NOMBRE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.\- ]{0,39}")
EMAIL = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._%+\-]{0,62}[A-Za-z0-9])?"      # parte local, sin signos en los bordes
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+"   # etiquetas del dominio
    r"[A-Za-z]{2,24}")                                          # extensión
EMAIL_MAX = 254
DOCUMENTO = re.compile(r"doc-\d{4,6}")
EXPEDIENTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]{0,39}")

# Cada motivo lleva la frase que ve recepción en la propuesta de revisión a mano.
MOTIVOS = {
    "cancelacion": "el huésped quiere cancelar o anular la reserva",
    "cambio_fechas": "el huésped pide cambiar las fechas",
    "documento_recibido": "el huésped ha enviado un documento",
    "solicitud_factura": "piden una factura y el mensaje no se enlaza con ninguna estancia",
    "solicitud_albaran": "piden un albarán y el mensaje no se enlaza con ninguna estancia",
    "envio_a_otra_direccion": "piden enviar un documento a una dirección que no consta en la estancia",
    "otro": "mensaje que el sistema no sabe clasificar",
}
HORAS = {"hora_checkin": "14:00", "hora_checkout": "12:00"}  # valores de demo, configurables por hotel

PLANTILLAS = {
    "confirmar_reserva": {"destino": "whatsapp", "slots": {"nombre": "nombre", "entrada": "fecha", "salida": "fecha"},
                          "texto": "Hola {nombre}, confirmamos tu reserva del {entrada} al {salida}. ¡Te esperamos!"},
    "pedir_documentos": {"destino": "whatsapp", "slots": {"nombre": "nombre"},
                         "texto": "Hola {nombre}, para agilizar tu llegada, ¿puedes enviarnos una foto de tu documento de identidad?"},
    "info_llegada": {"destino": "whatsapp", "slots": {"nombre": "nombre"},
                     "texto": "Hola {nombre}, el check-in empieza a las {hora_checkin} y el check-out termina a las {hora_checkout}. ¿A qué hora prevés llegar?"},
    "correo_info_llegada": {"destino": "correo", "slots": {"nombre": "nombre", "destinatario": "email"},
                            "asunto": "Horario de check-in y check-out",
                            "texto": "Hola {nombre}, el check-in empieza a las {hora_checkin} y el check-out termina a las {hora_checkout}. "
                                     "¿A qué hora prevés llegar? Un saludo, la recepción del hotel."},
    "cerrar_disponibilidad": {"destino": "roomcloud", "slots": {"tipo": "tipo", "entrada": "fecha", "salida": "fecha"},
                              "texto": "Cerrar la venta de {tipo} del {entrada} al {salida} en RoomCloud"},
    "emitir_factura": {"destino": "documentos", "slots": {"expediente": "expediente"},
                       "texto": "Emitir la factura de la estancia {expediente}"},
    "emitir_albaran": {"destino": "documentos", "slots": {"expediente": "expediente"},
                       "texto": "Emitir el albarán de la estancia {expediente}"},
    "enviar_documento": {"destino": "correo", "slots": {"documento": "documento", "destinatario": "email"},
                         "asunto": "Documento de su estancia",
                         "texto": "Enviar por correo el documento {documento} a {destinatario}"},
    "revision_humana": {"destino": "interno", "slots": {"motivo": "motivo"}, "texto": "Revisar a mano: {motivo}"},
}


def email_valido(valor) -> bool:
    """Un correo con forma estricta: sin espacios, comillas, saltos de línea ni caracteres fuera de ASCII."""
    return (isinstance(valor, str) and len(valor) <= EMAIL_MAX and ".." not in valor
            and EMAIL.fullmatch(valor) is not None)


def asunto(plantilla: str) -> str:
    """Asunto fijo de las plantillas que salen por correo (vacío para las demás)."""
    return PLANTILLAS.get(plantilla, {}).get("asunto", "")


def _valido(formato: str, valor) -> bool:
    if not isinstance(valor, str):
        return False
    if formato == "nombre":
        return NOMBRE.fullmatch(valor) is not None
    if formato == "fecha":
        try:
            return date.fromisoformat(valor).isoformat() == valor
        except ValueError:
            return False
    if formato == "tipo":
        return valor in capacidad()
    if formato == "motivo":
        return valor in MOTIVOS
    if formato == "email":
        return email_valido(valor)
    if formato == "documento":
        return DOCUMENTO.fullmatch(valor) is not None
    if formato == "expediente":
        return EXPEDIENTE.fullmatch(valor) is not None
    return False


def renderizar(plantilla: str, slots: dict) -> str:
    """Devuelve el texto final o lanza ValueError si falta una variable, sobra otra o no cumple su formato."""
    if not isinstance(plantilla, str) or plantilla not in PLANTILLAS:
        raise ValueError(f"Plantilla desconocida: {plantilla}")
    if not isinstance(slots, dict):
        raise ValueError("Las variables deben ser un objeto")
    definicion = PLANTILLAS[plantilla]
    if set(slots) != set(definicion["slots"]):
        raise ValueError("Las variables no coinciden con la plantilla")
    for nombre, formato in definicion["slots"].items():
        if not _valido(formato, slots[nombre]):
            raise ValueError(f"Valor no válido para '{nombre}'")
    valores = dict(slots)
    if "motivo" in valores:
        valores["motivo"] = MOTIVOS[valores["motivo"]]
    return definicion["texto"].format(**valores, **HORAS)
