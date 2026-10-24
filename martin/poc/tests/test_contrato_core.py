"""Contrato ejecutable del núcleo de la demo: las formas de `design/CONTRATO-CORE.md` apartados 3 y 4 con la semilla completa y con el
almacén vacío. Reutiliza el validador de formas y las formas de bloques de `test_contrato.py`."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import main  # noqa: E402
from app.store import Store  # noqa: E402
from test_contrato import (COLORES, COMUNICACION, CONFLICTO, CONTADORES_COLOR, ESTANCIA, FUENTE, ITEM_COLA, PRIORIDADES,  # noqa: E402
                           comprobar_bloque, exigir, ver)

CLAIRE = "2-EX-7730021"
DATOS_OFIHOTEL = {"disponible": bool, "datos_hasta": (str, None), "leido_el": (str, None), "fuente": (str, None)}
LEYENDA = [{"color": COLORES, "titulo": str, "descripcion": str}]
ACTIVIDAD = {"id": str, "ts": str, "hora": str, "fuente": str, "icono": str, "titulo": str, "detalle": str, "nivel": (int, None),
             "expediente_id": (str, None)}
FUENTE_UNICA = {"reloj": str, "prioridades": PRIORIDADES, "fuentes": [FUENTE], "cola": [ITEM_COLA], "actividad": [ACTIVIDAD],
                "totales": {"estancias": int, "comunicaciones_pendientes": int, "conflictos": int, "por_color": CONTADORES_COLOR},
                "datos_ofihotel": DATOS_OFIHOTEL, "leyenda": LEYENDA}
CONTADORES_COM = {"pendientes": int, "en_espera": int, "respondidas": int, "total": int, "whatsapp": int, "correo": int}
COMUNICACIONES = {"reloj": str, "?fuentes_consultadas": [{"id": str, "nombre": str, "nivel": int, "tipo": str}],
                  "comunicaciones": [COMUNICACION], "contadores": CONTADORES_COM, "prioridades": PRIORIDADES}
ESTANCIAS = {"reloj": str, "datos_ofihotel": DATOS_OFIHOTEL, "leyenda": LEYENDA, "estancias": [ESTANCIA], "conflictos": [CONFLICTO],
             "entradas": [dict], "contadores": CONTADORES_COLOR}
CASILLA = {"fecha": str, "?ocupadas": int, "?libres": int, "?cerrado_en_roomcloud": bool, "?por_fuente": dict}
OCUPACION = {"reloj": str, "desde": str, "dias": int, "mapa": {"fechas": [str], "tipos": dict}, "conflictos": [dict],
             "peticiones": [{"id": str, "canal": {"whatsapp", "correo"}, "prioridad": dict, "de": str, "hora": str,
                             "tipo_habitacion": str, "desde": str, "hasta": str, "habitaciones": int, "veredicto": str}],
             "fuentes": [dict]}
INSIGNIAS = {"insignias": {"comunicaciones": int, "estancias": int, "fuente": int}}
EVENTOS = {"herramienta", "bloque", "texto", "fin", "error"}


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = TestClient(main.app)
    c.post("/api/demo/semilla", params={"nivel": "completa"})
    return c


@pytest.fixture()
def vacio(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "vacio.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return TestClient(main.app)


def eventos_sse(c, mensaje: str, historial=None) -> list[tuple[str, dict]]:
    """Lee `POST /api/chat/stream` entero y devuelve los eventos como pares (nombre, datos), comprobando el formato del texto."""
    r = c.post("/api/chat/stream", json={"mensaje": mensaje, "historial": historial or []})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    eventos = []
    for trozo in r.text.split("\n\n"):
        if not trozo.strip():
            continue
        lineas = trozo.split("\n")
        assert len(lineas) == 2 and lineas[0].startswith("event: ") and lineas[1].startswith("data: "), repr(trozo)
        eventos.append((lineas[0][len("event: "):], json.loads(lineas[1][len("data: "):])))
    return eventos


# ================================================================ semilla completa

def test_prioridades_es_la_escalera_de_cinco_niveles(cliente):
    datos = ver(cliente, "/api/prioridades")
    exigir(PRIORIDADES, datos)
    assert [n["nivel"] for n in datos["niveles"]] == [1, 2, 3, 4, 5]
    assert [n["id"] for n in datos["niveles"]] == ["roomcloud", "ofihotel", "recepcion", "correo", "whatsapp"]
    assert [n["tipo"] for n in datos["niveles"]] == ["firme", "firme", "firme", "peticion", "peticion"]
    assert datos["reglas"]


def test_fuente_unica_tiene_la_forma_y_cuadra_con_las_demas_pantallas(cliente):
    datos = ver(cliente, "/api/fuente-unica")
    exigir(FUENTE_UNICA, datos)
    assert datos["prioridades"] == ver(cliente, "/api/prioridades")
    assert {f["id"] for f in datos["fuentes"]} >= {"roomcloud", "ofihotel", "recepcion", "correo", "whatsapp"}
    assert datos["totales"]["estancias"] == len(ver(cliente, "/api/estancias")["estancias"])
    assert datos["totales"]["conflictos"] == len(ver(cliente, "/api/conflictos")["conflictos"])
    assert datos["totales"]["comunicaciones_pendientes"] == ver(cliente, "/api/comunicaciones")["contadores"]["pendientes"]
    assert datos["totales"]["por_color"] == ver(cliente, "/api/estancias")["contadores"]
    # la cola viene ordenada por el nivel de la fuente y el front no la reordena
    niveles = [i["prioridad"]["nivel"] for i in datos["cola"]]
    assert niveles == sorted(niveles) and datos["cola"]


def test_comunicaciones_y_una_comunicacion_tienen_la_forma_del_contrato(cliente):
    datos = ver(cliente, "/api/comunicaciones", estado="pendientes", canal="todos")
    exigir(COMUNICACIONES, datos)
    assert datos["comunicaciones"] and all(c["estado"] == "pendiente" for c in datos["comunicaciones"])
    assert datos["contadores"]["pendientes"] == len(datos["comunicaciones"])
    for canal in ("whatsapp", "correo"):
        assert {c["canal"] for c in ver(cliente, "/api/comunicaciones", canal=canal)["comunicaciones"]} <= {canal}
    for com in datos["comunicaciones"]:
        assert com["respuesta"]["canal"] == com["canal"], "la respuesta sale por el mismo canal por el que llegó"
        assert com["prioridad"]["id"] == com["canal"]
        if com["tipo"] == "peticion_habitacion":
            assert com["peticion"] and com["contraste"]
    una = datos["comunicaciones"][0]
    assert ver(cliente, f"/api/comunicaciones/{una['id']}") == una
    exigir(COMUNICACION, ver(cliente, f"/api/comunicaciones/{una['id']}"))
    assert cliente.get("/api/comunicaciones/cm-9999").status_code == 404


def test_estancias_con_filtros_y_conflictos(cliente):
    datos = ver(cliente, "/api/estancias")
    exigir(ESTANCIAS, datos)
    assert datos["estancias"] and datos["datos_ofihotel"]["disponible"] is True
    assert sum(datos["contadores"].values()) == len(datos["estancias"])
    assert {e["id"] for e in datos["estancias"]} >= {CLAIRE}
    for filtro in ("hoy", "en_casa", "salidas"):
        filtrada = ver(cliente, "/api/estancias", filtro=filtro)
        exigir(ESTANCIAS, filtrada)
        assert {e["id"] for e in filtrada["estancias"]} <= {e["id"] for e in datos["estancias"]}
    rojas = ver(cliente, "/api/estancias", color="rojo")["estancias"]
    assert rojas and {e["semaforo"]["color"] for e in rojas} == {"rojo"}
    conflictos = ver(cliente, "/api/conflictos")
    exigir({"conflictos": [CONFLICTO]}, conflictos)
    assert conflictos["conflictos"] == datos["conflictos"]
    assert any(c["expediente_id"] == CLAIRE and c["nivel"] == "rojo" for c in conflictos["conflictos"])
    detalle = ver(cliente, f"/api/expedientes/{CLAIRE}")
    exigir({"registro": list, "tramites": dict, "sistemas": dict, "semaforo": dict, "conflictos": list}, {k: detalle[k] for k in (
        "registro", "tramites", "sistemas", "semaforo", "conflictos")})


def test_ocupacion_trae_el_mapa_por_fuente_y_las_peticiones(cliente):
    datos = ver(cliente, "/api/ocupacion", dias=14)
    exigir(OCUPACION, datos)
    assert datos["dias"] == 14 and len(datos["mapa"]["fechas"]) == 14
    for tipo, fila in datos["mapa"]["tipos"].items():
        exigir({"capacidad": int, "dias": [dict]}, fila)
        assert len(fila["dias"]) == 14
        for dia in fila["dias"]:
            assert set(dia["por_fuente"]) >= {"roomcloud", "ofihotel", "recepcion"}, tipo
    assert datos["peticiones"] and all(p["prioridad"]["tipo"] == "peticion" for p in datos["peticiones"])
    assert len(ver(cliente, "/api/ocupacion", dias=7)["mapa"]["fechas"]) == 7


def test_insignias_cuadran_con_los_contadores(cliente):
    datos = ver(cliente, "/api/insignias")
    exigir(INSIGNIAS, datos)
    assert datos["insignias"]["comunicaciones"] == ver(cliente, "/api/comunicaciones")["contadores"]["pendientes"]


@pytest.mark.parametrize("canal,contacto,asunto", [("whatsapp", "34600111222", None), ("correo", "prueba@example.com", "Habitación doble")])
def test_simular_devuelve_la_comunicacion_ya_contrastada(cliente, canal, contacto, asunto):
    antes = ver(cliente, "/api/comunicaciones")["contadores"]["pendientes"]
    cuerpo = {"canal": canal, "contacto": contacto, "nombre": "Prueba Demo",
              "texto": "Hola, ¿tenéis una doble libre del 3 al 5 de noviembre? Somos 2 personas."}
    if asunto:
        cuerpo["asunto"] = asunto
    r = cliente.post("/api/comunicaciones/simular", json=cuerpo)
    assert r.status_code == 200, r.text
    com = r.json()
    exigir(COMUNICACION, com)
    assert com["canal"] == canal and com["estado"] == "pendiente" and com["prioridad"]["id"] == canal
    assert com["de"]["contacto"] == contacto and com["respuesta"]["canal"] == canal
    assert com["peticion"] and com["contraste"]["veredicto"] in {"disponible", "ajustado", "en_competencia"}
    assert ver(cliente, "/api/comunicaciones")["contadores"]["pendientes"] == antes + 1
    assert ver(cliente, f"/api/comunicaciones/{com['id']}")["id"] == com["id"]


def test_simular_con_datos_incompletos_responde_error_de_validacion(cliente):
    assert cliente.post("/api/comunicaciones/simular", json={"canal": "telegram", "contacto": "x", "texto": "hola"}).status_code == 422
    assert cliente.post("/api/comunicaciones/simular", json={"canal": "correo"}).status_code == 422


def test_el_stream_emite_herramienta_bloque_texto_y_fin(cliente):
    eventos = eventos_sse(cliente, "¿Qué peticiones hay por confirmar?")
    nombres = [n for n, _ in eventos]
    assert set(nombres) <= EVENTOS and nombres[-1] == "fin" and "error" not in nombres
    assert {"herramienta", "bloque", "texto"} <= set(nombres)
    herramientas = [d for n, d in eventos if n == "herramienta"]
    for d in herramientas:
        exigir({"id": str, "nombre": str, "etiqueta": str, "estado": {"inicio", "fin"}}, d)
    assert [d["estado"] for d in herramientas][0] == "inicio" and [d["estado"] for d in herramientas][-1] == "fin"
    assert nombres.index("herramienta") < nombres.index("bloque") and nombres.index("bloque") < nombres.index("texto")
    bloques = [d for n, d in eventos if n == "bloque"]
    for b in bloques:
        comprobar_bloque(b)
    assert bloques[-1]["tipo"] == "sugerencias"
    textos = [d for n, d in eventos if n == "texto"]
    for d in textos:
        exigir({"delta": str}, d)
    fin = eventos[-1][1]
    exigir({"respuesta": str, "modo": {"real", "simulado"}, "propuestas": [str]}, fin)
    assert fin["respuesta"] == "".join(d["delta"] for d in textos)


def test_el_stream_y_el_chat_normal_dan_los_mismos_bloques(cliente):
    for pregunta in ("¿Qué conflictos hay?", "¿Qué prioridad tiene cada fuente?", "hola"):
        por_stream = [d for n, d in eventos_sse(cliente, pregunta) if n == "bloque"]
        assert por_stream == cliente.post("/api/chat", json={"mensaje": pregunta}).json()["bloques"], pregunta


def test_el_stream_acepta_historial_y_rechaza_el_mensaje_vacio(cliente):
    historial = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "Hola, ¿en qué puedo ayudarte?"}]
    assert eventos_sse(cliente, "¿Qué conflictos hay?", historial)[-1][0] == "fin"
    vacio = eventos_sse(cliente, "   ")
    assert [n for n, _ in vacio] == ["error"] and vacio[0][1]["mensaje"]


# ================================================================ almacén vacío

def test_con_el_almacen_vacio_las_pantallas_responden_con_su_forma(vacio):
    exigir(PRIORIDADES, ver(vacio, "/api/prioridades"))
    fuente = ver(vacio, "/api/fuente-unica")
    exigir(FUENTE_UNICA, fuente)
    assert fuente["cola"] == [] and fuente["totales"]["estancias"] == 0 and fuente["totales"]["conflictos"] == 0
    com = ver(vacio, "/api/comunicaciones")
    exigir(COMUNICACIONES, com)
    assert com["comunicaciones"] == [] and com["contadores"]["total"] == 0
    estancias = ver(vacio, "/api/estancias")
    exigir(ESTANCIAS, estancias)
    assert estancias["estancias"] == [] and sum(estancias["contadores"].values()) == 0
    assert ver(vacio, "/api/conflictos") == {"conflictos": []}
    ocupacion = ver(vacio, "/api/ocupacion", dias=14)
    exigir(OCUPACION, ocupacion)
    assert ocupacion["peticiones"] == [] and ocupacion["conflictos"] == []
    insignias = ver(vacio, "/api/insignias")
    exigir(INSIGNIAS, insignias)
    assert set(insignias["insignias"].values()) == {0}


def test_con_el_almacen_vacio_los_ids_desconocidos_dan_404_y_no_500(vacio):
    assert vacio.get("/api/comunicaciones/cm-0001").status_code == 404
    assert vacio.get("/api/expedientes/9-NO-EXISTE").status_code == 404
    assert vacio.post("/api/comunicaciones/cm-0001/descartar", json={"actor": "Flor"}).status_code == 404


def test_con_el_almacen_vacio_simular_funciona_y_contrasta_sin_datos(vacio):
    r = vacio.post("/api/comunicaciones/simular", json={"canal": "whatsapp", "contacto": "34600111222", "nombre": "Prueba",
                                                         "texto": "Hola, ¿tenéis una doble libre del 3 al 5 de noviembre?"})
    assert r.status_code == 200, r.text
    exigir(COMUNICACION, r.json())


def test_con_el_almacen_vacio_el_stream_termina_en_fin(vacio):
    for pregunta in ("¿Qué atender primero?", "¿Qué conflictos hay?", "¿Qué peticiones hay por confirmar?", "¿Qué prioridad tiene cada fuente?",
                     "¿Qué estancias tienen algo pendiente?", "¿Cómo está la ocupación?", "Enséñame cómo funciona la fuente única", "hola"):
        eventos = eventos_sse(vacio, pregunta)
        nombres = [n for n, _ in eventos]
        assert set(nombres) <= EVENTOS and nombres[-1] == "fin" and "error" not in nombres, pregunta
        bloques = [d for n, d in eventos if n == "bloque"]
        assert bloques and bloques[-1]["tipo"] == "sugerencias", pregunta
        for b in bloques:
            comprobar_bloque(b)
