# Arquitectura

## Componentes

```
repo cliente (.github/workflows/)                 este repo (público)
─────────────────────────────────                 ─────────────────────────────────────────
ci.yml            ── uses @v1 ───────────────────► python-react.yml
                                                     ├─ job backend : uv sync, ruff, pyright, pytest
                                                     │                (+ servicio postgres opcional)
                                                     └─ job frontend: npm ci, lint, typecheck, test, build

claude-review.yml ── uses @v1 + secretos ────────► claude-review.yml
                                                     └─ job review  : anthropics/claude-code-action
                                                                      ├─ lee AGENTS.md, spec, diff
                                                                      └─ comenta en el PR (inline + resumen)

pr-hygiene.yml    ── uses @v1 ───────────────────► pr-hygiene.yml
                                                     ├─ job hygiene    : secciones, tamaño, .rej, conflictos
                                                     └─ job secret-scan: gitleaks sobre los commits del PR

                                                   selftest.yml (solo este repo)
                                                     ├─ actionlint sobre workflows y examples/
                                                     ├─ hygiene-logic: tests/hygiene/ (casos que fallan)
                                                     ├─ ci, ci-postgres: python-react.yml ⟶ tests/fixture/
                                                     └─ pr-hygiene: pr-hygiene.yml sobre los PRs de este repo
```

Cada workflow reutilizable es un archivo autocontenido: no depende de otros archivos de este repo en tiempo de ejecución, porque GitHub hace el checkout del repo que llama, no de este (ver "Límites").

## Flujo de un PR en un repo cliente

1. Se abre o actualiza un PR. GitHub dispara los tres workflows del cliente.
2. Cada uno resuelve `solbeet-factory/workflows/...@v1` al commit al que apunta el tag `v1` en ese momento y corre los jobs de acá con el contexto del cliente (`github.repository`, el evento, sus secretos si los pasa).
3. Los jobs hacen checkout del repo del cliente (el commit de merge del PR) y corren los controles.
4. Resultados:
   - `ci / backend`, `ci / frontend`, `pr-hygiene / hygiene`, `pr-hygiene / secret-scan`: status checks; los cuatro deberían ser requeridos en la protección de rama.
   - `claude-review / review`: comentarios en el PR firmados por `github-actions[bot]` y un resumen con veredicto (`aprobar`, `cambios menores`, `cambios necesarios`). No bloquea.
   - Avisos (`::warning::`) y errores (`::error::`) quedan como anotaciones en el PR.

## Qué consume

- De GitHub: el runner `ubuntu-latest`, el commit de merge `refs/pull/N/merge` y el `GITHUB_TOKEN` del repo que llama.
- Actions de terceros fijadas por SHA: `actions/checkout`, `actions/setup-node`, `astral-sh/setup-uv`, `anthropics/claude-code-action`.
- Binarios fijados por versión y checksum: gitleaks (en `pr-hygiene`), actionlint (en `selftest` y `scripts/`).
- Del repo cliente: `pyproject.toml` + `uv.lock` con ruff, pyright y pytest como deps de desarrollo; `package.json` + `package-lock.json` con los scripts; `AGENTS.md` y la spec enlazada en el PR (para el revisor); opcionalmente `.gitleaks.toml`/`.gitleaksignore`.
- La API de Anthropic, a través de la action, con el secreto del cliente.

## Qué entrega a otros repos de la fábrica

- `solbeet-template` genera en cada proyecto `ci.yml` y `claude-review.yml` que llaman a `python-react.yml@v1` y `claude-review.yml@v1`. La plantilla de PR de ese repo define las secciones que `pr-hygiene` exige por defecto (`## Qué cambia y por qué`, `## Evidencia`). Si una cambia, la otra también.
- El contrato estable para los consumidores: nombres de archivo, nombres de jobs, inputs y secretos documentados en el README ([ADR 0002](decisiones/0002-contrato-de-nombres-y-versionado.md)).

## Límites: qué NO hace

- No despliega: no hay jobs de build de imágenes ni de deploy.
- No guarda ni provee secretos: los secretos son del repo cliente.
- No configura la protección de rama: el README dice qué checks marcar, pero se configura en cada repo.
- No ejecuta scripts de este repo dentro de los workflows reutilizables: la lógica está inline en cada YAML.
- No escanea toda la historia del repo cliente: solo los commits del PR.
- No soporta otros gestores de paquetes (pip, poetry, pnpm, yarn) ni otros eventos que `pull_request` en `pr-hygiene`.
- El revisor con Claude no modifica código ni hace push; solo lee y comenta.
