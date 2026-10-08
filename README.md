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
| `required-sections` | string (multilínea) | `## Qué cambia y por qué`<br>`## Evidencia` | no | Encabezados que debe tener el cuerpo del PR, uno por línea. Coinciden con la plantilla de PR de `solbeet-template`. Vacío = no se controla el cuerpo. |
| `require-section-content` | boolean | `true` | no | Cada sección requerida debe tener texto además del encabezado (los comentarios HTML `<!-- -->` no cuentan). |
| `max-diff-lines` | number | `400` | no | Si las líneas cambiadas superan este número se emite un aviso (no falla). `0` = sin aviso. |
| `diff-exclude` | string | `*.lock package-lock.json pnpm-lock.yaml yarn.lock` | no | Patrones que no cuentan para el tamaño del diff, en cualquier directorio. |

Secretos: ninguno. Outputs: ninguno. Permisos: `contents: read`.

Qué falla y qué avisa:

| Control | Job | Resultado |
|---|---|---|
| Falta una sección requerida o está vacía | `hygiene` | falla |
| Diff mayor a `max-diff-lines` | `hygiene` | aviso |
| Hay archivos `.rej` versionados | `hygiene` | falla |
| Líneas agregadas con `<<<<<<<`, `>>>>>>>` o `\|\|\|\|\|\|\|` | `hygiene` | falla |
| gitleaks encuentra un secreto en algún commit del PR | `secret-scan` | falla |

El escaneo de secretos revisa cada commit del PR (no solo el estado final), con gitleaks 8.30.1 descargado y verificado por checksum ([ADR 0003](docs/decisiones/0003-escaner-de-secretos-y-versiones-fijadas.md)). Si el repo cliente tiene `.gitleaks.toml` o `.gitleaksignore` en la raíz, gitleaks los usa (para falsos positivos).

## Checks requeridos

Cuando un workflow llama a otro, GitHub nombra cada check como `<job del que llama> / <job del reutilizable>`. Con los ejemplos de `examples/` quedan:

| Check | Requerido en la protección de rama |
|---|---|
| `ci / backend` | sí |
| `ci / frontend` | sí (si se saltea porque `frontend-dir` está vacío, GitHub lo cuenta como aprobado) |
| `pr-hygiene / hygiene` | sí |
| `pr-hygiene / secret-scan` | sí |
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
