"""Documentos: facturas y albaranes.

Versión de la base con lógica mínima pero real (ver `documentos.py`), a la que el agente back-documentos añade el PDF y la subida
de facturas ya emitidas, que aquí responden 501, sin cambiar la forma de las respuestas. Aviso fiscal: en la demo toda factura es
un borrador no fiscal con numeración de demostración.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import documentos, hub
from ..deps import get_store, http_de

router = APIRouter(prefix="/api/documentos", tags=["documentos"])

# El HTML del documento no necesita scripts ni recursos externos, así que se sirve con una política que no los admite.
CABECERAS_HTML = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "X-Content-Type-Options": "nosniff"}


# `lineas` y `receptor` se declaran como Any a propósito: así un cuerpo mal formado llega a la validación propia del módulo y
# responde con la misma lista de problemas que el resto de errores, en lugar del formato por defecto de pydantic.
class BorradorIn(BaseModel):
    tipo: str
    expediente_id: str
    lineas: Any = None


class EditarIn(BaseModel):
    lineas: Any = None
    receptor: Any = None


class EmitirIn(BaseModel):
    actor: str = "Recepción"


class EnviarIn(BaseModel):
    actor: str = "Recepción"
    destinatario: str | None = None
    confirmar_destinatario_nuevo: bool = False


class SubirIn(BaseModel):
    tipo: str = "factura"
    expediente_id: str
    numero: str
    nombre_archivo: str
    contenido_b64: str


@router.get("")
def listar_documentos(tipo: str | None = None, estado: str | None = None, expediente: str | None = None, store=Depends(get_store)):
    if tipo and tipo not in documentos.TIPOS:
        raise HTTPException(422, {"problemas": ["El tipo tiene que ser factura o albaran"]})
    if estado and estado not in documentos.ESTADOS:
        raise HTTPException(422, {"problemas": [f"El estado tiene que ser uno de: {', '.join(documentos.ESTADOS)}"]})
    return {"documentos": [documentos.resumen(d) for d in documentos.listar(store, tipo or None, estado or None, expediente or None)]}


@router.post("/borrador")
def crear_borrador(datos: BorradorIn, store=Depends(get_store)):
    try:
        doc = documentos.crear_borrador(store, datos.tipo, datos.expediente_id, datos.lineas)
    except hub.ErrorNegocio as error:
        raise http_de(error)
    store.guardar()
    return doc


@router.post("/subir")
def subir_documento(datos: SubirIn):
    raise HTTPException(501, "La subida de una factura ya emitida todavía no está disponible en esta versión del hub")


@router.get("/{doc_id}")
def ver_documento(doc_id: str, store=Depends(get_store)):
    try:
        return documentos.obtener(store, doc_id)
    except hub.ErrorNegocio as error:
        raise http_de(error)


@router.put("/{doc_id}")
def editar_documento(doc_id: str, datos: EditarIn, store=Depends(get_store)):
    try:
        doc = documentos.editar(store, doc_id, datos.lineas, datos.receptor)
    except hub.ErrorNegocio as error:
        raise http_de(error)
    store.guardar()
    return doc


@router.post("/{doc_id}/emitir")
def emitir_documento(doc_id: str, datos: EmitirIn, store=Depends(get_store)):
    try:
        doc = documentos.emitir(store, doc_id, documentos.limpiar_actor(datos.actor))
    except hub.ErrorNegocio as error:
        raise http_de(error)
    store.guardar()
    return doc


@router.get("/{doc_id}/html")
def documento_html(doc_id: str, store=Depends(get_store)):
    try:
        doc = documentos.obtener(store, doc_id)
    except hub.ErrorNegocio as error:
        raise http_de(error)
    return HTMLResponse(documentos.html(doc), headers=CABECERAS_HTML)


@router.get("/{doc_id}/pdf")
def documento_pdf(doc_id: str, store=Depends(get_store)):
    try:
        documentos.obtener(store, doc_id)
    except hub.ErrorNegocio as error:
        raise http_de(error)
    raise HTTPException(501, "La descarga en PDF todavía no está disponible en esta versión del hub: usa la vista HTML imprimible")


@router.post("/{doc_id}/enviar")
def enviar_documento(doc_id: str, datos: EnviarIn, store=Depends(get_store)):
    try:
        doc = documentos.enviar(store, doc_id, documentos.limpiar_actor(datos.actor), datos.destinatario,
                                datos.confirmar_destinatario_nuevo)
    except hub.ErrorNegocio as error:
        raise http_de(error)
    store.guardar()
    return doc
