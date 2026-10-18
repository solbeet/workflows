"""Prueba mutacion.yml de punta a punta sobre el fixture del backend.

Copia ``tests/fixture/backend`` a repos git temporales, arma el commit de merge de
un PR (HEAD^1 = base, HEAD^2 = punta) y corre los pasos del job con uv y mutmut de
verdad. La API de GitHub es un servidor local que guarda los comentarios.

Casos: un módulo con tests flojos (sobreviven mutantes y se muestra el diff), un
módulo con tests que detectan todo (100 %), un PR que no toca código, un repo que
ya configura mutmut, un tope agotado (incompleto) y el comentario único por PR
(la segunda corrida actualiza el comentario en vez de crear otro).

Uso (desde la raíz del repo; necesita uv y red para el primer ``uv sync``):

    uv run --no-project --with pyyaml==6.0.2 python tests/mutacion/test_mutacion.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/mutacion.yml"
FIXTURE = ROOT / "tests/fixture/backend"

CALC = '''def suma(a: int, b: int) -> int:
    return a + b


def es_mayor(a: int, b: int) -> bool:
    if a > b:
        return True
    return False
'''

TEST_FLOJO = '''from app.calc import es_mayor, suma


def test_suma():
    assert suma(2, 3) == 5


def test_mayor():
    assert es_mayor(3, 2)
'''

TEST_COMPLETO = TEST_FLOJO + '''

def test_igual_no_es_mayor():
    assert not es_mayor(2, 2)


def test_menor_no_es_mayor():
    assert not es_mayor(1, 2)
'''

MUTMUT_PROPIO = '\n[tool.mutmut]\npaths_to_mutate = ["app"]\n'


@dataclass
class Case:
    """Un caso: archivos del PR (relativos al backend), lo que debe decir el informe y el tope simulado."""

    name: str
    changes: dict[str, str]
    contains: list[str]
    absent: list[str] = field(default_factory=list)
    force_exit: str = ""
    segunda_corrida: bool = False


def git(cwd: str, *args: str) -> None:
    """Corre git en ``cwd`` y falla si devuelve error."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(root: str, changes: dict[str, str]) -> str:
    """Repo con el fixture en backend/, una rama con ``changes`` y un merge --no-ff."""
    repo = tempfile.mkdtemp(dir=root)
    shutil.copytree(FIXTURE, pathlib.Path(repo, "backend"), ignore=shutil.ignore_patterns(".venv", ".*_cache", "__pycache__"))
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "selftest@example.com")
    git(repo, "config", "user.name", "selftest")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "checkout", "-qb", "pr")
    for name, content in changes.items():
        path = pathlib.Path(repo, "backend", name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == "pyproject.toml":
            content = path.read_text() + content
        path.write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "pr")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "pr", "-m", "merge")
    return repo


class FakeGitHub(BaseHTTPRequestHandler):
    """API mínima de comentarios: GET lista, POST crea, PATCH actualiza."""

    comentarios: list[dict[str, object]] = []
    pedidos: list[str] = []

    def _json(self, codigo: int, cuerpo: object) -> None:
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _leer(self) -> dict[str, str]:
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        FakeGitHub.pedidos.append("GET")
        pagina = int(self.path.split("page=")[-1]) if "page=" in self.path else 1
        self._json(200, FakeGitHub.comentarios if pagina == 1 else [])

    def do_POST(self) -> None:  # noqa: N802
        FakeGitHub.pedidos.append("POST")
        comentario = {"id": len(FakeGitHub.comentarios) + 1, "body": self._leer()["body"], "user": {"type": "Bot"}}
        FakeGitHub.comentarios.append(comentario)
        self._json(201, comentario)

    def do_PATCH(self) -> None:  # noqa: N802
        FakeGitHub.pedidos.append("PATCH")
        identificador = int(self.path.rsplit("/", 1)[-1])
        for c in FakeGitHub.comentarios:
            if c["id"] == identificador:
                c["body"] = self._leer()["body"]
        self._json(200, {})

    def log_message(self, *args: object) -> None:
        """Sin ruido en la salida."""


def run_step(step: dict[str, str], cwd: str, env: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso con el intérprete que usaría GitHub."""
    if step.get("shell", "").startswith("python3"):
        cmd = [sys.executable, "-c", step["run"]]
    else:
        cmd = ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]]
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def make_timeout_shim(directory: str) -> None:
    """``timeout`` de GNU no existe en macOS: un reemplazo que ignora el tope y, si se pide, simula el 124."""
    shim = pathlib.Path(directory, "timeout")
    shim.write_text(
        '#!/bin/bash\n'
        'while [ "${1#--}" != "$1" ]; do shift; done\n'
        'shift\n'
        '"$@"; codigo=$?\n'
        '[ -n "$SHIM_FORCE_EXIT" ] && exit "$SHIM_FORCE_EXIT"\n'
        'exit $codigo\n'
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)


def main() -> int:
    """Corre los casos e imprime OK/FALLA por cada uno."""
    if shutil.which("uv") is None:
        print("Falta uv en el PATH.")
        return 1
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = (workflow.get("on") or workflow[True])["workflow_call"]["inputs"]
    assert inputs["max-minutes"]["default"] == 10, "el tope por defecto es de 10 minutos"
    steps = {s["name"]: s for s in workflow["jobs"]["mutacion"]["steps"]}
    order = ["Archivos del diff", "Correr mutmut sobre los archivos del diff", "Informe y comentario en el PR"]

    cases = [
        Case(
            "tests flojos: sobreviven mutantes y se ven",
            {"app/calc.py": CALC, "tests/test_calc.py": TEST_FLOJO},
            ["Puntaje: 50,0 %", "2 de 4 mutantes detectados", "2 sobrevivieron", "-    if a > b:", "+    if a >= b:", "app/calc.py"],
            segunda_corrida=True,
        ),
        Case(
            "tests que detectan todo: 100 %",
            {"app/calc.py": CALC, "tests/test_calc.py": TEST_COMPLETO},
            ["Puntaje: 100,0 %", "0 sobrevivieron"],
            ["Mutantes que los tests no detectaron"],
        ),
        Case(
            "tope agotado: incompleto",
            {"app/calc.py": CALC, "tests/test_calc.py": TEST_FLOJO},
            ["incompleto: se agotó el tope de 10 min"],
            force_exit="124",
        ),
        Case("PR que no toca código: no aplica", {"README.md": "# docs\n"}, ["No aplica"]),
        Case(
            "el repo ya configura mutmut: no se pisa",
            {"pyproject.toml": MUTMUT_PROPIO, "app/calc.py": CALC},
            ["No aplica", "[tool.mutmut]"],
        ),
    ]
    failures = 0
    servidor = HTTPServer(("127.0.0.1", 0), FakeGitHub)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as root:
        bin_dir = tempfile.mkdtemp(dir=root)
        make_timeout_shim(bin_dir)
        for case in cases:
            FakeGitHub.comentarios, FakeGitHub.pedidos = [], []
            repo = make_repo(root, case.changes)
            temp = tempfile.mkdtemp(dir=root)
            env = {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "SHIM_FORCE_EXIT": case.force_exit,
                "RUNNER_TEMP": temp,
                "GITHUB_OUTPUT": str(pathlib.Path(temp, "out")),
                "GITHUB_STEP_SUMMARY": str(pathlib.Path(temp, "summary.md")),
                "BACKEND_DIR": "backend",
                "TEST_PATHS": str(inputs["test-paths"]["default"]),
                "IGNORE_PATHS": str(inputs["ignore-paths"]["default"]),
                "MAX_MINUTES": "10",
                "MAX_SURVIVORS": "20",
                "MUTMUT_VERSION": str(inputs["mutmut-version"]["default"]),
                "GH_TOKEN": "x",
                "REPO": "o/r",
                "PR_NUMBER": "1",
                "HEAD_SHA": "abc",
                "API_URL": f"http://127.0.0.1:{servidor.server_port}",
            }
            output, code = "", 0
            for repeticion in range(2 if case.segunda_corrida else 1):
                if repeticion:
                    # Un runner nuevo por corrida: sin el setup.cfg ni mutants/ de la anterior.
                    git(repo, "clean", "-fdxq")
                for name in order:
                    if name != order[0] and "aplica=false" in pathlib.Path(env["GITHUB_OUTPUT"]).read_text():
                        break
                    cwd = repo + "/backend" if name in order[1:] else repo
                    code, out = run_step(steps[name], cwd, env)
                    output += out + "\n"
                    if code != 0 and name != order[1]:
                        break
            summary = pathlib.Path(env["GITHUB_STEP_SUMMARY"])
            output += summary.read_text() if summary.exists() else ""
            comentario = str(FakeGitHub.comentarios[0]["body"]) if FakeGitHub.comentarios else ""
            ok = all(c in output for c in case.contains) and not any(a in output for a in case.absent)
            if case.contains[0] != "No aplica":
                ok = ok and comentario.startswith("<!-- solbeet-mutacion -->") and all(c in comentario for c in case.contains[:1])
            else:
                ok = ok and not FakeGitHub.comentarios
            if case.segunda_corrida:
                ok = ok and len(FakeGitHub.comentarios) == 1 and FakeGitHub.pedidos.count("POST") == 1 and "PATCH" in FakeGitHub.pedidos
            failures += not ok
            print(f"{'OK   ' if ok else 'FALLA'} {case.name}: exit={code} comentarios={len(FakeGitHub.comentarios)} api={FakeGitHub.pedidos}")
            if not ok or os.environ.get("MUTACION_VERBOSE"):
                print(output if not ok else comentario)
    servidor.shutdown()
    print(f"\n{failures} caso(s) con resultado inesperado." if failures else "\nTodos los casos OK.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
