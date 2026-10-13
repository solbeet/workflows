"""Prueba la guardia de tests (guardia-tests.yml) sin depender de GitHub.

Arma repos git temporales que imitan el commit de merge de un PR (HEAD^1 =
base, HEAD^2 = punta del PR), corre los dos pasos del job ``tests`` y compara
el resultado con lo esperado. La API de GitHub (eventos del label y corridas
del commit) se reemplaza con archivos JSON vía ``GUARDIA_FAKE_API``.

Uso (desde la raíz del repo):

    uv run --no-project --with pyyaml==6.0.2 python tests/guardia/test_guardia.py

Sale con código 0 si todos los casos dan el resultado esperado y 1 si no.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/guardia-tests.yml"

BASE = {
    "backend/app/calc.py": "def suma(a, b):\n    return a + b\n",
    "backend/tests/test_calc.py": (
        '"""Tests de calc."""\n'
        "import pytest\n\n"
        "from app.calc import suma\n\n\n"
        "def test_suma():\n"
        '    """Suma dos números."""\n'
        "    assert suma(2, 3) == 5\n\n\n"
        "class TestBorde:\n"
        "    def test_cero(self):\n"
        "        assert suma(0, 0) == 0\n"
    ),
    "backend/tests/aceptacion/test_criterio_1.py": "def test_criterio_1():\n    assert True is True\n",
    "frontend/src/App.test.tsx": "it('muestra el título', () => {\n  expect(1).toBe(1);\n});\n",
}


@dataclass
class Case:
    """Un caso: cambios del PR (None = borrar), API falsa y resultado esperado."""

    name: str
    changes: dict[str, str | None]
    expect_ok: bool
    expect_output: str = ""
    label_events: list[dict[str, object]] = field(default_factory=list)
    run_created: str = "2026-10-13T10:00:00Z"
    renames: dict[str, str] = field(default_factory=dict)


def git(cwd: str, *args: str) -> None:
    """Corre git en ``cwd`` y falla si devuelve error."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(root: str, case: Case) -> str:
    """Repo con la base, una rama con los cambios del caso y un merge --no-ff."""
    repo = tempfile.mkdtemp(dir=root)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "selftest@example.com")
    git(repo, "config", "user.name", "selftest")
    git(repo, "config", "commit.gpgsign", "false")
    for name, content in BASE.items():
        path = pathlib.Path(repo, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "checkout", "-qb", "pr")
    for old, new in case.renames.items():
        pathlib.Path(repo, new).parent.mkdir(parents=True, exist_ok=True)
        git(repo, "mv", old, new)
    for name, content in case.changes.items():
        path = pathlib.Path(repo, name)
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "pr", "--allow-empty")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "pr", "-m", "merge")
    return repo


def run_step(step: dict[str, str], cwd: str, env: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso Python del workflow."""
    result = subprocess.run(
        [sys.executable, "-c", step["run"]], cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def labeled(login: str, when: str, kind: str = "User", event: str = "labeled") -> dict[str, object]:
    """Evento de issue para el label de escape."""
    return {"event": event, "label": {"name": "tests-con-dale"}, "actor": {"login": login, "type": kind}, "created_at": when}


def cases() -> list[Case]:
    """Casos que deben pasar y casos que deben fallar."""
    t = BASE["backend/tests/test_calc.py"]
    return [
        Case("solo código, sin tests", {"backend/app/calc.py": "def suma(a, b):\n    return b + a\n"}, True),
        Case("test nuevo en archivo nuevo", {"backend/tests/test_resta.py": "def test_resta():\n    assert 1 - 1 == 0\n"}, True),
        Case("test nuevo en archivo existente", {"backend/tests/test_calc.py": t + "\n\ndef test_suma_negativos():\n    assert suma(-1, -1) == -2\n"}, True),
        Case("reformatear, imports y docstring no cuentan", {
            "backend/tests/test_calc.py": t.replace('    """Suma dos números."""\n', '    """Suma dos enteros."""\n').replace("import pytest\n", "import os\nimport pytest\n").replace("assert suma(2, 3) == 5", "assert suma(2,  3)  ==  5")
        }, True),
        Case("test de aceptación nuevo", {"backend/tests/aceptacion/test_criterio_2.py": "def test_criterio_2():\n    assert 2 == 2\n"}, True),
        Case("mover un archivo de tests sin cambios", {}, True, renames={"backend/tests/test_calc.py": "backend/tests/unit/test_calc.py"}),
        Case("borra un archivo de tests", {"backend/tests/test_calc.py": None}, False, "borra"),
        Case("debilita un assert", {"backend/tests/test_calc.py": t.replace("assert suma(2, 3) == 5", "assert suma(2, 3)")}, False, "`test_suma` cambia"),
        Case("cambia el valor esperado", {"backend/tests/test_calc.py": t.replace("== 5", "== 6")}, False, "`test_suma` cambia"),
        Case("borra un test de una clase", {"backend/tests/test_calc.py": t.split("class TestBorde")[0] + "class TestBorde:\n    pass\n"}, False, "TestBorde.test_cero"),
        Case("skip en un test existente", {"backend/tests/test_calc.py": t.replace("def test_suma():", "@pytest.mark.skip\ndef test_suma():")}, False, "saltea"),
        Case("xfail en un test nuevo", {"backend/tests/test_nuevo.py": "import pytest\n\n\n@pytest.mark.xfail\ndef test_x():\n    assert False\n"}, False, "saltea"),
        Case("pytest.skip dentro de un test nuevo", {"backend/tests/test_nuevo.py": "import pytest\n\n\ndef test_x():\n    pytest.skip('después')\n"}, False, "saltea"),
        Case("toca un test de aceptación existente", {"backend/tests/aceptacion/test_criterio_1.py": BASE["backend/tests/aceptacion/test_criterio_1.py"] + "\n\ndef test_extra():\n    assert True\n"}, False, "aceptación"),
        Case("strings que mencionan skip no cuentan", {"backend/tests/test_textos.py": 'def test_texto():\n    assert "@pytest.mark.skip" in "x @pytest.mark.skip"\n'}, True),
        Case("pytestmark a nivel módulo saltea", {"backend/tests/test_mod.py": "import pytest\n\npytestmark = pytest.mark.skip(reason='x')\n\n\ndef test_a():\n    assert 1\n"}, False, "saltea"),
        Case("from unittest import skip y decorador", {"backend/tests/test_u.py": "from unittest import skip\n\n\n@skip('x')\ndef test_a():\n    assert 1\n"}, False, "saltea"),
        Case(".only en vitest", {"frontend/src/Nuevo.test.tsx": "it.only('x', () => {});\n"}, False, "saltea"),
        Case("cambia una línea de un test de vitest", {"frontend/src/App.test.tsx": BASE["frontend/src/App.test.tsx"].replace("toBe(1)", "toBeTruthy()")}, False, "reemplaza 1 línea"),
        Case("test de vitest nuevo al final", {"frontend/src/App.test.tsx": BASE["frontend/src/App.test.tsx"] + "\nit('otro', () => {\n  expect(2).toBe(2);\n});\n"}, True),
        Case("con dale de una persona después del push", {"backend/tests/test_calc.py": None}, True, "Aceptados por santiago",
             label_events=[labeled("santiago", "2026-10-13T11:00:00Z")]),
        Case("dale del autor del PR no vale", {"backend/tests/test_calc.py": None}, False, "autor del PR",
             label_events=[labeled("agente-solbeet", "2026-10-13T11:00:00Z")]),
        Case("dale de un bot no vale", {"backend/tests/test_calc.py": None}, False, "bot",
             label_events=[labeled("solbeet-revisor[bot]", "2026-10-13T11:00:00Z", kind="Bot")]),
        Case("dale de antes del último push no vale", {"backend/tests/test_calc.py": None}, False, "antes del último push",
             label_events=[labeled("santiago", "2026-10-13T09:00:00Z")]),
        Case("dale sacado no vale", {"backend/tests/test_calc.py": None}, False, "nadie puso",
             label_events=[labeled("santiago", "2026-10-13T11:00:00Z"), labeled("santiago", "2026-10-13T11:05:00Z", event="unlabeled")]),
    ]


def main() -> int:
    """Corre todos los casos e imprime OK/FALLA por cada uno."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    trigger = workflow.get("on") or workflow[True]
    inputs = trigger["workflow_call"]["inputs"]
    steps = {s["name"]: s for s in workflow["jobs"]["tests"]["steps"]}
    check, decide = steps["Cambios en tests existentes"], steps["Dale humano para los cambios en tests"]
    failures = 0
    with tempfile.TemporaryDirectory() as root:
        for case in cases():
            repo = make_repo(root, case)
            temp = tempfile.mkdtemp(dir=root)
            api = pathlib.Path(temp, "api")
            api.mkdir()
            (api / "repos_o_r_issues_7_events.json").write_text(json.dumps(case.label_events))
            (api / "repos_o_r_actions_runs.json").write_text(json.dumps({"workflow_runs": [{"created_at": case.run_created}]}))
            env = {
                "RUNNER_TEMP": temp,
                "GITHUB_STEP_SUMMARY": str(pathlib.Path(temp, "summary.md")),
                "TEST_PATHS": str(inputs["test-paths"]["default"]),
                "ACCEPTANCE_DIR": str(inputs["acceptance-dir"]["default"]),
                "OVERRIDE_LABEL": str(inputs["override-label"]["default"]),
                "OVERRIDE_APPROVERS": "",
                "REPO": "o/r",
                "PR_NUMBER": "7",
                "PR_AUTHOR": "agente-solbeet",
                "HEAD_SHA": "abc",
                "API_URL": "http://invalido",
                "GH_TOKEN": "x",
                "GUARDIA_FAKE_API": str(api),
            }
            code1, out1 = run_step(check, repo, env)
            code2, out2 = run_step(decide, repo, env) if code1 == 0 else (code1, "")
            output = out1 + "\n" + out2 + "\n" + pathlib.Path(env["GITHUB_STEP_SUMMARY"]).read_text()
            ok = code1 == 0 and (code2 == 0) == case.expect_ok and case.expect_output.lower() in output.lower()
            failures += not ok
            last = (out2 or out1).splitlines()[-1] if (out2 or out1) else ""
            print(f"{'OK   ' if ok else 'FALLA'} {case.name}: exit={code2} | {last[:150]}")
            if not ok:
                print(output)
    print(f"\n{failures} caso(s) con resultado inesperado." if failures else "\nTodos los casos OK.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
