# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado [semver](https://semver.org/lang/es/) con tag mayor móvil (ver README, "Versionado").

## [Sin publicar]

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
