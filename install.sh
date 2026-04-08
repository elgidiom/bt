#!/usr/bin/env bash
# install.sh — inicializa el repo y opcionalmente crea un launcher global
set -euo pipefail

BOARD_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
LINK_GLOBAL=0

usage() {
  cat <<'EOF'
Uso: bash install.sh [--link]

  --link   crea ~/.local/bin/bt como symlink al script de este repo

Sin flags, la instalación es local al repo y no modifica archivos de shell.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --link)
      LINK_GLOBAL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento no reconocido: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

echo "Agent Board — inicializando en $BOARD_DIR"

mkdir -p "$BOARD_DIR/tasks" "$BOARD_DIR/para-revisar"

if [ ! -f "$BOARD_DIR/board.md" ]; then
cat > "$BOARD_DIR/board.md" <<'EOF'
# Board — IT Agents

> Fuente de verdad del trabajo activo. Leer antes de empezar cualquier tarea.

## Activas

| ID | Tarea | Owner | Estado | Actividad | Actualizado |
|----|-------|-------|--------|-----------|-------------|
| — | — | — | — | — | — |

## En revisión / Bloqueadas

| ID | Tarea | Owner | Bloqueador | Actualizado |
|----|-------|-------|------------|-------------|
| — | — | — | — | — |

## Completadas

| ID | Tarea | Owner | Resultado breve | Fecha |
|----|-------|-------|-----------------|-------|
| — | — | — | — | — |
EOF
  echo "  ✓ board.md creado"
fi

[ -f "$BOARD_DIR/windows.json" ] || printf '{}\n' > "$BOARD_DIR/windows.json"
[ -f "$BOARD_DIR/para-revisar/manifest.json" ] || printf '{"items":[]}\n' > "$BOARD_DIR/para-revisar/manifest.json"

chmod +x "$BOARD_DIR/bt" "$BOARD_DIR/server.py"

if [ "$LINK_GLOBAL" -eq 1 ]; then
  mkdir -p "$BIN_DIR"
  ln -sfn "$BOARD_DIR/bt" "$BIN_DIR/bt"
  echo "  ✓ launcher global: $BIN_DIR/bt"
fi

echo
echo "Instalación completa."
echo
echo "Uso local:"
echo "  ./bt status"
echo "  ./bt serve"
echo
if [ "$LINK_GLOBAL" -eq 1 ]; then
  echo "Uso global:"
  echo "  bt status"
  echo "  bt serve"
  echo
else
  echo "Launcher global opcional:"
  echo "  bash install.sh --link"
  echo
fi
echo "Configuración opcional:"
echo "  cp config.example.json config.json"
