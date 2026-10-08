#!/usr/bin/env bash
# Lintea los workflows y los ejemplos con actionlint, igual que el job
# `actionlint` de selftest.yml.
#
# Descarga actionlint en la versión fijada, verifica el checksum SHA-256
# publicado en el release y lo guarda en un directorio de caché del usuario
# (no instala nada en el sistema). Si shellcheck está en el PATH, actionlint
# también revisa los scripts `run:`.
#
# Uso:    scripts/lint-workflows.sh
# Variables opcionales:
#   ACTIONLINT_CACHE_DIR  dónde guardar el binario (default: ~/.cache/solbeet-workflows)
#
# Compatible con bash 3.2 (el bash por defecto de macOS).
set -euo pipefail

# Mantener en sincronía con ACTIONLINT_VERSION en .github/workflows/selftest.yml.
VERSION="1.7.12"

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "$(uname -m)" in
  x86_64|amd64) arch=amd64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) echo "Arquitectura no soportada: $(uname -m)" >&2; exit 1 ;;
esac

# Checksums de actionlint_1.7.12_checksums.txt del release oficial.
case "${os}_${arch}" in
  darwin_amd64) sum=5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644 ;;
  darwin_arm64) sum=aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f ;;
  linux_amd64)  sum=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8 ;;
  linux_arm64)  sum=325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6 ;;
  *) echo "Sistema no soportado: ${os}_${arch}" >&2; exit 1 ;;
esac

cache="${ACTIONLINT_CACHE_DIR:-$HOME/.cache/solbeet-workflows}/actionlint-${VERSION}"
bin="$cache/actionlint"

if [ ! -x "$bin" ]; then
  mkdir -p "$cache"
  file="actionlint_${VERSION}_${os}_${arch}.tar.gz"
  curl -fsSL --retry 3 -o "$cache/$file" \
    "https://github.com/rhysd/actionlint/releases/download/v${VERSION}/${file}"
  if command -v sha256sum >/dev/null 2>&1; then
    echo "${sum}  $cache/$file" | sha256sum -c - >/dev/null
  else
    echo "${sum}  $cache/$file" | shasum -a 256 -c - >/dev/null
  fi
  tar -xzf "$cache/$file" -C "$cache" actionlint
  rm -f "$cache/$file"
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
"$bin" -version | head -n 1
"$bin" -color .github/workflows/*.yml examples/*.yml
echo "actionlint: sin hallazgos."
