"""Procesos del hotel que el asistente explica paso a paso (bloque `proceso`).

Son datos fijos de demostración: no leen el almacén. Máximo 6 pasos por proceso, cada uno con `id`, `titulo`, `fuente` (una clave de
FUENTES) y `detalle` de una frase. Las acciones del final abren la pantalla relacionada. Todo el texto es texto plano.
"""
import copy

FUENTES = {"roomcloud", "ofihotel", "recepcion", "correo", "whatsapp", "ses", "sistema"}


def _paso(id_: str, titulo: str, fuente: str, detalle: str, dato: str | None = None, resultado: str | None = None) -> dict:
    paso = {"id": id_, "titulo": titulo, "fuente": fuente, "detalle": detalle}
    if dato:
        paso["dato"] = dato
    if resultado:
        paso["resultado"] = resultado
    return paso


def _ir(etiqueta: str, seccion: str, **params) -> dict:
    return {"tipo": "abrir_seccion", "etiqueta": etiqueta, "seccion": seccion, "params": params}


def _preguntar(etiqueta: str, texto: str) -> dict:
    return {"tipo": "preguntar", "etiqueta": etiqueta, "texto": texto}


_PROCESOS = {
    "peticion_mensaje": {
        "tipo": "proceso", "id": "peticion_mensaje", "titulo": "Cómo entra una petición por WhatsApp",
        "resumen": "Del mensaje del huésped a la respuesta confirmada por recepción.",
        "pasos": [
            _paso("recibir", "Llega el mensaje", "whatsapp", "Un huésped pide habitación por WhatsApp o por correo y queda guardado en Comunicaciones con su hora."),
            _paso("entender", "Se entiende la petición", "sistema", "La aplicación extrae el tipo de habitación, las fechas y las personas, y detecta el idioma."),
            _paso("contrastar", "Se contrasta con las fuentes", "roomcloud", "Cuenta lo que ya ocupan RoomCloud, OfiHotel y recepción esas noches, y gana la fuente de más prioridad."),
            _paso("redactar", "Se redacta la respuesta", "sistema", "El borrador sale en el idioma del huésped con el veredicto de disponibilidad."),
            _paso("enviar", "Recepción confirma", "recepcion", "La respuesta sale por el mismo canal por el que llegó la petición y la habitación queda reservada."),
        ],
        "acciones": [_ir("Abrir comunicaciones", "comunicaciones")],
    },
    "reserva_canal": {
        "tipo": "proceso", "id": "reserva_canal", "titulo": "Qué pasa cuando entra una reserva de Booking",
        "resumen": "La reserva entra con prioridad 1 y avisa a las peticiones que competían.",
        "pasos": [
            _paso("llega", "Llega a RoomCloud", "roomcloud", "Booking envía la reserva con su referencia externa, las fechas y el tipo de habitación."),
            _paso("crear", "Se crea la estancia", "sistema", "La aplicación la da de alta con prioridad 1 y la cruza con OfiHotel por la referencia externa."),
            _paso("ocupacion", "Se actualiza la ocupación", "sistema", "Si el tipo se llena alguna noche, la aplicación propone cerrar la venta de ese tipo en RoomCloud."),
            _paso("avisar", "Se avisa a las peticiones", "sistema", "Las peticiones de esas noches pasan a no disponible, porque una reserva firme nunca la desplaza una petición."),
        ],
        "acciones": [_ir("Abrir ocupación", "ocupacion")],
    },
    "checkin_parte": {
        "tipo": "proceso", "id": "checkin_parte", "titulo": "Del check-in al parte de viajeros",
        "resumen": "Recepción recoge los datos, envía el parte y pasa la estancia a OfiHotel.",
        "pasos": [
            _paso("llega", "Llega el huésped", "recepcion", "Recepción abre la estancia, teclea documento y pago, y empieza a contar el plazo de 24 h del parte."),
            _paso("enviar", "Se envía el parte", "ses", "Recepción revisa el parte y confirma el envío a SES.Hospedajes, que en la demo devuelve un justificante simulado."),
            _paso("ofihotel", "Se pasa a OfiHotel", "recepcion", "Recepción copia la estancia a mano y la marca como hecha, porque la aplicación nunca escribe en OfiHotel."),
            _paso("migrada", "Se confirma al día siguiente", "ofihotel", "Cuando la lectura de OfiHotel trae la estancia, queda en verde."),
        ],
        "acciones": [_ir("Abrir estancias", "estancias")],
    },
    "overbooking_cierre": {
        "tipo": "proceso", "id": "overbooking_cierre", "titulo": "Cómo se evita un overbooking",
        "resumen": "La aplicación suma todas las fuentes, avisa y propone cerrar la venta.",
        "pasos": [
            _paso("detectar", "Se detecta la noche llena", "sistema", "Para cada noche suma lo que aportan RoomCloud, OfiHotel y recepción y lo compara con la capacidad del tipo."),
            _paso("proponer", "Se propone cerrar la venta", "roomcloud", "La aplicación prepara el cierre del tipo en RoomCloud y avisa a recepción."),
            _paso("aprobar", "Recepción decide", "recepcion", "Nada se ejecuta sin que una persona apruebe, y en la demo el cierre es simulado."),
        ],
        "acciones": [_ir("Abrir ocupación", "ocupacion"), _preguntar("Ver conflictos", "¿Qué conflictos hay?")],
    },
    "fuente_unica": {
        "tipo": "proceso", "id": "fuente_unica", "titulo": "Cómo funciona la fuente única",
        "resumen": "Cinco fuentes en una pantalla, con un color por estancia.",
        "pasos": [
            _paso("leer", "Se leen las fuentes", "sistema", "RoomCloud y OfiHotel entran en solo lectura, y el correo, WhatsApp y recepción aportan peticiones y confirmaciones."),
            _paso("unificar", "Se unifica cada estancia", "sistema", "La aplicación enlaza la misma estancia entre sistemas por la referencia externa, el nombre y las fechas."),
            _paso("estado", "Se calcula el color", "sistema", "Cada estancia recibe uno de seis colores según esté sincronizada, migrada y con el parte enviado."),
            _paso("conflictos", "Se marcan los conflictos", "sistema", "Si las fechas o el tipo no coinciden entre RoomCloud y OfiHotel, la estancia queda en rojo."),
        ],
        "acciones": [_ir("Abrir la fuente única", "fuente")],
    },
    "prioridades": {
        "tipo": "proceso", "id": "prioridades", "titulo": "Quién gana cuando dos fuentes compiten",
        "resumen": "Una individual libre, un correo, un WhatsApp y una reserva de Booking.",
        "pasos": [
            _paso("whatsapp", "Llega un WhatsApp a las 18:05", "whatsapp", "Pide la última individual de esta noche y queda como disponible con prioridad 5."),
            _paso("correo", "Llega un correo a las 18:40", "correo", "Pide la misma habitación con prioridad 4, así que gana al WhatsApp aunque llegase después."),
            _paso("booking", "Entra una reserva de Booking a las 19:10", "roomcloud", "Con prioridad 1 bloquea la habitación y las dos peticiones pasan a no disponible."),
            _paso("aviso", "Recepción responde con una alternativa", "recepcion", "La aplicación avisa y propone otras fechas si hay hueco."),
        ],
        "acciones": [_ir("Abrir la fuente única", "fuente")],
    },
}

PROCESOS = list(_PROCESOS)


def proceso(proceso_id: str) -> dict:
    """Copia del proceso. Lanza KeyError si no existe."""
    return copy.deepcopy(_PROCESOS[proceso_id])


# Pregunta con la que se pide cada proceso (el segundo valor es el icono de la tarjeta antigua y se conserva por compatibilidad).
TARJETAS = {
    "peticion_mensaje": ("Enséñame cómo entra una petición por WhatsApp", "mail"),
    "reserva_canal": ("Enséñame qué pasa cuando entra una reserva de Booking", "refresh"),
    "checkin_parte": ("Enséñame el proceso del check-in al parte de viajeros", "door"),
    "overbooking_cierre": ("Enséñame cómo se evita un overbooking", "alert"),
    "fuente_unica": ("Enséñame cómo funciona la fuente única", "layers"),
    "prioridades": ("Enséñame quién gana cuando dos fuentes compiten", "list"),
}
