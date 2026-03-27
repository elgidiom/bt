# Agent Board

A minimal task board for Claude agents. Agents log progress, request approvals, and deposit files for review — all visible in a local web UI.

## How it works

- `bt` — CLI used by agents (and you) to manage tasks
- `server.py` — HTTP server that serves the board and dispatches tasks to Claude via tmux
- `board.html` — the UI, auto-refreshes every few seconds
- Tasks live in `~/.it-board/tasks/`, one markdown file each

## Requirements

- Python 3.10+
- tmux
- Claude Code CLI (`claude`) in PATH

## Install

```bash
git clone <repo> ~/.it-board
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

`config.json` maps workspace slugs to local paths where Claude will run. Not committed to git — stays local.

```json
{
  "default": "main",
  "workspaces": {
    "main": {
      "label": "My Project",
      "path": "/home/user/projects/my-project"
    }
  }
}
```

## Start the server

```bash
bt serve
```

Then open `http://localhost:8765` in your browser. To access from another device on the same network (or via Tailscale), use your machine's IP instead of `localhost`.

To restart if already running:

```bash
bt serve --restart
```

## bt commands

```
bt new "task description"         create a new task
bt start <id>                     mark task as in_progress
bt log <id> "message"             log progress
bt block <id> "reason"            block task waiting for input or approval
bt done <id> "result"             close task with one-line result
bt revisar <file> "title" "note"  deposit file in review tray
bt ls                             show board
bt show <id>                      show task file
bt serve                          start the HTTP server
```

`<id>` can be a partial match (e.g. `bt log foo "msg"` matches task ID containing "foo").

## AGENTS.md

`AGENTS.md` in the repo root contains global instructions for all agents. Claude reads this automatically when launched from the board. Customize it to set logging expectations, approval workflows, etc.

Add a `CLAUDE.md` in each workspace directory for project-specific instructions.
