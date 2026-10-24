"""Correo: entrada con la forma de un mensaje de la API de Gmail y salida simulada.

SIMULADO. No hay conexión con ninguna cuenta: conectar Gmail de verdad exige un proyecto de Google Cloud, el
consentimiento OAuth del hotel y revisar los permisos que se piden. Lo que sí tiene la forma de producción es el
recurso de mensaje de la API de Gmail (`users.messages`): `id`, `threadId`, `labelIds`, `snippet`, `internalDate`
en milisegundos como texto y `payload` con `headers` (From, To y Subject) y el cuerpo en base64url. Un lector
real de Gmail solo tiene que entregar esos mensajes a `parsear` y el resto del hub no cambia.

El reloj de la demo es un datetime sin zona. Para que `internalDate` no dependa de la máquina ni se vuelva
ambiguo con el cambio de hora de octubre, se trata ese reloj como si fuera UTC al ir y al volver.
"""
import base64
import binascii
import hashlib
import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr

from .. import hub, plantillas

DIRECCION_HOTEL = "recepcion@hoteldemo.example"
ASUNTO_MAX = 200
NOMBRE_MAX = 80
CUERPO_MAX = 20_000
_CONTROL = re.compile(r"[\x00-\x1f\x7f  ]+")


def _una_linea(valor, maximo: int) -> str:
    """Quita saltos de línea y caracteres de control, que en una cabecera de correo abrirían una cabecera nueva."""
    return _CONTROL.sub(" ", str(valor or "")).strip()[:maximo]


def _nombre_de_cabecera(nombre) -> str:
    return re.sub(r'["<>\\]', "", _una_linea(nombre, NOMBRE_MAX)).strip()


def construir_mensaje_gmail(de: str, nombre: str, asunto: str, cuerpo: str, ahora: datetime) -> dict:
    """Mensaje entrante con la forma del recurso `users.messages` de la API de Gmail (formato `full`)."""
    if not plantillas.email_valido(de):
        raise ValueError("La dirección del remitente no es válida")
    texto = str(cuerpo or "")
    if len(texto) > CUERPO_MAX:
        raise ValueError(f"El cuerpo supera los {CUERPO_MAX} caracteres")
    asunto = _una_linea(asunto, ASUNTO_MAX)
    marca = int(ahora.replace(tzinfo=timezone.utc).timestamp() * 1000)
    identificador = hashlib.sha1(f"{de}|{asunto}|{marca}|{texto}".encode("utf-8")).hexdigest()[:16]
    datos = texto.encode("utf-8")
    remitente = f'"{_nombre_de_cabecera(nombre)}" <{de}>' if _nombre_de_cabecera(nombre) else de
    return {
        "id": identificador,
        "threadId": identificador,
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": " ".join(texto.split())[:100],
        "internalDate": str(marca),
        "sizeEstimate": len(datos),
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "From", "value": remitente},
                        {"name": "To", "value": DIRECCION_HOTEL},
                        {"name": "Subject", "value": asunto}],
            "body": {"size": len(datos), "data": base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")},
        },
    }


def _decodificar(datos: str) -> str:
    """Decodifica base64url con o sin relleno y rechaza cualquier carácter que no sea del alfabeto (`validate=True`)."""
    try:
        return base64.b64decode(datos + "=" * (-len(datos) % 4), altchars=b"-_", validate=True).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError, TypeError) as error:
        raise ValueError("El cuerpo del mensaje no se puede decodificar") from error


def _texto_plano(parte: dict) -> str | None:
    """Primer cuerpo text/plain del mensaje, bajando por las partes si es multipart."""
    if str(parte.get("mimeType", "")).startswith("text/plain") and parte.get("body", {}).get("data"):
        return _decodificar(parte["body"]["data"])
    for hija in parte.get("parts") or []:
        encontrado = _texto_plano(hija)
        if encontrado is not None:
            return encontrado
    return None


def _cabecera(valor: str) -> str:
    try:
        return str(make_header(decode_header(valor)))
    except Exception:  # una cabecera mal codificada no debe tumbar la lectura del mensaje
        return valor


def parsear(mensaje: dict) -> dict:
    """Invierte `construir_mensaje_gmail`: saca remitente, asunto, texto y hora de un mensaje con la forma de Gmail."""
    if not isinstance(mensaje, dict) or not isinstance(mensaje.get("payload"), dict):
        raise ValueError("No tiene la forma de un mensaje de Gmail")
    cabeceras = {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in mensaje["payload"].get("headers") or []}
    nombre, direccion = parseaddr(_cabecera(cabeceras.get("from", "")))
    try:
        marca = int(mensaje.get("internalDate", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("internalDate debe ser una cifra en milisegundos") from error
    return {
        "id": str(mensaje.get("id", "")),
        "thread_id": str(mensaje.get("threadId", "")),
        "de": direccion.strip(),
        "nombre": _nombre_de_cabecera(nombre),
        "para": _cabecera(cabeceras.get("to", "")),
        "asunto": _una_linea(_cabecera(cabeceras.get("subject", "")), ASUNTO_MAX),
        "texto": (_texto_plano(mensaje["payload"]) or "")[:CUERPO_MAX],
        "ts": datetime.fromtimestamp(marca / 1000, tz=timezone.utc).replace(tzinfo=None),
        "etiquetas": [str(e) for e in mensaje.get("labelIds") or []],
    }


def enviar_simulado(store, destinatario: str, asunto: str, cuerpo: str, adjuntos: list[dict] | None = None,
                    expediente_id: str | None = None, datos: dict | None = None) -> dict:
    """Registra el envío como evento `correo_saliente_simulado` y lo guarda en `db["outbox"]`. No sale nada del equipo.

    Los adjuntos son solo descriptores (`nombre`, `documento_id`, `tipo_mime`): el contenido del PDF no se guarda aquí.
    Devuelve la entrada del outbox, que incluye el `evento_id`.
    """
    if not plantillas.email_valido(destinatario):
        raise hub.ErrorNegocio("El correo de destino no es válido", 422)
    asunto = _una_linea(asunto, ASUNTO_MAX)
    adjuntos = [{"nombre": _una_linea(a.get("nombre"), 120), "documento_id": a.get("documento_id"),
                 "tipo_mime": a.get("tipo_mime", "application/pdf")} for a in adjuntos or []]
    if expediente_id is None:
        exp = hub.buscar_por_correo(store.db, destinatario)
        expediente_id = exp["id"] if exp else None
    ev = hub.registrar_evento(store, "correo", "correo_saliente_simulado", remitente=destinatario, contenido=str(cuerpo),
                              expediente_id=expediente_id,
                              datos={"correo": destinatario.lower(), "asunto": asunto, "adjuntos": adjuntos, "simulado": True,
                                     **(datos or {})})
    entrada = {"evento_id": ev["id"], "ts": ev["ts"], "para": destinatario, "asunto": asunto, "cuerpo": str(cuerpo),
               "adjuntos": adjuntos, "expediente_id": expediente_id, "simulado": True}
    store.db["outbox"].append(entrada)
    return entrada


def ejecutar(store, propuesta: dict, actor: str):
    """Ejecuta una propuesta aprobada cuyo destino es el correo."""
    plantilla = propuesta["plantilla"]
    if plantilla == "enviar_documento":
        from .. import documentos  # import perezoso: documentos importa este módulo
        return documentos.ejecutar(store, propuesta, actor)
    if plantilla == "correo_info_llegada":
        return enviar_simulado(store, propuesta["slots"]["destinatario"], plantillas.asunto(plantilla), propuesta["texto"],
                               expediente_id=propuesta.get("expediente_id"),
                               datos={"plantilla": plantilla, "aprobado_por": actor})
    raise hub.ErrorNegocio(f"El correo no sabe ejecutar la plantilla «{plantilla}»", 422)
