"""Relleno determinista del nivel de semilla `demo`: la semilla `completa` más reservas, estancias y mensajes de otros días.

El relleno se aplica DESPUÉS de `completa`, que no se toca, y pasa por las mismas funciones que usa la API (nuevo_expediente,
guardar_huesped, guardar_pago, confirmar_parte, nuevo_walkin, comunicaciones.registrar y confirmar...). Para que cada rastro lleve su
hora real (ayer por la tarde, o hoy temprano) se mueve el reloj de la demo hacia atrás mientras se aplica cada paso y se devuelve a las
09:00 al terminar. No hay random ni reloj real: los ids salen de los contadores del almacén y el orden de los pasos es fijo.

Reglas que respeta el relleno (las comprueban los tests): `completa` y sus veredictos guionizados no cambian, ningún tipo de habitación
llega a estar lleno ninguna noche salvo la doble del 24, y ninguna fila de OfiHotel sin referencia comparte habitación con otra.
"""
from datetime import datetime

from . import comunicaciones, hub
from .adapters import ofihotel_lectura
from .store import INICIO_DEMO
from .validators import letra_dni

RELOJ_FINAL = "2026-10-24T09:00"

# ---------------------------------------------------------------- reservas futuras de RoomCloud
# (portal, id_canal, nombre, apellidos, país, teléfono, correo, tipo, desde, hasta, adultos, niños, importe, medio de pago, notas, dlm)
RESERVAS_FUTURAS = [
    ("1", "BK-5520144", "Hans", "Weber", "DE", "+4915112345678", "hans.weber@example.de", "TPL-STD", "2026-10-25", "2026-10-28", 3, 0, "372.00", "TARJETA", "", "2026-10-12T10:20"),
    ("0", "WEB-90140", "Elena", "Castro Vidal", "ES", "+34622100201", "elena.castro@example.com", "SGL-STD", "2026-10-25", "2026-10-27", 1, 0, "176.00", "TRANSFERENCIA", "Viaja por trabajo.", "2026-10-15T09:05"),
    ("1", "BK-5531207", "James", "OConnor", "IE", "+353861234567", "james.oconnor@example.ie", "DBL-STD", "2026-10-30", "2026-11-01", 2, 0, "208.00", "TARJETA", "", "2026-10-16T18:40"),
    ("2", "EX-7741530", "Sven", "Lindgren", "SE", "+46701234567", "sven.lindgren@example.se", "DBL-STD", "2026-10-31", "2026-11-01", 2, 0, "118.00", "TARJETA", "", "2026-10-17T21:12"),
    ("0", "WEB-90141", "Rui", "Carvalho", "PT", "+351912345678", "rui.carvalho@example.pt", "TPL-STD", "2026-10-31", "2026-11-03", 3, 0, "441.00", "TRANSFERENCIA", "", "2026-10-18T11:30"),
    ("1", "BK-5536120", "Laura", "Fontán Ríos", "ES", "+34622100202", "laura.fontan@example.com", "SGL-STD", "2026-10-29", "2026-10-31", 1, 0, "176.00", "TARJETA", "Viaja por trabajo.", "2026-10-19T08:15"),
    ("2", "EX-7745012", "Giulia", "Ferri", "IT", "+393331234567", "giulia.ferri@example.it", "FAM-STD", "2026-10-30", "2026-11-02", 2, 2, "489.00", "TARJETA", "", "2026-10-20T19:02"),
    ("1", "BK-5544871", "Tomás", "Lago Pena", "ES", "+34622100203", "tomas.lago@example.com", "SGL-STD", "2026-11-02", "2026-11-05", 1, 0, "264.00", "TARJETA", "", "2026-10-21T12:45"),
    ("0", "WEB-90152", "Chloé", "Bernard", "FR", "+33612340099", "chloe.bernard@example.fr", "DBL-STD", "2026-11-04", "2026-11-07", 2, 0, "327.00", "TARJETA", "", "2026-10-22T16:20"),
    ("2", "EX-7750398", "Oliver", "Smith", "GB", "+447911123456", "oliver.smith@example.co.uk", "SUI-STD", "2026-10-31", "2026-11-02", 2, 0, "420.00", "TARJETA", "", "2026-10-22T20:55"),
    ("1", "BK-5552260", "Familia", "Iglesias", "ES", "+34622100204", "familia.iglesias@example.com", "FAM-STD", "2026-11-03", "2026-11-06", 2, 2, "465.00", "TARJETA", "", "2026-10-23T10:10"),
    ("0", "WEB-90160", "Nuria", "Pazos", "ES", "+34622100205", "nuria.pazos@example.com", "TPL-STD", "2026-11-05", "2026-11-07", 3, 0, "294.00", "TRANSFERENCIA", "", "2026-10-23T17:35"),
]
# Reservas de canal más: huéspedes en casa, llegadas de hoy, una cancelada que sigue viva en OfiHotel y relleno de fin de semana.
# (mismas columnas que arriba)
RESERVAS_EN_CASA = [
    ("1", "BK-5498302", "Aino", "Virtanen", "FI", "+358401234567", "aino.virtanen@example.fi", "SUI-STD", "2026-10-23", "2026-10-26", 2, 0, "630.00", "TARJETA", "", "2026-10-10T09:30"),
    ("2", "EX-7688120", "Familia", "Oliveira", "PT", "+351913000111", "familia.oliveira@example.pt", "TPL-STD", "2026-10-21", "2026-10-24", 3, 0, "351.00", "TARJETA", "", "2026-10-05T14:10"),
    ("1", "BK-5471022", "Familia", "Santos", "ES", "+34622100206", "familia.santos@example.com", "FAM-STD", "2026-10-21", "2026-10-24", 2, 2, "429.00", "TARJETA", "", "2026-10-04T10:00"),
    ("0", "WEB-90105", "Brais", "Seoane", "ES", "+34622100207", "brais.seoane@example.com", "SGL-STD", "2026-10-23", "2026-10-24", 1, 0, "88.00", "TARJETA", "", "2026-10-20T08:05"),
    ("1", "BK-5489917", "Elisa", "Marín", "ES", "+34622100208", "elisa.marin@example.com", "DBL-STD", "2026-10-22", "2026-10-24", 2, 0, "190.00", "TARJETA", "", "2026-10-09T18:20"),
]
LLEGADAS_HOY = [
    ("2", "EX-7755104", "Sara", "Mendes", "PT", "+351914222333", "sara.mendes@example.pt", "TPL-STD", "2026-10-24", "2026-10-26", 3, 0, "234.00", "TARJETA", "", "2026-10-21T22:10"),
    ("1", "BK-5558831", "Familia", "Novoa", "ES", "+34622100209", "familia.novoa@example.com", "FAM-STD", "2026-10-24", "2026-10-27", 2, 2, "462.00", "TARJETA", "", "2026-10-22T09:45"),
]
CANCELADA_VIVA = ("1", "BK-5560012", "Patricia", "Neira", "ES", "+34622100210", "patricia.neira@example.com", "TPL-STD", "2026-10-27", "2026-10-29", 2, 0, "216.00", "TARJETA", "",
                  "2026-10-23T23:30")
# Reservas más para llenar el fin de semana del 31 y la semana siguiente sin acercarse a ningún límite.
RESERVAS_EXTRA = [
    ("1", "BK-5562201", "Marc", "Dupont", "FR", "+33687654321", "marc.dupont@example.fr", "SUI-STD", "2026-10-29", "2026-10-31", 2, 0, "420.00", "TARJETA", "", "2026-10-22T11:11"),
    ("2", "EX-7760090", "Xoán", "Barreiro Neira", "ES", "+34622100214", "xoan.barreiro@example.com", "DBL-STD", "2026-10-30", "2026-10-31", 2, 0, "104.00", "TARJETA", "", "2026-10-23T13:40"),
    ("0", "WEB-90174", "Beatriz", "Souto Mera", "ES", "+34622100215", "beatriz.souto@example.com", "DBL-STD", "2026-11-03", "2026-11-04", 2, 0, "98.00", "TARJETA", "", "2026-10-23T14:50"),
    ("1", "BK-5577015", "Lorenzo", "Pita Gil", "ES", "+34622100216", "lorenzo.pita@example.com", "TPL-STD", "2026-10-28", "2026-10-31", 3, 0, "354.00", "TARJETA", "", "2026-10-22T09:20"),
    ("2", "EX-7762410", "Paula", "Nogueira", "ES", "+34622100217", "paula.nogueira@example.com", "TPL-STD", "2026-11-03", "2026-11-05", 3, 0, "236.00", "TARJETA", "", "2026-10-23T21:00"),
    ("0", "WEB-90170", "Miguel", "Casal Varela", "ES", "+34622100211", "miguel.casal@example.com", "TPL-STD", "2026-10-26", "2026-10-28", 3, 0, "236.00", "TRANSFERENCIA", "", "2026-10-23T15:25"),
    ("1", "BK-5570140", "Jonas", "Becker", "DE", "+4917612345678", "jonas.becker@example.de", "FAM-STD", "2026-11-02", "2026-11-03", 2, 1, "157.00", "TARJETA", "", "2026-10-21T20:00"),
    ("2", "EX-7761733", "Sofía", "Rey Lorenzo", "ES", "+34622100212", "sofia.rey@example.com", "SGL-STD", "2026-11-05", "2026-11-07", 1, 0, "176.00", "TARJETA", "", "2026-10-22T17:30"),
    ("1", "BK-5574400", "Peter", "Jansen", "NL", "+31612345678", "peter.jansen@example.nl", "SUI-STD", "2026-11-04", "2026-11-07", 2, 0, "615.00", "TARJETA", "", "2026-10-23T19:15"),
    ("0", "WEB-90172", "Carmen", "Dopico", "ES", "+34622100213", "carmen.dopico@example.com", "SGL-STD", "2026-11-01", "2026-11-02", 1, 0, "92.00", "TARJETA", "", "2026-10-23T20:05"),
]

# ---------------------------------------------------------------- huéspedes que ya hicieron el check-in
# (id de la reserva, nombre, apellido1, apellido2, sexo, nacimiento, nacionalidad, tipo de documento, número, país, localidad, hora de check-in, medio de pago)
HUESPEDES = {
    "1-BK-5498302": ("Aino", "Virtanen", "", "M", "1985-06-02", "FIN", "PAS", "XP1234567", "FIN", "Helsinki", "2026-10-23T16:00", "tarjeta"),
    "2-EX-7688120": ("Familia", "Oliveira", "Sá", "M", "1979-11-21", "PRT", "PAS", "CD4455667", "PRT", "Porto", "2026-10-21T18:00", "tarjeta"),
    "1-BK-5471022": ("Familia", "Santos", "Lage", "H", "1982-02-08", "ESP", "NIF", f"{43210987:08d}{letra_dni(43210987)}", "ESP", "Lugo", "2026-10-21T19:00", "tarjeta"),
    "0-WEB-90105": ("Brais", "Seoane", "Pardo", "H", "1991-09-30", "ESP", "NIF", f"{32165498:08d}{letra_dni(32165498)}", "ESP", "Ourense", "2026-10-23T15:00", "tarjeta"),
    "1-BK-5489917": ("Elisa", "Marín", "Nieto", "M", "1987-07-14", "ESP", "NIF", f"{35792468:08d}{letra_dni(35792468)}", "ESP", "Vigo", "2026-10-22T17:00", "tarjeta"),
}

# ---------------------------------------------------------------- walk-ins de recepción
# (nombre, apellidos, teléfono, tipo, desde, hasta, personas, hora a la que se registró)
WALKINS = [
    ("Irene", "Castiñeira", "+34622100301", "TPL-STD", "2026-10-28", "2026-10-30", 3, "2026-10-23T12:00"),
    ("Mercedes", "Varela", "+34622100302", "SUI-STD", "2026-11-02", "2026-11-04", 2, "2026-10-23T17:00"),
    ("Pedro", "Quintela", "+34622100303", "TPL-STD", "2026-11-01", "2026-11-02", 2, "2026-10-23T19:00"),
]

# ---------------------------------------------------------------- OfiHotel: la lectura de ayer
# (id, huésped, habitación, tipo, entrada, salida, estado, referencia, personas). La referencia vacía es una reserva de teléfono.
ESTANCIAS_OFIHOTEL = [
    # reservas de canal que ya estaban pasadas a OfiHotel ayer
    ("OH-10250", "Weber", "401", "TPL-STD", "2026-10-25", "2026-10-28", "reservada", "1-BK-5520144", 3),
    ("OH-10251", "Castro", "302", "SGL-STD", "2026-10-25", "2026-10-27", "reservada", "0-WEB-90140", 1),
    ("OH-10252", "OConnor", "106", "DBL-STD", "2026-10-30", "2026-11-01", "reservada", "1-BK-5531207", 2),
    ("OH-10253", "Lindgren", "107", "DBL-STD", "2026-10-31", "2026-11-01", "reservada", "2-EX-7741530", 2),
    ("OH-10254", "Carvalho", "402", "TPL-STD", "2026-10-31", "2026-11-03", "reservada", "0-WEB-90141", 3),
    ("OH-10255", "Fontán", "301", "SGL-STD", "2026-10-29", "2026-10-31", "reservada", "1-BK-5536120", 1),
    ("OH-10256", "Ferri", "501", "FAM-STD", "2026-10-30", "2026-11-02", "reservada", "2-EX-7745012", 4),
    ("OH-10257", "Lago", "302", "SGL-STD", "2026-11-02", "2026-11-04", "reservada", "1-BK-5544871", 1),  # RoomCloud dice hasta el 05: conflicto rojo
    ("OH-10258", "Smith", "602", "SUI-STD", "2026-10-31", "2026-11-02", "reservada", "2-EX-7750398", 2),
    ("OH-10259", "Dupont", "601", "SUI-STD", "2026-10-29", "2026-10-31", "reservada", "1-BK-5562201", 2),
    ("OH-10260", "Becker", "502", "FAM-STD", "2026-11-02", "2026-11-03", "reservada", "1-BK-5570140", 3),
    # huéspedes en casa
    ("OH-10261", "Virtanen", "601", "SUI-STD", "2026-10-23", "2026-10-26", "en_casa", "1-BK-5498302", 2),
    ("OH-10262", "Oliveira", "401", "TPL-STD", "2026-10-21", "2026-10-24", "en_casa", "2-EX-7688120", 3),
    ("OH-10263", "Santos", "501", "FAM-STD", "2026-10-21", "2026-10-24", "en_casa", "1-BK-5471022", 4),
    ("OH-10264", "Seoane", "303", "SGL-STD", "2026-10-23", "2026-10-24", "en_casa", "0-WEB-90105", 1),
    # llegadas de hoy
    ("OH-10265", "Mendes", "402", "TPL-STD", "2026-10-24", "2026-10-26", "reservada", "2-EX-7755104", 3),
    ("OH-10266", "Novoa", "502", "FAM-STD", "2026-10-24", "2026-10-27", "reservada", "1-BK-5558831", 4),
    # cancelada en RoomCloud y todavía viva aquí
    ("OH-10267", "Neira", "403", "TPL-STD", "2026-10-27", "2026-10-29", "reservada", "1-BK-5560012", 2),
    # reservas por teléfono, solo en OfiHotel
    ("OH-10270", "Cancela", "301", "SGL-STD", "2026-10-27", "2026-10-29", "reservada", "", 1),
    ("OH-10271", "Rivas", "501", "FAM-STD", "2026-10-27", "2026-10-29", "reservada", "", 3),
    ("OH-10272", "Soto", "602", "SUI-STD", "2026-10-27", "2026-10-29", "reservada", "", 2),
    ("OH-10273", "Vázquez", "108", "DBL-STD", "2026-10-29", "2026-10-30", "reservada", "", 2),
    ("OH-10274", "Ledo Camba", "403", "TPL-STD", "2026-10-30", "2026-10-31", "reservada", "", 2),
    ("OH-10275", "Miramontes", "502", "FAM-STD", "2026-11-06", "2026-11-08", "reservada", "", 4),
]
# El relleno no repite habitación: 601 y 501 se reutilizan solo cuando las fechas no se solapan (se comprueba en los tests).

# ---------------------------------------------------------------- comunicaciones
# (canal, nombre, contacto, asunto, texto, ts, hora de la respuesta, qué pasa)
RESPONDIDAS = [
    ("correo", "Henrik Olsen", "henrik.olsen@example.no", "Room request",
     "Hello, do you have a double room available from 5 to 7 november for 2 people? Kind regards, Henrik Olsen.", "2026-10-23T16:10", "2026-10-23T17:00", "reserva", None),
    ("correo", "Kevin Ruiz", "kevin.ruiz@example.com", "Habitación doble",
     "Buenas tardes, necesitamos una habitación doble del 3 al 4 de noviembre para 2 personas. Un saludo, Kevin.", "2026-10-23T17:40", "2026-10-23T18:00", "reserva", None),
    ("whatsapp", "Antón Rodríguez", "34622100401", "", "Boas, ¿tenéis una individual libre del 31 de octubre al 1 de noviembre? Gracias.", "2026-10-23T19:05", "2026-10-23T20:00", "reserva", None),
    ("whatsapp", "Rosa Dopico", "34622100402", "", "Buenas, ¿hasta qué hora sirven el desayuno?", "2026-10-24T06:40", "2026-10-24T07:00", "pregunta", None),
    ("correo", "Posicionamiento Web Pro", "ofertas@seo-rapido.example", "Aumente sus visitas",
     "Hola, mejoramos el posicionamiento de su web. Responda a este correo para recibir una oferta.", "2026-10-24T06:20", "2026-10-24T07:00", "descartar", None),
    ("correo", "Jean-Luc Moreau", "jeanluc.moreau@example.fr", "Chambre pour ce soir",
     "Bonjour, avez-vous une chambre double libre du 24 au 25 octobre pour 2 personnes ? Merci.", "2026-10-24T06:50", "2026-10-24T07:00", "sin_hueco", None),
]
# Pendientes sin petición de habitación. El contacto es el de una reserva cuando el mensaje se enlaza con ella.
PENDIENTES = [
    ("whatsapp", "Carlos Lema", "34622100403", "", "Hola, ¿tenéis parking para el coche? Llegamos mañana.", "2026-10-24T07:15", None),
    ("correo", "Chloé Bernard", "chloe.bernard@example.fr", "Annulation",
     "Bonjour, je dois annuler ma réservation à cause d'un imprévu. Pouvez-vous me confirmer l'annulation ? Merci.", "2026-10-24T07:22", "cambio"),
    ("whatsapp", "Rui Carvalho", "+351912345678", "", "Olá, podemos cambiar la salida un día más tarde? Preferimos quedarnos una noche más.", "2026-10-24T07:30", "cambio"),
    ("correo", "Sara Mendes", "sara.mendes@example.pt", "Check-in",
     "Buenos días, llegamos en tren a las 11:00. ¿Sería posible hacer el check-in antes de la hora habitual?", "2026-10-24T07:40", None),
]


def _a(store, iso: str) -> None:
    """Pone el reloj de la demo en la hora pedida (en horas enteras) para que lo que se haga a continuación quede con esa hora."""
    store.db["reloj_h"] = int((datetime.fromisoformat(iso) - INICIO_DEMO).total_seconds() // 3600)


def _reserva(fila) -> dict:
    portal, canal, nombre, apellidos, pais, tel, correo, tipo, desde, hasta, adultos, ninos, importe, pago, notas, dlm = fila
    return {"portal_id": portal, "id_canal": canal, "dlm": dlm, "estado_rc": "4", "checkin": desde, "checkout": hasta, "nombre": nombre,
            "apellidos": apellidos, "telefono": tel, "email": correo, "pais": pais, "importe": importe, "medio_pago": pago, "notas": notas,
            "habitaciones": [{"tipo": tipo, "tarifa": "BAR", "adultos": str(adultos), "ninos": str(ninos)}]}


def _entra_reserva(principal, store, fila, cancelada: bool = False) -> dict:
    """Entra una reserva de RoomCloud con la hora a la que se hizo, igual que la sincronización."""
    r = _reserva(fila)
    _a(store, r["dlm"][:13] + ":00")
    exp = principal.nuevo_expediente(r)
    nombre = f"{r['nombre']} {r['apellidos']}".strip()
    if cancelada:
        exp["estado"] = "cancelada"
        principal.anotar(exp, "Reserva ya cancelada en RoomCloud al leerla", "Sistema")
        store.db["expedientes"][exp["id"]] = exp
    else:
        store.db["expedientes"][exp["id"]] = exp
        hub.registrar_evento(store, "roomcloud", "reserva_nueva", nombre, f"Reserva {exp['id']}: {r['checkin']} a {r['checkout']}", exp["id"])
    return exp


def _checkin(principal, store, exp_id: str, con_parte: bool) -> None:
    (nombre, ap1, ap2, sexo, nacimiento, nacionalidad, tipo_doc, numero, pais, localidad, hora, medio) = HUESPEDES[exp_id]
    exp = store.db["expedientes"][exp_id]
    _a(store, hora)
    datos = {"nombre": nombre, "apellido1": ap1, "apellido2": ap2, "sexo": sexo, "fecha_nacimiento": nacimiento, "nacionalidad": nacionalidad,
             "tipo_documento": tipo_doc, "numero_documento": numero, "numero_soporte": "", "direccion": f"Rúa Nova {len(ap1) + 3}",
             "localidad": localidad, "codigo_postal": "15000", "pais": pais, "telefono": exp["reserva"]["telefono"], "email": exp["reserva"]["email"]}
    principal.guardar_huesped(exp_id, principal.HuespedIn(**datos))
    principal.guardar_pago(exp_id, principal.PagoIn(medio=medio))
    if con_parte:
        principal.confirmar_parte(exp_id, principal.ActorIn(actor="Flor"))


def _ofihotel(store) -> None:
    lectura = store.db["ofihotel"]
    nuevas = [{"id_ofihotel": i, "huesped": h, "habitacion": hab, "tipo": tipo, "entrada": ent, "salida": sal, "estado": estado,
               "numero_externo": ref.split("-", 1)[1] if ref else "", "ref_externa": ref, "personas": p}
              for (i, h, hab, tipo, ent, sal, estado, ref, p) in ESTANCIAS_OFIHOTEL]
    lectura["estancias"].extend(nuevas)
    lectura["ocupaciones"].extend(ofihotel_lectura._derivar_ocupaciones(nuevas))


def _responder(store, fila) -> None:
    canal, nombre, contacto, asunto, texto, ts, respuesta, accion, tipo = fila
    _a(store, respuesta)
    com = comunicaciones.registrar(store, canal, nombre, contacto, texto, asunto, ts=ts)
    if accion == "descartar":
        comunicaciones.descartar(store, com["id"], "Flor")
    else:
        comunicaciones.confirmar(store, com["id"], "Flor")


def rellenar(principal, store) -> None:
    """Añade el relleno a una semilla `completa` ya aplicada y deja el reloj en las 09:00 del 24/10."""
    for fila in RESERVAS_FUTURAS + RESERVAS_EXTRA:
        _entra_reserva(principal, store, fila)
    for fila in RESERVAS_EN_CASA + LLEGADAS_HOY:
        _entra_reserva(principal, store, fila)
    _entra_reserva(principal, store, CANCELADA_VIVA, cancelada=True)
    for exp_id in HUESPEDES:
        # el parte de Brais queda sin enviar: con el check-in de ayer a las 15:00 le quedan 6 horas a las 09:00
        _checkin(principal, store, exp_id, con_parte=exp_id != "0-WEB-90105")
    for nombre, apellidos, tel, tipo, desde, hasta, personas, hora in WALKINS:
        _a(store, hora)
        principal.nuevo_walkin(principal.WalkinIn(nombre=nombre, apellidos=apellidos, telefono=tel, tipo=tipo, checkin=desde, checkout=hasta,
                                                  personas=personas))
    _ofihotel(store)
    for fila in RESPONDIDAS:
        _responder(store, fila)
    for canal, nombre, contacto, asunto, texto, ts, tipo in PENDIENTES:
        _a(store, ts[:13] + ":00")
        com = comunicaciones.registrar(store, canal, nombre, contacto, texto, asunto, ts=ts)
        if tipo:
            com["tipo"] = tipo
    _a(store, RELOJ_FINAL)
    for com in store.db["comunicaciones"]:
        comunicaciones.vista(store, com)  # fija el veredicto de partida, como en `completa`
