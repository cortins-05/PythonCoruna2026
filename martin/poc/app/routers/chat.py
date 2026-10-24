"""Chat: respuesta en streaming, bloques de muestra y sugerencias de la pantalla de bienvenida.

`POST /api/chat` sigue en `main.py` y devuelve lo que devuelva `chat.responder`. `POST /api/chat/stream` entrega lo mismo como eventos SSE
(`herramienta`, `bloque`, `texto`, `fin`, `error`) para que la interfaz pinte los bloques según llegan y el texto letra a letra.
`bloques-muestra` no lee el almacén y siempre devuelve lo mismo, para desarrollar el pintado sin depender del resto.
"""
import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import chat, chat_bloques
from ..deps import get_store

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatIn(BaseModel):
    mensaje: str
    historial: list[dict] = []


def evento(nombre: str, datos: dict) -> str:
    return f"event: {nombre}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


@router.post("/stream")
def stream(datos: ChatIn, store=Depends(get_store)):
    def generar():
        try:
            r = chat.responder(store, datos.mensaje, datos.historial)
            for bloque in r["bloques"]:
                yield evento("bloque", bloque)
                time.sleep(0.05)
            texto = r["respuesta"]
            for i in range(0, len(texto), 18):
                yield evento("texto", {"delta": texto[i:i + 18]})
                time.sleep(0.015)
            yield evento("fin", {"respuesta": texto, "modo": r["modo"], "propuestas": r["propuestas"]})
        except Exception:  # el stream ya está abierto: se avisa con un evento y no con un 500
            yield evento("error", {"mensaje": "No se pudo completar la respuesta"})
    return StreamingResponse(generar(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/bloques-muestra")
def bloques_muestra():
    return {"bloques": chat_bloques.bloques_muestra()}


@router.get("/sugerencias")
def sugerencias():
    return chat_bloques.sugerencias_bienvenida()
