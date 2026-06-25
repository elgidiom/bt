# bt — board tool for agents

A minimal task board for running AI agents locally. Agents log progress, request approvals, and deposit files for review in a web UI served from the same repo.

## Goals

- Run from any clone location without assuming `~/.it-board`
- Avoid mutating shell rc files by default
- Keep the board directory inside the repo unless you explicitly override it

## How it works

- `bt` manages tasks and board state
- `server.py` serves the board and dispatches tasks to agents via `tmux`
- `board.html` is the UI
- Task files live in `./tasks/`
- Agent-to-agent session state lives in `./agent_sessions.json`
- Review artifacts live in `./para-revisar/`

## Requirements

- Python 3.10+
- `tmux`
- At least one agent CLI in `PATH`: `claude` and/or `codex`

## Quick start

```bash
git clone https://github.com/elgidiom/bt
cd bt
bash install.sh
./bt serve
```

Then open `http://localhost:8765/board.html`.

`install.sh` only initializes local files and marks scripts as executable. It does not edit `~/.zshrc`, `~/.bashrc`, or create global symlinks unless you ask for it.

## Optional global launcher

If you want `bt` in `PATH`:

```bash
bash install.sh --link
```

This creates `~/.local/bin/bt` as a symlink to the repo script. Because the script resolves its real path, it still uses this repo as the board directory.

## Board directory resolution

`bt` and `server.py` resolve the board directory in this order:

1. `IT_BOARD_DIR`
2. The real directory where the script lives

That makes the repo self-contained by default, while still allowing advanced users to point the tooling at another board directory.

## Workspace configuration

Copy the example config if you want dispatch targets beyond the board repo itself:

```bash
cp config.example.json config.json
```

`config.json` supports relative paths. Relative workspace paths are resolved from the directory containing `config.json`.

Example:

```json
{
  "default": "main",
  "default_agent": "claude",
  "workspaces": {
    "main": {
      "label": "Main Project",
      "path": "../my-project"
    },
    "other": {
      "label": "Other Project",
      "path": "../other-project",
      "agent": "codex"
    }
  }
}
```

If `config.json` does not exist, the server exposes a single default workspace pointing to this repo.

## Supported agents

| Agent | Command |
|-------|---------|
| `claude` | `claude --dangerously-skip-permissions` |
| `codex` | `codex exec --dangerously-bypass-approvals-and-sandbox` |

## Commands

```text
bt new "task description"
bt start <id>
bt log <id> "message"
bt block <id> "reason"
bt done <id> "result"
bt revisar <file> "title" "note" [--task X]
bt session request <from> <to> "reason"
bt session approve <my_task> <peer_task>
bt session reject <my_task> <peer_task> "reason"
bt session close <my_task> <peer_task> "reason"
bt session msg <from> <to> "message"
bt session ls [task]
bt ls [pending|in_progress|blocked|done|all]
bt show <id>
bt status
bt serve [--port N] [--restart]
```

## Agent sessions

Use agent sessions when two agents need to coordinate without collapsing their work into a single task row.

Flow:

1. Agent A asks for a channel:

```bash
bt session request task-a task-b "necesito pasarte hallazgos del mismo incidente"
```

2. Agent B explicitly approves:

```bash
bt session approve task-b task-a
```

3. Once active, both sides can exchange messages that are:

- appended to both task logs for auditability
- delivered live to the other agent's tmux window when available
- visible later via `bt show <task>`

Example:

```bash
bt session msg task-a task-b "ya confirmé que el error viene del webhook"
```

To stop the channel:

```bash
bt session close task-a task-b "handoff completo"
```

If one of the linked tasks is finalized, `bt` closes any active/pending session automatically so no stale channel remains.

## Google Chat bridge (`itagent`)

Lets you talk to the agents from Google Chat instead of (or in addition to) the board UI.
You `@itagent <request>` in a space; an agent picks it up, works the task, and replies **in the
same Chat thread**. The board stays as the audit log behind the scenes.

### Architecture

```
 Google Chat            NUBE (Apps Script, free)           LOCAL (this repo)
 @itagent  ──POST──►  Chat App webhook                ──► itagent_poller (in server.py)
                      - validates sender allowlist        - reads "inbound" tab every ~10s
                      - writes a row to a Google Sheet     - new row → creates task + dispatches agent
                                                           - acks in the thread
        ▲                                                          │ tmux
        └──────────  itagent_reply.py (Chat API) ◄──── claude agent (writes back to the thread)
```

- **Inbound (Chat → agent):** an Apps Script Chat App validates the sender and appends a row
  `{ts, event_id, type, space, thread, sender, text, status, task_id}` to the `inbound` tab of a
  Google Sheet. No public port on this machine is needed.
- **Poller:** `server.py` starts `itagent_poller` in a background thread on boot
  (`start_itagent_poller`). Each tick reads `pending` rows, marks them `processing`, creates a task
  and dispatches an agent in tmux (`chat_create_and_launch`, same flow as `/api/dispatch` but
  in-process), then marks the row `taken` and acks in the thread.
- **Outbound (agent → you):** the agent's prompt is augmented with the Chat `space`/`thread` and the
  exact `itagent_reply.py` command, so it replies directly via the Chat API. No outbound queue.

### Files

| File | Role |
|------|------|
| `itagent_common.py` | Shared helpers: service-account auth, read/write the Sheet queue, post to Chat |
| `itagent_poller.py` | The bridge loop: drains `pending` rows → dispatch + ack. Standalone or embedded |
| `itagent_reply.py` | One-shot helper the agent runs to write a message back to a thread |
| `server.py` | Hosts the poller (`start_itagent_poller`) and `chat_create_and_launch` |

### Config & secrets

Environment overrides (all optional, sensible defaults):

| Var | Default | Meaning |
|-----|---------|---------|
| `ITAGENT_SA_KEY` | `~/.it-board/itagent-poller-key.json` | Service-account key (gitignored) |
| `ITAGENT_SHEET_ID` | the `inbound` queue Sheet | Queue spreadsheet |
| `ITAGENT_POLL_INTERVAL` | `10` | Seconds between polls |
| `ITAGENT_WORKSPACE` | `it` | Workspace agents are dispatched into |

The service-account key (`itagent-poller-key.json`) is **gitignored** — never commit it. Auth uses
the `spreadsheets` and `chat.bot` scopes. Security relies on the **email allowlist enforced in the
Apps Script**: anyone who can `@itagent` would otherwise be dispatching agents that run with
`--dangerously-skip-permissions` on this host.

### Run it

The poller starts automatically with `./bt serve` (best-effort; logs `poller deshabilitado` and keeps
serving the board if the Google client libs or key are missing). To run the bridge standalone:

```bash
python3 itagent_poller.py   # dispatches via HTTP POST to /api/dispatch
```

## What is still intentionally local

- Agent binaries (`claude`, `codex`) must exist on the host
- Workspace paths in `config.json` are user-specific, even if written relatively
- `tmux` is required for agent dispatch/session management

## Repo publishing checklist

Before publishing broadly, the main remaining gaps are process-level rather than hardcoded-path issues:

- add a license
- add CI for a basic smoke test (`python -m py_compile bt server.py`)
- document supported operating systems and shells
- decide whether `tmux` should remain required or become optional
