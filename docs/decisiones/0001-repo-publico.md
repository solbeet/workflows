# 0001 · El repo de workflows es público

- Estado: aceptada
- Fecha: 2026-10-08

## Contexto

Los repos de los clientes viven en la organización de GitHub de cada cliente, no en la de Solbeet. GitHub solo permite llamar a un workflow reutilizable de otra organización si el repo que lo contiene es público. Un repo privado o interno solo se puede usar desde repos de la misma organización (o de la misma cuenta enterprise, con configuración de acceso explícita).

## Decisión

`solbeet-factory/workflows` es un repo público. Todo su contenido se escribe sabiendo que cualquiera lo puede leer y llamar:

- Ningún secreto, token, hostname o IP interna, nombre de cliente ni de otros productos de la empresa.
- Los secretos los aporta el repo que llama (`secrets:` o `secrets: inherit`), nunca este repo.
- Las credenciales que aparecen (`postgres:postgres` del servicio de tests) son de prueba y solo existen dentro del job efímero.
- Las actions de terceros se fijan por SHA, porque un repo público llamado por muchos es un blanco para ataques de cadena de suministro.

## Alternativas descartadas

- **Repo privado en la organización de Solbeet**: los repos de clientes en otras organizaciones no pueden llamarlo. Descartado por el requisito principal.
- **Copiar los workflows completos a cada repo cliente** (sin reutilizables): cada arreglo habría que replicarlo en N repos y se desincronizan. Se mantiene solo como salida de emergencia para un cliente que no acepte depender de un repo externo.
- **Composite actions en un repo privado + checkout con token**: exige distribuir un token con acceso al repo privado a cada cliente; más superficie de secretos y más fricción.
- **GitHub Enterprise con repos internos compartidos**: requiere que todos los clientes estén en la misma enterprise, lo que no ocurre.

## Consecuencias

- Cualquiera puede ver cómo es el CI de la fábrica. Se acepta: el valor no está en estos YAML sino en el método y la operación.
- Cualquiera puede llamar a estos workflows desde su repo. No tiene costo para Solbeet: corren con los minutos y secretos de quien llama.
- Revisión más estricta de cada PR de este repo: un secreto filtrado acá queda expuesto públicamente. `pr-hygiene` con `secret-scan` corre sobre los PRs de este mismo repo (vía `selftest.yml`).
- Los consumidores dependen de la disponibilidad de este repo. Mitigación: pueden fijar un SHA o, en el peor caso, copiar el YAML.
