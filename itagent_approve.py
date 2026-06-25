#!/usr/bin/env python3
"""itagent_approve — el agente pide a Juan una aprobación/decisión por el espacio privado.

Postea el mensaje en un hilo NUEVO del espacio de aprobaciones ("IT Agent") y
siembra el mapeo hilo→task en la cola (Sheet) para que la respuesta de Juan en
ese hilo enrute de vuelta a ESTA task como REPLY. Luego el agente debe bloquear:
    bt block <task_id> "esperando aprobación: <qué se aprueba>"

Cuando Juan responde en el hilo:
  - texto afirmativo (done/dale/listo/✅…) → el poller finaliza la task (= ✓ board);
  - cualquier otra cosa → va al inbox del agente como instrucción.

Uso:
    python3 itagent_approve.py <task_id> '<mensaje para Juan>'

Imprime el `spaces/.../threads/...` creado.
"""
import sys
import datetime
import itagent_common as ic

# Espacio privado *threaded* Juan + bot, donde se piden las aprobaciones.
APPROVALS_SPACE = "spaces/AAQANyiuwaU"  # "IT Agent"


def seed_thread_mapping(space, thread, task_id):
    """Inserta una fila 'puente' hilo→task en la cola para que findOpenTaskForThread_
    del Apps Script clasifique como REPLY los próximos mensajes de Juan en ese hilo.
    status='taken' para que el poller no la procese como pedido nuevo."""
    now = datetime.datetime.now().isoformat()
    row = [now, f"seed-{task_id}", "MAP", space, thread,
           "itagent-app", "(seed aprobación)", "taken", task_id]
    ic.sheets().spreadsheets().values().append(
        spreadsheetId=ic.SHEET_ID,
        range=f"{ic.SHEET_TAB}!A:I",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()


def main():
    if len(sys.argv) < 3:
        print("uso: itagent_approve.py <task_id> '<mensaje>'", file=sys.stderr)
        sys.exit(2)
    task_id = sys.argv[1]
    text = sys.argv[2]
    # En espacios, la app sólo recibe mensajes que la @mencionan → el footer le
    # dice a Juan exactamente cómo responder para que su respuesta llegue.
    text = text + "\n\n_Para aprobar/cerrar: respondé en este hilo *@itagent dale* (o `listo`/`ok`). Cualquier otra cosa = instrucción._"
    msg = ic.post_message(APPROVALS_SPACE, text)          # hilo nuevo
    thread = (msg.get("thread") or {}).get("name", "")
    if thread:
        seed_thread_mapping(APPROVALS_SPACE, thread, task_id)
    print(thread or msg.get("name", "ok"))


if __name__ == "__main__":
    main()
