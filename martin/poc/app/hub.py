"""Lógica del hub: eventos, propuestas con aprobación y comprobación de ocupación.

Todo lo que entra se normaliza como evento. Lo único que el sistema puede hacer hacia fuera son
propuestas basadas en plantillas cerradas, y nada sale hasta que recepción las aprueba.
"""
import re
from datetime import date, timedelta

from . import disponibilidad, plantillas

# Modo de las integraciones que no dependen de ninguna clave. Lo usan /api/integraciones, /api/estado y las
# conversaciones, para que todos cuenten lo mismo.
MODOS = {"roomcloud": "simulado", "ofihotel": "supuesto", "whatsapp": "simulado", "correo": "simulado", "ses": "simulado"}
ESTADOS_ENVIABLES = ("emitido", "enviado")
PROBLEMA_DESTINATARIO = "El destinatario no es un correo conocido de la estancia del documento: lo revisa una persona"


class ErrorNegocio(Exception):
    """Error previsto de una regla de negocio. `codigo` es el estado HTTP que le corresponde (404, 409 o 422)."""

    def __init__(self, mensaje: str, codigo: int = 422, problemas: list[str] | None = None, extra: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.problemas = list(problemas) if problemas else [mensaje]
        self.extra = extra or {}


def registrar_evento(store, fuente: str, tipo: str, remitente: str = "", contenido: str = "",
                     expediente_id: str | None = None, datos: dict | None = None) -> dict:
    ev = {"id": store.siguiente_id("ev"), "ts": store.ahora().isoformat(timespec="minutes"), "fuente": fuente,
          "tipo": tipo, "remitente": remitente, "contenido": contenido, "expediente_id": expediente_id,
          "datos": datos or {}, "estado": "nuevo"}
    store.db["eventos"].append(ev)
    return ev


def buscar_por_telefono(db: dict, telefono: str) -> dict | None:
    cola = re.sub(r"\D", "", telefono)[-9:]
    if len(cola) < 9:
        return None
    for exp in db["expedientes"].values():
        for candidato in (exp["reserva"].get("telefono", ""), exp["huesped"].get("telefono", "")):
            if re.sub(r"\D", "", candidato)[-9:] == cola:
                return exp
    return None


def _correo(valor) -> str:
    return valor.strip().lower() if isinstance(valor, str) else ""


def correos_de_expediente(exp: dict | None) -> set[str]:
    """Correos conocidos de una estancia, en minúsculas: el de la reserva, el del huésped y el de la empresa."""
    if not exp:
        return set()
    candidatos = (exp.get("reserva", {}).get("email"), exp.get("huesped", {}).get("email"), exp.get("empresa", {}).get("email"))
    return {c for c in map(_correo, candidatos) if c}


def correos_conocidos(db: dict, documento: dict) -> set[str]:
    """Correos a los que se puede enviar un documento sin pedir confirmación: los de su estancia y el de su receptor."""
    conocidos = correos_de_expediente(db["expedientes"].get(documento.get("expediente_id") or ""))
    receptor = _correo(documento.get("receptor", {}).get("email"))
    return conocidos | ({receptor} if receptor else set())


def buscar_por_correo(db: dict, correo: str) -> dict | None:
    """Estancia cuyo correo coincide con `correo` (sin mirar mayúsculas), prefiriendo las que no están canceladas."""
    objetivo = _correo(correo)
    if not objetivo:
        return None
    encontradas = [exp for exp in db["expedientes"].values() if objetivo in correos_de_expediente(exp)]
    return next((e for e in encontradas if e["estado"] != "cancelada"), encontradas[0] if encontradas else None)


def _texto(slots: dict, clave: str) -> str:
    valor = slots.get(clave)
    return valor if isinstance(valor, str) else ""


def problemas_contexto(store, plantilla: str, slots: dict) -> list[str]:
    """Comprueba que lo que menciona la plantilla existe y que enviar un documento no abre una fuga de datos.

    Devuelve la lista de problemas, vacía si el contexto es válido. Las plantillas sin reglas propias son válidas.
    """
    if not isinstance(slots, dict):
        return ["Las variables deben ser un objeto"]
    db = store.db
    if plantilla in ("emitir_factura", "emitir_albaran"):
        if _texto(slots, "expediente") not in db["expedientes"]:
            return [f"La estancia {_texto(slots, 'expediente') or '(sin indicar)'} no existe"]
    elif plantilla == "enviar_documento":
        doc = db["documentos"].get(_texto(slots, "documento"))
        if not doc:
            return [f"El documento {_texto(slots, 'documento') or '(sin indicar)'} no existe"]
        if doc["estado"] not in ESTADOS_ENVIABLES:
            return ["El documento no está emitido: solo se envían documentos emitidos"]
        if _correo(_texto(slots, "destinatario")) not in correos_conocidos(db, doc):
            return [PROBLEMA_DESTINATARIO]
    return []


def contexto_valido(store, plantilla: str, slots: dict) -> bool:
    return not problemas_contexto(store, plantilla, slots)


def problemas_de_propuesta(store, plantilla: str, slots: dict) -> list[str]:
    """Por qué no se puede crear (o aprobar) una propuesta: el fallo de las variables o los del contexto. Vacía si es válida."""
    try:
        plantillas.renderizar(plantilla, slots)
    except ValueError as error:
        return [str(error)]
    return problemas_contexto(store, plantilla, slots)


def crear_propuesta(store, plantilla: str, slots: dict, origen_evento: str | None = None,
                    expediente_id: str | None = None, destinatario: str = "", origen: str = "sistema") -> dict | None:
    """Valida las variables y el contexto y crea una propuesta pendiente. Devuelve None si no son válidos."""
    try:
        texto = plantillas.renderizar(plantilla, slots)
    except ValueError:
        return None
    if problemas_contexto(store, plantilla, slots):
        return None
    destino = plantillas.PLANTILLAS[plantilla]["destino"]
    if destino == "correo":
        destinatario = slots["destinatario"]  # en un correo el destinatario es el que se validó, no otro
    elif destino in ("documentos", "roomcloud"):
        destinatario = ""  # emitir un documento o cerrar ventas no envía nada a nadie
    if expediente_id is None:
        if "expediente" in slots:
            expediente_id = slots["expediente"]
        elif "documento" in slots:
            expediente_id = store.db["documentos"][slots["documento"]].get("expediente_id")
    prop = {"id": store.siguiente_id("pr"), "ts": store.ahora().isoformat(timespec="minutes"), "plantilla": plantilla,
            "destino": destino, "slots": slots, "texto": texto,
            "expediente_id": expediente_id, "destinatario": destinatario, "origen_evento": origen_evento,
            "origen": origen, "estado": "pendiente", "decidido_por": None, "hora_decision": None}
    store.db["propuestas"].append(prop)
    return prop


def derivar_a_revision(store, motivo: str, origen_evento: str | None = None, expediente_id: str | None = None,
                       destinatario: str = "", origen: str = "sistema") -> dict | None:
    """Crea la propuesta de revisión a mano con la que acaba un caso que el sistema no debe resolver solo."""
    return crear_propuesta(store, "revision_humana", {"motivo": motivo}, origen_evento, expediente_id, destinatario, origen)


def proponer_para_mensaje(store, evento: dict, expediente: dict | None, nombre_perfil: str, wa_id: str = "",
                          *, canal: str = "whatsapp", contacto: str | None = None) -> dict | None:
    """Enrutador determinista: de la intención del lector sale como mucho una propuesta con plantilla.

    `contacto` es con quien se habla por el canal: el wa_id en WhatsApp y la dirección del remitente en un correo.
    Por defecto (canal whatsapp y `wa_id` en quinto lugar) se comporta como siempre.
    """
    contacto = contacto if contacto is not None else wa_id
    intencion = evento["datos"]["interpretacion"]["intencion"]
    nombre = ((expediente["reserva"]["nombre"] if expediente else nombre_perfil) or "").strip()
    exp_id = expediente["id"] if expediente else None
    if intencion == "pregunta_checkin_horario":
        if canal == "correo":
            prop = crear_propuesta(store, "correo_info_llegada", {"nombre": nombre, "destinatario": contacto},
                                   evento["id"], exp_id, contacto, "enrutador")
        else:
            prop = crear_propuesta(store, "info_llegada", {"nombre": nombre}, evento["id"], exp_id, contacto, "enrutador")
        if prop:
            return prop
    if intencion in ("solicita_factura", "solicita_albaran") and exp_id:
        plantilla = "emitir_factura" if intencion == "solicita_factura" else "emitir_albaran"
        prop = crear_propuesta(store, plantilla, {"expediente": exp_id}, evento["id"], exp_id, contacto, "enrutador")
        if prop:
            return prop
    motivo = {"cancelacion": "cancelacion", "solicita_cambio_fechas": "cambio_fechas", "envia_documento": "documento_recibido",
              "solicita_factura": "solicitud_factura", "solicita_albaran": "solicitud_albaran"}.get(intencion, "otro")
    return derivar_a_revision(store, motivo, evento["id"], exp_id, contacto, "enrutador")


def revisar_ocupacion(store) -> list[dict]:
    """Avisa de overbooking y propone cerrar ventas cuando un tipo se llena (siempre con aprobación)."""
    desde = store.ahora().date().isoformat()
    nuevas = []
    for c in disponibilidad.conflictos(store.db, desde):
        entrada, salida = c["fecha"], (date.fromisoformat(c["fecha"]) + timedelta(days=1)).isoformat()
        ya = any(p["plantilla"] == "cerrar_disponibilidad" and p["slots"]["tipo"] == c["tipo"] and p["slots"]["entrada"] == entrada
                 and p["estado"] in ("pendiente", "aprobada", "rechazada") for p in store.db["propuestas"])
        cerrado = any(x["tipo"] == c["tipo"] and x["entrada"] <= entrada < x["salida"] for x in store.db["cierres"])
        if not ya and not cerrado:
            prop = crear_propuesta(store, "cerrar_disponibilidad", {"tipo": c["tipo"], "entrada": entrada, "salida": salida}, origen="ocupación")
            if prop:
                nuevas.append(prop)
        avisado = any(e["tipo"] == "alerta_ocupacion" and e["datos"].get("tipo") == c["tipo"] and e["datos"].get("fecha") == c["fecha"]
                      and e["datos"].get("nivel") == c["nivel"] for e in store.db["eventos"])
        if not avisado:
            texto = (f"Overbooking en {c['tipo']} el {entrada}: {c['ocupadas']} ocupadas para {c['capacidad']}"
                     if c["nivel"] == "overbooking" else f"{c['tipo']} completo el {entrada}")
            registrar_evento(store, "sistema", "alerta_ocupacion", contenido=texto, datos=dict(c))
    return nuevas


# ================================================================ ejecución de propuestas aprobadas

def _ejecutar_whatsapp(store, prop: dict, actor: str):
    return registrar_evento(store, "whatsapp", "mensaje_saliente_simulado", remitente=prop["destinatario"], contenido=prop["texto"],
                            expediente_id=prop["expediente_id"],
                            datos={"plantilla": prop["plantilla"], "aprobado_por": actor, "wa_id": prop["destinatario"]})


def _ejecutar_roomcloud(store, prop: dict, actor: str):
    s = prop["slots"]
    store.db["cierres"].append({"tipo": s["tipo"], "entrada": s["entrada"], "salida": s["salida"]})
    return registrar_evento(store, "roomcloud", "modify_simulado", contenido=prop["texto"], datos={"aprobado_por": actor, **s})


def _ejecutar_interno(store, prop: dict, actor: str):
    return registrar_evento(store, "sistema", "revision_hecha", contenido=prop["texto"], expediente_id=prop["expediente_id"],
                            datos={"aprobado_por": actor})


def _ejecutar_correo(store, prop: dict, actor: str):
    from .adapters import correo  # import perezoso: el adaptador importa este módulo
    return correo.ejecutar(store, prop, actor)


def _ejecutar_documentos(store, prop: dict, actor: str):
    from . import documentos  # import perezoso: documentos importa este módulo
    return documentos.ejecutar(store, prop, actor)


# Destino de la plantilla -> función (store, propuesta, actor). Cada ejecución deja un evento en db["eventos"].
EJECUTORES = {"whatsapp": _ejecutar_whatsapp, "roomcloud": _ejecutar_roomcloud, "interno": _ejecutar_interno,
              "correo": _ejecutar_correo, "documentos": _ejecutar_documentos}


def ejecutar_propuesta(store, prop: dict, actor: str):
    """Ejecución simulada de una propuesta aprobada. Cada paso queda registrado como evento."""
    ejecutor = EJECUTORES.get(prop["destino"])
    if ejecutor is None:
        raise ErrorNegocio(f"No hay ejecutor para el destino «{prop['destino']}»", 422)
    return ejecutor(store, prop, actor)
