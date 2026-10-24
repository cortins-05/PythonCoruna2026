"""Procesos del hotel que el asistente explica paso a paso (bloque `proceso`).

Son datos fijos de demostración: no leen el almacén. Cada paso lleva `id`, `titulo`, `fuente` (una clave de FUENTES), `detalle` y,
si hace falta, `dato` (una cifra o regla corta que enseña qué hace el sistema) y `resultado` (lo que queda tras el paso). Las
acciones del final abren la pantalla relacionada. Todo el texto es texto plano.
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
        "tipo": "proceso", "id": "peticion_mensaje", "titulo": "Cómo entra una petición por WhatsApp o correo",
        "resumen": "Un huésped escribe pidiendo habitación. La aplicación entiende la petición, la contrasta con todas las fuentes, "
                   "redacta la respuesta y recepción solo tiene que confirmarla.",
        "pasos": [
            _paso("recibir", "Llega el mensaje", "whatsapp",
                  "Un huésped escribe por WhatsApp o por correo pidiendo habitación y la aplicación lo guarda en Comunicaciones con la hora de llegada.",
                  "Prioridad 5 si llega por WhatsApp y prioridad 4 si llega por correo",
                  "Mensaje recibido y sin confirmar"),
            _paso("entender", "La aplicación entiende la petición", "sistema",
                  "Lee el texto, detecta el idioma y extrae el tipo de habitación, las fechas, las noches y el número de personas.",
                  "Doble, del 28 al 30 de octubre, 2 personas",
                  "Petición estructurada, lista para contrastar"),
            _paso("roomcloud", "Contrasta con RoomCloud", "roomcloud",
                  "Cuenta las reservas de Booking, Expedia y la web que ya ocupan habitaciones esas noches. Son reservas firmes con garantía de pago.",
                  "Prioridad 1: bloquea la habitación y ninguna petición la desplaza"),
            _paso("ofihotel", "Contrasta con OfiHotel", "ofihotel",
                  "Suma lo que ya está registrado en el programa del hotel. OfiHotel es de solo lectura y llega con los datos de ayer.",
                  "Prioridad 2, con la copia de ayer"),
            _paso("recepcion", "Contrasta con recepción", "recepcion",
                  "Suma los walk-ins y las peticiones que recepción ya ha confirmado desde la aplicación.",
                  "Prioridad 3: también es firme"),
            _paso("priorizar", "Decide quién gana", "sistema",
                  "Compara con las demás peticiones abiertas para las mismas noches. Gana el nivel más alto y, a igual nivel, la que llegó antes.",
                  "Libres para esta petición: 1 de 3 en las dos noches",
                  "Veredicto: disponible"),
            _paso("redactar", "Redacta la respuesta", "sistema",
                  "Prepara un borrador en el idioma del huésped con las fechas, el tipo de habitación y el siguiente paso. Recepción puede editarlo.",
                  resultado="Borrador listo para revisar"),
            _paso("enviar", "Recepción confirma y la respuesta sale por el mismo canal", "recepcion",
                  "Al pulsar confirmar, la respuesta sale por el canal por el que llegó la petición y la habitación queda reservada. El envío es simulado en esta demo.",
                  resultado="Petición respondida y habitación reservada con prioridad 3"),
        ],
        "acciones": [_ir("Ver las comunicaciones", "comunicaciones"), _ir("Ver la fuente única", "fuente")],
    },
    "reserva_canal": {
        "tipo": "proceso", "id": "reserva_canal", "titulo": "Qué pasa cuando entra una reserva de Booking",
        "resumen": "Una reserva de canal llega por RoomCloud, entra con la prioridad más alta y la aplicación actualiza la ocupación y avisa "
                   "a las peticiones que competían por el mismo hueco.",
        "pasos": [
            _paso("llega", "Llega la reserva a RoomCloud", "roomcloud",
                  "Un huésped reserva en Booking y RoomCloud recibe la reserva con su referencia externa, las fechas y el tipo de habitación.",
                  "Referencia externa de Booking, por ejemplo 4471920",
                  "Reserva leída por la aplicación"),
            _paso("crear", "La aplicación crea la estancia", "sistema",
                  "Da de alta la estancia con el tipo de habitación y las fechas de la reserva, y le asigna la prioridad 1.",
                  "Prioridad 1 (RoomCloud)",
                  "Estancia creada y visible en Estancias"),
            _paso("cruzar", "La cruza con OfiHotel", "ofihotel",
                  "Busca la misma reserva en la copia de OfiHotel usando la referencia externa. Si todavía no aparece, la estancia queda como pendiente de reflejar.",
                  "Cruce por referencia externa",
                  "Estancia enlazada, o gris si OfiHotel aún no la tiene"),
            _paso("ocupacion", "Actualiza la ocupación", "sistema",
                  "Suma la reserva al mapa de ocupación de todas las noches que cubre y la cuenta en la columna de RoomCloud.",
                  resultado="Ocupación recalculada con todas las fuentes"),
            _paso("llenar", "Detecta si el tipo se llena", "sistema",
                  "Compara las habitaciones ocupadas con la capacidad del tipo. Si una noche queda llena, prepara una propuesta para cerrar la venta de ese tipo en RoomCloud.",
                  "Capacidad del tipo doble: 3 habitaciones",
                  "Propuesta de cierre pendiente de aprobar"),
            _paso("avisar", "Avisa a las peticiones que competían", "sistema",
                  "Las peticiones de correo y WhatsApp para esas noches pasan a no disponible, con un aviso arriba del todo y una alternativa de fechas si existe.",
                  "Una reserva firme nunca la desplaza una petición",
                  "Recepción ve el aviso antes de responder"),
        ],
        "acciones": [_ir("Ver la ocupación", "ocupacion"), _ir("Ver las comunicaciones", "comunicaciones")],
    },
    "checkin_parte": {
        "tipo": "proceso", "id": "checkin_parte", "titulo": "Del check-in al parte de viajeros",
        "resumen": "Cuando llega el huésped, recepción recoge el documento y el pago, la aplicación prepara el parte y OfiHotel lo confirma "
                   "al día siguiente. Recepción pasa la estancia a OfiHotel a mano.",
        "pasos": [
            _paso("llega", "Llega el huésped", "recepcion",
                  "Recepción abre la estancia en la aplicación y empieza el check-in con la reserva que ya existe.",
                  "El reloj del parte empieza aquí",
                  "Estancia en casa y parte pendiente"),
            _paso("datos", "Se piden documento y pago", "recepcion",
                  "Recepción teclea los datos del documento de identidad y el medio de pago. Esta demo no lee documentos con OCR.",
                  resultado="Datos del huésped completos"),
            _paso("preparar", "La aplicación prepara el parte de viajeros", "sistema",
                  "Con los datos del huésped monta el parte que exige la normativa y marca el plazo para enviarlo.",
                  "Plazo: 24 horas desde el check-in",
                  "Parte listo y semáforo en naranja hasta que se envíe"),
            _paso("enviar", "Recepción confirma el envío a SES.Hospedajes", "ses",
                  "Recepción revisa el parte y confirma el envío. En la demo el envío es simulado y devuelve un justificante.",
                  "Justificante simulado, por ejemplo SIM-2509C2E7AC87",
                  "Parte enviado y semáforo en amarillo"),
            _paso("ofihotel", "Recepción pasa la estancia a OfiHotel", "recepcion",
                  "OfiHotel es de solo lectura para la aplicación, así que recepción copia los datos a mano en el programa y lo marca como hecho.",
                  "La aplicación nunca escribe en OfiHotel",
                  "Estancia marcada como pasada a OfiHotel"),
            _paso("migrada", "La lectura del día siguiente la confirma", "ofihotel",
                  "Cuando la aplicación lee la copia de OfiHotel del día siguiente y encuentra la estancia, la da por migrada.",
                  "OfiHotel llega con los datos de ayer",
                  "Estancia en verde: todo cuadrado"),
        ],
        "acciones": [_ir("Ver las estancias", "estancias"), _ir("Ver la fuente única", "fuente")],
    },
    "overbooking_cierre": {
        "tipo": "proceso", "id": "overbooking_cierre", "titulo": "Cómo se evita un overbooking",
        "resumen": "La aplicación cuenta la ocupación de todas las fuentes juntas. Si un tipo se llena, avisa y propone cerrar la venta en "
                   "RoomCloud, y recepción decide.",
        "pasos": [
            _paso("detectar", "Detecta la ocupación completa", "sistema",
                  "Para cada noche suma lo que aportan RoomCloud, OfiHotel y recepción, y lo compara con la capacidad del tipo de habitación.",
                  "Ocupadas igual o mayor que la capacidad, contando todas las fuentes",
                  "Noche llena detectada"),
            _paso("avisar", "Avisa a recepción", "sistema",
                  "Muestra un aviso en la fuente única y en la ocupación con el tipo y la noche afectados. Si hay más ocupadas que capacidad, lo marca como overbooking.",
                  resultado="Aviso visible en rojo"),
            _paso("proponer", "Propone cerrar la venta en RoomCloud", "roomcloud",
                  "Prepara una propuesta para cerrar la disponibilidad de ese tipo en esas noches y que no entren más reservas de canal.",
                  "Propuesta: cerrar el tipo doble de 24/10 a 25/10",
                  "Propuesta pendiente de aprobar"),
            _paso("aprobar", "Recepción aprueba", "recepcion",
                  "Nada se ejecuta sin la aprobación de una persona. Recepción puede aprobar o rechazar la propuesta desde el chat o desde la fuente única.",
                  "Aprobar pide confirmación",
                  "Propuesta aprobada"),
            _paso("cerrar", "Se cierra la venta de forma simulada", "roomcloud",
                  "La aplicación registra el cierre y la ocupación lo muestra con la marca de cerrado. En esta demo no se escribe en RoomCloud.",
                  "Cierre simulado",
                  "Tipo cerrado en el mapa de ocupación"),
        ],
        "acciones": [_ir("Ver la ocupación", "ocupacion"), _preguntar("Ver los conflictos", "¿Qué conflictos hay?")],
    },
    "fuente_unica": {
        "tipo": "proceso", "id": "fuente_unica", "titulo": "Cómo funciona la fuente única",
        "resumen": "Cada sistema aporta una parte de la información y la aplicación las unifica en una sola pantalla, con un color por estancia "
                   "y los conflictos a la vista.",
        "pasos": [
            _paso("partes", "Cada sistema aporta una parte", "sistema",
                  "RoomCloud trae las reservas de canal, OfiHotel trae lo registrado en el hotel, recepción aporta walk-ins y confirmaciones, "
                  "y el correo y WhatsApp traen las peticiones.",
                  "5 fuentes y SES.Hospedajes como salida"),
            _paso("leer", "La aplicación las lee", "roomcloud",
                  "Lee RoomCloud y OfiHotel en modo solo lectura y recibe los mensajes en cuanto llegan.",
                  "OfiHotel con los datos de ayer",
                  "Datos de todas las fuentes en el mismo sitio"),
            _paso("unificar", "Unifica cada estancia", "sistema",
                  "Enlaza la misma estancia entre sistemas por la referencia externa, el nombre y las fechas, y la deja como una sola ficha.",
                  resultado="Una ficha por estancia"),
            _paso("estado", "Calcula el estado por sistema", "sistema",
                  "Para cada estancia mira si está sincronizada en RoomCloud, migrada a OfiHotel y con el parte enviado, y elige un color de seis.",
                  "Rojo conflicto, naranja parte pendiente, amarillo falta pasar a OfiHotel, azul por atender, gris por reflejar y verde todo cuadrado",
                  "Semáforo de seis colores"),
            _paso("conflictos", "Detecta los conflictos", "sistema",
                  "Compara las fechas y los tipos entre RoomCloud y OfiHotel. Si no coinciden, lo marca en rojo y dice qué sistema difiere.",
                  resultado="Conflictos listados con su estancia"),
            _paso("pantalla", "Deja una sola pantalla de trabajo", "recepcion",
                  "Ordena la cola por la prioridad de la fuente y después por urgencia, así recepción empieza siempre por lo que más importa.",
                  resultado="Fuente única de verdad"),
        ],
        "acciones": [_ir("Abrir la fuente única", "fuente"), _ir("Ver las estancias", "estancias")],
    },
    "prioridades": {
        "tipo": "proceso", "id": "prioridades", "titulo": "Quién gana cuando dos fuentes compiten",
        "resumen": "Un ejemplo con una sola habitación individual libre esta noche: pide plaza un correo, pide plaza un WhatsApp y después "
                   "entra una reserva de Booking.",
        "pasos": [
            _paso("whatsapp", "Llega la petición por WhatsApp", "whatsapp",
                  "A las 18:05 un huésped escribe pidiendo la última habitación individual de esta noche.",
                  "Prioridad 5 (WhatsApp)",
                  "Petición abierta: disponible"),
            _paso("correo", "Llega la petición por correo", "correo",
                  "A las 18:40 otro huésped pide la misma habitación por correo, ya con los datos completos.",
                  "Prioridad 4 (correo)",
                  "Petición abierta: disponible"),
            _paso("gana", "Gana el correo aunque llegase después", "sistema",
                  "Entre dos peticiones gana el nivel más alto y la llegada solo desempata a igual nivel. La de WhatsApp pasa a estar en competencia.",
                  "Nivel 4 gana al nivel 5",
                  "Correo disponible y WhatsApp en competencia"),
            _paso("booking", "Entra una reserva de Booking por RoomCloud", "roomcloud",
                  "A las 19:10 RoomCloud trae una reserva de esa misma habitación. Es una reserva firme con garantía de pago.",
                  "Prioridad 1 (RoomCloud)",
                  "La habitación ya no está libre"),
            _paso("desplaza", "La reserva ocupa el hueco", "sistema",
                  "Lo firme bloquea la habitación y ninguna petición lo desplaza, así que las dos peticiones pasan a no disponible.",
                  "Firme (niveles 1 a 3) gana siempre a petición (niveles 4 y 5)",
                  "Las dos peticiones en no disponible"),
            _paso("aviso", "Aviso a recepción", "recepcion",
                  "La aplicación pone un aviso arriba de la petición con el motivo y propone otras fechas si hay hueco, para que recepción conteste con datos.",
                  resultado="Recepción responde con una alternativa"),
        ],
        "acciones": [_ir("Ver las prioridades", "fuente"), _ir("Ver las comunicaciones", "comunicaciones")],
    },
}

PROCESOS = list(_PROCESOS)


def proceso(proceso_id: str) -> dict:
    """Copia del proceso. Lanza KeyError si no existe."""
    return copy.deepcopy(_PROCESOS[proceso_id])


# Pregunta con la que la pantalla de bienvenida pide cada proceso, y su descripción corta para la tarjeta.
TARJETAS = {
    "peticion_mensaje": ("Enséñame cómo entra una petición por WhatsApp", "mail",
                         "Del mensaje del huésped a la respuesta confirmada por recepción, contrastando todas las fuentes."),
    "reserva_canal": ("Enséñame qué pasa cuando entra una reserva de Booking", "refresh",
                      "La reserva entra por RoomCloud con prioridad 1 y avisa a las peticiones que competían."),
    "checkin_parte": ("Enséñame el proceso del check-in al parte de viajeros", "door",
                      "Documento, pago, parte a SES.Hospedajes y paso a OfiHotel."),
    "overbooking_cierre": ("Enséñame cómo se evita un overbooking", "alert",
                           "Aviso de ocupación completa y propuesta de cierre en RoomCloud."),
    "fuente_unica": ("Enséñame cómo funciona la fuente única", "layers",
                     "Cómo la aplicación unifica los sistemas, calcula el semáforo y detecta conflictos."),
    "prioridades": ("Enséñame quién gana cuando dos fuentes compiten", "list",
                    "Correo contra WhatsApp por la última individual y después una reserva de Booking."),
}
