# AGENTS.md

Repo-specific instructions for Codex CLI and other agents working in this repository.

## Scope

- This repo is a Python CLI + Electron desktop GUI for Stake mirror latency testing and reporting.
- Read `README.md` and `CLAUDE.md` before editing.
- Keep changes narrow and preserve the async/network architecture.
- Core API layer (`src/core/`) is CLI-independent for GUI reuse.

## Operating rules

- Use the commands in `CLAUDE.md` for run/test verification.
- Never commit or log `STAKE_SESSION_TOKEN`.
- Keep `config.yaml` as the source of truth for mirrors and settings.
- Use repo-local `.codex/config.toml` for Codex workspace defaults.
- GUI changes should preserve the JSON-RPC API contract in `src/core/api.py`.

## Codex CLI notes

- Codex CLI should treat this file as the repo guidance source.
- Preserve the existing SQLite history and non-blocking network behavior.
- When modifying core logic, ensure CLI and GUI paths both work correctly.
