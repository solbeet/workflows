"""Prueba los pasos de agents-md.yml sin depender de GitHub ni del repo privado del método.

Extrae el script de cada paso del job ``verificar`` y lo corre contra carpetas temporales con un
``AGENTS.md`` de ejemplo. La red se reemplaza con un ``uvx`` falso en el PATH que registra cómo lo
llamaron y devuelve el código que el caso pide. También revisa el contrato del workflow y del
ejemplo (acciones fijadas por SHA, runner configurable, permisos mínimos, secreto pasado).

Uso (desde la raíz del repo):

    uv run --no-project --with pyyaml==6.0.2 python tests/agents_md/test_agents_md.py

Sale con código 0 si todos los casos dan el resultado esperado y 1 si no.
"""

from __future__ import annotations

import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass

import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github/workflows/agents-md.yml"
EJEMPLO = RAIZ / "examples/agents-md.yml"
TOKEN = "ghs_token_de_prueba_no_real"

BLOQUE = (
    "# AGENTS.md\n\ntexto del repo\n\n"
    "<!-- metodo:agents-md version={version} · generado con `metodo agents-md generar`, no editar -->\n"
    "## Cómo se programa\n\ncuerpo\n"
    "<!-- /metodo:agents-md -->\n"
)
UVX_FALSO = '#!/bin/sh\nprintf "%s\\n" "$@" > "$UVX_ARGS"\nexit "${UVX_SALIDA:-0}"\n'


@dataclass
class Caso:
    """Un caso: qué paso correr, qué hay en AGENTS.md y qué se espera."""

    nombre: str
    paso: str
    ok: bool
    agents: str | None = None
    env: dict[str, str] | None = None
    salida_contiene: str = ""
    verificar: Callable[[str, pathlib.Path], bool] | None = None


def pasos() -> dict[str, dict[str, str]]:
    """Pasos del job ``verificar`` por nombre."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return {p["name"]: p for p in workflow["jobs"]["verificar"]["steps"]}


def correr(paso: dict[str, str], cwd: pathlib.Path, env: dict[str, str]) -> tuple[int, str]:
    """Ejecuta el ``run`` de un paso con las mismas opciones que usa GitHub con bash."""
    cmd = ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", paso["run"]]
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True, check=False)
    return r.returncode, (r.stdout + r.stderr).strip()


def casos() -> list[Caso]:
    """Casos de los dos pasos con lógica propia."""
    leer = "Leer la versión que declara AGENTS.md"
    verif = "Verificar el bloque"

    def llamada_correcta(_salida: str, args: pathlib.Path) -> bool:
        texto = args.read_text()
        return (
            "--from" in texto
            and f"git+https://x-access-token:{TOKEN}@github.com/solbeet/solbeet-metodo@v1.6.0" in texto
            and "metodo\nagents-md\nverificar" in texto
        )

    def sin_filtrar_token(salida: str, _args: pathlib.Path) -> bool:
        return TOKEN not in salida

    return [
        Caso("lee la versión del bloque", leer, True, BLOQUE.format(version="1.6.0"), salida_contiene="1.6.0"),
        Caso("sin AGENTS.md falla", leer, False, None, salida_contiene="AGENTS.md"),
        Caso("sin bloque falla nombrando el archivo", leer, False, "# AGENTS.md\n", salida_contiene="AGENTS.md"),
        Caso("version=actual no sirve fuera del método", leer, False, BLOQUE.format(version="actual"), salida_contiene="actual"),
        Caso("versión mal formada falla", leer, False, BLOQUE.format(version="1.6"), salida_contiene="X.Y.Z"),
        Caso("llama a uvx con el tag declarado y el token", verif, True, env={"VERSION": "1.6.0"}, verificar=llamada_correcta),
        Caso("sin token es no_medido (3) y no llama a uvx", verif, False, env={"VERSION": "1.6.0", "GH_TOKEN": ""}, salida_contiene="no_medido"),
        Caso("propaga el rojo del check", verif, False, env={"VERSION": "1.6.0", "UVX_SALIDA": "1"}),
        Caso("propaga no_medido del check", verif, False, env={"VERSION": "1.6.0", "UVX_SALIDA": "3"}),
        Caso("el token no se imprime", verif, True, env={"VERSION": "1.6.0"}, verificar=sin_filtrar_token),
    ]


def correr_caso(caso: Caso, raiz: pathlib.Path) -> tuple[bool, int, str]:
    """Arma la carpeta del caso, corre el paso y compara con lo esperado."""
    cwd = pathlib.Path(tempfile.mkdtemp(dir=raiz))
    if caso.agents is not None:
        (cwd / "AGENTS.md").write_text(caso.agents)
    bin_dir = cwd.parent / f"bin-{cwd.name}"
    bin_dir.mkdir()
    uvx = bin_dir / "uvx"
    uvx.write_text(UVX_FALSO)
    uvx.chmod(uvx.stat().st_mode | stat.S_IXUSR)
    args = cwd.parent / f"args-{cwd.name}"
    salida_gh = cwd.parent / f"out-{cwd.name}"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "UVX_ARGS": str(args),
        "GITHUB_OUTPUT": str(salida_gh),
        "GH_TOKEN": TOKEN,
        **(caso.env or {}),
    }
    codigo, salida = correr(pasos()[caso.paso], cwd, env)
    ok = (codigo == 0) == caso.ok and caso.salida_contiene in (salida + salida_gh_texto(salida_gh))
    if ok and caso.verificar is not None:
        ok = caso.verificar(salida, args)
    if caso.nombre.startswith("sin token"):
        ok = ok and not args.exists() and codigo == 3
    if caso.nombre == "propaga no_medido del check":
        ok = ok and codigo == 3
    return ok, codigo, salida


def salida_gh_texto(ruta: pathlib.Path) -> str:
    """Contenido de GITHUB_OUTPUT (vacío si el paso no escribió nada)."""
    return ruta.read_text() if ruta.exists() else ""


def contrato() -> list[tuple[str, bool]]:
    """Revisiones estáticas del workflow reutilizable y del ejemplo."""
    texto = WORKFLOW.read_text()
    workflow = yaml.safe_load(texto)
    llamada = (workflow.get("on") or workflow[True])["workflow_call"]
    usos = re.findall(r"uses:\s*(\S+)", texto)
    ejemplo = yaml.safe_load(EJEMPLO.read_text())
    job = next(iter(ejemplo["jobs"].values()))
    return [
        ("todas las acciones fijadas por sha de 40 caracteres", bool(usos) and all(re.search(r"@[0-9a-f]{40}$", u) for u in usos)),
        ("input runner con default ubuntu-latest", llamada["inputs"]["runner"]["default"] == "ubuntu-latest"),
        ("runs-on sale del input runner", "inputs.runner || 'ubuntu-latest'" in texto),
        ("permisos mínimos: solo contents read", workflow["permissions"] == {"contents": "read"}),
        ("el job se llama verificar (contrato del nombre del check)", "verificar" in workflow["jobs"]),
        ("pide el secreto de lectura del método", "METODO_LECTURA_TOKEN" in llamada["secrets"]),
        ("el ejemplo llama a @v1 y pasa el secreto", job["uses"].endswith("/agents-md.yml@v1") and "METODO_LECTURA_TOKEN" in job["secrets"]),
        ("el ejemplo no usa pull_request_target", "pull_request_target" not in EJEMPLO.read_text()),
    ]


def main() -> int:
    """Corre los casos y el contrato; imprime OK/FALLA por cada uno."""
    fallas = 0
    with tempfile.TemporaryDirectory() as tmp:
        for caso in casos():
            ok, codigo, salida = correr_caso(caso, pathlib.Path(tmp))
            fallas += not ok
            ultima = salida.splitlines()[-1] if salida else ""
            print(f"{'OK   ' if ok else 'FALLA'} {caso.nombre}: exit={codigo} | {ultima}")
    for nombre, ok in contrato():
        fallas += not ok
        print(f"{'OK   ' if ok else 'FALLA'} contrato: {nombre}")
    print(f"\n{fallas} caso(s) con resultado inesperado." if fallas else "\nTodos los casos OK.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
