"""Nivel de semilla `demo`: completa intacta, relleno coherente, veredictos guionizados iguales y ningún endpoint con error."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app import disponibilidad, estados, main  # noqa: E402
from app.routers import demo  # noqa: E402
from app.store import Store  # noqa: E402

HOY = "2026-10-24"
VEREDICTOS = {"Sophie Martin": "no_disponible", "Carlos Meijide": "ajustado", "Lucía Fernández": "disponible",
              "Pablo Rey": "ajustado", "Marta Souto": "en_competencia"}


@pytest.fixture()
def nuevo(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HOTEL_AUTOSEMILLA", raising=False)

    def crear(nivel: str | None = None, ruta: str = "db.json"):
        monkeypatch.setattr(main, "store", Store(tmp_path / ruta))
        cliente = TestClient(main.app)
        if nivel:
            assert cliente.post(f"/api/demo/semilla?nivel={nivel}").status_code == 200
        return cliente
    return crear


@pytest.fixture()
def completa(nuevo):
    return nuevo("completa", "completa.json")


@pytest.fixture()
def con_demo(nuevo):
    return nuevo("demo", "demo.json")


def _veredictos(cliente) -> dict:
    return {c["de"]["nombre"]: c["contraste"]["veredicto"] for c in cliente.get("/api/comunicaciones").json()["comunicaciones"]
            if c["de"]["nombre"] in VEREDICTOS}


def _noches(cliente, dias=14) -> dict:
    """{tipo: {fecha: ocupadas}} con la ocupación que ve la aplicación."""
    mapa = cliente.get(f"/api/ocupacion?dias={dias}").json()["mapa"]["tipos"]
    return {t: {d["fecha"]: d["ocupadas"] for d in datos["dias"]} for t, datos in mapa.items()}


# ---------------------------------------------------------------- completa no cambia

def test_completa_sigue_igual(completa):
    db = main.store.db
    assert len(db["expedientes"]) == 4 and len(db["comunicaciones"]) == 6
    a_las_nueve = [e["id"] for e in db["eventos"] if e["ts"] == "2026-10-24T09:00"]
    assert a_las_nueve == ["ev-0001", "ev-0002", "ev-0003", "ev-0004", "ev-0006", "ev-0007", "ev-0009", "ev-0012"]
    assert len(db["eventos"]) == 8 and len(db["ofihotel"]["estancias"]) == 7
    assert [c["id"] for c in db["comunicaciones"]] == [f"cm-{n:04d}" for n in range(1, 7)]
    assert completa.get("/api/estancias").json()["contadores"] == {"rojo": 1, "naranja": 1, "amarillo": 1, "azul": 0, "gris": 1, "verde": 0}


def test_el_inventario_tiene_doce_habitaciones_en_cinco_tipos():
    assert disponibilidad.capacidad() == {"DBL-STD": 3, "SGL-STD": 2, "TPL-STD": 3, "FAM-STD": 2, "SUI-STD": 2}


# ---------------------------------------------------------------- demo

def test_demo_tiene_relleno_suficiente(con_demo):
    db = main.store.db
    assert len(db["ofihotel"]["estancias"]) >= 25 and len(db["comunicaciones"]) >= 15
    assert len(db["expedientes"]) >= 30
    assert main.store.ahora().isoformat(timespec="minutes") == "2026-10-24T09:00"


def test_demo_conserva_lo_de_completa_y_sus_ids(nuevo):
    cliente = nuevo("completa", "a.json")
    ids_completa = {e["id"]: e["ts"] for e in main.store.db["eventos"]}
    coms_completa = [c["id"] for c in main.store.db["comunicaciones"]]
    actividad_completa = [a["id"] for a in cliente.get("/api/fuente-unica").json()["actividad"]]
    cliente = nuevo("demo", "b.json")
    db = main.store.db
    assert {i: db_e["ts"] for db_e in db["eventos"] for i in [db_e["id"]] if i in ids_completa} == ids_completa
    assert [c["id"] for c in db["comunicaciones"]][:6] == coms_completa
    # lo más reciente de la actividad sigue siendo lo guionizado: sus 11 entradas son las mismas y en el mismo orden
    assert [a["id"] for a in cliente.get("/api/fuente-unica").json()["actividad"]][:len(actividad_completa)] == actividad_completa
    assert {e["id"] for e in db["eventos"] if e["ts"] == "2026-10-24T09:00"} == set(ids_completa)


def test_los_veredictos_guionizados_son_los_mismos_en_demo_y_en_completa(nuevo):
    en_completa = _veredictos(nuevo("completa", "c.json"))
    assert en_completa == VEREDICTOS
    assert _veredictos(nuevo("demo", "d.json")) == VEREDICTOS


def test_el_escenario_guionizado_cuadra_con_la_ocupacion(con_demo):
    n = _noches(con_demo)
    assert n["DBL-STD"]["2026-10-24"] == 3  # Sophie: la noche del 24 hay 3 de 3 dobles
    assert all(n["DBL-STD"][f] <= 2 for f in ("2026-10-25", "2026-10-26", "2026-10-27"))  # su alternativa del 25 al 28 sigue abierta
    assert all(n["DBL-STD"][f] == 0 for f in ("2026-11-01", "2026-11-02"))  # Carlos: 3 dobles justas
    assert all(n["DBL-STD"][f] <= 1 for f in ("2026-10-28", "2026-10-29"))  # Lucía: al menos 2 libres
    assert n["SGL-STD"]["2026-10-24"] == 1  # Pablo gana y Marta compite por la única individual libre
    comunicaciones = {c["de"]["nombre"]: c for c in con_demo.get("/api/comunicaciones").json()["comunicaciones"]}
    assert comunicaciones["Sophie Martin"]["contraste"]["alternativa"] == {"desde": "2026-10-25", "hasta": "2026-10-28", "noches": 3}
    assert comunicaciones["Lucía Fernández"]["contraste"]["noches"][0]["libres"] >= 2
    assert comunicaciones["Ana Pereira"]["tipo"] == "pregunta" and comunicaciones["Ana Pereira"]["contraste"] is None


def test_ningun_tipo_se_llena_salvo_la_doble_del_24(con_demo):
    llenas = []
    capacidad = disponibilidad.capacidad()
    for tipo, dias in _noches(con_demo, 30).items():
        for fecha, ocupadas in dias.items():
            assert ocupadas <= capacidad[tipo], f"{tipo} {fecha}: {ocupadas} para {capacidad[tipo]}"
            if ocupadas >= capacidad[tipo]:
                llenas.append((tipo, fecha))
    assert llenas == [("DBL-STD", HOY)]


def test_la_ocupacion_media_de_los_14_dias_es_razonable(con_demo):
    n = _noches(con_demo)
    capacidad = disponibilidad.capacidad()
    media = sum(sum(d.values()) for d in n.values()) / sum(capacidad[t] * 14 for t in n)
    assert 0.40 <= media <= 0.60
    fines = sum(n[t][f] for t in n for f in ("2026-10-24", "2026-10-25", "2026-10-31", "2026-11-01"))
    entre_semana = sum(n[t][f] for t in n for f in ("2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-11-03", "2026-11-04"))
    assert fines / 4 >= entre_semana / 6 - 1  # el fin de semana no está más vacío que la semana


def test_conflictos_son_los_guionizados_mas_los_extra_y_sin_habitacion_doble_ni_overbooking(con_demo):
    conflictos = con_demo.get("/api/conflictos").json()["conflictos"]
    tipos = sorted((c["tipo"], c["nivel"]) for c in conflictos)
    assert tipos == [("cancelada_activa_en_ofihotel", "gris"), ("cancelada_activa_en_ofihotel", "gris"), ("fechas_distintas", "rojo"),
                     ("fechas_distintas", "rojo")]
    assert not [c for c in conflictos if c["tipo"] in ("habitacion_doble", "overbooking")]
    assert [c for c in disponibilidad.conflictos(main.store.db, HOY, 30) if c["nivel"] == "overbooking"] == []


def test_ninguna_habitacion_de_ofihotel_se_solapa(con_demo):
    por_habitacion: dict[str, list] = {}
    for e in main.store.db["ofihotel"]["estancias"]:
        if e["estado"] in ("reservada", "en_casa"):
            por_habitacion.setdefault(e["habitacion"], []).append((e["entrada"], e["salida"], e["huesped"]))
    for hab, filas in por_habitacion.items():
        filas.sort()
        for (_, salida, _), (entrada, _, quien) in zip(filas, filas[1:]):
            assert salida <= entrada, f"habitación {hab}: {quien} se solapa"


def test_el_semaforo_reparte_los_seis_colores(con_demo):
    contadores = con_demo.get("/api/estancias").json()["contadores"]
    assert all(contadores[c] >= 1 for c in estados.COLORES), contadores
    assert contadores["verde"] > contadores["rojo"] + contadores["naranja"] + contadores["amarillo"] + contadores["azul"] + contadores["gris"]
    assert 2 <= contadores["azul"] <= 3
    en_casa = [e for e in con_demo.get("/api/estancias?filtro=en_casa").json()["estancias"]]
    naranja = [e for e in en_casa if e["semaforo"]["color"] == "naranja" and e["parte_restante_h"] is not None and e["parte_restante_h"] < 10]
    assert naranja and naranja[0]["parte_restante_h"] == 6.0


def test_origenes_y_comunicaciones_del_relleno(con_demo):
    origenes = [e["origen"] for e in main.store.db["expedientes"].values()]
    assert origenes.count("walk-in") == 3 and origenes.count("mensaje") == 3
    portales = {e["id"].split("-")[0] for e in main.store.db["expedientes"].values() if e["origen"] == "roomcloud"}
    assert {"0", "1", "2"} <= portales
    coms = main.store.db["comunicaciones"]
    assert sum(c["estado"] == "respondida" for c in coms) >= 5 and sum(c["estado"] == "descartada" for c in coms) == 1
    acciones = sorted(c["resultado"]["accion"] for c in coms if c["resultado"])
    assert acciones.count("reservada") == 3 and "sin_hueco" in acciones and "respondida" in acciones and "descartada" in acciones
    assert all(c["ts"] <= "2026-10-24T07:59" for c in coms[6:]) and all(c["ts"] >= "2026-10-23T16:00" for c in coms[6:])
    reservas = {c["resultado"]["reserva_id"] for c in coms if c["resultado"] and c["resultado"]["accion"] == "reservada"}
    assert all(main.store.db["expedientes"][r]["origen"] == "mensaje" for r in reservas)
    pendientes_sin_peticion = [c for c in coms[6:] if c["estado"] == "pendiente" and not c["peticion"]]
    assert len(pendientes_sin_peticion) == 4 and sum(bool(c["expediente_id"]) for c in pendientes_sin_peticion) == 3


def test_los_huespedes_en_casa_no_marcan_las_nueve_de_hoy(con_demo):
    for exp in main.store.db["expedientes"].values():
        if exp["estado"] != "en_curso" or exp["id"] in ("1-BK-4471920", "0-WEB-90112"):
            continue
        assert exp["checkin_hora"] < "2026-10-24T09:00"
        assert all(r["hora"] < "2026-10-24T09:00" for r in exp["registro"][1:])
        if exp["parte"]:
            assert exp["parte"]["enviado_el"] < "2026-10-24T09:00"


def test_es_determinista(nuevo):
    nuevo("demo", "uno.json")
    primero = main.store.db
    nuevo("demo", "dos.json")
    assert primero == main.store.db


# ---------------------------------------------------------------- endpoints sin error

RUTAS = ["/api/fuente-unica", "/api/comunicaciones", "/api/comunicaciones?estado=pendientes&canal=whatsapp", "/api/estancias",
         "/api/estancias?filtro=en_casa", "/api/estancias?filtro=hoy&color=azul", "/api/ocupacion?dias=14", "/api/conflictos",
         "/api/insignias", "/api/propuestas", "/api/propuestas?estado=pendiente", "/api/panel", "/api/hoy", "/api/disponibilidad?dias=14"]


@pytest.mark.parametrize("ruta", RUTAS)
def test_ningun_endpoint_da_500_con_demo(con_demo, ruta):
    assert con_demo.get(ruta).status_code < 500


def test_cada_comunicacion_y_cada_estancia_se_puede_abrir(con_demo):
    for c in con_demo.get("/api/comunicaciones").json()["comunicaciones"]:
        assert con_demo.get(f"/api/comunicaciones/{c['id']}").status_code == 200
    for e in con_demo.get("/api/estancias").json()["estancias"]:
        assert con_demo.get(f"/api/expedientes/{e['id']}").status_code == 200


@pytest.mark.parametrize("pregunta", ["¿Qué llegadas tenemos hoy?", "¿Cuántas dobles quedan libres esta semana?", "¿Qué comunicaciones están pendientes?"])
def test_el_chat_responde_con_demo(con_demo, pregunta):
    assert con_demo.post("/api/chat", json={"mensaje": pregunta}).status_code == 200
    r = con_demo.post("/api/chat/stream", json={"mensaje": pregunta})
    assert r.status_code == 200 and "event: error" not in r.text and "event: fin" in r.text


def test_los_niveles_anteriores_y_el_nivel_desconocido(nuevo):
    cliente = nuevo()
    assert cliente.post("/api/demo/semilla?nivel=inventado").status_code == 422
    assert set(demo.NIVELES) == {"vacia", "basica", "completa", "demo"}
    for nivel in ("vacia", "basica"):
        assert cliente.post(f"/api/demo/semilla?nivel={nivel}").status_code == 200


# ---------------------------------------------------------------- siembra automática al arrancar

def test_el_arranque_normal_no_siembra(nuevo, monkeypatch):
    monkeypatch.delenv("HOTEL_AUTOSEMILLA", raising=False)
    nuevo()
    with TestClient(main.app):
        assert main.store.db["expedientes"] == {} and main.store.db["eventos"] == []


def test_con_hotel_autosemilla_el_arranque_siembra_si_el_almacen_esta_vacio(nuevo, monkeypatch):
    monkeypatch.setenv("HOTEL_AUTOSEMILLA", "demo")
    nuevo()
    with TestClient(main.app):
        assert len(main.store.db["expedientes"]) >= 30 and len(main.store.db["comunicaciones"]) >= 15


def test_con_hotel_autosemilla_no_pisa_un_almacen_con_datos(nuevo, monkeypatch):
    monkeypatch.setenv("HOTEL_AUTOSEMILLA", "demo")
    cliente = nuevo("basica", "con_datos.json")
    antes = dict(main.store.db["expedientes"])
    with cliente:
        assert main.store.db["expedientes"] == antes
