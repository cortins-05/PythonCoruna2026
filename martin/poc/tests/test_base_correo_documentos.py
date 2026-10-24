"""Correo con la forma de Gmail, documentos (facturas y albaranes) y el enrutado de mensajes hacia ellos."""
import base64
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import documentos, hub, main  # noqa: E402
from app.adapters import correo  # noqa: E402
from app.store import Store  # noqa: E402

ANA, MARCOS, CLAIRE = "1-BK-4471920", "0-WEB-90112", "2-EX-7730021"
AHORA = datetime(2026, 10, 24, 9, 0)


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    """Solo las reservas de RoomCloud, sin check-ins, mensajes ni documentos."""
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = TestClient(main.app)
    c.post("/api/demo/semilla", params={"nivel": "basica"})
    return c


@pytest.fixture()
def completa(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = TestClient(main.app)
    c.post("/api/demo/semilla", params={"nivel": "completa"})
    return c


def tras_el_checkin_de(c, exp_id: str, email: str = "huesped@example.com") -> None:
    """Deja al huésped con el check-in hecho y el correo que se indique."""
    lectura = c.post(f"/api/expedientes/{exp_id}/ocr", json={}).json()["campos"]
    assert c.put(f"/api/expedientes/{exp_id}/huesped", json={**lectura, "telefono": "+34600000000", "email": email}).status_code == 200


# ---------------------------------------------------------------- correo con la forma de Gmail

def test_el_mensaje_tiene_la_forma_del_recurso_de_la_api_de_gmail():
    m = correo.construir_mensaje_gmail("claire.dubois@example.com", "Claire Dubois", "Factura de mi estancia", "Hola, ¿me envían la factura?", AHORA)
    assert set(m) == {"id", "threadId", "labelIds", "snippet", "internalDate", "sizeEstimate", "payload"}
    assert m["id"] == m["threadId"] and len(m["id"]) == 16 and int(m["id"], 16) >= 0
    assert m["labelIds"] == ["INBOX", "UNREAD"] and m["snippet"] == "Hola, ¿me envían la factura?"
    assert isinstance(m["internalDate"], str) and m["internalDate"].isdigit() and len(m["internalDate"]) == 13  # milisegundos como texto
    payload = m["payload"]
    assert payload["mimeType"] == "text/plain"
    cabeceras = {h["name"]: h["value"] for h in payload["headers"]}
    assert set(cabeceras) == {"From", "To", "Subject"}
    assert cabeceras["From"] == '"Claire Dubois" <claire.dubois@example.com>' and cabeceras["Subject"] == "Factura de mi estancia"
    assert cabeceras["To"] == correo.DIRECCION_HOTEL
    datos = payload["body"]["data"]
    assert "=" not in datos and "+" not in datos and "/" not in datos  # base64url sin relleno, como devuelve Gmail
    assert base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4)).decode("utf-8") == "Hola, ¿me envían la factura?"
    assert payload["body"]["size"] == len("Hola, ¿me envían la factura?".encode("utf-8"))
    assert m == correo.construir_mensaje_gmail("claire.dubois@example.com", "Claire Dubois", "Factura de mi estancia", "Hola, ¿me envían la factura?", AHORA)


@pytest.mark.parametrize("cuerpo", ["", "a", "Hola", "Acentos y eñes: ¿qué tal? 日本語 😀", "línea 1\nlínea 2\r\nlínea 3", "x" * 9000])
@pytest.mark.parametrize("ahora", [AHORA, datetime(2026, 10, 25, 2, 30), datetime(2026, 3, 29, 2, 30), datetime(2027, 1, 1, 0, 0)])
def test_parsear_invierte_a_construir_en_cualquier_hora_del_reloj(cuerpo, ahora):
    # 25/10/2026 a las 02:30 es una hora ambigua en España por el cambio de hora; el reloj de la demo se trata como UTC y vuelve igual.
    m = correo.construir_mensaje_gmail("ana@example.com", "Ana", "Asunto", cuerpo, ahora)
    p = correo.parsear(m)
    assert (p["de"], p["nombre"], p["asunto"], p["texto"], p["ts"]) == ("ana@example.com", "Ana", "Asunto", cuerpo, ahora)
    assert p["id"] == m["id"] and p["thread_id"] == m["threadId"] and p["para"] == correo.DIRECCION_HOTEL


def test_parsear_acepta_relleno_multipart_y_cabeceras_en_minusculas():
    texto = base64.urlsafe_b64encode("Cuerpo en texto".encode()).decode()  # con relleno
    mensaje = {"id": "abc", "threadId": "abc", "internalDate": "1790000000000", "labelIds": ["INBOX"],
               "payload": {"mimeType": "multipart/alternative",
                           "headers": [{"name": "from", "value": "Claire Dubois <claire@example.com>"}, {"name": "subject", "value": "=?utf-8?q?Se=C3=B1al?="}],
                           "parts": [{"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>html</p>").decode()}},
                                     {"mimeType": "text/plain", "body": {"data": texto}}]}}
    p = correo.parsear(mensaje)
    assert p["texto"] == "Cuerpo en texto" and p["de"] == "claire@example.com" and p["nombre"] == "Claire Dubois" and p["asunto"] == "Señal"


@pytest.mark.parametrize("malo", [None, [], "texto", {}, {"payload": "x"}, {"payload": {}, "internalDate": "no"},
                                  {"payload": {"headers": [], "body": {"data": "@@@@"}, "mimeType": "text/plain"}, "internalDate": "1"}])
def test_parsear_rechaza_lo_que_no_es_un_mensaje_de_gmail(malo):
    with pytest.raises(ValueError):
        correo.parsear(malo)


def test_una_cabecera_inyectada_no_llega_a_ningun_sitio():
    for de in ("a@b.com\nBcc: x@y.com", "a@b.com\r\nBcc: x@y.com", "a@b.com Bcc: x@y.com", "", "a" * 300 + "@b.com"):
        with pytest.raises(ValueError):
            correo.construir_mensaje_gmail(de, "X", "S", "c", AHORA)
    m = correo.construir_mensaje_gmail("a@b.com", 'Ana"\r\nBcc: x@y.com <z@y.com>', "Hola\r\nBcc: x@y.com\x00", "c", AHORA)
    for cabecera in m["payload"]["headers"]:
        assert "\n" not in cabecera["value"] and "\r" not in cabecera["value"] and "\x00" not in cabecera["value"]
    assert correo.parsear(m)["de"] == "a@b.com"  # la dirección del remitente sigue siendo solo la suya
    with pytest.raises(ValueError):
        correo.construir_mensaje_gmail("a@b.com", "X", "S", "x" * (correo.CUERPO_MAX + 1), AHORA)


def test_enviar_simulado_deja_un_evento_y_una_entrada_en_la_bandeja_de_salida(cliente):
    s = main.store
    entrada = correo.enviar_simulado(s, "ana.pereira@example.com", "Asunto\nBcc: x@y.com", "Cuerpo",
                                     [{"nombre": "Factura DEMO-F-0001.pdf", "documento_id": "doc-0003", "bytes": b"%PDF".decode()}])
    assert s.db["outbox"] == [entrada] and entrada["simulado"] is True
    assert entrada["asunto"] == "Asunto Bcc: x@y.com" and entrada["para"] == "ana.pereira@example.com" and entrada["expediente_id"] == ANA
    assert entrada["adjuntos"] == [{"nombre": "Factura DEMO-F-0001.pdf", "documento_id": "doc-0003", "tipo_mime": "application/pdf"}]
    evento = next(e for e in s.db["eventos"] if e["id"] == entrada["evento_id"])
    assert evento["tipo"] == "correo_saliente_simulado" and evento["fuente"] == "correo" and evento["remitente"] == "ana.pereira@example.com"
    assert evento["datos"]["correo"] == "ana.pereira@example.com" and evento["contenido"] == "Cuerpo" and evento["expediente_id"] == ANA
    for malo in ("", "a@b.com\nBcc: x@y.com", "no-es-un-correo", None):
        with pytest.raises(hub.ErrorNegocio):
            correo.enviar_simulado(s, malo, "S", "C")
    assert len(s.db["outbox"]) == 1


# ---------------------------------------------------------------- importes

def test_la_factura_por_defecto_suma_exactamente_el_importe_de_la_reserva(cliente):
    s = main.store
    doc = documentos.crear_borrador(s, "factura", ANA)
    assert doc["lineas"] == [{"concepto": "Alojamiento DBL-STD, 2 noches", "cantidad": 2, "precio_unitario": 96.3636, "iva_pct": 10}]
    assert doc["totales"] == {"base": 192.73, "iva": 19.27, "total": 212.0, "moneda": "EUR"}
    assert doc["estado"] == "borrador" and doc["numero"] is None and doc["fiscal"] is False and doc["origen"] == "generado"
    assert doc["receptor"]["nombre"] == "Ana Pereira Lage" and doc["receptor"]["email"] == "ana.pereira@example.com"  # sin empresa, el huésped
    assert doc["emisor"]["razon_social"] == "Hotel Demo SL" and doc["registro"][0]["accion"] == "Borrador creado desde el expediente"


def test_el_total_coincide_con_el_importe_para_cualquier_estancia():
    for noches in range(1, 15):
        for centimos in range(5_000, 60_000, 37):
            importe = Decimal(centimos) / 100
            exp = {"checkin_prevista": "2026-10-01", "checkout_prevista": f"2026-10-{1 + noches:02d}" if noches < 30 else "2026-11-01",
                   "habitaciones": [{"tipo": "DBL-STD"}], "importe": str(importe)}
            lineas = documentos.lineas_de_la_estancia(exp, "factura")
            assert documentos.calcular_totales(lineas)["total"] == float(importe), (noches, importe)


def test_totales_con_varias_lineas_y_lineas_sin_precio():
    lineas = [{"concepto": "A", "cantidad": 2, "precio_unitario": 50.0, "iva_pct": 10}, {"concepto": "B", "cantidad": 1, "precio_unitario": 10.0, "iva_pct": 21},
              {"concepto": "C", "cantidad": 3, "precio_unitario": None, "iva_pct": None}]
    assert documentos.calcular_totales(lineas) == {"base": 110.0, "iva": 12.1, "total": 122.1, "moneda": "EUR"}
    assert documentos.calcular_totales([lineas[2]]) == {"base": 0.0, "iva": 0.0, "total": 0.0, "moneda": "EUR"}
    assert documentos.euros(1234.5) == "1.234,50 EUR" and documentos.euros(212) == "212,00 EUR" and documentos.precio_es(96.3636) == "96,3636 EUR"
    assert documentos.precio_es(100.0) == "100,00 EUR" and documentos.precio_es(12.5) == "12,50 EUR"


@pytest.mark.parametrize("lineas", [
    [], "texto", [{"concepto": "", "cantidad": 1, "precio_unitario": 1, "iva_pct": 10}], [{"cantidad": 1, "precio_unitario": 1, "iva_pct": 10}],
    [{"concepto": "x\ny", "cantidad": 1, "precio_unitario": 1, "iva_pct": 10}], [{"concepto": "x" * 121, "cantidad": 1, "precio_unitario": 1, "iva_pct": 10}],
    [{"concepto": "x", "cantidad": 0, "precio_unitario": 1, "iva_pct": 10}], [{"concepto": "x", "cantidad": -1, "precio_unitario": 1, "iva_pct": 10}],
    [{"concepto": "x", "cantidad": "2", "precio_unitario": 1, "iva_pct": 10}], [{"concepto": "x", "cantidad": 10_001, "precio_unitario": 1, "iva_pct": 10}],
    [{"concepto": "x", "cantidad": True, "precio_unitario": 1, "iva_pct": 10}], [{"concepto": "x", "cantidad": float("nan"), "precio_unitario": 1, "iva_pct": 10}],
    [{"concepto": "x", "cantidad": 1, "precio_unitario": None, "iva_pct": 10}], [{"concepto": "x", "cantidad": 1, "precio_unitario": -1, "iva_pct": 10}],
    [{"concepto": "x", "cantidad": 1, "precio_unitario": 2_000_000, "iva_pct": 10}], [{"concepto": "x", "cantidad": 1, "precio_unitario": "9", "iva_pct": 10}],
    [{"concepto": "x", "cantidad": 1, "precio_unitario": 1, "iva_pct": 13}], [{"concepto": "x", "cantidad": 1, "precio_unitario": 1, "iva_pct": "10"}],
    ["no es un objeto"], [{"concepto": "x", "cantidad": 1, "precio_unitario": 1, "iva_pct": 10}] * 51,
])
def test_las_lineas_de_una_factura_se_validan(lineas):
    with pytest.raises(hub.ErrorNegocio) as error:
        documentos.validar_lineas("factura", lineas)
    assert error.value.codigo == 422 and error.value.problemas


def test_un_albaran_admite_lineas_sin_precio_y_normaliza_las_que_si_lo_llevan():
    limpias = documentos.validar_lineas("albaran", [{"concepto": " Desayuno ", "cantidad": 2.0}, {"concepto": "Parking", "cantidad": 1.5, "precio_unitario": 12}])
    assert limpias == [{"concepto": "Desayuno", "cantidad": 2, "precio_unitario": None, "iva_pct": None},
                       {"concepto": "Parking", "cantidad": 1.5, "precio_unitario": 12.0, "iva_pct": 10}]


# ---------------------------------------------------------------- ciclo de vida y numeración

def test_la_numeracion_no_tiene_saltos_y_cada_tipo_lleva_su_serie(cliente):
    s = main.store
    facturas = [documentos.crear_borrador(s, "factura", exp) for exp in (ANA, MARCOS, CLAIRE)]
    albaranes = [documentos.crear_borrador(s, "albaran", exp) for exp in (ANA, MARCOS)]
    assert all(d["numero"] is None for d in facturas + albaranes)
    # una emisión que falla no gasta número
    sin_receptor = documentos.crear_borrador(s, "factura", ANA)
    sin_receptor["receptor"]["nombre"] = ""
    with pytest.raises(hub.ErrorNegocio) as error:
        documentos.emitir(s, sin_receptor["id"])
    assert error.value.codigo == 422 and s.db["series"]["factura"] == 0
    sin_importe = documentos.crear_borrador(s, "factura", ANA, [{"concepto": "Cortesía", "cantidad": 1, "precio_unitario": 0, "iva_pct": 10}])
    with pytest.raises(hub.ErrorNegocio):
        documentos.emitir(s, sin_importe["id"])
    assert s.db["series"]["factura"] == 0
    numeros = [documentos.emitir(s, d["id"], "Flor")["numero"] for d in facturas[1:] + albaranes[:1] + facturas[:1] + albaranes[1:]]
    assert numeros == ["DEMO-F-0001", "DEMO-F-0002", "DEMO-A-0001", "DEMO-F-0003", "DEMO-A-0002"]
    assert s.db["series"] == {"factura": 3, "albaran": 2}
    emitida = s.db["documentos"][facturas[1]["id"]]
    assert emitida["estado"] == "emitido" and emitida["registro"][-1]["accion"] == "Emitido con el número DEMO-F-0001" and emitida["registro"][-1]["actor"] == "Flor"
    evento = next(e for e in s.db["eventos"] if e["tipo"] == "documento_emitido" and e["datos"]["numero"] == "DEMO-F-0001")
    assert evento["expediente_id"] == MARCOS and "sin validez fiscal" in evento["contenido"]


def test_un_documento_emitido_no_se_edita_ni_se_emite_otra_vez(cliente):
    s = main.store
    doc = documentos.crear_borrador(s, "factura", ANA)
    documentos.emitir(s, doc["id"])
    for accion in (lambda: documentos.emitir(s, doc["id"]), lambda: documentos.editar(s, doc["id"], lineas=doc["lineas"])):
        with pytest.raises(hub.ErrorNegocio) as error:
            accion()
        assert error.value.codigo == 409
    assert s.db["series"]["factura"] == 1


def test_editar_un_borrador_recalcula_los_totales_y_valida_el_receptor(cliente):
    s = main.store
    doc = documentos.crear_borrador(s, "factura", ANA)
    editado = documentos.editar(s, doc["id"], lineas=[{"concepto": "Alojamiento", "cantidad": 3, "precio_unitario": 100, "iva_pct": 10}],
                                receptor={"nombre": "Nueva SL", "nif": "B11111111", "email": "contabilidad@nueva.example"})
    assert editado["totales"] == {"base": 300.0, "iva": 30.0, "total": 330.0, "moneda": "EUR"}
    assert editado["receptor"]["nombre"] == "Nueva SL" and editado["receptor"]["direccion"] == doc["receptor"]["direccion"] and editado["registro"][-1]["accion"] == "Borrador editado"
    for malo in ({"campo_raro": "x"}, {"email": "no-es-un-correo"}, {"email": "a@b.com\nBcc: x@y.com"}, {"nombre": "x" * 121}, {"nombre": 5},
                 {"direccion": "dos\nlíneas"}, "texto"):
        with pytest.raises(hub.ErrorNegocio) as error:
            documentos.editar(s, doc["id"], receptor=malo)
        assert error.value.codigo == 422
    with pytest.raises(hub.ErrorNegocio):
        documentos.editar(s, doc["id"])  # sin nada que cambiar
    assert s.db["documentos"][doc["id"]]["receptor"]["nombre"] == "Nueva SL"  # los intentos fallidos no tocaron nada


def test_el_receptor_es_la_empresa_si_la_hay_y_si_no_el_huesped(completa):
    s = main.store
    factura = next(d for d in s.db["documentos"].values() if d["tipo"] == "factura")
    assert factura["receptor"] == {"nombre": "Atlántico Consultores SL", "nif": "B15000000", "direccion": "Rúa Real 1, A Coruña", "email": "facturas@atlantico.example"}
    marcos = documentos.crear_borrador(s, "factura", MARCOS)
    assert marcos["receptor"]["nombre"] == "Marcos Vilas Souto" and marcos["receptor"]["nif"] == "87654321X" and marcos["receptor"]["email"] == "marcos.vilas@example.com"
    assert marcos["receptor"]["direccion"] == "Rúa Nova 8, 1º, 15001 A Coruña"
    claire = documentos.crear_borrador(s, "factura", CLAIRE)  # sin check-in: se usa la reserva
    assert claire["receptor"]["nombre"] == "Claire Dubois" and claire["receptor"]["email"] == "claire.dubois@example.com"


# ---------------------------------------------------------------- envío por correo y regla del destinatario conocido

def test_enviar_a_un_correo_desconocido_pide_confirmacion_y_la_deja_en_el_registro(completa):
    s = main.store
    r = completa.post("/api/documentos/doc-0011/enviar", json={"actor": "Flor", "destinatario": "contable@otra.example"})
    assert r.status_code == 409
    assert r.json()["detail"]["requiere_confirmacion"] is True and r.json()["detail"]["destinatario"] == "contable@otra.example"
    assert s.db["documentos"]["doc-0011"]["estado"] == "emitido" and not s.db["outbox"]
    r = completa.post("/api/documentos/doc-0011/enviar", json={"actor": "Flor", "destinatario": "contable@otra.example", "confirmar_destinatario_nuevo": True})
    assert r.status_code == 200
    doc = r.json()
    assert doc["estado"] == "enviado" and len(doc["envios"]) == 1
    envio = doc["envios"][0]
    assert envio["destinatario"] == "contable@otra.example" and envio["simulado"] is True and envio["actor"] == "Flor" and envio["hora"] == "2026-10-24T09:00"
    assert [a["accion"] for a in doc["registro"]][-2:] == ["Destinatario nuevo confirmado: contable@otra.example", "Enviado por correo a contable@otra.example (simulado)"]
    salida = s.db["outbox"][0]
    assert salida["evento_id"] == envio["evento_id"] and salida["para"] == "contable@otra.example"
    assert salida["adjuntos"] == [{"nombre": "Factura DEMO-F-0001.pdf", "documento_id": "doc-0011", "tipo_mime": "application/pdf"}]
    assert "sin validez fiscal" in salida["cuerpo"] and "DEMO-F-0001" in salida["cuerpo"] and "24/10/2026 al 26/10/2026" in salida["cuerpo"]
    # los salientes aparecen en la conversación de esa dirección con su adjunto
    conv = completa.get("/api/mensajes/conversaciones/mail:contable@otra.example").json()
    assert conv["mensajes"][0]["direccion"] == "saliente" and conv["mensajes"][0]["adjuntos"] == [{"nombre": "Factura DEMO-F-0001.pdf", "documento_id": "doc-0011"}]
    assert conv["conversacion"]["sin_responder"] is False


@pytest.mark.parametrize("destinatario", [None, "facturas@atlantico.example", "FACTURAS@Atlantico.Example", "ana.pereira@example.com", "recepcion@hoteldemo.example"])
def test_enviar_a_un_correo_conocido_no_pide_confirmacion(completa, destinatario):
    # Conocidos: el del receptor (por defecto), el de la empresa y el del huésped. El del hotel (emisor) no es de la estancia.
    r = completa.post("/api/documentos/doc-0011/enviar", json={"actor": "Flor", "destinatario": destinatario})
    if destinatario == "recepcion@hoteldemo.example":
        assert r.status_code == 409
    else:
        assert r.status_code == 200 and r.json()["estado"] == "enviado"
        assert completa.post("/api/documentos/doc-0011/enviar", json={"actor": "Flor"}).status_code == 200  # reenviar está permitido
        assert len(main.store.db["documentos"]["doc-0011"]["envios"]) == 2


def test_enviar_valida_el_estado_y_el_formato_del_destinatario(completa):
    assert completa.post("/api/documentos/doc-0013/enviar", json={"destinatario": "facturas@atlantico.example"}).status_code == 409  # borrador
    assert completa.post("/api/documentos/doc-9999/enviar", json={}).status_code == 404
    for malo in ("no-es-un-correo", "a@b.com\nBcc: x@y.com", "a@b.com,c@d.com"):
        r = completa.post("/api/documentos/doc-0011/enviar", json={"destinatario": malo, "confirmar_destinatario_nuevo": True})
        assert r.status_code == 422, malo
    assert not main.store.db["outbox"]
    documentos_sin_correo = main.store.db["documentos"]["doc-0011"]
    documentos_sin_correo["receptor"]["email"] = ""
    r = completa.post("/api/documentos/doc-0011/enviar", json={})
    assert r.status_code == 422 and "correo de destino" in r.json()["detail"]["problemas"][0]


def test_el_correo_de_la_reserva_sigue_siendo_conocido_aunque_el_huesped_deje_otro(cliente):
    tras_el_checkin_de(cliente, ANA, email="otro.correo@example.com")
    doc = documentos.crear_borrador(main.store, "factura", ANA)
    documentos.emitir(main.store, doc["id"])
    conocidos = hub.correos_conocidos(main.store.db, doc)
    assert {"ana.pereira@example.com", "otro.correo@example.com"} <= conocidos  # el de la reserva y el del huésped


def test_la_empresa_guarda_su_correo_y_es_un_destinatario_valido(cliente):
    tras_el_checkin_de(cliente, ANA)
    pago = {"medio": "tarjeta", "empresa": {"razon_social": "Atlántico Consultores SL", "cif": "B15000000", "direccion": "Rúa Real 1", "email": " Facturas@Atlantico.example "}}
    assert cliente.put(f"/api/expedientes/{ANA}/pago", json=pago).status_code == 200
    assert main.store.db["expedientes"][ANA]["empresa"]["email"] == "Facturas@Atlantico.example"
    sin_correo = {**pago, "empresa": {k: v for k, v in pago["empresa"].items() if k != "email"}}
    assert cliente.put(f"/api/expedientes/{ANA}/pago", json=sin_correo).status_code == 200 and main.store.db["expedientes"][ANA]["empresa"]["email"] == ""
    malo = {**pago, "empresa": {**pago["empresa"], "email": "no-es-un-correo"}}
    r = cliente.put(f"/api/expedientes/{ANA}/pago", json=malo)
    assert r.status_code == 422 and "correo de la empresa" in r.json()["detail"]["problemas"][0]
    assert cliente.put(f"/api/expedientes/{ANA}/pago", json=pago).status_code == 200
    doc = documentos.crear_borrador(main.store, "factura", ANA)
    assert doc["receptor"]["email"] == "Facturas@Atlantico.example"
    assert hub.contexto_valido(main.store, "enviar_documento", {"documento": doc["id"], "destinatario": "facturas@atlantico.example"}) is False  # aún es borrador
    documentos.emitir(main.store, doc["id"])
    assert hub.contexto_valido(main.store, "enviar_documento", {"documento": doc["id"], "destinatario": "facturas@atlantico.example"})


# ---------------------------------------------------------------- HTML

def test_el_html_escapa_todo_y_lleva_el_aviso(cliente):
    s = main.store
    doc = documentos.crear_borrador(s, "factura", ANA, [{"concepto": "<script>alert(1)</script> & más", "cantidad": 1, "precio_unitario": 100, "iva_pct": 10}])
    documentos.editar(s, doc["id"], receptor={"nombre": '<img src=x onerror="alert(1)">', "direccion": "Calle <b>1</b>"})
    pagina = documentos.html(doc)
    assert "<script>" not in pagina and "<img" not in pagina and "<b>" not in pagina
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; más" in pagina and "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in pagina
    assert pagina.count("Documento de demostración sin validez fiscal") == 2 and "Factura (borrador)" in pagina and "110,00 EUR" in pagina
    emitida = documentos.html(documentos.emitir(s, doc["id"]))
    assert "<title>Factura DEMO-F-0001</title>" in emitida and "@media print" in emitida and 'lang="es"' in emitida


def test_el_html_de_un_albaran_sin_precios_no_lleva_columnas_de_importes(completa):
    pagina = completa.get("/api/documentos/doc-0013/html").text
    assert "Albarán (borrador)" in pagina and "Desayuno buffet" in pagina and "Precio" not in pagina and "Base imponible" not in pagina
    assert "Documento de demostración sin validez fiscal" in pagina


# ---------------------------------------------------------------- API de documentos

def test_crear_editar_emitir_y_enviar_por_la_api(cliente):
    r = cliente.post("/api/documentos/borrador", json={"tipo": "factura", "expediente_id": CLAIRE})
    assert r.status_code == 200
    doc = r.json()
    assert doc["id"].startswith("doc-") and doc["estado"] == "borrador" and doc["totales"]["total"] == 318.0 and doc["receptor"]["nombre"] == "Claire Dubois"
    r = cliente.put(f"/api/documentos/{doc['id']}", json={"lineas": [{"concepto": "Alojamiento y desayunos", "cantidad": 3, "precio_unitario": 100, "iva_pct": 10}]})
    assert r.status_code == 200 and r.json()["totales"]["total"] == 330.0
    assert cliente.put(f"/api/documentos/{doc['id']}", json={}).status_code == 422
    assert cliente.put(f"/api/documentos/{doc['id']}", json={"lineas": [{"concepto": "x", "cantidad": 1, "precio_unitario": "9"}]}).status_code == 422
    assert cliente.post(f"/api/documentos/{doc['id']}/enviar", json={}).status_code == 409  # un borrador no se envía
    r = cliente.post(f"/api/documentos/{doc['id']}/emitir", json={"actor": "Flor"})
    assert r.status_code == 200 and r.json()["numero"] == "DEMO-F-0001" and r.json()["estado"] == "emitido"
    assert cliente.post(f"/api/documentos/{doc['id']}/emitir", json={"actor": "Flor"}).status_code == 409
    assert cliente.put(f"/api/documentos/{doc['id']}", json={"lineas": doc["lineas"]}).status_code == 409
    r = cliente.post(f"/api/documentos/{doc['id']}/enviar", json={"actor": "Flor"})
    assert r.status_code == 200 and r.json()["envios"][0]["destinatario"] == "claire.dubois@example.com"
    # los errores de entrada
    assert cliente.post("/api/documentos/borrador", json={"tipo": "recibo", "expediente_id": CLAIRE}).status_code == 422
    assert cliente.post("/api/documentos/borrador", json={"tipo": "factura", "expediente_id": "9-NO-EXISTE"}).status_code == 404
    assert cliente.post("/api/documentos/borrador", json={"tipo": "albaran", "expediente_id": CLAIRE, "lineas": [{"concepto": "x", "cantidad": 0}]}).status_code == 422
    albaran = cliente.post("/api/documentos/borrador", json={"tipo": "albaran", "expediente_id": CLAIRE}).json()
    assert albaran["lineas"][0]["precio_unitario"] is None and albaran["totales"]["total"] == 0.0
    assert cliente.get("/api/documentos", params={"tipo": "albaran"}).json()["documentos"][0]["total"] is None
    # el actor se limpia
    r = cliente.post(f"/api/documentos/{albaran['id']}/emitir", json={"actor": "Flor\r\nBcc: x"})
    assert r.json()["registro"][-1]["actor"] == "Flor  Bcc: x"


# ---------------------------------------------------------------- ejecución de propuestas aprobadas

def test_aprobar_emitir_factura_la_crea_y_la_emite_una_sola_vez(completa):
    s = main.store
    propuesta = next(p for p in s.db["propuestas"] if p["plantilla"] == "emitir_factura")
    assert propuesta["slots"] == {"expediente": CLAIRE} and propuesta["destinatario"] == "" and propuesta["expediente_id"] == CLAIRE
    r = completa.post(f"/api/propuestas/{propuesta['id']}/aprobar", json={"actor": "Flor"})
    assert r.status_code == 200 and r.json()["estado"] == "aprobada"
    claire = documentos.listar(s, expediente=CLAIRE)
    assert len(claire) == 1 and claire[0]["numero"] == "DEMO-F-0002" and claire[0]["estado"] == "emitido" and claire[0]["receptor"]["nombre"] == "Claire Dubois"
    assert any(e["tipo"] == "documento_emitido" and e["expediente_id"] == CLAIRE for e in s.db["eventos"])
    # una segunda petición de factura para la misma estancia no duplica el documento
    otra = hub.crear_propuesta(s, "emitir_factura", {"expediente": CLAIRE}, origen="chat")
    assert completa.post(f"/api/propuestas/{otra['id']}/aprobar", json={"actor": "Flor"}).status_code == 200
    assert len(documentos.listar(s, expediente=CLAIRE)) == 1 and s.db["series"]["factura"] == 2
    assert any(e["tipo"] == "documento_ya_emitido" for e in s.db["eventos"])
    # un albarán en borrador se emite en lugar de crear otro
    albaran = hub.crear_propuesta(s, "emitir_albaran", {"expediente": ANA}, origen="chat")
    assert completa.post(f"/api/propuestas/{albaran['id']}/aprobar", json={"actor": "Flor"}).status_code == 200
    assert s.db["documentos"]["doc-0013"]["numero"] == "DEMO-A-0001" and len(documentos.listar(s, tipo="albaran")) == 1


def test_aprobar_enviar_documento_lo_manda_y_lo_deja_en_el_registro(completa):
    s = main.store
    propuesta = hub.crear_propuesta(s, "enviar_documento", {"documento": "doc-0011", "destinatario": "facturas@atlantico.example"}, origen="chat")
    assert propuesta["texto"] == "Enviar por correo el documento doc-0011 a facturas@atlantico.example"
    r = completa.post(f"/api/propuestas/{propuesta['id']}/aprobar", json={"actor": "Flor"})
    assert r.status_code == 200
    assert s.db["documentos"]["doc-0011"]["estado"] == "enviado" and len(s.db["outbox"]) == 1
    evento = next(e for e in s.db["eventos"] if e["id"] == s.db["outbox"][0]["evento_id"])
    assert evento["datos"]["aprobado_por"] == "Flor" and evento["datos"]["documento_id"] == "doc-0011"
    assert completa.post(f"/api/propuestas/{propuesta['id']}/aprobar", json={}).status_code == 409  # ya decidida


def test_aprobar_info_llegada_por_correo_envia_la_respuesta_a_quien_escribio(cliente):
    r = cliente.post("/api/correo/simular", json={"de": "claire.dubois@example.com", "nombre": "Claire Dubois", "asunto": "Check-in", "cuerpo": "¿A qué hora es el check-in?"})
    propuesta = r.json()[0]["propuesta"]
    assert cliente.post(f"/api/propuestas/{propuesta}/aprobar", json={"actor": "Flor"}).status_code == 200
    salida = main.store.db["outbox"][0]
    assert salida["para"] == "claire.dubois@example.com" and salida["asunto"] == "Horario de check-in y check-out" and salida["cuerpo"].startswith("Hola Claire,")
    conv = cliente.get("/api/mensajes/conversaciones/mail:claire.dubois@example.com").json()
    assert [m["direccion"] for m in conv["mensajes"]] == ["entrante", "saliente"] and conv["conversacion"]["sin_responder"] is False and conv["propuestas"] == []


def test_una_ejecucion_que_falla_deja_la_propuesta_pendiente(completa):
    s = main.store
    propuesta = hub.crear_propuesta(s, "enviar_documento", {"documento": "doc-0011", "destinatario": "facturas@atlantico.example"}, origen="chat")
    s.db["documentos"]["doc-0011"]["receptor"]["email"] = ""
    s.db["expedientes"][ANA]["empresa"]["email"] = ""
    s.db["expedientes"][ANA]["huesped"]["email"] = ""
    s.db["expedientes"][ANA]["reserva"]["email"] = ""
    r = completa.post(f"/api/propuestas/{propuesta['id']}/aprobar", json={"actor": "Flor"})
    assert r.status_code == 422  # ya no es un correo conocido
    assert next(p for p in s.db["propuestas"] if p["id"] == propuesta["id"])["estado"] == "pendiente"


# ---------------------------------------------------------------- enrutado de mensajes

def evento_con(intencion: str, texto: str = "x") -> dict:
    return {"id": "ev-9999", "datos": {"interpretacion": {"intencion": intencion, "confianza": 0.6, "modo": "reglas"}}, "contenido": texto}


def test_el_enrutador_por_defecto_sigue_siendo_el_de_whatsapp(cliente):
    s = main.store
    ana = s.db["expedientes"][ANA]
    prop = hub.proponer_para_mensaje(s, evento_con("pregunta_checkin_horario"), ana, "Ana", "34600111222")
    assert (prop["plantilla"], prop["destino"], prop["destinatario"], prop["origen"]) == ("info_llegada", "whatsapp", "34600111222", "enrutador")
    prop = hub.proponer_para_mensaje(s, evento_con("cancelacion"), ana, "Ana", "34600111222")
    assert prop["plantilla"] == "revision_humana" and prop["slots"] == {"motivo": "cancelacion"} and prop["destinatario"] == "34600111222"
    # el nombre del perfil con espacios sobrantes no impide la respuesta
    assert hub.proponer_para_mensaje(s, evento_con("pregunta_checkin_horario"), None, "Pedro ", "34699000111")["plantilla"] == "info_llegada"


@pytest.mark.parametrize("intencion, plantilla", [("solicita_factura", "emitir_factura"), ("solicita_albaran", "emitir_albaran")])
def test_factura_y_albaran_con_estancia_proponen_emitir_y_sin_estancia_van_a_revision(cliente, intencion, plantilla):
    s = main.store
    claire = s.db["expedientes"][CLAIRE]
    for canal, contacto in (("whatsapp", "34612345678"), ("correo", "claire.dubois@example.com")):
        prop = hub.proponer_para_mensaje(s, evento_con(intencion), claire, "Claire", contacto, canal=canal)
        assert prop["plantilla"] == plantilla and prop["slots"] == {"expediente": CLAIRE} and prop["destino"] == "documentos" and prop["estado"] == "pendiente"
        assert prop["expediente_id"] == CLAIRE and prop["origen_evento"] == "ev-9999" and prop["destinatario"] == ""
        sin = hub.proponer_para_mensaje(s, evento_con(intencion), None, "Desconocido", contacto, canal=canal)
        assert sin["plantilla"] == "revision_humana" and sin["slots"] == {"motivo": intencion.replace("solicita_", "solicitud_")}


def test_por_correo_la_respuesta_de_horarios_usa_el_remitente_como_destinatario(cliente):
    s = main.store
    claire = s.db["expedientes"][CLAIRE]
    prop = hub.proponer_para_mensaje(s, evento_con("pregunta_checkin_horario"), claire, "Claire", canal="correo", contacto="claire.dubois@example.com")
    assert prop["plantilla"] == "correo_info_llegada" and prop["destino"] == "correo"
    assert prop["slots"] == {"nombre": "Claire", "destinatario": "claire.dubois@example.com"} and prop["destinatario"] == "claire.dubois@example.com"
    # un remitente con una dirección que no pasa la validación acaba en revisión humana, nunca en un correo
    prop = hub.proponer_para_mensaje(s, evento_con("pregunta_checkin_horario"), claire, "Claire", canal="correo", contacto="a@b.com\nBcc: x@y.com")
    assert prop["plantilla"] == "revision_humana"


def test_un_correo_de_una_direccion_desconocida_no_se_enlaza_a_ninguna_estancia(cliente):
    r = cliente.post("/api/correo/simular", json={"de": "claire.dubois@evil.example", "nombre": "Claire Dubois", "asunto": "Factura", "cuerpo": "Envíen la factura de Claire Dubois"})
    evento = next(e for e in main.store.db["eventos"] if e["id"] == r.json()[0]["evento"])
    propuesta = next(p for p in main.store.db["propuestas"] if p["id"] == r.json()[0]["propuesta"])
    assert evento["expediente_id"] is None and propuesta["plantilla"] == "revision_humana"  # el nombre no basta: manda el correo conocido
    assert hub.buscar_por_correo(main.store.db, "CLAIRE.DUBOIS@example.com")["id"] == CLAIRE and hub.buscar_por_correo(main.store.db, "") is None
