"""Hub de expedientes: los datos de cada estancia viven aquí y salen por adaptadores."""
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import chat, disponibilidad, hub, lector, plantillas
from .adapters import ofihotel, ofihotel_lectura, roomcloud, ses, whatsapp
from .adapters.ocr import leer_documento
from .deps import http_de
from .store import Store
from .validators import campos_que_faltan, problemas_huesped

app = FastAPI(title="Expediente de estancia (demo)")
store = Store()
ESTATICO = Path(__file__).resolve().parent / "static"
PLAZO_PARTE_H = 24
HORA_AVISO = 20
TRAMITES_MARCABLES = {"ofihotel_alta", "factura", "habitacion_liberada"}
CAMPOS_HUESPED = ["nombre", "apellido1", "apellido2", "sexo", "fecha_nacimiento", "nacionalidad",
                  "tipo_documento", "numero_documento", "numero_soporte", "direccion", "localidad",
                  "codigo_postal", "pais", "telefono", "email"]


class HuespedIn(BaseModel):
    nombre: str = ""
    apellido1: str = ""
    apellido2: str = ""
    sexo: str = ""
    fecha_nacimiento: str = ""
    nacionalidad: str = ""
    tipo_documento: str = ""
    numero_documento: str = ""
    numero_soporte: str = ""
    direccion: str = ""
    localidad: str = ""
    codigo_postal: str = ""
    pais: str = ""
    telefono: str = ""
    email: str = ""


class EmpresaIn(BaseModel):
    razon_social: str = ""
    cif: str = ""
    direccion: str = ""
    email: str = ""  # opcional: es uno de los correos a los que se pueden enviar documentos de la estancia


class PagoIn(BaseModel):
    medio: str = ""
    empresa: EmpresaIn | None = None


class OcrIn(BaseModel):
    imagen_b64: str | None = None
    tipo_mime: str = "image/png"


class ActorIn(BaseModel):
    actor: str = "Recepción"
    nota: str = ""


class RelojIn(BaseModel):
    horas: int = 1


def requeridos(exp: dict) -> list[str]:
    base = ["huesped", "pago", "parte", "ofihotel_alta", "factura", "habitacion_liberada"]
    if exp["viaja_por_trabajo"]:
        base.insert(2, "empresa")
    return base


def pendientes(exp: dict) -> list[str]:
    return [t for t in requeridos(exp) if exp["tramites"][t]["estado"] != "hecho"]


def anotar(exp: dict, accion: str, actor: str) -> None:
    exp["registro"].append({"hora": store.ahora().isoformat(timespec="minutes"), "actor": actor, "accion": accion})


def hecho(exp: dict, tramite: str, actor: str, nota: str = "") -> None:
    exp["tramites"][tramite] = {"estado": "hecho", "hora": store.ahora().isoformat(timespec="minutes"),
                                "actor": actor, "nota": nota}
    anotar(exp, f"Trámite '{tramite}' hecho", actor)


def nuevo_expediente(r: dict) -> dict:
    notas = r["notas"].lower()
    nombres = [t for t in ("huesped", "pago", "empresa", "parte", "ofihotel_alta", "factura", "habitacion_liberada")]
    exp = {
        "id": f"{r['portal_id']}-{r['id_canal']}",
        "referencia": f"{r['portal_id']}-{r['id_canal']}",
        "origen": "roomcloud",
        "dlm": r["dlm"],
        "estado": "pendiente_llegada",
        "checkin_prevista": r["checkin"],
        "checkout_prevista": r["checkout"],
        "personas": sum(int(h["adultos"] or 0) + int(h["ninos"] or 0) for h in r["habitaciones"]) or 1,
        "habitaciones": r["habitaciones"],
        "importe": r["importe"],
        "reserva": {"nombre": r["nombre"], "apellidos": r["apellidos"], "pais": r["pais"], "telefono": r["telefono"],
                    "email": r["email"]},
        "huesped": {c: "" for c in CAMPOS_HUESPED},
        "pago": {"medio": r["medio_pago"]},
        "empresa": {},
        "viaja_por_trabajo": "trabajo" in notas or "empresa" in notas,
        "tramites": {t: {"estado": "pendiente"} for t in nombres},
        "parte": None,
        "checkin_hora": None,
        "registro": [],
    }
    exp["huesped"]["telefono"] = r["telefono"]
    exp["huesped"]["email"] = r["email"]
    anotar(exp, "Expediente creado desde RoomCloud", "Sistema")
    return exp


def obtener(exp_id: str) -> dict:
    exp = store.db["expedientes"].get(exp_id)
    if not exp:
        raise HTTPException(404, "Expediente no encontrado")
    return exp


def parte_restante_h(exp: dict) -> float | None:
    if exp["estado"] != "en_curso" or exp["tramites"]["parte"]["estado"] == "hecho" or not exp["checkin_hora"]:
        return None
    limite = datetime.fromisoformat(exp["checkin_hora"]) + timedelta(hours=PLAZO_PARTE_H)
    return round((limite - store.ahora()).total_seconds() / 3600, 1)


def alertas() -> list[dict]:
    ahora, salida = store.ahora(), []
    for exp in store.db["expedientes"].values():
        nombre = f"{exp['huesped']['nombre']} {exp['huesped']['apellido1']}".strip() or exp["reserva"]["nombre"]
        restante = parte_restante_h(exp)
        if restante is not None:
            if restante <= 0:
                salida.append({"id": exp["id"], "nivel": "critico", "texto": f"{nombre}: el parte está fuera de plazo"})
            elif ahora.hour >= HORA_AVISO or ahora.hour < 8:
                salida.append({"id": exp["id"], "nivel": "aviso", "texto": f"{nombre}: parte sin enviar pasadas las {HORA_AVISO} h"})
            elif restante <= 4:
                salida.append({"id": exp["id"], "nivel": "aviso", "texto": f"{nombre}: quedan {restante} h para enviar el parte"})
        if exp["estado"] == "pendiente_llegada" and exp["checkin_prevista"] < ahora.date().isoformat():
            salida.append({"id": exp["id"], "nivel": "aviso", "texto": f"{nombre}: llegada prevista pasada sin check-in"})
    return salida


def resumen(exp: dict) -> dict:
    h = exp["huesped"]
    return {"id": exp["id"], "huesped": f"{h['nombre']} {h['apellido1']}".strip() or f"{exp['reserva']['nombre']} {exp['reserva']['apellidos']}",
            "estado": exp["estado"], "checkin": exp["checkin_prevista"], "checkout": exp["checkout_prevista"],
            "pendientes": pendientes(exp) if exp["estado"] != "cancelada" else [],
            "parte": exp["tramites"]["parte"]["estado"], "parte_restante_h": parte_restante_h(exp),
            "viaja_por_trabajo": exp["viaja_por_trabajo"]}


app.mount("/static", StaticFiles(directory=ESTATICO), name="static")


@app.get("/")
def portada():
    nueva = ESTATICO / "index.html"
    return FileResponse(nueva if nueva.exists() else ESTATICO / "legacy.html")


@app.get("/legacy")
def interfaz_antigua():
    return FileResponse(ESTATICO / "legacy.html")


@app.get("/api/estado")
def estado():
    con_clave = bool(os.environ.get("ANTHROPIC_API_KEY"))
    modo_claude = "real" if con_clave else "simulado"
    return {"reloj": store.ahora().isoformat(timespec="minutes"),
            "ocr": "en vivo" if con_clave else "simulado",
            "ses": "simulado", "roomcloud": "XML grabado", "ofihotel": "copia asistida",
            # Añadido por la interfaz nueva: el modo de cada integración, con los mismos ids que /api/integraciones.
            "modos": {**hub.MODOS, "ocr": modo_claude, "lector": modo_claude, "chat": modo_claude}}


@app.post("/api/reiniciar")
def reiniciar():
    store.reiniciar()
    return {"ok": True}


@app.post("/api/reloj")
def avanzar_reloj(datos: RelojIn):
    store.db["reloj_h"] += datos.horas
    store.guardar()
    return {"reloj": store.ahora().isoformat(timespec="minutes")}


@app.post("/api/sync/roomcloud")
def sincronizar():
    cuenta = {"nuevas": 0, "actualizadas": 0, "sin_cambios": 0, "canceladas": 0}
    for r in roomcloud.leer_reservas():
        ref = f"{r['portal_id']}-{r['id_canal']}"
        existente = store.db["expedientes"].get(ref)
        cancelada = r["estado_rc"] in roomcloud.ESTADOS_CANCELADOS
        nombre = f"{r['nombre']} {r['apellidos']}".strip()
        if existente and r["dlm"] <= existente["dlm"]:
            cuenta["sin_cambios"] += 1
            continue
        if cancelada:
            if existente:
                existente["estado"], existente["dlm"] = "cancelada", r["dlm"]
                anotar(existente, "Reserva cancelada en RoomCloud", "Sistema")
                hub.registrar_evento(store, "roomcloud", "reserva_cancelada", nombre, f"Reserva {ref} cancelada", ref)
            cuenta["canceladas"] += 1
            continue
        if existente:
            existente.update(dlm=r["dlm"], checkin_prevista=r["checkin"], checkout_prevista=r["checkout"])
            anotar(existente, "Reserva modificada en RoomCloud", "Sistema")
            hub.registrar_evento(store, "roomcloud", "reserva_modificada", nombre, f"Reserva {ref} modificada", ref)
            cuenta["actualizadas"] += 1
        else:
            store.db["expedientes"][ref] = nuevo_expediente(r)
            hub.registrar_evento(store, "roomcloud", "reserva_nueva", nombre,
                                 f"Reserva {ref}: {r['checkin']} a {r['checkout']}", ref)
            cuenta["nuevas"] += 1
    hub.revisar_ocupacion(store)
    store.guardar()
    return cuenta


@app.get("/api/panel")
def panel():
    hoy = store.ahora().date().isoformat()
    exps = [e for e in store.db["expedientes"].values() if e["estado"] != "cancelada"]
    return {
        "reloj": store.ahora().isoformat(timespec="minutes"),
        "llegadas_hoy": [resumen(e) for e in exps if e["checkin_prevista"] == hoy],
        "en_casa": [resumen(e) for e in exps if e["estado"] == "en_curso"],
        "salidas_hoy": [resumen(e) for e in exps if e["checkout_prevista"] == hoy and e["estado"] != "cerrado"],
        "partes": {"enviados": sum(e["tramites"]["parte"]["estado"] == "hecho" for e in exps),
                   "pendientes": sum(e["estado"] == "en_curso" and e["tramites"]["parte"]["estado"] != "hecho" for e in exps)},
        "alertas": alertas(),
    }


@app.get("/api/expedientes")
def listar():
    return [resumen(e) for e in store.db["expedientes"].values()]


@app.get("/api/expedientes/{exp_id}")
def detalle(exp_id: str):
    exp = obtener(exp_id)
    return {**exp, "pendientes": pendientes(exp), "parte_restante_h": parte_restante_h(exp)}


@app.post("/api/expedientes/{exp_id}/ocr")
def ocr(exp_id: str, datos: OcrIn):
    obtener(exp_id)
    lectura = leer_documento(datos.imagen_b64, datos.tipo_mime)
    lectura["problemas"] = problemas_huesped(lectura["campos"], store.ahora().date())
    lectura["dudosos"] = [c for c, v in lectura["confianza"].items() if v < 0.85]
    return lectura


@app.put("/api/expedientes/{exp_id}/huesped")
def guardar_huesped(exp_id: str, datos: HuespedIn):
    exp = obtener(exp_id)
    nuevo = datos.model_dump()
    problemas = problemas_huesped(nuevo, store.ahora().date())
    if problemas:
        raise HTTPException(422, {"problemas": problemas})
    exp["huesped"] = nuevo
    if exp["estado"] == "pendiente_llegada":
        exp["estado"], exp["checkin_hora"] = "en_curso", store.ahora().isoformat(timespec="minutes")
    hecho(exp, "huesped", "Recepción")
    store.guardar()
    return {"ok": True, "pendientes": pendientes(exp)}


@app.put("/api/expedientes/{exp_id}/pago")
def guardar_pago(exp_id: str, datos: PagoIn):
    exp = obtener(exp_id)
    if not datos.medio.strip():
        raise HTTPException(422, {"problemas": ["Falta el medio de pago"]})
    empresa_completa = bool(datos.empresa and datos.empresa.cif and datos.empresa.razon_social and datos.empresa.direccion)
    if exp["viaja_por_trabajo"] and not empresa_completa:
        raise HTTPException(422, {"problemas": ["Viaja por trabajo: faltan razón social, CIF o dirección de la empresa"]})
    if datos.empresa and datos.empresa.email.strip() and not plantillas.email_valido(datos.empresa.email.strip()):
        raise HTTPException(422, {"problemas": ["El correo de la empresa no es válido"]})
    exp["pago"] = {"medio": datos.medio.strip().upper()}
    hecho(exp, "pago", "Recepción")
    if empresa_completa:
        exp["empresa"] = {**datos.empresa.model_dump(), "email": datos.empresa.email.strip()}
        hecho(exp, "empresa", "Recepción", "Datos fiscales recogidos en el check-in")
    store.guardar()
    return {"ok": True, "pendientes": pendientes(exp)}


@app.get("/api/expedientes/{exp_id}/parte")
def previsualizar_parte(exp_id: str):
    exp = obtener(exp_id)
    faltan = campos_que_faltan(exp["huesped"], exp["pago"])
    problemas = problemas_huesped(exp["huesped"], store.ahora().date())
    xml = ses.construir_xml(exp) if not faltan and not problemas else None
    return {"faltan": faltan, "problemas": problemas, "xml": xml, "nota": ses.NOTA, "enviado": exp["parte"]}


@app.post("/api/expedientes/{exp_id}/parte/confirmar")
def confirmar_parte(exp_id: str, datos: ActorIn):
    exp = obtener(exp_id)
    if exp["parte"]:
        raise HTTPException(409, "El parte ya se envió")
    faltan = campos_que_faltan(exp["huesped"], exp["pago"])
    problemas = problemas_huesped(exp["huesped"], store.ahora().date())
    if faltan or problemas or exp["tramites"]["huesped"]["estado"] != "hecho":
        raise HTTPException(409, {"faltan": faltan, "problemas": problemas})
    xml = ses.construir_xml(exp)
    exp["parte"] = {**ses.enviar_simulado(xml, store.ahora()), "actor": datos.actor, "xml": xml}
    hecho(exp, "parte", datos.actor, f"Justificante {exp['parte']['justificante']} (simulado)")
    store.guardar()
    return exp["parte"]


@app.get("/api/expedientes/{exp_id}/ofihotel")
def copia_ofihotel(exp_id: str):
    exp = obtener(exp_id)
    if exp["tramites"]["huesped"]["estado"] != "hecho":
        raise HTTPException(409, "Faltan los datos del huésped")
    return ofihotel.preparar_copia(exp)


@app.post("/api/expedientes/{exp_id}/tramites/{tramite}")
def marcar(exp_id: str, tramite: str, datos: ActorIn):
    exp = obtener(exp_id)
    if tramite not in TRAMITES_MARCABLES:
        raise HTTPException(404, "Trámite no marcable a mano")
    if exp["estado"] != "en_curso":
        raise HTTPException(409, "El huésped no ha hecho el check-in")
    if tramite == "factura" and exp["viaja_por_trabajo"] and exp["tramites"]["empresa"]["estado"] != "hecho":
        raise HTTPException(409, "Faltan los datos fiscales de la empresa")
    hecho(exp, tramite, datos.actor, datos.nota)
    store.guardar()
    return {"ok": True, "pendientes": pendientes(exp)}


@app.post("/api/expedientes/{exp_id}/cerrar")
def cerrar(exp_id: str, datos: ActorIn):
    exp = obtener(exp_id)
    falta = pendientes(exp)
    if falta:
        raise HTTPException(409, {"pendientes": falta})
    exp["estado"] = "cerrado"
    anotar(exp, "Expediente cerrado", datos.actor)
    store.guardar()
    return {"ok": True}


# ---------------------------------------------------------------- hub: ocupación, WhatsApp, aprobaciones

class WalkinIn(BaseModel):
    nombre: str
    apellidos: str = ""
    telefono: str = ""
    tipo: str
    checkin: str
    checkout: str
    personas: int = 1
    viaja_por_trabajo: bool = False
    forzar: bool = False


class WhatsappIn(BaseModel):
    wa_id: str
    nombre: str = ""
    texto: str


@app.get("/api/disponibilidad")
def ver_disponibilidad(dias: int = 7):
    desde = store.ahora().date().isoformat()
    return {"mapa": disponibilidad.mapa(store.db, desde, dias), "conflictos": disponibilidad.conflictos(store.db, desde, dias)}


@app.post("/api/sync/ofihotel")
def sincronizar_ofihotel():
    """Lectura SOLO LECTURA de OfiHotel (instantánea de ejemplo): nunca se escribe en OfiHotel."""
    instantanea = ofihotel_lectura.leer_instantanea()
    store.db["ofihotel"] = instantanea
    hub.registrar_evento(store, "ofihotel", "instantanea_lectura",
                         contenido=f"{len(instantanea['ocupaciones'])} ocupaciones leídas (solo lectura)")
    hub.revisar_ocupacion(store)
    store.guardar()
    return {"ocupaciones": len(instantanea["ocupaciones"])}


@app.post("/api/walkin")
def nuevo_walkin(datos: WalkinIn):
    try:
        entrada, salida = date.fromisoformat(datos.checkin), date.fromisoformat(datos.checkout)
    except ValueError:
        raise HTTPException(422, {"problemas": ["Las fechas deben tener formato AAAA-MM-DD"]})
    if salida <= entrada:
        raise HTTPException(422, {"problemas": ["La salida debe ser posterior a la llegada"]})
    if datos.tipo not in disponibilidad.capacidad():
        raise HTTPException(422, {"problemas": [f"Tipo de habitación desconocido: {datos.tipo}"]})
    numero = store.siguiente_id("w").split("-")[1]
    r = {"portal_id": "W", "id_canal": numero, "dlm": store.ahora().isoformat(timespec="minutes"), "estado_rc": "4",
         "checkin": datos.checkin, "checkout": datos.checkout, "nombre": datos.nombre, "apellidos": datos.apellidos,
         "telefono": datos.telefono, "email": "", "pais": "", "importe": "", "medio_pago": "",
         "notas": "trabajo" if datos.viaja_por_trabajo else "",
         "habitaciones": [{"tipo": datos.tipo, "tarifa": "", "adultos": str(datos.personas), "ninos": "0"}]}
    exp = nuevo_expediente(r)
    exp["origen"] = "walk-in"
    store.db["expedientes"][exp["id"]] = exp
    choques = [c for c in disponibilidad.conflictos(store.db, store.ahora().date().isoformat(), 14)
               if c["tipo"] == datos.tipo and c["nivel"] == "overbooking" and datos.checkin <= c["fecha"] < datos.checkout]
    if choques and not datos.forzar:
        del store.db["expedientes"][exp["id"]]
        raise HTTPException(409, {"conflicto": choques})
    hub.registrar_evento(store, "recepcion", "walk_in", f"{datos.nombre} {datos.apellidos}".strip(),
                         f"Reserva física {datos.tipo} del {datos.checkin} al {datos.checkout}", exp["id"])
    hub.revisar_ocupacion(store)
    store.guardar()
    return {"id": exp["id"], "conflicto": choques}


def _procesar_whatsapp(payload: dict) -> list[dict]:
    creados = []
    for m in whatsapp.parsear(payload):
        exp = hub.buscar_por_telefono(store.db, m["wa_id"])
        ev = hub.registrar_evento(store, "whatsapp", "mensaje_entrante", m["nombre"] or m["wa_id"], m["texto"],
                                  exp["id"] if exp else None, {"wa_id": m["wa_id"], "tipo_mensaje": m["tipo"]})
        if m["tipo"] == "text":
            ev["datos"]["interpretacion"] = lector.interpretar(m["texto"])
        else:
            ev["datos"]["interpretacion"] = {"intencion": "envia_documento" if m["tipo"] in ("image", "document") else "otro",
                                             "confianza": 0.0, "modo": "tipo de mensaje"}
        prop = hub.proponer_para_mensaje(store, ev, exp, m["nombre"], m["wa_id"])
        creados.append({"evento": ev["id"], "propuesta": prop["id"] if prop else None})
    store.guardar()
    return creados


@app.post("/api/webhook/whatsapp")
def webhook_whatsapp(payload: dict):
    return _procesar_whatsapp(payload)


@app.post("/api/whatsapp/simular")
def simular_whatsapp(datos: WhatsappIn):
    return _procesar_whatsapp(whatsapp.construir_payload(datos.wa_id, datos.nombre, datos.texto, store.ahora()))


class ChatIn(BaseModel):
    mensaje: str
    historial: list[dict] = []


@app.post("/api/chat")
def chat_con_la_informacion(datos: ChatIn):
    return chat.responder(store, datos.mensaje, datos.historial)


@app.get("/api/bandeja")
def bandeja():
    return {"eventos": list(reversed(store.db["eventos"]))[:100],
            "propuestas": [p for p in store.db["propuestas"] if p["estado"] == "pendiente"]}


@app.get("/api/propuestas")
def propuestas(estado: str | None = None):
    return [p for p in store.db["propuestas"] if estado is None or p["estado"] == estado]


def _propuesta(pid: str) -> dict:
    prop = next((p for p in store.db["propuestas"] if p["id"] == pid), None)
    if not prop:
        raise HTTPException(404, "Propuesta no encontrada")
    if prop["estado"] != "pendiente":
        raise HTTPException(409, "La propuesta ya está decidida")
    return prop


@app.post("/api/propuestas/{pid}/aprobar")
def aprobar(pid: str, datos: ActorIn):
    prop = _propuesta(pid)
    # Se vuelve a validar al aprobar, por si los datos cambiaron desde que se propuso: variables y contexto (que el
    # expediente o el documento existan, que el documento siga emitido y que el destinatario siga siendo conocido).
    problemas = hub.problemas_de_propuesta(store, prop["plantilla"], prop["slots"])
    if problemas:
        raise HTTPException(422, {"problemas": problemas})
    prop["texto"] = plantillas.renderizar(prop["plantilla"], prop["slots"])
    anterior = {campo: prop[campo] for campo in ("estado", "decidido_por", "hora_decision")}
    prop.update(estado="aprobada", decidido_por=datos.actor, hora_decision=store.ahora().isoformat(timespec="minutes"))
    try:
        hub.ejecutar_propuesta(store, prop, datos.actor)
    except hub.ErrorNegocio as error:  # si la ejecución falla, la propuesta sigue pendiente y recepción ve el motivo
        prop.update(anterior)
        raise http_de(error)
    store.guardar()
    return prop


@app.post("/api/propuestas/{pid}/rechazar")
def rechazar(pid: str, datos: ActorIn):
    prop = _propuesta(pid)
    prop.update(estado="rechazada", decidido_por=datos.actor, hora_decision=store.ahora().isoformat(timespec="minutes"))
    store.guardar()
    return prop


# ================================================================ routers de la interfaz nueva (bloque de la base)
# Se incluyen al final para que puedan importar lo que define este módulo sin ciclos. Cada router vive en su fichero
# y usa `deps.get_store`, que devuelve `main.store` en el momento de la llamada.
from .routers import chat as router_chat  # noqa: E402
from .routers import demo, hoy, integraciones, mensajes  # noqa: E402
from .routers import documentos as router_documentos  # noqa: E402

for _router in (hoy.router, integraciones.router, mensajes.router, router_documentos.router, router_chat.router, demo.router):
    app.include_router(_router)
