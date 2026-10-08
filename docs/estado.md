# Estado

Última actualización: 2026-10-08 · Versión: v1.0.0 (sin publicar en GitHub)

## Qué funciona y cómo se verificó

Todo verificado localmente en macOS arm64, con los comandos de `docs/desarrollo.md` tal cual están escritos.

| Qué | Comando | Resultado |
|---|---|---|
| Lint de los 4 workflows y los 3 ejemplos (con shellcheck en el PATH) | `scripts/lint-workflows.sh` | actionlint 1.7.12 sin hallazgos |
| Los 8 archivos YAML parsean | `yaml.safe_load` sobre `.github/**/*.yml` y `examples/*.yml` | OK |
| Lógica de `pr-hygiene` (job `hygiene`) | `uv run --no-project --with pyyaml==6.0.2 python tests/hygiene/test_pr_hygiene.py` | 12/12 casos con el resultado esperado, incluidos los que deben fallar (sección faltante o vacía, `.rej`, marcadores de conflicto) y el aviso por diff grande excluyendo lockfiles |
| Comandos del job `backend` sobre el fixture | `uv sync --frozen`, `ruff check`, `ruff format --check`, `pyright`, `pytest` | todo en verde; pytest: 3 passed, 1 skipped (el de Postgres, sin `DATABASE_URL`) |
| Test de Postgres del fixture | pytest con `DATABASE_URL` apuntando a un puerto con un servidor escuchando / sin servidor | pasa / falla, como corresponde |
| Comandos del job `frontend` sobre el fixture | `npm ci`, `npm run lint`, `typecheck`, `test`, `build` | todo en verde; node --test: 3 pass |
| Comando de gitleaks de `secret-scan` | `gitleaks git . --log-opts="HEAD^1..HEAD^2" --redact --no-banner --exit-code 1` con el binario 8.30.1 darwin (checksum verificado) en un repo con merge `--no-ff` | detecta una clave agregada en un commit y borrada en el siguiente (exit 1); sin commits en el rango, "no leaks found" |
| Checksums de gitleaks y actionlint | `shasum -a 256 -c` contra el `checksums.txt` de cada release | coinciden |
| Tag de la imagen Docker de actionlint documentada | API de Docker Hub `rhysd/actionlint:1.7.12` | existe |

## Qué NO se probó

- **Ningún workflow se ejecutó en GitHub Actions.** El repo no está publicado (no se hizo push ni se creó el repo remoto) y no hay `act` en el flujo. En particular, sin verificar en un runner real:
  - Que GitHub acepte `image: ''` para saltear el servicio Postgres (comportamiento documentado por la comunidad, no en la documentación oficial) y que el servicio arranque con `postgres: true`.
  - Que `setup-uv` v10.2.0 respete `UV_PYTHON` exportado en un paso anterior y que la caché por `cache-dependency-glob` funcione con un `backend-dir` anidado.
  - Que `claude-review.yml` funcione de punta a punta con `anthropics/claude-code-action` v1.0.245 y `github_token` del workflow (comentarios inline, `gh pr comment`). No se probó con ningún secreto real.
  - Los nombres de checks resultantes (`ci / backend`, etc.) se tomaron de la documentación de GitHub, no de una corrida.
  - El paso `Instalar gitleaks` en un runner Linux (se probó el comando de escaneo con el binario de macOS, no la descarga en Linux).
- El awk del paso "Marcadores de conflicto" se probó con el awk de macOS (BSD); en el runner Ubuntu corre `mawk`. El script usa solo awk POSIX.
- Los pasos se probaron como scripts sueltos; no las expresiones `${{ }}` de los `if:` (las valida actionlint, no se evaluaron).

## Limitaciones conocidas

- `require-section-content` considera "con contenido" cualquier texto que no sea comentario HTML. La plantilla de PR de los proyectos trae casillas y bloques de código vacíos en `## Evidencia`, que cuentan como contenido aunque no se completen.
- El tamaño del diff es un aviso, nunca falla.
- `pr-hygiene` solo funciona con `pull_request` (necesita el commit de merge).
- Solo uv + npm. No soporta pip/poetry ni pnpm/yarn.
- Runner fijo `ubuntu-latest`; no hay input para runners propios.
- `claude-review` se saltea en verde si no hay secretos: una configuración rota se ve solo en el aviso del log.
- El repo no tiene licencia todavía (necesaria antes de hacerlo público).

## Pendientes (en orden)

1. Crear el repo público `solbeet-factory/workflows`, hacer push de `main` y de los tags `v1.0.0` y `v1`, y confirmar que `selftest` pasa en verde en GitHub. Corregir lo que aparezca y publicar `v1.0.1` si hace falta.
2. Elegir y agregar una licencia (`LICENSE`) antes de hacerlo público.
3. Probar `claude-review.yml` desde un repo de prueba con un secreto real; ajustar el prompt según los primeros resultados.
4. Probar los tres ejemplos desde un proyecto generado con `solbeet-template` y configurar la protección de rama con los checks del README.
5. Evaluar un input `runs-on` para runners propios y si conviene exigir que las casillas de `## Evidencia` estén marcadas.
