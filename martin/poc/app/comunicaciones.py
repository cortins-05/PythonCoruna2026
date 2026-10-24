"""Comunicaciones recibidas por WhatsApp y correo, ya contrastadas con todas las fuentes y listas para confirmar y responder.

Es la pantalla central de la demo: cada mensaje que llega se entiende (¿es una petición de habitación?), se contrasta con RoomCloud, OfiHotel
y las reservas físicas aplicando la escalera de prioridades de `prioridades.py`, y recepción solo tiene que confirmar el borrador de respuesta,
que sale por el mismo canal por el que llegó la petición.

FACHADA DE DEMO. El contraste y la redacción son reales sobre los datos del almacén, pero la comprensión del mensaje usa reglas deterministas
(fechas, personas y tipo de habitación en español, francés e inglés) para que la demo no dependa de la red, y los envíos son simulados.
"""
import re
import unicodedata
from datetime import date, datetime, timedelta

from . import disponibilidad, estados, hub, plantillas, prioridades

ABIERTAS = ("pendiente", "en_espera")
HORIZONTE_ALTERNATIVA = 14
NOMBRE_CANAL = {"correo": "correo", "whatsapp": "WhatsApp"}
TEXTO_MAX = 2000
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12, "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
NUMEROS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "one": 1, "two": 2,
           "three": 3, "four": 4, "five": 5, "six": 6, "deux": 2, "trois": 3, "quatre": 4}
NOMBRE_MES = {"es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
              "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
              "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}
NOMBRE_TIPO = {"es": {"DBL-STD": "habitación doble", "SGL-STD": "habitación individual", "TPL-STD": "habitación triple",
                      "FAM-STD": "habitación familiar", "SUI-STD": "suite"},
               "fr": {"DBL-STD": "chambre double", "SGL-STD": "chambre simple", "TPL-STD": "chambre triple",
                      "FAM-STD": "chambre familiale", "SUI-STD": "suite"},
               "en": {"DBL-STD": "double room", "SGL-STD": "single room", "TPL-STD": "triple room",
                      "FAM-STD": "family room", "SUI-STD": "suite"}}
PLURALES = {"habitación": "habitaciones", "individual": "individuales", "doble": "dobles", "triple": "triples", "familiar": "familiares",
            "suite": "suites", "chambre": "chambres", "simple": "simples", "double": "doubles", "familiale": "familiales", "room": "rooms"}

RANGO_MES = re.compile(r"(\d{1,2})(?:\s+de)?(?:\s+([a-z]{3,}))?\s+(?:al|au|to|hasta(?:\s+el)?|a)\s+(\d{1,2})(?:\s+de)?\s+([a-z]{3,})")
RANGO_NUM = re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-]\d{2,4})?\s*(?:al|a|-|to|au|hasta)\s*(\d{1,2})[/-](\d{1,2})")
RANGO_DIAS_NUM = re.compile(r"(?<![\d/-])(\d{1,2})\s*(?:al|a|-|to|au|hasta)\s*(\d{1,2})[/-](\d{1,2})(?!\d)")
RANGO_MES_PRIMERO = re.compile(r"([a-z]{3,})\s+(\d{1,2})(?:st|nd|rd|th)?\s*(?:to|-|until)\s*(?:([a-z]{3,})\s+)?(\d{1,2})(?:st|nd|rd|th)?")
PALABRAS_PETICION = re.compile(r"habitaci|libre|disponib|reserv|room|chambre|doble|individual|single|double|triple|familiar|family|famille|suite|alojamiento|noche|nuit|night|plaza")
PALABRAS_PREGUNTA = re.compile(r"check-?in|check-?out|hora|horario|parking|desayuno|wifi|direccion|como llegar|aparcamiento")
PALABRAS_CAMBIO = re.compile(r"cancel|anular|cambiar|modificar|adelantar|retrasar|un dia antes|un dia despues")


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()


def _mes(token: str) -> int | None:
    if token in MESES:
        return MESES[token]
    if len(token) >= 3:
        for nombre, numero in MESES.items():
            if nombre.startswith(token):
                return numero
    return None


def _fecha(dia: int, mes: int, hoy: date) -> date | None:
    try:
        f = date(hoy.year, mes, dia)
    except ValueError:
        return None
    return f if f >= hoy else date(hoy.year + 1, mes, dia)


NUM_RE = r"\d+|un|una|uno|dos|tres|cuatro|cinco|seis|one|two|three|four|five|six|deux|trois|quatre"


def _numero(token: str) -> int | None:
    return int(token) if token.isdigit() else NUMEROS.get(token)


def extraer_fechas(texto: str, hoy: date) -> tuple[str, str] | None:
    n = _sin_tildes(texto)
    m = RANGO_MES.search(n)
    if m:
        d1, mes1, d2, mes2 = int(m.group(1)), _mes(m.group(2) or ""), int(m.group(3)), _mes(m.group(4))
        mes1 = mes1 or mes2
        if mes1 and mes2:
            desde, hasta = _fecha(d1, mes1, hoy), _fecha(d2, mes2, hoy)
            if desde and hasta:
                if hasta <= desde:
                    hasta = _fecha(d2, mes2, desde + timedelta(days=1)) or hasta
                return desde.isoformat(), hasta.isoformat()
    m = RANGO_NUM.search(n)
    if m:
        desde, hasta = _fecha(int(m.group(1)), int(m.group(2)), hoy), _fecha(int(m.group(3)), int(m.group(4)), hoy)
        if desde and hasta and hasta > desde:
            return desde.isoformat(), hasta.isoformat()
    m = RANGO_DIAS_NUM.search(n)
    if m:
        mes = int(m.group(3))
        desde, hasta = _fecha(int(m.group(1)), mes, hoy), _fecha(int(m.group(2)), mes, hoy)
        if desde and hasta and hasta > desde:
            return desde.isoformat(), hasta.isoformat()
    m = RANGO_MES_PRIMERO.search(n)
    if m and _mes(m.group(1)) and (not m.group(3) or _mes(m.group(3))):
        mes1 = _mes(m.group(1))
        mes2 = _mes(m.group(3)) if m.group(3) else mes1
        desde, hasta = _fecha(int(m.group(2)), mes1, hoy), _fecha(int(m.group(4)), mes2, hoy)
        if desde and hasta:
            if hasta <= desde:
                hasta = _fecha(int(m.group(4)), mes2, desde + timedelta(days=1)) or hasta
            return desde.isoformat(), hasta.isoformat()
    if re.search(r"esta noche|tonight|ce soir|para hoy", n):
        return hoy.isoformat(), (hoy + timedelta(days=1)).isoformat()
    if re.search(r"(?<!esta )\bmanana\b|tomorrow|demain", n):
        return (hoy + timedelta(days=1)).isoformat(), (hoy + timedelta(days=2)).isoformat()
    return None


def extraer_personas(texto: str) -> int | None:
    n = _sin_tildes(texto)
    for patron in (r"\b(" + NUM_RE + r")\s*(?:personas?|pers|adultos?|people|persons?|guests?|personnes?|pax|adults?)\b",
                   r"\bsomos\s+(" + NUM_RE + r")\b", r"\bfor\s+(" + NUM_RE + r")\b(?!\s*(?:nights?|nuits?|noches?|rooms?|habitaci))",
                   r"\bpour\s+(" + NUM_RE + r")\b(?!\s*(?:nuits?|noches?|nights?|chambres?))"):
        m = re.search(patron, n)
        if m and _numero(m.group(1)):
            return _numero(m.group(1))
    return None


def extraer_habitaciones(texto: str) -> int:
    m = re.search(r"\b(" + NUM_RE + r")\s+(?:(?:double|single|triple|family|twin)\s+)?"
                  r"(?:habitaciones|habitacion|rooms?|chambres?|dobles|individuales|triples|familiares|suites)\b", _sin_tildes(texto))
    return max(1, min(_numero(m.group(1)) or 1, 10)) if m else 1


PERSONAS_POR_TIPO = {"SGL-STD": 1, "DBL-STD": 2, "TPL-STD": 3, "FAM-STD": 4, "SUI-STD": 2}


def extraer_tipo(texto: str, personas: int | None) -> str:
    n = _sin_tildes(texto)
    if re.search(r"\bsuite", n):
        return "SUI-STD"
    if re.search(r"familiar|family|familiale|\bfam\b", n):
        return "FAM-STD"
    if re.search(r"\btriple|\btpl\b", n):
        return "TPL-STD"
    if re.search(r"individual|single|sencilla|simple|\bsgl\b|chambre simple", n):
        return "SGL-STD"
    if re.search(r"doble|double|matrimonio|twin|\bdbl\b", n):
        return "DBL-STD"
    if personas is None:
        return "DBL-STD"
    return "SGL-STD" if personas <= 1 else "DBL-STD" if personas == 2 else "TPL-STD" if personas == 3 else "FAM-STD"


def idioma_de(texto: str) -> str:
    n = _sin_tildes(texto)
    if re.search(r"\b(bonjour|chambre|avez-vous|je voudrais|nous voudrions|merci|pour|nuit|cordialement)\b", n):
        return "fr"
    if re.search(r"\b(hello|hi|dear|room|available|nights?|please|thanks|regards)\b", n) and not re.search(r"\b(hola|buenas|habitacion|gracias)\b", n):
        return "en"
    return "es"


def analizar(texto: str, asunto: str, hoy: date) -> dict:
    """Entiende el mensaje: tipo, petición de habitación si la hay e idioma. Reglas deterministas, sin red."""
    completo = f"{asunto}\n{texto}".strip()
    n = _sin_tildes(completo)
    fechas = extraer_fechas(completo, hoy)
    idioma = idioma_de(completo)
    if fechas and PALABRAS_PETICION.search(n):
        personas = extraer_personas(completo)
        desde, hasta = fechas
        return {"tipo": "peticion_habitacion", "idioma": idioma,
                "peticion": {"tipo_habitacion": extraer_tipo(completo, personas), "desde": desde, "hasta": hasta,
                             "noches": (date.fromisoformat(hasta) - date.fromisoformat(desde)).days, "personas": personas or PERSONAS_POR_TIPO.get(extraer_tipo(completo, personas), 2),
                             "habitaciones": extraer_habitaciones(completo)}}
    if PALABRAS_CAMBIO.search(n):
        return {"tipo": "cambio", "idioma": idioma, "peticion": None}
    if PALABRAS_PREGUNTA.search(n):
        return {"tipo": "pregunta", "idioma": idioma, "peticion": None}
    return {"tipo": "otro", "idioma": idioma, "peticion": None}


# ================================================================ contraste con las fuentes

def _ids_de(db: dict) -> dict[str, str]:
    return {i: estados.nombre_de(e) for i, e in db["expedientes"].items()}


def _gana(otra: dict, esta: dict) -> bool:
    """¿La petición `otra` tiene prioridad sobre `esta`? Mayor nivel (número menor) y, a igual nivel, la que llegó antes."""
    return (otra["prioridad"]["nivel"], otra["ts"], otra["id"]) < (esta["prioridad"]["nivel"], esta["ts"], esta["id"])


def _noches(desde: str, hasta: str) -> list[str]:
    return list(disponibilidad._dias(desde, hasta))


def _retenciones(store, com: dict, tipo: str, fecha: str) -> list[dict]:
    """Peticiones abiertas, distintas de ésta, que ganan a ésta y se quedan con una habitación del tipo esa noche."""
    return [c for c in store.db.get("comunicaciones", []) if c["id"] != com["id"] and c["estado"] in ABIERTAS and c.get("peticion")
            and c["peticion"]["tipo_habitacion"] == tipo and c["peticion"]["desde"] <= fecha < c["peticion"]["hasta"] and _gana(c, com)]


def contrastar(store, com: dict, peticion: dict | None = None) -> dict:
    """Contrasta la petición con las tres fuentes que bloquean habitaciones y con las peticiones que la superan en prioridad."""
    p = peticion or com["peticion"]
    tipo, n = p["tipo_habitacion"], p["habitaciones"]
    capacidad = disponibilidad.capacidad().get(tipo)
    if capacidad is None:
        nombre_tipo = NOMBRE_TIPO["es"].get(tipo, tipo)
        return {"veredicto": "sin_datos", "motivo": f"El inventario no incluye {nombre_tipo}: recepción lo comprueba a mano.",
                "noches": [], "bloqueada_por": [],
                "retenida_por": [], "alternativa": None}
    nombres, filas = _ids_de(store.db), disponibilidad.ocupaciones(store.db)
    noches = []
    for fecha in _noches(p["desde"], p["hasta"]):
        ocupantes = {"roomcloud": [], "ofihotel": [], "recepcion": []}
        for o in filas:
            if o["tipo"] == tipo and o["desde"] <= fecha < o["hasta"]:
                ocupantes[prioridades.grupo_de_origen(o["fuente"])].append(nombres.get(str(o["quien"]), str(o["quien"])))
        retenidas = _retenciones(store, com, tipo, fecha)
        firmes = sum(len(v) for v in ocupantes.values())
        reservadas = sum(c["peticion"]["habitaciones"] for c in retenidas)
        noches.append({"fecha": fecha, "capacidad": capacidad, "ocupadas": firmes, "libres": capacidad - firmes, "retenidas": reservadas,
                       "libres_para_esta": capacidad - firmes - reservadas,
                       "por_fuente": {k: len(v) for k, v in ocupantes.items()}, "ocupantes": ocupantes,
                       "retenida_por": [c["id"] for c in retenidas]})
    peor_firme = min(noches, key=lambda x: x["libres"])
    peor_mia = min(noches, key=lambda x: x["libres_para_esta"])
    bloqueada, retenida = [], []
    if peor_firme["libres"] < n:
        veredicto = "no_disponible"
        for grupo in ("roomcloud", "ofihotel", "recepcion"):
            quienes = peor_firme["ocupantes"][grupo]
            if quienes:
                info = prioridades.info(grupo)
                bloqueada.append({"fuente": info["fuente"], "id": grupo, "nivel": info["nivel"], "cantidad": len(quienes), "ocupantes": quienes})
        quien = " y ".join(f"{b['fuente']} {b['cantidad']}" for b in bloqueada)
        libres = max(0, peor_firme["libres"])
        queda = ("no queda ninguna " + NOMBRE_TIPO["es"][tipo] + " libre" if libres == 0
                 else f"solo queda{'n' if libres > 1 else ''} {_tipo_plural(tipo, libres, 'es')} libre{'s' if libres > 1 else ''} y pide {n}")
        motivo = f"El {_fecha_larga(peor_firme['fecha'], 'es')} {queda}: {quien}, con más prioridad."
    elif peor_mia["libres_para_esta"] < n:
        veredicto = "en_competencia"
        ganadoras = [c for c in _retenciones(store, com, tipo, peor_mia["fecha"])]
        retenida = [{"comunicacion": c["id"], "de": c["de"]["nombre"], "canal": c["canal"], "nivel": c["prioridad"]["nivel"],
                     "fuente": c["prioridad"]["fuente"], "hora": c["ts"][11:16]} for c in ganadoras]
        primera = retenida[0]
        motivo = (f"La petición por {primera['fuente'].lower()} de {primera['de']}, de las {primera['hora']}, tiene más prioridad "
                  f"que esta, nivel {primera['nivel']} frente a {com['prioridad']['nivel']}, y se queda con la última habitación.")
    elif peor_mia["libres_para_esta"] == n:
        veredicto, motivo = "ajustado", f"Queda justo lo que pide y después no sobra ninguna {NOMBRE_TIPO['es'][tipo]}."
    else:
        libres = peor_mia["libres_para_esta"]
        veredicto, motivo = "disponible", (f"Queda{'n' if libres > 1 else ''} {_tipo_plural(tipo, libres, 'es')} libre{'s' if libres > 1 else ''} "
                                           f"todas las noches.")
    alternativa = _alternativa(store, com, p, nombres) if veredicto in ("no_disponible", "en_competencia") else None
    return {"veredicto": veredicto, "motivo": motivo, "noches": noches, "bloqueada_por": bloqueada, "retenida_por": retenida,
            "alternativa": alternativa}


def _alternativa(store, com: dict, p: dict, nombres: dict) -> dict | None:
    """Primer hueco del mismo número de noches, pasadas las fechas pedidas, en el que sí cabe la petición."""
    largo, n = p["noches"], p["habitaciones"]
    base = date.fromisoformat(p["desde"])
    for salto in range(1, HORIZONTE_ALTERNATIVA + 1):
        desde = (base + timedelta(days=salto)).isoformat()
        hasta = (base + timedelta(days=salto + largo)).isoformat()
        prueba = dict(p, desde=desde, hasta=hasta)
        c = contrastar_sin_alternativa(store, com, prueba)
        if c in ("disponible", "ajustado"):
            return {"desde": desde, "hasta": hasta, "noches": largo}
    return None


def contrastar_sin_alternativa(store, com: dict, p: dict) -> str:
    capacidad = disponibilidad.capacidad().get(p["tipo_habitacion"], 0)
    filas = disponibilidad.ocupaciones(store.db)
    for fecha in _noches(p["desde"], p["hasta"]):
        firmes = sum(1 for o in filas if o["tipo"] == p["tipo_habitacion"] and o["desde"] <= fecha < o["hasta"])
        retenidas = sum(c["peticion"]["habitaciones"] for c in _retenciones(store, com, p["tipo_habitacion"], fecha))
        if capacidad - firmes - retenidas < p["habitaciones"]:
            return "no_disponible"
    return "disponible"


# ================================================================ borrador de respuesta

def _fecha_larga(iso: str, idioma: str) -> str:
    d = date.fromisoformat(iso)
    mes = NOMBRE_MES[idioma][d.month - 1]
    return f"{d.day} de {mes}" if idioma == "es" else (f"{d.day} {mes}" if idioma == "fr" else f"{mes} {d.day}")


def _tipo_plural(tipo: str, n: int, idioma: str) -> str:
    base = NOMBRE_TIPO[idioma].get(tipo, tipo)
    if n == 1:
        return f"una {base}" if idioma == "es" else (f"une {base}" if idioma == "fr" else f"a {base}")
    if base == tipo:  # tipo sin nombre conocido
        return f"{n} × {tipo}"
    palabras = [PLURALES.get(w, w) for w in base.split()]
    if idioma == "en" and len(palabras) == 2 and palabras[1] == "rooms":
        palabras = base.split()[:1] + ["rooms"]
    elif idioma == "en" and base == "suite":
        palabras = ["suites"]
    return f"{n} {' '.join(palabras)}"


def redactar(com: dict, contraste: dict | None) -> dict:
    """Borrador de respuesta por el mismo canal por el que llegó el mensaje. Recepción puede editarlo antes de confirmar."""
    idioma, nombre = com["idioma"], (com["de"]["nombre"].split() or ["", ""])[0]
    p = com.get("peticion")
    if p and contraste:
        v, alt = contraste["veredicto"], contraste.get("alternativa")
        d1, d2 = _fecha_larga(p["desde"], idioma), _fecha_larga(p["hasta"], idioma)
        cosa = _tipo_plural(p["tipo_habitacion"], p["habitaciones"], idioma)
        if v in ("disponible", "ajustado"):
            cuerpo = {"es": f"Hola {nombre}, sí tenemos {cosa} libre del {d1} al {d2}, {p['noches']} noche{'s' if p['noches'] != 1 else ''}. Te la dejamos reservada a tu nombre.",
                      "fr": f"Bonjour {nombre}, nous avons {cosa} de libre du {d1} au {d2}, {p['noches']} nuit{'s' if p['noches'] != 1 else ''}. Nous vous la réservons à votre nom.",
                      "en": f"Hello {nombre}, we have {cosa} available from {d1} to {d2}, {p['noches']} night{'s' if p['noches'] != 1 else ''}. We have booked it in your name."}[idioma]
        elif v == "sin_datos":
            cuerpo = {"es": f"Hola {nombre}, estamos comprobando si tenemos {cosa} del {d1} al {d2} y te respondemos en breve.",
                      "fr": f"Bonjour {nombre}, nous vérifions si nous avons {cosa} du {d1} au {d2} et nous vous répondons rapidement.",
                      "en": f"Hello {nombre}, we are checking whether we have {cosa} from {d1} to {d2} and will reply shortly."}[idioma]
        elif v == "en_competencia":
            cuerpo = {"es": f"Hola {nombre}, estamos confirmando otra consulta para esas fechas y en unos minutos te decimos si podemos reservártela.",
                      "fr": f"Bonjour {nombre}, nous confirmons une autre demande pour ces dates et nous revenons vers vous dans quelques minutes.",
                      "en": f"Hello {nombre}, we are confirming another request for those dates and will tell you in a few minutes whether we can book it."}[idioma]
        else:
            extra = ""
            if alt:
                a1, a2 = _fecha_larga(alt["desde"], idioma), _fecha_larga(alt["hasta"], idioma)
                extra = {"es": f" Sí tenemos {cosa} del {a1} al {a2}. ¿Te la reservamos?",
                         "fr": f" Nous avons {cosa} de libre du {a1} au {a2}. Souhaitez-vous la réserver ?",
                         "en": f" We do have {cosa} available from {a1} to {a2}. Shall we book it?"}[idioma]
            cuerpo = {"es": f"Hola {nombre}, lo sentimos, del {d1} al {d2} no nos queda {NOMBRE_TIPO['es'][p['tipo_habitacion']]} libre.{extra}",
                      "fr": f"Bonjour {nombre}, désolés, du {d1} au {d2} nous n'avons plus de {NOMBRE_TIPO['fr'][p['tipo_habitacion']]} libre.{extra}",
                      "en": f"Hello {nombre}, sorry, from {d1} to {d2} we have no {NOMBRE_TIPO['en'][p['tipo_habitacion']]} left.{extra}"}[idioma]
    elif com["tipo"] == "pregunta":
        cuerpo = (f"Hola {nombre}, el check-in empieza a las {plantillas.HORAS['hora_checkin']} y el check-out termina a las "
                  f"{plantillas.HORAS['hora_checkout']}. ¿A qué hora llegas?")
    else:
        cuerpo = f"Hola {nombre}, lo revisamos y te respondemos en breve."
    firma = {"es": "\n\nUn saludo,\nRecepción", "fr": "\n\nCordialement,\nLa réception", "en": "\n\nKind regards,\nReception"}[idioma]
    asunto = f"Re: {com['asunto']}" if com["canal"] == "correo" and com.get("asunto") else ("Re: su consulta" if com["canal"] == "correo" else "")
    return {"canal": com["canal"], "destinatario": com["de"]["contacto"], "asunto": asunto,
            "texto": cuerpo + (firma if com["canal"] == "correo" else ""), "idioma": idioma}


# ================================================================ vida de una comunicación

def _db(store) -> list[dict]:
    return store.db.setdefault("comunicaciones", [])


def registrar(store, canal: str, nombre: str, contacto: str, texto: str, asunto: str = "", ts: str | None = None) -> dict:
    """Recibe un mensaje: lo entiende, lo enlaza con la estancia si es de un huésped conocido y lo deja pendiente de confirmar."""
    if canal not in ("whatsapp", "correo"):
        raise hub.ErrorNegocio("El canal tiene que ser whatsapp o correo", 422)
    texto, asunto, nombre = str(texto or "").strip(), str(asunto or "").strip()[:200], str(nombre or "").strip()[:80]
    if not texto or len(texto) > TEXTO_MAX:
        raise hub.ErrorNegocio(f"El mensaje no puede estar vacío ni pasar de {TEXTO_MAX} caracteres", 422)
    if canal == "correo":
        contacto = str(contacto or "").strip().lower()
        if not plantillas.email_valido(contacto):
            raise hub.ErrorNegocio("El remitente del correo no es una dirección válida", 422)
        exp = hub.buscar_por_correo(store.db, contacto)
    else:
        contacto = re.sub(r"\D", "", str(contacto or ""))
        if not 9 <= len(contacto) <= 15:
            raise hub.ErrorNegocio("El teléfono tiene que tener entre 9 y 15 cifras", 422)
        exp = hub.buscar_por_telefono(store.db, contacto)
    ahora = store.ahora()
    analisis = analizar(texto, asunto, ahora.date())
    store.db["cm_seq"] = store.db.get("cm_seq", 0) + 1
    com = {"id": f"cm-{store.db['cm_seq']:04d}", "ts": ts or ahora.isoformat(timespec="minutes"), "canal": canal,
           "de": {"nombre": nombre or contacto, "contacto": contacto}, "asunto": asunto, "texto": texto, "tipo": analisis["tipo"],
           "idioma": analisis["idioma"], "peticion": analisis["peticion"], "prioridad": prioridades.nivel_de_canal(canal),
           "estado": "pendiente", "expediente_id": exp["id"] if exp else None, "texto_editado": None, "alerta": None,
           "veredicto_visto": None, "resultado": None}
    _db(store).append(com)
    return com


def obtener(store, com_id: str) -> dict:
    com = next((c for c in _db(store) if c["id"] == com_id), None)
    if not com:
        raise hub.ErrorNegocio("Comunicación no encontrada", 404)
    return com


def vista(store, com: dict) -> dict:
    """Lo que ve la interfaz: la comunicación con su contraste y su borrador calculados ahora, y no cuando llegó."""
    cerrada = com["estado"] not in ABIERTAS
    if cerrada and com.get("contraste_final"):
        contraste = com["contraste_final"]  # lo que se vio al responder: la reserva que se crea al confirmar ya no cuenta como competencia
    else:
        contraste = contrastar(store, com) if com.get("peticion") else None
    if com["estado"] in ABIERTAS and contraste:
        previo, ahora_v = com.get("veredicto_visto"), contraste["veredicto"]
        if (previo in ("disponible", "ajustado") and ahora_v in ("no_disponible", "en_competencia")) or (
                previo == "en_competencia" and ahora_v == "no_disponible"):
            com["alerta"] = {"hora": store.ahora().isoformat(timespec="minutes"),
                             "texto": f"Ha dejado de estar disponible: {contraste['motivo']}"}
        elif ahora_v in ("disponible", "ajustado"):
            com["alerta"] = None
        com["veredicto_visto"] = ahora_v
    borrador = redactar(com, contraste)
    if com["texto_editado"] and com["estado"] in ABIERTAS:
        borrador["texto"] = com["texto_editado"]
    elif cerrada and com.get("resultado") and com["resultado"].get("texto"):
        borrador["texto"] = com["resultado"]["texto"]  # lo que se envió de verdad
    return {"id": com["id"], "ts": com["ts"], "hora": com["ts"][11:16], "canal": com["canal"], "de": com["de"], "asunto": com["asunto"],
            "texto": com["texto"], "tipo": com["tipo"], "idioma": com["idioma"], "peticion": com["peticion"], "prioridad": com["prioridad"],
            "estado": com["estado"], "expediente_id": com["expediente_id"], "contraste": contraste, "respuesta": borrador,
            "alerta": com["alerta"], "resultado": com["resultado"]}


def listar(store, estado: str | None = None, canal: str | None = None) -> list[dict]:
    todas = [c for c in _db(store) if (canal in (None, "todos") or c["canal"] == canal)]
    if estado == "pendientes":
        todas = [c for c in todas if c["estado"] in ABIERTAS]
    elif estado in ("respondida", "descartada", "pendiente", "en_espera"):
        todas = [c for c in todas if c["estado"] == estado]
    orden = {"pendiente": 0, "en_espera": 1, "respondida": 2, "descartada": 3}
    todas.sort(key=lambda c: (orden[c["estado"]], c["prioridad"]["nivel"], c["ts"]) if c["estado"] in ABIERTAS else (orden[c["estado"]], "", c["ts"]))
    return [vista(store, c) for c in todas]


def _crear_reserva(store, com: dict, p: dict) -> dict:
    from . import main
    numero = store.siguiente_id("m").split("-")[1]
    nombre = com["de"]["nombre"].split()
    por_habitacion = max(1, p["personas"] // p["habitaciones"])
    r = {"portal_id": "M", "id_canal": numero, "dlm": store.ahora().isoformat(timespec="minutes"), "estado_rc": "4",
         "checkin": p["desde"], "checkout": p["hasta"], "nombre": nombre[0] if nombre else "", "apellidos": " ".join(nombre[1:]),
         "telefono": com["de"]["contacto"] if com["canal"] == "whatsapp" else "", "email": com["de"]["contacto"] if com["canal"] == "correo" else "",
         "pais": "", "importe": "", "medio_pago": "", "notas": f"Reserva confirmada desde la comunicación {com['id']}",
         "habitaciones": [{"tipo": p["tipo_habitacion"], "tarifa": "", "adultos": str(por_habitacion), "ninos": "0"} for _ in range(p["habitaciones"])]}
    exp = main.nuevo_expediente(r)
    exp["origen"] = "mensaje"
    store.db["expedientes"][exp["id"]] = exp
    hub.registrar_evento(store, "recepcion", "reserva_por_mensaje", com["de"]["nombre"],
                         f"{com['de']['nombre']}: {estados._corta(p['desde'])} a {estados._corta(p['hasta'])}, confirmada por {com['canal']}", exp["id"],
                         {"comunicacion": com["id"]})
    return exp


def _enviar(store, com: dict, respuesta: dict, texto: str, actor: str, exp_id: str | None) -> None:
    if com["canal"] == "whatsapp":
        hub.registrar_evento(store, "whatsapp", "mensaje_saliente_simulado", remitente=com["de"]["contacto"], contenido=texto,
                             expediente_id=exp_id or com["expediente_id"],
                             datos={"wa_id": com["de"]["contacto"], "comunicacion": com["id"], "aprobado_por": actor})
    else:
        from .adapters import correo
        correo.enviar_simulado(store, com["de"]["contacto"], respuesta["asunto"] or "Re: su consulta", texto,
                               expediente_id=exp_id or com["expediente_id"], datos={"comunicacion": com["id"], "aprobado_por": actor})


def confirmar(store, com_id: str, actor: str = "Recepción", texto: str | None = None) -> dict:
    """Envía el borrador (editado o no) por el mismo canal. Si hay hueco, además reserva la habitación; si compite, deja la petición en espera."""
    com = obtener(store, com_id)
    if com["estado"] not in ABIERTAS:
        raise hub.ErrorNegocio("Esta comunicación ya está respondida", 409)
    v = vista(store, com)
    if texto is not None:
        texto = str(texto).strip()
        if not texto or len(texto) > TEXTO_MAX:
            raise hub.ErrorNegocio("El texto de la respuesta no puede estar vacío ni pasar de 2000 caracteres", 422)
        v["respuesta"]["texto"] = texto
    veredicto = v["contraste"]["veredicto"] if v["contraste"] else None
    exp_id, accion = None, "respondida"
    if veredicto in ("disponible", "ajustado"):
        exp_id, accion = _crear_reserva(store, com, com["peticion"])["id"], "reservada"
    elif veredicto == "en_competencia":
        accion = "en_espera"
    elif veredicto == "no_disponible":
        accion = "sin_hueco"
    _enviar(store, com, v["respuesta"], v["respuesta"]["texto"], actor, exp_id)
    com["estado"] = "en_espera" if accion == "en_espera" else "respondida"
    if com["estado"] == "respondida":
        com["contraste_final"] = v["contraste"]
    com["alerta"] = None
    com["resultado"] = {"hora": store.ahora().isoformat(timespec="minutes"), "canal": com["canal"], "destinatario": com["de"]["contacto"],
                        "texto": v["respuesta"]["texto"], "accion": accion, "reserva_id": exp_id, "actor": actor, "simulado": True}
    hub.revisar_ocupacion(store)
    return vista(store, com)


def descartar(store, com_id: str, actor: str = "Recepción") -> dict:
    com = obtener(store, com_id)
    if com["estado"] not in ABIERTAS:
        raise hub.ErrorNegocio("Esta comunicación ya está respondida", 409)
    com["contraste_final"] = vista(store, com)["contraste"]
    com["estado"] = "descartada"
    com["alerta"] = None
    com["resultado"] = {"hora": store.ahora().isoformat(timespec="minutes"), "canal": com["canal"], "destinatario": com["de"]["contacto"],
                        "texto": "", "accion": "descartada", "reserva_id": None, "actor": actor, "simulado": True}
    return vista(store, com)


def editar_texto(store, com_id: str, texto: str) -> dict:
    com = obtener(store, com_id)
    texto = str(texto or "").strip()
    if not texto or len(texto) > TEXTO_MAX:
        raise hub.ErrorNegocio("El texto no puede estar vacío ni pasar de 2000 caracteres", 422)
    com["texto_editado"] = texto
    return vista(store, com)


# ================================================================ fuente única: fuentes, cola de trabajo y actividad

ICONOS_EVENTO = {"roomcloud": "refresh", "ofihotel": "building", "whatsapp": "message", "correo": "mail", "recepcion": "door",
                 "sistema": "alert", "ses": "shield"}
TEXTOS_EVENTO = {"reserva_nueva": "Reserva nueva", "reserva_modificada": "Reserva modificada", "reserva_cancelada": "Reserva cancelada",
                 "instantanea_lectura": "Lectura de OfiHotel", "mensaje_saliente_simulado": "Respuesta por WhatsApp",
                 "correo_saliente_simulado": "Respuesta por correo", "walk_in": "Walk-in", "reserva_por_mensaje": "Reserva desde un mensaje",
                 "alerta_ocupacion": "Aviso de ocupación", "modify_simulado": "Venta cerrada en RoomCloud"}


def fuentes(store) -> list[dict]:
    db, ev = store.db, store.db["eventos"]
    comms = _db(store)
    lectura = estados.lectura_ofihotel(db)
    hoy = store.ahora().date().isoformat()

    def ultima(fuente: str) -> str | None:
        marcas = [e["ts"] for e in ev if e["fuente"] == fuente]
        return max(marcas)[11:16] if marcas else None

    def ultima_com(canal: str) -> str | None:
        marcas = [c["ts"] for c in comms if c["canal"] == canal]
        return max(marcas)[11:16] if marcas else None

    rc = [e for e in ev if e["fuente"] == "roomcloud" and e["tipo"] in ("reserva_nueva", "reserva_modificada", "reserva_cancelada")]
    rc_vivas = sum(1 for e in db["expedientes"].values() if e["origen"] == "roomcloud")
    partes = [e["parte"]["enviado_el"] for e in db["expedientes"].values() if e.get("parte")]
    ncorreo, nwa = sum(c["canal"] == "correo" for c in comms), sum(c["canal"] == "whatsapp" for c in comms)
    pend = lambda canal: sum(c["canal"] == canal and c["estado"] in ABIERTAS for c in comms)  # noqa: E731
    base = [
        {"id": "roomcloud", "nivel": prioridades.info("roomcloud")["nivel"], "tipo": "firme", "nombre": "RoomCloud", "icono": "refresh",
         "estado": "simulado", "recibido": rc_vivas, "detalle": f"{rc_vivas} reservas leídas", "ultima": ultima("roomcloud"),
         "entra": "Reservas de Booking, Expedia y la web"},
        {"id": "ofihotel", "nivel": prioridades.info("ofihotel")["nivel"], "tipo": "firme", "nombre": "OfiHotel", "icono": "building",
         "estado": "simulado" if lectura else "sin_lectura", "recibido": len(lectura.get("estancias", [])),
         "detalle": f"{len(lectura.get('estancias', []))} estancias, datos de ayer hasta las {lectura['datos_hasta'][11:16] if lectura else '-'}" if lectura else "Sin leer",
         "ultima": ultima("ofihotel"), "entra": "La copia diaria de SQL Server"},
        {"id": "recepcion", "nivel": prioridades.info("recepcion")["nivel"], "tipo": "firme", "nombre": "Recepción", "icono": "door",
         "estado": "real", "recibido": sum(1 for e in db["expedientes"].values() if e["origen"] in ("walk-in", "mensaje")),
         "detalle": "Walk-ins y peticiones confirmadas", "ultima": ultima("recepcion"),
         "entra": "Lo que recepción registra o confirma"},
        {"id": "correo", "nivel": prioridades.info("correo")["nivel"], "tipo": "peticion", "nombre": "Correo", "icono": "mail",
         "estado": "simulado", "recibido": ncorreo, "detalle": f"{pend('correo')} por confirmar de {ncorreo}", "ultima": ultima_com("correo"),
         "entra": "Peticiones y consultas por correo"},
        {"id": "whatsapp", "nivel": prioridades.info("whatsapp")["nivel"], "tipo": "peticion", "nombre": "WhatsApp", "icono": "message",
         "estado": "simulado", "recibido": nwa, "detalle": f"{pend('whatsapp')} por confirmar de {nwa}",
         "ultima": ultima_com("whatsapp"),
         "entra": "Peticiones y consultas por WhatsApp"},
    ]
    base.append({"id": "ses", "nivel": None, "tipo": "salida", "nombre": "SES.Hospedajes", "icono": "shield", "estado": "simulado",
                 "recibido": len(partes), "detalle": f"{len(partes)} partes de viajeros enviados", "ultima": max(partes)[11:16] if partes else None,
                 "entra": "Salida: el parte de viajeros de cada llegada"})
    for f in base:
        f["hoy"] = hoy
    return base


def cola(store) -> list[dict]:
    """Qué atender primero: ordenado por la prioridad de la fuente (RoomCloud antes que correo y WhatsApp) y, dentro de ella, por urgencia."""
    ahora, db = store.ahora(), store.db
    lista = estados.conflictos(db, ahora)
    items = []
    from . import main
    for exp in db["expedientes"].values():
        r = main.resumen(exp, lista)
        color = r["semaforo"]["color"]
        if color == "verde":
            continue
        tipo = {"rojo": "conflicto", "naranja": "parte", "amarillo": "migrar", "azul": "atender", "gris": "reflejar"}[color]
        motivo = r["semaforo"]["motivo"]
        items.append({"id": f"est-{exp['id']}", "tipo": tipo, "color": color,
                      "titulo": motivo if motivo.startswith(r["huesped"]) else f"{r['huesped']}: {motivo}",
                      "detalle": r["semaforo"]["accion_sugerida"], "prioridad": r["prioridad"], "ts": exp.get("checkin_hora") or exp["checkin_prevista"],
                      "ruta": "estancias", "params": {"id": exp["id"]}})
    for c in lista:
        if not c["expediente_id"]:
            items.append({"id": f"conf-{c['id']}", "tipo": "conflicto", "color": c["nivel"], "titulo": c["texto"], "detalle": "Revisar el conflicto",
                          "prioridad": prioridades.info("roomcloud" if "roomcloud" in c["sistemas"] else "ofihotel"), "ts": "", "ruta": "ocupacion", "params": {}})
    for c in _db(store):
        if c["estado"] in ABIERTAS:
            v = vista(store, c)
            hay_aviso = bool(v["alerta"]) or (v["contraste"] and v["contraste"]["veredicto"] in ("no_disponible", "en_competencia"))
            items.append({"id": f"com-{c['id']}", "tipo": "comunicacion", "color": "rojo" if v["alerta"] else "azul",
                          "titulo": f"{'Petición' if c['tipo'] == 'peticion_habitacion' else 'Mensaje'} por {NOMBRE_CANAL[c['canal']]} de {c['de']['nombre']}",
                          "detalle": (v["contraste"]["motivo"] if v["contraste"] and hay_aviso else "Responder"),
                          "prioridad": c["prioridad"], "ts": c["ts"], "ruta": "comunicaciones", "params": {"id": c["id"]}})
    items.sort(key=lambda i: (i["prioridad"]["nivel"], estados.COLORES.index(i["color"]), i["ts"]))
    return items


def peticiones_abiertas(store) -> list[dict]:
    """Peticiones de habitación por confirmar, para pintarlas encima del mapa de ocupación."""
    salida = []
    for c in _db(store):
        if c["estado"] in ABIERTAS and c.get("peticion"):
            v = vista(store, c)
            p = c["peticion"]
            salida.append({"id": c["id"], "canal": c["canal"], "prioridad": c["prioridad"], "de": c["de"]["nombre"], "hora": c["ts"][11:16],
                           "tipo_habitacion": p["tipo_habitacion"], "desde": p["desde"], "hasta": p["hasta"], "habitaciones": p["habitaciones"],
                           "veredicto": v["contraste"]["veredicto"] if v["contraste"] else "sin_datos"})
    return sorted(salida, key=lambda x: (x["prioridad"]["nivel"], x["hora"]))


def actividad(store, limite: int = 14) -> list[dict]:
    """Lo último que ha entrado de cualquier fuente, ya normalizado."""
    salida = []
    nombres = {"roomcloud": 1, "ofihotel": 2, "recepcion": 3, "correo": 4, "whatsapp": 5}
    for e in store.db["eventos"]:
        titulo = TEXTOS_EVENTO.get(e["tipo"])
        if not titulo or e["tipo"] == "mensaje_entrante":
            continue
        fuente = e["fuente"] if e["fuente"] in ICONOS_EVENTO else "sistema"
        salida.append({"id": e["id"], "ts": e["ts"], "hora": e["ts"][11:16], "fuente": fuente, "icono": ICONOS_EVENTO[fuente], "titulo": titulo,
                       "detalle": (e["contenido"] or e["remitente"])[:140], "nivel": nombres.get(fuente), "expediente_id": e["expediente_id"]})
    for c in _db(store):
        salida.append({"id": c["id"], "ts": c["ts"], "hora": c["ts"][11:16], "fuente": c["canal"], "icono": ICONOS_EVENTO[c["canal"]],
                       "titulo": f"{'Petición de habitación' if c['tipo'] == 'peticion_habitacion' else 'Mensaje'} por {NOMBRE_CANAL[c['canal']]}",
                       "detalle": f"{c['de']['nombre']}: {c['texto'][:110]}", "nivel": c["prioridad"]["nivel"], "expediente_id": c["expediente_id"]})
    salida.sort(key=lambda a: a["ts"], reverse=True)
    return salida[:limite]
