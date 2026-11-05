# 0011 · Check de AGENTS.md con la versión del bloque y un token de lectura

Fecha: 2026-11-04 · Estado: propuesta (solbeet/solbeet-metodo#32)

## Contexto

El bloque «Cómo se programa» de los `AGENTS.md` se genera con `metodo agents-md` desde las reglas de una versión de `solbeet-metodo`, y su texto promete que un check de CI falla si difiere. Ese check (`metodo agents-md verificar`) existía en el CI del método pero no en los repos que llevan el bloque. `solbeet-metodo` es un repo privado: el `GITHUB_TOKEN` del repo que llama no lo puede leer.

## Decisión

- Un workflow reutilizable `agents-md.yml` con el job `verificar`, más un caller de pocas líneas en cada repo (`examples/agents-md.yml`).
- La versión del método **no es un input**: se lee del marcador del propio bloque (`version=X.Y.Z`) y esa misma versión elige la CLI (`uvx --from git+...@vX.Y.Z`) y las reglas contra las que se compara. Hay un solo lugar que la declara; subirla es regenerar el bloque.
- Acceso: un secreto `METODO_LECTURA_TOKEN` con solo lectura de `solbeet/solbeet-metodo`, que el caller pasa al reutilizable. Sin el secreto (o en forks) el job falla con `no_medido`, código 3, antes de llamar a nada: el check nunca pasa sin comparar.
- No es check requerido: lo decide una persona.

## Alternativas descartadas

- Sumar un job a `ci.yml` de cada repo: mezcla un control de documentación con el CI de código y hay que repetir el paso en nueve repos; un cambio al paso exigiría tocarlos todos. Además `solbeet-docs`, `solbeet-infra` y otros no tienen `ci.yml`.
- Hacer público `solbeet-metodo`: expone las reglas y los trabajos de los agentes; la decisión de visibilidad no es de este cambio.
- Un input `metodo-version`: dos lugares que pueden diverger (el input y el marcador).
- Que el check salte cuando falta el secreto: un verde que no midió es peor que un rojo.

## Consecuencias

- Hay que crear el secreto (de organización, alcance a los repos que lo usan) y mantenerlo vigente; si vence, el check queda en `no_medido`, no en verde.
- El token viaja en la URL de `uvx --from`. GitHub lo enmascara en los logs por ser secreto; el job no tiene permisos más allá de `contents: read`.
- Hasta que se mueva el tag `v1`, los callers que apuntan a `@v1` no encuentran el workflow.
