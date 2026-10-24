"""Validaciones deterministas del expediente: nada de esto pasa por un LLM."""
from datetime import date

LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"

# Lista orientativa de campos del parte por huésped adulto (RD 933/2021). No hay XSD oficial
# público, así que esta lista no está validada contra el esquema del Ministerio.
CAMPOS_PARTE = {
    "nombre": "Nombre",
    "apellido1": "Primer apellido",
    "sexo": "Sexo",
    "fecha_nacimiento": "Fecha de nacimiento",
    "nacionalidad": "Nacionalidad",
    "tipo_documento": "Tipo de documento",
    "numero_documento": "Número de documento",
    "direccion": "Dirección",
    "localidad": "Localidad",
    "codigo_postal": "Código postal",
    "pais": "País de residencia",
    "telefono": "Teléfono",
    "email": "Correo electrónico",
}


def letra_dni(numero: int) -> str:
    return LETRAS_DNI[numero % 23]


def validar_documento(tipo: str, numero: str) -> list[str]:
    """Comprueba la letra de control de NIF y NIE. El pasaporte no tiene dígito de control."""
    numero = (numero or "").strip().upper()
    if not tipo or not numero:
        return []
    if tipo == "NIF":
        if len(numero) != 9 or not numero[:8].isdigit():
            return ["El NIF debe tener 8 dígitos y una letra"]
        if letra_dni(int(numero[:8])) != numero[8]:
            return [f"La letra del NIF no cuadra (debería ser {letra_dni(int(numero[:8]))})"]
    if tipo == "NIE":
        if len(numero) != 9 or numero[0] not in "XYZ" or not numero[1:8].isdigit():
            return ["El NIE debe tener una letra inicial, 7 dígitos y una letra final"]
        base = int(str("XYZ".index(numero[0])) + numero[1:8])
        if letra_dni(base) != numero[8]:
            return [f"La letra del NIE no cuadra (debería ser {letra_dni(base)})"]
    return []


def validar_fecha_nacimiento(valor: str, hoy: date) -> list[str]:
    if not valor:
        return []
    try:
        nacimiento = date.fromisoformat(valor)
    except ValueError:
        return ["La fecha de nacimiento no tiene formato AAAA-MM-DD"]
    if nacimiento >= hoy:
        return ["La fecha de nacimiento es futura"]
    if (hoy - nacimiento).days > 120 * 366:
        return ["La fecha de nacimiento da más de 120 años"]
    return []


def campos_que_faltan(huesped: dict, pago: dict) -> list[str]:
    faltan = [etiqueta for campo, etiqueta in CAMPOS_PARTE.items() if not str(huesped.get(campo, "")).strip()]
    if not str(pago.get("medio", "")).strip():
        faltan.append("Medio de pago")
    return faltan


def problemas_huesped(huesped: dict, hoy: date) -> list[str]:
    return validar_documento(huesped.get("tipo_documento", ""), huesped.get("numero_documento", "")) + \
        validar_fecha_nacimiento(huesped.get("fecha_nacimiento", ""), hoy)
