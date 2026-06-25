"""itagent — helpers compartidos del puente Google Chat ⇄ bt.

Auth: service account itagent-poller (key local). Lee/escribe la cola (Sheet)
y postea mensajes a Google Chat como la app itagent (scope chat.bot).
"""
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

KEY        = os.environ.get("ITAGENT_SA_KEY", "/home/gidiom/.it-board/itagent-poller-key.json")
SHEET_ID   = os.environ.get("ITAGENT_SHEET_ID", "1mPV15B11zKH0RV718Z7pdf4B4QuWW6CjQVaREeb9LeE")
SHEET_TAB  = "inbound"
SCOPES     = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/chat.bot",
]

# columnas (0-based) de la hoja inbound
COL = {"ts": 0, "event_id": 1, "type": 2, "space": 3, "thread": 4,
       "sender": 5, "text": 6, "status": 7, "task_id": 8}

_creds = None
def _credentials():
    global _creds
    if _creds is None:
        _creds = service_account.Credentials.from_service_account_file(KEY, scopes=SCOPES)
    return _creds

def sheets():
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)

def chat():
    return build("chat", "v1", credentials=_credentials(), cache_discovery=False)


def read_rows():
    """Devuelve lista de dicts {row, ts, event_id, type, space, thread, sender, text, status, task_id}.
    `row` es el número de fila 1-based en el Sheet (header = fila 1)."""
    res = sheets().spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A2:I").execute()
    out = []
    for i, r in enumerate(res.get("values", [])):
        r = r + [""] * (9 - len(r))  # pad
        out.append({
            "row": i + 2,
            "ts": r[0], "event_id": r[1], "type": r[2], "space": r[3],
            "thread": r[4], "sender": r[5], "text": r[6],
            "status": r[7], "task_id": r[8],
        })
    return out


def set_status(row, status, task_id=None):
    """Actualiza status (col H) y opcionalmente task_id (col I) de una fila."""
    values = [[status]] if task_id is None else [[status, task_id]]
    rng = f"{SHEET_TAB}!H{row}" if task_id is None else f"{SHEET_TAB}!H{row}:I{row}"
    sheets().spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=rng,
        valueInputOption="RAW", body={"values": values}).execute()


def post_message(space, text, thread=None):
    """Postea un mensaje a Google Chat como la app itagent.
    Si se pasa `thread`, responde en ese hilo (fallback a hilo nuevo)."""
    body = {"text": text}
    kwargs = {"parent": space, "body": body}
    if thread:
        body["thread"] = {"name": thread}
        kwargs["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
    return chat().spaces().messages().create(**kwargs).execute()
