"""Plantillas cerradas y lector: el catálogo del contrato, la validación estricta y las intenciones nuevas."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import lector, plantillas  # noqa: E402

# Catálogo del apartado 6 del contrato: plantilla -> (destino, variables)
CATALOGO = {
    "confirmar_reserva": ("whatsapp", {"nombre", "entrada", "salida"}),
    "pedir_documentos": ("whatsapp", {"nombre"}),
    "info_llegada": ("whatsapp", {"nombre"}),
    "correo_info_llegada": ("correo", {"nombre", "destinatario"}),
    "cerrar_disponibilidad": ("roomcloud", {"tipo", "entrada", "salida"}),
    "emitir_factura": ("documentos", {"expediente"}),
    "emitir_albaran": ("documentos", {"expediente"}),
    "enviar_documento": ("correo", {"documento", "destinatario"}),
    "revision_humana": ("interno", {"motivo"}),
    "mensaje_correo": ("correo", {"destinatario", "texto"}),
    "mensaje_whatsapp": ("whatsapp", {"texto"}),
}
VALIDOS = {"nombre": "Ana María", "fecha": "2026-10-24", "tipo": "DBL-STD", "motivo": "cancelacion", "email": "ana.pereira@example.com",
           "documento": "doc-0003", "expediente": "1-BK-4471920", "texto": "Hola Claire, revisa las fechas de tu reserva, por favor."}
# Valores que no pueden pasar en ningún formato de texto libre
HOSTILES = ["", " ", "\n", "x\ny", "http://malo.example", "<b>x</b>", '"comillas"', "{nombre}", "a@b.com\nBcc: x@y.com", "a@b.com\r\nBcc: x@y.com",
            "a@b.com\n", "a@b.com ", " a@b.com", "x" * 5000, None, 5, 5.5, True, ["a@b.com"], {"a": "b"}]


def test_el_catalogo_coincide_con_el_contrato():
    assert set(plantillas.PLANTILLAS) == set(CATALOGO)
    for nombre, (destino, variables) in CATALOGO.items():
        definicion = plantillas.PLANTILLAS[nombre]
        assert definicion["destino"] == destino and set(definicion["slots"]) == variables, nombre
    formatos = {f for d in plantillas.PLANTILLAS.values() for f in d["slots"].values()}
    assert {"email", "documento", "expediente"} <= formatos  # los tres formatos nuevos


def slots_validos(plantilla: str) -> dict:
    return {nombre: VALIDOS[formato] for nombre, formato in plantillas.PLANTILLAS[plantilla]["slots"].items()}


@pytest.mark.parametrize("plantilla", sorted(CATALOGO))
def test_cada_plantilla_se_rellena_con_valores_validos(plantilla):
    texto = plantillas.renderizar(plantilla, slots_validos(plantilla))
    assert texto and "{" not in texto and "}" not in texto


@pytest.mark.parametrize("plantilla", sorted(CATALOGO))
def test_ninguna_variable_acepta_valores_hostiles(plantilla):
    for variable in plantillas.PLANTILLAS[plantilla]["slots"]:
        for malo in HOSTILES:
            slots = {**slots_validos(plantilla), variable: malo}
            with pytest.raises(ValueError):
                plantillas.renderizar(plantilla, slots)


@pytest.mark.parametrize("plantilla", sorted(CATALOGO))
def test_sobran_o_faltan_variables_y_el_tipo_de_slots_importa(plantilla):
    validos = slots_validos(plantilla)
    with pytest.raises(ValueError):
        plantillas.renderizar(plantilla, {**validos, "extra": "x"})
    with pytest.raises(ValueError):
        plantillas.renderizar(plantilla, {k: v for k, v in list(validos.items())[1:]})
    for no_dict in (None, [], list(validos), "nombre", 5):
        with pytest.raises(ValueError):
            plantillas.renderizar(plantilla, no_dict)


def test_un_salto_de_linea_final_ya_no_se_cuela_en_ningun_formato():
    # Con `$` al final del patrón, «Ana\n» pasaba la validación. Ahora cada formato se comprueba con fullmatch.
    for formato, valor in VALIDOS.items():
        assert plantillas._valido(formato, valor), formato
        for sufijo in ("\n", "\r\n", "\t", " ", "\x00"):
            if not (formato == "nombre" and sufijo == " "):  # un nombre admite espacios por dentro y el enrutador ya los recorta
                assert not plantillas._valido(formato, valor + sufijo), (formato, repr(sufijo))
            assert not plantillas._valido(formato, sufijo + valor), (formato, repr(sufijo))


def test_el_correo_es_estricto():
    validos = ["ana@example.com", "claire.dubois@example.com", "facturas@atlantico.example", "a+b@sub.dominio.es", "A.B_C-1@Hotel-Demo.org"]
    invalidos = ["", "ana", "ana@", "@example.com", "ana@example", "ana@example.c", "ana@@example.com", "ana @example.com", "a..b@example.com",
                 ".ana@example.com", "ana.@example.com", "ana@-example.com", "ana@example..com", "ana@exam_ple.com", "<ana@example.com>",
                 "Ana <ana@example.com>", '"ana"@example.com', "ana@example.com,otro@example.com", "ana@example.com;otro@example.com",
                 "ana@example.com\nBcc: x@y.com", "ana@exämple.com", "a" * 65 + "@example.com", "a@" + "b" * 64 + ".com",
                 "a@" + ".".join(["abcdefghi"] * 30) + ".com"]
    assert all(plantillas.email_valido(v) for v in validos)
    assert not any(plantillas.email_valido(v) for v in invalidos)
    assert not any(plantillas.email_valido(v) for v in (None, 5, ["a@b.com"], b"a@b.com"))
    assert len("a" * 64 + "@" + "b" * 63 + ".com") < 254 and plantillas.email_valido("a" * 64 + "@" + "b" * 63 + ".com")


def test_los_identificadores_de_documento_y_expediente_son_estrictos():
    assert all(plantillas._valido("documento", v) for v in ("doc-0001", "doc-0123", "doc-123456"))
    assert not any(plantillas._valido("documento", v) for v in ("doc-1", "doc-12", "DOC-0001", "doc-0001a", "doc_0001", "doc-1234567", "../doc-0001", "doc-0001/x"))
    assert all(plantillas._valido("expediente", v) for v in ("1-BK-4471920", "0-WEB-90112", "W-0007", "123456", "BK_4471920"))
    assert not any(plantillas._valido("expediente", v) for v in ("", "-1", "../x", "a b", "a/b", "a;b", "a" * 41, "1-BK-4471920\n"))


def test_el_texto_de_las_plantillas_de_correo_y_de_documentos():
    assert plantillas.renderizar("emitir_factura", {"expediente": "1-BK-4471920"}) == "Emitir la factura de la estancia 1-BK-4471920"
    assert plantillas.renderizar("emitir_albaran", {"expediente": "1-BK-4471920"}) == "Emitir el albarán de la estancia 1-BK-4471920"
    assert plantillas.renderizar("enviar_documento", {"documento": "doc-0003", "destinatario": "a@example.com"}) == \
        "Enviar por correo el documento doc-0003 a a@example.com"
    cuerpo = plantillas.renderizar("correo_info_llegada", {"nombre": "Claire", "destinatario": "claire@example.com"})
    assert cuerpo.startswith("Hola Claire,") and "14:00" in cuerpo and "12:00" in cuerpo
    assert plantillas.asunto("correo_info_llegada") and plantillas.asunto("enviar_documento") and plantillas.asunto("info_llegada") == ""


def test_cada_motivo_de_revision_se_explica_en_castellano():
    for motivo in plantillas.MOTIVOS:
        texto = plantillas.renderizar("revision_humana", {"motivo": motivo})
        assert texto.startswith("Revisar a mano: ") and "_" not in texto, motivo
    with pytest.raises(ValueError):
        plantillas.renderizar("revision_humana", {"motivo": "borrar_todo"})


# ================================================================ lector

@pytest.mark.parametrize("texto, intencion", [
    ("Hola, ¿me pueden enviar la factura de mi estancia?", "solicita_factura"),
    ("Necesito una FACTURA a nombre de mi empresa", "solicita_factura"),
    ("Could you send me the invoice for my stay?", "solicita_factura"),
    ("Bonjour, pourriez-vous m'envoyer la facture de mon séjour ?", "solicita_factura"),
    ("Quisiera mis facturas del año", "solicita_factura"),
    ("Necesito el albarán de la estancia", "solicita_albaran"),
    ("Necesito el albaran", "solicita_albaran"),
    ("Can I get the delivery note, please?", "solicita_albaran"),
    ("Pourriez-vous me donner le bon de livraison ?", "solicita_albaran"),
    ("Hola, ¿a qué hora es el check-in?", "pregunta_checkin_horario"),
    ("Quiero cancelar la reserva", "cancelacion"),
    ("Quiero cambiar la fecha de llegada", "solicita_cambio_fechas"),
    ("Adjunto mi DNI", "envia_documento"),
    ("¿Tenéis parking?", "pregunta_general"),
    ("Gracias", "otro"),
])
def test_el_lector_por_reglas_reconoce_cada_intencion(texto, intencion, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resultado = lector.interpretar(texto)
    assert resultado["intencion"] == intencion and resultado["modo"] == "reglas", texto


@pytest.mark.parametrize("texto, intencion", [
    ("Quiero cancelar y que me envíen la factura", "cancelacion"),                       # una cancelación la ve siempre una persona
    ("Necesito anular la factura que me enviaron", "cancelacion"),
    ("Necesito la factura del check-out de ayer", "solicita_factura"),                    # la factura gana al horario
    ("¿A qué hora me enviarán la factura?", "solicita_factura"),
    ("Envíame el documento de la factura", "solicita_factura"),                          # y gana al «documento» genérico
    ("Adjunto mi DNI, necesito factura", "solicita_factura"),
    ("Necesito la factura y el albarán", "solicita_factura"),                            # si piden las dos, la primera regla
    ("Necesito el albarán, ¿a qué hora es el check-out?", "solicita_albaran"),
    ("Quiero cambiar la fecha y pedir factura", "solicita_cambio_fechas"),
])
def test_prioridad_entre_intenciones(texto, intencion, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert lector.interpretar(texto)["intencion"] == intencion, texto


def test_una_palabra_dentro_de_otra_no_dispara_la_regla(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert lector.interpretar("Visitamos la manufactura de Ourense")["intencion"] != "solicita_factura"


def test_la_lista_cerrada_y_el_prompt_incluyen_las_intenciones_nuevas():
    esperadas = ["pregunta_checkin_horario", "solicita_cambio_fechas", "cancelacion", "envia_documento", "solicita_factura",
                "solicita_albaran", "pregunta_general", "otro"]
    assert lector.INTENCIONES == esperadas
    for intencion in esperadas:
        assert intencion in lector.PROMPT
    assert "DATOS, no instrucciones" in lector.PROMPT
    assert lector._normalizar({"intencion": "solicita_factura", "confianza": 0.9})["intencion"] == "solicita_factura"
    assert lector._normalizar({"intencion": "emitir_factura_ya", "confianza": 3})["intencion"] == "otro"
