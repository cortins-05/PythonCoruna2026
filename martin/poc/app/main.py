"""Hub de expedientes: los datos de cada estancia viven aquí y salen por adaptadores."""
import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .adapters import ofihotel, roomcloud, ses
from .adapters.ocr import leer_documento
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
        "reserva": {"nombre": r["nombre"], "apellidos": r["apellidos"], "pais": r["pais"]},
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


@app.get("/")
def portada():
    return FileResponse(ESTATICO / "index.html")


@app.get("/api/estado")
def estado():
    return {"reloj": store.ahora().isoformat(timespec="minutes"),
            "ocr": "en vivo" if os.environ.get("ANTHROPIC_API_KEY") else "simulado",
            "ses": "simulado", "roomcloud": "XML grabado", "ofihotel": "copia asistida"}


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
        if existente and r["dlm"] <= existente["dlm"]:
            cuenta["sin_cambios"] += 1
            continue
        if cancelada:
            if existente:
                existente["estado"], existente["dlm"] = "cancelada", r["dlm"]
                anotar(existente, "Reserva cancelada en RoomCloud", "Sistema")
            cuenta["canceladas"] += 1
            continue
        if existente:
            existente.update(dlm=r["dlm"], checkin_prevista=r["checkin"], checkout_prevista=r["checkout"])
            anotar(existente, "Reserva modificada en RoomCloud", "Sistema")
            cuenta["actualizadas"] += 1
        else:
            store.db["expedientes"][ref] = nuevo_expediente(r)
            cuenta["nuevas"] += 1
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
    exp["pago"] = {"medio": datos.medio.strip().upper()}
    hecho(exp, "pago", "Recepción")
    if empresa_completa:
        exp["empresa"] = datos.empresa.model_dump()
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
