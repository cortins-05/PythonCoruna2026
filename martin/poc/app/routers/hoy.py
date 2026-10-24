"""Hoy: el resumen del día para recepción.

Versión de la base con cuentas simples hechas sobre el almacén. El agente back-hoy puede afinar los criterios sin cambiar la
forma de la respuesta. Las insignias del menú salen de los mismos números que los KPI, para que nunca se contradigan.
"""
import math

from fastapi import APIRouter, Depends

from .. import conversaciones, disponibilidad
from ..deps import get_store

router = APIRouter(prefix="/api", tags=["hoy"])
MAX_ALERTAS = 8
MAX_ACCIONES = 6
ORDEN_NIVEL = {"critico": 0, "aviso": 1, "info": 2}


def _principal():
    from .. import main  # import perezoso: main incluye este router
    return main


def _fecha_corta(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def _kpi(id_: str, etiqueta: str, valor, detalle: str, tono: str, ruta: str) -> dict:
    return {"id": id_, "etiqueta": etiqueta, "valor": valor, "detalle": detalle, "tono": tono, "ruta": ruta}


def _sin_responder_en_texto(cuenta: dict) -> str:
    partes = []
    if cuenta["whatsapp"]:
        partes.append(f"{cuenta['whatsapp']} WhatsApp")
    if cuenta["correo"]:
        partes.append(f"{cuenta['correo']} {'correo' if cuenta['correo'] == 1 else 'correos'}")
    return " y ".join(partes)


def _kpi_ocupacion(store, hoy: str) -> dict:
    tipos = disponibilidad.mapa(store.db, hoy, 1)["tipos"]
    llenos = [(t, d["capacidad"], d["dias"][0]["ocupadas"]) for t, d in tipos.items() if d["capacidad"] > 0]
    if not llenos:
        return _kpi("ocupacion", "Ocupación de hoy", "0 %", "", "neutro", "ocupacion")
    tipo, capacidad, ocupadas = max(llenos, key=lambda f: (f[2] / f[1], f[2]))
    porcentaje = round(100 * ocupadas / capacidad)
    tono = "critico" if ocupadas >= capacidad else "aviso" if porcentaje >= 80 else "neutro"
    return _kpi("ocupacion", "Ocupación de hoy", f"{porcentaje} %", f"{ocupadas} de {capacidad} {tipo}", tono, "ocupacion")


def _etiqueta_propuesta(store, p: dict) -> str:
    s, principal = p["slots"], _principal()
    if p["plantilla"] in ("info_llegada", "pedir_documentos", "confirmar_reserva", "correo_info_llegada"):
        return f"Aprobar la respuesta a {s['nombre']}"
    if p["plantilla"] in ("emitir_factura", "emitir_albaran"):
        exp = store.db["expedientes"].get(s["expediente"])
        quien = principal.resumen(exp)["huesped"] if exp else s["expediente"]
        return f"Aprobar la emisión {'de la factura' if p['plantilla'] == 'emitir_factura' else 'del albarán'} de {quien}"
    if p["plantilla"] == "enviar_documento":
        return f"Aprobar el envío del documento {s['documento']}"
    if p["plantilla"] == "cerrar_disponibilidad":
        return f"Aprobar el cierre de {s['tipo']} el {_fecha_corta(s['entrada'])}"
    return "Revisar a mano un mensaje"


def calcular(store) -> dict:
    principal = _principal()
    ahora = store.ahora()
    hoy = ahora.date().isoformat()
    exps = [e for e in store.db["expedientes"].values() if e["estado"] != "cancelada"]
    llegadas = [e for e in exps if e["checkin_prevista"] == hoy]
    en_casa = [e for e in exps if e["estado"] == "en_curso"]
    salidas = [e for e in exps if e["checkout_prevista"] == hoy and e["estado"] != "cerrado"]
    con_parte_pendiente = [e for e in en_casa if e["tramites"]["parte"]["estado"] != "hecho"]
    restantes = [h for h in (principal.parte_restante_h(e) for e in con_parte_pendiente) if h is not None]
    propuestas = [p for p in store.db["propuestas"] if p["estado"] == "pendiente"]
    sin_responder = conversaciones.contar_sin_responder(store)
    por_enviar = [d for d in store.db["documentos"].values() if d["estado"] == "emitido"]

    hechos = sum(e["estado"] != "pendiente_llegada" for e in llegadas)
    if not con_parte_pendiente:
        detalle_partes = ""
    elif min(restantes, default=1) <= 0:
        detalle_partes = "alguno está fuera de plazo"
    elif restantes:
        horas = math.floor(min(restantes))
        detalle_partes = f"el más urgente vence en {horas} h" if horas else "el más urgente vence en menos de 1 h"
    else:
        detalle_partes = ""
    total_sin_responder = sin_responder["whatsapp"] + sin_responder["correo"]
    kpis = [
        _kpi("llegadas", "Llegadas de hoy", len(llegadas),
             (f"{hechos} con check-in hecho" if hechos else "ninguna con check-in hecho") if llegadas else "", "neutro", "recepcion"),
        _kpi("en_casa", "En casa", len(en_casa), "", "neutro", "recepcion"),
        _kpi("salidas", "Salidas de hoy", len(salidas), "", "neutro", "recepcion"),
        _kpi("partes", "Partes sin enviar", len(con_parte_pendiente), detalle_partes,
             "critico" if any(h <= 0 for h in restantes) else "aviso" if con_parte_pendiente else "ok", "recepcion"),
        _kpi("pendientes", "Pendientes de aprobar", len(propuestas), "", "aviso" if propuestas else "ok", "bandeja"),
        _kpi("sin_responder", "Mensajes sin responder", total_sin_responder, _sin_responder_en_texto(sin_responder),
             "aviso" if total_sin_responder else "ok", "mensajes"),
        _kpi_ocupacion(store, hoy),
        _kpi("documentos", "Documentos por enviar", len(por_enviar), "", "neutro", "documentos"),
    ]

    alertas = [{"nivel": a["nivel"], "texto": a["texto"], "ruta": "recepcion",
                "params": {"id": a["id"], **({"paso": "parte"} if "parte" in a["texto"] else {})}} for a in principal.alertas()]
    for c in disponibilidad.conflictos(store.db, hoy, 7):
        overbooking = c["nivel"] == "overbooking"
        texto = (f"Overbooking en {c['tipo']} el {_fecha_corta(c['fecha'])}: {c['ocupadas']} ocupadas para {c['capacidad']}"
                 if overbooking else f"{c['tipo']} completo el {_fecha_corta(c['fecha'])}")
        alertas.append({"nivel": "critico" if overbooking else "aviso", "texto": texto, "ruta": "ocupacion",
                        "params": {"tipo": c["tipo"], "fecha": c["fecha"]}})
    alertas.sort(key=lambda a: ORDEN_NIVEL[a["nivel"]])
    alertas = [{"id": f"al-{n}", **a} for n, a in enumerate(alertas[:MAX_ALERTAS], 1)]

    acciones = [{"texto": _etiqueta_propuesta(store, p), "ruta": "bandeja", "params": {"propuesta": p["id"]}} for p in propuestas]
    acciones += [{"texto": f"Enviar el parte de {principal.resumen(e)['huesped']}", "ruta": "recepcion",
                  "params": {"id": e["id"], "paso": "parte"}} for e in con_parte_pendiente]
    acciones += [{"texto": f"Enviar el documento {d['numero']}", "ruta": "documentos", "params": {"id": d["id"]}} for d in por_enviar]
    acciones += [{"texto": f"Hacer el check-in de {principal.resumen(e)['huesped']}", "ruta": "recepcion",
                  "params": {"id": e["id"], "paso": "documento"}} for e in llegadas if e["estado"] == "pendiente_llegada"]

    return {"reloj": ahora.isoformat(timespec="minutes"), "kpis": kpis, "alertas": alertas,
            "llegadas": [principal.resumen(e) for e in llegadas], "salidas": [principal.resumen(e) for e in salidas],
            "proximas_acciones": acciones[:MAX_ACCIONES],
            "insignias": {"bandeja": len(propuestas), "mensajes": total_sin_responder,
                          "recepcion": len(con_parte_pendiente), "documentos": len(por_enviar)}}


@router.get("/hoy")
def hoy(store=Depends(get_store)):
    return calcular(store)
