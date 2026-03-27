# bt — board tool for agents

A minimal task board for running AI agents locally. Agents log progress, request approvals, and deposit files for review — all visible in a web UI served from your machine.

## How it works

- `bt` — CLI used by agents (and you) to manage tasks
- `server.py` — HTTP server that serves the board and dispatches tasks to agents via tmux
- `board.html` — the UI, auto-refreshes every few seconds (pauses while you type)
- Tasks live in `~/.it-board/tasks/`, one markdown file each
- Agents run in a tmux session named `bt-agents`, one window per task

## Supported agents

| Agent | Command |
|-------|---------|
| `claude` | `claude --dangerously-skip-permissions` |
| `codex` | `codex exec --dangerously-bypass-approvals-and-sandbox` |

## Requirements

- Python 3.10+
- tmux
- At least one agent CLI in PATH: `claude` (Claude Code) and/or `codex` (OpenAI Codex)

## Install

```bash
git clone https://github.com/elgidiom/bt ~/.it-board
cd ~/.it-board
bash install.sh
source ~/.zshrc   # or ~/.bashrc
```

`install.sh` will:
- Create `tasks/` and `para-revisar/` directories
- Symlink `bt` to `~/.local/bin/bt`
- Add `IT_BOARD_DIR` and PATH to your shell rc

## Configure workspaces

Copy the example config and edit it:

```bash
cp config.example.json config.json
```

`config.json` maps workspace slugs to local paths. Not committed to git — stays local.

```json
{
  "default": "main",
  "default_agent": "claude",
  "workspaces": {
    "main": {
      "label": "My Project",
      "path": "/home/user/projects/my-project"
    },
    "other": {
      "label": "Other Project",
      "path": "/home/user/projects/other-project",
      "agent": "codex"
    }
  }
}
```

Agent resolution priority: task dispatch modal → workspace `agent` field → `default_agent` → `claude`.

## Start the server

```bash
bt serve
```

Then open `http://localhost:8765` in your browser. To access from another device on the same network (or via Tailscale), use your machine's IP instead of `localhost`.

```bash
bt serve --restart   # restart if already running
```

## bt commands

```
bt new "task description"                    create a new task
bt start <id>                                mark task as in_progress
bt log <id> "message"                        log progress
bt block <id> "reason"                       block task waiting for input or approval
bt done <id> "result"                        close task with one-line result
bt revisar <file> "title" "note" [--task X]  deposit file in review tray
bt ls [pending|in_progress|blocked|done|all] list tasks filtered by status
bt status                                    show task counts per section
bt serve [--port N] [--restart]              start the HTTP server
```

`<id>` can be a partial match (e.g. `bt log foo "msg"` matches any task ID containing "foo").

## Board UI features

- **Dispatch modal** — create a task with workspace and agent selector
- **Approval bar** — tasks blocked with `esperando aprobación:` show ✓/✗ buttons
- **Input bar** — tasks blocked with `esperando input:` show a free-text response field
- **Intervene** — active tasks show a `✎ intervenir` button to send a message or cancel the task
- **Logs** — each task card has a `▸ logs` toggle showing the full progress log
- **Review tray** — files deposited with `bt revisar` appear in a side panel for download/review
- **Auto-refresh** — board updates every 5 seconds, pauses while you are typing

## AGENTS.md

`AGENTS.md` in the repo root contains global instructions loaded into every agent's prompt at dispatch time. Customize it to set logging expectations, approval workflows, and tool conventions.

Add a `CLAUDE.md` (or equivalent) in each workspace directory for project-specific instructions.
