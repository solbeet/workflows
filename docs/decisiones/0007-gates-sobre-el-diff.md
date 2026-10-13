# 0007 · Gates de verificación sobre el diff del PR

Fecha: 2026-10-13 · Estado: propuesta (fase V de la fábrica, ítem V1)

## Contexto

La fábrica pasa a mergear solo los PRs de zona baja cuando el revisor aprueba y los checks requeridos están en verde (ADR 0004 §13 de `solbeet-docs`). Hasta acá esos checks eran lint, tipos y tests (`python-react.yml`) e higiene del PR (`pr-hygiene.yml`). Nada medía si el cambio estaba probado, si una migración era destructiva, si la API seguía cumpliendo su OpenAPI ni si entraba una dependencia vulnerable. La investigación `estrategia/investigacion/verificacion-continua.md` (§1.2 y §1.5) propone esos cuatro gates.

Los pilotos incluyen un producto existente sin tests. Un gate que mide todo el repo (cobertura total, todas las vulnerabilidades, todo el contrato) queda en rojo desde el primer día y no sirve como señal.

## Decisión

Un workflow reutilizable nuevo, `gates.yml`, con cuatro jobs (`cobertura-cambio`, `migraciones`, `contrato`, `dependencias`) que **solo frenan lo que introduce el PR**:

- Cada job usa el commit de merge de `pull_request` y compara contra la base (`HEAD^1`, en un `git worktree` aparte).
- Lo que ya fallaba en la base se reporta como aviso en el resumen del job.
- Cobertura: `diff-cover` sobre las líneas cambiadas, no la cobertura total.
- Migraciones: squawk solo sobre el SQL de las revisiones nuevas; pytest-alembic se compara contra la base.
- Contrato: Schemathesis corre sobre la base y sobre el PR con generación determinista. Como la generación igual varía entre corridas (estado de la base, tiempos), antes de declarar un fallo nuevo se reenvían a la base las mismas peticiones que dieron 5xx y se insiste con más casos en esa operación. Un falso «heredado» deja pasar algo; un falso «nuevo» frena un PR sano, que es lo que más rompe la confianza en el check.
- Dependencias: OSV-Scanner sobre los lockfiles de los dos árboles; frena solo vulnerabilidades nuevas, altas o críticas y con versión arreglada.
- Los secretos ya los frena `pr-hygiene / secret-scan` (gitleaks); no se duplican.
- Herramientas fijadas: binarios con SHA-256 (ADR 0003) y paquetes de PyPI con versión exacta. Las variables de versión se llaman `VERSION_<X>` porque uvicorn y Schemathesis leen variables con su prefijo como opciones (`UVICORN_VERSION` se toma como `--version`).

## Alternativas descartadas

- Agregar los jobs a `python-react.yml`: cambiaría el comportamiento de los clientes que ya usan `@v1` (checks nuevos que pueden fallar en PRs existentes). Un workflow aparte es opt-in.
- Codecov u otros servicios: pagos o con datos fuera de GitHub; diff-cover alcanza.
- Pact para el contrato: tiene sentido con equipos y repos separados; en un monorepo alcanza con el OpenAPI que FastAPI ya genera.
- Gates sobre todo el repo: inservibles en código heredado.

## Consecuencias

- `v1.4.0` (compatible): `v1` se mueve al publicarla.
- Cada PR corre la suite de tests una vez más (cobertura) y levanta la app dos veces (contrato): unos minutos de runner por PR.
- El contrato depende de que la app levante con `DATABASE_URL` y `alembic upgrade head`; si no, el job falla con el log de uvicorn.
- Medido en `solbeet-pruebas/app-prueba`: un PR por caso que debe fallar y contrapruebas en verde (ver `docs/estado.md`).
