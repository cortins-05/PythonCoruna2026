"""Adaptador de salida hacia SES.Hospedajes.

SIMULADO. El servicio web real exige credenciales técnicas propias (usuario con sufijo _WS) y la
especificación y el XSD solo se descargan dentro del portal oficial. Este generador sigue la lista
orientativa de campos del RD 933/2021 y NO está validado contra el esquema del Ministerio.
"""
import hashlib
from datetime import datetime
from lxml import etree

NOTA = "SIMULADO: estructura orientativa según RD 933/2021, no validada contra el XSD oficial"


def construir_xml(exp: dict) -> str:
    h, pago = exp["huesped"], exp["pago"]
    raiz = etree.Element("comunicacion")
    raiz.append(etree.Comment(f" {NOTA} "))
    contrato = etree.SubElement(raiz, "contrato")
    for etiqueta, valor in [
        ("referencia", exp["referencia"]),
        ("fechaEntrada", exp["checkin_prevista"]),
        ("fechaSalida", exp["checkout_prevista"]),
        ("numPersonas", str(exp.get("personas", 1))),
    ]:
        etree.SubElement(contrato, etiqueta).text = valor
    etree.SubElement(etree.SubElement(contrato, "pago"), "medioPago").text = pago.get("medio", "")
    persona = etree.SubElement(raiz, "persona", rol="VI")
    for campo in ["nombre", "apellido1", "apellido2", "sexo", "fecha_nacimiento", "nacionalidad",
                  "tipo_documento", "numero_documento", "numero_soporte", "direccion", "localidad",
                  "codigo_postal", "pais", "telefono", "email"]:
        etree.SubElement(persona, campo).text = h.get(campo, "")
    return etree.tostring(raiz, pretty_print=True, encoding="unicode", xml_declaration=False)


def enviar_simulado(xml: str, ahora: datetime) -> dict:
    """No sale nada de la máquina. Devuelve un justificante con la huella del XML y la hora."""
    huella = hashlib.sha256(xml.encode("utf-8")).hexdigest()[:12].upper()
    return {"justificante": f"SIM-{huella}", "enviado_el": ahora.isoformat(timespec="minutes"), "simulado": True}
