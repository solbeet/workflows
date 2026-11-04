"""Tests de scripts/criterios.py: matriz por criterio y «no corrió nada» no es verde (V22).

Cada criterio de solbeet/workflows#33 tiene su test ``test_ca_33_<n>_*``: el propio job
``criterios`` los cuenta cuando corre sobre el PR de este repo (selftest).

GitHub y git van detrás de interfaces; acá se usan fakes, sin red ni repos reales.

Uso (desde la raíz del repo):

    uv run --directory tests/criterios --frozen pytest
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("criterios", ROOT / "scripts/criterios.py")
assert _spec and _spec.loader
criterios = importlib.util.module_from_spec(_spec)
sys.modules["criterios"] = criterios
_spec.loader.exec_module(criterios)

REPO = "org/app"

ISSUE_4_CRITERIOS = textwrap.dedent(
    """\
    ## Problema

    - [ ] esto no es un criterio

    ## Criterios de aceptación

    - [ ] Dado A, cuando B, entonces C.
    - [ ] Dado D, cuando E, entonces F.
    - [x] Dado G, cuando H, entonces I.
    - [ ] Dado J, cuando K, entonces L.
      - [ ] un sub-bullet no cuenta

    ## Fuera de alcance

    - [ ] tampoco esto
    """
)


class FakeIssues:
    """Issues en memoria; ``None`` simula un issue que no se puede leer."""

    def __init__(self, cuerpos: dict[str, str | None]) -> None:
        self.cuerpos = cuerpos
        self.leidos: list[str] = []

    def cuerpo(self, necesidad: criterios.Necesidad) -> str:
        clave = str(necesidad)
        self.leidos.append(clave)
        valor = self.cuerpos.get(clave)
        if valor is None:
            raise criterios.IssueIlegible(f"{clave}: 404")
        return valor


class FakeDiff:
    def __init__(self, texto: str) -> None:
        self.texto = texto

    def lineas_agregadas(self) -> str:
        return self.texto


def junit(tmp_path: pathlib.Path, casos: dict[str, str]) -> pathlib.Path:
    """JUnit XML como el de pytest: ``casos`` = nombre -> pasa | falla | saltea."""
    filas = []
    for nombre, estado in casos.items():
        hijo = {"pasa": "", "falla": "<failure message='x'/>", "saltea": "<skipped message='x'/>"}[estado]
        filas.append(f'<testcase classname="tests.test_x" name="{nombre}">{hijo}</testcase>')
    ruta = tmp_path / "junit.xml"
    ruta.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{len(casos)}">'
        f"{''.join(filas)}</testsuite></testsuites>"
    )
    return ruta


def diff_con(*nombres: str) -> str:
    return "".join(f"+def {n}():\n+    assert True\n" for n in nombres)


def evaluar(tmp_path, *, cuerpo_pr="Closes #7", issues=None, diff="", casos=None, runtime=None):
    suite = criterios.leer_junit(junit(tmp_path, casos)) if casos is not None else None
    return criterios.evaluar(
        cuerpo_pr=cuerpo_pr,
        repo=REPO,
        issues=issues or FakeIssues({f"{REPO}#7": ISSUE_4_CRITERIOS}),
        diff=FakeDiff(diff),
        suite=suite,
        runtime=runtime or set(),
    )


TRES = ("test_ca_7_1_a", "test_ca_7_2_b", "test_ca_7_3_c")
CUATRO = (*TRES, "test_ca_7_4_d")


# --- Criterio 1: una suite que no corrió ningún test es rojo ------------------------------


@pytest.mark.parametrize("casos", [{}, {"test_x": "saltea", "test_y": "saltea"}], ids=["vacia", "todo-salteado"])
def test_ca_33_1_suite_sin_tests_corridos_da_rojo(tmp_path, casos):
    informe = evaluar(tmp_path, diff=diff_con(*CUATRO), casos=casos)
    assert informe.resultado == "rojo"
    assert informe.motivo == "sin_tests_corridos"


def test_ca_33_1_sin_reporte_de_la_suite_da_rojo(tmp_path):
    informe = evaluar(tmp_path, diff=diff_con(*CUATRO), casos=None)
    assert (informe.resultado, informe.motivo) == ("rojo", "sin_tests_corridos")


def test_ca_33_1_reporte_ilegible_cuenta_como_sin_tests(tmp_path):
    ruta = tmp_path / "roto.xml"
    ruta.write_text("<testsuites><testsuite")
    assert criterios.leer_junit(ruta) is None
    assert criterios.leer_junit(tmp_path / "no-existe.xml") is None


@pytest.mark.parametrize("codigo", ["0", "5"])
def test_ca_33_1_main_rojo_con_salida_0_o_5_de_pytest(tmp_path, codigo):
    entorno = entorno_main(tmp_path, casos={}, pytest_codigo=codigo)
    assert criterios.main(entorno, issues=FakeIssues({f"{REPO}#7": ISSUE_4_CRITERIOS}), diff=FakeDiff("")) == 0
    salidas = leer_output(tmp_path)
    assert salidas["resultado"] == "rojo"
    assert salidas["motivo"] == "sin_tests_corridos"
    assert f"código de salida {codigo}" in json.loads((tmp_path / "matriz.json").read_text())["detalle"]


# --- Criterio 2: criterio sin prueba → rojo nombrándolo -----------------------------------


def test_ca_33_2_criterio_sin_prueba_da_rojo_y_lo_nombra(tmp_path):
    informe = evaluar(tmp_path, diff=diff_con(*TRES), casos=dict.fromkeys(TRES, "pasa"))
    assert informe.resultado == "rojo"
    assert informe.motivo == "criterios_sin_evidencia"
    assert "criterio 4 de org/app#7" in informe.detalle
    assert "criterio 3" not in informe.detalle
    assert [c.estado for c in informe.criterios] == ["CODE", "CODE", "CODE", "SIN-EVIDENCIA"]


def test_ca_33_2_prueba_que_no_paso_en_ci_no_cuenta(tmp_path):
    casos = {**dict.fromkeys(TRES, "pasa"), "test_ca_7_4_d": "falla"}
    informe = evaluar(tmp_path, diff=diff_con(*CUATRO), casos=casos)
    assert informe.resultado == "rojo"
    assert "criterio 4 de org/app#7" in informe.detalle
    assert "no pasó" in informe.detalle


def test_ca_33_2_prueba_que_no_esta_en_el_diff_no_cuenta(tmp_path):
    # La suite la corre, pero el PR no la agrega: el script cuenta lo que trae el diff.
    informe = evaluar(tmp_path, diff=diff_con(*TRES), casos=dict.fromkeys(CUATRO, "pasa"))
    assert informe.resultado == "rojo"
    assert "criterio 4 de org/app#7" in informe.detalle


# --- Criterio 3: todos con prueba → verde, matriz en el resumen y en JSON -----------------


def test_ca_33_3_todos_los_criterios_con_prueba_da_verde(tmp_path):
    informe = evaluar(tmp_path, diff=diff_con(*CUATRO), casos=dict.fromkeys(CUATRO, "pasa"))
    assert (informe.resultado, informe.motivo) == ("verde", "ok")
    assert [c.tests for c in informe.criterios] == [[n] for n in CUATRO]


def test_ca_33_3_parametrizado_cuenta_si_ningun_caso_falla(tmp_path):
    casos = {**dict.fromkeys(TRES, "pasa"), "test_ca_7_4_d[a]": "pasa", "test_ca_7_4_d[b]": "pasa"}
    assert evaluar(tmp_path, diff=diff_con(*CUATRO), casos=casos).resultado == "verde"
    casos["test_ca_7_4_d[b]"] = "falla"
    assert evaluar(tmp_path, diff=diff_con(*CUATRO), casos=casos).resultado == "rojo"


def test_ca_33_3_main_publica_resumen_y_json(tmp_path):
    entorno = entorno_main(tmp_path, casos=dict.fromkeys(CUATRO, "pasa"))
    issues = FakeIssues({f"{REPO}#7": ISSUE_4_CRITERIOS})
    assert criterios.main(entorno, issues=issues, diff=FakeDiff(diff_con(*CUATRO))) == 0
    assert leer_output(tmp_path) == {"resultado": "verde", "motivo": "ok"}
    datos = json.loads((tmp_path / "matriz.json").read_text())
    assert datos["schema"] == 1
    assert datos["resultado"] == "verde"
    assert datos["necesidades"] == ["org/app#7"]
    assert [(c["n"], c["estado"], c["tests"]) for c in datos["criterios"]] == [
        (i + 1, "CODE", [n]) for i, n in enumerate(CUATRO)
    ]
    resumen = (tmp_path / "summary.md").read_text()
    assert "## Criterios de la necesidad" in resumen
    assert "| org/app#7 | 4 | Dado J, cuando K, entonces L. | CODE | `test_ca_7_4_d` |" in resumen


# --- Criterio 4: RUNTIME / CODE / SIN-EVIDENCIA -------------------------------------------


RESULTADO_STAGING = {
    "schema": 1,
    "e2e": {
        "estado": "corrio",
        "criterios": ["CA-7-1", "CA-7-3"],
        "fallos": [{"criterio": "CA-7-3", "test": "test_ca_7_3_c", "mensaje": "x"}],
    },
}


def test_ca_33_4_runtime_code_y_sin_evidencia(tmp_path):
    runtime = criterios.leer_runtime(RESULTADO_STAGING)
    assert runtime == {(7, 1)}  # CA-7-3 tuvo un fallo en staging: no es resultado 0
    casos = dict.fromkeys(("test_ca_7_1_a", "test_ca_7_2_b", "test_ca_7_3_c"), "pasa")
    informe = evaluar(tmp_path, diff=diff_con(*TRES), casos=casos, runtime=runtime)
    assert [c.estado for c in informe.criterios] == ["RUNTIME", "CODE", "CODE", "SIN-EVIDENCIA"]


def test_ca_33_4_runtime_alcanza_sin_prueba_en_el_diff(tmp_path):
    runtime = {(7, 1), (7, 2), (7, 3), (7, 4)}
    informe = evaluar(tmp_path, diff="", casos={"test_otro": "pasa"}, runtime=runtime)
    assert [c.estado for c in informe.criterios] == ["RUNTIME"] * 4
    assert informe.resultado == "verde"


@pytest.mark.parametrize(
    "resultado",
    [{}, {"e2e": {"estado": "ausente", "motivo": "x"}}, {"e2e": "roto"}, []],
    ids=["sin-e2e", "ausente", "roto", "no-dict"],
)
def test_ca_33_4_runtime_sin_corrida_no_da_evidencia(resultado):
    assert criterios.leer_runtime(resultado) == set()


def test_ca_33_4_main_lee_el_resultado_de_staging(tmp_path):
    ruta = tmp_path / "resultado.json"
    ruta.write_text(json.dumps(RESULTADO_STAGING))
    entorno = entorno_main(tmp_path, casos=dict.fromkeys(TRES, "pasa"))
    entorno["RUNTIME_RESULTADO"] = str(ruta)
    criterios.main(entorno, issues=FakeIssues({f"{REPO}#7": ISSUE_4_CRITERIOS}), diff=FakeDiff(diff_con(*TRES)))
    datos = json.loads((tmp_path / "matriz.json").read_text())
    assert [c["estado"] for c in datos["criterios"]] == ["RUNTIME", "CODE", "CODE", "SIN-EVIDENCIA"]


# --- Criterio 5: sin necesidad o criterios ilegibles → neutral no_medido ------------------


@pytest.mark.parametrize(
    ("cuerpo_pr", "cuerpos", "en_detalle"),
    [
        ("Arreglo un typo.", {}, "sin necesidad vinculada"),
        ("", {}, "sin necesidad vinculada"),
        ("Closes #7", {f"{REPO}#7": None}, "no se pudo leer"),
        ("Closes #7", {f"{REPO}#7": "## Problema\n\n- [ ] algo\n"}, "sin criterios legibles"),
        ("Closes #7", {f"{REPO}#7": "## Criterios de aceptación\n\nUn párrafo sin bullets.\n"}, "sin criterios"),
        ("Closes #7\nCloses #8", {f"{REPO}#7": ISSUE_4_CRITERIOS, f"{REPO}#8": None}, "org/app#8"),
    ],
    ids=["sin-closes", "cuerpo-vacio", "issue-ilegible", "sin-encabezado", "sin-bullets", "una-de-dos-ilegible"],
)
def test_ca_33_5_no_medido_da_neutral(tmp_path, cuerpo_pr, cuerpos, en_detalle):
    informe = evaluar(
        tmp_path,
        cuerpo_pr=cuerpo_pr,
        issues=FakeIssues(cuerpos),
        diff=diff_con(*CUATRO),
        casos=dict.fromkeys(CUATRO, "pasa"),
    )
    assert (informe.resultado, informe.motivo) == ("neutral", "no_medido")
    assert en_detalle in informe.detalle


def test_ca_33_5_main_neutral_nunca_verde(tmp_path):
    entorno = entorno_main(tmp_path, casos=dict.fromkeys(CUATRO, "pasa"))
    entorno["PR_BODY"] = "sin vínculo"
    criterios.main(entorno, issues=FakeIssues({}), diff=FakeDiff(diff_con(*CUATRO)))
    assert leer_output(tmp_path) == {"resultado": "neutral", "motivo": "no_medido"}


# --- Piezas: vínculos, criterios y nombres en el diff -------------------------------------


def test_necesidades_vinculadas_mismo_repo_y_otro_repo():
    cuerpo = "Closes #7\nfixes otra/cosa#12\nResolves: #7\nRelacionado con #99\n`Closes #5` también cuenta"
    assert [str(n) for n in criterios.necesidades_vinculadas(cuerpo, REPO)] == [
        "org/app#7",
        "otra/cosa#12",
        "org/app#5",
    ]


def test_leer_criterios_solo_bullets_bajo_el_encabezado():
    assert criterios.leer_criterios(ISSUE_4_CRITERIOS) == [
        "Dado A, cuando B, entonces C.",
        "Dado D, cuando E, entonces F.",
        "Dado G, cuando H, entonces I.",
        "Dado J, cuando K, entonces L.",
    ]


def test_tests_por_criterio_solo_lineas_agregadas():
    diff = (
        "+++ b/tests/test_x.py\n"
        "+def test_ca_7_1_a():\n"
        "-def test_ca_7_2_borrado():\n"
        " def test_ca_7_3_contexto():\n"
        "+test('test_ca_7_4_js', () => {})\n"
    )
    assert criterios.tests_por_criterio(diff) == {(7, 1): {"test_ca_7_1_a"}, (7, 4): {"test_ca_7_4_js"}}


def test_prueba_de_otro_issue_no_cuenta(tmp_path):
    otro = "## Criterios\n\n- [ ] Dado X.\n"
    informe = evaluar(
        tmp_path,
        issues=FakeIssues({f"{REPO}#7": otro}),
        diff=diff_con("test_ca_8_1_a"),
        casos={"test_ca_8_1_a": "pasa"},
    )
    assert informe.resultado == "rojo"
    assert "criterio 1 de org/app#7" in informe.detalle


# --- helpers del main ---------------------------------------------------------------------


def entorno_main(tmp_path, *, casos, pytest_codigo="0"):
    for nombre in ("summary.md", "output.txt"):
        (tmp_path / nombre).write_text("")
    return {
        "PR_BODY": "Closes #7",
        "REPO": REPO,
        "JUNIT": str(junit(tmp_path, casos)),
        "PYTEST_CODIGO": pytest_codigo,
        "MATRIZ_JSON": str(tmp_path / "matriz.json"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
    }


def leer_output(tmp_path) -> dict[str, str]:
    lineas = (tmp_path / "output.txt").read_text().splitlines()
    return dict(linea.split("=", 1) for linea in lineas if "=" in linea)


def test_tests_por_criterio_solo_cuenta_definiciones():
    # Un comentario o un doc que nombra un test existente no es una prueba que agregue el PR.
    diff = (
        "+# ver test_ca_7_1_viejo, que ya pasaba\n"
        "+Cubierto por `test_ca_7_2_otro` en el README.\n"
        "+    async def test_ca_7_3_asincrono():\n"
        "+  it(\"test_ca_7_4_js\", async () => {})\n"
    )
    assert criterios.tests_por_criterio(diff) == {(7, 3): {"test_ca_7_3_asincrono"}, (7, 4): {"test_ca_7_4_js"}}
