"""Bloques del chat: tarjetas, tablas, formularios y documentos que el servidor construye a partir de datos del hotel.

Seguridad (obligatoria). Los bloques y sus acciones salen de lo que hay en el almacén y nunca del texto que escribe el modelo:
el modelo solo elige herramientas, y aquí se decide qué se pinta. Todos los textos son texto plano, sin HTML, y las acciones
usan únicamente los tipos de la lista cerrada del contrato (`ACCIONES`). Esta versión es la mínima de la base: reconoce el
tema por palabras clave. El agente back-chat puede sustituirla sin cambiar la forma de los bloques.
"""
import copy
import re
import unicodedata
from datetime import timedelta

from . import conversaciones, disponibilidad, documentos

ACCIONES = {"preguntar", "abrir_seccion", "abrir_expediente", "abrir_documento", "abrir_conversacion", "aprobar_propuesta",
            "rechazar_propuesta", "enviar_formulario", "sincronizar", "emitir_documento", "enviar_documento"}
TONOS = {"neutro", "ok", "aviso", "critico", "info"}
ORIGENES = {"roomcloud": "RoomCloud", "walk-in": "Reserva física"}
ESTADOS_EXPEDIENTE = {"pendiente_llegada": ("pendiente de llegada", "aviso"), "en_curso": ("en casa", "ok"),
                      "cerrado": ("cerrada", "neutro"), "cancelada": ("cancelada", "critico")}
MAX_TARJETAS = 5
PASOS = [("huesped", "Documento y datos", "documento"), ("pago", "Pago", "pago"), ("empresa", "Datos de la empresa", "pago"),
         ("parte", "Parte de viajeros", "parte"), ("ofihotel_alta", "Alta en OfiHotel", "ofihotel"),
         ("factura", "Factura", "checkout"), ("habitacion_liberada", "Habitación liberada", "checkout")]

# El orden importa: gana el primer tema que encaje, de lo más concreto a lo más general.
TEMAS = [
    ("reserva_fisica", r"reserva f[ií]sica|walk-?in|sin reserva|(a[ñn]adir|nueva|crear|hacer) (una )?reserva"),
    ("documentos", r"factura|albar[aá]n|invoice|documentos? (hay|por|pendiente|emitid|generad|sin enviar)|enviar (el |la |los )?documento"),
    ("estancia", r"check-?in|check-?out|checkout|estancia|expediente|flujo|pasos|llegada|salida"),  # solo si nombra a un huésped
    ("partes", r"\bpartes?\b"),
    ("mensajes", r"mensaje|whatsapp|correo|e-?mail|dicho|escrib|sin responder"),
    ("propuestas", r"propuesta|aprobar|aprobaci|pendiente"),
    ("ocupacion", r"ocupaci|libre|disponib|complet|overbooking|habitaci"),
    ("llegadas", r"llegad|hoy|reserva|check-?in|salida|en casa"),
]
_TEMAS = [(tema, re.compile(patron)) for tema, patron in TEMAS]


# ---------------------------------------------------------------- utilidades

def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _principal():
    from . import main  # import perezoso: main importa el chat
    return main


def _hoy(store) -> str:
    return store.ahora().date().isoformat()


def _fecha_corta(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def _nombre(exp: dict) -> str:
    return f"{exp['reserva']['nombre']} {exp['reserva']['apellidos']}".strip()


def _item(etiqueta: str, valor, detalle: str = "", tono: str = "neutro") -> dict:
    return {"etiqueta": etiqueta, "valor": str(valor), "detalle": detalle, "tono": tono}


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


def tema_de(store, mensaje: str) -> tuple[str, dict | None]:
    """(tema, estancia nombrada). El tema `estancia` exige que el mensaje nombre a un huésped; si no, se pasa al siguiente."""
    bajo = mensaje.lower()
    exp = expediente_nombrado(store, mensaje)
    for tema, patron in _TEMAS:
        if patron.search(bajo) and (tema != "estancia" or exp):
            return tema, exp
    return "ayuda", exp


# ---------------------------------------------------------------- constructores de bloques

def bloque_resumen_kpi(store) -> dict:
    exps = [e for e in store.db["expedientes"].values() if e["estado"] != "cancelada"]
    hoy = _hoy(store)
    llegadas = [e for e in exps if e["checkin_prevista"] == hoy]
    hechos = sum(e["estado"] != "pendiente_llegada" for e in llegadas)
    partes = sum(e["estado"] == "en_curso" and e["tramites"]["parte"]["estado"] != "hecho" for e in exps)
    return {"tipo": "resumen_kpi", "titulo": "Hoy", "items": [
        _item("Llegadas", len(llegadas), f"{hechos} con check-in hecho" if llegadas else ""),
        _item("En casa", sum(e["estado"] == "en_curso" for e in exps)),
        _item("Salidas", sum(e["checkout_prevista"] == hoy and e["estado"] != "cerrado" for e in exps)),
        _item("Partes sin enviar", partes, tono="aviso" if partes else "ok")]}


def bloque_tarjeta_reserva(exp: dict, acciones_extra: list[dict] | None = None) -> dict:
    texto_estado, tono = ESTADOS_EXPEDIENTE.get(exp["estado"], (exp["estado"], "neutro"))
    chips = [{"texto": texto_estado, "tono": tono}]
    if exp["estado"] == "en_curso":
        hecho = exp["tramites"]["parte"]["estado"] == "hecho"
        chips.append({"texto": "parte enviado" if hecho else "parte pendiente", "tono": "ok" if hecho else "aviso"})
    tipos = ", ".join(sorted({h["tipo"] for h in exp["habitaciones"]}))
    fechas = f"{_fecha_corta(exp['checkin_prevista'])} a {_fecha_corta(exp['checkout_prevista'])}"
    return {"tipo": "tarjeta_reserva", "id": exp["id"], "titulo": _nombre(exp),
            "subtitulo": f"{fechas} · {tipos}" if tipos else fechas,
            "chips": chips,
            "campos": [{"etiqueta": "Origen", "valor": ORIGENES.get(exp["origen"], exp["origen"])},
                       {"etiqueta": "Viaja por trabajo", "valor": "Sí" if exp["viaja_por_trabajo"] else "No"}],
            "acciones": [{"tipo": "abrir_expediente", "etiqueta": "Abrir", "id": exp["id"]}, *(acciones_extra or [])]}


def bloque_tabla_ocupacion(store, dias: int = 7) -> dict:
    mapa = disponibilidad.mapa(store.db, _hoy(store), dias)
    return {"tipo": "tabla_ocupacion", "fechas": mapa["fechas"], "filas": [
        {"tipo": tipo, "capacidad": datos["capacidad"],
         "celdas": [{"fecha": c["fecha"], "ocupadas": c["ocupadas"], "libres": c["libres"], "cerrado": c["cerrado_en_roomcloud"]}
                    for c in datos["dias"]]} for tipo, datos in mapa["tipos"].items()]}


def _documento_vigente(store, exp_id: str, tipo: str) -> dict | None:
    return next((d for d in documentos.listar(store, tipo=tipo, expediente=exp_id) if d["estado"] != "anulado"), None)


def _detalle_paso(store, exp: dict, paso: str) -> str:
    hecho = exp["tramites"][paso]["estado"] == "hecho"
    h, pago = exp["huesped"], exp["pago"]
    if paso == "huesped":
        return f"{h['tipo_documento']} {h['numero_documento']}" if hecho else "Leer el documento y confirmar los datos"
    if paso == "pago":
        return pago.get("medio", "") if hecho else "Elegir el medio de pago"
    if paso == "empresa":
        return exp["empresa"].get("razon_social", "") if hecho else "Razón social, CIF y dirección"
    if paso == "parte":
        if hecho:
            return f"Justificante {exp['parte']['justificante']} (simulado)"
        restante = _principal().parte_restante_h(exp)
        return f"Quedan {restante} h para enviarlo" if restante is not None else "Se envía después del check-in"
    if paso == "ofihotel_alta":
        return "Datos copiados a OfiHotel" if hecho else "Copiar los datos a OfiHotel"
    if paso == "factura":
        doc = _documento_vigente(store, exp["id"], "factura")
        if doc and doc["numero"]:
            return f"{documentos.rotulo(doc)}, {documentos.estado_texto(doc)} (sin validez fiscal)"
        return "Factura hecha" if hecho else "Emitir o marcar la factura"
    return "Habitación liberada" if hecho else "Liberar la habitación al salir"


def bloque_flujo(store, exp: dict) -> dict:
    """Pasos de la estancia. El primero pendiente y sin bloqueo es el actual; un paso bloqueado espera a otro."""
    t = exp["tramites"]
    bloqueos = {"parte": t["huesped"]["estado"] != "hecho" or t["pago"]["estado"] != "hecho",
                "ofihotel_alta": t["huesped"]["estado"] != "hecho",
                "factura": exp["viaja_por_trabajo"] and t["empresa"]["estado"] != "hecho"}
    hay_actual, pasos = False, []
    for paso, titulo, ruta in PASOS:
        if paso == "empresa" and not exp["viaja_por_trabajo"]:
            continue
        if t[paso]["estado"] == "hecho":
            estado = "hecho"
        elif bloqueos.get(paso):
            estado = "bloqueado"
        elif not hay_actual:
            estado, hay_actual = "actual", True
        else:
            estado = "pendiente"
        pasos.append({"id": paso, "titulo": titulo, "estado": estado, "detalle": _detalle_paso(store, exp, paso),
                      "accion": {"tipo": "abrir_expediente", "etiqueta": "Abrir paso", "id": exp["id"], "paso": ruta}})
    inicio = "Check-in de" if exp["estado"] == "pendiente_llegada" else "Estancia de"
    return {"tipo": "flujo", "titulo": f"{inicio} {_nombre(exp)}", "pasos": pasos}


def bloque_propuesta(prop: dict) -> dict:
    pendiente = prop["estado"] == "pendiente"
    return {"tipo": "propuesta", "id": prop["id"], "texto": prop["texto"], "plantilla": prop["plantilla"], "destino": prop["destino"],
            "origen": prop["origen"], "destinatario": prop["destinatario"], "estado": prop["estado"],
            "acciones": [{"tipo": "aprobar_propuesta", "etiqueta": "Aprobar", "id": prop["id"]},
                         {"tipo": "rechazar_propuesta", "etiqueta": "Rechazar", "id": prop["id"]}] if pendiente else []}


def bloque_lista_mensajes(store, limite: int = MAX_TARJETAS) -> dict:
    filas = []
    for conv in conversaciones.listar(store)[:limite]:
        entrante = conv["ultimo"]["direccion"] == "entrante"
        filas.append({"de": conv["nombre"] if entrante else "Recepción", "canal": conv["canal"], "hora": conv["ultimo"]["hora"],
                      "texto": conv["ultimo"]["texto"], "intencion": conv["intencion"] if entrante else None,
                      "accion": {"tipo": "abrir_conversacion", "etiqueta": "Abrir", "id": conv["id"]}})
    return {"tipo": "lista_mensajes", "titulo": "Últimos mensajes", "mensajes": filas}


def bloque_formulario_walkin(store) -> dict:
    hoy = store.ahora().date()
    texto = lambda nombre, etiqueta, obligatorio=False: {"nombre": nombre, "etiqueta": etiqueta, "tipo": "texto", "opciones": [],
                                                         "valor": "", "obligatorio": obligatorio}
    tipos = list(disponibilidad.capacidad())
    return {"tipo": "formulario", "id": "walkin", "titulo": "Reserva física", "campos": [
        texto("nombre", "Nombre", True), texto("apellidos", "Apellidos"), texto("telefono", "Teléfono"),
        {"nombre": "tipo", "etiqueta": "Tipo de habitación", "tipo": "select", "opciones": tipos, "valor": tipos[0] if tipos else "",
         "obligatorio": True},
        {"nombre": "checkin", "etiqueta": "Llegada", "tipo": "fecha", "opciones": [], "valor": hoy.isoformat(), "obligatorio": True},
        {"nombre": "checkout", "etiqueta": "Salida", "tipo": "fecha", "opciones": [], "valor": (hoy + timedelta(days=1)).isoformat(),
         "obligatorio": True},
        {"nombre": "personas", "etiqueta": "Personas", "tipo": "numero", "opciones": [], "valor": "1", "obligatorio": True}],
        "envio": {"tipo": "enviar_formulario", "etiqueta": "Añadir reserva", "formulario": "walkin"}}


def bloque_documento(store, doc: dict) -> dict:
    exp = store.db["expedientes"].get(doc["expediente_id"])
    con_importes = documentos.tiene_importes(doc)
    lineas = []
    for linea in doc["lineas"]:
        importe = documentos.total_de_linea(linea)  # con IVA, para que las líneas sumen el total que se muestra
        lineas.append({"concepto": linea["concepto"] if importe is not None
                       else f"{linea['concepto']} × {documentos.cantidad_es(linea['cantidad'])}",
                       "importe": documentos.euros(importe) if importe is not None else ""})
    acciones = [{"tipo": "abrir_documento", "etiqueta": "Abrir", "id": doc["id"]}]
    if doc["estado"] == "borrador":
        acciones.append({"tipo": "emitir_documento", "etiqueta": "Emitir", "id": doc["id"]})
    elif doc["estado"] in ("emitido", "enviado"):
        enviar = {"tipo": "enviar_documento", "etiqueta": "Enviar por correo" if doc["estado"] == "emitido" else "Volver a enviar",
                  "id": doc["id"]}
        if doc["receptor"].get("email"):
            acciones.append({**enviar, "destinatario": doc["receptor"]["email"]})
    return {"tipo": "documento", "id": doc["id"], "documento": doc["tipo"], "estado": doc["estado"], "numero": doc["numero"],
            "titulo": f"{documentos.ROTULOS[doc['tipo']]} de {_nombre(exp) if exp else doc['receptor'].get('nombre', '')}",
            "receptor": doc["receptor"].get("nombre", ""),
            "total": documentos.euros(doc["totales"]["total"]) if con_importes else "Sin importes",
            "fiscal": doc["fiscal"], "aviso": doc["aviso_fiscal"], "lineas": lineas, "acciones": acciones}


def bloque_aviso(titulo: str, texto: str, tono: str = "info") -> dict:
    return {"tipo": "aviso", "tono": tono, "titulo": titulo, "texto": texto}


def bloque_sugerencias(items: list[str]) -> dict:
    return {"tipo": "sugerencias", "items": items[:3]}


# ---------------------------------------------------------------- del mensaje a los bloques

def _por_tema(store, tema: str, mensaje: str, exp: dict | None) -> list[dict]:
    bajo = mensaje.lower()
    exps = [e for e in store.db["expedientes"].values() if e["estado"] != "cancelada"]
    hoy = _hoy(store)
    if tema == "llegadas":
        if "salida" in bajo:
            elegidas, vacio = [e for e in exps if e["checkout_prevista"] == hoy and e["estado"] != "cerrado"], "No hay salidas previstas hoy."
        elif "en casa" in bajo:
            elegidas, vacio = [e for e in exps if e["estado"] == "en_curso"], "Ahora mismo no hay nadie en casa."
        else:
            elegidas, vacio = [e for e in exps if e["checkin_prevista"] == hoy], "No hay llegadas previstas hoy."
        return [bloque_resumen_kpi(store)] + ([bloque_tarjeta_reserva(e) for e in elegidas[:MAX_TARJETAS]] or [bloque_aviso("Sin resultados", vacio)])
    if tema == "ocupacion":
        return [bloque_tabla_ocupacion(store)]
    if tema == "partes":
        pendientes = [e for e in exps if e["estado"] == "en_curso" and e["tramites"]["parte"]["estado"] != "hecho"]
        if not pendientes:
            return [bloque_aviso("Partes al día", "No hay partes de viajeros pendientes de enviar.", "ok")]
        return [b for e in pendientes[:3] for b in (bloque_tarjeta_reserva(e), bloque_flujo(store, e))]
    if tema == "mensajes":
        lista = bloque_lista_mensajes(store)
        return [lista] if lista["mensajes"] else [bloque_aviso("Sin mensajes", "Todavía no ha llegado ningún mensaje de WhatsApp ni de correo.")]
    if tema == "propuestas":
        pendientes = [p for p in store.db["propuestas"] if p["estado"] == "pendiente"]
        return [bloque_propuesta(p) for p in pendientes[:MAX_TARJETAS]] or [
            bloque_aviso("Nada pendiente", "No hay propuestas esperando aprobación.", "ok")]
    if tema == "documentos":
        tipo = "albaran" if "albar" in bajo and "factur" not in bajo else "factura" if "factur" in bajo and "albar" not in bajo else None
        docs = documentos.listar(store, tipo=tipo, expediente=exp["id"] if exp else None)
        if docs:
            return [bloque_documento(store, d) for d in docs[:4]]
        crear = [{"tipo": "abrir_seccion", "etiqueta": "Preparar factura", "seccion": "documentos",
                  "params": {"nuevo": exp["id"], "tipo": "factura"}},
                 {"tipo": "abrir_seccion", "etiqueta": "Preparar albarán", "seccion": "documentos",
                  "params": {"nuevo": exp["id"], "tipo": "albaran"}}] if exp else []
        aviso = bloque_aviso("Sin documentos", "Todavía no hay facturas ni albaranes" + (f" de {_nombre(exp)}." if exp else "."))
        return [aviso] + ([bloque_tarjeta_reserva(exp, crear)] if exp else [])
    if tema == "estancia":
        return [bloque_tarjeta_reserva(exp), bloque_flujo(store, exp)]
    if tema == "reserva_fisica":
        return [bloque_formulario_walkin(store)]
    return []


def sugerencias_de(tema: str, exp: dict | None, mensaje: str) -> list[str]:
    nombre = exp["reserva"]["nombre"] if exp else "Ana"
    por_tema = {
        "llegadas": ["¿Cómo está la ocupación?", "¿Qué partes están pendientes?", "¿Qué mensajes han llegado?"],
        "ocupacion": ["¿Qué llegadas hay hoy?", "Quiero añadir una reserva física", "¿Qué propuestas hay pendientes de aprobar?"],
        "partes": ["¿Qué llegadas hay hoy?", "¿Qué propuestas hay pendientes de aprobar?", "¿Qué documentos hay por enviar?"],
        "mensajes": ["¿Qué propuestas hay pendientes de aprobar?", "¿Qué llegadas hay hoy?", "¿Qué documentos hay por enviar?"],
        "propuestas": ["¿Qué mensajes han llegado?", "¿Qué partes están pendientes?", "¿Cómo está la ocupación?"],
        "documentos": ["¿Qué documentos hay por enviar?", f"Prepara el albarán de {nombre}", "¿Qué mensajes han llegado?"],
        "estancia": ["¿Qué partes están pendientes?", f"Prepara la factura de {nombre}", "¿Cómo está la ocupación?"],
        "reserva_fisica": ["¿Cómo está la ocupación?", "¿Qué llegadas hay hoy?", "¿Qué propuestas hay pendientes de aprobar?"],
    }
    base = por_tema.get(tema, ["¿Qué llegadas hay hoy?", "¿Cómo está la ocupación?", "¿Qué documentos hay por enviar?"])
    return [s for s in base if s.lower() != mensaje.strip().lower()]


def para_mensaje(store, mensaje: str) -> list[dict]:
    """Bloques reales para una pregunta, según el tema que reconocen las palabras clave, y sugerencias en cualquier caso."""
    tema, exp = tema_de(store, mensaje)
    return _por_tema(store, tema, mensaje, exp) + [bloque_sugerencias(sugerencias_de(tema, exp, mensaje))]


def bloques_de_propuestas(store, ids: list[str]) -> list[dict]:
    """Un bloque `propuesta` por cada id, construido desde el almacén."""
    por_id = {p["id"]: p for p in store.db["propuestas"]}
    return [bloque_propuesta(por_id[i]) for i in ids if i in por_id]


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
    for pasos in bloque.get("pasos", []):
        encontradas.append(pasos["accion"])
    for fila in bloque.get("mensajes", []):
        encontradas.append(fila["accion"])
    return encontradas


# ---------------------------------------------------------------- bloques de muestra
# Un bloque de cada tipo con datos de la semilla `completa` (Ana, su factura DEMO-F-0001, su albarán en borrador, la propuesta
# pr-0008 y la conversación de Claire). `/api/chat/bloques-muestra` los devuelve tal cual, sin leer el almacén, para poder
# desarrollar el pintado sin depender del resto. Un test comprueba que coinciden con lo que construye el servidor sobre esa
# semilla, así que si la semilla cambia el test dice qué hay que actualizar aquí.
_MUESTRA = [
    {'tipo': 'resumen_kpi',
     'titulo': 'Hoy',
     'items': [{'etiqueta': 'Llegadas', 'valor': '3', 'detalle': '2 con check-in hecho', 'tono': 'neutro'},
               {'etiqueta': 'En casa', 'valor': '2', 'detalle': '', 'tono': 'neutro'},
               {'etiqueta': 'Salidas', 'valor': '0', 'detalle': '', 'tono': 'neutro'},
               {'etiqueta': 'Partes sin enviar', 'valor': '1', 'detalle': '', 'tono': 'aviso'}]},
    {'tipo': 'tarjeta_reserva',
     'id': '1-BK-4471920',
     'titulo': 'Ana Pereira Lage',
     'subtitulo': '24/10 a 26/10 · DBL-STD',
     'chips': [{'texto': 'en casa', 'tono': 'ok'}, {'texto': 'parte enviado', 'tono': 'ok'}],
     'campos': [{'etiqueta': 'Origen', 'valor': 'RoomCloud'}, {'etiqueta': 'Viaja por trabajo', 'valor': 'Sí'}],
     'acciones': [{'tipo': 'abrir_expediente', 'etiqueta': 'Abrir', 'id': '1-BK-4471920'}]},
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
    {'tipo': 'flujo',
     'titulo': 'Estancia de Ana Pereira Lage',
     'pasos': [{'id': 'huesped',
                'titulo': 'Documento y datos',
                'estado': 'hecho',
                'detalle': 'NIF 12345678Z',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'documento'}},
               {'id': 'pago',
                'titulo': 'Pago',
                'estado': 'hecho',
                'detalle': 'TARJETA',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'pago'}},
               {'id': 'empresa',
                'titulo': 'Datos de la empresa',
                'estado': 'hecho',
                'detalle': 'Atlántico Consultores SL',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'pago'}},
               {'id': 'parte',
                'titulo': 'Parte de viajeros',
                'estado': 'hecho',
                'detalle': 'Justificante SIM-2509C2E7AC87 (simulado)',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'parte'}},
               {'id': 'ofihotel_alta',
                'titulo': 'Alta en OfiHotel',
                'estado': 'actual',
                'detalle': 'Copiar los datos a OfiHotel',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'ofihotel'}},
               {'id': 'factura',
                'titulo': 'Factura',
                'estado': 'pendiente',
                'detalle': 'Factura DEMO-F-0001, emitida (sin validez fiscal)',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'checkout'}},
               {'id': 'habitacion_liberada',
                'titulo': 'Habitación liberada',
                'estado': 'pendiente',
                'detalle': 'Liberar la habitación al salir',
                'accion': {'tipo': 'abrir_expediente', 'etiqueta': 'Abrir paso', 'id': '1-BK-4471920', 'paso': 'checkout'}}]},
    {'tipo': 'propuesta',
     'id': 'pr-0008',
     'texto': 'Hola Ana, el check-in empieza a las 14:00 y el check-out termina a las 12:00. ¿A qué hora prevés llegar?',
     'plantilla': 'info_llegada',
     'destino': 'whatsapp',
     'origen': 'enrutador',
     'destinatario': '34600111222',
     'estado': 'pendiente',
     'acciones': [{'tipo': 'aprobar_propuesta', 'etiqueta': 'Aprobar', 'id': 'pr-0008'},
                  {'tipo': 'rechazar_propuesta', 'etiqueta': 'Rechazar', 'id': 'pr-0008'}]},
    {'tipo': 'lista_mensajes',
     'titulo': 'Últimos mensajes',
     'mensajes': [{'de': 'Claire Dubois',
                   'canal': 'correo',
                   'hora': '09:00',
                   'texto': 'Buenos días, ¿podrían enviarme la factura de mi estancia? La necesito para presentarla en mi empresa. '
                            'Gracias.',
                   'intencion': 'solicita_factura',
                   'accion': {'tipo': 'abrir_conversacion', 'etiqueta': 'Abrir', 'id': 'mail:claire.dubois@example.com'}},
                  {'de': 'Ana',
                   'canal': 'whatsapp',
                   'hora': '09:00',
                   'texto': 'Hola, ¿a qué hora es el check-in?',
                   'intencion': 'pregunta_checkin_horario',
                   'accion': {'tipo': 'abrir_conversacion', 'etiqueta': 'Abrir', 'id': 'wa:34600111222'}}]},
    {'tipo': 'formulario',
     'id': 'walkin',
     'titulo': 'Reserva física',
     'campos': [{'nombre': 'nombre', 'etiqueta': 'Nombre', 'tipo': 'texto', 'opciones': [], 'valor': '', 'obligatorio': True},
                {'nombre': 'apellidos', 'etiqueta': 'Apellidos', 'tipo': 'texto', 'opciones': [], 'valor': '', 'obligatorio': False},
                {'nombre': 'telefono', 'etiqueta': 'Teléfono', 'tipo': 'texto', 'opciones': [], 'valor': '', 'obligatorio': False},
                {'nombre': 'tipo',
                 'etiqueta': 'Tipo de habitación',
                 'tipo': 'select',
                 'opciones': ['DBL-STD', 'SGL-STD'],
                 'valor': 'DBL-STD',
                 'obligatorio': True},
                {'nombre': 'checkin',
                 'etiqueta': 'Llegada',
                 'tipo': 'fecha',
                 'opciones': [],
                 'valor': '2026-10-24',
                 'obligatorio': True},
                {'nombre': 'checkout',
                 'etiqueta': 'Salida',
                 'tipo': 'fecha',
                 'opciones': [],
                 'valor': '2026-10-25',
                 'obligatorio': True},
                {'nombre': 'personas', 'etiqueta': 'Personas', 'tipo': 'numero', 'opciones': [], 'valor': '1', 'obligatorio': True}],
     'envio': {'tipo': 'enviar_formulario', 'etiqueta': 'Añadir reserva', 'formulario': 'walkin'}},
    {'tipo': 'documento',
     'id': 'doc-0011',
     'documento': 'factura',
     'estado': 'emitido',
     'numero': 'DEMO-F-0001',
     'titulo': 'Factura de Ana Pereira Lage',
     'receptor': 'Atlántico Consultores SL',
     'total': '212,00 EUR',
     'fiscal': False,
     'aviso': 'Documento de demostración sin validez fiscal',
     'lineas': [{'concepto': 'Alojamiento DBL-STD, 2 noches', 'importe': '212,00 EUR'}],
     'acciones': [{'tipo': 'abrir_documento', 'etiqueta': 'Abrir', 'id': 'doc-0011'},
                  {'tipo': 'enviar_documento',
                   'etiqueta': 'Enviar por correo',
                   'id': 'doc-0011',
                   'destinatario': 'facturas@atlantico.example'}]},
    {'tipo': 'documento',
     'id': 'doc-0013',
     'documento': 'albaran',
     'estado': 'borrador',
     'numero': None,
     'titulo': 'Albarán de Ana Pereira Lage',
     'receptor': 'Atlántico Consultores SL',
     'total': 'Sin importes',
     'fiscal': False,
     'aviso': 'Documento de demostración sin validez fiscal',
     'lineas': [{'concepto': 'Alojamiento DBL-STD (noches) × 2', 'importe': ''}, {'concepto': 'Desayuno buffet × 2', 'importe': ''}],
     'acciones': [{'tipo': 'abrir_documento', 'etiqueta': 'Abrir', 'id': 'doc-0013'},
                  {'tipo': 'emitir_documento', 'etiqueta': 'Emitir', 'id': 'doc-0013'}]},
    {'tipo': 'aviso', 'tono': 'info', 'titulo': 'Sin documentos', 'texto': 'Todavía no hay facturas ni albaranes de Claire Dubois.'},
    {'tipo': 'sugerencias', 'items': ['¿Cómo está la ocupación?', '¿Qué partes están pendientes?', '¿Qué mensajes han llegado?']},
]


def bloques_muestra() -> list[dict]:
    return copy.deepcopy(_MUESTRA)


# ---------------------------------------------------------------- sugerencias de bienvenida

def sugerencias_bienvenida() -> dict:
    """Pantalla de bienvenida del asistente: cuatro categorías con tres preguntas y cuatro flujos."""
    return {"categorias": [
        {"id": "llegadas", "titulo": "Llegadas", "icono": "key",
         "preguntas": ["¿Qué llegadas hay hoy?", "¿Qué partes están pendientes?", "¿Quién está en casa ahora mismo?"]},
        {"id": "ocupacion", "titulo": "Ocupación", "icono": "bed",
         "preguntas": ["¿Cómo está la ocupación?", "¿Qué salidas hay hoy?", "Quiero añadir una reserva física"]},
        {"id": "mensajes", "titulo": "Mensajes", "icono": "message",
         "preguntas": ["¿Qué mensajes han llegado?", "¿Qué mensajes están sin responder?", "¿Qué propuestas hay pendientes de aprobar?"]},
        {"id": "documentos", "titulo": "Documentos", "icono": "file",
         "preguntas": ["¿Qué documentos hay por enviar?", "Enséñame la factura de Ana", "Prepara el albarán de Ana"]}],
        "flujos": [
            {"id": "checkin", "titulo": "Hacer un check-in", "icono": "door", "pregunta": "Quiero hacer el check-in de Ana",
             "descripcion": "Documento y datos, pago, parte de viajeros y alta en OfiHotel de un huésped que llega."},
            {"id": "checkout", "titulo": "Hacer un check-out", "icono": "key", "pregunta": "Quiero hacer el check-out de Ana",
             "descripcion": "Factura, habitación liberada y cierre del expediente de un huésped que se va."},
            {"id": "factura", "titulo": "Preparar una factura", "icono": "file", "pregunta": "Prepara la factura de Ana",
             "descripcion": "Crea la factura de una estancia, emítela y envíala por correo con confirmación."},
            {"id": "reserva_fisica", "titulo": "Añadir una reserva física", "icono": "bed", "pregunta": "Quiero añadir una reserva física",
             "descripcion": "Reserva de mostrador con aviso previo si no queda habitación libre."}]}
