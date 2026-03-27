#!/usr/bin/env bash
# install.sh — configura it-board como herramienta global
set -e

BOARD_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SHELL_RC=""

echo "IT Board — instalando desde $BOARD_DIR"

# 1. Crear directorios de datos
mkdir -p "$BOARD_DIR/tasks" "$BOARD_DIR/para-revisar"

# 2. Inicializar archivos si no existen
if [ ! -f "$BOARD_DIR/board.md" ]; then
cat > "$BOARD_DIR/board.md" << 'EOF'
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

[ ! -f "$BOARD_DIR/windows.json" ] && echo '{}' > "$BOARD_DIR/windows.json"
[ ! -f "$BOARD_DIR/para-revisar/manifest.json" ] && echo '{"items":[]}' > "$BOARD_DIR/para-revisar/manifest.json"

# 3. Hacer bt ejecutable
chmod +x "$BOARD_DIR/bt" "$BOARD_DIR/server.py"

# 4. Symlink bt → ~/.local/bin/bt
mkdir -p "$BIN_DIR"
if [ -L "$BIN_DIR/bt" ] || [ -f "$BIN_DIR/bt" ]; then
  rm -f "$BIN_DIR/bt"
fi
ln -s "$BOARD_DIR/bt" "$BIN_DIR/bt"
echo "  ✓ bt → $BIN_DIR/bt"

# 5. Detectar shell rc
if [ -f "$HOME/.zshrc" ]; then
  SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
  SHELL_RC="$HOME/.bashrc"
fi

# 6. Agregar IT_BOARD_DIR y PATH si no están ya
if [ -n "$SHELL_RC" ]; then
  MARKER="# it-board config"
  if ! grep -q "$MARKER" "$SHELL_RC" 2>/dev/null; then
cat >> "$SHELL_RC" << EOF

$MARKER
export IT_BOARD_DIR="$BOARD_DIR"
export PATH="\$HOME/.local/bin:\$PATH"
EOF
    echo "  ✓ IT_BOARD_DIR=$BOARD_DIR agregado a $SHELL_RC"
  else
    echo "  ✓ $SHELL_RC ya configurado"
  fi
fi

# 7. Exportar para la sesión actual
export IT_BOARD_DIR="$BOARD_DIR"
export PATH="$BIN_DIR:$PATH"

echo ""
echo "Instalación completa."
echo ""
echo "Comandos disponibles:"
echo "  bt new \"tarea\"           # registrar tarea"
echo "  bt log <id> \"msg\"        # actualizar progreso"
echo "  bt done <id> \"resultado\" # cerrar tarea"
echo "  bt status                 # resumen del board"
echo ""
echo "Para iniciar el servidor:"
echo "  python3 $BOARD_DIR/server.py"
echo ""
echo "Recarga tu shell:  source $SHELL_RC"
