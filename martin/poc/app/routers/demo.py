"""Datos de demostración: `POST /api/demo/semilla?nivel=vacia|basica|completa`.

La semilla `completa` deja siempre el mismo estado con el reloj en 2026-10-24T09:00, para que todos los agentes
capturen pantallas comparables. El estado se construye llamando a las mismas funciones que usa la API (sincronizar,
guardar el huésped, confirmar el parte, simular un mensaje...), así que pasa por las mismas validaciones y deja el mismo
rastro en el registro y en los eventos que dejaría una persona. Los ids salen de un contador que se reinicia con el
almacén, y el orden de los pasos es fijo, por eso son siempre los mismos.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from .. import documentos
from ..adapters.ocr import leer_documento
from ..deps import get_store
from ..store import INICIO_DEMO

router = APIRouter(prefix="/api/demo", tags=["demo"])
NIVELES = ("vacia", "basica", "completa")
RELOJ_DEMO = datetime.fromisoformat("2026-10-24T09:00:00")

ANA = "1-BK-4471920"
MARCOS = "0-WEB-90112"
CLAIRE = "2-EX-7730021"
TELEFONO_ANA = "34600111222"
CORREO_CLAIRE = "claire.dubois@example.com"
EMPRESA_ANA = {"razon_social": "Atlántico Consultores SL", "cif": "B15000000", "direccion": "Rúa Real 1, A Coruña",
               "email": "facturas@atlantico.example"}
HUESPED_MARCOS = {
    "nombre": "Marcos", "apellido1": "Vilas", "apellido2": "Souto", "sexo": "H", "fecha_nacimiento": "1990-03-12",
    "nacionalidad": "ESP", "tipo_documento": "NIF", "numero_documento": "87654321X", "numero_soporte": "CAA654321",
    "direccion": "Rúa Nova 8, 1º", "localidad": "A Coruña", "codigo_postal": "15001", "pais": "ESP",
    "telefono": "+34611222333", "email": "marcos.vilas@example.com",
}
LINEAS_ALBARAN_ANA = [
    {"concepto": "Alojamiento DBL-STD (noches)", "cantidad": 2, "precio_unitario": None, "iva_pct": None},
    {"concepto": "Desayuno buffet", "cantidad": 2, "precio_unitario": None, "iva_pct": None},
]


def _ajustar_reloj(store) -> None:
    """Pone el reloj de la demo en las 09:00 del 24/10 si el origen configurado (DEMO_START) difiere en horas enteras."""
    horas = (RELOJ_DEMO - INICIO_DEMO).total_seconds() / 3600
    store.db["reloj_h"] = int(horas) if horas == int(horas) else 0


def _leer_reservas(principal) -> None:
    principal.sincronizar()
    principal.sincronizar_ofihotel()


def _checkin_de_ana(principal) -> None:
    lectura = leer_documento(None)  # sin imagen devuelve siempre el documento de muestra, haya clave o no
    huesped = principal.HuespedIn(**{**lectura["campos"], "telefono": "+34600111222", "email": "ana.pereira@example.com"})
    principal.guardar_huesped(ANA, huesped)
    principal.guardar_pago(ANA, principal.PagoIn(medio="tarjeta", empresa=principal.EmpresaIn(**EMPRESA_ANA)))
    principal.confirmar_parte(ANA, principal.ActorIn(actor="Flor"))


def _checkin_de_marcos(principal) -> None:
    principal.guardar_huesped(MARCOS, principal.HuespedIn(**HUESPED_MARCOS))
    principal.guardar_pago(MARCOS, principal.PagoIn(medio="transferencia"))  # el parte queda pendiente a propósito


def _mensajes(principal, store) -> None:
    from . import mensajes
    principal.simular_whatsapp(principal.WhatsappIn(wa_id=TELEFONO_ANA, nombre="Ana", texto="Hola, ¿a qué hora es el check-in?"))
    mensajes.simular_correo(mensajes.CorreoIn(
        de=CORREO_CLAIRE, nombre="Claire Dubois", asunto="Factura de mi estancia",
        cuerpo="Buenos días, ¿podrían enviarme la factura de mi estancia? La necesito para presentarla en mi empresa. Gracias."), store)


def _documentos(store) -> None:
    factura = documentos.crear_borrador(store, "factura", ANA, actor="Sistema")
    documentos.emitir(store, factura["id"], "Flor")
    documentos.crear_borrador(store, "albaran", ANA, LINEAS_ALBARAN_ANA, actor="Flor")


def sembrar_estado(store, nivel: str) -> None:
    """Deja `store` en el estado del nivel pedido. No guarda: lo hace quien llama."""
    from .. import main as principal
    if store is not principal.store:
        raise RuntimeError("La semilla solo puede aplicarse al almacén de la aplicación")
    store.reiniciar()
    _ajustar_reloj(store)
    if nivel == "vacia":
        return
    _leer_reservas(principal)
    if nivel == "basica":
        return
    _mensajes(principal, store)  # el mensaje de Ana llega antes de su check-in: así se enlaza por el teléfono de la reserva
    _checkin_de_ana(principal)
    _checkin_de_marcos(principal)
    _documentos(store)


@router.post("/semilla")
def sembrar(nivel: str = "completa", store=Depends(get_store)):
    if nivel not in NIVELES:
        raise HTTPException(422, {"problemas": [f"El nivel tiene que ser uno de: {', '.join(NIVELES)}"]})
    with store.lock:
        sembrar_estado(store, nivel)
        store.guardar()
        db = store.db
        return {"nivel": nivel, "reloj": store.ahora().isoformat(timespec="minutes"), "expedientes": len(db["expedientes"]),
                "eventos": len(db["eventos"]), "propuestas": len(db["propuestas"]),
                "propuestas_pendientes": sum(p["estado"] == "pendiente" for p in db["propuestas"]),
                "documentos": len(db["documentos"])}
