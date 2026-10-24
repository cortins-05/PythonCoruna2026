import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import chat, main  # noqa: E402
from app.store import Store  # noqa: E402

ANA = "1-BK-4471920"


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = TestClient(main.app)
    c.post("/api/sync/roomcloud")
    return c


def test_chat_sin_clave_responde_con_los_datos_vivos_y_lo_dice(cliente):
    r = cliente.post("/api/chat", json={"mensaje": "¿Qué llegadas hay hoy?"}).json()
    assert "Ana Pereira" in r["respuesta"] and "sin LLM" in r["modo"]
    ocupacion = cliente.post("/api/chat", json={"mensaje": "¿Cómo está la ocupación?"}).json()["respuesta"]
    assert "DBL-STD: 2 de 3" in ocupacion


def test_chat_ve_los_mensajes_pero_solo_puede_proponer(cliente):
    cliente.post("/api/whatsapp/simular", json={"wa_id": "34600111222", "nombre": "Ana", "texto": "¿A qué hora es el check-in?"})
    texto = cliente.post("/api/chat", json={"mensaje": "¿Qué mensajes han llegado por whatsapp?"}).json()["respuesta"]
    assert "check-in" in texto


def test_proponer_accion_crea_una_propuesta_pendiente_y_no_ejecuta_nada(cliente):
    store = main.store
    r = chat.ejecutar(store, "proponer_accion", {"plantilla": "pedir_documentos", "slots": {"nombre": "Ana"}, "expediente_id": ANA})
    assert r["estado"] == "pendiente de aprobación"
    propuesta = next(p for p in store.db["propuestas"] if p["id"] == r["propuesta"])
    assert propuesta["estado"] == "pendiente" and propuesta["destinatario"] == "34600111222" and propuesta["origen"] == "chat"
    assert not any(e["tipo"] == "mensaje_saliente_simulado" for e in store.db["eventos"])


def test_proponer_accion_rechaza_variables_peligrosas_y_plantillas_inventadas(cliente):
    store = main.store
    antes = len(store.db["propuestas"])
    for args in [
        {"plantilla": "pedir_documentos", "slots": {"nombre": "Ana http://malo.example"}, "expediente_id": ANA},
        {"plantilla": "borrar_reserva", "slots": {}, "expediente_id": ANA},
        {"plantilla": "pedir_documentos", "slots": {"nombre": "Ana"}},  # sin expediente no hay destinatario
    ]:
        assert "error" in chat.ejecutar(store, "proponer_accion", args)
    assert len(store.db["propuestas"]) == antes


def test_el_asistente_no_tiene_herramientas_de_escritura_salvo_proponer():
    nombres = {h["name"] for h in chat.HERRAMIENTAS}
    assert nombres == {"reservas_hoy", "ocupacion", "partes_pendientes", "mensajes_recientes", "proponer_accion"}
