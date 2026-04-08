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
bt ls [pending|in_progress|blocked|done|all]
bt show <id>
bt status
bt serve [--port N] [--restart]
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
