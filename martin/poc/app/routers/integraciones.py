"""Integraciones: qué está conectado, qué es simulado y qué límites tiene cada pieza.

Versión de la base en la que el modo de cada integración sale de `hub.MODOS` y de la variable `OPENAI_API_KEY`, igual que en
`/api/estado`, y en la que el agente back-hoy puede afinar los textos y los estados sin cambiar la forma de la respuesta.
"""
import os

from fastapi import APIRouter, Depends

from .. import hub
from ..deps import get_store

router = APIRouter(prefix="/api", tags=["integraciones"])
EVENTOS_ROOMCLOUD = {"reserva_nueva", "reserva_modificada", "reserva_cancelada"}
MENSAJES = {"mensaje_entrante", "mensaje_saliente_simulado", "correo_saliente_simulado"}


def _ultima(store, fuente: str, tipos: set[str] | None = None) -> str | None:
    marcas = [e["ts"] for e in store.db["eventos"] if e["fuente"] == fuente and (tipos is None or e["tipo"] in tipos)]
    return max(marcas) if marcas else None


def _ultimo_parte(store) -> str | None:
    marcas = [e["parte"]["enviado_el"] for e in store.db["expedientes"].values() if e.get("parte")]
    return max(marcas) if marcas else None


def _integracion(id_: str, nombre: str, tipo: str, modo: str, estado: str, resumen: str, ultima_sync: str | None,
                 capacidades: list[str], limites: list[str], acciones: list[dict] | None = None) -> dict:
    return {"id": id_, "nombre": nombre, "tipo": tipo, "modo": modo, "estado": estado, "resumen": resumen,
            "ultima_sync": ultima_sync, "capacidades": capacidades, "limites": limites, "acciones": acciones or []}


def calcular(store) -> dict:
    con_clave = bool(os.environ.get("OPENAI_API_KEY"))
    modo_llm = "real" if con_clave else "simulado"
    sync_roomcloud = _ultima(store, "roomcloud", EVENTOS_ROOMCLOUD)
    sync_ofihotel = _ultima(store, "ofihotel", {"instantanea_lectura"})
    entrantes = [m for m in (_ultima(store, canal, {"mensaje_entrante"}) for canal in ("whatsapp", "correo")) if m]
    integraciones = [
        _integracion(
            "roomcloud", "RoomCloud", "Channel manager", hub.MODOS["roomcloud"], "ok" if sync_roomcloud else "aviso",
            "XML grabado y reconstruido" if sync_roomcloud else "Todavía no se ha leído ninguna reserva", sync_roomcloud,
            ["Leer reservas nuevas, modificadas y canceladas", "Descartar los datos de tarjeta al leer",
             "Proponer el cierre de ventas cuando un tipo de habitación se llena"],
            ["El XML es una reconstrucción a partir de la investigación, no una respuesta real de RoomCloud",
             "El cierre de disponibilidad es simulado y siempre pasa por aprobación",
             "Si OfiChannel ya sube la disponibilidad a RoomCloud, este sistema no puede escribir también"],
            [{"id": "sincronizar", "etiqueta": "Leer reservas", "metodo": "POST", "ruta": "/api/sync/roomcloud"}]),
        _integracion(
            "ofihotel", "OfiHotel", "Programa de gestión del hotel", hub.MODOS["ofihotel"], "ok" if sync_ofihotel else "aviso",
            "Lectura de solo lectura sobre una instantánea de ejemplo" if sync_ofihotel else "Todavía no se ha leído OfiHotel",
            sync_ofihotel,
            ["Leer las ocupaciones en solo lectura", "Preparar los datos del huésped para copiarlos a OfiHotel a mano"],
            ["Todavía no sabemos cómo se leerá OfiHotel de verdad: SQL en solo lectura, una exportación o la pantalla",
             "Nunca se escribe en OfiHotel y no tiene API pública, así que el alta del huésped es una copia asistida",
             "Alguien sigue tecleando en OfiHotel y el sistema solo ve lo que entra por la lectura"],
            [{"id": "sincronizar", "etiqueta": "Leer OfiHotel", "metodo": "POST", "ruta": "/api/sync/ofihotel"}]),
        _integracion(
            "whatsapp", "WhatsApp", "Mensajería con los huéspedes", hub.MODOS["whatsapp"], "ok",
            "Los mensajes entran con la forma del webhook de Meta, sin conexión real", _ultima(store, "whatsapp", MENSAJES),
            ["Recibir mensajes con la forma del webhook de Meta", "Enlazar cada mensaje con su estancia por el teléfono",
             "Proponer respuestas con plantillas cerradas"],
            ["La API oficial exige un número de empresa, verificación en Meta y plantillas aprobadas",
             "El receptor no hace el handshake de verificación ni comprueba la firma X-Hub-Signature-256",
             "Nada sale sin que recepción lo apruebe"]),
        _integracion(
            "correo", "Correo", "Correo electrónico (Gmail)", hub.MODOS["correo"], "ok",
            "Los correos entran con la forma de la API de Gmail y los envíos se guardan en la bandeja de salida",
            _ultima(store, "correo", MENSAJES),
            ["Recibir correos con la forma de un mensaje de Gmail y pasarlos por el lector",
             "Responder con plantillas cerradas", "Enviar facturas y albaranes como adjunto"],
            ["No hay conexión con ninguna cuenta: conectar Gmail exige el consentimiento OAuth del hotel",
             "Los envíos son simulados y se quedan en este equipo",
             "Un documento solo se envía sin confirmación a un correo conocido de la estancia"]),
        _integracion(
            "ses", "SES.Hospedajes", "Registro de viajeros", hub.MODOS["ses"], "ok",
            "XML orientativo y justificante falso, sin conexión con el Ministerio", _ultimo_parte(store),
            ["Construir el parte de viajeros con los datos del check-in", "Controlar el plazo de 24 horas desde el check-in"],
            ["La estructura sigue la lista orientativa del RD 933/2021 y no está validada contra el XSD oficial",
             "El envío es simulado y el justificante empieza por SIM-",
             "El servicio real exige credenciales técnicas propias del hotel"]),
        _integracion(
            "lector", "Lector de mensajes", "Clasificador de intenciones", modo_llm, "ok",
            "Clasifica con un modelo de OpenAI, sin herramientas" if con_clave
            else "Clasifica con reglas de palabras clave en español, inglés y francés",
            max(entrantes) if entrantes else None,
            ["Clasificar cada mensaje en una intención de una lista cerrada", "Detectar las peticiones de factura y de albarán"],
            ["No tiene herramientas ni toca expedientes: solo devuelve una intención",
             "Con reglas solo acierta con las palabras clave previstas"]),
        _integracion(
            "chat", "Asistente", "Chat con la información del hotel", modo_llm, "ok",
            "Responde con OpenAI y herramientas de lectura" if con_clave else "Responde con reglas fijas y lo indica en pantalla",
            None,
            ["Responder sobre llegadas, ocupación, partes, mensajes y documentos", "Mostrar bloques con datos reales del hotel",
             "Proponer acciones con plantillas, siempre pendientes de aprobación"],
            ["Solo puede leer y proponer: nada se ejecuta sin que recepción lo apruebe",
             "Sin OPENAI_API_KEY solo contesta a las preguntas que reconocen sus reglas"]),
    ]
    return {"reloj": store.ahora().isoformat(timespec="minutes"), "integraciones": integraciones,
            "avisos_globales": ["Todo lo marcado como simulado no sale de este equipo.",
                                "Las facturas que genera esta demo son documentos de demostración sin validez fiscal."]}


@router.get("/integraciones")
def integraciones(store=Depends(get_store)):
    return calcular(store)
