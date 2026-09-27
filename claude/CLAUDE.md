# Git workflow

In any git repository, always do non-trivial work (new features, multi-file edits, anything beyond a one-line fix) on a dedicated branch — never directly on `main`/`master` or whatever the currently checked-out branch was at session start. Prefer an actual `git worktree` (a separate working directory via `git worktree add ../<repo>-<branch> -b <branch>`) over an in-place `git checkout -b` when the work will span multiple turns or might need to be set aside — it keeps the primary checkout untouched and lets me switch back to it instantly without stashing. A plain `git checkout -b` in place is acceptable for short-lived, single-turn work where a worktree would be overkill. Only skip branching entirely if the user explicitly says to work directly on the current branch.

# Python projects

For any Python project, set up and run it via `uv`, not the bare system `python3`:

1. If the project has no `pyproject.toml`, scaffold it with `uv init`.
2. Create/use a venv with `uv venv` (or `uv sync` if a lockfile/deps exist), then activate it: `source .venv/bin/activate`.
3. Once the venv is active, run commands as `python ...` / `python -m ...` — drop the `python3` prefix; that's only for the initial system-level bootstrap before a venv exists.
4. Prefer `uv run <cmd>` as a shortcut when you don't want to activate the venv explicitly.
