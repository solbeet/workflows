# 0009 · Mutación informativa sobre el diff

Fecha: 2026-10-18 · Estado: propuesta (fase V de la fábrica, ítem V12)

## Contexto

Los gates de cobertura (V1) y la guardia de tests (V2) dicen si hay tests, no si esos tests detectan fallas: un test sin asserts relevantes cubre líneas y no frena nada. La investigación de verificación continua (§1.3: Meta ACH, Atlassian) propone mutar el código cambiado y ver cuántos mutantes detectan los tests. Antes de bloquear con eso hay que saber qué tan ruidoso es.

## Decisión

Un workflow reutilizable `mutacion.yml` con el job `mutacion`, **informativo**:

- Muta solo los archivos de Python que el PR agrega o modifica (sin tests, config ni migraciones) con mutmut 3 (versión fijada), con un tope de `max-minutes` (10 por defecto). Si se agota, informa lo medido y marca «incompleto».
- Puntaje = mutantes detectados (muertos, timeouts, segfaults) sobre los medidos (detectados, sobrevivientes, sin tests, sospechosos). Los no medidos se informan aparte.
- Deja un único comentario por PR con la marca `<!-- solbeet-mutacion -->`: puntaje, diff de cada sobreviviente (hasta `max-survivors`) y una línea JSON con los datos para la medición.
- Al revisor con Claude llega por ese comentario: el prompt de `claude-review.yml` le dice que lo lea como dato. No hay garantía de orden entre los dos checks; si la mutación termina después, el revisor sigue sin esperarla.
- El job no falla por el puntaje ni por un error de la herramienta. No se marca como check requerido.
- Si el repo ya tiene `[tool.mutmut]` en `pyproject.toml`, no se mide: mutmut solo lee su configuración de ahí y no hay forma de acotarla a los archivos del diff sin reescribir el archivo del cliente.

Los datos de cada corrida están en el JSON del comentario. Criterio para pasar a gate: medirlo en 20 PRs reales y decidir con puntaje, duración, tasa de «incompleto» y de falsos sobrevivientes (mutantes equivalentes).

## Alternativas descartadas

- Gate bloqueante desde el principio: sin tasa de ruido medida (mutantes equivalentes, tests lentos) bloquearía PRs sin razón.
- Esperar a la mutación antes de revisar (job `needs`): une dos workflows reutilizables independientes y retrasa el revisor hasta 10 minutos.
- Mutar el repo entero: tarda órdenes de magnitud más y mide código que el PR no tocó.

## Consecuencias

- Permiso de escritura nuevo en el caller: `pull-requests: write` (solo para el comentario). En PRs de forks no hay comentario; queda el resumen del job.
- Costo de cómputo: hasta `max-minutes` por push en PRs que tocan código de Python.
- Solo Python. Stryker para JS/TS queda como ítem aparte.
- Límite medido con mutmut 3.8.0: no muta las funciones con decorador. En el fixture, `@app.get(...)` hace que ninguna ruta de FastAPI genere mutantes, así que el puntaje mide la lógica que vive en funciones sin decorar (servicios, helpers), no los handlers. Si el PR solo toca handlers decorados, el informe dice «no se pudo medir». Es un dato clave para decidir si pasa a gate. mutmut tampoco corre en Windows.
