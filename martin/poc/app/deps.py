"""Dependencias compartidas de FastAPI para los routers."""
from fastapi import HTTPException


def get_store():
    """Devuelve el almacén que tiene `main` en el momento de la llamada.

    El import es perezoso por dos motivos: evita un ciclo (main importa los routers y los routers importan
    esto) y respeta que los tests sustituyen `main.store` por uno temporal después de importar la aplicación.
    """
    from . import main
    return main.store


def http_de(error) -> HTTPException:
    """Traduce un `hub.ErrorNegocio` al error HTTP que le corresponde, con el mismo formato que el resto de la API."""
    if error.codigo == 404:
        return HTTPException(404, error.problemas[0])
    return HTTPException(error.codigo, {"problemas": error.problemas, **error.extra})
