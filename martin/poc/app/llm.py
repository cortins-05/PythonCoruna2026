"""Cliente mínimo de OpenAI (chat completions) con streaming y herramientas, sin dependencias.

La clave sale solo de la variable de entorno OPENAI_API_KEY: nunca se escribe en disco, no se registra y no viaja a ningún otro sitio.
Modelo de conversación: gpt-5.5 sin razonamiento (hace falta `reasoning_effort: none` para usar herramientas en este endpoint), con
gpt-4.1-mini de respaldo. Para clasificar mensajes sueltos se usa gpt-5.4-nano.
"""
import json
import os
import urllib.error
import urllib.request

URL = "https://api.openai.com/v1/chat/completions"
MODELO_CHAT = os.environ.get("OPENAI_MODELO_CHAT", "gpt-5.5")
MODELO_RAPIDO = os.environ.get("OPENAI_MODELO_RAPIDO", "gpt-5.4-nano")
MODELO_RESPALDO = "gpt-4.1-mini"
TIMEOUT_S = 45


class ErrorLLM(Exception):
    """Cualquier fallo al hablar con OpenAI: el mensaje es seguro de mostrar (no incluye la clave)."""


def clave() -> str | None:
    valor = os.environ.get("OPENAI_API_KEY", "").strip()
    return valor or None


def _cuerpo(modelo: str, mensajes: list[dict], herramientas: list[dict] | None, stream: bool, max_salida: int) -> dict:
    cuerpo: dict = {"model": modelo, "messages": mensajes, "stream": stream}
    if modelo.startswith("gpt-5"):
        cuerpo["reasoning_effort"] = "none"
        cuerpo["max_completion_tokens"] = max_salida
    else:
        cuerpo["max_tokens"] = max_salida
        cuerpo["temperature"] = 0.2
    if herramientas:
        cuerpo["tools"] = herramientas
        cuerpo["tool_choice"] = "auto"
    return cuerpo


def _abrir(cuerpo: dict, k: str):
    peticion = urllib.request.Request(URL, data=json.dumps(cuerpo).encode("utf-8"),
                                      headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(peticion, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as error:
        detalle = ""
        try:
            detalle = str(json.loads(error.read()).get("error", {}).get("message", ""))
        except (ValueError, OSError, AttributeError):
            pass
        raise ErrorLLM(f"OpenAI respondió {error.code}" + (f": {detalle[:160]}" if detalle else "")) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ErrorLLM(f"No hay conexión con OpenAI ({type(error).__name__})") from None


def respuesta_en_flujo(mensajes: list[dict], herramientas: list[dict] | None = None, modelo: str | None = None, max_salida: int = 900):
    """Genera pares ("texto", fragmento) según llegan y, si el modelo pide herramientas, un último ("llamadas", [{id, nombre, argumentos}])."""
    k = clave()
    if not k:
        raise ErrorLLM("Falta OPENAI_API_KEY")
    modelo = modelo or MODELO_CHAT
    try:
        respuesta = _abrir(_cuerpo(modelo, mensajes, herramientas, True, max_salida), k)
    except ErrorLLM:
        if modelo == MODELO_RESPALDO:
            raise
        respuesta = _abrir(_cuerpo(MODELO_RESPALDO, mensajes, herramientas, True, max_salida), k)
    llamadas: dict[int, dict] = {}
    try:
        with respuesta:
            for crudo in respuesta:
                linea = crudo.decode("utf-8", "replace").strip()
                if not linea.startswith("data:"):
                    continue
                dato = linea[5:].strip()
                if dato == "[DONE]":
                    break
                try:
                    trozo = json.loads(dato)
                except ValueError:
                    continue
                for opcion in trozo.get("choices") or []:
                    delta = opcion.get("delta") or {}
                    if delta.get("content"):
                        yield ("texto", delta["content"])
                    for llamada in delta.get("tool_calls") or []:
                        actual = llamadas.setdefault(llamada.get("index", 0), {"id": "", "nombre": "", "argumentos": ""})
                        if llamada.get("id"):
                            actual["id"] = llamada["id"]
                        funcion = llamada.get("function") or {}
                        actual["nombre"] += funcion.get("name") or ""
                        actual["argumentos"] += funcion.get("arguments") or ""
    except (TimeoutError, OSError) as error:
        raise ErrorLLM(f"Se cortó la conexión con OpenAI ({type(error).__name__})") from None
    if llamadas:
        yield ("llamadas", [llamadas[i] for i in sorted(llamadas)])


def completar_json(sistema: str, usuario: str, modelo: str | None = None, max_salida: int = 300) -> dict:
    """Una sola llamada sin herramientas que devuelve un objeto JSON. Para clasificar textos cortos."""
    k = clave()
    if not k:
        raise ErrorLLM("Falta OPENAI_API_KEY")
    cuerpo = _cuerpo(modelo or MODELO_RAPIDO, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], None, False, max_salida)
    cuerpo["response_format"] = {"type": "json_object"}
    with _abrir(cuerpo, k) as respuesta:
        try:
            return json.loads(json.loads(respuesta.read())["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError):
            raise ErrorLLM("OpenAI devolvió una respuesta que no se puede leer") from None
