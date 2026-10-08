# 0006 · Publicación de imágenes en ghcr.io con un workflow reutilizable

Fecha: 2026-10-08 · Estado: aceptada

## Contexto

Los servicios de Solbeet (`solbeet-plataforma`, `solbeet-run`, `solbeet-bandeja`, `solbeet-conector`) declaran sus imágenes en `deploy/contract.yaml` como `ghcr.io/solbeet/<repo>-api` (y `-web`), y `solbeet-infra` las fija por tag. Ningún repo tenía un workflow que las publicara.

## Decisión

Un workflow reutilizable `imagen.yml` en este repo, llamado por un `imagenes.yml` en cada repo de servicio al pushear un tag `vX.Y.Z`:

- Registry: `ghcr.io/<owner del repo>/<imagen>`. Autenticación con el `GITHUB_TOKEN` del caller (`packages: write`); sin secretos extra. El paquete queda vinculado al repo por el label `org.opencontainers.image.source`, así hereda su visibilidad (privado).
- Tags: `X.Y.Z` (sin `v`) y `sha-<sha7>`. Nunca `latest`: `solbeet-infra` y los charts fijan versión.
- Plataforma por defecto `linux/amd64` (los servidores de prueba son x86); se puede pedir `linux/arm64` con el input `plataformas`.
- Acciones fijadas por SHA como el resto del repo.

## Alternativas descartadas

- Un workflow por repo copiado a mano: la misma lógica en cuatro lugares.
- Publicar desde la máquina de una persona: sin trazabilidad entre tag de git e imagen.
- Tag `latest`: un deploy no reproducible.

## Consecuencias

- Agregar un workflow es compatible: `v1.1.0` y `v1` se mueve.
- El job `imagen` no es un check requerido (corre en tags, no en PRs).
