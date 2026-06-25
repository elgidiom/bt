#!/usr/bin/env python3
"""itagent_poller — puente Google Chat → bt.

Cada POLL_INTERVAL segundos lee la cola (Sheet) con la service account, y por
cada fila `pending`:
  1. la marca `processing` (evita doble proceso),
  2. crea+despacha un agente, inyectando el canal de Google Chat (space/thread)
     y cómo responder,
  3. ackea en el hilo de Chat y marca la fila `taken` + task_id.

La vuelta (agente → usuario) la hace el propio agente con itagent_reply.py.

Dos formas de correr:
  - Standalone (manual):  python3 itagent_poller.py   → despacha vía HTTP /api/dispatch
  - Embebido en server.py: server importa este módulo, setea `dispatch_impl` a una
    función que lanza el agente directo (sin HTTP), y llama tick() en un hilo.

Arquitectura: ver Alegra/it/docs/chat-agent-bridge-plan.md
"""
import os
import json
import time
import sys
import urllib.request
import itagent_common as ic

POLL_INTERVAL = int(os.environ.get("ITAGENT_POLL_INTERVAL", "10"))
DISPATCH_URL  = os.environ.get("ITAGENT_DISPATCH_URL", "http://localhost:8765/api/dispatch")
WORKSPACE     = os.environ.get("ITAGENT_WORKSPACE", "it")
REPLY_HELPER  = "/home/gidiom/.it-board/itagent_reply.py"


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


def _http_dispatch(context, title):
    """Despacho por defecto (standalone): POST al server /api/dispatch."""
    payload = json.dumps({"context": context, "workspace": WORKSPACE, "title": title}).encode()
    req = urllib.request.Request(DISPATCH_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Inyectable: server.py la reemplaza por un despacho directo (sin HTTP).
# Debe aceptar (context, title) y devolver {"task_id": ...}.
dispatch_impl = _http_dispatch


def process_row(rowdata):
    row = rowdata["row"]
    text = (rowdata["text"] or "").strip()
    space = rowdata["space"]
    thread = rowdata["thread"]
    title = (text[:48] + "…") if len(text) > 48 else (text or "mensaje de Chat")

    ic.set_status(row, "processing")
    try:
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
