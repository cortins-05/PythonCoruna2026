import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main  # noqa: E402
from app.adapters import roomcloud  # noqa: E402
from app.routers.demo import HUESPED_ANA  # noqa: E402
from app.store import Store  # noqa: E402
from app.validators import validar_documento  # noqa: E402

ANA = "1-BK-4471920"


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = TestClient(main.app)
    c.post("/api/sync/roomcloud")
    return c


def datos_ana(**cambios):
    return {**HUESPED_ANA, **cambios}


def test_documento_letra_de_control():
    assert validar_documento("NIF", "12345678Z") == []
    assert validar_documento("NIF", "12345678A")
    assert validar_documento("NIE", "X1234567L") == []
    assert validar_documento("NIE", "X1234567A")
    assert validar_documento("PAS", "AB123456") == []


def test_parser_descarta_la_tarjeta():
    reservas = roomcloud.leer_reservas()
    assert len(reservas) == 4
    assert "4111111111111111" not in json.dumps(reservas)
    assert "5555555555554444" not in json.dumps(reservas)


def test_sync_es_idempotente_y_no_guarda_tarjetas(cliente):
    segunda = cliente.post("/api/sync/roomcloud").json()
    assert segunda["nuevas"] == 0 and segunda["sin_cambios"] >= 3
    guardado = main.store.ruta.read_text(encoding="utf-8")
    assert "4111111111111111" not in guardado and "ccData" not in guardado
    assert len(cliente.get("/api/expedientes").json()) == 4  # las tres vivas y la que ya llegó cancelada


def test_la_aplicacion_ya_no_tiene_ocr_ni_check_out(cliente):
    assert cliente.post(f"/api/expedientes/{ANA}/ocr", json={}).status_code in (404, 405)
    assert cliente.post(f"/api/expedientes/{ANA}/cerrar", json={}).status_code in (404, 405)
    assert cliente.post(f"/api/expedientes/{ANA}/tramites/factura", json={}).status_code == 404
    assert cliente.post(f"/api/expedientes/{ANA}/tramites/habitacion_liberada", json={}).status_code == 404
    assert main.requeridos(main.store.db["expedientes"][ANA]) == ["huesped", "pago", "empresa", "parte"]


def test_letra_mala_bloquea_el_guardado(cliente):
    r = cliente.put(f"/api/expedientes/{ANA}/huesped", json=datos_ana(numero_documento="12345678A"))
    assert r.status_code == 422


def test_viaje_de_trabajo_exige_empresa_antes_de_seguir(cliente):
    cliente.put(f"/api/expedientes/{ANA}/huesped", json=datos_ana())
    r = cliente.put(f"/api/expedientes/{ANA}/pago", json={"medio": "tarjeta"})
    assert r.status_code == 422
    assert cliente.get(f"/api/expedientes/{ANA}").json()["tramites"]["pago"]["estado"] == "pendiente"


def test_flujo_completo_hasta_el_parte_y_el_paso_a_ofihotel(cliente):
    assert cliente.put(f"/api/expedientes/{ANA}/huesped", json=datos_ana()).status_code == 200
    pago = {"medio": "tarjeta", "empresa": {"razon_social": "Atlántico Consultores SL", "cif": "B15000000", "direccion": "Rúa Real 1, A Coruña"}}
    assert cliente.put(f"/api/expedientes/{ANA}/pago", json=pago).status_code == 200

    previa = cliente.get(f"/api/expedientes/{ANA}/parte").json()
    assert previa["faltan"] == [] and "SIMULADO" in previa["xml"]

    enviado = cliente.post(f"/api/expedientes/{ANA}/parte/confirmar", json={"actor": "Flor"}).json()
    assert enviado["simulado"] is True and enviado["justificante"].startswith("SIM-")
    assert cliente.post(f"/api/expedientes/{ANA}/parte/confirmar", json={}).status_code == 409

    detalle = cliente.get(f"/api/expedientes/{ANA}").json()
    assert detalle["pendientes"] == []  # lo que se hace aquí está hecho: el check-out y la factura son de OfiHotel
    assert detalle["tramites"]["ofihotel_alta"]["estado"] == "pendiente"
    assert cliente.post(f"/api/expedientes/{ANA}/tramites/ofihotel_alta", json={"actor": "Flor"}).status_code == 200
    assert cliente.get(f"/api/expedientes/{ANA}").json()["tramites"]["ofihotel_alta"]["estado"] == "hecho"


def test_parte_sin_medio_de_pago_no_se_puede_confirmar(cliente):
    otro = "0-WEB-90112"
    assert cliente.put(f"/api/expedientes/{otro}/huesped", json=datos_ana(nombre="Marcos", apellido1="Vilas", apellido2="")).status_code == 200
    main.store.db["expedientes"][otro]["pago"]["medio"] = ""  # la reserva traía un medio de pago, aquí lo quitamos
    r = cliente.post(f"/api/expedientes/{otro}/parte/confirmar", json={})
    assert r.status_code == 409 and "Medio de pago" in r.json()["detail"]["faltan"]


def test_alerta_de_parte_fuera_de_plazo_con_el_reloj(cliente):
    cliente.put(f"/api/expedientes/{ANA}/huesped", json=datos_ana())
    assert cliente.get("/api/panel").json()["alertas"] == []
    cliente.post("/api/reloj", json={"horas": 12})  # 21:00, pasadas las 20 h
    assert [a["nivel"] for a in cliente.get("/api/panel").json()["alertas"]] == ["aviso"]
    cliente.post("/api/reloj", json={"horas": 6})  # 03:00, el aviso no puede desaparecer de madrugada
    niveles = [a["nivel"] for a in cliente.get("/api/panel").json()["alertas"]]
    assert "aviso" in niveles and "critico" not in niveles
    cliente.post("/api/reloj", json={"horas": 7})  # 34 h después del check-in
    assert "critico" in [a["nivel"] for a in cliente.get("/api/panel").json()["alertas"]]
