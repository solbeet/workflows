# Estado

Última actualización: 2026-10-13 · Sin publicar: v1.4.0 (`gates.yml`, V1) v1.5.0 (`guardia-tests.yml`, V2) y v1.6.0 (`rojo-verde.yml`, V3); ver abajo. Publicada: v1.3.0 (`imagen.yml` con la revisión completa como anotación del índice y outputs `tag`/`revision`; actionlint y selftest sin hallazgos; verificado en ghcr.io: el índice OCI de `ghcr.io/solbeet-pruebas/app-prueba-api:sha-fa1e676`, construido por `solbeet-pruebas/app-prueba` con `@v1` = v1.3.0, trae `org.opencontainers.image.revision` = sha completo, consultado por la API del registro; corrida multi-arch en menos de 2 min). Antes: v1.2.0 (multi-arquitectura)

## v1.6.0 (sin publicar): `rojo-verde.yml`

| Qué | Cómo | Resultado |
|---|---|---|
| Los cuatro caminos con uv y pytest de verdad | `tests/rojo_verde/test_rojo_verde.py` sobre el fixture (macOS, bash 3.2) | 4/4: test nuevo rojo→verde → verde; test espejo → rojo; PR solo de tests → no aplica; test que no pasa con el cambio → rojo |
| Test espejo en un repo real | `solbeet-pruebas/app-prueba#16`: agrega `/api/version` con un test que no lo ejercita | `solbeet / rojo-verde` en rojo («ya pasaba sin el cambio») |
| Contraprueba | `app-prueba#17`: `/api/version` con su test | `solbeet / rojo-verde` en verde, tabla «sin el cambio: falla · con el cambio: pasa» |

No verificado: el dale humano contra la API real (mismo código que la guardia, probado con la API simulada allá). Solo Python: vitest y jest quedan para más adelante.

## v1.5.0 (sin publicar): `guardia-tests.yml`

| Qué | Cómo | Resultado |
|---|---|---|
| Reglas y vía de escape | `tests/guardia/test_guardia.py` (repos git temporales, API de GitHub simulada) | 30/30 casos: borrar, debilitar (assert, valor esperado, caso de parametrize), saltear (decorador, `pytestmark`, conftest, `.only`), tocar aceptación → rojo; tests nuevos, setup, reformateo, mover → verde; label de persona después del push → verde; del autor, de un bot, previo al push o sacado → rojo |
| Trampa estilo ImpossibleBench en un repo real | `solbeet-pruebas/app-prueba#15`: cambia el orden del listado y ajusta el valor esperado del test existente | `solbeet / tests` en rojo; el resto verde |
| Contraprueba | `app-prueba#17` | `solbeet / tests` en verde |
| Falsos positivos sobre historia real | el paso de la guardia reproducido sobre los últimos 30 PRs mergeados de `solbeet-run`, `solbeet-plataforma`, `solbeet-bandeja` y `solbeet-conector` | 23 pasan, 7 frenan; en los 7 el PR cambió de verdad un valor esperado o sacó un test (ninguna detección errónea). Con la primera regla («cualquier cambio a un test existente») frenaban 18 |

No verificado: la vía de escape contra la API real de GitHub (requiere que una persona ponga el label; está cubierta con la API simulada).

## v1.4.0 (sin publicar): `gates.yml`

Verificado en GitHub Actions, no solo local:

| Qué | Cómo | Resultado |
|---|---|---|
| Los cuatro jobs contra el fixture | `selftest / gates` en el PR #12 (llama a `gates.yml` por ruta local, `contract-app: app.main:app`) | verdes; `migraciones` saltea con aviso (el fixture no usa Alembic) |
| Veredictos (heredado vs nuevo) de squawk, contrato y dependencias | `tests/gates/test_gates.py` en `selftest / hygiene-logic` | 12/12 casos |
| Cobertura del cambio baja | `solbeet-pruebas/app-prueba#9`: función nueva sin test | `solbeet / cobertura-cambio` en rojo (25% de las líneas cambiadas), el resto verde |
| Migración con `DROP COLUMN` | `app-prueba#10` | `solbeet / migraciones` en rojo: squawk `ban-drop-column` y pytest-alembic `test_model_definitions_match_ddl` nuevo |
| Secreto en el diff | `app-prueba#11` (token falso con formato de GitHub) | `pr-hygiene / secret-scan` en rojo; los cuatro gates verdes |
| Dependencia vulnerable | `app-prueba#14` (`urllib3==1.26.4`) | `solbeet / dependencias` en rojo con 8 vulnerabilidades altas con arreglo; las 4 heredadas del frontend, aviso |
| Contrato roto | `app-prueba#13`: endpoint que da 500 fuera del caso feliz | `solbeet / contrato` en rojo solo por `GET /api/version/{parte}`; los 500 heredados de `items` como aviso |
| Contraprueba | `app-prueba#12` y `#17`: endpoint nuevo con su test | todo verde |

Hallazgos en el camino:

- `app-prueba` (y por lo tanto la plantilla) tiene errores de contrato heredados: `PATCH /api/items/{id}` con `name: null`, `GET /api/items` con `offset` negativo y otros dan 500. Quedan como aviso en cada PR; conviene arreglarlos en la plantilla.
- La generación de Schemathesis no es igual entre corridas aunque se pida determinista: hizo falta reenviar a la base las peticiones que fallan en el PR (ADR 0007).

## Qué funciona y cómo se verificó

Todo verificado localmente en macOS arm64, con los comandos de `docs/desarrollo.md` tal cual están escritos.

| Qué | Comando | Resultado |
|---|---|---|
| Lint de los 4 workflows y los 3 ejemplos (con shellcheck en el PATH) | `scripts/lint-workflows.sh` | actionlint 1.7.12 sin hallazgos |
| `imagen.yml` y `examples/imagenes.yml` (v1.1.0) | `scripts/lint-workflows.sh` | actionlint 1.7.12 sin hallazgos. No corrió en Actions: falta el primer tag de un servicio para ver la imagen en ghcr.io |
| Los 8 archivos YAML parsean | `yaml.safe_load` sobre `.github/**/*.yml` y `examples/*.yml` | OK |
| Lógica de `pr-hygiene` (job `hygiene`) | `uv run --no-project --with pyyaml==6.0.2 python tests/hygiene/test_pr_hygiene.py` | 12/12 casos con el resultado esperado, incluidos los que deben fallar (sección faltante o vacía, `.rej`, marcadores de conflicto) y el aviso por diff grande excluyendo lockfiles |
| Comandos del job `backend` sobre el fixture | `uv sync --frozen`, `ruff check`, `ruff format --check`, `pyright`, `pytest` | todo en verde; pytest: 3 passed, 1 skipped (el de Postgres, sin `DATABASE_URL`) |
| Test de Postgres del fixture | pytest con `DATABASE_URL` apuntando a un puerto con un servidor escuchando / sin servidor | pasa / falla, como corresponde |
| Comandos del job `frontend` sobre el fixture | `npm ci`, `npm run lint`, `typecheck`, `test`, `build` | todo en verde; node --test: 3 pass |
| Comando de gitleaks de `secret-scan` | `gitleaks git . --log-opts="HEAD^1..HEAD^2" --redact --no-banner --exit-code 1` con el binario 8.30.1 darwin (checksum verificado) en un repo con merge `--no-ff` | detecta una clave agregada en un commit y borrada en el siguiente (exit 1); sin commits en el rango, "no leaks found" |
| Checksums de gitleaks y actionlint | `shasum -a 256 -c` contra el `checksums.txt` de cada release | coinciden |
| Callers que genera `solbeet-template` v0.1.2 (`ci.yml`, `claude-review.yml`, `pr-hygiene.yml`) | `scripts/verificar-plantilla.sh` de la plantilla con actionlint 1.7.12 en el PATH | sin hallazgos; inputs, secretos y ids de job coinciden con `examples/` |
| Paso "Secciones de evidencia" contra las plantillas de PR reales | script del paso extraído del YAML, con `PR_BODY` = plantilla de `solbeet-template` y `plantilla-pr.md` del plugin | plugin v0.1.1: pasa; plantilla sin completar: falla con "sección vacía" (esperado: obliga a escribir el porqué); plugin v0.1.0: fallaba por `## Qué cambia` |
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
- La licencia es un aviso propietario corto ([ADR 0005](decisiones/0005-licencia-propietaria.md)), sin revisión legal.

## Pendientes (en orden)

0. Mergear `integracion/opcion-b`, etiquetar `v1.1.0`, mover `v1` y ver la primera imagen publicada por `imagen.yml` desde un tag de `solbeet-plataforma`.
1. (Hecho: repo publicado hasta v1.0.3.) Crear el repo público `solbeet/workflows` (org `solbeet`), hacer push de `main` y de los tags `v1.0.0`, `v1.0.1`, `v1.0.2` y `v1`, y confirmar que `selftest` pasa en verde en GitHub. Corregir lo que aparezca y publicar `v1.0.3` si hace falta.
2. Probar `claude-review.yml` desde un repo de prueba con un secreto real; ajustar el prompt según los primeros resultados.
3. Ejecutar en GitHub los tres callers desde un proyecto generado con `solbeet-template` (ya los genera, lintados) y configurar la protección de rama con los checks del README.
4. Evaluar un input `runs-on` para runners propios y si conviene exigir que las casillas de `## Evidencia` estén marcadas.
