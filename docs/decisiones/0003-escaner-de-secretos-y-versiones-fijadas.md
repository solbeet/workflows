# 0003 · Escáner de secretos (gitleaks CLI) y versiones fijadas

- Estado: aceptada
- Fecha: 2026-10-08

## Contexto

`pr-hygiene` tiene que detectar secretos que entren en un PR, incluidos los que se agregan en un commit y se borran en otro (siguen en la historia). Tiene que funcionar en repos de cualquier organización sin licencias ni cuentas extra, y este repo es público ([0001](0001-repo-publico.md)), así que todo lo que descarga y ejecuta en los repos de los clientes tiene que ser reproducible y verificable.

## Decisión

### Escáner

Se usa el **binario de gitleaks** descargado del release oficial de GitHub, con versión exacta y verificación SHA-256 contra el `checksums.txt` publicado en ese release, antes de ejecutarlo.

- Se escanean los commits del PR: `gitleaks git . --log-opts="HEAD^1..HEAD^2"` sobre el commit de merge (`HEAD^1` base, `HEAD^2` punta del PR), con checkout de historia completa.
- `--redact` para que el valor del secreto no quede en el log público del job.
- Si el repo cliente tiene `.gitleaks.toml` o `.gitleaksignore`, gitleaks los toma automáticamente.

### Versiones fijadas

| Componente | Versión | Cómo se fija | Dónde |
|---|---|---|---|
| gitleaks | 8.30.1 | versión + SHA-256 (linux x64 y arm64) | `pr-hygiene.yml` (`env`) |
| actionlint | 1.7.12 | versión + SHA-256 (linux y darwin, amd64 y arm64) | `selftest.yml`, `scripts/lint-workflows.sh` |
| actions/checkout | v7.0.1 | SHA del commit del tag | todos los workflows |
| actions/setup-node | v7.0.0 | SHA del commit del tag | `python-react.yml` |
| astral-sh/setup-uv | v10.2.0 | SHA del commit del tag | `python-react.yml`, `selftest.yml` |
| anthropics/claude-code-action | v1.0.245 | SHA del commit del tag | `claude-review.yml` |
| pyyaml (tests de hygiene) | 6.0.2 | `--with pyyaml==6.0.2` | `selftest.yml`, docs |

Eran las últimas versiones estables publicadas al 2026-10-08 (gitleaks 8.30.1 es de marzo de 2026, actionlint 1.7.12 de marzo de 2026), con más de dos semanas de publicadas.

Motivo de fijar por SHA en vez de tag: los tags de git se pueden mover; un tag movido en una action de terceros ejecutaría código nuevo en los repos de todos los clientes sin revisión. El comentario `# vX.Y.Z` al lado del SHA es el que lee Dependabot para proponer actualizaciones.

## Alternativas descartadas

- **`gitleaks/gitleaks-action`**: exige una licencia (`GITLEAKS_LICENSE`) para repos de organizaciones. Cada cliente tendría que conseguirla y configurarla.
- **trufflehog CLI**: alternativa válida, con verificación activa de credenciales contra los proveedores. Se descartó porque la verificación activa hace llamadas de red con los secretos encontrados desde los runners del cliente (indeseable por defecto) y sin ella la ventaja frente a gitleaks es menor. El binario y las reglas de gitleaks son más simples de auditar y de ajustar por repo con `.gitleaks.toml`.
- **Secret scanning / push protection de GitHub**: no está disponible gratis en repos privados de todas las organizaciones (requiere GitHub Advanced Security / Secret Protection). Se recomienda activarlo donde exista, como complemento.
- **Instalar con un gestor de paquetes (apt, brew) o `go install`**: la versión depende del runner y no se verifica el binario.
- **Escanear solo el árbol final del PR (`gitleaks dir`)**: no ve un secreto agregado y borrado dentro del mismo PR.

## Consecuencias

- Las versiones no se actualizan solas. gitleaks y actionlint se actualizan a mano (procedimiento en `docs/desarrollo.md`); las actions, con PRs de Dependabot.
- Si cambian las reglas de gitleaks en una versión nueva pueden aparecer hallazgos nuevos en los clientes: actualizar gitleaks es un cambio minor que se anota en el CHANGELOG.
- Si GitHub no está disponible para descargar el binario, `secret-scan` falla (no pasa en silencio).
