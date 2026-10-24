"""Pruebas de la lectura de OfiHotel: sin red y sin SQL Server real (sqlite3 inyectado)."""
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from app.adapters import ofihotel_lectura, ofihotel_sql
from app.adapters.ofihotel_sql import ConsultaNoPermitida

RAIZ = Path(__file__).resolve().parents[1]
PATRON = r"^(?P<localizador>.+)-(?P<portal>\d+)$"

MAPEO_PRUEBA = {
    "consultas": {"estancias": "SELECT id AS id_ofihotel, apellido AS huesped, hab AS habitacion, tp AS tipo, "
                               "f_in AS entrada, f_out AS salida, st AS estado, num_ext AS numero_externo, "
                               "pax AS personas FROM reservas"},
    "tipos_habitacion": {"DB": "DBL-STD", "IN": "SGL-STD"},
    "estados": {"R": "reservada", "I": "en_casa", "O": "salida", "A": "anulada"},
    "formato_fecha": "%d/%m/%Y",
    "regex_numero_externo": PATRON,
}


def crear_sqlite(ruta: Path) -> Path:
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE reservas (id TEXT, apellido TEXT, hab TEXT, tp TEXT, f_in TEXT, f_out TEXT, "
                "st TEXT, num_ext TEXT, pax INTEGER)")
    con.executemany("INSERT INTO reservas VALUES (?,?,?,?,?,?,?,?,?)", [
        ("1", "Pérez", "101", "DB", "24/10/2026", "26/10/2026", "R", "BK-4471920-1", 2),
        ("2", "Souto", "102", "IN", "20/10/2026", "24/10/2026", "I", "", 1),
        ("3", "Vila", "103", "DB", "10/10/2026", "12/10/2026", "O", "raro", 2),
        ("4", "Ares", "104", "DB", "25/10/2026", "27/10/2026", "A", "", 2),
    ])
    con.commit()
    con.close()
    return ruta


def hash_fichero(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_modo_fixture_devuelve_forma_normalizada():
    r = ofihotel_lectura.leer_instantanea(modo="fixture")
    assert r["fuente"] == "fixture"
    assert r["leido_el"] == "2026-10-24T09:00" and r["datos_hasta"] == "2026-10-23T23:59"
    assert len(r["estancias"]) == 6
    dubois = next(e for e in r["estancias"] if e["huesped"] == "Dubois")
    assert dubois["ref_externa"] == "2-EX-7730021" and dubois["numero_externo"] == "EX-7730021-2"
    assert {o["huesped"] for o in r["ocupaciones"]} == {"García", "Dubois", "Rey"}
    assert set(r["ocupaciones"][0]) == {"habitacion", "tipo", "desde", "hasta", "huesped", "ref_externa"}


def test_ref_externa_con_y_sin_patron_valido():
    assert ofihotel_sql.ref_externa_de("BK-4471920-1", PATRON) == "1-BK-4471920"
    assert ofihotel_sql.ref_externa_de("EX-7730021-2", PATRON) == "2-EX-7730021"
    assert ofihotel_sql.ref_externa_de("sin portal", PATRON) == ""
    assert ofihotel_sql.ref_externa_de("", PATRON) == ""
    assert ofihotel_sql.ref_externa_de(None, PATRON) == ""
    assert ofihotel_sql.ref_externa_de("BK-1-x", PATRON) == ""


def test_traduccion_de_tipos_y_estados():
    fila = dict(id_ofihotel="9", huesped="X", habitacion="1", tipo="DB", entrada="24/10/2026",
                salida="25/10/2026", estado="I", numero_externo="", personas="2")
    e = ofihotel_sql.normalizar_fila(fila, MAPEO_PRUEBA)
    assert (e["tipo"], e["estado"], e["entrada"], e["personas"]) == ("DBL-STD", "en_casa", "2026-10-24", 2)
    assert ofihotel_sql.normalizar_fila({**fila, "tipo": "ZZ"}, MAPEO_PRUEBA)["tipo"] == "ZZ"
    with pytest.raises(ofihotel_sql.MapeoError):
        ofihotel_sql.normalizar_fila({**fila, "estado": "?"}, MAPEO_PRUEBA)


def test_ocupaciones_solo_reservada_y_en_casa(tmp_path):
    db = crear_sqlite(tmp_path / "of.db")
    estancias = ofihotel_sql.leer_estancias(MAPEO_PRUEBA, conectar=lambda: sqlite3.connect(db))
    assert [e["estado"] for e in estancias] == ["reservada", "en_casa", "salida", "anulada"]
    ocup = ofihotel_lectura._derivar_ocupaciones(estancias)
    assert [o["huesped"] for o in ocup] == ["Pérez", "Souto"]
    assert ocup[0]["ref_externa"] == "1-BK-4471920" and ocup[1]["ref_externa"] == ""


def test_datos_hasta_por_defecto_y_por_variable(monkeypatch):
    monkeypatch.delenv("OFIHOTEL_DATOS_HASTA", raising=False)
    r = ofihotel_lectura.leer_instantanea(ahora="2026-10-24T09:00", modo="fixture")
    assert r["datos_hasta"] == "2026-10-23T23:59" and r["leido_el"] == "2026-10-24T09:00"
    monkeypatch.setenv("OFIHOTEL_DATOS_HASTA", "2026-10-20T12:00")
    assert ofihotel_lectura.leer_instantanea(ahora="2026-10-24T09:00", modo="fixture")["datos_hasta"] == "2026-10-20T12:00"


def test_modo_por_variable_y_modo_invalido(monkeypatch):
    monkeypatch.setenv("OFIHOTEL_MODO", "fixture")
    assert ofihotel_lectura.leer_instantanea()["fuente"] == "fixture"
    with pytest.raises(ValueError):
        ofihotel_lectura.leer_instantanea(modo="otro")


@pytest.mark.parametrize("sql", [
    "UPDATE reservas SET st='A'",
    "DELETE FROM reservas",
    "EXEC sp_who",
    "EXECUTE xp_cmdshell 'dir'",
    "SELECT 1; DROP TABLE reservas",
    "SELECT 1 /* inocente */ ; /* otro */ DROP TABLE reservas",
    "-- solo select\nDELETE FROM reservas",
    "/* SELECT */ UPDATE reservas SET st='A'",
    "SELECT * INTO copia FROM reservas",
    "WITH x AS (SELECT 1) DELETE FROM reservas",
    "SELECT 1 /* sin cerrar",
    "",
])
def test_guarda_rechaza_escritura(sql):
    with pytest.raises(ConsultaNoPermitida):
        ofihotel_sql.validar_solo_lectura(sql)


@pytest.mark.parametrize("sql", [
    "SELECT a FROM t",
    "  -- comentario\n select a from t;",
    "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
    "SELECT 'texto con UPDATE dentro' AS nota FROM t",
])
def test_guarda_admite_lecturas(sql):
    assert ofihotel_sql.validar_solo_lectura(sql) == sql


def test_mapeo_con_consulta_de_escritura_se_rechaza(tmp_path):
    mapeo = {**MAPEO_PRUEBA, "consultas": {"x": "DELETE FROM reservas"}}
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps(mapeo), encoding="utf-8")
    with pytest.raises(ConsultaNoPermitida):
        ofihotel_sql.cargar_mapeo(ruta)


def test_mapeo_de_ejemplo_es_valido_y_marca_placeholders():
    mapeo = ofihotel_sql.cargar_mapeo()
    assert "TABLA_RESERVAS" in mapeo["consultas"]["estancias"]
    assert "marcador" in mapeo["_comentario"].lower()


def test_pyodbc_ausente_da_mensaje_claro(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pyodbc", None)
    with pytest.raises(RuntimeError, match="pyodbc"):
        ofihotel_sql._conectar_pyodbc()


def test_conexion_se_cierra_aunque_falle():
    cerrada = []

    class Con:
        def cursor(self):
            raise RuntimeError("fallo")

        def close(self):
            cerrada.append(True)

    with pytest.raises(RuntimeError):
        ofihotel_sql.leer_estancias(MAPEO_PRUEBA, conectar=Con)
    assert cerrada == [True]


def test_modo_sql_de_la_instantanea_con_mapeo_inyectado(tmp_path, monkeypatch):
    db = crear_sqlite(tmp_path / "of.db")
    original = ofihotel_sql.leer_estancias
    monkeypatch.setattr(ofihotel_sql, "leer_estancias",
                        lambda: original(MAPEO_PRUEBA, conectar=lambda: sqlite3.connect(db)))
    monkeypatch.delenv("OFIHOTEL_DATOS_HASTA", raising=False)
    r = ofihotel_lectura.leer_instantanea(ahora="2026-10-24T09:00", modo="sql")
    assert r["fuente"] == "sql" and len(r["estancias"]) == 4 and len(r["ocupaciones"]) == 2


def cargar_explorador():
    spec = importlib.util.spec_from_file_location("ofihotel_explorar", RAIZ / "scripts" / "ofihotel_explorar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_explorador_informe_markdown_con_tabla_candidata(tmp_path):
    db = crear_sqlite(tmp_path / "of.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE parametros (clave TEXT, valor TEXT)")
    con.commit()
    con.close()
    exp = cargar_explorador()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    informe = exp.generar_informe(con, "sqlite", "reserva,huesped", muestra=2, mascara=True)
    con.close()
    assert informe.startswith("# Informe de esquema de OfiHotel")
    assert "| reservas | TABLE | 4 |" in informe
    assert "parametros" in informe.split("## Resto de tablas")[1]
    assert "Pé***" in informe and "Pérez" not in informe
    assert "Pérez" in exp.generar_informe(sqlite3.connect(db), "sqlite", "reserva", 1, mascara=False)


def test_explorador_ignora_tildes_y_mayusculas(tmp_path):
    exp = cargar_explorador()
    assert exp.normalizar("HABITACIÓN") == "habitacion"
    con = sqlite3.connect(tmp_path / "t.db")
    con.execute("CREATE TABLE Habitación (Número TEXT)")
    informe = exp.generar_informe(con, "sqlite", "habitacion,numero")
    assert "| Habitación | TABLE | 0 | 4 |" in informe


def test_explorador_cli_sqlite(tmp_path, capsys):
    db = crear_sqlite(tmp_path / "of.db")
    assert cargar_explorador().main(["--sqlite", str(db), "--muestra", "1"]) == 0
    assert "reservas" in capsys.readouterr().out


def test_ninguna_funcion_escribe_en_la_base(tmp_path):
    db = crear_sqlite(tmp_path / "of.db")
    antes = hash_fichero(db)
    ofihotel_sql.leer_estancias(MAPEO_PRUEBA, conectar=lambda: sqlite3.connect(f"file:{db}?mode=ro", uri=True))
    exp = cargar_explorador()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    exp.generar_informe(con, "sqlite", muestra=3)
    con.close()
    assert hash_fichero(db) == antes
    # y en modo de solo lectura la base rechaza incluso un intento de escritura directo
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM reservas")
    con.close()
