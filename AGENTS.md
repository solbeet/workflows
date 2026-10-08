# AGENTS.md · workflows

Workflows reutilizables de GitHub Actions para los repos de clientes. El repo es **público**: todo lo que se escriba acá lo puede leer cualquiera.

## Estructura

```
.github/workflows/
  python-react.yml     CI reutilizable (jobs: backend, frontend)
  claude-review.yml    revisor con Claude (job: review)
  pr-hygiene.yml       higiene de PR y secretos (jobs: hygiene, secret-scan)
  selftest.yml         CI de este repo: actionlint + fixture + casos de pr-hygiene
.github/dependabot.yml actualiza las actions fijadas por SHA y las deps del fixture
examples/              workflows que copia un repo cliente (también se lintean)
scripts/lint-workflows.sh  actionlint en versión fijada, igual que en CI
tests/fixture/backend  FastAPI mínimo (uv) que ejercita el job backend
tests/fixture/frontend JS + tsc + node --test que ejercita el job frontend
tests/hygiene/         prueba la lógica de pr-hygiene.yml contra repos git temporales
docs/                  arquitectura, desarrollo, estado, ADRs
```

## Comandos

Todos desde la raíz del repo. Requieren `git`, `curl`, `uv` y Node 20+ con npm.

```bash
# Lint de workflows y ejemplos (descarga actionlint 1.7.12 verificado a ~/.cache)
scripts/lint-workflows.sh

# Casos de pr-hygiene (deben fallar los que tienen que fallar)
uv run --no-project --with pyyaml==6.0.2 python tests/hygiene/test_pr_hygiene.py

# Fixture backend: lo mismo que corre el job backend
cd tests/fixture/backend && uv sync --frozen && uv run --frozen ruff check . \
  && uv run --frozen ruff format --check . && uv run --frozen pyright && uv run --frozen pytest

# Fixture frontend: lo mismo que corre el job frontend
cd tests/fixture/frontend && npm ci && npm run lint && npm run typecheck && npm run test && npm run build
```

No hay build ni paquete: "publicar" es crear tags (ver `docs/desarrollo.md#publicar-una-versión`).

## Convenciones

- Comentarios, descripciones de inputs y docs en español. Nombres de inputs en kebab-case inglés (`backend-dir`).
- Toda action de terceros se fija por SHA completo con la versión en un comentario: `uses: actions/checkout@<sha> # v7.0.1`.
- Binarios descargados (gitleaks, actionlint): versión exacta + checksum SHA-256 del release oficial, verificado antes de usar.
- `permissions` mínimos a nivel workflow (`contents: read`) y se amplían solo en el job que lo necesita.
- Datos controlados por el autor del PR (título, cuerpo, rama) entran a los scripts por `env:`, nunca interpolados con `${{ }}` dentro de `run:` ni del prompt.
- Cada input nuevo: `description`, `type`, `default`, y una fila en la tabla del README.
- Los comentarios explican el porqué; si hay ADR, se enlaza.

## Pedir confirmación antes de

- Cambiar el nombre de un job, quitar o renombrar un input o secreto, o cambiar un default de forma incompatible: es una versión mayor (ADR 0002).
- Mover un tag (`v1`) o hacer push de tags.
- Ampliar `permissions` de cualquier workflow reutilizable.
- Cambiar la versión de gitleaks o actionlint.

## Nunca

- Poner secretos, hostnames o IPs internas, nombres de clientes o de otros productos de la empresa. El repo es público.
- Usar `gitleaks/gitleaks-action` (exige licencia para organizaciones; ver ADR 0003).
- Referenciar actions por tag móvil (`@v4`, `@main`) en los workflows reutilizables.
- Interpolar `github.event.pull_request.body`/`title`/`head_ref` dentro de `run:` o del prompt.
- Marcar `claude-review / review` como check requerido en la documentación o los ejemplos.

## Trampas conocidas

- Los workflows reutilizables corren con el checkout del repo **que llama**, no de este. No se pueden usar scripts de este repo desde `run:`; por eso la lógica va inline.
- Desde `selftest.yml` se llaman con ruta local (`./.github/workflows/x.yml`), así cada PR prueba su propia versión. Los ejemplos usan `@v1`.
- El nombre del check es `<job que llama> / <job reutilizable>`. Renombrar un job rompe la protección de rama de todos los clientes.
- `services` no acepta `if:`. Para que Postgres sea opcional se usa imagen vacía (`image: ''`), que GitHub interpreta como "no levantar".
- `pr-hygiene` depende del commit de merge de `pull_request` (`HEAD^1` = base, `HEAD^2` = punta del PR). Con `push` o `pull_request_target` no funciona: falla a propósito.
- PyYAML lee la clave `on:` como `True`; `tests/hygiene/test_pr_hygiene.py` ya lo contempla.
- En macOS el bash es 3.2: nada de `mapfile` ni arrays asociativos en `scripts/`.
- actionlint solo corre shellcheck sobre los `run:` si `shellcheck` está en el PATH; en el runner de GitHub está.
- La concurrencia de los reutilizables usa prefijos propios (`python-react-…`) para no chocar con el grupo del workflow que llama (si coinciden, se bloquean entre sí).
- Al mover el tag mayor, apuntarlo al commit (`"v1.1.0^{}"`), no al tag anotado: si no, git crea un tag anidado.

- `node --test <carpeta>` falla en Node 22 (toma la carpeta como módulo): usar un glob `"test/**/*.test.js"`.
