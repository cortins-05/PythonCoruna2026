"""Comunicaciones recibidas (WhatsApp y correo), prioridades de las fuentes y la vista de fuente única.

FACHADA DE DEMO: todo se calcula sobre los datos del almacén, pero los envíos son simulados y la comprensión de los mensajes usa reglas.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import comunicaciones, disponibilidad, estados, habitaciones, hub, prioridades
from ..deps import get_store, http_de

router = APIRouter(prefix="/api", tags=["comunicaciones"])


class SimularIn(BaseModel):
    canal: str
    contacto: str
    texto: str
    nombre: str = ""
    asunto: str = ""


class ConfirmarIn(BaseModel):
    actor: str = "Recepción"
    texto: str | None = None
    forzar: bool = False


class TextoIn(BaseModel):
    texto: str


def _contadores(store) -> dict:
    todas = comunicaciones._db(store)
    return {"pendientes": sum(c["estado"] == "pendiente" for c in todas), "en_espera": sum(c["estado"] == "en_espera" for c in todas),
            "respondidas": sum(c["estado"] == "respondida" for c in todas), "total": len(todas),
            "whatsapp": sum(c["canal"] == "whatsapp" and c["estado"] in comunicaciones.ABIERTAS for c in todas),
            "correo": sum(c["canal"] == "correo" and c["estado"] in comunicaciones.ABIERTAS for c in todas)}


def _prioridades() -> dict:
    return {"niveles": prioridades.NIVELES, "reglas": prioridades.REGLAS}


@router.get("/prioridades")
def ver_prioridades():
    return _prioridades()


@router.get("/comunicaciones")
def listar(estado: str | None = None, canal: str = "todos", store=Depends(get_store)):
    return {"reloj": store.ahora().isoformat(timespec="minutes"),
            "fuentes_consultadas": [{"id": n["id"], "nombre": n["nombre"], "nivel": n["nivel"], "tipo": n["tipo"]} for n in prioridades.NIVELES[:3]],
            "comunicaciones": comunicaciones.listar(store, estado, canal), "contadores": _contadores(store), "prioridades": _prioridades()}


@router.post("/comunicaciones/simular")
def simular(datos: SimularIn, store=Depends(get_store)):
    try:
        com = comunicaciones.registrar(store, datos.canal, datos.nombre, datos.contacto, datos.texto, datos.asunto)
        store.guardar()
        return comunicaciones.vista(store, com)
    except hub.ErrorNegocio as error:
        raise http_de(error)


@router.get("/comunicaciones/{com_id}")
def detalle(com_id: str, store=Depends(get_store)):
    try:
        return comunicaciones.vista(store, comunicaciones.obtener(store, com_id))
    except hub.ErrorNegocio as error:
        raise http_de(error)


@router.put("/comunicaciones/{com_id}/texto")
def editar(com_id: str, datos: TextoIn, store=Depends(get_store)):
    try:
        resultado = comunicaciones.editar_texto(store, com_id, datos.texto)
        store.guardar()
        return resultado
    except hub.ErrorNegocio as error:
        raise http_de(error)


@router.post("/comunicaciones/{com_id}/confirmar")
def confirmar(com_id: str, datos: ConfirmarIn, store=Depends(get_store)):
    try:
        resultado = comunicaciones.confirmar(store, com_id, datos.actor, datos.texto, datos.forzar)
        store.guardar()
        return resultado
    except hub.ErrorNegocio as error:
        raise http_de(error)


@router.post("/comunicaciones/{com_id}/descartar")
def descartar(com_id: str, datos: ConfirmarIn, store=Depends(get_store)):
    try:
        resultado = comunicaciones.descartar(store, com_id, datos.actor)
        store.guardar()
        return resultado
    except hub.ErrorNegocio as error:
        raise http_de(error)


@router.get("/fuente-unica")
def fuente_unica(store=Depends(get_store)):
    """Todo lo que entra, en un solo sitio: las fuentes y su prioridad, la cola de trabajo, la actividad y los totales por color."""
    from .. import main
    resumen = main.estancias(filtro="todas")
    cuenta = _contadores(store)
    return {"reloj": store.ahora().isoformat(timespec="minutes"), "prioridades": _prioridades(),
            "fuentes": comunicaciones.fuentes(store), "cola": comunicaciones.cola(store), "actividad": comunicaciones.actividad(store),
            "totales": {"estancias": len(resumen["estancias"]), "comunicaciones_pendientes": cuenta["pendientes"] + cuenta["en_espera"],
                        "conflictos": len(resumen["conflictos"]), "por_color": resumen["contadores"]},
            "datos_ofihotel": resumen["datos_ofihotel"], "leyenda": estados.LEYENDA}


@router.get("/ocupacion")
def ocupacion(dias: int = 14, store=Depends(get_store)):
    """Mapa de ocupación con el desglose por fuente de cada casilla y las peticiones que todavía compiten por habitaciones."""
    desde = store.ahora().date().isoformat()
    dias = max(1, min(dias, 30))
    return {"reloj": store.ahora().isoformat(timespec="minutes"), "desde": desde, "dias": dias,
            "mapa": disponibilidad.mapa(store.db, desde, dias), "conflictos": disponibilidad.conflictos(store.db, desde, dias),
            "peticiones": comunicaciones.peticiones_abiertas(store), "fuentes": prioridades.NIVELES[:3]}


@router.get("/insignias")
def insignias(store=Depends(get_store)):
    """Contadores del menú lateral: peticiones por confirmar, estancias con algo pendiente y elementos en la cola de trabajo."""
    from .. import main
    resumen = main.estancias(filtro="todas")
    cuenta = _contadores(store)
    pendientes = sum(n for color, n in resumen["contadores"].items() if color != "verde")
    return {"insignias": {"comunicaciones": cuenta["pendientes"] + cuenta["en_espera"], "estancias": pendientes,
                          "fuente": len(comunicaciones.cola(store))}}


@router.get("/habitaciones")
def ver_habitaciones(fecha: str | None = None, store=Depends(get_store)):
    """Quién hay en cada habitación un día (hoy por defecto), con quién llega y quién sale."""
    return habitaciones.vista(store, fecha)


class FechasIn(BaseModel):
    checkin: str
    checkout: str
    actor: str = "Recepción"
    forzar: bool = False


@router.put("/expedientes/{exp_id}/fechas")
def cambiar_fechas(exp_id: str, datos: FechasIn, store=Depends(get_store)):
    """Cambia las fechas de una estancia. Si el cambio produce overbooking en su tipo de habitación responde 409, salvo que se fuerce."""
    from datetime import date
    from fastapi import HTTPException
    from .. import main
    exp = store.db["expedientes"].get(exp_id)
    if not exp:
        raise HTTPException(404, "Estancia no encontrada")
    if exp["estado"] in ("cancelada", "cerrado"):
        raise HTTPException(409, {"problemas": ["La estancia está cancelada o cerrada"]})
    try:
        entrada, salida = date.fromisoformat(datos.checkin), date.fromisoformat(datos.checkout)
    except ValueError:
        raise HTTPException(422, {"problemas": ["Las fechas deben tener formato AAAA-MM-DD"]})
    if salida <= entrada:
        raise HTTPException(422, {"problemas": ["La salida debe ser posterior a la llegada"]})
    antes = (exp["checkin_prevista"], exp["checkout_prevista"])
    exp["checkin_prevista"], exp["checkout_prevista"] = datos.checkin, datos.checkout
    choques = [c for c in disponibilidad.conflictos(store.db, store.ahora().date().isoformat(), 30)
               if c["nivel"] == "overbooking" and datos.checkin <= c["fecha"] < datos.checkout and c["tipo"] in [h["tipo"] for h in exp["habitaciones"]]]
    if choques and not datos.forzar:
        exp["checkin_prevista"], exp["checkout_prevista"] = antes
        raise HTTPException(409, {"conflicto": choques})
    main.anotar(exp, f"Fechas cambiadas de {antes[0]} a {antes[1]} a {datos.checkin} a {datos.checkout}", datos.actor)
    hub.registrar_evento(store, "recepcion", "reserva_modificada", estados.nombre_de(exp), f"{estados.nombre_de(exp)}: nuevas fechas {datos.checkin} a {datos.checkout}", exp_id)
    hub.revisar_ocupacion(store)
    store.guardar()
    return main.resumen(exp)


class HabitacionIn(BaseModel):
    numero: int
    actor: str = "Recepción"


@router.put("/expedientes/{exp_id}/habitacion")
def fijar_habitacion(exp_id: str, datos: HabitacionIn, store=Depends(get_store)):
    """Fija el número de habitación de una estancia. El número tiene que ser de su tipo y estar libre en sus fechas."""
    from fastapi import HTTPException
    from .. import main
    exp = store.db["expedientes"].get(exp_id)
    if not exp:
        raise HTTPException(404, "Estancia no encontrada")
    tipo = exp["habitaciones"][0]["tipo"]
    if datos.numero not in habitaciones.NUMEROS.get(tipo, []):
        raise HTTPException(422, {"problemas": [f"La habitación {datos.numero} no es de tipo {tipo}"]})
    antes = exp.get("habitacion_fija")
    exp["habitacion_fija"] = datos.numero
    _, asignadas = habitaciones.asignar(store.db)
    if asignadas.get(f"{exp_id}#0") != datos.numero:
        exp["habitacion_fija"] = antes
        if antes is None:
            exp.pop("habitacion_fija", None)
        raise HTTPException(409, {"problemas": [f"La habitación {datos.numero} ya está ocupada otra de esas noches por una habitación fijada"]})
    main.anotar(exp, f"Habitación {datos.numero} asignada", datos.actor)
    hub.registrar_evento(store, "recepcion", "habitacion_asignada", estados.nombre_de(exp), f"{estados.nombre_de(exp)}: habitación {datos.numero}", exp_id)
    store.guardar()
    return {"id": exp_id, "habitacion": datos.numero}
