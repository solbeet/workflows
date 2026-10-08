# 0005 · Licencia propietaria en un repo público

- Estado: aceptada
- Fecha: 2026-10-08
- Decide: Solbeet

## Contexto

El repo tiene que ser público para que los repos de clientes en otras organizaciones puedan llamar a sus workflows con `uses:` ([ADR 0001](0001-repo-publico.md)). Un repo público sin archivo de licencia queda con todos los derechos reservados por defecto, pero no lo dice: quien lo lee no sabe qué puede hacer con él. Los demás repos de la fábrica son privados.

## Decisión

`LICENSE` con un aviso propietario: "Copyright (c) 2026 Solbeet. Todos los derechos reservados." El código es visible solo para que los repos de clientes de Solbeet lo llamen con `uses:`; no se otorga licencia de copia, modificación ni redistribución. Los repos privados de la fábrica llevan el mismo encabezado, sin la parte de visibilidad.

## Alternativas descartadas

- **MIT u otra licencia abierta**: permitiría copiar y redistribuir el CI de la fábrica sin acuerdo con Solbeet. Hacer público el repo es una restricción técnica de GitHub, no una decisión de abrir el código.
- **Sin archivo de licencia**: legalmente equivale a todos los derechos reservados, pero deja la duda a quien lo lee.
- **Licencia de código fuente disponible con condiciones (BSL y similares)**: más texto y términos que mantener para un repo de YAML; no aporta frente a un aviso corto.

## Consecuencias

- Cualquiera puede leer y técnicamente llamar a los workflows (GitHub no lo impide); el aviso deja claro que fuera del servicio de Solbeet no hay licencia.
- Si algún día se quiere abrir el repo, se reemplaza `LICENSE` y se escribe un ADR que reemplace a este.
- No incluye texto legal revisado por un abogado: revisar antes de tener clientes que dependan del repo.
