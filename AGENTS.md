# AGENTS.md · workflows

Workflows reutilizables de GitHub Actions para los repos de clientes. El repo es **público**: todo lo que se escriba acá lo puede leer cualquiera.

## Estructura

```
.github/workflows/
  python-react.yml     CI reutilizable (jobs: backend, frontend)
  claude-review.yml    revisor con Claude (job: review)
  pr-hygiene.yml       higiene de PR y secretos (jobs: hygiene, secret-scan)
  agents-md.yml        bloque «Cómo se programa» de AGENTS.md al día con el método (job: verificar; secreto METODO_LECTURA_TOKEN)
  selftest.yml         CI de este repo: actionlint + fixture + casos de pr-hygiene
.github/dependabot.yml actualiza las actions fijadas por SHA y las deps del fixture
examples/              workflows que copia un repo cliente (también se lintean)
scripts/lint-workflows.sh  actionlint en versión fijada, igual que en CI
scripts/criterios.py       matriz por criterio del job criterios de gates.yml (fuente; va incrustado en el YAML)
scripts/incrustar-criterios.py  copia scripts/criterios.py al paso «Matriz por criterio» de gates.yml
tests/fixture/backend  FastAPI mínimo (uv) que ejercita el job backend
tests/fixture/frontend JS + tsc + node --test que ejercita el job frontend
tests/hygiene/         prueba la lógica de pr-hygiene.yml contra repos git temporales
tests/agents_md/       prueba los pasos de agents-md.yml con un uvx falso y revisa el contrato del workflow y del ejemplo
tests/criterios/       proyecto uv con pytest: tests de scripts/criterios.py y del job criterios (test_ca_33_<n>_*)
docs/                  arquitectura, desarrollo, estado, ADRs
```

## Comandos

Todos desde la raíz del repo. Requieren `git`, `curl`, `uv` y Node 20+ con npm.

```bash
# Lint de workflows y ejemplos (descarga actionlint 1.7.12 verificado a ~/.cache)
scripts/lint-workflows.sh

# Matriz por criterio: script y job criterios de punta a punta (uv y pytest de verdad)
uv run --directory tests/criterios --frozen pytest

# Casos de pr-hygiene (deben fallar los que tienen que fallar)
uv run --no-project --with pyyaml==6.0.2 python tests/hygiene/test_pr_hygiene.py

# agents-md.yml: versión declarada, llamada a uvx y contrato
uv run --no-project --with pyyaml==6.0.2 python tests/agents_md/test_agents_md.py

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

- Los workflows reutilizables corren con el checkout del repo **que llama**, no de este. No se pueden usar scripts de este repo desde `run:`; por eso la lógica va inline. Excepción: el job `criterios` de `gates.yml` lleva incrustado `scripts/criterios.py`; se edita el script y se corre `python3 scripts/incrustar-criterios.py` (tests/criterios falla si difieren).
- Un job de un reutilizable con `permissions:` que el caller no da hace fallar al workflow entero al arrancar, aunque ese job tenga `if:` falso. `gates.yml` pide `issues: read` por el job `criterios`.
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

<!-- metodo:agents-md version=1.6.0 · generado con `metodo agents-md generar`, no editar -->
## Cómo se programa

Sale de las reglas del método 1.6.0 (`reglas/tdd-unitario.md`, `reglas/oficio-y-diseno.md`). No la edites acá: el check de CI falla si difiere de lo generado. Para cambiarla, cambiá la regla en `solbeet/solbeet-metodo` y regenerá con `uvx --from git+https://github.com/solbeet/solbeet-metodo@v1.6.0 metodo agents-md generar --version 1.6.0 --escribir AGENTS.md`. El resto de este archivo es del repo.

### TDD en ciclos chicos

Además de las pruebas de los criterios, el código se escribe con TDD también a nivel unitario: cada regla, caso borde o rama nueva entra por un test. Nada de código de producción sin un test que lo pida.

1. **Rojo.** Escribí un test por vez, el más chico que exprese la próxima regla, y corrélo hasta ver que falle por la razón correcta (la aserción sobre el comportamiento que falta), no por un import roto o un nombre mal escrito. Guardá el nombre del test y el mensaje de la falla.
2. **Verde.** El código mínimo para que ese test pase, sin adelantarte a casos que ningún test pide. Corré los tests del módulo.
3. **Refactor.** Con todo en verde, mejorá nombres, duplicación y estructura de lo que tocaste. Corré los tests después de cada cambio; si algo se pone rojo, volvé al último verde.

Repetí el ciclo hasta cubrir lo que pide la spec. El valor esperado de cada test sale del pedido, nunca de la misma cuenta que hace el código.

#### Que se vea en la historia y en la evidencia

- Cada test nuevo va en un commit igual o anterior al del código que lo hace pasar: puede ir solo, antes, o en el mismo commit que su código, pero nunca después.
- En `## Evidencia` del PR, arriba de la salida en rojo, una línea `Falló primero: <nombre del test> — <mensaje de la falla>` con el primer test que corriste fallando (si hubo pruebas de criterios, la primera de ellas) y, si hay tests unitarios aparte, su primer rojo también.
- Un test que escribiste después del código y que pasa sin el cambio no prueba nada, y la revisión lo bloquea: antes de terminar, reescribilo para que falle sin el cambio, o sacalo y decilo en la evidencia.

### Oficio y diseño

Oficio:

- No entregues lo que no sabés que funciona: si no lo viste andar con un test o una salida real, no está terminado.
- Si algo no se puede hacer bien dentro del alcance, decilo (en `no_verificado` o escalando) en lugar de entregarlo a medias o con atajos escondidos.
- Estado y estimaciones honestos: lo que falta se dice, no se maquilla.
- Dejá lo que tocaste un poco más claro de lo que estaba; nada de refactors fuera del alcance (regla «Cambio mínimo»).

Diseño, con el mismo criterio que para servicios separados:

- Cada módulo tiene una responsabilidad y un contrato explícito: qué recibe, qué devuelve y qué errores da, con tipos.
- Los bordes (HTTP, base de datos, colas, archivos, GitHub, modelos de lenguaje) quedan detrás de una interfaz chica que se reemplaza en los tests por una versión en memoria.
- Donde dos servicios se hablan, tests de contrato fijan la forma del mensaje de los dos lados.
- Nada de dependencias ocultas entre módulos: ni estado global compartido, ni importar internos de otro módulo; lo que un módulo necesita le llega por parámetro.

<!-- /metodo:agents-md -->
