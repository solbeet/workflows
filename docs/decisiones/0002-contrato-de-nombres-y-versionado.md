# 0002 · Nombres de jobs como contrato y versionado semver con tag mayor móvil

- Estado: aceptada
- Fecha: 2026-10-08

## Contexto

Los clientes llaman a estos workflows con `uses: ...@<ref>` y marcan sus jobs como checks requeridos en la protección de rama. GitHub nombra cada check como `<job del que llama> / <job del reutilizable>` (por ejemplo `ci / backend`). Si un job de este repo cambia de nombre, el check requerido viejo nunca llega y los PRs de todos los clientes quedan bloqueados. Lo mismo pasa si se quita un input que un cliente usa: el workflow falla al validar.

## Decisión

1. Son contrato público: nombres de archivo de los workflows, ids de jobs (`backend`, `frontend`, `review`, `hygiene`, `secret-scan`), inputs, secretos y su semántica. Cada job declara `name:` igual a su id para que el nombre no dependa de cambios accidentales.
2. Versionado semver con tags de git (`vX.Y.Z`) más un tag mayor móvil (`vX`) que apunta a la última `vX.y.z`. Los clientes usan `@v1`.
3. Cambio incompatible ⇒ versión mayor nueva (`v2.0.0` + `v2`); `v1` no se mueve más allá de la última versión compatible.
4. Son incompatibles: renombrar o quitar un job, input o secreto; cambiar un default de forma que cambie el resultado para quien no lo fija (por ejemplo, que un aviso pase a ser error); pedir permisos nuevos al workflow que llama.
5. Son compatibles: inputs nuevos opcionales con default que conserve el comportamiento, arreglos, actualizar versiones fijadas de actions o herramientas sin cambiar el contrato.

## Alternativas descartadas

- **Que los clientes usen `@main`**: cualquier merge rompe a todos al instante y no hay forma de volver atrás por cliente.
- **Solo tags exactos (`@v1.2.3`)**: cada arreglo exige un PR en cada repo cliente. Se deja como opción para quien quiera congelar, no como default.
- **Ramas de release (`releases/v1`)**: equivalentes al tag móvil pero más fáciles de romper con un push directo; el tag se mueve solo en el procedimiento de release.

## Consecuencias

- Un error en una versión `v1.x.y` llega a todos los clientes en su próxima corrida. Mitigación: `selftest.yml` en cada PR, y rollback moviendo `v1` a la versión anterior (`docs/desarrollo.md`).
- Mover un tag requiere `git push -f`; solo lo hace quien publica, siguiendo el procedimiento.
- La documentación de checks requeridos del README depende de estos nombres; se actualiza en el mismo PR que cualquier cambio (solo posible en una versión mayor).
