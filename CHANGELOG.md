# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado [semver](https://semver.org/lang/es/) con tag mayor móvil (ver README, "Versionado").

## [1.7.0] - sin publicar

Sin tag publicado: se etiqueta al mergear.

### Agregado

- `imagen.yml`: construcción nativa por arquitectura (fase C, ítem C4, solbeet/workflows#22). Inputs `runner-amd64` y `runner-arm64`; con runner para cada plataforma, cada una se construye en el suyo y el índice multi-arch se arma con `docker buildx imagetools create`. Sin `runner-arm64` sigue QEMU como en v1.6.0. El job que ven los callers (`imagen`), los tags y las anotaciones no cambian. Jobs nuevos: `plan` y `construir (linux-<arq>)`.
- `tests/imagen/test_imagen_plan.py` (9 casos de la decisión nativo/QEMU, en `selftest / hygiene-logic`).
- Input `runner` (string, default `ubuntu-latest`) en `python-react.yml`, `pr-hygiene.yml`, `claude-review.yml`, `gates.yml`, `guardia-tests.yml`, `rojo-verde.yml` e `imagen.yml` (fase C, ítem C3, solbeet/workflows#21). Sin pasarlo, el comportamiento es el de v1.6.0; los nombres de jobs y checks no cambian. Vacío cae a `ubuntu-latest`. Ver README, «Elegir dónde corre».
- `selftest.yml` llama a `ci-postgres` con `runner: ubuntu-24.04` para probar un valor distinto del default.

### Corregido

- `imagen.yml`: en modo nativo, los digests se bajan por nombre exacto (`digests-<imagen>-linux-amd64`, `digests-<imagen>-linux-arm64`, armados por el job `plan` desde la matriz) y no con `digests-<imagen>-*`, que también casaba con los de otra imagen cuyo nombre empiece igual (`app` y `app-web`) y metía digests ajenos en el índice. Además el paso que arma el índice verifica que se bajó un digest por plataforma. Casos nuevos en `tests/imagen/test_imagen_plan.py`.

## [1.6.0] - 2026-10-14

Sin tag publicado: se etiqueta al mergear #14 (`rojo-verde.yml`), que entra después del arreglo de la guardia (#15).

### Agregado

- `rojo-verde.yml` (fase V, ítem V3, solbeet/workflows#10): job `rojo-verde` que corre los tests nuevos del PR contra la base (tienen que fallar) y contra el PR (tienen que pasar); tabla en el resumen del job; label `tests-con-dale` para tests de caracterización.
- `examples/rojo-verde.yml` y `tests/rojo_verde/test_rojo_verde.py` (uv y pytest de verdad sobre el fixture, en `selftest / hygiene-logic`).

### Corregido

- `guardia-tests.yml`: los salteos escritos con alias ya no pasan inadvertidos. `from pytest import mark` + `@mark.skip`, `import pytest as pt` + `@pt.mark.skip`, `from pytest import mark as m` + `@m.xfail`, `pytestmark = mark.skip`, `import unittest as ut` + `@ut.skip` y `from pytest import skip as saltar` se resuelven a su nombre completo antes de compararlos (hallazgo H1 del revisor en #13). 7 casos nuevos en `tests/guardia/test_guardia.py` (37 en total).

## [1.5.0] - 2026-10-13

Sin tag publicado. Va después de 1.4.0 (PR apilado).

### Agregado

- `guardia-tests.yml` (fase V, ítem V2, solbeet/workflows#9): job `tests` que frena el PR que borra, debilita o saltea tests existentes o toca `tests/aceptacion/`, salvo label `tests-con-dale` puesto por una persona que no es el autor, después del último push. Comparación por árbol sintáctico en Python y por líneas en otros lenguajes. [ADR 0008](docs/decisiones/0008-guardia-de-tests.md).
- `examples/guardia-tests.yml` y `tests/guardia/test_guardia.py` (30 casos, en `selftest / hygiene-logic`).

## [1.4.0] - 2026-10-13

Sin tag publicado: se etiqueta al mergear (ver `docs/desarrollo.md`). Al publicarlo, `v1` se mueve (workflow nuevo, compatible).

### Agregado

- `gates.yml` (fase V, ítem V1, solbeet/workflows#8): jobs `cobertura-cambio` (diff-cover ≥ 80%), `migraciones` (pytest-alembic + squawk sobre el SQL de las migraciones nuevas), `contrato` (Schemathesis contra la app levantada en el runner) y `dependencias` (OSV-Scanner). Solo frenan lo que introduce el PR: comparan contra la rama base. [ADR 0007](docs/decisiones/0007-gates-sobre-el-diff.md).
- `examples/gates.yml` y casos de veredicto en `tests/gates/test_gates.py` (corren en `selftest / hygiene-logic`).

## [1.3.0] - 2026-10-11

### Agregado
- `imagen.yml`: anotaciones OCI (incluida `org.opencontainers.image.revision` con el sha completo) en cada manifiesto y en el índice multi-arch (`DOCKER_METADATA_ANNOTATIONS_LEVELS: manifest,index`), además del label que ya estaba. Outputs `tag` (`sha-<sha7>`) y `revision` (sha completo) para el caller. Motivo: el deploy a staging de solbeet-run (contrato v5 «Deploy por ambientes», roadmap F1.2) y los estados derivados (ADR 0002 de la fábrica) necesitan el sha completo; `sha-<sha7>` solo es ambiguo para la API de compare.

## [1.2.0] - 2026-10-08

### Cambiado
- `imagen.yml`: por defecto construye `linux/amd64,linux/arm64` (imágenes multi-arquitectura) y agrega QEMU cuando hay arm64. Motivo: los servidores de Solbeet y de los clientes pueden ser ARM o x86 (el entorno de prueba usa uno de cada uno). Para volver a una sola arquitectura, pasar `plataformas: linux/amd64`.

## [Sin publicar]

## [1.1.0] - 2026-10-08

Tag local en la rama `integracion/opcion-b` (sin push): se publica después de mergear el PR con merge commit. Al publicarlo, `v1` se mueve a esta versión (cambio compatible).

### Agregado

- `imagen.yml`: workflow reutilizable que construye y publica la imagen de un servicio en `ghcr.io/<owner>/<imagen>` (tags `X.Y.Z` desde un tag `vX.Y.Z` y `sha-<sha7>`; nunca `latest`). Acciones fijadas por SHA: `docker/setup-buildx-action` v4.4.1, `docker/login-action` v4.6.0, `docker/metadata-action` v6.2.0, `docker/build-push-action` v7.4.0. [ADR 0006](docs/decisiones/0006-imagenes-en-ghcr.md).
- `examples/imagenes.yml`: caller que publica al pushear un tag `v*.*.*`.

## [1.0.2] - 2026-10-08

Sin cambios en la lógica de los workflows. `v1` se mueve a esta versión.

### Agregado

- `LICENSE` con aviso de licencia propietaria y [ADR 0005](docs/decisiones/0005-licencia-propietaria.md).

### Cambiado

- Org de GitHub `solbeet` en lugar de `solbeet-factory` en `examples/`, el README y `docs/`. Los callers tienen que usar `solbeet/workflows/.github/workflows/<archivo>@v1`.

## [1.0.1] - 2026-10-08

Sin cambios en los workflows: solo documentación. `v1` se mueve a esta versión.

### Cambiado

- `docs/arquitectura.md`: la plantilla genera también `pr-hygiene.yml` y pasa siempre `frontend-dir`; ids de job alineados con `examples/`.
- `docs/estado.md`: verificación cruzada con la plantilla de PR de `solbeet-template` y la del plugin `solbeet` (la del plugin no pasaba `hygiene` antes de su v0.1.1).

## [1.0.0] - 2026-10-08

### Agregado

- `python-react.yml`: CI reutilizable con jobs `backend` (uv sync --frozen, ruff check, ruff format --check, pyright, pytest, Postgres opcional) y `frontend` (npm ci y scripts configurables; se saltea con `frontend-dir: ""`). Caché de uv y npm, concurrencia por PR, `contents: read`.
- `claude-review.yml`: revisor independiente con `anthropics/claude-code-action` v1.0.245. Acepta `ANTHROPIC_API_KEY` o `CLAUDE_CODE_OAUTH_TOKEN`, saltea borradores, inputs `model` y `max-turns`.
- `pr-hygiene.yml`: jobs `hygiene` (secciones requeridas del cuerpo, aviso por diff grande, `.rej`, marcadores de conflicto) y `secret-scan` (gitleaks 8.30.1 con checksum verificado sobre los commits del PR).
- `selftest.yml`: actionlint 1.7.12, casos de `pr-hygiene` (`tests/hygiene/`) y ejecución de los workflows contra `tests/fixture/`.
- `examples/` con los workflows para un repo cliente.
- `scripts/lint-workflows.sh`, documentación (`README.md`, `AGENTS.md`, `docs/`) y ADRs 0001–0004.
