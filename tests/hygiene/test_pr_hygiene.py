"""Prueba la lógica de los pasos de pr-hygiene.yml sin depender de GitHub.

Lee el workflow, extrae el script de cada paso del job ``hygiene`` y lo corre
contra repos git temporales que imitan el commit de merge que GitHub arma
para un PR (HEAD^1 = base, HEAD^2 = punta del PR). Así se prueban casos que
deben fallar (falta una sección, marcadores de conflicto, archivos .rej),
algo que no se puede hacer llamando al workflow reutilizable desde selftest.

Uso (desde la raíz del repo):

    uv run --no-project --with pyyaml==6.0.2 python tests/hygiene/test_pr_hygiene.py

Sale con código 0 si todos los casos dan el resultado esperado y 1 si no.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/pr-hygiene.yml"


@dataclass
class Case:
    """Un caso de prueba: qué paso correr, con qué archivos en el PR y qué se espera."""

    name: str
    step: str
    expect_ok: bool
    files: dict[str, str] = field(default_factory=lambda: {"x.txt": "x\n"})
    env: dict[str, str] = field(default_factory=dict)
    expect_output: str = ""


def git(cwd: str, *args: str) -> None:
    """Corre un comando git en ``cwd`` y falla si devuelve error."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_pr_repo(root: str, files: dict[str, str]) -> str:
    """Crea un repo con base, una rama con ``files`` y un merge --no-ff de esa rama.

    Args:
        root: Directorio temporal donde crear el repo.
        files: Archivos (ruta relativa -> contenido) que agrega el "PR".

    Returns:
        Ruta del repo, con HEAD en el commit de merge.
    """
    repo = tempfile.mkdtemp(dir=root)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "selftest@example.com")
    git(repo, "config", "user.name", "selftest")
    git(repo, "config", "commit.gpgsign", "false")
    pathlib.Path(repo, "README.md").write_text("base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "checkout", "-qb", "pr")
    for name, content in files.items():
        path = pathlib.Path(repo, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "pr")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "pr", "-m", "merge")
    return repo


def run_step(step: dict[str, str], cwd: str, env: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso con el mismo intérprete que usaría GitHub.

    Returns:
        Código de salida y salida combinada (stdout + stderr).
    """
    full_env = {**os.environ, **env}
    if step.get("shell", "").startswith("python3"):
        cmd = [sys.executable, "-c", step["run"]]
    else:
        # Mismas opciones que usa GitHub con `shell: bash`.
        cmd = ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]]
    result = subprocess.run(cmd, cwd=cwd, env=full_env, capture_output=True, text=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def build_cases(inputs: dict[str, dict[str, object]]) -> list[Case]:
    """Arma los casos usando los defaults del workflow, para no duplicarlos acá."""
    sections = str(inputs["required-sections"]["default"])
    first, second = [s.strip() for s in sections.splitlines() if s.strip()][:2]
    exclude = str(inputs["diff-exclude"]["default"])
    body_step = "Secciones de evidencia en el cuerpo del PR"

    def body_env(body: str, required: str = sections) -> dict[str, str]:
        return {"PR_BODY": body, "REQUIRED_SECTIONS": required, "REQUIRE_CONTENT": "true"}

    return [
        Case("cuerpo completo", body_step, True, env=body_env(f"{first}\nCloses #1\n{second}\npytest: 3 passed")),
        Case("cuerpo con CRLF y mayúsculas", body_step, True, env=body_env(f"{first.upper()}\r\nx\r\n{second}\r\ny")),
        Case(
            "falta una sección", body_step, False, env=body_env(f"{first}\nCloses #1"), expect_output="Falta la sección"
        ),
        Case(
            "sección solo con comentario",
            body_step,
            False,
            env=body_env(f"{first}\n<!-- link -->\n{second}\nok"),
            expect_output="está vacía",
        ),
        Case("cuerpo vacío", body_step, False, env=body_env("")),
        Case("sin secciones configuradas", body_step, True, env=body_env("", required="")),
        Case(
            "diff grande avisa sin fallar",
            "Tamaño del diff",
            True,
            files={"a.py": "x\n" * 500, "uv.lock": "y\n" * 9000, "web/package-lock.json": "z\n" * 900},
            env={"MAX_DIFF_LINES": "400", "DIFF_EXCLUDE": exclude},
            expect_output="::warning::El diff tiene 500",
        ),
        Case(
            "lockfiles no cuentan",
            "Tamaño del diff",
            True,
            files={"a.py": "x\n" * 10, "backend/uv.lock": "y\n" * 9000},
            env={"MAX_DIFF_LINES": "400", "DIFF_EXCLUDE": exclude},
            expect_output="Líneas cambiadas (sin excluidos): 10",
        ),
        Case("archivo .rej falla", "Archivos .rej", False, files={"src/a.py.rej": "x\n"}),
        Case("sin .rej pasa", "Archivos .rej", True, files={"src/a.py": "x\n"}),
        Case(
            "marcadores de conflicto fallan",
            "Marcadores de conflicto",
            False,
            files={"src/a.py": "a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> rama\n"},
            expect_output="file=src/a.py,line=2",
        ),
        Case(
            "subrayado rst no es conflicto",
            "Marcadores de conflicto",
            True,
            files={"doc.rst": "Título\n=======\ntexto\n"},
        ),
    ]


def main() -> int:
    """Corre todos los casos e imprime OK/FALLA por cada uno."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    # PyYAML interpreta la clave `on` como el booleano True.
    trigger = workflow.get("on") or workflow[True]
    inputs = trigger["workflow_call"]["inputs"]
    steps = {s["name"]: s for s in workflow["jobs"]["hygiene"]["steps"]}

    failures = 0
    with tempfile.TemporaryDirectory() as root:
        for case in build_cases(inputs):
            repo = make_pr_repo(root, case.files)
            code, output = run_step(steps[case.step], repo, case.env)
            ok = (code == 0) == case.expect_ok and case.expect_output in output
            failures += not ok
            last = output.splitlines()[-1] if output else ""
            print(f"{'OK   ' if ok else 'FALLA'} {case.name}: exit={code} | {last}")
    print(f"\n{failures} caso(s) con resultado inesperado." if failures else "\nTodos los casos OK.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
