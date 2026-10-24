"""Facturas y albaranes: modelo, numeración, envío por correo y HTML imprimible (versión mínima de la base).

AVISO FISCAL. Una factura emitida por este sistema sería software de facturación sujeto a Verifactu, así que en la
demo toda factura es un borrador no fiscal: lleva `fiscal: False`, el texto «Documento de demostración sin validez
fiscal» y una numeración de demostración (`DEMO-F-0001`). Los albaranes no son documentos fiscales. Las facturas con
validez las sigue emitiendo OfiHotel; el producto real puede subir la que ya emitió OfiHotel (origen `subido`) o
integrar un servicio de facturación homologado.

Las funciones de este módulo modifican `store.db` pero no guardan: quien las llama (un router, un ejecutor de
propuestas o la semilla) hace `store.guardar()` al terminar. Los errores previstos son `hub.ErrorNegocio`.

Esta versión no genera PDF. Quien lo haga (`fpdf2`) puede apoyarse en `html`, `resumen` y en el modelo tal cual.
"""
import html as _html
import math
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from . import hub, plantillas
from .adapters import correo

AVISO_FISCAL = "Documento de demostración sin validez fiscal"
# Datos de demostración del hotel emisor y tipo de IVA del alojamiento. Son valores de configuración inventados, no
# datos fiscales verificados. back-documentos los traslada a fixtures/hotel.json.
EMISOR = {"razon_social": "Hotel Demo SL", "nif": "B00000000", "direccion": "Rúa Demo 1, 15000 A Coruña",
          "email": "recepcion@hoteldemo.example"}
IVA_ALOJAMIENTO_PCT = 10
TIPOS_IVA = (0, 4, 10, 21)
TIPOS = ("factura", "albaran")
ESTADOS = ("borrador", "emitido", "enviado", "anulado")
PREFIJOS = {"factura": "DEMO-F", "albaran": "DEMO-A"}
ROTULOS = {"factura": "Factura", "albaran": "Albarán"}
EMITIDO = {"factura": "emitida", "albaran": "emitido"}
MAX_LINEAS = 50
LIMITES_RECEPTOR = {"nombre": 120, "nif": 20, "direccion": 200, "email": 254}
_CONTROL = re.compile(r"[\x00-\x1f\x7f  ]")


# ================================================================ dinero y formato

def _dec(valor) -> Decimal:
    return Decimal(str(valor))


def _a_centimos(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_totales(lineas: list[dict]) -> dict:
    """Base, IVA y total de las líneas con precio. Las líneas sin precio (un albarán sin importes) no suman."""
    base = total = Decimal(0)
    for linea in lineas:
        if linea.get("precio_unitario") is None:
            continue
        importe = _dec(linea["cantidad"]) * _dec(linea["precio_unitario"])
        base += importe
        total += importe * (1 + _dec(linea.get("iva_pct") or 0) / 100)
    base, total = _a_centimos(base), _a_centimos(total)
    return {"base": float(base), "iva": float(total - base), "total": float(total), "moneda": "EUR"}


def _separadores_es(texto: str) -> str:
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def euros(valor: float) -> str:
    return f"{_separadores_es(f'{valor:,.2f}')} EUR"


def precio_es(valor: float) -> str:
    """Precio unitario con sus decimales reales (hasta cuatro), para que cantidad por precio cuadre con el importe."""
    entero, _, decimales = f"{valor:,.4f}".partition(".")
    return f"{_separadores_es(entero + '.' + decimales.rstrip('0').ljust(2, '0'))} EUR"


def cantidad_es(valor) -> str:
    return str(int(valor)) if float(valor).is_integer() else _separadores_es(f"{valor:,.3f}").rstrip("0").rstrip(",")


def fecha_es(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso or "") else (iso or "")


def tiene_importes(doc: dict) -> bool:
    return any(linea.get("precio_unitario") is not None for linea in doc["lineas"])


def importe_de_linea(linea: dict) -> float | None:
    """Importe de la línea sin IVA, o None si no lleva precio."""
    if linea.get("precio_unitario") is None:
        return None
    return float(_a_centimos(_dec(linea["cantidad"]) * _dec(linea["precio_unitario"])))


def total_de_linea(linea: dict) -> float | None:
    """Importe de la línea con el IVA incluido, o None si no lleva precio."""
    if linea.get("precio_unitario") is None:
        return None
    return float(_a_centimos(_dec(linea["cantidad"]) * _dec(linea["precio_unitario"]) * (1 + _dec(linea.get("iva_pct") or 0) / 100)))


def estado_texto(doc: dict) -> str:
    """El estado con el género del documento: factura emitida, albarán emitido."""
    femenino = doc["tipo"] == "factura"
    return {"borrador": "borrador", "emitido": "emitida" if femenino else "emitido", "enviado": "enviada" if femenino else "enviado",
            "anulado": "anulada" if femenino else "anulado"}.get(doc["estado"], doc["estado"])


# ================================================================ validación

def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _entero_si_se_puede(valor):
    return int(valor) if float(valor).is_integer() else round(float(valor), 3)


def validar_lineas(tipo: str, lineas) -> list[dict]:
    """Devuelve las líneas normalizadas o lanza un ErrorNegocio 422 con un problema por cada defecto."""
    if not isinstance(lineas, list) or not lineas:
        raise hub.ErrorNegocio("Hace falta al menos una línea", 422)
    if len(lineas) > MAX_LINEAS:
        raise hub.ErrorNegocio(f"Un documento admite como mucho {MAX_LINEAS} líneas", 422)
    problemas, limpias = [], []
    for n, linea in enumerate(lineas, 1):
        if not isinstance(linea, dict):
            problemas.append(f"Línea {n}: tiene que ser un objeto con concepto, cantidad y precio")
            continue
        errores = []
        concepto = linea.get("concepto")
        if not isinstance(concepto, str) or not concepto.strip():
            errores.append("falta el concepto")
        elif len(concepto.strip()) > 120 or _CONTROL.search(concepto):
            errores.append("el concepto debe caber en una línea de 120 caracteres")
        cantidad = linea.get("cantidad", 1)
        if not _numero(cantidad) or not 0 < cantidad <= 10_000:
            errores.append("la cantidad debe ser un número mayor que 0")
        precio, iva = linea.get("precio_unitario"), linea.get("iva_pct")
        if precio is None and tipo == "factura":
            errores.append("falta el precio unitario")
        elif precio is not None and (not _numero(precio) or not 0 <= precio <= 1_000_000):
            errores.append("el precio unitario debe ser un número entre 0 y 1.000.000")
        if precio is not None and iva is None:
            iva = IVA_ALOJAMIENTO_PCT
        if iva is not None and (not _numero(iva) or iva not in TIPOS_IVA):
            errores.append(f"el IVA debe ser uno de {', '.join(str(t) for t in TIPOS_IVA)} %")
        if errores:
            problemas.append(f"Línea {n}: " + "; ".join(errores))
            continue
        limpias.append({"concepto": concepto.strip(), "cantidad": _entero_si_se_puede(cantidad),
                        "precio_unitario": None if precio is None else round(float(precio), 4),
                        "iva_pct": None if precio is None else int(iva)})
    if problemas:
        raise hub.ErrorNegocio("Las líneas no son válidas", 422, problemas)
    return limpias


def validar_receptor(receptor, actual: dict) -> dict:
    """Mezcla los campos recibidos con el receptor actual, comprobando tipo, longitud y formato de cada uno."""
    if not isinstance(receptor, dict):
        raise hub.ErrorNegocio("El receptor tiene que ser un objeto", 422)
    desconocidos = sorted(set(receptor) - set(LIMITES_RECEPTOR))
    problemas = [f"Campo desconocido del receptor: {c}" for c in desconocidos if isinstance(c, str)]
    limpios = {}
    for campo, maximo in LIMITES_RECEPTOR.items():
        if campo not in receptor:
            continue
        valor = receptor[campo]
        valor = "" if valor is None else valor
        if not isinstance(valor, str) or _CONTROL.search(valor) or len(valor.strip()) > maximo:
            problemas.append(f"Receptor, {campo}: texto de una línea de {maximo} caracteres como máximo")
        elif campo == "email" and valor.strip() and not plantillas.email_valido(valor.strip()):
            problemas.append("Receptor, email: el correo no es válido")
        else:
            limpios[campo] = valor.strip()
    if problemas:
        raise hub.ErrorNegocio("El receptor no es válido", 422, problemas)
    return {**actual, **limpios}


# ================================================================ creación y consulta

def _hoy(store) -> str:
    return store.ahora().date().isoformat()


def _anotar(store, doc: dict, actor: str, accion: str) -> None:
    doc["registro"].append({"hora": store.ahora().isoformat(timespec="minutes"), "actor": actor, "accion": accion})


def limpiar_actor(actor) -> str:
    texto = _CONTROL.sub(" ", actor).strip()[:40] if isinstance(actor, str) else ""
    return texto or "Recepción"


def obtener(store, doc_id) -> dict:
    doc = store.db["documentos"].get(doc_id) if isinstance(doc_id, str) else None
    if not doc:
        raise hub.ErrorNegocio("Documento no encontrado", 404)
    return doc


def rotulo(doc: dict) -> str:
    return f"{ROTULOS[doc['tipo']]} {doc['numero']}" if doc.get("numero") else f"{ROTULOS[doc['tipo']]} (borrador)"


def _importe_de_la_reserva(exp: dict) -> Decimal:
    try:
        return max(Decimal(str(exp.get("importe") or "0").replace(",", ".").strip() or "0"), Decimal(0))
    except ArithmeticError:
        return Decimal(0)


def lineas_de_la_estancia(exp: dict, tipo: str) -> list[dict]:
    """Una línea de alojamiento: noches por la tarifa media sin IVA del importe total de la reserva.

    El precio unitario lleva cuatro decimales para que cantidad por precio vuelva a dar el importe de la reserva sin
    perder un céntimo. Un albarán sale sin precios, porque no los necesita.
    """
    noches = max(1, (date.fromisoformat(exp["checkout_prevista"]) - date.fromisoformat(exp["checkin_prevista"])).days)
    tipos = " + ".join(sorted({h["tipo"] for h in exp["habitaciones"]})) or "habitación"
    concepto = f"Alojamiento {tipos}, {noches} {'noche' if noches == 1 else 'noches'}"
    if tipo == "albaran":
        return [{"concepto": f"Alojamiento {tipos} (noches)", "cantidad": noches, "precio_unitario": None, "iva_pct": None}]
    tarifa = _importe_de_la_reserva(exp) / (1 + Decimal(IVA_ALOJAMIENTO_PCT) / 100) / noches
    return [{"concepto": concepto, "cantidad": noches, "precio_unitario": float(tarifa.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
             "iva_pct": IVA_ALOJAMIENTO_PCT}]


def receptor_de_la_estancia(exp: dict) -> dict:
    """La empresa si la estancia la paga una (razón social y CIF recogidos en el check-in) y, si no, el huésped."""
    empresa, h, reserva = exp.get("empresa") or {}, exp["huesped"], exp["reserva"]
    if empresa.get("razon_social") and empresa.get("cif"):
        receptor = {"nombre": empresa["razon_social"], "nif": empresa["cif"], "direccion": empresa.get("direccion", ""),
                    "email": empresa.get("email", "")}
    else:
        nombre = " ".join(p for p in (h.get("nombre"), h.get("apellido1"), h.get("apellido2")) if p) or \
            f"{reserva['nombre']} {reserva['apellidos']}".strip()
        poblacion = f"{h.get('codigo_postal', '')} {h.get('localidad', '')}".strip()
        receptor = {"nombre": nombre, "nif": h.get("numero_documento", ""),
                    "direccion": ", ".join(p for p in (h.get("direccion", ""), poblacion) if p),
                    "email": h.get("email") or reserva.get("email", "")}
    return {campo: str(valor or "")[:LIMITES_RECEPTOR[campo]] for campo, valor in receptor.items()}


def crear_borrador(store, tipo: str, expediente_id: str, lineas: list[dict] | None = None, actor: str = "Sistema") -> dict:
    if tipo not in TIPOS:
        raise hub.ErrorNegocio("El tipo tiene que ser factura o albaran", 422)
    exp = store.db["expedientes"].get(expediente_id) if isinstance(expediente_id, str) else None
    if not exp:
        raise hub.ErrorNegocio("Expediente no encontrado", 404)
    desde_la_estancia = not lineas
    lineas = lineas_de_la_estancia(exp, tipo) if desde_la_estancia else validar_lineas(tipo, lineas)
    doc = {"id": store.siguiente_id("doc"), "tipo": tipo, "estado": "borrador", "numero": None, "origen": "generado",
           "fiscal": False, "aviso_fiscal": AVISO_FISCAL, "expediente_id": exp["id"], "fecha": _hoy(store),
           "emisor": dict(EMISOR), "receptor": receptor_de_la_estancia(exp), "lineas": lineas,
           "totales": calcular_totales(lineas), "archivo": None, "envios": [], "registro": []}
    _anotar(store, doc, actor, "Borrador creado desde el expediente" if desde_la_estancia else "Borrador creado con líneas propias")
    store.db["documentos"][doc["id"]] = doc
    return doc


def listar(store, tipo: str | None = None, estado: str | None = None, expediente: str | None = None) -> list[dict]:
    """Documentos filtrados, los más recientes primero."""
    docs = [d for d in store.db["documentos"].values()
            if (not tipo or d["tipo"] == tipo) and (not estado or d["estado"] == estado)
            and (not expediente or d["expediente_id"] == expediente)]
    return list(reversed(docs))


def resumen(doc: dict) -> dict:
    """Fila de la lista de documentos. `total` es null cuando ninguna línea lleva precio (un albarán sin importes)."""
    return {"id": doc["id"], "tipo": doc["tipo"], "estado": doc["estado"], "numero": doc["numero"],
            "expediente_id": doc["expediente_id"], "receptor_nombre": doc["receptor"].get("nombre", ""),
            "total": doc["totales"]["total"] if tiene_importes(doc) else None, "fecha": doc["fecha"],
            "enviado": bool(doc["envios"]), "fiscal": doc["fiscal"], "origen": doc["origen"]}


# ================================================================ cambios de estado

def editar(store, doc_id: str, lineas=None, receptor=None, actor: str = "Recepción") -> dict:
    doc = obtener(store, doc_id)
    if doc["estado"] != "borrador":
        raise hub.ErrorNegocio("Un documento emitido no se edita", 409)
    if lineas is None and receptor is None:
        raise hub.ErrorNegocio("No hay nada que cambiar: indica líneas o receptor", 422)
    nuevas = validar_lineas(doc["tipo"], lineas) if lineas is not None else None
    nuevo_receptor = validar_receptor(receptor, doc["receptor"]) if receptor is not None else None
    if nuevas is not None:
        doc["lineas"], doc["totales"] = nuevas, calcular_totales(nuevas)
    if nuevo_receptor is not None:
        doc["receptor"] = nuevo_receptor
    _anotar(store, doc, actor, "Borrador editado")
    return doc


def _problemas_para_emitir(doc: dict) -> list[str]:
    problemas = []
    if not doc["receptor"].get("nombre"):
        problemas.append("Falta el nombre del receptor")
    if doc["tipo"] == "factura" and doc["totales"]["total"] <= 0:
        problemas.append("La factura no tiene importe: revisa los precios de las líneas")
    return problemas


def emitir(store, doc_id: str, actor: str = "Recepción") -> dict:
    """Asigna el siguiente número de la serie del tipo, sin saltos, y pasa el borrador a emitido."""
    with store.lock:
        doc = obtener(store, doc_id)
        if doc["estado"] != "borrador":
            raise hub.ErrorNegocio("El documento ya está emitido", 409)
        problemas = _problemas_para_emitir(doc)
        if problemas:
            raise hub.ErrorNegocio("El documento no se puede emitir", 422, problemas)
        serie = store.db["series"]
        serie[doc["tipo"]] = serie.get(doc["tipo"], 0) + 1  # el contador solo avanza cuando todo lo anterior ha ido bien
        doc.update(numero=f"{PREFIJOS[doc['tipo']]}-{serie[doc['tipo']]:04d}", estado="emitido", fecha=_hoy(store))
        _anotar(store, doc, actor, f"Emitido con el número {doc['numero']}")
        hub.registrar_evento(store, "documentos", "documento_emitido", remitente=actor,
                             contenido=f"{rotulo(doc)} {EMITIDO[doc['tipo']]} (demostración sin validez fiscal)",
                             expediente_id=doc["expediente_id"], datos={"documento_id": doc["id"], "numero": doc["numero"]})
        return doc


def asunto_y_cuerpo(store, doc: dict) -> tuple[str, str]:
    """Asunto y cuerpo fijos del correo que acompaña al documento. Solo llevan datos propios del sistema."""
    exp = store.db["expedientes"].get(doc["expediente_id"])
    estancia = f" de su estancia del {fecha_es(exp['checkin_prevista'])} al {fecha_es(exp['checkout_prevista'])}" if exp else ""
    emisor = doc["emisor"]["razon_social"]
    articulo = "la" if doc["tipo"] == "factura" else "el"
    cuerpo = (f"Hola,\n\nAdjuntamos {articulo} {ROTULOS[doc['tipo']].lower()} {doc['numero']}{estancia}.\n\n"
              f"{AVISO_FISCAL}.\n\nUn saludo,\n{emisor}")
    return f"{rotulo(doc)} de {emisor}", cuerpo


def enviar(store, doc_id: str, actor: str = "Recepción", destinatario: str | None = None,
           confirmar_destinatario_nuevo: bool = False, datos: dict | None = None) -> dict:
    """Envía el documento emitido por correo (simulado) con un adjunto PDF.

    Un destinatario que no sea un correo conocido de la estancia (el de la reserva, el del huésped, el de la empresa o el
    del receptor) se rechaza con un 409 salvo que llegue `confirmar_destinatario_nuevo`, y esa confirmación queda en el
    registro del documento. Es la regla que evita mandar datos de un huésped a una dirección cualquiera.
    """
    doc = obtener(store, doc_id)
    if doc["estado"] not in hub.ESTADOS_ENVIABLES:
        raise hub.ErrorNegocio("Solo se envían documentos emitidos", 409)
    if destinatario is not None and not isinstance(destinatario, str):
        raise hub.ErrorNegocio("El destinatario tiene que ser un texto", 422)
    destino = (destinatario or doc["receptor"].get("email") or "").strip()
    if not destino:
        raise hub.ErrorNegocio("El documento no tiene correo de destino: indica uno", 422)
    if not plantillas.email_valido(destino):
        raise hub.ErrorNegocio("El correo de destino no es válido", 422)
    nuevo = destino.lower() not in hub.correos_conocidos(store.db, doc)
    if nuevo and not confirmar_destinatario_nuevo:
        raise hub.ErrorNegocio("El destinatario no es un correo conocido de la estancia: confirma que quieres enviarlo ahí", 409,
                               extra={"requiere_confirmacion": True, "destinatario": destino})
    asunto, cuerpo = asunto_y_cuerpo(store, doc)
    adjunto = {"nombre": f"{rotulo(doc)}.pdf", "documento_id": doc["id"], "tipo_mime": "application/pdf"}
    entrada = correo.enviar_simulado(store, destino, asunto, cuerpo, [adjunto], expediente_id=doc["expediente_id"],
                                     datos={"documento_id": doc["id"], "actor": actor, **(datos or {})})
    if nuevo:
        _anotar(store, doc, actor, f"Destinatario nuevo confirmado: {destino}")
    doc["envios"].append({"hora": store.ahora().isoformat(timespec="minutes"), "destinatario": destino,
                          "evento_id": entrada["evento_id"], "simulado": True, "actor": actor})
    doc["estado"] = "enviado"
    _anotar(store, doc, actor, f"Enviado por correo a {destino} (simulado)")
    return doc


# ================================================================ ejecución de propuestas aprobadas

def _documento_vigente(store, expediente_id: str, tipo: str) -> dict | None:
    """El documento más reciente de ese tipo para la estancia que no esté anulado."""
    return next((d for d in listar(store, tipo=tipo, expediente=expediente_id) if d["estado"] != "anulado"), None)


def ejecutar(store, propuesta: dict, actor: str):
    """Ejecuta una propuesta aprobada de las plantillas emitir_factura, emitir_albaran y enviar_documento.

    Emitir no duplica: si la estancia ya tiene un documento emitido de ese tipo, lo deja como está y lo anota; si tiene un
    borrador, emite ese borrador, y si no tiene nada, crea el borrador desde la estancia y lo emite.
    """
    plantilla, slots = propuesta["plantilla"], propuesta["slots"]
    if plantilla in ("emitir_factura", "emitir_albaran"):
        tipo = "factura" if plantilla == "emitir_factura" else "albaran"
        vigente = _documento_vigente(store, slots["expediente"], tipo)
        if vigente and vigente["estado"] != "borrador":
            hub.registrar_evento(store, "documentos", "documento_ya_emitido", remitente=actor,
                                 contenido=f"{rotulo(vigente)} ya estaba emitido: no se emite otro",
                                 expediente_id=slots["expediente"], datos={"documento_id": vigente["id"], "aprobado_por": actor})
            return vigente
        doc = vigente or crear_borrador(store, tipo, slots["expediente"], actor=actor)
        return emitir(store, doc["id"], actor)
    if plantilla == "enviar_documento":
        return enviar(store, slots["documento"], actor, slots["destinatario"], False, datos={"aprobado_por": actor})
    raise hub.ErrorNegocio(f"Documentos no sabe ejecutar la plantilla «{plantilla}»", 422)


# ================================================================ HTML imprimible

_ESTILOS = """
  :root { color-scheme: light; }
  body { font: 15px/1.5 system-ui, "Segoe UI", sans-serif; color: #1c1b19; background: #fff; margin: 0; padding: 32px; }
  main { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  .aviso { border: 2px solid #8a4b00; background: #fff4e0; color: #5c3200; padding: 10px 14px; border-radius: 6px; font-weight: 600; margin: 0 0 20px; }
  .partes { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin: 20px 0; }
  .partes h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; margin: 0 0 4px; color: #555; }
  .partes p { margin: 0; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  caption { text-align: left; font-weight: 600; padding-bottom: 6px; }
  th, td { border-bottom: 1px solid #ccc; padding: 6px 8px; text-align: left; }
  th.n, td.n { text-align: right; font-variant-numeric: tabular-nums; }
  tfoot td { border: 0; font-weight: 600; }
  footer { margin-top: 28px; font-size: 13px; color: #555; }
  @page { size: A4; margin: 16mm; }
  @media print { body { padding: 0; } .aviso { border-color: #000; background: #fff; color: #000; } }
"""


def html(doc: dict) -> str:
    """El documento como página HTML imprimible, con el aviso fiscal visible arriba y abajo. Todo el texto va escapado."""
    e = _html.escape
    con_importes = tiene_importes(doc)
    filas = []
    for linea in doc["lineas"]:
        importe = importe_de_linea(linea)
        celdas = [f"<td>{e(linea['concepto'])}</td>", f"<td class=\"n\">{e(cantidad_es(linea['cantidad']))}</td>"]
        if con_importes:
            celdas += [f"<td class=\"n\">{e(precio_es(linea['precio_unitario'])) if importe is not None else ''}</td>",
                       f"<td class=\"n\">{e(str(linea['iva_pct'])) + ' %' if importe is not None else ''}</td>",
                       f"<td class=\"n\">{e(euros(importe)) if importe is not None else ''}</td>"]
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    cabecera = "<th scope=\"col\">Concepto</th><th scope=\"col\" class=\"n\">Cantidad</th>" + (
        "<th scope=\"col\" class=\"n\">Precio</th><th scope=\"col\" class=\"n\">IVA</th><th scope=\"col\" class=\"n\">Importe</th>"
        if con_importes else "")
    columnas = 5 if con_importes else 2
    t = doc["totales"]
    pie = "".join(f"<tr><td colspan=\"{columnas - 1}\" class=\"n\">{e(nombre)}</td><td class=\"n\">{e(euros(t[clave]))}</td></tr>"
                  for nombre, clave in (("Base imponible", "base"), ("IVA", "iva"), ("Total", "total"))) if con_importes else ""

    def parte(titulo: str, datos: dict, nombre: str) -> str:
        lineas = [datos.get(nombre, ""), f"NIF {datos['nif']}" if datos.get("nif") else "", datos.get("direccion", ""), datos.get("email", "")]
        return f"<div><h2>{e(titulo)}</h2>" + "".join(f"<p>{e(x)}</p>" for x in lineas if x) + "</div>"

    aviso = f"<p class=\"aviso\" role=\"note\">{e(doc['aviso_fiscal'])}</p>" if doc.get("aviso_fiscal") else ""
    return (f"<!doctype html>\n<html lang=\"es\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{e(rotulo(doc))}</title><style>{_ESTILOS}</style></head><body><main>"
            f"{aviso}<h1>{e(rotulo(doc))}</h1><p>Fecha: {e(fecha_es(doc['fecha']))} · Estancia {e(doc['expediente_id'])}</p>"
            f"<section class=\"partes\">{parte('Emisor', doc['emisor'], 'razon_social')}{parte('Receptor', doc['receptor'], 'nombre')}</section>"
            f"<table><caption>Detalle</caption><thead><tr>{cabecera}</tr></thead><tbody>{''.join(filas)}</tbody>"
            f"<tfoot>{pie}</tfoot></table>"
            f"<footer>{e(doc.get('aviso_fiscal') or '')}</footer></main></body></html>")
