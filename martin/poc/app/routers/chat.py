"""Chat: bloques de muestra y sugerencias de la pantalla de bienvenida.

`POST /api/chat` sigue en `main.py` y devuelve lo que devuelva `chat.responder`. Aquí viven los dos GET que permiten desarrollar el
pintado de los bloques sin depender del resto: `bloques-muestra` no lee el almacén y siempre devuelve lo mismo.
"""
from fastapi import APIRouter

from .. import chat_bloques

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/bloques-muestra")
def bloques_muestra():
    return {"bloques": chat_bloques.bloques_muestra()}


@router.get("/sugerencias")
def sugerencias():
    return chat_bloques.sugerencias_bienvenida()
