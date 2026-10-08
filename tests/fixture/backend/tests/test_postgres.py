"""Verifica el servicio Postgres que levanta python-react.yml con postgres: true.

Sin DATABASE_URL el test se saltea, así la misma batería corre con y sin
servicio. Usa solo la biblioteca estándar (socket) para no sumar un driver.
"""

import os
import socket
from urllib.parse import urlparse

import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL no definida")
def test_postgres_acepta_conexiones() -> None:
    assert DATABASE_URL is not None
    url = urlparse(DATABASE_URL)
    assert url.scheme == "postgresql"
    with socket.create_connection((url.hostname or "localhost", url.port or 5432), timeout=5):
        pass
