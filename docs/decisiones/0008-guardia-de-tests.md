# 0008 · Guardia de tests determinista con dale humano

Fecha: 2026-10-13 · Estado: propuesta (fase V de la fábrica, ítem V2)

## Contexto

En ImpossibleBench (CMU y Anthropic, oct-2025) los modelos más capaces hacen más trampa cuando un test no pasa, y en Claude más del 79% de las trampas son editar el test. Un juez LLM detecta solo entre el 42% y el 65%. Con merge automático, un PR que debilita un test para quedar en verde entra sin que nadie lo vea.

## Decisión

Un workflow reutilizable `guardia-tests.yml` con el job `tests`:

- Compara la base y el PR por árbol sintáctico en Python (funciones `test*` y métodos `test*` de clases `Test*`) y por líneas en otros lenguajes.
- Frena: borrar un test o un archivo de tests; **debilitar** un test existente (perder o cambiar un assert, `self.assert*`/`mock.assert_*`, `pytest.raises`/`warns` o un caso de `parametrize`); saltear tests existentes (skip/xfail en un test que estaba, `pytestmark`, skip en `conftest.py`, `.only`/`.skip`/`xit`); tocar un archivo existente de `tests/aceptacion/`.
- No frena cambios de setup, fixtures o helpers. La primera versión frenaba cualquier cambio a un test existente; reproducida sobre 30 PRs reales de la fábrica frenaba 18, casi todos ajustes legítimos. Con la regla de «debilitar» frena 7, y en los 7 el PR cambió de verdad un valor esperado o sacó un test. Cambiar un helper para debilitar un test queda como riesgo aceptado: lo mira el revisor.
- Vía de escape: label `tests-con-dale` puesto por una persona que no es el autor del PR ni un bot, después del último push. El «último push» se toma de la primera corrida de Actions del commit (fecha del servidor de GitHub, no de git, que el autor controla). Si el PR cambia después, el label deja de valer.

## Alternativas descartadas

- Juez LLM sobre el diff de tests: detecta la mitad y no es determinista.
- Tests ocultos para el agente: frenan casi toda la trampa pero también bajan el éxito legítimo (ImpossibleBench); quedan para la fase V4 (escenarios ocultos).
- Marca puesta por el propio agente («pido dale»): el agente la pondría siempre. El label lo tiene que poner otra persona.
- Que el revisor-agente acepte la justificación: es otro LLM; la decisión queda en una persona.

## Consecuencias

- Con la tasa medida, alrededor de 1 de cada 4 PRs de dogfooding necesitaría el label: es fricción real para la persona y conviene medirla antes de marcar el check como requerido (la investigación pide 10 PRs sin falsos positivos).
- Permisos de lectura extra en el caller (`pull-requests`, `issues`, `actions`), sin escritura.
- Se integra con V4: los tests de aceptación que escribe `construir` en `tests/aceptacion/` quedan protegidos una vez mergeados.
