# Agent Board — Instrucciones globales

Este documento aplica a **todos los agentes** lanzados desde el board, sin importar el workspace.

---

## Board Tool (`bt`)

`bt` es el CLI central para gestionar tareas. Está en `~/.local/bin/bt` y escribe al board en `~/.it-board/`.

**NUNCA** editar `board.md` a mano. **NUNCA** usar TaskCreate de Claude. **SIEMPRE** `bt`.

### Comandos

```bash
bt start <id>                    # marcar tarea como in_progress (hazlo primero)
bt log <id> "mensaje"            # registrar progreso (úsalo frecuentemente)
bt block <id> "razon"            # bloquear tarea esperando aprobación o input
bt done <id> "resultado"         # cerrar tarea con resultado en una línea
bt revisar <archivo> "titulo" "nota" --task <id>  # depositar archivo en bandeja de revisión
bt ls                            # ver board completo
bt show <id>                     # ver archivo de tarea
```

El `<id>` puede ser parcial (ej: `bt log prueba "avanzando"` si el ID contiene "prueba").

### Flujo estándar

```
bt start <id>
  → bt log <id> "qué vas a hacer primero"
  → hacer acción
  → bt log <id> "resultado de la acción"
  → bt log <id> "siguiente paso"
  → ...
bt done <id> "resultado en una línea"
```

**Regla de oro: `bt log` antes Y después de cada acción relevante.** No acumules logs al final.

Acciones que SIEMPRE requieren `bt log`:
- Buscar en Linear, Notion, GWS, etc.
- Encontrar (o no encontrar) un resultado
- Ejecutar un comando o llamada a API
- Detectar un error o bloqueo
- Hacer una pregunta al usuario

---

## Cuándo pedir aprobación y cuándo bloquear

### Bloquear por aprobación (acción irreversible o externa)

Si vas a ejecutar una acción irreversible o visible externamente (enviar correo, modificar datos de producción, eliminar usuarios, cambiar permisos, etc.):

1. Si hay un archivo que el usuario debe ver primero (PDF, borrador, reporte): depositarlo con `bt revisar` **antes** de bloquear.
2. Bloquear: `bt block <id> "esperando aprobación: <descripción breve de la acción>"`.
3. Mostrar en pantalla el detalle completo de lo que se va a hacer.
4. Esperar respuesta del usuario antes de continuar.
5. Cuando te aprueben: `bt start <id>` y ejecutar.

**El texto del bloqueador debe empezar con "esperando aprobación:"** — el board lo detecta y muestra los botones ✓/✗ al usuario.

### Bloquear por input del usuario (necesitas información para continuar)

Si necesitas que el usuario aclare algo antes de continuar (qué ticket es, qué correo usar, cuál es el grupo, etc.):

1. Loguear lo que encontraste hasta ahora: `bt log <id> "búsqueda realizada, resultado: ..."`.
2. Bloquear: `bt block <id> "esperando input: <pregunta concreta>"`.
3. Hacer la pregunta en pantalla.
4. Cuando el usuario responda: `bt start <id>` y continuar.

**Nunca dejes una pregunta al usuario sin bloquear la tarea.** Preguntar sin bloquear rompe el flujo del board.

---

## `bt revisar` — bandeja de revisión

Úsalo cuando generes un archivo que el usuario debe aprobar antes de que continues:

```bash
bt revisar /ruta/al/archivo.pdf "Borrador correo Nubosoft" "revisar tono y adjunto" --task <id>
```

Esto copia el archivo a `~/.it-board/para-revisar/`, lo registra en el manifest y lo hace visible en `board.html`.

**Siempre pasá `--task <id>`** — cuando la tarea se cierre con `bt done`, todos sus items de para-revisar se eliminan automáticamente.

**Cuándo usarlo:**
- Generaste un PDF, doc o borrador que necesita aprobación.
- El archivo es el insumo para una decisión del usuario.

**Cuándo NO usarlo:**
- Evidencia interna de tarea completada → va a `docs/evidence/` del workspace.
- Capturas o logs temporales de depuración → eliminar al cerrar la tarea.

---

## Al terminar una tarea

`bt done` cierra la tarea, la mueve a Completadas en el board y cierra la terminal automáticamente.

El resultado debe ser **una línea concisa** con qué se hizo y el outcome clave:
```bash
bt done <id> "correo enviado a soporte@nubosoft.com, adjunto PDF 3 págs, smtp 250"
```

---

## Reglas generales

- Empezar siempre con `bt start` antes de hacer cualquier cosa.
- `bt log` antes Y después de cada acción relevante — nunca acumular logs al final.
- Si necesitas input del usuario: `bt block <id> "esperando input: <pregunta>"` y luego preguntar.
- Si la acción requiere aprobación: `bt block <id> "esperando aprobación: <acción>"` y detallar en pantalla.
- Si te bloqueas por permisos o error técnico: `bt block <id> "bloqueado: <causa exacta>"`.
- No dejar tareas en `in_progress` sin actividad — si no puedes continuar, bloquear con motivo.
- Al terminar, leer las instrucciones del workspace (`CLAUDE.md`) para ver si hay pasos adicionales (handoffs, evidencia, etc.).

### Resumen de prefijos para `bt block`

| Prefijo | Cuándo usarlo |
|---------|--------------|
| `esperando aprobación:` | Acción irreversible o externa pendiente de ✓/✗ |
| `esperando input:` | Necesito datos del usuario para continuar |
| `bloqueado:` | Error técnico o de permisos que impide avanzar |
