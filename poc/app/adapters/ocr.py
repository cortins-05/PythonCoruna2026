"""Lectura de documentos de identidad con Claude vision.

Sin `ANTHROPIC_API_KEY` devuelve el fixture `ocr_dni_muestra.json` y lo marca como simulado.
El camino en vivo no se ha probado con la API real, porque al montar la demo no había clave.
La imagen solo se usa para la extracción y no se guarda en ningún sitio.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "ocr_dni_muestra.json"
MODELO = os.environ.get("OCR_MODEL", "claude-sonnet-5-5")
CAMPOS = ["nombre", "apellido1", "apellido2", "sexo", "fecha_nacimiento", "nacionalidad",
          "tipo_documento", "numero_documento", "numero_soporte", "direccion", "localidad",
          "codigo_postal", "pais"]

PROMPT = f"""Eres un lector de documentos de identidad (DNI, NIE o pasaporte).
Devuelve SOLO un JSON con dos objetos: "campos" y "confianza" (un número de 0 a 1 por campo).
Campos: {", ".join(CAMPOS)}.
Formatos: fecha_nacimiento AAAA-MM-DD, sexo H o M, nacionalidad y pais en ISO 3166-1 alfa-3,
tipo_documento NIF, NIE o PAS. Si un campo no se lee o no aparece, pon "" y confianza 0.
No inventes nada y no completes campos que no veas en la imagen."""


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def extraer_json(texto: str) -> dict:
    """Saca el primer objeto JSON de la respuesta, por si el modelo añade texto alrededor."""
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin < inicio:
        raise ValueError("La respuesta no contiene JSON")
    datos = json.loads(texto[inicio:fin + 1])
    campos = {k: str(datos.get("campos", {}).get(k, "") or "") for k in CAMPOS}
    confianza = {k: float(datos.get("confianza", {}).get(k, 0) or 0) for k in CAMPOS}
    return {"campos": campos, "confianza": confianza}


def leer_documento(imagen_b64: str | None, tipo_mime: str = "image/png") -> dict:
    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave or not imagen_b64:
        return {**_fixture(), "modo": "simulado",
                "aviso": "OCR simulado con un documento de muestra" if not clave else "Sin imagen: se usa la muestra"}
    cuerpo = {
        "model": MODELO,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": tipo_mime, "data": imagen_b64}},
            {"type": "text", "text": PROMPT},
        ]}],
    }
    peticion = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            texto = json.loads(respuesta.read())["content"][0]["text"]
        return {**extraer_json(texto), "modo": "en vivo", "aviso": ""}
    except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError) as error:
        return {**_fixture(), "modo": "simulado", "aviso": f"Falló la lectura en vivo ({error}); se usa la muestra"}
