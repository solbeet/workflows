"""Endpoints del fixture: un healthcheck y una suma.

Existen solo para que ruff, pyright y pytest tengan código real que revisar
cuando el selftest llama a python-react.yml.
"""

from fastapi import FastAPI

app = FastAPI(title="fixture-backend")


@app.get("/health")
def health() -> dict[str, str]:
    """Devuelve el estado del servicio.

    Returns:
        Diccionario con la clave ``status`` en ``"ok"``.
    """
    return {"status": "ok"}


@app.get("/sum")
def sum_numbers(a: int, b: int) -> dict[str, int]:
    """Suma dos enteros recibidos por query string.

    Args:
        a: Primer sumando.
        b: Segundo sumando.

    Returns:
        Diccionario con la clave ``result``.
    """
    return {"result": a + b}
