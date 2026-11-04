#!/usr/bin/env python3
"""Copia scripts/criterios.py al paso «Matriz por criterio» del job criterios de gates.yml.

Los workflows reutilizables corren con el checkout del repo que llama, así que el job no
puede leer scripts/ de este repo: lleva el script incrustado. Este archivo es la única
forma de actualizar esa copia; tests/criterios falla si difiere del script.

Uso (desde la raíz del repo): python3 scripts/incrustar-criterios.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATES = ROOT / ".github/workflows/gates.yml"
SCRIPT = ROOT / "scripts/criterios.py"
PASO = "      - name: Matriz por criterio"
SANGRIA = " " * 10


def incrustar(yaml_texto: str, script: str) -> str:
    """Reemplaza el bloque ``run: |`` del paso por el script, con la sangría del bloque."""
    lineas = yaml_texto.split("\n")
    inicio = lineas.index(PASO)
    run = next(i for i in range(inicio, len(lineas)) if lineas[i].strip() == "run: |")
    fin = run + 1
    while fin < len(lineas) and (lineas[fin] == "" or lineas[fin].startswith(SANGRIA)):
        fin += 1
    while lineas[fin - 1] == "":
        fin -= 1
    bloque = [SANGRIA + linea if linea else "" for linea in script.rstrip("\n").split("\n")]
    return "\n".join(lineas[: run + 1] + bloque + lineas[fin:])


def main() -> int:
    GATES.write_text(incrustar(GATES.read_text(), SCRIPT.read_text()))
    print(f"{SCRIPT.relative_to(ROOT)} incrustado en {GATES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
