"""Bloques del chat: tarjetas, listas, tablas, procesos y formularios que el servidor construye a partir de datos del hotel.

Seguridad (obligatoria). Los bloques y sus acciones salen de lo que hay en el almacén y nunca del texto que escribe el modelo:
el modelo solo elige herramientas, y aquí se decide qué se pinta. Todos los textos son texto plano, sin HTML, y las acciones
usan únicamente los tipos de la lista cerrada del contrato (`ACCIONES`, apartado 4.2 de CONTRATO-CORE.md).

El respaldo sin LLM (`para_mensaje`) reconoce el tema por palabras clave y devuelve la lista de bloques adecuada.
"""
import copy
import re
import unicodedata
from datetime import timedelta

from . import chat_procesos, comunicaciones, disponibilidad, estados, prioridades

ACCIONES = {"preguntar", "abrir_seccion", "abrir_estancia", "abrir_comunicacion", "confirmar_comunicacion", "descartar_comunicacion",
            "aprobar_propuesta", "rechazar_propuesta", "enviar_formulario", "sincronizar", "simular_roomcloud", "marcar_ofihotel"}
TONOS = {"neutro", "ok", "aviso", "critico", "info"}
ORIGENES = {"roomcloud": "RoomCloud", "ofihotel": "OfiHotel", "walk-in": "Walk-in", "mensaje": "Petición confirmada por recepción"}
MAX_ITEMS = 6
PROCESOS = list(chat_procesos.PROCESOS)
FILTROS = {"todas": "Estancias", "hoy": "Llegadas de hoy", "en_casa": "Estancias en casa", "salidas": "Salidas de hoy"}
DESTINOS = {
    "fuente": ("Fuente única", "Todas las fuentes unificadas y la cola de trabajo", "layers"),
    "comunicaciones": ("Comunicaciones", "Peticiones contrastadas, listas para confirmar", "inbox"),
    "estancias": ("Estancias", "Estado de cada estancia en RoomCloud, OfiHotel y documentación", "key"),
    "ocupacion": ("Ocupación", "Mapa de habitaciones libres y ocupadas por fuente", "bed"),
    "asistente": ("Asistente", "Pregunta, enseña los procesos y ejecuta lo básico", "sparkles"),
}
PASOS = [("huesped", "Datos del huésped", "documento"), ("pago", "Pago", "pago"), ("empresa", "Datos de la empresa", "pago"),
         ("parte", "Parte de viajeros", "parte"), ("ofihotel_alta", "Alta en OfiHotel", "ofihotel")]


# ================================================================ utilidades

def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _principal():
    from . import main  # import perezoso: main importa el chat
    return main


def _hoy(store) -> str:
    return store.ahora().date().isoformat()


def _fecha_corta(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def _item(etiqueta: str, valor, detalle: str = "", tono: str = "neutro") -> dict:
    return {"etiqueta": etiqueta, "valor": str(valor), "detalle": detalle, "tono": tono}


def _lista_conflictos(store) -> list[dict]:
    return estados.conflictos(store.db, store.ahora())


def _estancias(store, lista: list[dict] | None = None) -> list[dict]:
    """Resumen de todas las estancias, con su semáforo, ordenadas por color, llegada y nombre."""
    principal = _principal()
    lista = _lista_conflictos(store) if lista is None else lista
    todas = [principal.resumen(e, lista) for e in store.db["expedientes"].values()]
    todas.sort(key=lambda r: (estados.COLORES.index(r["semaforo"]["color"]), r["checkin"], r["huesped"]))
    return todas


def _abiertas(store) -> list[dict]:
    return comunicaciones.listar(store, "pendientes", "todos")


def expediente_nombrado(store, mensaje: str) -> dict | None:
    """Estancia cuyo huésped se nombra en el mensaje (por nombre o apellido), o None. Gana la que más palabras comparte."""
    palabras = set(re.findall(r"[a-z0-9]{3,}", _sin_tildes(mensaje.lower())))
    mejor, mejor_n = None, 0
    for exp in store.db["expedientes"].values():
        if exp["estado"] == "cancelada":
            continue
        h = exp["huesped"]
        nombres = " ".join([exp["reserva"]["nombre"], exp["reserva"]["apellidos"], h.get("nombre", ""), h.get("apellido1", ""),
                            h.get("apellido2", "")])
        coincidencias = len(palabras & set(re.findall(r"[a-z0-9]{3,}", _sin_tildes(nombres.lower()))))
        if coincidencias > mejor_n:
            mejor, mejor_n = exp, coincidencias
    return mejor


# ================================================================ constructores de bloques

def bloque_resumen_kpi(store) -> dict:
    exps = [e for e in store.db["expedientes"].values() if e["estado"] != "cancelada"]
    hoy = _hoy(store)
    llegadas = [e for e in exps if e["checkin_prevista"] == hoy]
    hechos = sum(e["estado"] != "pendiente_llegada" for e in llegadas)
    partes = sum(e["estado"] == "en_curso" and e["tramites"]["parte"]["estado"] != "hecho" for e in exps)
    abiertas = _abiertas(store)
    conflictos = len(_lista_conflictos(store))
    return {"tipo": "resumen_kpi", "titulo": "Hoy", "items": [
        _item("Llegadas", len(llegadas), f"{hechos} con check-in hecho" if llegadas else ""),
        _item("En casa", sum(e["estado"] == "en_curso" for e in exps)),
        _item("Peticiones por confirmar", len(abiertas), "Correo y WhatsApp" if abiertas else "", "aviso" if abiertas else "ok"),
        _item("Conflictos", conflictos, "Entre RoomCloud y OfiHotel" if conflictos else "", "critico" if conflictos else "ok"),
        _item("Partes pendientes", partes, "Plazo de 24 horas" if partes else "", "aviso" if partes else "ok")]}


def bloque_lista_estancias(store, filtro: str = "todas", color: str | None = None) -> dict:
    """Estancias filtradas. Sin filtro ni color se muestran las que tienen algo pendiente (todas menos las verdes)."""
    if filtro not in FILTROS:
        filtro = "todas"
    if color is not None and color not in estados.COLORES:
        color = None
    hoy = _hoy(store)
    lista = _lista_conflictos(store)
    todas = _estancias(store, lista)
    filtros = {"hoy": lambda r: r["checkin"] == hoy and r["estado"] != "cancelada", "en_casa": lambda r: r["estado"] == "en_curso",
               "salidas": lambda r: r["checkout"] == hoy and r["estado"] != "cancelada", "todas": lambda r: True}
    elegidas = [r for r in todas if filtros[filtro](r) and (color is None or r["semaforo"]["color"] == color)]
    if filtro == "todas" and color is None:
        elegidas = [r for r in elegidas if r["semaforo"]["color"] != "verde"]
        titulo = "Estancias con algo pendiente"
    elif color is not None:
        titulo = f"{FILTROS[filtro]} en {color}"
    else:
        titulo = FILTROS[filtro]
    return {"tipo": "lista_estancias", "titulo": titulo, "contadores": estados.contadores(todas), "estancias": elegidas}


def bloque_tarjeta_estancia(store, exp_id: str) -> dict:
    """Tarjeta de una estancia. Lanza KeyError si no existe."""
    exp = store.db["expedientes"][exp_id]
    r = _principal().resumen(exp, _lista_conflictos(store))
    sem = r["semaforo"]
    chips = [{"texto": _titulo_color(sem["color"]), "tono": sem["tono"]}]
    if exp["estado"] == "en_curso":
        enviado = r["parte"] == "hecho"
        chips.append({"texto": "Parte enviado" if enviado else "Parte pendiente", "tono": "ok" if enviado else "aviso"})
    elif exp["estado"] == "pendiente_llegada":
        chips.append({"texto": "Pendiente de llegada", "tono": "info"})
    campos = [{"etiqueta": "Origen", "valor": ORIGENES.get(r["origen"], r["origen"])}, {"etiqueta": "Personas", "valor": str(r["personas"])},
              {"etiqueta": "Viaja por trabajo", "valor": "Sí" if r["viaja_por_trabajo"] else "No"}]
    return {"tipo": "tarjeta_reserva", "id": r["id"], "titulo": r["huesped"],
            "subtitulo": f"{_fecha_corta(r['checkin'])} a {_fecha_corta(r['checkout'])} · {r['tipo']}" if r["tipo"] else
            f"{_fecha_corta(r['checkin'])} a {_fecha_corta(r['checkout'])}",
            "chips": chips, "campos": campos, "prioridad": r["prioridad"], "semaforo": sem, "sistemas": r["sistemas"],
            "acciones": [{"tipo": "abrir_estancia", "etiqueta": "Abrir", "id": r["id"]}]}


def _titulo_color(color: str) -> str:
    return next(x["titulo"] for x in estados.LEYENDA if x["color"] == color)


def bloque_lista_comunicaciones(store, estado: str = "pendientes", canal: str = "todos") -> dict:
    lista = comunicaciones.listar(store, estado, canal)
    titulo = {"pendientes": "Peticiones por confirmar", "respondida": "Comunicaciones respondidas",
              "descartada": "Comunicaciones descartadas"}.get(estado, "Comunicaciones")
    if canal in ("whatsapp", "correo"):
        titulo += " por WhatsApp" if canal == "whatsapp" else " por correo"
    return {"tipo": "lista_comunicaciones", "titulo": titulo, "comunicaciones": lista,
            "acciones": [{"tipo": "abrir_seccion", "etiqueta": "Abrir las comunicaciones", "seccion": "comunicaciones",
                          "params": {"canal": canal} if canal in ("whatsapp", "correo") else {}}]}


def bloque_comunicacion(store, com_id: str) -> dict:
    """Una comunicación completa (con contraste y respuesta) y sus acciones. Lanza ErrorNegocio si no existe."""
    com = comunicaciones.vista(store, comunicaciones.obtener(store, com_id))
    acciones = []
    if com["estado"] in comunicaciones.ABIERTAS:
        por = "WhatsApp" if com["canal"] == "whatsapp" else "correo"
        acciones += [{"tipo": "confirmar_comunicacion", "etiqueta": f"Confirmar y enviar por {por}", "id": com["id"]},
                     {"tipo": "descartar_comunicacion", "etiqueta": "Descartar", "id": com["id"]}]
    acciones.append({"tipo": "abrir_comunicacion", "etiqueta": "Abrir", "id": com["id"]})
    return {"tipo": "comunicacion", "comunicacion": com, "acciones": acciones}


def bloque_fuentes(store) -> dict:
    return {"tipo": "fuentes", "titulo": "De dónde bebe la aplicación", "fuentes": comunicaciones.fuentes(store),
            "prioridades": {"niveles": copy.deepcopy(prioridades.NIVELES), "reglas": list(prioridades.REGLAS)},
            "acciones": [{"tipo": "sincronizar", "etiqueta": "Leer RoomCloud", "fuente": "roomcloud"},
                         {"tipo": "sincronizar", "etiqueta": "Leer OfiHotel", "fuente": "ofihotel"}]}


def bloque_prioridades(resaltar: str | None = None) -> dict:
    if resaltar not in {n["id"] for n in prioridades.NIVELES}:
        resaltar = None
    return {"tipo": "prioridades", "titulo": "Quién gana cuando dos cosas compiten",
            "prioridades": {"niveles": copy.deepcopy(prioridades.NIVELES), "reglas": list(prioridades.REGLAS)}, "resaltar": resaltar}


def bloque_cola(store) -> dict:
    return {"tipo": "cola", "titulo": "Qué atender primero", "items": comunicaciones.cola(store)}


def bloque_conflictos(store) -> dict:
    return {"tipo": "conflictos", "titulo": "Conflictos entre fuentes", "conflictos": _lista_conflictos(store)}


def bloque_tabla_ocupacion(store, dias: int = 7) -> dict:
    dias = max(1, min(dias, 30))
    mapa = disponibilidad.mapa(store.db, _hoy(store), dias)
    return {"tipo": "tabla_ocupacion", "fechas": mapa["fechas"], "filas": [
        {"tipo": tipo, "capacidad": datos["capacidad"],
         "celdas": [{"fecha": c["fecha"], "ocupadas": c["ocupadas"], "libres": c["libres"], "cerrado": c["cerrado_en_roomcloud"]}
                    for c in datos["dias"]]} for tipo, datos in mapa["tipos"].items()]}


def bloque_propuesta(store, prop_id: str) -> dict:
    """Bloque de una propuesta del almacén. Lanza KeyError si no existe."""
    prop = next((p for p in store.db["propuestas"] if p["id"] == prop_id), None)
    if prop is None:
        raise KeyError(prop_id)
    pendiente = prop["estado"] == "pendiente"
    return {"tipo": "propuesta", "id": prop["id"], "texto": prop["texto"], "plantilla": prop["plantilla"], "destino": prop["destino"],
            "origen": prop["origen"], "destinatario": prop["destinatario"], "estado": prop["estado"],
            "acciones": [{"tipo": "aprobar_propuesta", "etiqueta": "Aprobar", "id": prop["id"]},
                         {"tipo": "rechazar_propuesta", "etiqueta": "Rechazar", "id": prop["id"]}] if pendiente else []}


def bloque_navegacion(store, destinos: list[str]) -> dict:
    """Atajos a pantallas. Destinos válidos: fuente, comunicaciones, estancias, ocupacion y asistente."""
    cuenta = {"comunicaciones": len(_abiertas(store)), "fuente": len(comunicaciones.cola(store)),
              "estancias": sum(r["semaforo"]["color"] != "verde" for r in _estancias(store)),
              "ocupacion": len(disponibilidad.conflictos(store.db, _hoy(store), 7))}
    items = []
    for destino in destinos:
        if destino not in DESTINOS:
            continue
        titulo, descripcion, icono = DESTINOS[destino]
        item = {"seccion": destino, "titulo": titulo, "descripcion": descripcion, "icono": icono, "params": {}}
        if cuenta.get(destino):
            item["insignia"] = cuenta[destino]
        items.append(item)
    return {"tipo": "navegacion", "titulo": "Ir a una pantalla", "items": items}


def bloque_proceso(proceso_id: str) -> dict:
    """Proceso explicado paso a paso con datos fijos. Lanza KeyError si no existe."""
    return chat_procesos.proceso(proceso_id)


def bloque_formulario_walkin() -> dict:
    """Formulario de walk-in. Las fechas por defecto salen del reloj fijo de la demo y el front las rellena con la fecha real."""
    texto = lambda nombre, etiqueta, obligatorio=False: {"nombre": nombre, "etiqueta": etiqueta, "tipo": "texto", "opciones": [],  # noqa: E731
                                                         "valor": "", "obligatorio": obligatorio}
    tipos = list(disponibilidad.capacidad())
    hoy = _reloj_demo()
    return {"tipo": "formulario", "id": "walkin", "titulo": "Walk-in", "campos": [
        texto("nombre", "Nombre", True), texto("apellidos", "Apellidos"), texto("telefono", "Teléfono"),
        {"nombre": "tipo", "etiqueta": "Tipo de habitación", "tipo": "select", "opciones": tipos, "valor": tipos[0] if tipos else "",
         "obligatorio": True},
        {"nombre": "checkin", "etiqueta": "Llegada", "tipo": "fecha", "opciones": [], "valor": hoy.isoformat(), "obligatorio": True},
        {"nombre": "checkout", "etiqueta": "Salida", "tipo": "fecha", "opciones": [], "valor": (hoy + timedelta(days=1)).isoformat(),
         "obligatorio": True},
        {"nombre": "personas", "etiqueta": "Personas", "tipo": "numero", "opciones": [], "valor": "1", "obligatorio": True}],
        "envio": {"tipo": "enviar_formulario", "etiqueta": "Añadir walk-in", "formulario": "walkin"}}


def _reloj_demo():
    """Fecha actual del almacén de la aplicación (el reloj de la demo)."""
    try:
        return _principal().store.ahora().date()
    except Exception:  # noqa: BLE001 - sin almacén se usa la fecha fija de la demo
        from datetime import date
        return date(2026, 10, 24)


def bloque_aviso(tono: str, titulo: str, texto: str) -> dict:
    return {"tipo": "aviso", "tono": tono if tono in TONOS else "info", "titulo": titulo, "texto": texto}


def bloque_sugerencias(items: list[str]) -> dict:
    return {"tipo": "sugerencias", "items": items[:3]}


# ================================================================ del mensaje a los bloques

# El orden importa: gana el primer tema que encaje, de lo más concreto a lo más general.
TEMAS = [
    ("proceso", r"c[oó]mo (funciona|entra|se |es el|va |sale|pasa)|ens[eé][ñn]ame|expl[ií]ca|qu[eé] pasa (cuando|si)|el proceso|paso a paso"),
    ("reserva_fisica", r"walk-?in|sin reserva|reserva f[ií]sica|(a[ñn]adir|nueva|crear|hacer) (una )?reserva"),
    ("conflictos", r"conflict|discrepan|no coincid|desajust"),
    ("prioridades", r"prioridad|qui[eé]n gana|escalera|compit"),
    ("cola", r"atender primero|primero|cola|urgente|qu[eé] hago"),
    ("ir", r"\bir a\b|ll[eé]vame|abre |abrir |d[oó]nde est[aá]|pantalla|navega"),
    ("fuentes", r"fuentes?|sistemas|roomcloud|ofihotel|de d[oó]nde"),
    ("mensajes", r"comunicaci|mensaje|whatsapp|correo|e-?mail|petici|sin responder|por confirmar"),
    ("propuestas", r"propuesta|aprobar|cerrar la venta|cierre"),
    ("ocupacion", r"ocupaci|libre|disponib|complet|overbooking|habitaci"),
    ("partes", r"\bpartes?\b|ses\.hospedajes"),
    ("llegadas", r"estancia|en casa|salida|sem[aá]foro|llegad|hoy|check-?in|resumen|kpi"),
]
_TEMAS = [(tema, re.compile(patron)) for tema, patron in TEMAS]
_PROCESO_POR_PALABRA = [
    ("overbooking_cierre", r"overbooking|cierre|cerrar la venta"),
    ("reserva_canal", r"booking|reserva de canal|reserva del canal|expedia"),
    ("checkin_parte", r"check-?in|\bpartes?\b|\bses\b|hospedajes|llegada del hu[eé]sped|viajeros"),
    ("prioridades", r"prioridad|qui[eé]n gana|compit"),
    ("fuente_unica", r"fuente [uú]nica|unifica|sem[aá]foro|sistemas"),
    ("peticion_mensaje", r"whatsapp|correo|mensaje|petici|e-?mail"),
]


def tema_de(store, mensaje: str) -> tuple[str, dict | None]:
    """(tema, estancia nombrada). Si el mensaje nombra a un huésped y no encaja un tema más concreto, el tema es `estancia`."""
    bajo = mensaje.lower()
    exp = expediente_nombrado(store, mensaje)
    for tema, patron in _TEMAS:
        if patron.search(bajo):
            if tema == "llegadas" and exp:
                return "estancia", exp
            return tema, exp
    return ("estancia" if exp else "ayuda"), exp


def _proceso_de(mensaje: str) -> str | None:
    bajo = mensaje.lower()
    for proceso_id, patron in _PROCESO_POR_PALABRA:
        if re.search(patron, bajo):
            return proceso_id
    return None


def _filtro_de(bajo: str) -> str:
    if "salida" in bajo:
        return "salidas"
    if "en casa" in bajo:
        return "en_casa"
    if re.search(r"llegad|hoy|check-?in", bajo):
        return "hoy"
    return "todas"


def _por_tema(store, tema: str, mensaje: str, exp: dict | None) -> list[dict]:
    bajo = mensaje.lower()
    if tema == "proceso":
        proceso_id = _proceso_de(mensaje)
        return [bloque_proceso(proceso_id)] if proceso_id else [bloque_aviso(
            "info", "Procesos que puedo enseñar", "Dime cuál quieres ver: la petición por WhatsApp, la reserva de Booking, el check-in y el parte, "
            "el overbooking, la fuente única o las prioridades.")]
    if tema == "reserva_fisica":
        return [bloque_formulario_walkin()]
    if tema == "conflictos":
        bloque = bloque_conflictos(store)
        return [bloque] if bloque["conflictos"] else [bloque_aviso("ok", "Sin conflictos", "RoomCloud y OfiHotel coinciden en todas las estancias.")]
    if tema == "prioridades":
        resaltar = "correo" if "correo" in bajo else "whatsapp" if "whatsapp" in bajo else None
        return [bloque_prioridades(resaltar)]
    if tema == "cola":
        bloque = bloque_cola(store)
        return [bloque] if bloque["items"] else [bloque_aviso("ok", "Nada pendiente", "No hay nada en la cola de trabajo.")]
    if tema == "ir":
        pedidos = [d for d in DESTINOS if d in _sin_tildes(bajo) or (d == "fuente" and "fuente" in bajo)] or ["fuente", "comunicaciones", "estancias", "ocupacion"]
        return [bloque_navegacion(store, pedidos)]
    if tema == "fuentes":
        return [bloque_fuentes(store)]
    if tema == "mensajes":
        canal = "whatsapp" if "whatsapp" in bajo else "correo" if re.search(r"correo|e-?mail", bajo) else "todos"
        bloque = bloque_lista_comunicaciones(store, "pendientes", canal)
        bloque["comunicaciones"] = bloque["comunicaciones"][:MAX_ITEMS]
        return [bloque] if bloque["comunicaciones"] else [bloque_aviso("ok", "Todo respondido", "No hay peticiones ni mensajes por confirmar.")]
    if tema == "propuestas":
        ids = [p["id"] for p in store.db["propuestas"] if p["estado"] == "pendiente"]
        return [bloque_propuesta(store, i) for i in ids[:MAX_ITEMS]] or [bloque_aviso("ok", "Nada pendiente", "No hay propuestas esperando aprobación.")]
    if tema == "ocupacion":
        return [bloque_tabla_ocupacion(store)]
    if tema == "estancia" and exp:
        return [bloque_tarjeta_estancia(store, exp["id"])]
    if tema == "partes":
        bloque = bloque_lista_estancias(store, "todas", "naranja")
        return [bloque] if bloque["estancias"] else [bloque_aviso("ok", "Partes al día", "No hay partes de viajeros pendientes de enviar.")]
    if tema == "llegadas":
        filtro = _filtro_de(bajo)
        bloque = bloque_lista_estancias(store, filtro)
        bloque["estancias"] = bloque["estancias"][:MAX_ITEMS]
        if filtro != "todas" and not bloque["estancias"]:
            return [bloque_resumen_kpi(store), bloque_aviso("info", "Sin resultados", "No hay estancias que encajen con esa pregunta.")]
        return [bloque_resumen_kpi(store), bloque]
    return [bloque_aviso("info", "No he entendido la pregunta",
                         "Puedo enseñarte las comunicaciones, las estancias, la ocupación, las fuentes y cómo funcionan los procesos del hotel.")]


def sugerencias_de(tema: str, exp: dict | None, mensaje: str) -> list[str]:
    por_tema = {
        "proceso": ["Enséñame cómo entra una petición por WhatsApp", "¿Qué prioridades hay?", "¿Qué conflictos hay?"],
        "reserva_fisica": ["¿Cómo está la ocupación?", "¿Qué llegadas hay hoy?", "¿Qué conflictos hay?"],
        "conflictos": ["¿Qué atender primero?", "¿De dónde bebe la aplicación?", "Enséñame cómo funciona la fuente única"],
        "prioridades": ["Enséñame quién gana cuando dos fuentes compiten", "¿Qué peticiones hay por confirmar?", "¿Qué atender primero?"],
        "cola": ["¿Qué peticiones hay por confirmar?", "¿Qué conflictos hay?", "¿Cómo está la ocupación?"],
        "ir": ["¿Qué llegadas hay hoy?", "¿Qué peticiones hay por confirmar?", "¿Cómo está la ocupación?"],
        "fuentes": ["¿Qué prioridades hay?", "¿Qué atender primero?", "Enséñame cómo funciona la fuente única"],
        "mensajes": ["Enséñame cómo entra una petición por WhatsApp", "¿Qué prioridades hay?", "¿Cómo está la ocupación?"],
        "propuestas": ["¿Qué peticiones hay por confirmar?", "Enséñame cómo se evita un overbooking", "¿Cómo está la ocupación?"],
        "ocupacion": ["¿Qué llegadas hay hoy?", "Enséñame cómo se evita un overbooking", "Quiero añadir un walk-in"],
        "estancia": ["¿Qué conflictos hay?", "Enséñame el proceso del check-in al parte de viajeros", "¿Cómo está la ocupación?"],
        "partes": ["¿Qué llegadas hay hoy?", "¿Qué conflictos hay?", "Enséñame el proceso del check-in al parte de viajeros"],
        "llegadas": ["¿Qué conflictos hay?", "¿Cómo está la ocupación?", "Enséñame el proceso del check-in al parte de viajeros"],
    }
    base = por_tema.get(tema, ["¿Qué llegadas hay hoy?", "¿Qué peticiones hay por confirmar?", "Enséñame cómo funciona la fuente única"])
    return [s for s in base if s.lower() != mensaje.strip().lower()]


def para_mensaje(store, mensaje: str) -> list[dict]:
    """Bloques reales para una pregunta, según el tema que reconocen las palabras clave, y sugerencias en cualquier caso."""
    tema, exp = tema_de(store, mensaje)
    return _por_tema(store, tema, mensaje, exp) + [bloque_sugerencias(sugerencias_de(tema, exp, mensaje))]


def bloques_de_propuestas(store, ids: list[str]) -> list[dict]:
    """Un bloque `propuesta` por cada id que exista en el almacén."""
    existentes = {p["id"] for p in store.db["propuestas"]}
    return [bloque_propuesta(store, i) for i in ids if i in existentes]


def para_respuesta(store, mensaje: str, ids_propuestas: list[str]) -> list[dict]:
    """Como `para_mensaje`, más un bloque por cada propuesta que el asistente haya creado en esta respuesta."""
    bloques = para_mensaje(store, mensaje)
    ya = {b["id"] for b in bloques if b["tipo"] == "propuesta"}
    nuevas = bloques_de_propuestas(store, [i for i in ids_propuestas if i not in ya])
    return bloques[:-1] + nuevas + bloques[-1:]  # las sugerencias van siempre al final


def acciones_de(bloque: dict) -> list[dict]:
    """Todas las acciones que lleva un bloque, estén donde estén, para poder comprobar que son de la lista cerrada."""
    encontradas = []
    for clave in ("acciones", "accion", "envio"):
        valor = bloque.get(clave)
        encontradas += valor if isinstance(valor, list) else [valor] if isinstance(valor, dict) else []
    return encontradas


# ================================================================ bloques de muestra
# Un bloque de cada tipo con datos de la semilla `completa`. `/api/chat/bloques-muestra` los devuelve tal cual, sin leer el almacén,
# para poder desarrollar el pintado sin depender del resto. Los tests comprueban que cada uno tiene la forma del contrato.
_MUESTRA = [{'tipo': 'resumen_kpi',
  'titulo': 'Hoy',
  'items': [{'etiqueta': 'Llegadas', 'valor': '3', 'detalle': '2 con check-in hecho', 'tono': 'neutro'},
            {'etiqueta': 'En casa', 'valor': '2', 'detalle': '', 'tono': 'neutro'},
            {'etiqueta': 'Peticiones por confirmar', 'valor': '6', 'detalle': 'Correo y WhatsApp', 'tono': 'aviso'},
            {'etiqueta': 'Conflictos', 'valor': '2', 'detalle': 'Entre RoomCloud y OfiHotel', 'tono': 'critico'},
            {'etiqueta': 'Partes pendientes', 'valor': '1', 'detalle': 'Plazo de 24 horas', 'tono': 'aviso'}]},
 {'tipo': 'tarjeta_reserva',
  'id': '2-EX-7730021',
  'titulo': 'Claire Dubois',
  'subtitulo': '24/10 a 27/10 · DBL-STD',
  'chips': [{'texto': 'Conflicto', 'tono': 'critico'}, {'texto': 'Pendiente de llegada', 'tono': 'info'}],
  'campos': [{'etiqueta': 'Origen', 'valor': 'RoomCloud'},
             {'etiqueta': 'Personas', 'valor': '2'},
             {'etiqueta': 'Viaja por trabajo', 'valor': 'No'}],
  'prioridad': {'nivel': 1, 'fuente': 'RoomCloud', 'id': 'roomcloud', 'tipo': 'firme'},
  'semaforo': {'color': 'rojo',
               'tono': 'critico',
               'motivo': 'Claire Dubois: RoomCloud dice del 24/10 al 27/10 y OfiHotel del 24/10 al 26/10',
               'accion_sugerida': 'Revisar el conflicto'},
  'sistemas': {'roomcloud': {'estado': 'sincronizado', 'detalle': 'Leída de RoomCloud'},
               'ofihotel': {'estado': 'migrado',
                            'detalle': 'Está en OfiHotel (hab. 105), según los datos de ayer',
                            'habitacion': '105',
                            'inferida': False},
               'documentacion': {'estado': 'sin_datos', 'detalle': 'Faltan los datos del huésped'}},
  'acciones': [{'tipo': 'abrir_estancia', 'etiqueta': 'Abrir', 'id': '2-EX-7730021'}]},
 {'tipo': 'lista_estancias',
  'titulo': 'Estancias con algo pendiente',
  'contadores': {'rojo': 1, 'naranja': 1, 'amarillo': 1, 'azul': 0, 'gris': 1, 'verde': 0},
  'estancias': [{'id': '2-EX-7730021',
                 'huesped': 'Claire Dubois',
                 'estado': 'pendiente_llegada',
                 'checkin': '2026-10-24',
                 'checkout': '2026-10-27',
                 'pendientes': ['huesped', 'pago', 'parte'],
                 'parte': 'pendiente',
                 'parte_restante_h': None,
                 'viaja_por_trabajo': False,
                 'tipo': 'DBL-STD',
                 'origen': 'roomcloud',
                 'personas': 2,
                 'prioridad': {'nivel': 1, 'fuente': 'RoomCloud', 'id': 'roomcloud', 'tipo': 'firme'},
                 'sistemas': {'roomcloud': {'estado': 'sincronizado', 'detalle': 'Leída de RoomCloud'},
                              'ofihotel': {'estado': 'migrado',
                                           'detalle': 'Está en OfiHotel (hab. 105), según los datos de ayer',
                                           'habitacion': '105',
                                           'inferida': False},
                              'documentacion': {'estado': 'sin_datos', 'detalle': 'Faltan los datos del huésped'}},
                 'semaforo': {'color': 'rojo',
                              'tono': 'critico',
                              'motivo': 'Claire Dubois: RoomCloud dice del 24/10 al 27/10 y OfiHotel del 24/10 al 26/10',
                              'accion_sugerida': 'Revisar el conflicto'}},
                {'id': '0-WEB-90112',
                 'huesped': 'Marcos Vilas',
                 'estado': 'en_curso',
                 'checkin': '2026-10-24',
                 'checkout': '2026-10-25',
                 'pendientes': ['parte'],
                 'parte': 'pendiente',
                 'parte_restante_h': 24.0,
                 'viaja_por_trabajo': False,
                 'tipo': 'SGL-STD',
                 'origen': 'roomcloud',
                 'personas': 1,
                 'prioridad': {'nivel': 1, 'fuente': 'RoomCloud', 'id': 'roomcloud', 'tipo': 'firme'},
                 'sistemas': {'roomcloud': {'estado': 'sincronizado', 'detalle': 'Leída de RoomCloud'},
                              'ofihotel': {'estado': 'por_migrar', 'detalle': 'Todavía no está en OfiHotel'},
                              'documentacion': {'estado': 'parte_pendiente', 'detalle': 'Quedan 24.0 h para enviar el parte'}},
                 'semaforo': {'color': 'naranja',
                              'tono': 'aviso',
                              'motivo': 'Quedan 24.0 h para enviar el parte',
                              'accion_sugerida': 'Completar y enviar el parte'}}]},
 {'tipo': 'comunicacion',
  'comunicacion': {'id': 'cm-0005',
                   'ts': '2026-10-24T08:52',
                   'hora': '08:52',
                   'canal': 'whatsapp',
                   'de': {'nombre': 'Lucía Fernández', 'contacto': '34655123123'},
                   'asunto': '',
                   'texto': 'Hola, ¿tenéis una doble libre del 28 al 30 de octubre? Somos 2 personas.',
                   'tipo': 'peticion_habitacion',
                   'idioma': 'es',
                   'peticion': {'tipo_habitacion': 'DBL-STD',
                                'desde': '2026-10-28',
                                'hasta': '2026-10-30',
                                'noches': 2,
                                'personas': 2,
                                'habitaciones': 1},
                   'prioridad': {'nivel': 5, 'fuente': 'WhatsApp', 'id': 'whatsapp', 'tipo': 'peticion'},
                   'estado': 'pendiente',
                   'expediente_id': None,
                   'contraste': {'veredicto': 'disponible',
                                 'motivo': 'Hay 3 libres todas las noches.',
                                 'noches': [{'fecha': '2026-10-28',
                                             'capacidad': 3,
                                             'ocupadas': 0,
                                             'libres': 3,
                                             'retenidas': 0,
                                             'libres_para_esta': 3,
                                             'por_fuente': {'roomcloud': 0, 'ofihotel': 0, 'recepcion': 0},
                                             'ocupantes': {'roomcloud': [], 'ofihotel': [], 'recepcion': []},
                                             'retenida_por': []},
                                            {'fecha': '2026-10-29',
                                             'capacidad': 3,
                                             'ocupadas': 0,
                                             'libres': 3,
                                             'retenidas': 0,
                                             'libres_para_esta': 3,
                                             'por_fuente': {'roomcloud': 0, 'ofihotel': 0, 'recepcion': 0},
                                             'ocupantes': {'roomcloud': [], 'ofihotel': [], 'recepcion': []},
                                             'retenida_por': []}],
                                 'bloqueada_por': [],
                                 'retenida_por': [],
                                 'alternativa': None},
                   'respuesta': {'canal': 'whatsapp',
                                 'destinatario': '34655123123',
                                 'asunto': '',
                                 'texto': 'Hola Lucía, buenos días. Sí tenemos una habitación doble libre del 28 de octubre al 30 de '
                                          'octubre (2 noches). Te la dejamos reservada a tu nombre; si necesitas cualquier cambio, dínoslo '
                                          'por aquí. ¡Te esperamos!',
                                 'idioma': 'es'},
                   'alerta': None,
                   'resultado': None},
  'acciones': [{'tipo': 'confirmar_comunicacion', 'etiqueta': 'Confirmar y enviar por WhatsApp', 'id': 'cm-0005'},
               {'tipo': 'descartar_comunicacion', 'etiqueta': 'Descartar', 'id': 'cm-0005'},
               {'tipo': 'abrir_comunicacion', 'etiqueta': 'Abrir', 'id': 'cm-0005'}]},
 {'tipo': 'lista_comunicaciones',
  'titulo': 'Peticiones por confirmar',
  'comunicaciones': [{'id': 'cm-0001',
                      'ts': '2026-10-24T07:58',
                      'hora': '07:58',
                      'canal': 'correo',
                      'de': {'nombre': 'Sophie Martin', 'contacto': 'sophie.martin@example.fr'},
                      'asunto': 'Demande de chambre du 24 au 27 octobre',
                      'texto': "Bonjour, avez-vous une chambre double de libre du 24 au 27 octobre pour 2 personnes ? Merci d'avance.",
                      'tipo': 'peticion_habitacion',
                      'idioma': 'fr',
                      'peticion': {'tipo_habitacion': 'DBL-STD',
                                   'desde': '2026-10-24',
                                   'hasta': '2026-10-27',
                                   'noches': 3,
                                   'personas': 2,
                                   'habitaciones': 1},
                      'prioridad': {'nivel': 4, 'fuente': 'Correo', 'id': 'correo', 'tipo': 'peticion'},
                      'estado': 'pendiente',
                      'expediente_id': None,
                      'contraste': {'veredicto': 'no_disponible',
                                    'motivo': 'El 24 de octubre no queda ninguna habitación doble libre: lo ocupan RoomCloud (2) y '
                                              'OfiHotel (1), con más prioridad que esta petición.',
                                    'noches': [{'fecha': '2026-10-24',
                                                'capacidad': 3,
                                                'ocupadas': 3,
                                                'libres': 0,
                                                'retenidas': 0,
                                                'libres_para_esta': 0,
                                                'por_fuente': {'roomcloud': 2, 'ofihotel': 1, 'recepcion': 0},
                                                'ocupantes': {'roomcloud': ['Ana Pereira', 'Claire Dubois'],
                                                              'ofihotel': ['García'],
                                                              'recepcion': []},
                                                'retenida_por': []},
                                               {'fecha': '2026-10-25',
                                                'capacidad': 3,
                                                'ocupadas': 2,
                                                'libres': 1,
                                                'retenidas': 0,
                                                'libres_para_esta': 1,
                                                'por_fuente': {'roomcloud': 2, 'ofihotel': 0, 'recepcion': 0},
                                                'ocupantes': {'roomcloud': ['Ana Pereira', 'Claire Dubois'],
                                                              'ofihotel': [],
                                                              'recepcion': []},
                                                'retenida_por': []},
                                               {'fecha': '2026-10-26',
                                                'capacidad': 3,
                                                'ocupadas': 2,
                                                'libres': 1,
                                                'retenidas': 0,
                                                'libres_para_esta': 1,
                                                'por_fuente': {'roomcloud': 1, 'ofihotel': 1, 'recepcion': 0},
                                                'ocupantes': {'roomcloud': ['Claire Dubois'], 'ofihotel': ['Rey'], 'recepcion': []},
                                                'retenida_por': []}],
                                    'bloqueada_por': [{'fuente': 'RoomCloud',
                                                       'id': 'roomcloud',
                                                       'nivel': 1,
                                                       'cantidad': 2,
                                                       'ocupantes': ['Ana Pereira', 'Claire Dubois']},
                                                      {'fuente': 'OfiHotel',
                                                       'id': 'ofihotel',
                                                       'nivel': 2,
                                                       'cantidad': 1,
                                                       'ocupantes': ['García']}],
                                    'retenida_por': [],
                                    'alternativa': {'desde': '2026-10-25', 'hasta': '2026-10-28', 'noches': 3}},
                      'respuesta': {'canal': 'correo',
                                    'destinatario': 'sophie.martin@example.fr',
                                    'asunto': 'Re: Demande de chambre du 24 au 27 octobre',
                                    'texto': "Bonjour Sophie, nous sommes désolés : du 24 octobre au 27 octobre nous n'avons plus de "
                                             'chambre double libre. Nous avons une chambre double de libre du 25 octobre au 28 octobre. '
                                             'Souhaitez-vous la réserver ?\n'
                                             '\n'
                                             'Cordialement,\n'
                                             'La réception',
                                    'idioma': 'fr'},
                      'alerta': None,
                      'resultado': None},
                     {'id': 'cm-0005',
                      'ts': '2026-10-24T08:52',
                      'hora': '08:52',
                      'canal': 'whatsapp',
                      'de': {'nombre': 'Lucía Fernández', 'contacto': '34655123123'},
                      'asunto': '',
                      'texto': 'Hola, ¿tenéis una doble libre del 28 al 30 de octubre? Somos 2 personas.',
                      'tipo': 'peticion_habitacion',
                      'idioma': 'es',
                      'peticion': {'tipo_habitacion': 'DBL-STD',
                                   'desde': '2026-10-28',
                                   'hasta': '2026-10-30',
                                   'noches': 2,
                                   'personas': 2,
                                   'habitaciones': 1},
                      'prioridad': {'nivel': 5, 'fuente': 'WhatsApp', 'id': 'whatsapp', 'tipo': 'peticion'},
                      'estado': 'pendiente',
                      'expediente_id': None,
                      'contraste': {'veredicto': 'disponible',
                                    'motivo': 'Hay 3 libres todas las noches.',
                                    'noches': [{'fecha': '2026-10-28',
                                                'capacidad': 3,
                                                'ocupadas': 0,
                                                'libres': 3,
                                                'retenidas': 0,
                                                'libres_para_esta': 3,
                                                'por_fuente': {'roomcloud': 0, 'ofihotel': 0, 'recepcion': 0},
                                                'ocupantes': {'roomcloud': [], 'ofihotel': [], 'recepcion': []},
                                                'retenida_por': []},
                                               {'fecha': '2026-10-29',
                                                'capacidad': 3,
                                                'ocupadas': 0,
                                                'libres': 3,
                                                'retenidas': 0,
                                                'libres_para_esta': 3,
                                                'por_fuente': {'roomcloud': 0, 'ofihotel': 0, 'recepcion': 0},
                                                'ocupantes': {'roomcloud': [], 'ofihotel': [], 'recepcion': []},
                                                'retenida_por': []}],
                                    'bloqueada_por': [],
                                    'retenida_por': [],
                                    'alternativa': None},
                      'respuesta': {'canal': 'whatsapp',
                                    'destinatario': '34655123123',
                                    'asunto': '',
                                    'texto': 'Hola Lucía, buenos días. Sí tenemos una habitación doble libre del 28 de octubre al 30 de '
                                             'octubre (2 noches). Te la dejamos reservada a tu nombre; si necesitas cualquier cambio, '
                                             'dínoslo por aquí. ¡Te esperamos!',
                                    'idioma': 'es'},
                      'alerta': None,
                      'resultado': None}],
  'acciones': [{'tipo': 'abrir_seccion', 'etiqueta': 'Abrir las comunicaciones', 'seccion': 'comunicaciones', 'params': {}}]},
 {'tipo': 'fuentes',
  'titulo': 'De dónde bebe la aplicación',
  'fuentes': [{'id': 'roomcloud',
               'nivel': 1,
               'tipo': 'firme',
               'nombre': 'RoomCloud',
               'icono': 'refresh',
               'estado': 'simulado',
               'recibido': 4,
               'detalle': '4 reservas de canal leídas',
               'ultima': '09:00',
               'entra': 'Reservas de Booking, Expedia y la web, con cancelaciones y cambios',
               'hoy': '2026-10-24'},
              {'id': 'ofihotel',
               'nivel': 2,
               'tipo': 'firme',
               'nombre': 'OfiHotel',
               'icono': 'building',
               'estado': 'simulado',
               'recibido': 7,
               'detalle': '7 estancias, datos hasta 23:59 de ayer',
               'ultima': '09:00',
               'entra': 'La copia diaria de SQL Server: quién está, quién llega y qué ya se pasó',
               'hoy': '2026-10-24'},
              {'id': 'recepcion',
               'nivel': 3,
               'tipo': 'firme',
               'nombre': 'Recepción',
               'icono': 'door',
               'estado': 'real',
               'recibido': 0,
               'detalle': 'Walk-ins y peticiones confirmadas',
               'ultima': None,
               'entra': 'Lo que recepción teclea o confirma desde la aplicación',
               'hoy': '2026-10-24'}],
  'prioridades': {'niveles': [{'nivel': 1,
                               'id': 'roomcloud',
                               'nombre': 'RoomCloud',
                               'tipo': 'firme',
                               'icono': 'refresh',
                               'descripcion': 'Reservas de Booking, Expedia y la web: confirmadas y con garantía de pago. Bloquean la '
                                              'habitación siempre.'},
                              {'nivel': 2,
                               'id': 'ofihotel',
                               'nombre': 'OfiHotel',
                               'tipo': 'firme',
                               'icono': 'building',
                               'descripcion': 'Lo que ya está registrado en el programa del hotel, con los datos de ayer.'}],
                  'reglas': ['Gana la fuente de mayor prioridad: lo firme (niveles 1 a 3) bloquea la habitación y una petición (niveles 4 '
                             'y 5) nunca la desplaza.',
                             'Entre dos peticiones por la misma habitación gana la de nivel más alto, y a igual nivel la que llegó antes.',
                             'Si entra una reserva de RoomCloud que ocupa el hueco de una petición, la petición pasa a «no disponible» y '
                             'se avisa.']},
  'acciones': [{'tipo': 'sincronizar', 'etiqueta': 'Leer RoomCloud', 'fuente': 'roomcloud'},
               {'tipo': 'sincronizar', 'etiqueta': 'Leer OfiHotel', 'fuente': 'ofihotel'}]},
 {'tipo': 'prioridades',
  'titulo': 'Quién gana cuando dos cosas compiten',
  'prioridades': {'niveles': [{'nivel': 1,
                               'id': 'roomcloud',
                               'nombre': 'RoomCloud',
                               'tipo': 'firme',
                               'icono': 'refresh',
                               'descripcion': 'Reservas de Booking, Expedia y la web: confirmadas y con garantía de pago. Bloquean la '
                                              'habitación siempre.'},
                              {'nivel': 2,
                               'id': 'ofihotel',
                               'nombre': 'OfiHotel',
                               'tipo': 'firme',
                               'icono': 'building',
                               'descripcion': 'Lo que ya está registrado en el programa del hotel, con los datos de ayer.'},
                              {'nivel': 3,
                               'id': 'recepcion',
                               'nombre': 'Recepción',
                               'tipo': 'firme',
                               'icono': 'door',
                               'descripcion': 'Reservas físicas y peticiones que recepción ya ha confirmado desde la aplicación.'}],
                  'reglas': ['Gana la fuente de mayor prioridad: lo firme (niveles 1 a 3) bloquea la habitación y una petición (niveles 4 '
                             'y 5) nunca la desplaza.',
                             'Entre dos peticiones por la misma habitación gana la de nivel más alto, y a igual nivel la que llegó antes.',
                             'Si entra una reserva de RoomCloud que ocupa el hueco de una petición, la petición pasa a «no disponible» y '
                             'se avisa.']},
  'resaltar': 'correo'},
 {'tipo': 'cola',
  'titulo': 'Qué atender primero',
  'items': [{'id': 'est-2-EX-7730021',
             'tipo': 'conflicto',
             'color': 'rojo',
             'titulo': 'Claire Dubois: RoomCloud dice del 24/10 al 27/10 y OfiHotel del 24/10 al 26/10',
             'detalle': 'Revisar el conflicto',
             'prioridad': {'nivel': 1, 'fuente': 'RoomCloud', 'id': 'roomcloud', 'tipo': 'firme'},
             'ts': '2026-10-24',
             'ruta': 'estancias',
             'params': {'id': '2-EX-7730021'}},
            {'id': 'est-0-WEB-90112',
             'tipo': 'parte',
             'color': 'naranja',
             'titulo': 'Marcos Vilas: Quedan 24.0 h para enviar el parte',
             'detalle': 'Completar y enviar el parte',
             'prioridad': {'nivel': 1, 'fuente': 'RoomCloud', 'id': 'roomcloud', 'tipo': 'firme'},
             'ts': '2026-10-24T09:00',
             'ruta': 'estancias',
             'params': {'id': '0-WEB-90112'}},
            {'id': 'est-1-BK-4471920',
             'tipo': 'migrar',
             'color': 'amarillo',
             'titulo': 'Ana Pereira: Falta pasarla a OfiHotel',
             'detalle': 'Pasarla a OfiHotel',
             'prioridad': {'nivel': 1, 'fuente': 'RoomCloud', 'id': 'roomcloud', 'tipo': 'firme'},
             'ts': '2026-10-24T09:00',
             'ruta': 'estancias',
             'params': {'id': '1-BK-4471920'}}]},
 {'tipo': 'conflictos',
  'titulo': 'Conflictos entre fuentes',
  'conflictos': [{'tipo': 'fechas_distintas',
                  'nivel': 'rojo',
                  'expediente_id': '2-EX-7730021',
                  'sistemas': ['roomcloud', 'ofihotel'],
                  'texto': 'Claire Dubois: RoomCloud dice del 24/10 al 27/10 y OfiHotel del 24/10 al 26/10',
                  'id': 'cf-1'},
                 {'tipo': 'cancelada_activa_en_ofihotel',
                  'nivel': 'gris',
                  'expediente_id': '1-BK-4488003',
                  'sistemas': ['roomcloud', 'ofihotel'],
                  'texto': 'Luis Otero: cancelada en RoomCloud pero todavía viva en OfiHotel',
                  'id': 'cf-2'}]},
 {'tipo': 'navegacion',
  'titulo': 'Ir a una pantalla',
  'items': [{'seccion': 'fuente',
             'titulo': 'Fuente única',
             'descripcion': 'Todas las fuentes unificadas y la cola de trabajo',
             'icono': 'layers',
             'params': {},
             'insignia': 10},
            {'seccion': 'comunicaciones',
             'titulo': 'Comunicaciones',
             'descripcion': 'Peticiones contrastadas, listas para confirmar',
             'icono': 'inbox',
             'params': {},
             'insignia': 6},
            {'seccion': 'estancias',
             'titulo': 'Estancias',
             'descripcion': 'Estado de cada estancia en RoomCloud, OfiHotel y documentación',
             'icono': 'key',
             'params': {},
             'insignia': 4},
            {'seccion': 'ocupacion',
             'titulo': 'Ocupación',
             'descripcion': 'Mapa de habitaciones libres y ocupadas por fuente',
             'icono': 'bed',
             'params': {},
             'insignia': 1},
            {'seccion': 'asistente',
             'titulo': 'Asistente',
             'descripcion': 'Pregunta, enseña los procesos y ejecuta lo básico',
             'icono': 'sparkles',
             'params': {}}]},
 {'tipo': 'proceso',
  'id': 'peticion_mensaje',
  'titulo': 'Cómo entra una petición por WhatsApp o correo',
  'resumen': 'Un huésped escribe pidiendo habitación. La aplicación entiende la petición, la contrasta con todas las fuentes, redacta la '
             'respuesta y recepción solo tiene que confirmarla.',
  'pasos': [{'id': 'recibir',
             'titulo': 'Llega el mensaje',
             'fuente': 'whatsapp',
             'detalle': 'Un huésped escribe por WhatsApp o por correo pidiendo habitación y la aplicación lo guarda en Comunicaciones con '
                        'la hora de llegada.',
             'dato': 'Prioridad 5 si llega por WhatsApp y prioridad 4 si llega por correo',
             'resultado': 'Mensaje recibido y sin confirmar'},
            {'id': 'entender',
             'titulo': 'La aplicación entiende la petición',
             'fuente': 'sistema',
             'detalle': 'Lee el texto, detecta el idioma y extrae el tipo de habitación, las fechas, las noches y el número de personas.',
             'dato': 'Doble, del 28 al 30 de octubre, 2 personas',
             'resultado': 'Petición estructurada, lista para contrastar'},
            {'id': 'roomcloud',
             'titulo': 'Contrasta con RoomCloud',
             'fuente': 'roomcloud',
             'detalle': 'Cuenta las reservas de Booking, Expedia y la web que ya ocupan habitaciones esas noches. Son reservas firmes con '
                        'garantía de pago.',
             'dato': 'Prioridad 1: bloquea la habitación y ninguna petición la desplaza'},
            {'id': 'ofihotel',
             'titulo': 'Contrasta con OfiHotel',
             'fuente': 'ofihotel',
             'detalle': 'Suma lo que ya está registrado en el programa del hotel. OfiHotel es de solo lectura y llega con los datos de '
                        'ayer.',
             'dato': 'Prioridad 2, con la copia de ayer'},
            {'id': 'recepcion',
             'titulo': 'Contrasta con recepción',
             'fuente': 'recepcion',
             'detalle': 'Suma los walk-ins y las peticiones que recepción ya ha confirmado desde la aplicación.',
             'dato': 'Prioridad 3: también es firme'},
            {'id': 'priorizar',
             'titulo': 'Decide quién gana',
             'fuente': 'sistema',
             'detalle': 'Compara con las demás peticiones abiertas para las mismas noches. Gana el nivel más alto y, a igual nivel, la que '
                        'llegó antes.',
             'dato': 'Libres para esta petición: 1 de 3 en las dos noches',
             'resultado': 'Veredicto: disponible'},
            {'id': 'redactar',
             'titulo': 'Redacta la respuesta',
             'fuente': 'sistema',
             'detalle': 'Prepara un borrador en el idioma del huésped con las fechas, el tipo de habitación y el siguiente paso. Recepción '
                        'puede editarlo.',
             'resultado': 'Borrador listo para revisar'},
            {'id': 'enviar',
             'titulo': 'Recepción confirma y la respuesta sale por el mismo canal',
             'fuente': 'recepcion',
             'detalle': 'Al pulsar confirmar, la respuesta sale por el canal por el que llegó la petición y la habitación queda reservada. '
                        'El envío es simulado en esta demo.',
             'resultado': 'Petición respondida y habitación reservada con prioridad 3'}],
  'acciones': [{'tipo': 'abrir_seccion', 'etiqueta': 'Ver las comunicaciones', 'seccion': 'comunicaciones', 'params': {}},
               {'tipo': 'abrir_seccion', 'etiqueta': 'Ver la fuente única', 'seccion': 'fuente', 'params': {}}]},
 {'tipo': 'tabla_ocupacion',
  'fechas': ['2026-10-24', '2026-10-25', '2026-10-26'],
  'filas': [{'tipo': 'DBL-STD',
             'capacidad': 3,
             'celdas': [{'fecha': '2026-10-24', 'ocupadas': 3, 'libres': 0, 'cerrado': False},
                        {'fecha': '2026-10-25', 'ocupadas': 2, 'libres': 1, 'cerrado': False},
                        {'fecha': '2026-10-26', 'ocupadas': 2, 'libres': 1, 'cerrado': False}]},
            {'tipo': 'SGL-STD',
             'capacidad': 2,
             'celdas': [{'fecha': '2026-10-24', 'ocupadas': 1, 'libres': 1, 'cerrado': False},
                        {'fecha': '2026-10-25', 'ocupadas': 0, 'libres': 2, 'cerrado': False},
                        {'fecha': '2026-10-26', 'ocupadas': 0, 'libres': 2, 'cerrado': False}]}]},
 {'tipo': 'propuesta',
  'id': 'pr-0005',
  'texto': 'Cerrar la venta de DBL-STD del 2026-10-24 al 2026-10-25 en RoomCloud',
  'plantilla': 'cerrar_disponibilidad',
  'destino': 'roomcloud',
  'origen': 'ocupación',
  'destinatario': '',
  'estado': 'pendiente',
  'acciones': [{'tipo': 'aprobar_propuesta', 'etiqueta': 'Aprobar', 'id': 'pr-0005'},
               {'tipo': 'rechazar_propuesta', 'etiqueta': 'Rechazar', 'id': 'pr-0005'}]},
 {'tipo': 'formulario',
  'id': 'walkin',
  'titulo': 'Walk-in',
  'campos': [{'nombre': 'nombre', 'etiqueta': 'Nombre', 'tipo': 'texto', 'opciones': [], 'valor': '', 'obligatorio': True},
             {'nombre': 'apellidos', 'etiqueta': 'Apellidos', 'tipo': 'texto', 'opciones': [], 'valor': '', 'obligatorio': False},
             {'nombre': 'telefono', 'etiqueta': 'Teléfono', 'tipo': 'texto', 'opciones': [], 'valor': '', 'obligatorio': False},
             {'nombre': 'tipo',
              'etiqueta': 'Tipo de habitación',
              'tipo': 'select',
              'opciones': ['DBL-STD', 'SGL-STD'],
              'valor': 'DBL-STD',
              'obligatorio': True},
             {'nombre': 'checkin', 'etiqueta': 'Llegada', 'tipo': 'fecha', 'opciones': [], 'valor': '2026-10-24', 'obligatorio': True},
             {'nombre': 'checkout', 'etiqueta': 'Salida', 'tipo': 'fecha', 'opciones': [], 'valor': '2026-10-25', 'obligatorio': True},
             {'nombre': 'personas', 'etiqueta': 'Personas', 'tipo': 'numero', 'opciones': [], 'valor': '1', 'obligatorio': True}],
  'envio': {'tipo': 'enviar_formulario', 'etiqueta': 'Añadir walk-in', 'formulario': 'walkin'}},
 {'tipo': 'aviso', 'tono': 'info', 'titulo': 'Sin resultados', 'texto': 'No hay estancias que encajen con esa pregunta.'},
 {'tipo': 'sugerencias',
  'items': ['¿Qué llegadas hay hoy?', '¿Qué peticiones hay por confirmar?', 'Enséñame cómo funciona la fuente única']}]


def bloques_muestra() -> list[dict]:
    return copy.deepcopy(_MUESTRA)


# ================================================================ sugerencias de bienvenida

def sugerencias_bienvenida() -> dict:
    """Pantalla de bienvenida del asistente: cinco categorías con tres preguntas y una tarjeta por proceso."""
    tarjetas = chat_procesos.TARJETAS
    return {"categorias": [
        {"id": "hoy", "titulo": "Hoy", "icono": "sun",
         "preguntas": ["¿Qué llegadas hay hoy?", "¿Qué atender primero?", "¿Qué conflictos hay?"]},
        {"id": "comunicaciones", "titulo": "Comunicaciones", "icono": "inbox",
         "preguntas": ["¿Qué peticiones hay por confirmar?", "¿Qué mensajes han llegado por WhatsApp?", "¿Qué prioridad tiene cada fuente?"]},
        {"id": "estancias", "titulo": "Estancias", "icono": "key",
         "preguntas": ["¿Qué estancias tienen algo pendiente?", "¿Quién está en casa ahora mismo?", "¿Qué salidas hay hoy?"]},
        {"id": "ocupacion", "titulo": "Ocupación", "icono": "bed",
         "preguntas": ["¿Cómo está la ocupación?", "¿Qué propuestas hay pendientes de aprobar?", "Quiero añadir un walk-in"]},
        {"id": "procesos", "titulo": "Procesos", "icono": "layers",
         "preguntas": [tarjetas["peticion_mensaje"][0], tarjetas["checkin_parte"][0], tarjetas["fuente_unica"][0]]}],
        "flujos": [{"id": pid, "titulo": chat_procesos.proceso(pid)["titulo"], "icono": tarjetas[pid][1], "pregunta": tarjetas[pid][0],
                    "descripcion": tarjetas[pid][2]} for pid in PROCESOS]}
