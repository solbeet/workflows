"""Prueba el paso «Plan de construcción» de imagen.yml sin depender de GitHub.

Extrae el script del job ``plan`` y lo corre con distintas combinaciones de
inputs, leyendo lo que escribe en ``GITHUB_OUTPUT``. Cubre la decisión entre
construcción nativa por arquitectura y QEMU (el default de v1.6.0).

Uso (desde la raíz del repo):

    uv run --no-project --with pyyaml==6.0.2 python tests/imagen/test_imagen_plan.py

Sale con código 0 si todos los casos dan el resultado esperado y 1 si no.
"""

from __future__ import annotations

import fnmatch
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/imagen.yml"
BOTH = "linux/amd64,linux/arm64"


@dataclass
class Case:
    """Un caso: inputs del workflow y resultado esperado del plan."""

    name: str
    plataformas: str
    runner: str = ""
    runner_amd64: str = ""
    runner_arm64: str = ""
    imagen: str = "app"
    nativo: bool = False
    runners: tuple[str, ...] = ()


CASES = [
    Case("sin runners propios: QEMU como v1.6.0", BOTH),
    Case("solo runner base: QEMU", BOTH, runner="propio"),
    Case("solo runner amd64: QEMU", BOTH, runner_amd64="x86"),
    Case("arm64 sin runner base: amd64 usa hosted", BOTH, runner_arm64="arm", nativo=True, runners=("ubuntu-latest", "arm")),
    Case("runner base + arm64", BOTH, runner="propio", runner_arm64="arm", nativo=True, runners=("propio", "arm")),
    Case("runner-amd64 pisa al base", BOTH, runner="propio", runner_amd64="x86", runner_arm64="arm", nativo=True, runners=("x86", "arm")),
    Case("una sola plataforma: sin índice, QEMU", "linux/arm64", runner_arm64="arm"),
    Case("plataforma sin runner (arm/v7): QEMU", "linux/amd64,linux/arm/v7", runner_arm64="arm"),
    Case("espacios y orden invertido", " linux/arm64 , linux/amd64 ", runner_arm64="arm", nativo=True, runners=("arm", "ubuntu-latest")),
]


def run_plan(step: dict[str, object], case: Case) -> dict[str, str]:
    """Corre el script del paso y devuelve lo que escribió en GITHUB_OUTPUT."""
    with tempfile.NamedTemporaryFile("r", suffix=".out") as salida:
        env = {
            **os.environ,
            "PLATAFORMAS": case.plataformas,
            "IMAGEN": case.imagen,
            "RUNNER": case.runner,
            "RUNNER_AMD64": case.runner_amd64,
            "RUNNER_ARM64": case.runner_arm64,
            "GITHUB_OUTPUT": salida.name,
        }
        subprocess.run([sys.executable, "-c", str(step["run"])], env=env, check=True, capture_output=True, text=True)
        pares = (linea.split("=", 1) for linea in salida.read().splitlines() if "=" in linea)
        return dict(pares)


def expandir_llaves(patron: str) -> list[str]:
    """Expande un grupo de llaves `a-{x,y}` como lo hace minimatch (un solo nivel)."""
    m = re.fullmatch(r"(.*)\{([^{}]*)\}(.*)", patron)
    if not m:
        return [patron]
    return [m[1] + opcion + m[3] for opcion in m[2].split(",")]


def casa(patron: str, nombre: str) -> bool:
    """True si el artifact `nombre` lo bajaría download-artifact con `patron`."""
    return any(fnmatch.fnmatchcase(nombre, p) for p in expandir_llaves(patron))


def probar_digests(step: dict[str, object]) -> int:
    """El pattern de digests no puede casar con los artifacts de otra imagen de nombre parecido."""
    fallas = 0
    for imagen, otra in (("app", "app-web"), ("app", "app-linux"), ("app-web", "app")):
        out = run_plan(step, Case("colisión", BOTH, runner_arm64="arm", imagen=imagen))
        patron = out["digests"]
        propios = [f"digests-{imagen}-linux-amd64", f"digests-{imagen}-linux-arm64"]
        ajenos = [f"digests-{otra}-linux-amd64", f"digests-{otra}-linux-arm64"]
        ok = all(casa(patron, n) for n in propios) and not any(casa(patron, n) for n in ajenos)
        # El pattern viejo (`digests-<imagen>-*`) casaba con la otra imagen: el caso tiene que poder fallar.
        viejo_casa_ajenos = any(fnmatch.fnmatchcase(n, f"digests-{imagen}-*") for n in ajenos)
        fallas += not ok
        print(f"{'OK   ' if ok else 'FALLA'} digests de {imagen} sin pisar a {otra}: {patron} (pattern viejo casaba con la ajena: {viejo_casa_ajenos})")
    qemu = run_plan(step, Case("qemu", BOTH))
    ok = qemu["digests"] == ""
    fallas += not ok
    print(f"{'OK   ' if ok else 'FALLA'} modo QEMU: sin pattern de digests")
    return fallas


def main() -> int:
    """Corre todos los casos e imprime OK/FALLA por cada uno."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    step = next(s for s in workflow["jobs"]["plan"]["steps"] if s.get("id") == "plan")
    # PyYAML interpreta la clave `on` como el booleano True.
    inputs = (workflow.get("on") or workflow[True])["workflow_call"]["inputs"]
    assert inputs["runner-arm64"]["default"] == "", "runner-arm64 vacío tiene que ser el default (QEMU)"
    assert inputs["plataformas"]["default"] == BOTH

    fallas = 0
    for case in CASES:
        out = run_plan(step, case)
        matriz = json.loads(out["matriz"])
        ok = (out["nativo"] == "true") == case.nativo and tuple(m["runner"] for m in matriz) == case.runners
        if case.nativo:
            ok = ok and all(m["par"] == m["plataforma"].replace("/", "-") for m in matriz)
        fallas += not ok
        print(f"{'OK   ' if ok else 'FALLA'} {case.name}: nativo={out['nativo']} matriz={out['matriz']}")
    fallas += probar_digests(step)
    print(f"\n{fallas} caso(s) con resultado inesperado." if fallas else "\nTodos los casos OK.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
