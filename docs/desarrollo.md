# Desarrollo

## Preparar el entorno desde cero

Herramientas necesarias (ninguna se instala a nivel sistema desde este repo):

| Herramienta | Para qué | Cómo verificar |
|---|---|---|
| `git`, `curl`, `bash` | todo | `git --version` |
| `uv` | fixture backend y `tests/hygiene/` | `uv --version` (instalación: https://docs.astral.sh/uv/) |
| Node.js 20+ y npm | fixture frontend | `node --version` |
| `shellcheck` (opcional) | que actionlint revise los scripts `run:` | `shellcheck --version` |

```bash
git clone https://github.com/solbeet-factory/workflows.git
cd workflows
scripts/lint-workflows.sh
```

`scripts/lint-workflows.sh` descarga actionlint 1.7.12 a `~/.cache/solbeet-workflows/` (o a `$ACTIONLINT_CACHE_DIR`), verifica su checksum y lo corre. Alternativa con Docker, si el daemon está corriendo:

```bash
docker run --rm -v "$PWD:/repo" --workdir /repo rhysd/actionlint:1.7.12 -color .github/workflows/*.yml examples/*.yml
```

## Correr cada tipo de prueba

Todo desde la raíz del repo.

```bash
# 1. Lint de workflows y ejemplos
scripts/lint-workflows.sh

# 2. Lógica de pr-hygiene (12 casos, incluidos los que deben fallar)
uv run --no-project --with pyyaml==6.0.2 python tests/hygiene/test_pr_hygiene.py

# 3. Fixture backend (los mismos comandos que el job backend)
(cd tests/fixture/backend && uv sync --frozen && uv run --frozen ruff check . \
  && uv run --frozen ruff format --check . && uv run --frozen pyright && uv run --frozen pytest)

# 4. Fixture frontend (los mismos comandos que el job frontend)
(cd tests/fixture/frontend && npm ci && npm run lint && npm run typecheck && npm run test && npm run build)
```

El test de Postgres del fixture (`tests/fixture/backend/tests/test_postgres.py`) se saltea sin `DATABASE_URL`. Para probarlo localmente con una base real:

```bash
docker run --rm -d --name pg-selftest -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=test -p 5432:5432 postgres:17
(cd tests/fixture/backend && DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test uv run --frozen pytest)
docker stop pg-selftest
```

## Probar un cambio de punta a punta

Los workflows solo se ejecutan de verdad en GitHub. No hay `act` en el flujo.

1. Abrir un PR en este repo. `selftest.yml` llama a los workflows por ruta local, así que prueba exactamente la versión del PR: actionlint, casos de `pr-hygiene`, `python-react` con y sin Postgres contra el fixture, y `pr-hygiene` sobre el propio PR (el cuerpo tiene que seguir `.github/pull_request_template.md`).
2. Para probar desde un repo cliente real antes de publicar, apuntar su workflow a la rama del PR:
   ```yaml
   uses: solbeet-factory/workflows/.github/workflows/python-react.yml@nombre-de-la-rama
   ```
   y abrir un PR de prueba en ese repo. Volver a `@v1` antes de mergear allá.
3. `claude-review.yml` no se ejercita en `selftest` (necesita secretos y una llamada paga). Probarlo desde un repo de prueba con el secreto configurado, con el paso 2.

## Publicar una versión

Ver la política en el README ("Versionado") y el [ADR 0002](decisiones/0002-contrato-de-nombres-y-versionado.md).

1. Decidir el número: arreglo → patch (`v1.0.1`), input nuevo opcional o mejora compatible → minor (`v1.1.0`), cambio incompatible → mayor (`v2.0.0`).
2. Mover las entradas de `## [Sin publicar]` a una sección nueva en `CHANGELOG.md` y actualizar `docs/estado.md`. Commit en `main` por PR.
3. Crear el tag exacto y mover el mayor:
   ```bash
   git checkout main && git pull
   git tag -a v1.1.0 -m "v1.1.0"
   git tag -f -a v1 -m "v1 -> v1.1.0" "v1.1.0^{}"   # ^{} = el commit, no el tag (evita un tag anidado)
   git push origin v1.1.0
   git push -f origin v1
   ```
4. Para una versión mayor: crear `v2.0.0` y `v2` (sin mover `v1`), y avisar a los consumidores. En los repos cliente se actualiza por PR cambiando `@v1` por `@v2` (en los proyectos de la plantilla, con `copier update`).
5. Si un release `v1.x.y` rompe a los clientes: `git tag -f -a v1 -m "rollback" "v1.<anterior>^{}"` y `git push -f origin v1`. Los clientes vuelven a la versión anterior en la próxima corrida sin tocar nada.

## Actualizar versiones fijadas

- Actions (`uses: ...@<sha> # vX`): Dependabot abre los PRs (`.github/dependabot.yml`). Revisar el changelog de la action, en especial `anthropics/claude-code-action` (cambian inputs con frecuencia).
- gitleaks (`pr-hygiene.yml`) y actionlint (`selftest.yml` y `scripts/lint-workflows.sh`): a mano. Bajar `<herramienta>_<versión>_checksums.txt` del release oficial, copiar los SHA-256 de las plataformas usadas y cambiar versión y checksums en el mismo commit:
  ```bash
  gh release download v8.30.1 -R gitleaks/gitleaks -p 'gitleaks_8.30.1_checksums.txt' -O - | grep linux
  gh release download v1.7.12 -R rhysd/actionlint -p 'actionlint_1.7.12_checksums.txt' -O - | grep -E 'linux|darwin'
  ```
  Registrar el cambio en `docs/decisiones/0003-escaner-de-secretos-y-versiones-fijadas.md` (tabla de versiones).

## Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `uv sync --frozen` falla con "lockfile needs to be updated" | `pyproject.toml` cambió sin regenerar `uv.lock` | `uv lock` y commitear el lockfile |
| `npm ci` falla por lockfile desincronizado | `package.json` cambió sin `npm install` | `npm install` y commitear `package-lock.json` |
| `uv run --frozen ruff` dice "Failed to spawn: ruff" | ruff/pyright/pytest no están en las deps de desarrollo del cliente | agregarlos a `[dependency-groups] dev` y `uv lock` |
| `pr-hygiene` falla con "solo funciona con el evento pull_request" | el caller lo dispara con `push` o `pull_request_target` | usar `on: pull_request` (ver `examples/pr-hygiene.yml`) |
| El check `ci / backend` no aparece para marcarlo como requerido | GitHub solo lista checks que ya corrieron | correr el workflow una vez (abrir un PR) y después configurar la protección |
| `claude-review` termina en verde sin comentar | no hay secretos (fork) o el PR es borrador | ver el aviso en el log del job; los borradores se revisan al pasar a "ready for review" |
| `secret-scan` marca un falso positivo | patrón genérico de gitleaks | agregar el fingerprint a `.gitleaksignore` en el repo cliente |
| actionlint: `sha256sum: WARNING: 1 computed checksum did NOT match` | descarga corrupta o versión/checksum desincronizados | borrar `~/.cache/solbeet-workflows/` y revisar que versión y checksum coincidan |
