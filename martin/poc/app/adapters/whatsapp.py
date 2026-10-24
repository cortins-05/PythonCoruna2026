"""WhatsApp: entrada con el formato real del webhook de Meta (Cloud API) y salida simulada.

SIMULADO. La API oficial exige un número de empresa dedicado, verificación en Meta y plantillas
aprobadas; no hay forma de conectarla sin esos tres pasos. El parser sí tiene la forma de producción:
`entry[].changes[].value.messages[]` con `from` y `text.body`, y `contacts[]` con `wa_id` y el nombre
del perfil.
"""
from datetime import datetime


def construir_payload(wa_id: str, nombre: str, texto: str, ahora: datetime) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "DEMO-WABA", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "34000000000", "phone_number_id": "DEMO"},
            "contacts": [{"profile": {"name": nombre}, "wa_id": wa_id}],
            "messages": [{"from": wa_id, "id": f"wamid.DEMO{int(ahora.timestamp())}",
                          "timestamp": str(int(ahora.timestamp())), "type": "text", "text": {"body": texto}}],
        }}]}],
    }


def parsear(payload: dict) -> list[dict]:
    mensajes = []
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            valor = cambio.get("value", {})
            nombres = {c.get("wa_id"): c.get("profile", {}).get("name", "") for c in valor.get("contacts", [])}
            for m in valor.get("messages", []):
                tipo = m.get("type", "")
                mensajes.append({
                    "wa_id": m.get("from", ""),
                    "nombre": nombres.get(m.get("from"), ""),
                    "texto": m.get("text", {}).get("body", "") if tipo == "text" else "",
                    "tipo": tipo,
                })
    return mensajes
