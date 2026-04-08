#!/usr/bin/env python3
"""Agent Board Server — sirve el board y despacha tareas a agentes vía tmux."""

import json, os, re, shlex, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR   = Path(__file__).resolve().parent
BOARD_DIR    = Path(os.environ.get("IT_BOARD_DIR", str(SCRIPT_DIR))).expanduser().resolve()
BT           = BOARD_DIR / "bt"
WINDOWS_FILE = BOARD_DIR / "windows.json"
CONFIG_FILE  = BOARD_DIR / "config.json"
PORT         = int(os.environ.get("PORT", 8765))
TMUX_SESSION = os.environ.get("IT_TMUX_SESSION", "bt-agents")

# Comando base por agente. El prompt se añade como último argumento (quoted).
AGENT_CMDS = {
    "claude": "claude --dangerously-skip-permissions",
    # `codex exec` exits as soon as it returns a final answer, which leaves
    # blocked/review tasks orphaned because the tmux window disappears before
    # the user can answer from the board. Use the interactive CLI instead.
    "codex":  "codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen",
}
DEFAULT_AGENT = "claude"

BOARD_TEMPLATE = """# Board — IT Agents

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
"""

MIME = {
    ".html": "text/html; charset=utf-8",
    ".md":   "text/plain; charset=utf-8",
    ".json": "application/json",
    ".css":  "text/css",
    ".js":   "application/javascript",
    ".pdf":  "application/pdf",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
}


def ensure_board_layout():
    (BOARD_DIR / "tasks").mkdir(parents=True, exist_ok=True)
    (BOARD_DIR / "para-revisar").mkdir(parents=True, exist_ok=True)
    if not (BOARD_DIR / "board.md").exists():
        (BOARD_DIR / "board.md").write_text(BOARD_TEMPLATE)
    if not WINDOWS_FILE.exists():
        WINDOWS_FILE.write_text("{}\n")
    manifest = BOARD_DIR / "para-revisar" / "manifest.json"
    if not manifest.exists():
        manifest.write_text('{"items":[]}\n')


def resolve_workspace_path(raw_path: str) -> str:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (CONFIG_FILE.parent / path).resolve()
    return str(path)


def load_config() -> dict:
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except Exception:
        cfg = {
            "default": "board",
            "workspaces": {
                "board": {
                    "label": "Board repo",
                    "path": str(BOARD_DIR),
                }
            },
        }
    for ws in cfg.get("workspaces", {}).values():
        raw_path = ws.get("path")
        if raw_path:
            ws["path"] = resolve_workspace_path(raw_path)
    # Siempre exponer la lista de agentes soportados al UI
    cfg.setdefault("agents", list(AGENT_CMDS.keys()))
    cfg.setdefault("default_agent", DEFAULT_AGENT)
    return cfg


def read_windows() -> dict:
    try:
        if WINDOWS_FILE.exists():
            return json.loads(WINDOWS_FILE.read_text())
    except Exception:
        pass
    return {}


def write_windows(data: dict):
    WINDOWS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def find_tmux_window(slug: str) -> str | None:
    r = subprocess.run(
        ["tmux", "list-windows", "-t", TMUX_SESSION, "-F", "#{window_index} #{window_name}"],
        capture_output=True, text=True
    )
    for line in r.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and slug in parts[1]:
            return parts[0]
    return None


def close_task_window(task_id: str):
    windows = read_windows()
    slug = windows.pop(task_id, None)
    if slug is not None:
        write_windows(windows)
    slug = slug or task_id.replace("task-", "")[-22:]
    window_idx = find_tmux_window(slug)
    if window_idx is not None:
        subprocess.run(
            ["tmux", "kill-window", "-t", f"{TMUX_SESSION}:{window_idx}"],
            capture_output=True
        )


def finalize_task(task_id: str, result: str) -> subprocess.CompletedProcess:
    close_task_window(task_id)
    return subprocess.run(
        [str(BT), "finalize", task_id, result],
        capture_output=True, text=True,
        env={**os.environ, "IT_BOARD_DIR": str(BOARD_DIR)}
    )


def read_task_blocker(task_id: str) -> str:
    """Devuelve el texto del bloqueador actual de la tarea, o '' si no tiene."""
    task_file = BOARD_DIR / "tasks" / f"{task_id}.md"
    if not task_file.exists():
        return ""
    in_blocker = False
    for line in task_file.read_text().splitlines():
        if line.strip() == "## Bloqueadores":
            in_blocker = True
            continue
        if in_blocker:
            if line.startswith("## "):
                break
            stripped = line.strip()
            if stripped and stripped != "ninguno":
                return stripped
    return ""


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.lstrip("/")

        # API endpoints
        if path == "api/config":
            return self.send_json(200, load_config())

        if path.startswith("api/task/") and path.endswith("/progress"):
            task_id = path[len("api/task/"):-len("/progress")]
            return self._task_progress(task_id)

        # Archivos estáticos desde BOARD_DIR
        if not path or path == "board.html":
            path = "board.html"

        try:
            target = (BOARD_DIR / path).resolve()
            target.relative_to(BOARD_DIR)
        except (ValueError, RuntimeError):
            self.send_response(403); self.end_headers(); return

        # Si es directorio, buscar index.html dentro
        if target.is_dir():
            target = target / "index.html"

        if not target.exists() or not target.is_file():
            self.send_response(404); self.end_headers(); return

        data = target.read_bytes()
        mime = MIME.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self):
        if self.path == "/api/dispatch":
            self._dispatch()
        elif self.path == "/api/respond":
            self._respond()
        elif self.path == "/api/done":
            self._done()
        elif self.path == "/api/cancel":
            self._cancel()
        else:
            self.send_response(404); self.end_headers()

    def _dispatch(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            return self.send_json(400, {"error": "JSON inválido"})

        context      = (body.get("context")     or "").strip()
        workspace_id = (body.get("workspace")   or "").strip()
        agent_id     = (body.get("agent")       or "").strip()

        if not context:
            return self.send_json(400, {"error": "context es requerido"})

        # Generar título desde las primeras palabras del contexto
        title = (body.get("title") or "").strip()
        if not title:
            words = context.split()
            title = " ".join(words[:8])
            if len(words) > 8:
                title += "…"

        # Resolver workspace y agente
        cfg = load_config()
        if not workspace_id or workspace_id not in cfg.get("workspaces", {}):
            workspace_id = cfg.get("default", "")
        ws_info  = cfg.get("workspaces", {}).get(workspace_id, {})
        ws_path  = ws_info.get("path", str(BOARD_DIR))
        ws_label = ws_info.get("label", workspace_id)
        if not Path(ws_path).exists():
            return self.send_json(400, {
                "error": f"workspace inválido: {workspace_id}",
                "detail": f"La ruta no existe: {ws_path}",
            })

        # Prioridad: body > workspace config > default global
        if not agent_id or agent_id not in AGENT_CMDS:
            agent_id = ws_info.get("agent", "") or cfg.get("default_agent", DEFAULT_AGENT)
        if agent_id not in AGENT_CMDS:
            agent_id = DEFAULT_AGENT

        # 1. Registrar en bt (--desc preserva el input completo para agentes que retomen)
        result = subprocess.run(
            [str(BT), "new", title, "--workspace", workspace_id, "--owner", agent_id,
             "--desc", context],
            capture_output=True, text=True, cwd=ws_path,
            env={**os.environ, "IT_BOARD_DIR": str(BOARD_DIR)}
        )
        task_id = None
        for line in (result.stdout + result.stderr).splitlines():
            if "creada:" in line:
                task_id = line.split("creada:")[-1].strip()
                break

        if not task_id:
            return self.send_json(500, {
                "error": "No se pudo crear la tarea",
                "detail": result.stdout + result.stderr
            })

        # 2. Armar prompt
        agents_md = (BOARD_DIR / "AGENTS.md").read_text() if (BOARD_DIR / "AGENTS.md").exists() else ""
        prompt = "\n".join([
            agents_md,
            "---",
            f"Tu tarea ya está registrada en el board con ID: {task_id}",
            f"Workspace activo: {ws_label} ({ws_path})",
            f"NO uses 'bt new' — el task ya existe.",
            "",
            f"TAREA: {context}",
            "",
            f"Empieza ahora con: bt start {task_id}",
        ])

        # 3. Lanzar en tmux
        slug = task_id.replace("task-", "")[-22:]
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", TMUX_SESSION],
            capture_output=True
        )
        # Exporta IT_BOARD_DIR y asegura que el repo del board quede en PATH
        # para que el agente use este bt incluso sin symlink global.
        # Al terminar claude, la ventana tmux se cierra sola (via bt done o el fallback).
        bin_dirs  = [str(SCRIPT_DIR), str(Path.home() / ".local" / "bin")]
        agent_cmd = AGENT_CMDS[agent_id]
        cmd = (
            f"export IT_BOARD_DIR={shlex.quote(str(BOARD_DIR))} && "
            f"export PATH={shlex.quote(':'.join(bin_dirs))}:\"$PATH\" && "
            f"cd {shlex.quote(ws_path)} && "
            f"{agent_cmd} {shlex.quote(prompt)}"
        )
        subprocess.Popen(
            ["tmux", "new-window", "-t", f"{TMUX_SESSION}:", "-n", slug, cmd]
        )

        # Guardar mapeo task_id → slug en windows.json
        windows = read_windows()
        windows[task_id] = slug
        write_windows(windows)

        self.send_json(200, {"ok": True, "task_id": task_id, "workspace": ws_label})

    def _done(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            return self.send_json(400, {"error": "JSON inválido"})

        task_id = (body.get("task_id") or "").strip()
        result = (body.get("result") or "completada manualmente desde el board").strip()
        if not task_id:
            return self.send_json(400, {"error": "task_id requerido"})

        done = finalize_task(task_id, result)
        if done.returncode != 0:
            return self.send_json(500, {
                "error": "no se pudo marcar la tarea como done",
                "detail": (done.stdout + done.stderr).strip(),
            })

        self.send_json(200, {"ok": True, "task_id": task_id, "result": result})

    def _cancel(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            return self.send_json(400, {"error": "JSON inválido"})

        task_id = (body.get("task_id") or "").strip()
        result = (body.get("result") or "cancelada manualmente desde el board").strip()
        if not task_id:
            return self.send_json(400, {"error": "task_id requerido"})

        canceled = finalize_task(task_id, result)
        if canceled.returncode != 0:
            return self.send_json(500, {
                "error": "no se pudo cancelar la tarea",
                "detail": (canceled.stdout + canceled.stderr).strip(),
            })

        self.send_json(200, {"ok": True, "task_id": task_id, "result": result})

    def _task_progress(self, task_id: str):
        if not re.match(r'^task-[\w-]+$', task_id):
            return self.send_json(400, {"error": "ID inválido"})
        task_file = BOARD_DIR / "tasks" / f"{task_id}.md"
        if not task_file.exists():
            return self.send_json(404, {"error": "tarea no encontrada"})
        content = task_file.read_text()
        lines = content.splitlines()
        in_section = False
        result_lines = []
        for line in lines:
            if line.strip() == "## Progreso":
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                result_lines.append(line)
        progress = "\n".join(result_lines).strip()
        self.send_json(200, {"task_id": task_id, "progress": progress})

    def _respond(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            return self.send_json(400, {"error": "JSON inválido"})

        task_id  = (body.get("task_id")  or "").strip()
        response = (body.get("response") or "adelante").strip()

        if not task_id:
            return self.send_json(400, {"error": "task_id requerido"})

        # Detectar si es una aprobación de cierre — en ese caso finalize directamente
        # sin volver al agente (que ya terminó su turno al llamar bt done).
        blocker = read_task_blocker(task_id)
        is_close_approval = blocker.startswith("esperando aprobación: cerrar")

        if is_close_approval:
            # El cierre (✓ Done) llega por /api/done, no por aquí.
            # Lo que llega aquí es siempre una intervención: desbloquear y enviar al agente.
            subprocess.run(
                [str(BT), "start", task_id],
                capture_output=True, text=True,
                env={**os.environ, "IT_BOARD_DIR": str(BOARD_DIR)}
            )
            windows = read_windows()
            slug = windows.get(task_id) or task_id.replace("task-", "")[-22:]
            window_idx = find_tmux_window(slug)
            if window_idx is not None:
                subprocess.run([
                    "tmux", "send-keys", "-t", f"{TMUX_SESSION}:{window_idx}",
                    response, "Enter"
                ])
            return self.send_json(200, {"ok": True, "intervened": True, "task_id": task_id,
                                        "sent": response})

        # Flujo normal: enviar mensaje al agente vía tmux
        windows = read_windows()
        slug = windows.get(task_id) or task_id.replace("task-", "")[-22:]

        window_idx = find_tmux_window(slug)
        if window_idx is None:
            return self.send_json(404, {"error": f"Ventana tmux no encontrada para {task_id}"})

        subprocess.run([
            "tmux", "send-keys", "-t", f"{TMUX_SESSION}:{window_idx}",
            response, "Enter"
        ])

        self.send_json(200, {"ok": True, "sent": response, "window": window_idx})


if __name__ == "__main__":
    try:
        ip = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.strip().split()[0]
    except Exception:
        ip = "?"

    ensure_board_layout()

    HTTPServer.allow_reuse_address = True
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Agent Board Server")
    print(f"  Board dir: {BOARD_DIR}")
    print(f"  Local:     http://localhost:{PORT}/board.html")
    print(f"  Red:       http://{ip}:{PORT}/board.html")
    print("Ctrl+C para detener")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
