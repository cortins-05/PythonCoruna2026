"""Almacén (HOTEL_DB, JSON antiguo) y semilla de demostración (siempre el mismo estado)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app import main, store as modulo_store  # noqa: E402
from app.store import Store  # noqa: E402

ANA, MARCOS, CLAIRE = "1-BK-4471920", "0-WEB-90112", "2-EX-7730021"
CLAVES_NUEVAS = {"documentos": {}, "outbox": [], "series": {"factura": 0, "albaran": 0}}


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return TestClient(main.app)


# ================================================================ almacén

def test_la_ruta_del_json_sale_de_hotel_db_y_si_no_es_la_de_siempre(tmp_path, monkeypatch):
    monkeypatch.setenv("HOTEL_DB", str(tmp_path / "otra" / "mia.json"))
    assert Store().ruta == tmp_path / "otra" / "mia.json" and modulo_store.ruta_db() == tmp_path / "otra" / "mia.json"
    s = Store()
    s.guardar()  # crea las carpetas que falten
    assert (tmp_path / "otra" / "mia.json").exists()
    monkeypatch.setenv("HOTEL_DB", "   ")
    assert Store().ruta == modulo_store.RUTA_POR_DEFECTO and Store().ruta.parts[-2:] == ("data", "db.json")
    monkeypatch.delenv("HOTEL_DB")
    assert Store().ruta == modulo_store.RUTA_POR_DEFECTO
    assert Store(tmp_path / "explicita.json").ruta == tmp_path / "explicita.json"  # una ruta pasada a mano manda sobre la variable


def test_dos_procesos_con_hotel_db_distinto_usan_cada_uno_su_fichero(tmp_path):
    codigo = ("import sys; sys.path.insert(0, sys.argv[1]); from app.main import store; "
              "store.db['seq'] = int(sys.argv[2]); store.guardar(); print(store.ruta)")
    rutas = []
    for numero in (3, 7):
        entorno = {"HOTEL_DB": str(tmp_path / f"proceso{numero}.json"), "SYSTEMROOT": "C:/Windows", "PATH": ""}
        fuera = subprocess.run([sys.executable, "-I", "-c", codigo, str(RAIZ), str(numero)], capture_output=True, text=True, env=entorno, timeout=60)
        assert fuera.returncode == 0, fuera.stderr
        rutas.append(fuera.stdout.strip())
    assert rutas == [str(tmp_path / "proceso3.json"), str(tmp_path / "proceso7.json")]
    assert [json.loads((tmp_path / f"proceso{n}.json").read_text(encoding="utf-8"))["seq"] for n in (3, 7)] == [3, 7]


def test_un_json_antiguo_sin_las_claves_nuevas_se_carga_y_se_completa(tmp_path):
    antiguo = {"expedientes": {}, "reloj_h": 3, "seq": 5, "eventos": [{"id": "ev-0001"}], "propuestas": [], "cierres": [], "ofihotel": {}}
    ruta = tmp_path / "antiguo.json"
    ruta.write_text(json.dumps(antiguo), encoding="utf-8")
    s = Store(ruta)
    assert {k: s.db[k] for k in CLAVES_NUEVAS} == CLAVES_NUEVAS
    assert s.db["reloj_h"] == 3 and s.db["seq"] == 5 and s.db["eventos"] == [{"id": "ev-0001"}]  # lo que ya había se conserva
    ruta.write_text(json.dumps({**antiguo, "series": {"factura": 4}, "documentos": [], "outbox": {}}), encoding="utf-8")
    s = Store(ruta)
    assert s.db["series"] == {"factura": 4, "albaran": 0} and s.db["documentos"] == {} and s.db["outbox"] == []
    ruta.write_text("{}", encoding="utf-8")
    assert Store(ruta).db["series"] == {"factura": 0, "albaran": 0}


def test_el_estado_vacio_incluye_documentos_outbox_y_series(tmp_path):
    s = Store(tmp_path / "nuevo.json")
    assert {k: s.db[k] for k in CLAVES_NUEVAS} == CLAVES_NUEVAS
    s.db["series"]["factura"] = 9
    s.reiniciar()
    assert s.db["series"] == {"factura": 0, "albaran": 0}
    assert Store(tmp_path / "nuevo.json").db["series"] == {"factura": 0, "albaran": 0}


def test_guardar_y_volver_a_cargar_conserva_los_documentos(tmp_path, cliente):
    cliente.post("/api/demo/semilla")
    recargado = Store(main.store.ruta)
    assert recargado.db == json.loads(json.dumps(main.store.db))
    assert recargado.db["documentos"]["doc-0011"]["numero"] == "DEMO-F-0001" and recargado.db["series"]["factura"] == 1


# ================================================================ semilla

def test_la_semilla_vacia_deja_todo_a_cero_con_el_reloj_en_su_sitio(cliente):
    cliente.post("/api/demo/semilla")
    cliente.post("/api/reloj", json={"horas": 30})
    r = cliente.post("/api/demo/semilla", params={"nivel": "vacia"})
    assert r.status_code == 200 and r.json() == {"nivel": "vacia", "reloj": "2026-10-24T09:00", "expedientes": 0, "eventos": 0,
                                                  "propuestas": 0, "propuestas_pendientes": 0, "documentos": 0}
    db = main.store.db
    assert db["expedientes"] == {} and db["documentos"] == {} and db["outbox"] == [] and db["series"] == {"factura": 0, "albaran": 0} and db["seq"] == 0


def test_la_semilla_basica_trae_las_reservas_y_la_lectura_de_ofihotel_y_nada_mas(cliente):
    r = cliente.post("/api/demo/semilla", params={"nivel": "basica"})
    assert r.status_code == 200 and r.json()["expedientes"] == 3 and r.json()["documentos"] == 0
    db = main.store.db
    assert set(db["expedientes"]) == {ANA, MARCOS, CLAIRE}  # la reserva cancelada de Luis no crea expediente
    assert all(e["estado"] == "pendiente_llegada" for e in db["expedientes"].values())
    assert db["ofihotel"]["ocupaciones"] and any(p["plantilla"] == "cerrar_disponibilidad" for p in db["propuestas"])
    assert not any(e["fuente"] in ("whatsapp", "correo") for e in db["eventos"]) and not db["outbox"]


def test_la_semilla_completa_trae_todo_lo_que_describe_el_contrato(cliente):
    r = cliente.post("/api/demo/semilla", params={"nivel": "completa"})
    assert r.status_code == 200 and r.json()["reloj"] == "2026-10-24T09:00"
    db = main.store.db
    ana, marcos, claire = (db["expedientes"][i] for i in (ANA, MARCOS, CLAIRE))
    # Ana: check-in hecho con la lectura de muestra, pago con tarjeta, empresa con correo y parte enviado (simulado)
    assert ana["estado"] == "en_curso" and ana["huesped"]["numero_documento"] == "12345678Z" and ana["pago"] == {"medio": "TARJETA"}
    assert ana["empresa"] == {"razon_social": "Atlántico Consultores SL", "cif": "B15000000", "direccion": "Rúa Real 1, A Coruña", "email": "facturas@atlantico.example"}
    assert ana["tramites"]["huesped"]["estado"] == ana["tramites"]["pago"]["estado"] == ana["tramites"]["empresa"]["estado"] == ana["tramites"]["parte"]["estado"] == "hecho"
    assert ana["parte"]["simulado"] is True and ana["parte"]["justificante"].startswith("SIM-") and ana["reserva"]["email"] == "ana.pereira@example.com"
    # Marcos: check-in hecho con un NIF válido y el parte pendiente
    assert marcos["estado"] == "en_curso" and marcos["huesped"]["numero_documento"] == "87654321X" and marcos["tramites"]["parte"]["estado"] == "pendiente"
    assert main.parte_restante_h(marcos) == 24.0
    assert claire["estado"] == "pendiente_llegada"
    # mensajes: el WhatsApp de Ana y el correo de Claire, cada uno con su propuesta
    mensajes = [e for e in db["eventos"] if e["tipo"] == "mensaje_entrante"]
    assert [(m["fuente"], m["expediente_id"], m["datos"]["interpretacion"]["intencion"]) for m in mensajes] == [
        ("whatsapp", ANA, "pregunta_checkin_horario"), ("correo", CLAIRE, "solicita_factura")]
    pendientes = {p["plantilla"]: p for p in db["propuestas"] if p["estado"] == "pendiente"}
    assert set(pendientes) == {"cerrar_disponibilidad", "info_llegada", "emitir_factura"}
    assert pendientes["info_llegada"]["origen_evento"] == mensajes[0]["id"] and pendientes["emitir_factura"]["origen_evento"] == mensajes[1]["id"]
    # documentos: una factura emitida y un albarán en borrador con dos líneas, los dos de Ana
    docs = sorted(db["documentos"].values(), key=lambda d: d["id"])
    assert [(d["tipo"], d["estado"], d["numero"], d["expediente_id"]) for d in docs] == [("factura", "emitido", "DEMO-F-0001", ANA), ("albaran", "borrador", None, ANA)]
    assert len(docs[1]["lineas"]) == 2 and docs[0]["envios"] == [] and db["series"] == {"factura": 1, "albaran": 0}
    # la ocupación llega a 3 de 3 en DBL-STD con la lectura de OfiHotel, sin contar dos veces a Claire
    assert {"tipo": "DBL-STD", "fecha": "2026-10-24", "ocupadas": 3, "capacidad": 3, "nivel": "lleno"} in cliente.get("/api/disponibilidad").json()["conflictos"]


def test_la_semilla_completa_es_siempre_identica(tmp_path, monkeypatch):
    def sembrar(ruta, antes=None):
        monkeypatch.setattr(main, "store", Store(ruta))
        c = TestClient(main.app)
        if antes:
            antes(c)
        assert c.post("/api/demo/semilla", params={"nivel": "completa"}).status_code == 200
        return json.dumps(main.store.db, sort_keys=True, ensure_ascii=False)

    primera = sembrar(tmp_path / "a.json")
    segunda = sembrar(tmp_path / "b.json")
    ensuciada = sembrar(tmp_path / "c.json", antes=lambda c: (c.post("/api/demo/semilla"), c.post("/api/reloj", json={"horas": 40}),
                                                              c.post("/api/documentos/borrador", json={"tipo": "factura", "expediente_id": ANA})))
    assert primera == segunda == ensuciada
    sembrar(tmp_path / "a.json")  # sembrar encima del mismo fichero tampoco cambia nada
    assert json.dumps(main.store.db, sort_keys=True, ensure_ascii=False) == primera


def test_los_ids_de_la_semilla_completa_son_estables(cliente):
    """Los agentes de front capturan pantallas con estos ids: si cambian, hay que avisar."""
    cliente.post("/api/demo/semilla")
    db = main.store.db
    assert [e["id"] for e in db["eventos"]] == ["ev-0001", "ev-0002", "ev-0003", "ev-0004", "ev-0006", "ev-0007", "ev-0009", "ev-0012"]
    assert {p["id"]: p["plantilla"] for p in db["propuestas"]} == {"pr-0005": "cerrar_disponibilidad", "pr-0008": "info_llegada", "pr-0010": "emitir_factura"}
    assert sorted(db["documentos"]) == ["doc-0011", "doc-0013"] and db["seq"] == 13
    assert [c["id"] for c in cliente.get("/api/mensajes/conversaciones").json()["conversaciones"]] == ["mail:claire.dubois@example.com", "wa:34600111222"]


def test_la_semilla_valida_el_nivel_y_por_defecto_es_completa(cliente):
    r = cliente.post("/api/demo/semilla", params={"nivel": "enorme"})
    assert r.status_code == 422 and "vacia, basica, completa" in r.json()["detail"]["problemas"][0]
    assert cliente.post("/api/demo/semilla").json()["nivel"] == "completa"


def test_con_otro_origen_del_reloj_la_semilla_sigue_dejando_las_nueve_del_24(cliente, monkeypatch):
    from datetime import datetime
    from app.routers import demo
    monkeypatch.setattr(demo, "INICIO_DEMO", datetime.fromisoformat("2026-10-23T07:00:00"))
    monkeypatch.setattr(modulo_store, "INICIO_DEMO", datetime.fromisoformat("2026-10-23T07:00:00"))
    assert cliente.post("/api/demo/semilla", params={"nivel": "vacia"}).json()["reloj"] == "2026-10-24T09:00"
    assert main.store.db["reloj_h"] == 26


def test_la_semilla_se_puede_aplicar_a_un_almacen_que_no_es_el_de_la_aplicacion_solo_si_es_el_mismo(tmp_path):
    from app.routers import demo
    with pytest.raises(RuntimeError):
        demo.sembrar_estado(Store(tmp_path / "ajeno.json"), "completa")
