"""Conversaciones: los eventos de WhatsApp y de correo agrupados por persona y canal.

Es una vista de solo lectura sobre `db["eventos"]` que comparten el router de mensajes, el de «Hoy» y los bloques del
chat, para que los tres cuenten lo mismo (por ejemplo, qué es un mensaje sin responder). Una conversación es un hilo
con una persona por un canal y su id es `wa:<wa_id>` o `mail:<dirección en minúsculas>`.
"""
import re

from . import hub

ENTRANTE = "mensaje_entrante"
SALIENTE = {"whatsapp": "mensaje_saliente_simulado", "correo": "correo_saliente_simulado"}
PREVIA_MAX = 140


def _contacto_de(ev: dict) -> tuple[str, str] | None:
    """(canal, contacto) del evento, o None si no es un mensaje de WhatsApp ni de correo."""
    datos = ev.get("datos") or {}
    if ev["fuente"] == "whatsapp" and ev["tipo"] in (ENTRANTE, SALIENTE["whatsapp"]):
        crudo = str(datos.get("wa_id") or (ev["remitente"] if ev["tipo"] != ENTRANTE else ""))
        contacto = re.sub(r"\D", "", crudo) or crudo.strip()
        return ("whatsapp", contacto) if contacto else None
    if ev["fuente"] == "correo" and ev["tipo"] in (ENTRANTE, SALIENTE["correo"]):
        contacto = str(datos.get("correo") or "").strip().lower()
        return ("correo", contacto) if contacto else None
    return None


def id_de(canal: str, contacto: str) -> str:
    return ("wa:" if canal == "whatsapp" else "mail:") + contacto


def canal_y_contacto(conv_id: str) -> tuple[str, str] | None:
    if isinstance(conv_id, str) and conv_id.startswith("wa:") and len(conv_id) > 3:
        return "whatsapp", conv_id[3:]
    if isinstance(conv_id, str) and conv_id.startswith("mail:") and len(conv_id) > 5:
        return "correo", conv_id[5:].lower()
    return None


def _hilos(store) -> dict[str, list[dict]]:
    hilos: dict[str, list[dict]] = {}
    for ev in store.db["eventos"]:
        clave = _contacto_de(ev)
        if clave:
            hilos.setdefault(id_de(*clave), []).append(ev)
    return hilos


def _es_nombre(remitente: str, contacto: str) -> bool:
    return bool(remitente) and re.sub(r"\D", "", remitente) != contacto and remitente.strip().lower() != contacto


def _previa(texto: str) -> str:
    una_linea = " ".join(str(texto).split())
    return una_linea if len(una_linea) <= PREVIA_MAX else una_linea[:PREVIA_MAX - 1].rstrip() + "…"


def _texto_de(ev: dict) -> str:
    tipo = (ev.get("datos") or {}).get("tipo_mensaje")
    if not ev["contenido"] and tipo not in (None, "text"):
        return f"[Mensaje sin texto, de tipo {tipo}]"
    return ev["contenido"]


def propuestas_pendientes_de(store, conv_id: str, eventos: list[dict]) -> list[dict]:
    """Propuestas pendientes que salen de un mensaje de la conversación o van dirigidas a su contacto."""
    canal, contacto = canal_y_contacto(conv_id)
    ids = {e["id"] for e in eventos}
    salida = []
    for p in store.db["propuestas"]:
        if p["estado"] != "pendiente":
            continue
        quien = str(p.get("destinatario") or "")
        quien = re.sub(r"\D", "", quien) if canal == "whatsapp" else quien.strip().lower()
        if p.get("origen_evento") in ids or (quien and quien == contacto and p["destino"] in (canal, "interno")):
            salida.append(p)
    return salida


def _resumen(store, conv_id: str, eventos: list[dict]) -> dict:
    canal, contacto = canal_y_contacto(conv_id)
    ultimo = eventos[-1]
    entrantes = [e for e in eventos if e["tipo"] == ENTRANTE]
    exp_id = next((e["expediente_id"] for e in reversed(eventos) if e.get("expediente_id")), None)
    if not exp_id:
        exp = hub.buscar_por_telefono(store.db, contacto) if canal == "whatsapp" else hub.buscar_por_correo(store.db, contacto)
        exp_id = exp["id"] if exp else None
    exp = store.db["expedientes"].get(exp_id or "")
    nombre = next((e["remitente"] for e in reversed(entrantes) if _es_nombre(e["remitente"], contacto)), "")
    if not nombre and exp:
        nombre = f"{exp['reserva']['nombre']} {exp['reserva']['apellidos']}".strip()
    intencion = next(((e["datos"].get("interpretacion") or {}).get("intencion") for e in reversed(entrantes)
                      if (e["datos"].get("interpretacion") or {}).get("intencion")), None)
    entrante = ultimo["tipo"] == ENTRANTE
    return {"id": conv_id, "canal": canal, "nombre": nombre or contacto, "contacto": contacto, "expediente_id": exp_id,
            "ultimo": {"texto": _previa(_texto_de(ultimo)), "hora": ultimo["ts"][11:16],
                       "direccion": "entrante" if entrante else "saliente"},
            "sin_responder": entrante, "intencion": intencion,
            "propuestas_pendientes": len(propuestas_pendientes_de(store, conv_id, eventos))}


def listar(store, canal: str = "todos") -> list[dict]:
    """Conversaciones del canal pedido, la que tiene el mensaje más reciente primero."""
    hilos = [(conv_id, eventos) for conv_id, eventos in _hilos(store).items()
             if canal == "todos" or canal_y_contacto(conv_id)[0] == canal]
    hilos.sort(key=lambda h: (h[1][-1]["ts"], h[1][-1]["id"]), reverse=True)
    return [_resumen(store, conv_id, eventos) for conv_id, eventos in hilos]


def _mensaje(ev: dict, canal: str) -> dict:
    datos = ev.get("datos") or {}
    entrante = ev["tipo"] == ENTRANTE
    return {"id": ev["id"], "direccion": "entrante" if entrante else "saliente", "hora": ev["ts"][11:16],
            "texto": _texto_de(ev), "asunto": str(datos.get("asunto") or "") if canal == "correo" else None,
            "adjuntos": [{"nombre": a.get("nombre", ""), "documento_id": a.get("documento_id")} for a in datos.get("adjuntos") or []],
            "interpretacion": datos.get("interpretacion") if entrante else None,
            "simulado": hub.MODOS.get(canal) == "simulado"}


def detalle(store, conv_id: str) -> dict | None:
    """La conversación con todos sus mensajes y sus propuestas pendientes, o None si no existe."""
    eventos = _hilos(store).get(conv_id)
    if not eventos:
        return None
    return {"conversacion": _resumen(store, conv_id, eventos),
            "mensajes": [_mensaje(e, canal_y_contacto(conv_id)[0]) for e in eventos],
            "propuestas": propuestas_pendientes_de(store, conv_id, eventos)}


def contar_sin_responder(store) -> dict:
    """Conversaciones cuyo último mensaje es del huésped, por canal."""
    cuenta = {"whatsapp": 0, "correo": 0}
    for conv_id, eventos in _hilos(store).items():
        if eventos[-1]["tipo"] == ENTRANTE:
            cuenta[canal_y_contacto(conv_id)[0]] += 1
    return cuenta
