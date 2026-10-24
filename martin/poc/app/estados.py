"""Estado de cada estancia por sistema y semáforo (propuesta del documento `docs/07-fuente-de-verdad.md`).

Cada estancia lleva un estado por cada sistema (RoomCloud, OfiHotel y documentación) y un color que resume lo más urgente:

- rojo: conflicto entre orígenes (fechas distintas, habitación doble, overbooking) o parte fuera de plazo.
- naranja: parte de viajeros sin enviar con el plazo de 24 horas corriendo.
- amarillo: falta pasar la estancia a OfiHotel y la llegada es hoy o antes.
- azul: hay que atender algo nuevo (llegada de hoy sin check-in) o un mensaje que no está enlazado con ninguna estancia.
- gris: cancelada en RoomCloud pero todavía viva en OfiHotel, pendiente de reflejar.
- verde: todo cuadrado.

OfiHotel llega con los datos del día anterior, así que "migrado" significa "estaba en la lectura de ayer": lo que recepción pasa hoy
queda en "marcado" hasta que la lectura de mañana lo confirme.
"""
import re
import unicodedata
from datetime import datetime, timedelta

from . import disponibilidad

PLAZO_PARTE_H = 24
COLORES = ("rojo", "naranja", "amarillo", "azul", "gris", "verde")
TONOS = {"rojo": "critico", "naranja": "aviso", "amarillo": "aviso", "azul": "info", "gris": "neutro", "verde": "ok"}
LEYENDA = [
    {"color": "rojo", "titulo": "Conflicto", "descripcion": "Orígenes que no coinciden, habitación doble, overbooking o parte fuera de plazo"},
    {"color": "naranja", "titulo": "Parte pendiente", "descripcion": "El parte de viajeros no se ha enviado y el plazo de 24 horas corre"},
    {"color": "amarillo", "titulo": "Por pasar a OfiHotel", "descripcion": "Falta pasar la estancia a OfiHotel y la llegada es hoy o antes"},
    {"color": "azul", "titulo": "Por atender", "descripcion": "Llegada de hoy sin check-in o mensaje nuevo sin enlazar con ninguna estancia"},
    {"color": "gris", "titulo": "Por reflejar", "descripcion": "Cancelada en RoomCloud pero todavía viva en OfiHotel"},
    {"color": "verde", "titulo": "Todo cuadrado", "descripcion": "Nada pendiente"},
]


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()


def _palabras(texto: str) -> set[str]:
    return {p for p in re.split(r"[^a-z0-9]+", _sin_tildes(texto)) if len(p) > 2}


def _corta(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def _horas(h: float) -> str:
    """Horas con coma decimal y sin ceros sobrantes: 24 y 23,5."""
    return f"{h:g}".replace(".", ",")


def _solapan(desde_a: str, hasta_a: str, desde_b: str, hasta_b: str) -> bool:
    return desde_a < hasta_b and desde_b < hasta_a


def lectura_ofihotel(db: dict) -> dict:
    return db.get("ofihotel") or {}


def tipo_de(exp: dict) -> str:
    return exp["habitaciones"][0]["tipo"] if exp.get("habitaciones") else ""


def nombre_de(exp: dict) -> str:
    h = exp["huesped"]
    return f"{h['nombre']} {h['apellido1']}".strip() or f"{exp['reserva']['nombre']} {exp['reserva']['apellidos']}".strip()


def buscar_en_ofihotel(db: dict, exp: dict) -> dict | None:
    """Estancia de OfiHotel que corresponde a este expediente: por referencia externa y, si no hay, por apellido y fechas solapadas."""
    estancias = [e for e in lectura_ofihotel(db).get("estancias", []) if e.get("estado") != "anulada" or e.get("ref_externa") == exp["referencia"]]
    for e in estancias:
        if e.get("ref_externa") and e["ref_externa"] == exp["referencia"]:
            return {**e, "inferida": False}
    apellidos = _palabras(f"{exp['reserva']['apellidos']} {exp['huesped'].get('apellido1', '')} {exp['huesped'].get('apellido2', '')}")
    if not apellidos:
        return None
    for e in estancias:
        if e.get("ref_externa"):
            continue  # ya pertenece a otra reserva de canal
        if apellidos & _palabras(e.get("huesped", "")) and _solapan(exp["checkin_prevista"], exp["checkout_prevista"], e["entrada"], e["salida"]):
            return {**e, "inferida": True}
    return None


def parte_restante_h(exp: dict, ahora: datetime) -> float | None:
    if exp["estado"] != "en_curso" or exp["tramites"]["parte"]["estado"] == "hecho" or not exp.get("checkin_hora"):
        return None
    limite = datetime.fromisoformat(exp["checkin_hora"]) + timedelta(hours=PLAZO_PARTE_H)
    return round((limite - ahora).total_seconds() / 3600, 1)


def sistemas_de(db: dict, exp: dict, ahora: datetime) -> dict:
    """Estado de la estancia en cada sistema, cada uno con un texto corto para mostrarlo tal cual."""
    t = exp["tramites"]
    if exp["estado"] == "cancelada":
        roomcloud = {"estado": "cancelada", "detalle": "Cancelada en RoomCloud"}
    elif exp["origen"] == "roomcloud":
        roomcloud = {"estado": "sincronizado", "detalle": "Leída de RoomCloud"}
    else:
        roomcloud = {"estado": "no_aplica", "detalle": "Reserva física: no pasa por RoomCloud"}

    lectura, encontrada = lectura_ofihotel(db), buscar_en_ofihotel(db, exp)
    if not lectura:
        ofihotel = {"estado": "sin_lectura", "detalle": "OfiHotel todavía no se ha leído"}
    elif encontrada:
        sitio = f" (hab. {encontrada['habitacion']})" if encontrada.get("habitacion") else ""
        ofihotel = {"estado": "migrado", "detalle": f"Está en OfiHotel{sitio}, según los datos de ayer", "habitacion": encontrada.get("habitacion", ""),
                    "inferida": encontrada["inferida"]}
    elif exp["estado"] == "cancelada":
        ofihotel = {"estado": "no_aplica", "detalle": "Cancelada y sin rastro en OfiHotel"}
    elif t["ofihotel_alta"]["estado"] == "hecho":
        ofihotel = {"estado": "marcado", "detalle": "Marcada como pasada a OfiHotel; la lectura de mañana lo confirmará"}
    else:
        ofihotel = {"estado": "por_migrar", "detalle": "Todavía no está en OfiHotel"}

    restante = parte_restante_h(exp, ahora)
    if exp["estado"] == "cancelada":
        documentacion = {"estado": "no_aplica", "detalle": "Sin documentación: la reserva está cancelada"}
    elif exp["parte"]:
        documentacion = {"estado": "parte_enviado", "detalle": f"Parte enviado, justificante {exp['parte']['justificante']} (simulado)"}
    elif restante is not None and restante <= 0:
        documentacion = {"estado": "parte_vencido", "detalle": "El parte está fuera de plazo"}
    elif t["huesped"]["estado"] == "hecho" and t["pago"]["estado"] == "hecho":
        documentacion = {"estado": "parte_pendiente", "detalle": f"Quedan {_horas(restante)} h para enviar el parte" if restante is not None else "Falta enviar el parte"}
    elif t["huesped"]["estado"] == "hecho":
        documentacion = {"estado": "incompleta", "detalle": "Faltan el medio de pago o los datos de la empresa"}
    else:
        documentacion = {"estado": "sin_datos", "detalle": "Faltan los datos del huésped"}
    return {"roomcloud": roomcloud, "ofihotel": ofihotel, "documentacion": documentacion}


def conflictos(db: dict, ahora: datetime) -> list[dict]:
    """Conflictos globales entre RoomCloud, OfiHotel y la ocupación, con el expediente afectado cuando lo hay."""
    hoy = ahora.date().isoformat()
    salida = []
    for c in disponibilidad.conflictos(db, hoy):
        if c["nivel"] == "overbooking":
            salida.append({"tipo": "overbooking", "nivel": "rojo", "expediente_id": None, "sistemas": ["roomcloud", "ofihotel"],
                           "texto": f"Overbooking en {c['tipo']} el {_corta(c['fecha'])}: {c['ocupadas']} ocupadas para {c['capacidad']}"})
    for exp in db["expedientes"].values():
        encontrada = buscar_en_ofihotel(db, exp)
        if not encontrada:
            continue
        nombre = nombre_de(exp)
        if exp["estado"] == "cancelada":
            if encontrada["estado"] in ("reservada", "en_casa"):
                salida.append({"tipo": "cancelada_activa_en_ofihotel", "nivel": "gris", "expediente_id": exp["id"], "sistemas": ["roomcloud", "ofihotel"],
                               "texto": f"{nombre}: cancelada en RoomCloud pero todavía viva en OfiHotel"})
            continue
        if (encontrada["entrada"], encontrada["salida"]) != (exp["checkin_prevista"], exp["checkout_prevista"]):
            salida.append({"tipo": "fechas_distintas", "nivel": "rojo", "expediente_id": exp["id"], "sistemas": ["roomcloud", "ofihotel"],
                           "texto": (f"{nombre}: RoomCloud dice del {_corta(exp['checkin_prevista'])} al {_corta(exp['checkout_prevista'])} "
                                     f"y OfiHotel del {_corta(encontrada['entrada'])} al {_corta(encontrada['salida'])}")})
    vistas: dict[str, list[dict]] = {}
    for e in lectura_ofihotel(db).get("estancias", []):
        if e.get("estado") in ("reservada", "en_casa") and e.get("habitacion"):
            for otra in vistas.setdefault(e["habitacion"], []):
                if _solapan(e["entrada"], e["salida"], otra["entrada"], otra["salida"]):
                    salida.append({"tipo": "habitacion_doble", "nivel": "rojo", "expediente_id": None, "sistemas": ["ofihotel"],
                                   "texto": f"Habitación {e['habitacion']} con dos estancias solapadas en OfiHotel ({otra['huesped']} y {e['huesped']})"})
            vistas[e["habitacion"]].append(e)
    for i, c in enumerate(salida, 1):
        c["id"] = f"cf-{i}"
    return salida


def semaforo_de(db: dict, exp: dict, ahora: datetime, sistemas: dict | None = None, lista: list[dict] | None = None) -> dict:
    sistemas = sistemas or sistemas_de(db, exp, ahora)
    propios = [c for c in (lista if lista is not None else conflictos(db, ahora)) if c["expediente_id"] == exp["id"]]
    hoy = ahora.date().isoformat()
    doc, ofi = sistemas["documentacion"]["estado"], sistemas["ofihotel"]["estado"]
    rojos = [c for c in propios if c["nivel"] == "rojo"]
    if rojos:
        return _sem("rojo", rojos[0]["texto"], "Revisar el conflicto")
    if doc == "parte_vencido":
        return _sem("rojo", "El parte de viajeros está fuera de plazo", "Enviar el parte ya")
    if doc == "parte_pendiente" or (exp["estado"] == "en_curso" and doc in ("sin_datos", "incompleta")):
        return _sem("naranja", sistemas["documentacion"]["detalle"], "Completar y enviar el parte")
    grises = [c for c in propios if c["nivel"] == "gris"]
    if grises:
        return _sem("gris", grises[0]["texto"], "Anularla en OfiHotel")
    if exp["estado"] == "cancelada":
        return _sem("gris", "Reserva cancelada", "")
    if ofi in ("por_migrar", "sin_lectura") and exp["checkin_prevista"] <= hoy and exp["estado"] != "cancelada":
        return _sem("amarillo", "Falta pasarla a OfiHotel", "Pasarla a OfiHotel")
    if exp["estado"] == "pendiente_llegada" and exp["checkin_prevista"] <= hoy:
        return _sem("azul", "Llega hoy y no tiene check-in", "Hacer el check-in")
    return _sem("verde", "Todo cuadrado", "")


def _sem(color: str, motivo: str, accion: str) -> dict:
    return {"color": color, "tono": TONOS[color], "motivo": motivo, "accion_sugerida": accion}


def contadores(estancias: list[dict]) -> dict:
    cuenta = {c: 0 for c in COLORES}
    for e in estancias:
        cuenta[e["semaforo"]["color"]] += 1
    return cuenta
