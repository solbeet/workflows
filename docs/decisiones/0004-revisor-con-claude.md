# 0004 · Revisor de PRs con Claude: contexto limpio, token del workflow y no bloqueante

- Estado: aceptada
- Fecha: 2026-10-08

## Contexto

En la fábrica, un agente escribe el código y otro tiene que revisarlo sin haber participado, como haría una segunda persona. La revisión debe seguir el mismo orden en todos los repos (spec, tests, bugs y seguridad, evidencia) y dejar un veredicto legible para quien decide el merge.

## Decisión

- Se envuelve `anthropics/claude-code-action` en `claude-review.yml` con un prompt fijo en español. El revisor arranca sin contexto: lee `AGENTS.md`, el PR, el diff y la spec enlazada en el cuerpo del PR.
- Solo se interpolan en el prompt el nombre del repo y el número de PR. Título, cuerpo y comentarios del PR los lee Claude con `gh pr view`, y el prompt los declara datos, no instrucciones (mitiga inyección de prompt desde el PR).
- Herramientas permitidas: comentario inline, `gh pr comment`, `gh pr diff`, `gh pr view` y `gh issue view` (este último, agregado para leer specs escritas como issues). No puede editar archivos ni hacer push.
- Se pasa `github_token: ${{ github.token }}` en vez de depender de la GitHub App de Claude: funciona en cualquier organización sin instalar nada. Consecuencia: los comentarios los firma `github-actions[bot]`.
- Acepta `ANTHROPIC_API_KEY` o `CLAUDE_CODE_OAUTH_TOKEN`. Sin ninguno, avisa y termina en verde (PRs desde forks no reciben secretos).
- No es un check requerido. Depende de un servicio externo y de secretos; un corte del proveedor no debe frenar los merges. La decisión la toma una persona con el veredicto a la vista.
- Los borradores no se revisan (ahorra costo mientras el PR cambia).

## Alternativas descartadas

- **Hacerlo check requerido o que el veredicto "cambios necesarios" falle el job**: convierte una opinión de un modelo en un bloqueo duro y acopla los merges a la disponibilidad del proveedor. Se puede reconsiderar cuando haya datos de precisión del revisor.
- **Usar la GitHub App de Claude (OIDC)**: requiere instalar la App en cada organización cliente.
- **Prompt configurable por input**: dispersa el criterio de revisión entre clientes. El criterio vive acá; cada repo lo adapta vía su `AGENTS.md`.

## Consecuencias

- Cada revisión consume tokens del cliente. `max-turns` (default 30) acota el costo; la concurrencia cancela la revisión anterior si llega un push nuevo.
- Cambios en la action (inputs, herramientas) pueden romper el workflow; se fija por SHA y se actualiza revisando su changelog.
- El modo de falla silenciosa (sin secretos, termina en verde) puede ocultar una configuración rota: el aviso queda en el log y en las anotaciones del PR.
