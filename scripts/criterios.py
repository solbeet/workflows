"""Matriz por criterio de la necesidad del PR, contada por script (V22, solbeet/workflows#33).

Lee los criterios de aceptación de la necesidad que cierra el PR (bullets ``- [ ]`` bajo
un encabezado con «criterio»), busca en las líneas que agrega el PR al menos un test
``test_ca_<issue>_<n>_*`` por criterio y cruza con el JUnit de la suite corrida en el job:

- RUNTIME: el criterio pasó contra un ambiente (``resultado.json`` de la verificación en
  staging, ``e2e.criterios``, sin fallos de ese criterio).
- CODE: un test del criterio que agrega el PR pasó en esta corrida de CI.
- SIN-EVIDENCIA: ninguna de las dos.

Resultado: ``verde`` (todo criterio RUNTIME o CODE), ``rojo`` (``sin_tests_corridos`` si
la suite no corrió ningún test, ``criterios_sin_evidencia`` si falta alguno) o ``neutral``
(``no_medido``: sin necesidad vinculada o sin criterios legibles). Nunca usa un modelo.

Este archivo es la fuente: el paso «Matriz por criterio» del job ``criterios`` de
``.github/workflows/gates.yml`` lleva una copia incrustada (los reutilizables corren con
el checkout del repo que llama, ver AGENTS.md). ``scripts/incrustar-criterios.py`` la
actualiza y ``tests/criterios`` falla si difieren. Solo biblioteca estándar, Python 3.10+.

Entrada por entorno: PR_BODY, REPO, API_URL, GH_TOKEN (solo lectura), JUNIT,
PYTEST_CODIGO, RUNTIME_RESULTADO (opcional), MATRIZ_JSON, GITHUB_STEP_SUMMARY,
GITHUB_OUTPUT, GITHUB_WORKSPACE.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

SCHEMA = 1
RUNTIME, CODE, SIN_EVIDENCIA = "RUNTIME", "CODE", "SIN-EVIDENCIA"

_VINCULO = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+(?:([\w.-]+/[\w.-]+))?#(\d+)\b",
    re.IGNORECASE,
)
_ENCABEZADO = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+\[[ xX]\]\s+(.+?)\s*$")
_TEST_CA = re.compile(r"\b(test_ca_(\d+)_(\d+)\w*)")
_CA_RUNTIME = re.compile(r"^CA-(\d+)-(\d+)$", re.IGNORECASE)


# --- Datos --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Necesidad:
    repo: str
    numero: int

    def __str__(self) -> str:
        return f"{self.repo}#{self.numero}"


@dataclass
class FilaCriterio:
    necesidad: str
    issue: int
    n: int
    texto: str
    estado: str
    tests: list[str] = field(default_factory=list)
    motivo: str = ""


@dataclass
class Suite:
    """Lo que corrió la suite: cantidad de tests no salteados y estado por nombre base."""

    corridos: int
    fallados: frozenset[str]
    pasados: frozenset[str]

    def paso(self, nombre: str) -> bool:
        return nombre in self.pasados and nombre not in self.fallados


@dataclass
class Informe:
    resultado: str
    motivo: str
    detalle: str
    necesidades: list[str] = field(default_factory=list)
    criterios: list[FilaCriterio] = field(default_factory=list)
    corridos: int | None = None

    def a_json(self) -> dict:
        datos = asdict(self)
        return {"schema": SCHEMA, **datos}


class IssueIlegible(Exception):
    """La necesidad no se pudo leer (no existe, sin permiso, error de red, es un PR)."""


class DiffIlegible(Exception):
    """No se pudo calcular el diff del PR."""


# --- Interfaces externas ------------------------------------------------------------------


class FuenteIssues(Protocol):
    def cuerpo(self, necesidad: Necesidad) -> str: ...


class FuenteDiff(Protocol):
    def lineas_agregadas(self) -> str: ...


class GitHubIssues:
    """Lee issues con la API REST y un token de solo lectura."""

    def __init__(self, api_url: str, token: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token

    def cuerpo(self, necesidad: Necesidad) -> str:
        url = f"{self.api_url}/repos/{necesidad.repo}/issues/{necesidad.numero}"
        cabeceras = {"Accept": "application/vnd.github+json"}
        if self.token:
            cabeceras["Authorization"] = f"Bearer {self.token}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cabeceras), timeout=30) as r:
                datos = json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise IssueIlegible(f"{necesidad}: {exc}") from exc
        if "pull_request" in datos:
            raise IssueIlegible(f"{necesidad}: es un PR, no una necesidad")
        return datos.get("body") or ""


class GitDiff:
    """Líneas del commit de merge de pull_request contra su base (HEAD^1)."""

    def __init__(self, cwd: str) -> None:
        self.cwd = cwd

    def lineas_agregadas(self) -> str:
        r = subprocess.run(
            ["git", "diff", "--unified=0", "--no-color", "HEAD^1", "HEAD"],
            cwd=self.cwd,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise DiffIlegible(r.stderr.strip() or f"git diff salió con {r.returncode}")
        return r.stdout


# --- Lectura ------------------------------------------------------------------------------


def necesidades_vinculadas(cuerpo_pr: str, repo: str) -> list[Necesidad]:
    """Necesidades que cierra el PR (Closes/Fixes/Resolves #N u owner/repo#N), sin repetir."""
    vistas: list[Necesidad] = []
    for m in _VINCULO.finditer(cuerpo_pr or ""):
        necesidad = Necesidad(m.group(1) or repo, int(m.group(2)))
        if necesidad not in vistas:
            vistas.append(necesidad)
    return vistas


def leer_criterios(cuerpo_issue: str) -> list[str]:
    """Bullets ``- [ ]`` de primer nivel bajo el primer encabezado que dice «criterio»."""
    criterios: list[str] = []
    dentro = False
    for linea in (cuerpo_issue or "").splitlines():
        encabezado = _ENCABEZADO.match(linea.strip())
        if encabezado:
            if dentro:
                break
            dentro = "criterio" in encabezado.group(1).lower()
            continue
        bullet = _BULLET.match(linea) if dentro else None
        if bullet:
            criterios.append(bullet.group(1))
    return criterios


def tests_por_criterio(diff: str) -> dict[tuple[int, int], set[str]]:
    """Nombres ``test_ca_<issue>_<n>*`` en las líneas que agrega el diff."""
    encontrados: dict[tuple[int, int], set[str]] = {}
    for linea in diff.splitlines():
        if not linea.startswith("+") or linea.startswith("+++"):
            continue
        for m in _TEST_CA.finditer(linea):
            encontrados.setdefault((int(m.group(2)), int(m.group(3))), set()).add(m.group(1))
    return encontrados


def leer_junit(ruta: Path) -> Suite | None:
    """Suite desde el JUnit XML de pytest; ``None`` si no hay reporte o no se puede leer."""
    try:
        raiz = ET.parse(ruta).getroot()
    except (ET.ParseError, OSError):
        return None
    corridos = 0
    fallados: set[str] = set()
    pasados: set[str] = set()
    for caso in raiz.iter("testcase"):
        if caso.find("skipped") is not None:
            continue
        corridos += 1
        nombre = caso.get("name", "").split("[", 1)[0]
        malo = caso.find("failure") is not None or caso.find("error") is not None
        (fallados if malo else pasados).add(nombre)
    return Suite(corridos, frozenset(fallados), frozenset(pasados))


def leer_runtime(resultado: object) -> set[tuple[int, int]]:
    """Criterios que pasaron contra un ambiente según ``resultado.json`` (esquema 1)."""
    e2e = resultado.get("e2e") if isinstance(resultado, dict) else None
    if not isinstance(e2e, dict) or e2e.get("estado") != "corrio":
        return set()
    fallados = {f.get("criterio") for f in e2e.get("fallos") or [] if isinstance(f, dict)}
    pasaron: set[tuple[int, int]] = set()
    for criterio in e2e.get("criterios") or []:
        m = _CA_RUNTIME.match(str(criterio))
        if m and criterio not in fallados:
            pasaron.add((int(m.group(1)), int(m.group(2))))
    return pasaron


# --- Decisión -----------------------------------------------------------------------------


def _leer_necesidades(
    cuerpo_pr: str, repo: str, issues: FuenteIssues
) -> tuple[list[Necesidad], dict[Necesidad, list[str]], list[str]]:
    necesidades = necesidades_vinculadas(cuerpo_pr, repo)
    if not necesidades:
        return [], {}, ["sin necesidad vinculada (Closes #N en el cuerpo del PR)"]
    criterios: dict[Necesidad, list[str]] = {}
    problemas: list[str] = []
    for necesidad in necesidades:
        try:
            textos = leer_criterios(issues.cuerpo(necesidad))
        except IssueIlegible as exc:
            problemas.append(f"{necesidad}: no se pudo leer ({exc})")
            continue
        if not textos:
            problemas.append(f"{necesidad}: sin criterios legibles (bullets - [ ] bajo un encabezado con «criterio»)")
        criterios[necesidad] = textos
    return necesidades, criterios, problemas


def _fila(
    necesidad: Necesidad,
    n: int,
    texto: str,
    en_diff: set[str],
    suite: Suite | None,
    runtime: set[tuple[int, int]],
) -> FilaCriterio:
    clave = (necesidad.numero, n)
    tests = sorted(en_diff)
    fila = FilaCriterio(str(necesidad), necesidad.numero, n, texto, SIN_EVIDENCIA, tests)
    if clave in runtime:
        fila.estado = RUNTIME
    elif suite is not None and any(suite.paso(t) for t in tests):
        fila.estado = CODE
    elif tests:
        fila.motivo = f"su prueba no pasó en CI ({', '.join(tests)})"
    else:
        fila.motivo = f"sin prueba test_ca_{necesidad.numero}_{n}_* en el PR"
    return fila


def armar_matriz(
    criterios: dict[Necesidad, list[str]],
    en_diff: dict[tuple[int, int], set[str]],
    suite: Suite | None,
    runtime: set[tuple[int, int]],
) -> list[FilaCriterio]:
    return [
        _fila(necesidad, n, texto, en_diff.get((necesidad.numero, n), set()), suite, runtime)
        for necesidad, textos in criterios.items()
        for n, texto in enumerate(textos, start=1)
    ]


def evaluar(
    *,
    cuerpo_pr: str,
    repo: str,
    issues: FuenteIssues,
    diff: FuenteDiff,
    suite: Suite | None,
    runtime: set[tuple[int, int]],
    codigo_suite: str = "",
) -> Informe:
    necesidades, criterios, problemas = _leer_necesidades(cuerpo_pr, repo, issues)
    try:
        en_diff = tests_por_criterio(diff.lineas_agregadas())
    except DiffIlegible as exc:
        en_diff = {}
        problemas.append(f"no se pudo leer el diff del PR ({exc})")
    filas = armar_matriz(criterios, en_diff, suite, runtime)
    informe = Informe("", "", "", [str(n) for n in necesidades], filas, suite.corridos if suite else None)
    if suite is None or suite.corridos == 0:
        codigo = f" (pytest terminó con código de salida {codigo_suite})" if codigo_suite else ""
        informe.resultado, informe.motivo = "rojo", "sin_tests_corridos"
        informe.detalle = "la suite no corrió ningún test" + codigo
    elif problemas:
        informe.resultado, informe.motivo, informe.detalle = "neutral", "no_medido", "; ".join(problemas)
    elif faltan := [f for f in filas if f.estado == SIN_EVIDENCIA]:
        informe.resultado, informe.motivo = "rojo", "criterios_sin_evidencia"
        informe.detalle = "; ".join(f"criterio {f.n} de {f.necesidad}: {f.motivo}" for f in faltan)
    else:
        informe.resultado, informe.motivo = "verde", "ok"
        informe.detalle = f"{len(filas)} criterios con evidencia"
    return informe


# --- Salida -------------------------------------------------------------------------------


def _celda(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def resumen_markdown(informe: Informe) -> str:
    lineas = [
        "## Criterios de la necesidad",
        "",
        f"**Resultado:** {informe.resultado} (`{informe.motivo}`): {_celda(informe.detalle)}",
        "",
    ]
    if informe.criterios:
        lineas += ["| Necesidad | # | Criterio | Evidencia | Tests del PR |", "|---|---|---|---|---|"]
        for f in informe.criterios:
            tests = ", ".join(f"`{t}`" for t in f.tests) or "—"
            lineas.append(f"| {f.necesidad} | {f.n} | {_celda(f.texto)} | {f.estado} | {tests} |")
        lineas.append("")
    lineas.append(
        "RUNTIME: pasó contra un ambiente · CODE: su test del PR pasó en este CI · SIN-EVIDENCIA: ninguna de las dos."
    )
    return "\n".join(lineas) + "\n"


def _anotar(informe: Informe) -> None:
    nivel = {"verde": "notice", "rojo": "error", "neutral": "warning"}[informe.resultado]
    texto = f"criterios {informe.resultado} ({informe.motivo}): {informe.detalle}"
    print(f"::{nivel}::{texto.replace('%', '%25').replace(chr(10), '%0A')}")


def _leer_json(ruta: str) -> object:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(
    entorno: dict[str, str],
    issues: FuenteIssues | None = None,
    diff: FuenteDiff | None = None,
) -> int:
    runtime_ruta = entorno.get("RUNTIME_RESULTADO", "")
    informe = evaluar(
        cuerpo_pr=entorno.get("PR_BODY", ""),
        repo=entorno["REPO"],
        issues=issues or GitHubIssues(entorno.get("API_URL", "https://api.github.com"), entorno.get("GH_TOKEN", "")),
        diff=diff or GitDiff(entorno.get("GITHUB_WORKSPACE", ".")),
        suite=leer_junit(Path(entorno.get("JUNIT", ""))),
        runtime=leer_runtime(_leer_json(runtime_ruta)) if runtime_ruta else set(),
        codigo_suite=entorno.get("PYTEST_CODIGO", ""),
    )
    Path(entorno["MATRIZ_JSON"]).write_text(
        json.dumps(informe.a_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with open(entorno["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumen:
        resumen.write(resumen_markdown(informe))
    with open(entorno["GITHUB_OUTPUT"], "a", encoding="utf-8") as salida:
        salida.write(f"resultado={informe.resultado}\nmotivo={informe.motivo}\n")
    _anotar(informe)
    return 0


if __name__ == "__main__":
    sys.exit(main(dict(os.environ)))
