"""Lógica del hub: eventos, propuestas con aprobación y comprobación de ocupación.

Todo lo que entra se normaliza como evento. Lo único que el sistema puede hacer hacia fuera son
propuestas basadas en plantillas cerradas, y nada sale hasta que recepción las aprueba.
"""
import re
from datetime import date, timedelta

from . import disponibilidad, plantillas


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


def crear_propuesta(store, plantilla: str, slots: dict, origen_evento: str | None = None,
                    expediente_id: str | None = None, destinatario: str = "", origen: str = "sistema") -> dict | None:
    """Valida las variables y crea una propuesta pendiente. Devuelve None si no son válidas."""
    try:
        texto = plantillas.renderizar(plantilla, slots)
    except ValueError:
        return None
    prop = {"id": store.siguiente_id("pr"), "ts": store.ahora().isoformat(timespec="minutes"), "plantilla": plantilla,
            "destino": plantillas.PLANTILLAS[plantilla]["destino"], "slots": slots, "texto": texto,
            "expediente_id": expediente_id, "destinatario": destinatario, "origen_evento": origen_evento,
            "origen": origen, "estado": "pendiente", "decidido_por": None, "hora_decision": None}
    store.db["propuestas"].append(prop)
    return prop


def proponer_para_mensaje(store, evento: dict, expediente: dict | None, nombre_perfil: str, wa_id: str) -> dict:
    """Enrutador determinista: de la intención del lector sale como mucho una propuesta con plantilla."""
    intencion = evento["datos"]["interpretacion"]["intencion"]
    nombre = (expediente["reserva"]["nombre"] if expediente else nombre_perfil) or ""
    exp_id = expediente["id"] if expediente else None
    if intencion == "pregunta_checkin_horario":
        prop = crear_propuesta(store, "info_llegada", {"nombre": nombre}, evento["id"], exp_id, wa_id, "enrutador")
        if prop:
            return prop
    motivo = {"cancelacion": "cancelacion", "solicita_cambio_fechas": "cambio_fechas",
              "envia_documento": "documento_recibido"}.get(intencion, "otro")
    return crear_propuesta(store, "revision_humana", {"motivo": motivo}, evento["id"], exp_id, wa_id, "enrutador")


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


def ejecutar_propuesta(store, prop: dict, actor: str) -> None:
    """Ejecución simulada de una propuesta aprobada. Cada paso queda registrado como evento."""
    if prop["destino"] == "whatsapp":
        registrar_evento(store, "whatsapp", "mensaje_saliente_simulado", remitente=prop["destinatario"], contenido=prop["texto"],
                         expediente_id=prop["expediente_id"], datos={"plantilla": prop["plantilla"], "aprobado_por": actor})
    elif prop["destino"] == "roomcloud":
        s = prop["slots"]
        store.db["cierres"].append({"tipo": s["tipo"], "entrada": s["entrada"], "salida": s["salida"]})
        registrar_evento(store, "roomcloud", "modify_simulado", contenido=prop["texto"], datos={"aprobado_por": actor, **s})
    else:
        registrar_evento(store, "sistema", "revision_hecha", contenido=prop["texto"], expediente_id=prop["expediente_id"],
                         datos={"aprobado_por": actor})
