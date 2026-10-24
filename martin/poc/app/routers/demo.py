"""Datos de demostración: `POST /api/demo/semilla?nivel=vacia|basica|completa|demo`.

La semilla `completa` deja siempre el mismo estado con el reloj en 2026-10-24T09:00, para que todos los agentes
capturen pantallas comparables. El estado se construye llamando a las mismas funciones que usa la API (sincronizar,
guardar el huésped, confirmar el parte, simular un mensaje...), así que pasa por las mismas validaciones y deja el mismo
rastro en el registro y en los eventos que dejaría una persona. Los ids salen de un contador que se reinicia con el
almacén, y el orden de los pasos es fijo, por eso son siempre los mismos.

El nivel `demo` es `completa` más un relleno determinista (`demo_datos.py`) para que las pantallas no se vean vacías. Con la variable de
entorno `HOTEL_AUTOSEMILLA=demo` (o cualquier otro nivel) la aplicación siembra ese nivel al arrancar, pero solo si el almacén está vacío.
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import comunicaciones, disponibilidad, documentos, hub
from ..deps import get_store
from ..store import INICIO_DEMO

router = APIRouter(prefix="/api/demo", tags=["demo"])
NIVELES = ("vacia", "basica", "completa", "demo")
RELOJ_DEMO = datetime.fromisoformat("2026-10-24T09:00:00")

ANA = "1-BK-4471920"
MARCOS = "0-WEB-90112"
CLAIRE = "2-EX-7730021"
TELEFONO_ANA = "34600111222"
CORREO_CLAIRE = "claire.dubois@example.com"
EMPRESA_ANA = {"razon_social": "Atlántico Consultores SL", "cif": "B15000000", "direccion": "Rúa Real 1, A Coruña",
               "email": "facturas@atlantico.example"}
HUESPED_ANA = {
    "nombre": "Ana", "apellido1": "Pereira", "apellido2": "Lage", "sexo": "M", "fecha_nacimiento": "1988-04-17",
    "nacionalidad": "ESP", "tipo_documento": "NIF", "numero_documento": "12345678Z", "numero_soporte": "BAB123456",
    "direccion": "Rúa do Orzán 12, 3º B", "localidad": "A Coruña", "codigo_postal": "15003", "pais": "ESP",
    "telefono": "+34600111222", "email": "ana.pereira@example.com",
}
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


# Mensajes que llegan por la mañana del 24/10. Pasan por el mismo `registrar` que uno escrito en directo: se entienden con las reglas, se
# contrastan con RoomCloud, OfiHotel y las reservas físicas, y esperan a que recepción confirme la respuesta por el canal de origen.
COMUNICACIONES_DEMO = [
    ("correo", "Sophie Martin", "sophie.martin@example.fr", "Demande de chambre du 24 au 27 octobre",
     "Bonjour, avez-vous une chambre double de libre du 24 au 27 octobre pour 2 personnes ? Merci d'avance.", "2026-10-24T07:58"),
    ("correo", "Carlos Meijide", "carlos.meijide@meijide-consulting.example", "Reserva para un evento de empresa",
     "Buenos días. Necesitamos 3 habitaciones dobles del 1 al 3 de noviembre para un equipo de 6 personas. ¿Tenéis disponibilidad?",
     "2026-10-24T08:31"),
    ("whatsapp", "Ana Pereira", TELEFONO_ANA, "", "Hola, ¿a qué hora es el check-in?", "2026-10-24T08:40"),
    ("whatsapp", "Marta Souto", "34622334455", "", "Buenas, necesito una individual para esta noche, ¿hay algo?", "2026-10-24T08:49"),
    ("whatsapp", "Lucía Fernández", "34655123123", "", "Hola, ¿tenéis una doble libre del 28 al 30 de octubre? Somos 2 personas.", "2026-10-24T08:52"),
    ("correo", "Pablo Rey", "pablo.rey@example.com", "Habitación individual esta noche",
     "Buenas, ¿tenéis una individual libre esta noche? Llegaría sobre las 19:00.", "2026-10-24T08:57"),
]
# Dos desajustes entre RoomCloud y OfiHotel para enseñar la detección de conflictos: Dubois sale un día antes en OfiHotel y Otero sigue
# viva en OfiHotel aunque RoomCloud la canceló (por la regla de prioridad, su fila vieja no ocupa habitación).
OFIHOTEL_OTERO = {"id_ofihotel": "OH-10240", "huesped": "Otero", "habitacion": "112", "tipo": "SGL-STD", "entrada": "2026-10-24",
                  "salida": "2026-10-25", "estado": "reservada", "numero_externo": "BK-4488003-1", "ref_externa": "1-BK-4488003", "personas": 1}


class ReservaRoomcloudIn(BaseModel):
    tipo: str = "SGL-STD"
    desde: str | None = None
    hasta: str | None = None
    nombre: str = "Reserva de Booking"
    personas: int = 1


def _ajustar_reloj(store) -> None:
    """Pone el reloj de la demo en las 09:00 del 24/10 si el origen configurado (DEMO_START) difiere en horas enteras."""
    horas = (RELOJ_DEMO - INICIO_DEMO).total_seconds() / 3600
    store.db["reloj_h"] = int(horas) if horas == int(horas) else 0


def _desajustes_de_ofihotel(store) -> None:
    lectura = store.db.get("ofihotel") or {}
    for e in lectura.get("estancias", []):
        if e.get("ref_externa") == CLAIRE:
            e["salida"] = "2026-10-26"
    lectura.setdefault("estancias", []).append(dict(OFIHOTEL_OTERO))
    for o in lectura.get("ocupaciones", []):
        if o.get("ref_externa") == CLAIRE:
            o["hasta"] = "2026-10-26"
    lectura.setdefault("ocupaciones", []).append({"habitacion": "112", "tipo": "SGL-STD", "desde": "2026-10-24", "hasta": "2026-10-25",
                                                    "huesped": "Otero", "ref_externa": "1-BK-4488003"})


def _leer_reservas(principal) -> None:
    principal.sincronizar()
    principal.sincronizar_ofihotel()


def _comunicaciones(store) -> None:
    for canal, nombre, contacto, asunto, texto, ts in COMUNICACIONES_DEMO:
        comunicaciones.registrar(store, canal, nombre, contacto, texto, asunto, ts=ts)
    for com in store.db["comunicaciones"]:
        comunicaciones.vista(store, com)  # fija el veredicto de partida: los avisos se disparan por cambios posteriores, no por el orden de la semilla


def _checkin_de_ana(principal) -> None:
    principal.guardar_huesped(ANA, principal.HuespedIn(**HUESPED_ANA))
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
    _desajustes_de_ofihotel(store)
    _comunicaciones(store)
    if nivel == "demo":
        from .. import demo_datos
        demo_datos.rellenar(principal, store)


def _autosembrar() -> None:
    """Arranque con `HOTEL_AUTOSEMILLA=<nivel>`: siembra ese nivel solo si el almacén está vacío. Sin la variable no hace nada."""
    nivel = os.environ.get("HOTEL_AUTOSEMILLA", "").strip().lower()
    if not nivel:
        return
    if nivel not in NIVELES:
        raise RuntimeError(f"HOTEL_AUTOSEMILLA tiene que ser uno de: {', '.join(NIVELES)}")
    store = get_store()
    with store.lock:
        if store.db["expedientes"] or store.db.get("comunicaciones") or store.db["eventos"]:
            return
        sembrar_estado(store, nivel)
        store.guardar()


router.on_startup.append(_autosembrar)


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


@router.post("/reserva-roomcloud")
def reserva_roomcloud(datos: ReservaRoomcloudIn, store=Depends(get_store)):
    """Control de la demo: entra una reserva nueva de Booking por RoomCloud (prioridad 1) y las peticiones que competían por el hueco lo notan."""
    from .. import main as principal
    hoy = store.ahora().date()
    desde, hasta = datos.desde or hoy.isoformat(), datos.hasta or (hoy + timedelta(days=1)).isoformat()
    try:
        entrada, salida = datetime.fromisoformat(desde), datetime.fromisoformat(hasta)
    except ValueError:
        raise HTTPException(422, {"problemas": ["Las fechas deben tener formato AAAA-MM-DD"]})
    if salida <= entrada:
        raise HTTPException(422, {"problemas": ["La salida debe ser posterior a la llegada"]})
    if datos.tipo not in disponibilidad.capacidad():
        raise HTTPException(422, {"problemas": [f"Tipo de habitación desconocido: {datos.tipo}"]})
    nombre = (datos.nombre.strip() or "Reserva de Booking").split()
    numero = store.siguiente_id("rc").split("-")[1]
    r = {"portal_id": "1", "id_canal": f"BK-91{numero}", "dlm": store.ahora().isoformat(timespec="minutes"), "estado_rc": "4",
         "checkin": desde, "checkout": hasta, "nombre": nombre[0], "apellidos": " ".join(nombre[1:]), "telefono": "", "email": "", "pais": "",
         "importe": "", "medio_pago": "TARJETA", "notas": "",
         "habitaciones": [{"tipo": datos.tipo, "tarifa": "BAR", "adultos": str(max(1, datos.personas)), "ninos": "0"}]}
    exp = principal.nuevo_expediente(r)
    store.db["expedientes"][exp["id"]] = exp
    hub.registrar_evento(store, "roomcloud", "reserva_nueva", " ".join(nombre), f"Reserva {exp['id']}: {desde} a {hasta}", exp["id"])
    hub.revisar_ocupacion(store)
    store.guardar()
    return {"id": exp["id"], "tipo": datos.tipo, "desde": desde, "hasta": hasta}
