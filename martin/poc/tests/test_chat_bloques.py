"""Constructores de bloques del chat sobre la semilla `completa` (CONTRATO-CORE.md apartados 4.1 y 4.2)."""
import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import chat_bloques as b  # noqa: E402
from app import chat_procesos, main  # noqa: E402
from app.hub import ErrorNegocio  # noqa: E402
from app.store import Store  # noqa: E402

CLAIRE = "2-EX-7730021"
CLAVES = {
    "resumen_kpi": {"titulo", "items"},
    "tarjeta_reserva": {"id", "titulo", "subtitulo", "chips", "campos", "prioridad", "semaforo", "sistemas", "acciones"},
    "lista_estancias": {"titulo", "contadores", "estancias"},
    "comunicacion": {"comunicacion", "acciones"},
    "lista_comunicaciones": {"titulo", "comunicaciones"},
    "fuentes": {"titulo", "fuentes", "prioridades", "acciones"},
    "prioridades": {"titulo", "prioridades", "resaltar"},
    "cola": {"titulo", "items"},
    "conflictos": {"titulo", "conflictos"},
    "navegacion": {"titulo", "items"},
    "proceso": {"id", "titulo", "resumen", "pasos", "acciones"},
    "tabla_ocupacion": {"fechas", "filas"},
    "propuesta": {"id", "texto", "plantilla", "destino", "origen", "destinatario", "estado", "acciones"},
    "formulario": {"id", "titulo", "campos", "envio"},
    "aviso": {"tono", "titulo", "texto"},
    "sugerencias": {"items"},
}
FUENTES_VALIDAS = {"roomcloud", "ofihotel", "recepcion", "correo", "whatsapp", "ses", "sistema"}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert TestClient(main.app).post("/api/demo/semilla", params={"nivel": "completa"}).status_code == 200
    return main.store


def forma(bloque: dict) -> None:
    faltan = CLAVES[bloque["tipo"]] - bloque.keys()
    assert not faltan, f"{bloque['tipo']} no lleva {faltan}"
    for accion in b.acciones_de(bloque):
        assert accion["tipo"] in b.ACCIONES, accion
        assert accion.get("etiqueta") or accion["tipo"] == "preguntar"


def todos_los_bloques(store) -> list[dict]:
    return [b.bloque_resumen_kpi(store), b.bloque_lista_estancias(store), b.bloque_lista_estancias(store, "hoy"),
            b.bloque_lista_estancias(store, "todas", "rojo"), b.bloque_tarjeta_estancia(store, CLAIRE),
            b.bloque_lista_comunicaciones(store), b.bloque_lista_comunicaciones(store, "pendientes", "whatsapp"),
            b.bloque_comunicacion(store, "cm-0001"), b.bloque_fuentes(store), b.bloque_prioridades(), b.bloque_prioridades("correo"),
            b.bloque_cola(store), b.bloque_conflictos(store), b.bloque_tabla_ocupacion(store, 7),
            b.bloque_propuesta(store, "pr-0005"), b.bloque_navegacion(store, list(b.DESTINOS)), b.bloque_formulario_walkin(),
            b.bloque_aviso("info", "Título", "Texto"), b.bloque_sugerencias(["a", "b", "c", "d"])] + [b.bloque_proceso(p) for p in b.PROCESOS]


def test_cada_constructor_devuelve_la_forma_del_contrato(store):
    for bloque in todos_los_bloques(store):
        forma(bloque)


def test_resumen_kpi_trae_los_cinco_indicadores_del_dia(store):
    items = {i["etiqueta"]: i for i in b.bloque_resumen_kpi(store)["items"]}
    assert list(items) == ["Llegadas", "En casa", "Peticiones por confirmar", "Conflictos", "Partes pendientes"]
    assert items["Peticiones por confirmar"]["valor"] == "6"
    assert all(i["tono"] in b.TONOS for i in items.values())


def test_lista_de_estancias_filtra_y_cuenta_los_colores(store):
    lista = b.bloque_lista_estancias(store)
    assert lista["titulo"] == "Estancias pendientes"
    assert all(e["semaforo"]["color"] != "verde" for e in lista["estancias"])
    assert lista["contadores"]["rojo"] == 1
    rojas = b.bloque_lista_estancias(store, "todas", "rojo")["estancias"]
    assert [e["id"] for e in rojas] == [CLAIRE]
    assert b.bloque_lista_estancias(store, "filtro-raro", "color-raro")["estancias"]


def test_tarjeta_de_estancia_lleva_semaforo_sistemas_y_accion(store):
    t = b.bloque_tarjeta_estancia(store, CLAIRE)
    assert t["titulo"] == "Claire Dubois" and t["semaforo"]["color"] == "rojo"
    assert set(t["sistemas"]) == {"roomcloud", "ofihotel", "documentacion"}
    assert t["acciones"] == [{"tipo": "abrir_estancia", "etiqueta": "Abrir", "id": CLAIRE}]
    with pytest.raises(KeyError):
        b.bloque_tarjeta_estancia(store, "no-existe")


def test_comunicacion_abierta_tiene_tres_acciones_y_una_cerrada_solo_abrir(store):
    abierta = b.bloque_comunicacion(store, "cm-0001")
    assert [a["tipo"] for a in abierta["acciones"]] == ["confirmar_comunicacion", "descartar_comunicacion", "abrir_comunicacion"]
    assert abierta["acciones"][0]["etiqueta"] == "Confirmar y enviar por correo"
    assert abierta["comunicacion"]["contraste"]["veredicto"] and abierta["comunicacion"]["respuesta"]["texto"]
    assert b.bloque_comunicacion(store, "cm-0005")["acciones"][0]["etiqueta"] == "Confirmar y enviar por WhatsApp"
    comunicaciones_descartar = abierta["comunicacion"]["id"]
    from app import comunicaciones
    comunicaciones.descartar(store, comunicaciones_descartar)
    assert [a["tipo"] for a in b.bloque_comunicacion(store, comunicaciones_descartar)["acciones"]] == ["abrir_comunicacion"]
    with pytest.raises(ErrorNegocio):
        b.bloque_comunicacion(store, "cm-9999")


def test_lista_de_comunicaciones_y_filtro_por_canal(store):
    todas = b.bloque_lista_comunicaciones(store)["comunicaciones"]
    wa = b.bloque_lista_comunicaciones(store, "pendientes", "whatsapp")["comunicaciones"]
    assert len(todas) == 6 and len(wa) == 3 and all(c["canal"] == "whatsapp" for c in wa)


def test_fuentes_prioridades_cola_y_conflictos(store):
    fuentes = b.bloque_fuentes(store)
    assert [f["id"] for f in fuentes["fuentes"]] == ["roomcloud", "ofihotel", "recepcion", "correo", "whatsapp", "ses"]
    assert len(fuentes["prioridades"]["niveles"]) == 5 and fuentes["acciones"][0]["fuente"] == "roomcloud"
    assert b.bloque_prioridades("correo")["resaltar"] == "correo" and b.bloque_prioridades("nada")["resaltar"] is None
    assert b.bloque_cola(store)["items"][0]["prioridad"]["nivel"] == 1
    conflictos = b.bloque_conflictos(store)["conflictos"]
    assert conflictos and {"id", "tipo", "nivel", "texto", "expediente_id", "sistemas"} <= conflictos[0].keys()


def test_tabla_ocupacion_y_propuesta(store):
    tabla = b.bloque_tabla_ocupacion(store, 3)
    assert len(tabla["fechas"]) == 3 and tabla["filas"][0]["celdas"][0]["fecha"] == tabla["fechas"][0]
    pendiente = b.bloque_propuesta(store, "pr-0005")
    assert [a["tipo"] for a in pendiente["acciones"]] == ["aprobar_propuesta", "rechazar_propuesta"]
    with pytest.raises(KeyError):
        b.bloque_propuesta(store, "pr-9999")


def test_navegacion_con_los_cinco_destinos_e_insignias(store):
    nav = b.bloque_navegacion(store, ["fuente", "comunicaciones", "estancias", "ocupacion", "asistente", "inexistente"])
    assert [i["seccion"] for i in nav["items"]] == ["fuente", "comunicaciones", "estancias", "ocupacion", "asistente"]
    por = {i["seccion"]: i for i in nav["items"]}
    assert por["comunicaciones"]["insignia"] == 6 and por["comunicaciones"]["icono"] == "inbox"
    assert all(i["descripcion"] and i["icono"] for i in nav["items"])
    assert "insignia" not in por["ocupacion"]  # un número de conflictos sin explicación confunde en la tarjeta


def test_los_seis_procesos_existen_con_pasos_y_fuente_valida():
    assert set(b.PROCESOS) == {"peticion_mensaje", "reserva_canal", "checkin_parte", "overbooking_cierre", "fuente_unica", "prioridades"}
    for pid in b.PROCESOS:
        p = b.bloque_proceso(pid)
        assert p["id"] == pid and 3 <= len(p["pasos"]) <= 6 and p["acciones"]
        assert len({s["id"] for s in p["pasos"]}) == len(p["pasos"])
        for paso in p["pasos"]:
            assert paso["fuente"] in FUENTES_VALIDAS and paso["titulo"] and paso["detalle"]
    with pytest.raises(KeyError):
        b.bloque_proceso("no_existe")
    b.bloque_proceso("fuente_unica")["pasos"].clear()  # es una copia
    assert b.bloque_proceso("fuente_unica")["pasos"]


def test_los_textos_de_los_procesos_cumplen_las_reglas_de_estilo():
    texto = json.dumps([chat_procesos.proceso(p) for p in b.PROCESOS], ensure_ascii=False)
    assert "—" not in texto and "OCR" not in texto.replace("sin OCR", "").replace("con OCR", "")
    assert not re.search(r"\bno es\b[^.]{0,60}\bsino\b", texto, re.I)


def test_bloques_muestra_cubre_todos_los_tipos_nuevos():
    muestra = b.bloques_muestra()
    assert {m["tipo"] for m in muestra} == set(CLAVES)
    for bloque in muestra:
        forma(bloque)
    muestra[0]["titulo"] = "cambiado"
    assert b.bloques_muestra()[0]["titulo"] != "cambiado"


def test_bloques_muestra_no_lee_el_almacen(monkeypatch):
    class Roto:
        def __getattr__(self, nombre):
            raise AssertionError("bloques_muestra no puede leer el almacén")

    monkeypatch.setattr(main, "store", Roto())
    assert len(b.bloques_muestra()) == len(CLAVES)


def test_ningun_bloque_contiene_html_ni_claves_de_api(store):
    candidatos = todos_los_bloques(store) + b.bloques_muestra() + list(chat_procesos.PROCESOS)
    for tipo in ("sugerencias_bienvenida",):
        candidatos.append(b.sugerencias_bienvenida())
    texto = json.dumps(candidatos, ensure_ascii=False)
    assert not re.search(r"</?[a-zA-Z][^>]*>", texto)
    assert not re.search(r"sk-[A-Za-z0-9_-]{8,}|api[_-]?key|Bearer ", texto, re.I)


@pytest.mark.parametrize("mensaje, tipo", [
    ("comunicaciones", "lista_comunicaciones"), ("fuentes", "fuentes"), ("prioridades", "prioridades"), ("conflictos", "conflictos"),
    ("ocupación", "tabla_ocupacion"), ("llegadas de hoy", "lista_estancias"), ("cómo funciona el check-in", "proceso"),
    ("quiero añadir un walk-in", "formulario"), ("¿qué atender primero?", "cola"), ("enséñame cómo entra una petición por WhatsApp", "proceso"),
    ("¿qué propuestas hay pendientes de aprobar?", "propuesta"), ("qué le pasa a Claire", "tarjeta_reserva"),
    ("llévame a la ocupación", "navegacion"),
])
def test_para_mensaje_elige_los_bloques_por_palabras_clave(store, mensaje, tipo):
    bloques = b.para_mensaje(store, mensaje)
    assert tipo in [x["tipo"] for x in bloques], [x["tipo"] for x in bloques]
    assert bloques[-1]["tipo"] == "sugerencias"
    for bloque in bloques:
        forma(bloque)


def test_el_proceso_correcto_para_cada_pregunta(store):
    casos = {"cómo funciona el check-in": "checkin_parte", "enséñame cómo se evita un overbooking": "overbooking_cierre",
             "qué pasa cuando entra una reserva de Booking": "reserva_canal", "cómo funciona la fuente única": "fuente_unica",
             "enséñame quién gana cuando dos fuentes compiten": "prioridades", "enséñame cómo entra una petición por WhatsApp": "peticion_mensaje"}
    for mensaje, esperado in casos.items():
        assert b.para_mensaje(store, mensaje)[0]["id"] == esperado, mensaje


def test_una_frase_sin_sentido_recibe_la_respuesta_por_defecto_con_sugerencias(store):
    bloques = b.para_mensaje(store, "asdf qwerty zzz")
    assert [x["tipo"] for x in bloques] == ["aviso", "sugerencias"]
    assert bloques[1]["items"] and len(bloques[1]["items"]) <= 3


def test_sugerencias_de_bienvenida_son_cuatro_preguntas():
    s = b.sugerencias_bienvenida()
    assert len(s["preguntas"]) == 4 and "Enséñame cómo entra una petición por WhatsApp" in s["preguntas"]
    assert "categorias" not in s and "flujos" not in s
