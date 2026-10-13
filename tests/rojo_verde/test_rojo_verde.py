"""Prueba rojo-verde.yml de punta a punta sobre el fixture del backend.

Copia ``tests/fixture/backend`` a repos git temporales, arma el commit de merge
de un PR (HEAD^1 = base, HEAD^2 = punta) y corre los pasos del job con uv y
pytest de verdad. Casos: un test nuevo que falla sin el cambio y pasa con él
(verde), un test espejo que pasa igual sin el cambio (rojo), un PR solo de tests
(no aplica) y un test nuevo que no pasa con el cambio (rojo).

Uso (desde la raíz del repo; necesita uv y red para el primer ``uv sync``):

    uv run --no-project --with pyyaml==6.0.2 python tests/rojo_verde/test_rojo_verde.py
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/rojo-verde.yml"
FIXTURE = ROOT / "tests/fixture/backend"

RESTA = '''

@app.get("/resta")
def resta(a: int, b: int) -> dict[str, int]:
    """Resta dos enteros."""
    return {"result": a - b}
'''

TEST_RESTA = '''"""Tests de /resta."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_resta() -> None:
    assert client.get("/resta", params={"a": 5, "b": 3}).json() == {"result": 2}
'''

TEST_ESPEJO = '''"""Test espejo: prueba algo que ya existía, no lo nuevo."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_suma_otra_vez() -> None:
    assert client.get("/sum", params={"a": 1, "b": 1}).json() == {"result": 2}
'''


@dataclass
class Case:
    """Un caso: archivos que cambia el PR (relativos al backend) y resultado esperado."""

    name: str
    changes: dict[str, str]
    expect_ok: bool
    expect_output: str


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
        if name == "app/main.py":
            content = path.read_text() + content
        path.write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "pr")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "pr", "-m", "merge")
    return repo


def run_step(step: dict[str, str], cwd: str, env: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso con el intérprete que usaría GitHub."""
    if step.get("shell", "").startswith("python3"):
        cmd = [sys.executable, "-c", step["run"]]
    else:
        cmd = ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]]
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    """Corre los casos e imprime OK/FALLA por cada uno."""
    if shutil.which("uv") is None:
        print("Falta uv en el PATH.")
        return 1
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = (workflow.get("on") or workflow[True])["workflow_call"]["inputs"]
    steps = {s["name"]: s for s in workflow["jobs"]["rojo-verde"]["steps"]}
    order = ["Tests nuevos del PR", "Correr los tests nuevos contra la base y contra el PR", "Veredicto rojo → verde", "Dale humano para tests que ya pasaban"]
    cases = [
        Case("test nuevo rojo → verde", {"app/main.py": RESTA, "tests/test_resta.py": TEST_RESTA}, True, "fallan sin el cambio y pasan con él"),
        Case("test espejo (pasa sin el cambio)", {"app/main.py": RESTA, "tests/test_espejo.py": TEST_ESPEJO}, False, "pasa sin el cambio"),
        Case("PR solo de tests: no aplica", {"tests/test_espejo.py": TEST_ESPEJO}, True, "no cambia código"),
        Case("test nuevo que no pasa con el cambio", {"app/main.py": RESTA, "tests/test_resta.py": TEST_RESTA.replace("== {\"result\": 2}", "== {\"result\": 3}")}, False, "no pasa con el cambio"),
    ]
    failures = 0
    with tempfile.TemporaryDirectory() as root:
        for case in cases:
            repo = make_repo(root, case.changes)
            temp = tempfile.mkdtemp(dir=root)
            env = {
                "RUNNER_TEMP": temp,
                "GITHUB_OUTPUT": str(pathlib.Path(temp, "out")),
                "GITHUB_STEP_SUMMARY": str(pathlib.Path(temp, "summary.md")),
                "BACKEND_DIR": "backend",
                "BASE_DIR": str(pathlib.Path(temp, "base")),
                "TEST_PATHS": str(inputs["test-paths"]["default"]),
                "IGNORE_PATHS": str(inputs["ignore-paths"]["default"]),
                "OVERRIDE_LABEL": "tests-con-dale",
                # Sin API real: el dale no se puede validar y falla cerrado.
                "API_URL": "http://127.0.0.1:9",
                "GH_TOKEN": "x", "REPO": "o/r", "PR_NUMBER": "1", "PR_AUTHOR": "agente", "HEAD_SHA": "abc",
            }
            output, code = "", 0
            for name in order:
                if name != order[0] and "aplica=false" in pathlib.Path(env["GITHUB_OUTPUT"]).read_text():
                    break
                code, out = run_step(steps[name], repo, env)
                output += out + "\n"
                if code != 0:
                    break
            summary = pathlib.Path(env["GITHUB_STEP_SUMMARY"])
            output += summary.read_text() if summary.exists() else ""
            ok = (code == 0) == case.expect_ok and case.expect_output in output
            failures += not ok
            print(f"{'OK   ' if ok else 'FALLA'} {case.name}: exit={code}")
            if not ok:
                print(output)
    print(f"\n{failures} caso(s) con resultado inesperado." if failures else "\nTodos los casos OK.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
