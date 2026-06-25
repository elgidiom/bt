#!/usr/bin/env python3
"""itagent_poller — puente Google Chat → bt.

Cada POLL_INTERVAL segundos lee la cola (Sheet) con la service account, y por
cada fila `pending` decide según su columna `type`:

  - NEW   → crea+despacha un agente nuevo (inyecta space/thread + cómo responder),
            ackea en el hilo y marca la fila `taken` + task_id.
  - REPLY → es una respuesta del usuario en un hilo que YA tiene task asociada.
            La entrega al agente existente vía el server local:
              · si la task está "esperando aprobación" y el texto es afirmativo
                ("done", "dale", "listo", ✅…) → POST /api/done (finaliza por vos).
              · en cualquier otro caso → POST /api/respond (va al inbox del agente).

El `type` lo decide el Apps Script de ingestión (busca en el Sheet si el `thread`
ya tiene un `task_id` abierto). Ver alegra-it-chatagent/README.md.

La vuelta (agente → usuario) la hace el propio agente con itagent_reply.py.

Dos formas de correr:
  - Standalone (manual):  python3 itagent_poller.py   → despacha vía HTTP /api/dispatch
  - Embebido en server.py: server importa este módulo, setea `dispatch_impl` a una
    función que lanza el agente directo (sin HTTP), y llama tick() en un hilo.

Arquitectura: ver Alegra/it/docs/chat-agent-bridge-plan.md
"""
import os
import re
import json
import time
import sys
import urllib.request
import itagent_common as ic

POLL_INTERVAL = int(os.environ.get("ITAGENT_POLL_INTERVAL", "10"))
DISPATCH_URL  = os.environ.get("ITAGENT_DISPATCH_URL", "http://localhost:8765/api/dispatch")
WORKSPACE     = os.environ.get("ITAGENT_WORKSPACE", "it")
REPLY_HELPER  = "/home/gidiom/.it-board/itagent_reply.py"
BOARD_DIR     = os.environ.get("IT_BOARD_DIR", "/home/gidiom/.it-board")

# Base del server local (deriva de DISPATCH_URL: …/api/dispatch → …/api).
_API_BASE   = DISPATCH_URL.rsplit("/", 1)[0]
RESPOND_URL = f"{_API_BASE}/respond"
DONE_URL    = f"{_API_BASE}/done"

# Palabras/íconos que interpretamos como "aprobado / cerrá la tarea".
AFFIRMATIVE = {
    "done", "dale", "listo", "ok", "okay", "oka", "aprobado", "aprobada",
    "apruebo", "aprueba", "hecho", "va", "vale", "perfecto", "si", "sí",
    "👍", "✅", "👌",
}


def build_context(text, space, thread):
    reply_cmd = f"python3 {REPLY_HELPER} '{space}' 'TU_MENSAJE' '{thread}'"
    return "\n".join([
        text,
        "",
        "---",
        "[Canal: Google Chat] El usuario te escribió por Google Chat, NO por el board.",
        "Para responderle, pedirle contexto o reportar avance, escribíle por ese mismo hilo ejecutando:",
        f"  {reply_cmd}",
        "(reemplazá TU_MENSAJE por el texto; mantené las comillas simples).",
        "Usá ese canal como vía principal con el usuario. Igual registrá avance con bt log.",
        f"Space: {space}  Thread: {thread}",
    ])


def _http_post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _http_dispatch(context, title):
    """Despacho por defecto (standalone): POST al server /api/dispatch."""
    return _http_post(DISPATCH_URL, {"context": context, "workspace": WORKSPACE, "title": title})

# Inyectable: server.py la reemplaza por un despacho directo (sin HTTP).
# Debe aceptar (context, title) y devolver {"task_id": ...}.
dispatch_impl = _http_dispatch


def read_task_blocker(task_id):
    """Lee el bloqueador actual de la task desde su archivo .md (sección
    '## Bloqueadores'). Devuelve '' si no hay o no se puede leer."""
    path = os.path.join(BOARD_DIR, "tasks", f"{task_id}.md")
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError:
        return ""
    grabbing = False
    for line in lines:
        if line.strip().lower().startswith("## bloqueadores"):
            grabbing = True
            continue
        if grabbing:
            if line.startswith("## "):
                break
            t = line.strip()
            if t:
                return "" if t.lower() == "ninguno" else t
    return ""


def _is_affirmative(text):
    t = (text or "").strip().lower().strip(".!¡ ")
    if not t:
        return False
    if t in AFFIRMATIVE:
        return True
    # primera palabra afirmativa y mensaje corto (evita "ok pero cambiá X")
    first = t.split()[0]
    return first in AFFIRMATIVE and len(t.split()) <= 2


def deliver_reply(task_id, text):
    """Entrega un REPLY del usuario al agente existente. Si la task está
    esperando aprobación y el texto es afirmativo → finaliza (equivale al ✓ del
    board). Si no → al inbox del agente vía /api/respond."""
    blocker = read_task_blocker(task_id)
    waiting_approval = blocker.lower().startswith("esperando aprobación")
    if waiting_approval and _is_affirmative(text):
        _http_post(DONE_URL, {"task_id": task_id,
                              "result": f"aprobado por chat: {text[:80]}"})
        return "done"
    _http_post(RESPOND_URL, {"task_id": task_id, "response": text})
    return "respond"


def process_row(rowdata):
    row = rowdata["row"]
    text = (rowdata["text"] or "").strip()
    space = rowdata["space"]
    thread = rowdata["thread"]
    rtype = (rowdata.get("type") or "NEW").strip().upper()
    task_id = (rowdata.get("task_id") or "").strip()
    title = (text[:48] + "…") if len(text) > 48 else (text or "mensaje de Chat")

    ic.set_status(row, "processing")
    try:
        if rtype == "REPLY" and task_id:
            action = deliver_reply(task_id, text)
            ic.set_status(row, "taken", task_id)
            print(f"[itagent][ok] reply row {row} -> {task_id} ({action})")
            return

        # NEW (default): crear task + despachar agente.
        context = build_context(text, space, thread)
        res = dispatch_impl(context, title)
        task_id = (res or {}).get("task_id", "")
        ic.set_status(row, "taken", task_id)
        try:
            ic.post_message(space, f"👍 Tomé tu pedido (`{task_id}`). Arranco y te escribo por acá.", thread)
        except Exception as e:
            print(f"[itagent][warn] ack falló row {row}: {e}", file=sys.stderr)
        print(f"[itagent][ok] row {row} -> {task_id}")
    except Exception as e:
        ic.set_status(row, "error")
        print(f"[itagent][error] row {row}: {e}", file=sys.stderr)


def tick():
    for rowdata in ic.read_rows():
        if (rowdata.get("status") or "").strip().lower() == "pending":
            process_row(rowdata)


def loop():
    print(f"[itagent] poller activo (cada {POLL_INTERVAL}s, ws={WORKSPACE})", flush=True)
    while True:
        try:
            tick()
        except Exception as e:
            print(f"[itagent][loop-error] {e}", file=sys.stderr, flush=True)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    loop()
