"""Prioridad de las fuentes: quién gana cuando dos cosas compiten por la misma habitación.

La escalera es esta, de más a menos autoridad, y es una regla de negocio configurable (hoy, la de la demo):

1. RoomCloud: reservas de Booking, Expedia y la web, confirmadas y con garantía de pago.
2. OfiHotel (los datos de ayer): lo que ya está registrado en el programa del hotel.
3. Recepción: reservas físicas y peticiones que recepción ya ha confirmado desde la aplicación.
4. Correo: una petición de fechas por correo, todavía sin confirmar.
5. WhatsApp: una petición de fechas por WhatsApp, todavía sin confirmar.

Los niveles 1 a 3 son **firmes** y bloquean la habitación. Los niveles 4 y 5 son **peticiones**: nunca desplazan a una reserva firme, y entre
dos peticiones gana la de nivel más alto y, a igual nivel, la que llegó antes.
"""

NIVELES = [
    {"nivel": 1, "id": "roomcloud", "nombre": "RoomCloud", "tipo": "firme", "icono": "refresh",
     "descripcion": "Booking, Expedia y la web, con garantía de pago"},
    {"nivel": 2, "id": "ofihotel", "nombre": "OfiHotel", "tipo": "firme", "icono": "building",
     "descripcion": "El programa del hotel, con los datos de ayer"},
    {"nivel": 3, "id": "recepcion", "nombre": "Recepción", "tipo": "firme", "icono": "door",
     "descripcion": "Walk-ins y peticiones ya confirmadas"},
    {"nivel": 4, "id": "correo", "nombre": "Correo", "tipo": "peticion", "icono": "mail",
     "descripcion": "Petición sin confirmar"},
    {"nivel": 5, "id": "whatsapp", "nombre": "WhatsApp", "tipo": "peticion", "icono": "message",
     "descripcion": "Petición sin confirmar"},
]
REGLAS = [
    "Gana la fuente de mayor prioridad: lo firme bloquea la habitación y una petición nunca la desplaza.",
    "Entre dos peticiones gana el nivel más alto y, a igual nivel, la que llegó antes.",
    "Si RoomCloud ocupa el hueco de una petición, la petición pasa a no disponible y se avisa.",
]
_POR_ID = {n["id"]: n for n in NIVELES}
_GRUPO_DE_ORIGEN = {"roomcloud": "roomcloud", "ofihotel": "ofihotel"}


def grupo_de_origen(origen: str) -> str:
    """Grupo de prioridad de lo que ocupa una habitación: lo que no es de RoomCloud ni de OfiHotel lo ha metido recepción."""
    return _GRUPO_DE_ORIGEN.get(origen, "recepcion")


def info(grupo: str) -> dict:
    n = _POR_ID[grupo]
    return {"nivel": n["nivel"], "fuente": n["nombre"], "id": n["id"], "tipo": n["tipo"]}


def nivel_de_origen(origen: str) -> dict:
    return info(grupo_de_origen(origen))


def nivel_de_canal(canal: str) -> dict:
    return info("correo" if canal == "correo" else "whatsapp")
