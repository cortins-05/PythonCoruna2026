"""Adaptador de salida hacia OfiHotel: el hueco abierto.

OfiHotel no tiene API pública, así que hoy la única salida es preparar los datos para copiarlos.
Cuando Ofimática confirme una vía (importación, servicio web de partners, módulos OfiScan o
OfiCheckin) o se acepte un script de automatización de pantalla en el PC del hotel, solo hay que
sustituir `preparar_copia` por un adaptador que escriba de verdad.
"""

ORDEN = [
    ("Apellidos", lambda h: f"{h['apellido1']} {h['apellido2']}".strip()),
    ("Nombre", lambda h: h["nombre"]),
    ("Documento", lambda h: f"{h['tipo_documento']} {h['numero_documento']}"),
    ("Nacionalidad", lambda h: h["nacionalidad"]),
    ("Fecha de nacimiento", lambda h: h["fecha_nacimiento"]),
    ("Dirección", lambda h: f"{h['direccion']}, {h['codigo_postal']} {h['localidad']} ({h['pais']})"),
    ("Teléfono", lambda h: h["telefono"]),
    ("Correo electrónico", lambda h: h["email"]),
]


def preparar_copia(exp: dict) -> dict:
    h = exp["huesped"]
    filas = [{"campo": etiqueta, "valor": f(h)} for etiqueta, f in ORDEN]
    filas.append({"campo": "Llegada / salida", "valor": f"{exp['checkin_prevista']} a {exp['checkout_prevista']}"})
    if exp.get("empresa", {}).get("cif"):
        e = exp["empresa"]
        filas.append({"campo": "Empresa (facturación)", "valor": f"{e['razon_social']} · {e['cif']} · {e['direccion']}"})
    return {"modo": "copia asistida (sin API de OfiHotel)", "filas": filas}
