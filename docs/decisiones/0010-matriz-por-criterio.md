# 0010 · «No corrió nada» no es verde, y matriz por criterio contada por script

Fecha: 2026-11-03 · Estado: propuesta (fase V de la fábrica, ítem V22, solbeet/workflows#33)

## Contexto

Una suite que no recolecta ningún test termina en verde (o en un código que alguien trata como verde), y un job que se saltea puede quedar aprobado. La tabla criterio ↔ prueba de cada PR la armaba el revisor, que es un modelo: si se equivoca, un criterio sin prueba pasa. Nadie decía, criterio por criterio, qué se probó contra el sistema funcionando y qué no.

## Decisión

Un job nuevo `criterios` en `gates.yml`:

- Corre la suite de `criterios-dir` (por defecto `backend-dir`) con `--junitxml`. Si el JUnit no existe, no se puede leer o no tiene ningún test que no se haya salteado, es **rojo** con `sin_tests_corridos`, salga pytest con 0 o con 5.
- Lee la necesidad que cierra el PR (`Closes #N` en el cuerpo del evento) con el `GITHUB_TOKEN` del job, que solo tiene `contents: read` e `issues: read`. Los criterios son los bullets `- [ ]` de primer nivel bajo el primer encabezado con «criterio».
- Cuenta en las líneas que agrega el PR (`git diff HEAD^1 HEAD`) los nombres `test_ca_<issue>_<n>_*`, la convención de la autoprueba por cambio (`backend/tests/aceptacion/`, que corre dentro del proceso en CI y contra el ambiente con `ACEPTACION_BASE_URL`).
- Matriz: RUNTIME (pasó contra un ambiente según el `resultado.json` de la verificación en staging), CODE (su test del PR pasó en esta corrida), SIN-EVIDENCIA. Verde solo si ningún criterio queda SIN-EVIDENCIA.
- Sin necesidad, sin poder leerla o sin criterios legibles: **neutral** con `no_medido`. GitHub Actions no tiene conclusión neutral para un job (solo la API de checks, que pide `checks: write`, un token de escritura): el job termina en failure para que nunca cuente como verde, y el motivo queda en la anotación, el resumen y el artefacto.
- Publica la matriz en el resumen del job y como artefacto JSON (esquema 1), que leen el revisor y la ficha.
- Informativo en esta versión: no figura como requerido en `examples/` y cada repo decide cuándo exigirlo.

La lógica vive en `scripts/criterios.py` (biblioteca estándar, con GitHub y git detrás de interfaces y fakes en `tests/criterios`). Como los reutilizables corren con el checkout del repo que llama, el paso lleva una **copia incrustada**: `scripts/incrustar-criterios.py` la genera y un test falla si difiere del script.

## Alternativas descartadas

- Que el revisor arme la tabla: es un modelo; el conteo tiene que ser determinista.
- Bajar el script con `actions/checkout` de este repo: un reutilizable no sabe con qué ref lo llamaron (`github.job_workflow_sha` llega vacío; la vía con el token OIDC pide `id-token: write`).
- Leer el JUnit del job `cobertura-cambio`: acopla dos jobs, y si ese falla por cobertura, `criterios` queda sin datos. Se paga una corrida más de la suite.
- Contar los `test_ca_` de todo el repo y no del diff: el criterio pide la prueba en el PR que cierra la necesidad.

## Consecuencias

- **Permiso nuevo en el caller: `issues: read`.** Si el caller no lo da, GitHub rechaza el workflow entero, también los cuatro gates existentes. El ADR 0002 (§4) clasifica pedir permisos nuevos como incompatible (versión mayor). Callers conocidos a 2026-11-03 en las orgs `solbeet` y `solbeet-pruebas`: solo la plantilla (`verificacion.yml.jinja`), que ya da `issues: read`. Publicarlo en `v1` o en `v2` lo decide quien taggea; el ejemplo y el selftest ya dan el permiso.
- Una corrida más de la suite por PR.
- RUNTIME no aparece en el PR: el cambio llega a staging después del merge. La ficha rearma la matriz corriendo el script con `RUNTIME_RESULTADO`.
- Un PR sin `Closes` (dependabot, cambios de mantenimiento) queda en failure con `no_medido`: es lo que pide «nunca verde», y es la razón para que entre como informativo.
- Compatible con el gate por workflow (solbeet/workflows#34): `criterios` es un job más que el gate puede poner en su `needs`; no usa `continue-on-error` ni `!cancelled()`.
