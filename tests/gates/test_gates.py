"""Prueba la lógica de veredicto de gates.yml sin depender de GitHub.

Extrae del workflow los pasos que deciden si un job frena o no (squawk,
contrato, dependencias) y los corre con entradas armadas a mano: lo que ya
fallaba en la base tiene que pasar con aviso y lo nuevo tiene que frenar.
Las herramientas en sí (squawk, Schemathesis, OSV-Scanner, diff-cover) se
prueban de punta a punta en un repo real (ver docs/estado.md).

Uso (desde la raíz del repo):

    uv run --no-project --with pyyaml==6.0.2 python tests/gates/test_gates.py

Sale con código 0 si todos los casos dan el resultado esperado y 1 si no.
"""

from __future__ import annotations

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/gates.yml"


@dataclass
class Case:
    """Un caso: job y paso a correr, archivos de entrada y resultado esperado."""

    name: str
    job: str
    step: str
    expect_ok: bool
    files: dict[str, object] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    expect_output: str = ""


def run_step(step: dict[str, str], cwd: str, env: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso con el mismo intérprete que usaría GitHub."""
    full_env = {**os.environ, **env}
    if step.get("shell", "").startswith("python3"):
        cmd = [sys.executable, "-c", step["run"]]
    else:
        cmd = ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]]
    result = subprocess.run(cmd, cwd=cwd, env=full_env, capture_output=True, text=True, check=False)
    return result.returncode, (result.stdout + result.stderr).strip()


def contrato(*entries: tuple[str, str]) -> dict[str, object]:
    """Archivo de baseline de Schemathesis con (operación, firma) dadas."""
    return {
        "format_version": 1,
        "entries": [
            {"operation": op, "check": "not_a_server_error", "failure": "ServerError", "signature": sig}
            for op, sig in entries
        ],
    }


def osv(root: str, *vulns: tuple[str, str, str, float, bool]) -> dict[str, object]:
    """Salida JSON de OSV-Scanner con (paquete, versión, id, cvss, hay_arreglo)."""
    packages = []
    for name, version, vid, sev, fixed in vulns:
        events = [{"introduced": "0"}] + ([{"fixed": "99.0.0"}] if fixed else [])
        packages.append(
            {
                "package": {"name": name, "version": version, "ecosystem": "PyPI"},
                "groups": [{"ids": [vid], "max_severity": str(sev)}],
                "vulnerabilities": [
                    {"id": vid, "affected": [{"package": {"name": name}, "ranges": [{"events": events}]}]}
                ],
            }
        )
    return {"results": [{"source": {"path": f"{root}/backend/uv.lock"}, "packages": packages}]}


def squawk(*rules: str) -> list[dict[str, object]]:
    """Salida json de squawk con una violación por regla."""
    return [{"file": "/tmp/sql/0002.sql", "rule_name": r, "message": f"msg {r}", "level": "Warning"} for r in rules]


def build_cases(inputs: dict[str, dict[str, object]], tmp: str) -> list[Case]:
    """Arma los casos con los defaults del workflow, para no duplicarlos acá."""
    blocking = str(inputs["migrations-blocking-rules"]["default"])
    pr_root, base_root = f"{tmp}/pr", f"{tmp}/base"
    osv_env = {
        "OSV_PR": f"{tmp}/osv-pr.json",
        "OSV_BASE": f"{tmp}/osv-base.json",
        "ROOT_PR": pr_root,
        "ROOT_BASE": base_root,
        "MIN_SEVERITY": "7",
    }
    c_env = {"BASELINE_PR": f"{tmp}/c-pr.json", "BASELINE_BASE": f"{tmp}/c-base.json", "CONFIRMADOS": f"{tmp}/c-conf.json"}
    s_env = {"BLOCKING_RULES": blocking, "SQL_DIR": f"{tmp}/sql"}
    sq = "squawk sobre las migraciones nuevas"
    return [
        Case("squawk sin migraciones nuevas", "migraciones", sq, True, {"squawk": squawk()}, s_env, "Sin migraciones"),
        Case(
            "squawk DROP COLUMN frena",
            "migraciones",
            sq,
            False,
            {"sql/0002.sql": "x", "squawk": squawk("ban-drop-column", "transaction-nesting")},
            s_env,
            "::error::migración 0002: ban-drop-column",
        ),
        Case(
            "squawk índice sin CONCURRENTLY solo avisa",
            "migraciones",
            sq,
            True,
            {"sql/0002.sql": "x", "squawk": squawk("require-concurrent-index-creation", "prefer-bigint-over-int")},
            s_env,
            "::warning::migración 0002: require-concurrent-index-creation",
        ),
        Case(
            "contrato sin fallos",
            "contrato",
            "Veredicto del contrato",
            True,
            {"c-pr.json": contrato(), "c-base.json": contrato()},
            c_env,
            "",
        ),
        Case(
            "contrato: fallo heredado no frena",
            "contrato",
            "Veredicto del contrato",
            True,
            {"c-pr.json": contrato(("PATCH /items/{id}", "500")), "c-base.json": contrato(("PATCH /items/{id}", "500"))},
            c_env,
            "ya fallaba en la base",
        ),
        Case(
            "contrato: fallo nuevo frena",
            "contrato",
            "Veredicto del contrato",
            False,
            {"c-pr.json": contrato(("PATCH /items/{id}", "500"), ("GET /version", "500")), "c-base.json": contrato(("PATCH /items/{id}", "500"))},
            c_env,
            "::error::GET /version",
        ),
        Case(
            "contrato: la misma petición da 5xx en la base, es heredado",
            "contrato",
            "Veredicto del contrato",
            True,
            {"c-pr.json": contrato(("POST /items", "500")), "c-base.json": contrato(), "c-conf.json": [["POST /items", "not_a_server_error"]]},
            c_env,
            "ya fallaba en la base",
        ),
        Case(
            "contrato: base sin app, todo es nuevo",
            "contrato",
            "Veredicto del contrato",
            False,
            {"c-pr.json": contrato(("GET /x", "500"))},
            c_env,
            "es nuevo",
        ),
        Case(
            "dependencias: crítica nueva con arreglo frena",
            "dependencias",
            "Veredicto de dependencias",
            False,
            {"osv-pr.json": osv(pr_root, ("requests", "2.19.0", "GHSA-1", 9.8, True)), "osv-base.json": osv(base_root)},
            osv_env,
            "::error::Dependencia vulnerable nueva: requests",
        ),
        Case(
            "dependencias: heredada no frena aunque cambie la versión",
            "dependencias",
            "Veredicto de dependencias",
            True,
            {
                "osv-pr.json": osv(pr_root, ("tinypool", "1.1.2", "GHSA-2", 9.5, True)),
                "osv-base.json": osv(base_root, ("tinypool", "1.1.1", "GHSA-2", 9.5, True)),
            },
            osv_env,
            "ya estaban en la base",
        ),
        Case(
            "dependencias: media nueva solo avisa",
            "dependencias",
            "Veredicto de dependencias",
            True,
            {"osv-pr.json": osv(pr_root, ("x", "1.0", "GHSA-3", 5.9, True)), "osv-base.json": osv(base_root)},
            osv_env,
            "::warning::",
        ),
        Case(
            "dependencias: alta sin arreglo solo avisa",
            "dependencias",
            "Veredicto de dependencias",
            True,
            {"osv-pr.json": osv(pr_root, ("y", "1.0", "GHSA-4", 8.1, False)), "osv-base.json": osv(base_root)},
            osv_env,
            "sin versión arreglada",
        ),
    ]


def main() -> int:
    """Corre todos los casos e imprime OK/FALLA por cada uno."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    trigger = workflow.get("on") or workflow[True]
    inputs = trigger["workflow_call"]["inputs"]
    failures = 0
    with tempfile.TemporaryDirectory() as root:
        for i, _ in enumerate(build_cases(inputs, "/x")):
            tmp = pathlib.Path(root, f"c{i}")
            tmp.mkdir()
            case = build_cases(inputs, str(tmp))[i]
            steps = {s["name"]: s for s in workflow["jobs"][case.job]["steps"]}
            bindir = tmp / "bin"
            bindir.mkdir()
            env = {
                **case.env,
                "RUNNER_TEMP": str(tmp),
                "GITHUB_OUTPUT": str(tmp / "out"),
                "GITHUB_STEP_SUMMARY": str(tmp / "summary"),
                "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
            }
            for name, content in case.files.items():
                if name == "squawk":
                    # squawk falso: devuelve la salida json armada para el caso.
                    fake = bindir / "squawk"
                    fake.write_text(f"#!/bin/sh\ncat <<'EOF'\n{json.dumps(content)}\nEOF\nexit 1\n")
                    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
                    continue
                path = tmp / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content if isinstance(content, str) else json.dumps(content))
            code, output = run_step(steps[case.step], str(tmp), env)
            ok = (code == 0) == case.expect_ok and case.expect_output in output
            failures += not ok
            last = output.splitlines()[-1] if output else ""
            print(f"{'OK   ' if ok else 'FALLA'} {case.name}: exit={code} | {last}")
            if not ok:
                print(output)
    print(f"\n{failures} caso(s) con resultado inesperado." if failures else "\nTodos los casos OK.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
