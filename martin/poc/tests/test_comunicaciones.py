"""La pantalla central de la demo: comunicaciones contrastadas con las fuentes, escalera de prioridades y respuesta por el canal de origen."""
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import comunicaciones, main, prioridades  # noqa: E402
from app.store import Store  # noqa: E402

HOY = date(2026, 10, 24)


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", Store(tmp_path / "db.json"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = TestClient(main.app)
    assert c.post("/api/demo/semilla", params={"nivel": "completa"}).status_code == 200
    return c


def por_remitente(c, nombre):
    return next(x for x in c.get("/api/comunicaciones").json()["comunicaciones"] if x["de"]["nombre"] == nombre)


def test_entiende_fechas_personas_y_tipo_en_tres_idiomas():
    es = comunicaciones.analizar("¿Tenéis una doble libre del 28 al 30 de octubre? Somos 2 personas.", "", HOY)
    assert es["tipo"] == "peticion_habitacion" and es["idioma"] == "es"
    assert es["peticion"] == {"tipo_habitacion": "DBL-STD", "desde": "2026-10-28", "hasta": "2026-10-30", "noches": 2, "personas": 2, "habitaciones": 1}
    fr = comunicaciones.analizar("Bonjour, avez-vous une chambre double du 24 au 27 octobre pour 2 personnes ?", "", HOY)
    assert fr["idioma"] == "fr" and fr["peticion"]["desde"] == "2026-10-24" and fr["peticion"]["hasta"] == "2026-10-27"
    en = comunicaciones.analizar("Hello, do you have a single room available from 3 to 5 November?", "", HOY)
    assert en["idioma"] == "en" and en["peticion"]["tipo_habitacion"] == "SGL-STD" and en["peticion"]["desde"] == "2026-11-03"
    grupo = comunicaciones.analizar("Necesitamos 3 habitaciones dobles del 1 al 3 de noviembre", "", HOY)
    assert grupo["peticion"]["habitaciones"] == 3 and grupo["peticion"]["desde"] == "2026-11-01"
    noche = comunicaciones.analizar("Necesito una individual para esta noche", "", HOY)
    assert noche["peticion"]["desde"] == "2026-10-24" and noche["peticion"]["hasta"] == "2026-10-25"
    assert comunicaciones.analizar("¿A qué hora es el check-in?", "", HOY)["tipo"] == "pregunta"
    assert comunicaciones.analizar("Quiero cancelar mi reserva", "", HOY)["tipo"] == "cambio"


def test_la_escalera_de_prioridades_pone_roomcloud_por_encima_de_correo_y_whatsapp():
    assert [n["id"] for n in prioridades.NIVELES] == ["roomcloud", "ofihotel", "recepcion", "correo", "whatsapp"]
    assert [n["tipo"] for n in prioridades.NIVELES] == ["firme", "firme", "firme", "peticion", "peticion"]
    assert prioridades.nivel_de_origen("roomcloud")["nivel"] < prioridades.nivel_de_canal("correo")["nivel"] < prioridades.nivel_de_canal("whatsapp")["nivel"]
    assert prioridades.nivel_de_origen("walk-in")["id"] == "recepcion" and prioridades.nivel_de_origen("mensaje")["id"] == "recepcion"


def test_una_peticion_que_choca_con_reservas_firmes_no_esta_disponible_y_propone_alternativa(cliente):
    sophie = por_remitente(cliente, "Sophie Martin")
    c = sophie["contraste"]
    assert sophie["prioridad"]["nivel"] == 4 and c["veredicto"] == "no_disponible"
    assert {b["id"]: b["cantidad"] for b in c["bloqueada_por"]} == {"roomcloud": 2, "ofihotel": 1}
    assert c["alternativa"] == {"desde": "2026-10-25", "hasta": "2026-10-28", "noches": 3}
    assert "no queda ninguna habitación doble libre" in c["motivo"] and "más prioridad" in c["motivo"]
    assert sophie["respuesta"]["canal"] == "correo" and sophie["respuesta"]["texto"].startswith("Bonjour Sophie")
    assert "du 25 octobre au 28 octobre" in sophie["respuesta"]["texto"]


def test_entre_dos_peticiones_gana_el_correo_al_whatsapp_aunque_llegara_despues(cliente):
    pablo, marta = por_remitente(cliente, "Pablo Rey"), por_remitente(cliente, "Marta Souto")
    assert pablo["contraste"]["veredicto"] == "ajustado" and marta["contraste"]["veredicto"] == "en_competencia"
    assert marta["ts"] < pablo["ts"]  # Marta escribió antes, pero el correo tiene más nivel que WhatsApp
    retenida = marta["contraste"]["retenida_por"][0]
    assert retenida["de"] == "Pablo Rey" and retenida["nivel"] == 4 and "más prioridad" in marta["contraste"]["motivo"]
    assert "confirmando otra consulta" in marta["respuesta"]["texto"] and marta["alerta"] is None


def test_confirmar_reserva_responde_por_el_canal_de_origen_y_crea_una_reserva_de_nivel_3(cliente):
    lucia = por_remitente(cliente, "Lucía Fernández")
    assert lucia["contraste"]["veredicto"] == "disponible" and lucia["respuesta"]["canal"] == "whatsapp"
    r = cliente.post(f"/api/comunicaciones/{lucia['id']}/confirmar", json={"actor": "Flor"})
    assert r.status_code == 200 and r.json()["estado"] == "respondida" and r.json()["resultado"]["accion"] == "reservada"
    exp = main.store.db["expedientes"][r.json()["resultado"]["reserva_id"]]
    assert exp["origen"] == "mensaje" and prioridades.nivel_de_origen(exp["origen"])["nivel"] == 3
    assert (exp["checkin_prevista"], exp["checkout_prevista"]) == ("2026-10-28", "2026-10-30")
    enviados = [e for e in main.store.db["eventos"] if e["tipo"] == "mensaje_saliente_simulado" and e["datos"].get("comunicacion") == lucia["id"]]
    assert len(enviados) == 1 and enviados[0]["datos"]["aprobado_por"] == "Flor" and enviados[0]["remitente"] == "34655123123"
    assert cliente.post(f"/api/comunicaciones/{lucia['id']}/confirmar", json={}).status_code == 409
    assert por_remitente(cliente, "Lucía Fernández")["estado"] == "respondida"


def test_el_correo_responde_por_correo_con_asunto_y_firma(cliente):
    carlos = por_remitente(cliente, "Carlos Meijide")
    assert carlos["contraste"]["veredicto"] == "ajustado" and carlos["peticion"]["habitaciones"] == 3
    assert carlos["respuesta"]["asunto"] == "Re: Reserva para un evento de empresa" and carlos["respuesta"]["texto"].endswith("Recepción")
    assert cliente.post(f"/api/comunicaciones/{carlos['id']}/confirmar", json={"actor": "Flor"}).status_code == 200
    assert [m["para"] for m in main.store.db["outbox"]] == ["carlos.meijide@meijide-consulting.example"]


def test_si_entra_una_reserva_de_roomcloud_la_peticion_deja_de_estar_disponible_y_se_avisa(cliente):
    pablo = por_remitente(cliente, "Pablo Rey")
    assert pablo["contraste"]["veredicto"] == "ajustado" and pablo["alerta"] is None
    assert cliente.post("/api/demo/reserva-roomcloud", json={"tipo": "SGL-STD", "nombre": "Reserva de Booking"}).status_code == 200
    despues = por_remitente(cliente, "Pablo Rey")
    assert despues["contraste"]["veredicto"] == "no_disponible" and "Ha dejado de estar disponible" in despues["alerta"]["texto"]
    assert [(b["id"], b["cantidad"]) for b in despues["contraste"]["bloqueada_por"]] == [("roomcloud", 2)]


def test_confirmar_una_peticion_en_competencia_solo_la_deja_en_espera(cliente):
    marta = por_remitente(cliente, "Marta Souto")
    r = cliente.post(f"/api/comunicaciones/{marta['id']}/confirmar", json={"actor": "Flor"}).json()
    assert r["estado"] == "en_espera" and r["resultado"]["accion"] == "en_espera" and r["resultado"]["reserva_id"] is None


def test_al_confirmar_a_pablo_la_peticion_de_marta_pasa_a_no_disponible(cliente):
    pablo, marta = por_remitente(cliente, "Pablo Rey"), por_remitente(cliente, "Marta Souto")
    assert cliente.post(f"/api/comunicaciones/{pablo['id']}/confirmar", json={"actor": "Flor"}).json()["resultado"]["accion"] == "reservada"
    despues = por_remitente(cliente, "Marta Souto")
    assert despues["id"] == marta["id"] and despues["contraste"]["veredicto"] == "no_disponible"
    assert "lo sentimos" in despues["respuesta"]["texto"]


def test_simular_un_mensaje_en_directo_lo_entiende_y_lo_contrasta(cliente):
    r = cliente.post("/api/comunicaciones/simular", json={"canal": "whatsapp", "nombre": "Iria", "contacto": "+34 677 000 111",
                                                          "texto": "¡Hola! ¿Os queda una doble del 5 al 7 de noviembre? Somos dos"})
    assert r.status_code == 200
    com = r.json()
    assert com["peticion"]["desde"] == "2026-11-05" and com["peticion"]["personas"] == 2 and com["de"]["contacto"] == "34677000111"
    assert com["contraste"]["veredicto"] == "disponible" and com["estado"] == "pendiente"
    assert cliente.post("/api/comunicaciones/simular", json={"canal": "correo", "contacto": "no-es-un-correo", "texto": "hola"}).status_code == 422
    assert cliente.post("/api/comunicaciones/simular", json={"canal": "telegram", "contacto": "x", "texto": "hola"}).status_code == 422


def test_la_fuente_unica_ordena_la_cola_por_prioridad_de_la_fuente(cliente):
    datos = cliente.get("/api/fuente-unica").json()
    assert [f["id"] for f in datos["fuentes"]] == ["roomcloud", "ofihotel", "recepcion", "correo", "whatsapp", "ses"]
    niveles = [i["prioridad"]["nivel"] for i in datos["cola"]]
    assert niveles == sorted(niveles) and niveles[0] == 1 and niveles[-1] == 5
    assert datos["totales"]["comunicaciones_pendientes"] == 6 and datos["totales"]["conflictos"] == 2
    assert len(datos["prioridades"]["reglas"]) == 3 and len(datos["prioridades"]["niveles"]) == 5


def test_los_desajustes_entre_roomcloud_y_ofihotel_salen_como_conflictos(cliente):
    tipos = {c["tipo"] for c in cliente.get("/api/conflictos").json()["conflictos"]}
    assert {"fechas_distintas", "cancelada_activa_en_ofihotel"} <= tipos
    estancias = {e["huesped"]: e for e in cliente.get("/api/estancias").json()["estancias"]}
    assert estancias["Claire Dubois"]["semaforo"]["color"] == "rojo" and estancias["Claire Dubois"]["prioridad"]["nivel"] == 1
    assert "RoomCloud dice del 24/10 al 27/10" in estancias["Claire Dubois"]["semaforo"]["motivo"]
    assert estancias["Luis Otero"]["semaforo"]["color"] == "gris"
