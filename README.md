# workflows

Workflows reutilizables de GitHub Actions que usan los repos de los clientes de la fábrica. Cada repo cliente declara en pocas líneas qué quiere correr y la lógica (CI de backend y frontend, revisión con Claude, higiene de PRs, escaneo de secretos) vive acá, en un solo lugar y versionada. Así un cambio en el CI se hace una vez y llega a todos los repos por un cambio de tag.

Dónde encaja: es la pieza de CI de la fábrica (ver [`../README.md`](../README.md)). Los proyectos generados con `solbeet-template` ya traen los workflows que llaman a este repo.

Este repo está pensado para ser **público**: GitHub solo deja llamar workflows reutilizables de otra organización si el repo que los contiene es público ([ADR 0001](docs/decisiones/0001-repo-publico.md)). Por eso no contiene secretos, hostnames internos ni nada específico de un cliente.

Licencia: propietaria ([`LICENSE`](LICENSE), [ADR 0005](docs/decisiones/0005-licencia-propietaria.md)). El código es visible para que los repos de clientes de Solbeet lo llamen con `uses:`; no se otorga licencia de copia, modificación ni redistribución.

## Contenido

| Workflow | Qué hace | Jobs (checks) |
|---|---|---|
| [`python-react.yml`](.github/workflows/python-react.yml) | CI de backend Python con uv (ruff, pyright, pytest) y frontend Node con npm (lint, typecheck, test, build) | `backend`, `frontend` |
| [`claude-review.yml`](.github/workflows/claude-review.yml) | Revisor independiente de PRs con `anthropics/claude-code-action`: spec, tests, bugs y seguridad, evidencia. Deja comentarios inline y un resumen con veredicto | `review` |
| [`pr-hygiene.yml`](.github/workflows/pr-hygiene.yml) | Secciones de evidencia en el cuerpo del PR, aviso por diff grande, archivos `.rej`, marcadores de conflicto y escaneo de secretos con gitleaks | `hygiene`, `secret-scan` |
| [`imagen.yml`](.github/workflows/imagen.yml) | Construye y publica la imagen de un servicio en `ghcr.io/<owner>/<imagen>` con tag = versión semver sin `v` y `sha-<sha7>` (sin `latest`); el sha completo va como label y anotación `org.opencontainers.image.revision` (outputs `tag` y `revision`). Usa el `GITHUB_TOKEN` con `packages: write` | `imagen` (no es check requerido) |
| [`gates.yml`](.github/workflows/gates.yml) | Gates sobre el diff del PR (fase V): cobertura de las líneas cambiadas, migraciones (pytest-alembic + squawk), contrato de la API (Schemathesis) y dependencias vulnerables (OSV-Scanner). Solo frena lo que introduce el PR | `cobertura-cambio`, `migraciones`, `contrato`, `dependencias` |
| [`guardia-tests.yml`](.github/workflows/guardia-tests.yml) | Guardia de tests (fase V): frena el PR que borra, debilita o saltea tests existentes, o toca tests de aceptación, salvo dale de una persona (label) | `tests` |
| [`rojo-verde.yml`](.github/workflows/rojo-verde.yml) | Rojo → verde (fase V): cada test nuevo de Python tiene que fallar sin el cambio y pasar con él | `rojo-verde` |
| [`selftest.yml`](.github/workflows/selftest.yml) | Uso interno: lintea los workflows y los ejecuta contra el fixture de `tests/fixture/` | — |

## Requisitos (repo cliente)

- Backend: `pyproject.toml` y `uv.lock` versionado. `ruff`, `pyright` y `pytest` declarados como dependencias de desarrollo (por ejemplo en `[dependency-groups] dev`): el workflow los corre con `uv run`, así la versión la fija el lockfile del cliente.
- Frontend: `package.json` con los scripts `lint`, `typecheck`, `test` y `build` (o los que se pasen en `frontend-scripts`) y `package-lock.json` versionado. `test` debe terminar solo (sin modo watch); con `CI=true`, que GitHub define, vitest y jest ya lo hacen.
- Para `claude-review`: el secreto `ANTHROPIC_API_KEY` o `CLAUDE_CODE_OAUTH_TOKEN` en el repo o en la organización.
- Para `pr-hygiene`: que el evento sea `pull_request`.

## Uso rápido

Copiar los ejemplos de [`examples/`](examples/) a `.github/workflows/` del repo cliente:

```bash
# desde la raíz del repo cliente, con este repo clonado al lado
mkdir -p .github/workflows
cp ../workflows/examples/ci.yml ../workflows/examples/claude-review.yml ../workflows/examples/pr-hygiene.yml .github/workflows/
```

El núcleo de cada ejemplo:

```yaml
jobs:
  ci:
    uses: solbeet/workflows/.github/workflows/python-react.yml@v1
    with:
      backend-dir: backend
      frontend-dir: frontend
```

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: read
jobs:
  claude-review:
    uses: solbeet/workflows/.github/workflows/claude-review.yml@v1
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, edited, ready_for_review]
jobs:
  pr-hygiene:
    uses: solbeet/workflows/.github/workflows/pr-hygiene.yml@v1
```

`secrets: inherit` también sirve en lugar de pasar los secretos uno por uno.

## Referencia de configuración

### `python-react.yml`

| Input | Tipo | Default | Obligatorio | Descripción |
|---|---|---|---|---|
| `runner` | string | `ubuntu-latest` | no | Runner (label de `runs-on`) de todos los jobs. Vacío = `ubuntu-latest`. Ver «Elegir dónde corre». |
| `backend-dir` | string | `backend` | no | Directorio con `pyproject.toml` y `uv.lock`. |
| `frontend-dir` | string | `frontend` | no | Directorio con `package.json` y `package-lock.json`. Vacío (`""`) = el job `frontend` se saltea. |
| `python-version` | string | `""` | no | Versión de Python. Vacío = `.python-version` del backend; si no hay, el de la raíz; si no hay, `3.12`. |
| `node-version` | string | `22` | no | Versión de Node.js. |
| `run-pyright` | boolean | `true` | no | Correr `pyright`. |
| `postgres` | boolean | `false` | no | Levanta un servicio Postgres en `localhost:5432` y exporta `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test` (credenciales de prueba, solo existen dentro del job). |
| `postgres-image` | string | `postgres:17` | no | Imagen del servicio Postgres. |
| `frontend-scripts` | string | `lint typecheck test build` | no | Scripts de npm a correr en orden, separados por espacios. Corren todos aunque uno falle y el job falla si alguno falló. |

Secretos: ninguno. Outputs: ninguno. Permisos que usa: `contents: read`.

Pasos del job `backend`: `uv sync --frozen` → `ruff check` → `ruff format --check` → `pyright` → `pytest`. Del job `frontend`: `npm ci` → cada script de `frontend-scripts`. Después de `uv sync`, los controles corren todos aunque uno falle, para ver todos los errores en una sola corrida. Caché: la de uv (clave por `uv.lock`) y la de npm (clave por `package-lock.json`).

### `claude-review.yml`

| Input | Tipo | Default | Obligatorio | Descripción |
|---|---|---|---|---|
| `runner` | string | `ubuntu-latest` | no | Runner (label de `runs-on`) de todos los jobs. Vacío = `ubuntu-latest`. Ver «Elegir dónde corre». |
| `model` | string | `""` | no | Modelo, se pasa como `--model`. Vacío = el default de la action. |
| `max-turns` | number | `30` | no | Límite de turnos del agente revisor (acota costo y tiempo). |

| Secreto | Obligatorio | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | uno de los dos | API key de Anthropic. |
| `CLAUDE_CODE_OAUTH_TOKEN` | uno de los dos | Token OAuth de Claude Code. |

Si no llega ninguno de los dos (por ejemplo, en PRs desde forks, que no reciben secretos) el job emite un aviso y termina sin revisar. Outputs: ninguno. Permisos que necesita del workflow que llama: `contents: read`, `pull-requests: write`, `issues: read`. Los PRs en borrador se saltean; se revisan al pasar a "ready for review" (por eso el ejemplo escucha `ready_for_review`).

El revisor tiene permitido: comentarios inline, `gh pr comment`, `gh pr diff`, `gh pr view` y `gh issue view` (para leer una spec que sea un issue), además de las herramientas de lectura de archivos. No puede modificar código ni hacer push.

### `pr-hygiene.yml`

| Input | Tipo | Default | Obligatorio | Descripción |
|---|---|---|---|---|
| `runner` | string | `ubuntu-latest` | no | Runner (label de `runs-on`) de todos los jobs. Vacío = `ubuntu-latest`. Ver «Elegir dónde corre». |
| `required-sections` | string (multilínea) | `## Qué cambia y por qué`<br>`## Evidencia` | no | Encabezados que debe tener el cuerpo del PR, uno por línea. Coinciden con la plantilla de PR de `solbeet-template`. Vacío = no se controla el cuerpo. |
| `require-section-content` | boolean | `true` | no | Cada sección requerida debe tener texto además del encabezado (los comentarios HTML `<!-- -->` no cuentan). |
| `max-diff-lines` | number | `400` | no | Si las líneas cambiadas superan este número se emite un aviso (no falla). `0` = sin aviso. |
| `diff-exclude` | string | `*.lock package-lock.json pnpm-lock.yaml yarn.lock` | no | Patrones que no cuentan para el tamaño del diff, en cualquier directorio. |

Secretos: ninguno. Outputs: ninguno. Permisos: `contents: read`.

Los PRs cuyo autor es `dependabot[bot]` quedan eximidos solo de la exigencia de secciones en el cuerpo (Dependabot genera el cuerpo y no las trae). El resto de los controles, incluido `secret-scan`, aplica igual.

Qué falla y qué avisa:

| Control | Job | Resultado |
|---|---|---|
| Falta una sección requerida o está vacía | `hygiene` | falla |
| Diff mayor a `max-diff-lines` | `hygiene` | aviso |
| Hay archivos `.rej` versionados | `hygiene` | falla |
| Líneas agregadas con `<<<<<<<`, `>>>>>>>` o `\|\|\|\|\|\|\|` | `hygiene` | falla |
| gitleaks encuentra un secreto en algún commit del PR | `secret-scan` | falla |

El escaneo de secretos revisa cada commit del PR (no solo el estado final), con gitleaks 8.30.1 descargado y verificado por checksum ([ADR 0003](docs/decisiones/0003-escaner-de-secretos-y-versiones-fijadas.md)). Si el repo cliente tiene `.gitleaks.toml` o `.gitleaksignore` en la raíz, gitleaks los usa (para falsos positivos).

### `gates.yml`

Cuatro checks pensados para ser requeridos antes de prender el merge automático (ADR 0004 §13 de la fábrica: "checks requeridos en verde"). **Regla común: solo frenan lo que introduce el PR.** Cada job compara contra la rama base (`HEAD^1` del commit de merge de `pull_request`): lo que ya fallaba en la base se informa como aviso. Así sirven en código heredado sin tests. Solo funciona con el evento `pull_request` ([ADR 0007](docs/decisiones/0007-gates-sobre-el-diff.md)).

| Input | Tipo | Default | Obligatorio | Descripción |
|---|---|---|---|---|
| `runner` | string | `ubuntu-latest` | no | Runner (label de `runs-on`) de todos los jobs. Vacío = `ubuntu-latest`. Ver «Elegir dónde corre». |
| `backend-dir` | string | `backend` | no | Directorio con `pyproject.toml` y `uv.lock`. |
| `python-version` | string | `""` | no | Igual que en `python-react.yml`. |
| `postgres` | boolean | `false` | no | Postgres para los tests de `cobertura-cambio` (exporta `DATABASE_URL`). `migraciones` y `contrato` lo levantan siempre. |
| `postgres-image` | string | `postgres:17` | no | Imagen del servicio Postgres. |
| `coverage-min` | number | `80` | no | Porcentaje mínimo de líneas cambiadas cubiertas. |
| `coverage-omit` | string | `tests/*,migrations/*` | no | Patrones (coma) que no se miden, relativos a `backend-dir`. |
| `migrations-blocking-rules` | string | `ban-drop-column ban-drop-table ban-drop-database ban-truncate-cascade renaming-column renaming-table changing-column-type adding-required-field` | no | Reglas de squawk que frenan; el resto avisa. |
| `contract-app` | string | `""` | no | App ASGI (`modulo:objeto`) que levanta el job `contrato`. Vacío = no corre. |
| `contract-factory` | boolean | `false` | no | `contract-app` es una fábrica (`uvicorn --factory`). |
| `contract-max-examples` | number | `30` | no | Casos por operación en Schemathesis. |
| `contract-checks` | string | `not_a_server_error,response_schema_conformance,content_type_conformance` | no | Checks de Schemathesis. |
| `vuln-min-severity` | number | `7` | no | CVSS desde el que una vulnerabilidad nueva con arreglo frena. |

Secretos: ninguno. Permisos: `contents: read`. Output del job `migraciones`: `destructiva` (`true` si una migración nueva tiene una operación de las reglas que frenan; señal para clasificar el PR como zona alta).

| Job | Qué hace | Frena si | Avisa (no frena) |
|---|---|---|---|
| `cobertura-cambio` | `coverage run -m pytest` en `backend-dir` y `diff-cover` contra `HEAD^1` | menos de `coverage-min`% de las líneas Python cambiadas están cubiertas | pytest falla (eso lo frena `ci / backend`) |
| `migraciones` | si hay `alembic.ini`: SQL offline de cada revisión nueva + squawk; pytest-alembic (`single_head_revision`, `upgrade`, `up_down_consistency`, `model_definitions_match_ddl`) contra Postgres | una migración nueva borra, renombra o cambia el tipo de algo existente; una prueba de pytest-alembic falla con el PR y pasaba en la base | locks largos, timeouts, estilo; pruebas que ya fallaban en la base |
| `contrato` | levanta la base y el PR en el runner (Postgres + `alembic upgrade head` + uvicorn) y corre Schemathesis sobre los dos | un fallo de contrato (5xx, respuesta fuera del esquema) que no está en la base | fallos heredados; antes de declarar uno nuevo se reenvía a la base la misma petición y se insiste en esa operación |
| `dependencias` | OSV-Scanner sobre los lockfiles del PR y de la base | una vulnerabilidad nueva con CVSS ≥ `vuln-min-severity` y versión arreglada | nuevas sin arreglo o de menor severidad; heredadas |

Herramientas fijadas: squawk 2.66.0 y OSV-Scanner 2.6.0 (binarios con SHA-256), coverage 7.16.2, diff-cover 10.6.0, pytest-alembic 0.13.0, Schemathesis 4.28.0, uvicorn 0.53.0 (por PyPI, versión exacta). El cliente no tiene que declararlas en sus dependencias.

### `guardia-tests.yml`

Un agente que no logra pasar un test tiende a cambiar el test (ImpossibleBench, 2025). Este check lo frena sin juez LLM, comparando la base con el PR ([ADR 0008](docs/decisiones/0008-guardia-de-tests.md)). Solo con el evento `pull_request`.

| Input | Tipo | Default | Obligatorio | Descripción |
|---|---|---|---|---|
| `runner` | string | `ubuntu-latest` | no | Runner (label de `runs-on`) de todos los jobs. Vacío = `ubuntu-latest`. Ver «Elegir dónde corre». |
| `test-paths` | string (multilínea) | `tests/*`, `*/tests/*`, `test_*.py`, `conftest.py`, `*.test.*`, `*.spec.*`, … | no | Patrones fnmatch de archivos de tests. |
| `acceptance-dir` | string | `tests/aceptacion` | no | Carpeta de tests de aceptación (en cualquier nivel). |
| `override-label` | string | `tests-con-dale` | no | Label del dale humano. |
| `override-approvers` | string | `""` | no | Logins que pueden dar el dale. Vacío = cualquier persona que no sea el autor ni un bot. |

Permisos que necesita del caller: `contents: read`, `pull-requests: read`, `issues: read`, `actions: read` (lee quién puso el label y cuándo llegó el último push; no escribe nada). El caller tiene que escuchar `labeled` y `unlabeled` para reevaluar al poner el label.

| Frena | Ejemplo |
|---|---|
| borrar un archivo de tests o un test que existía | `test_suma` desaparece |
| debilitar un test existente: sacar o cambiar un assert, `self.assert*`, `mock.assert_*`, `pytest.raises`/`warns` o un caso de `parametrize` | `assert suma(2, 3) == 5` pasa a `== 6` |
| saltear tests existentes | `@pytest.mark.skip` en un test que estaba, `pytestmark` a nivel módulo, skip en `conftest.py`, `.only`/`.skip`/`xit` |
| tocar un archivo existente de `tests/aceptacion/` | cualquier cambio |

No frena: tests nuevos (en archivos nuevos o existentes), cambiar setup, fixtures o helpers, reformatear, imports, docstrings, mover archivos sin cambios. Los salteos dentro de tests nuevos los ve `rojo-verde.yml`.

**Dale humano:** una persona revisa el cambio y pone el label `tests-con-dale`. Vale si lo puso alguien que no es bot ni autor del PR (y está en `override-approvers`, si se configuró) **después del último push**: si el PR cambia, hay que volver a ponerlo. El uso queda en el resumen del job.

### `rojo-verde.yml`

Un test nuevo tiene que demostrar que prueba el cambio: con el código de la base tiene que fallar y con el del PR tiene que pasar. Un test que pasa igual sin el cambio (el «test espejo», o uno que no ejercita lo nuevo) no prueba nada. Solo con `pull_request`.

| Input | Tipo | Default | Obligatorio | Descripción |
|---|---|---|---|---|
| `runner` | string | `ubuntu-latest` | no | Runner (label de `runs-on`) de todos los jobs. Vacío = `ubuntu-latest`. Ver «Elegir dónde corre». |
| `backend-dir` | string | `backend` | no | Directorio con `pyproject.toml` y `uv.lock`. |
| `python-version` | string | `""` | no | Igual que en `python-react.yml`. |
| `postgres` | boolean | `false` | no | Postgres para los tests (exporta `DATABASE_URL`). |
| `postgres-image` | string | `postgres:17` | no | Imagen del servicio Postgres. |
| `test-paths` | string (multilínea) | patrones de tests de Python | no | Qué archivos cuentan como tests. |
| `ignore-paths` | string (multilínea) | `*.md`, `docs/*`, `.github/*`, lockfiles, config | no | Archivos que no cuentan como cambio de código. |
| `override-label` | string | `tests-con-dale` | no | Label del dale humano para tests que ya pasaban (caracterización). |

Permisos del caller: los mismos que `guardia-tests.yml`.

Cómo funciona: lista los tests nuevos del PR (funciones `test*` y métodos `test*` de `Test*`), copia los archivos de tests del PR sobre un checkout de la base y los corre ahí; después los corre sobre el PR. Si el PR no cambia código (solo tests, docs o config) o no agrega tests de Python, no aplica (verde). La tabla test | sin el cambio | con el cambio queda en el resumen del job.

| Resultado | Check |
|---|---|
| todos los tests nuevos fallan sin el cambio y pasan con él | verde |
| un test nuevo pasa sin el cambio (o se saltea) | rojo, salvo label `tests-con-dale` de una persona (mismas reglas que la guardia): caso legítimo, tests de caracterización antes de un refactor |
| un test nuevo no pasa con el cambio | rojo, sin vía de escape |

Hoy solo Python (pytest) dentro de `backend-dir`; un parametrizado cuenta como rojo en la base si falla al menos un caso.

## Elegir dónde corre (`runner`)

Todos los workflows reutilizables aceptan el input `runner` (string, default `ubuntu-latest`): es el label que usan sus jobs en `runs-on`. Los nombres de los jobs y de los checks no dependen del runner, así que cambiarlo no toca los rulesets.

La forma recomendada es fijarlo con una variable de la organización (`SOLBEET_RUNNER`) y pasarla en cada caller. Con la variable sin definir (o vacía) corre en el runner hosted de siempre:

```yaml
jobs:
  ci:
    uses: solbeet/workflows/.github/workflows/python-react.yml@v1
    with:
      runner: ${{ vars.SOLBEET_RUNNER || 'ubuntu-latest' }}
```

- Pasar al scale set propio: definir `SOLBEET_RUNNER` con el nombre del scale set. Volver a hosted: borrar la variable o ponerle `ubuntu-latest`. No hay que tocar ningún repo.
- Un input sirve para todos los jobs del workflow (por ejemplo `backend` y `frontend` de `python-react.yml`).
- Advertencia: no usar runners self-hosted en repos públicos que reciban PRs de forks. Un PR de un fork ejecuta código ajeno en el runner. En esos repos dejar `ubuntu-latest`.
- El runner propio tiene que traer lo que el job espera (Docker para `imagen.yml`, `python3`, `git`, `curl`); los workflows no lo instalan.

## Checks requeridos

Cuando un workflow llama a otro, GitHub nombra cada check como `<job del que llama> / <job del reutilizable>`. Con los ejemplos de `examples/` quedan:

| Check | Requerido en la protección de rama |
|---|---|
| `ci / backend` | sí |
| `ci / frontend` | sí (si se saltea porque `frontend-dir` está vacío, GitHub lo cuenta como aprobado) |
| `pr-hygiene / hygiene` | sí |
| `pr-hygiene / secret-scan` | sí |
| `solbeet / cobertura-cambio`, `solbeet / migraciones`, `solbeet / contrato`, `solbeet / dependencias` | sí, antes de prender el merge automático (con `examples/gates.yml`, cuyo job se llama `solbeet`) |
| `solbeet / tests` | sí, antes de prender el merge automático (con `examples/guardia-tests.yml`) |
| `solbeet / rojo-verde` | sí, antes de prender el merge automático (con `examples/rojo-verde.yml`) |
| `claude-review / review` | **no**: es informativo. Depende de un servicio externo y de secretos que los forks no reciben |

Si el repo cliente le pone otro id (o `name:`) al job que llama, la primera parte del nombre cambia. Los nombres de los jobs de este repo (`backend`, `frontend`, `review`, `hygiene`, `secret-scan`) son parte del contrato y solo cambian en una versión mayor.

## Versionado

- Cada versión es un tag semver (`v1.0.0`, `v1.1.0`, …) descrito en [`CHANGELOG.md`](CHANGELOG.md).
- Además existe un tag mayor móvil (`v1`) que apunta a la última versión `v1.x.y`. Los clientes usan `@v1` y reciben arreglos y features compatibles sin tocar su repo.
- Un cambio incompatible (quitar o renombrar un input, secreto o job; cambiar un default de forma que rompa a quien no lo fija; exigir permisos nuevos) va en una versión mayor nueva (`v2.0.0` y tag `v2`). `v1` queda donde estaba.
- Quien necesite congelar el CI puede usar un tag exacto (`@v1.0.0`) o un SHA.

Procedimiento completo en [`docs/desarrollo.md`](docs/desarrollo.md#publicar-una-versión).

## Documentación

| Documento | Contenido |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Cómo trabaja un agente en este repo: comandos, reglas, trampas |
| [`docs/arquitectura.md`](docs/arquitectura.md) | Componentes, flujo, qué consume y qué entrega, límites |
| [`docs/desarrollo.md`](docs/desarrollo.md) | Entorno, pruebas, cómo probar un cambio de punta a punta, publicar una versión, problemas comunes |
| [`docs/estado.md`](docs/estado.md) | Qué funciona y cómo se verificó, qué no se probó, pendientes |
| [`docs/decisiones/`](docs/decisiones/) | ADRs: [0001 repo público](docs/decisiones/0001-repo-publico.md), [0002 nombres de jobs y versionado](docs/decisiones/0002-contrato-de-nombres-y-versionado.md), [0003 escáner de secretos y versiones fijadas](docs/decisiones/0003-escaner-de-secretos-y-versiones-fijadas.md), [0004 revisor con Claude](docs/decisiones/0004-revisor-con-claude.md), [0005 licencia propietaria](docs/decisiones/0005-licencia-propietaria.md) |
| [`CHANGELOG.md`](CHANGELOG.md) | Cambios por versión |
