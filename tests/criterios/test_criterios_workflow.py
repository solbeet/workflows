"""Prueba el job ``criterios`` de gates.yml de punta a punta sobre el fixture del backend.

Copia ``tests/fixture/backend`` a repos git temporales, arma el commit de merge de un PR
(HEAD^1 = base, HEAD^2 = punta) y corre los pasos del job tal como están en el YAML: la
suite con uv y pytest de verdad, la matriz (copia incrustada de scripts/criterios.py) y el
veredicto. La API de GitHub es un servidor local que devuelve la necesidad.

Casos (criterio 6 de solbeet/workflows#33): una suite sin tests, un criterio sin prueba y
todos los criterios con su prueba. Además: la copia incrustada es igual al script, el job
lee el issue con un token de solo lectura y los callers le dan ese permiso.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATES = ROOT / ".github/workflows/gates.yml"
SELFTEST = ROOT / ".github/workflows/selftest.yml"
EJEMPLO = ROOT / "examples/gates.yml"
SCRIPT = ROOT / "scripts/criterios.py"
FIXTURE = ROOT / "tests/fixture/backend"

NECESIDAD = """## Criterios de aceptación

- [ ] Dado A, cuando B, entonces C.
- [ ] Dado D, cuando E, entonces F.
- [ ] Dado G, cuando H, entonces I.
- [ ] Dado J, cuando K, entonces L.
"""


def codigo_tests_ca(*numeros: int) -> str:
    return "".join(f"\n\ndef test_ca_7_{n}_criterio():\n    assert {n} == {n}\n" for n in numeros)


def workflow(ruta: pathlib.Path) -> dict:
    return yaml.safe_load(ruta.read_text())


def job_criterios() -> dict:
    return workflow(GATES)["jobs"]["criterios"]


def pasos() -> dict[str, dict]:
    return {p["name"]: p for p in job_criterios()["steps"]}


def git(cwd: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def armar_repo(raiz: str, cambios: dict[str, str], borrar: tuple[str, ...]) -> str:
    """Repo con el fixture en backend/ (sin ``borrar``), un PR con ``cambios`` y merge --no-ff."""
    repo = tempfile.mkdtemp(dir=raiz)
    ignorar = shutil.ignore_patterns(".venv", ".*_cache", "__pycache__")
    shutil.copytree(FIXTURE, pathlib.Path(repo, "backend"), ignore=ignorar)
    for nombre in borrar:
        pathlib.Path(repo, "backend", nombre).unlink()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "selftest@example.com")
    git(repo, "config", "user.name", "selftest")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "checkout", "-qb", "pr")
    for nombre, contenido in cambios.items():
        pathlib.Path(repo, "backend", nombre).write_text(contenido)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "pr")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "pr", "-m", "merge")
    return repo


class FakeGitHub(BaseHTTPRequestHandler):
    """Devuelve la necesidad org/app#7; cualquier otra ruta es 404."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/repos/org/app/issues/7":
            datos, codigo = json.dumps({"number": 7, "body": NECESIDAD}).encode(), 200
        else:
            datos, codigo = b'{"message": "Not Found"}', 404
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args: object) -> None:
        """Sin ruido en la salida."""


@pytest.fixture(scope="module")
def api_url():
    servidor = HTTPServer(("127.0.0.1", 0), FakeGitHub)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_port}"
    servidor.shutdown()


def correr_paso(paso: dict, cwd: str, entorno: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso con el intérprete que usaría GitHub."""
    if paso.get("shell", "").startswith("python3"):
        comando = [sys.executable, "-c", paso["run"]]
    else:
        comando = ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", paso["run"]]
    entorno_sin_venv = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}
    r = subprocess.run(comando, cwd=cwd, env={**entorno_sin_venv, **entorno}, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def leer_output(ruta: pathlib.Path) -> dict[str, str]:
    return dict(linea.split("=", 1) for linea in ruta.read_text().splitlines() if "=" in linea)


def correr_job(repo: str, api_url: str) -> tuple[int, dict[str, str], pathlib.Path, str]:
    """Corre suite → matriz → veredicto como en el runner. Devuelve código, outputs, json y log."""
    temp = pathlib.Path(tempfile.mkdtemp(dir=repo + "/.."))
    salida, resumen = temp / "output.txt", temp / "summary.md"
    salida.write_text("")
    resumen.write_text("")
    comun = {
        "GITHUB_OUTPUT": str(salida),
        "GITHUB_STEP_SUMMARY": str(resumen),
        "GITHUB_WORKSPACE": repo,
        "RUNNER_TEMP": str(temp),
        "JUNIT": str(temp / "criterios-junit.xml"),
        "CRITERIOS_DIR": "backend",
    }
    p = pasos()
    codigo, log = correr_paso(p["Correr la suite"], str(pathlib.Path(repo, "backend")), comun)
    assert codigo == 0, f"la suite no debe frenar el job por sí misma:\n{log}"
    suite = leer_output(salida)
    matriz = temp / "criterios-matriz.json"
    entorno_matriz = {
        **comun,
        "PR_BODY": "Closes #7",
        "REPO": "org/app",
        "API_URL": api_url,
        "GH_TOKEN": "token-de-prueba",
        "PYTEST_CODIGO": suite["codigo"],
        "MATRIZ_JSON": str(matriz),
    }
    codigo, log_matriz = correr_paso(p["Matriz por criterio"], repo, entorno_matriz)
    assert codigo == 0, log_matriz
    salidas = leer_output(salida)
    entorno_veredicto = {**comun, "RESULTADO": salidas["resultado"], "MOTIVO": salidas["motivo"]}
    codigo, log_veredicto = correr_paso(p["Veredicto"], repo, entorno_veredicto)
    return codigo, salidas, matriz, "\n".join([log, log_matriz, log_veredicto])


CASOS = {
    "sin-tests": ({}, ("tests/test_main.py", "tests/test_postgres.py"), "rojo", "sin_tests_corridos", ""),
    "criterio-faltante": (
        {"tests/test_ca.py": codigo_tests_ca(1, 2, 3)},
        (),
        "rojo",
        "criterios_sin_evidencia",
        "criterio 4 de org/app#7",
    ),
    "todos-presentes": ({"tests/test_ca.py": codigo_tests_ca(1, 2, 3, 4)}, (), "verde", "ok", ""),
}


@pytest.mark.parametrize("caso", list(CASOS))
def test_ca_33_6_fixture_del_job_da_el_resultado_esperado(tmp_path, api_url, caso):
    if shutil.which("uv") is None:
        pytest.fail("Falta uv en el PATH: el caso corre la suite de verdad.")
    cambios, borrar, resultado, motivo, en_log = CASOS[caso]
    repo = armar_repo(str(tmp_path), {"app/nuevo.py": "VALOR = 1\n", **cambios}, borrar)
    codigo, salidas, matriz, log = correr_job(repo, api_url)
    assert (salidas["resultado"], salidas["motivo"]) == (resultado, motivo), log
    assert (codigo == 0) == (resultado == "verde"), log
    assert en_log in log
    datos = json.loads(matriz.read_text())
    assert datos["resultado"] == resultado
    if resultado == "verde":
        assert [c["estado"] for c in datos["criterios"]] == ["CODE"] * 4


def test_ca_33_6_selftest_corre_los_casos_y_el_job_sobre_el_propio_pr():
    selftest = workflow(SELFTEST)["jobs"]
    corridas = [p.get("run", "") for p in selftest["hygiene-logic"]["steps"]]
    assert any("tests/criterios" in r and "pytest" in r for r in corridas)
    gates = selftest["gates"]
    assert gates["with"]["criterios-dir"] == "tests/criterios"
    assert gates["permissions"] == {"contents": "read", "issues": "read"}


def test_ca_33_3_el_job_sube_la_matriz_como_artefacto():
    subir = pasos()["Subir la matriz"]
    assert subir["uses"].startswith("actions/upload-artifact@")
    assert subir["with"]["if-no-files-found"] == "error"


def test_la_copia_incrustada_es_igual_al_script():
    incrustado = pasos()["Matriz por criterio"]["run"]
    assert incrustado == SCRIPT.read_text(), (
        "La copia de scripts/criterios.py en gates.yml quedó vieja: correr python3 scripts/incrustar-criterios.py"
    )


def test_el_issue_se_lee_con_un_token_de_solo_lectura():
    assert job_criterios()["permissions"] == {"contents": "read", "issues": "read"}


def test_el_ejemplo_cubre_los_permisos_de_todos_los_jobs():
    # Un caller que no da issues: read hace fallar al workflow entero al arrancar.
    assert workflow(EJEMPLO)["permissions"] == {"contents": "read", "issues": "read"}
