"""Mensajes: conversaciones de WhatsApp y de correo, propuestas desde una conversación y correo simulado.

Versión de la base con lógica mínima pero real: las conversaciones salen de `db["eventos"]` (ver `conversaciones.py`).
El agente back-mensajes puede sustituir lo que haga falta sin cambiar la forma de las respuestas.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import conversaciones, hub, lector, plantillas
from ..adapters import correo
from ..deps import get_store, http_de

router = APIRouter(prefix="/api", tags=["mensajes"])
CANALES = ("todos", "whatsapp", "correo")


@router.get("/mensajes/conversaciones")
def listar_conversaciones(canal: str = "todos", store=Depends(get_store)):
    if canal not in CANALES:
        raise HTTPException(422, {"problemas": ["El canal tiene que ser todos, whatsapp o correo"]})
    return {"conversaciones": conversaciones.listar(store, canal)}


@router.get("/mensajes/conversaciones/{conv_id}")
def detalle_conversacion(conv_id: str, store=Depends(get_store)):
    datos = conversaciones.detalle(store, conv_id)
    if not datos:
        raise HTTPException(404, "Conversación no encontrada")
    return datos


class ProponerIn(BaseModel):
    plantilla: str
    slots: dict = {}


@router.post("/mensajes/conversaciones/{conv_id}/proponer")
def proponer(conv_id: str, datos: ProponerIn, store=Depends(get_store)):
    """Crea una propuesta pendiente desde la conversación. Nunca envía nada: lo decide recepción al aprobarla.

    Si la plantilla pide un `destinatario` (correo) y la conversación es de correo, o pide una `expediente` y la
    conversación está enlazada con una estancia, se rellena solo cuando no viene en `slots`.
    """
    detalle = conversaciones.detalle(store, conv_id)
    if not detalle:
        raise HTTPException(404, "Conversación no encontrada")
    conv = detalle["conversacion"]
    definicion = plantillas.PLANTILLAS.get(datos.plantilla)
    if not definicion:
        raise HTTPException(422, {"problemas": [f"Plantilla desconocida: {datos.plantilla}"]})
    destino = definicion["destino"]
    if destino == "roomcloud" or (destino == "whatsapp" and conv["canal"] != "whatsapp"):
        raise HTTPException(422, {"problemas": [f"La plantilla {datos.plantilla} no se puede proponer desde una conversación de {conv['canal']}"]})
    slots = dict(datos.slots)
    if "destinatario" in definicion["slots"] and "destinatario" not in slots and conv["canal"] == "correo":
        slots["destinatario"] = conv["contacto"]
    if "expediente" in definicion["slots"] and "expediente" not in slots and conv["expediente_id"]:
        slots["expediente"] = conv["expediente_id"]
    prop = hub.crear_propuesta(store, datos.plantilla, slots, None, conv["expediente_id"],
                               conv["contacto"] if destino == "whatsapp" else "", "recepción")
    if not prop:
        raise HTTPException(422, {"problemas": hub.problemas_de_propuesta(store, datos.plantilla, slots) or ["La propuesta no es válida"]})
    store.guardar()
    return prop


class CorreoIn(BaseModel):
    de: str
    nombre: str = ""
    asunto: str = ""
    cuerpo: str = ""


def procesar_correo(store, mensaje: dict) -> list[dict]:
    """Un correo con la forma de Gmail pasa por el mismo camino que un WhatsApp: evento, lector y, como mucho, una propuesta."""
    m = correo.parsear(mensaje)
    if not plantillas.email_valido(m["de"]):
        raise hub.ErrorNegocio("El remitente del correo no es una dirección válida", 422)
    exp = hub.buscar_por_correo(store.db, m["de"])
    ev = hub.registrar_evento(store, "correo", "mensaje_entrante", m["nombre"] or m["de"], m["texto"], exp["id"] if exp else None,
                              {"correo": m["de"].lower(), "asunto": m["asunto"], "gmail_id": m["id"], "thread_id": m["thread_id"]})
    ev["datos"]["interpretacion"] = lector.interpretar(f"{m['asunto']}\n{m['texto']}".strip())
    prop = hub.proponer_para_mensaje(store, ev, exp, m["nombre"], canal="correo", contacto=m["de"])
    store.guardar()
    return [{"evento": ev["id"], "propuesta": prop["id"] if prop else None}]


@router.post("/correo/simular")
def simular_correo(datos: CorreoIn, store=Depends(get_store)):
    try:
        mensaje = correo.construir_mensaje_gmail(datos.de, datos.nombre, datos.asunto, datos.cuerpo, store.ahora())
        return procesar_correo(store, mensaje)
    except ValueError as error:
        raise HTTPException(422, {"problemas": [str(error)]})
    except hub.ErrorNegocio as error:
        raise http_de(error)
