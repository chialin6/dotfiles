#!/usr/bin/env python3
"""Claude Code hook: append the `!` commands you type in Claude Code to ~/.zsh_history.

Only bash-mode input (a prompt starting with `!`) is recorded; commands Claude
runs on its own through the Bash tool are not. Bash mode runs outside the tool
pipeline, so no hook fires for it directly. Instead Claude Code records each one
in the session transcript as a user message "<bash-input>cmd</bash-input>", and
this hook, registered on UserPromptSubmit / Stop / SessionEnd in
claude/settings.json, scans the transcript for entries it has not written yet.
A `!` command therefore reaches history at your next prompt, when Claude
finishes a turn, or when the session ends, stamped with the time you ran it.
With SHARE_HISTORY on (oh-my-zsh default), open shells pick it up at their next
prompt, so zsh-history-substring-search (up-arrow) finds it.

Entries are written in EXTENDED_HISTORY format (": <epoch>:0;<cmd>"), with
multi-line commands continued by a trailing backslash and bytes metafied the
way zsh does, so the file stays readable by zsh. Transcript entry ids already
written are kept in ~/.claude/zsh-history-hook.seen, so resumed sessions, which
replay earlier entries, are not written twice. Set CLAUDE_ZSH_HISTFILE to write
somewhere other than ~/.zsh_history. Never fails the hook.
"""
import fcntl
import json
import os
import re
import sys
from datetime import datetime

# zsh stores NUL and bytes 0x83 (Meta) .. 0xa2 (Marker) as Meta, byte ^ 0x20
META = 0x83
# ids remembered in the seen file; old ones only matter for resumed sessions
MAX_SEEN = 5000

BASH_INPUT = re.compile(r"<bash-input>(.*)</bash-input>", re.DOTALL)
SEEN_FILE = os.path.expanduser("~/.claude/zsh-history-hook.seen")


def metafy(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b == 0 or META <= b <= 0xA2:
            out += bytes((META, b ^ 0x20))
        else:
            out.append(b)
    return bytes(out)


def bang_commands(transcript_path: str):
    """Yield (uuid, epoch, command) for each `!` command in the transcript."""
    with open(transcript_path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            if "<bash-input>" not in raw:
                continue
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if entry.get("type") != "user" or entry.get("isSidechain"):
                continue
            content = (entry.get("message") or {}).get("content")
            if not isinstance(content, str):
                continue
            match = BASH_INPUT.fullmatch(content.strip())
            command = match.group(1).strip() if match else ""
            uuid = entry.get("uuid")
            if not command or not uuid:
                continue
            try:
                stamp = entry["timestamp"].replace("Z", "+00:00")
                epoch = int(datetime.fromisoformat(stamp).timestamp())
            except (KeyError, AttributeError, ValueError):
                continue
            yield uuid, epoch, command


def history_line(epoch: int, command: str) -> bytes:
    # zsh writes an embedded newline as backslash-newline
    body = command.replace("\n", "\\\n")
    return metafy(f": {epoch}:0;{body}\n".encode())


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.isfile(transcript_path):
        return

    # Hooks for one session can overlap (they run async), so hold a lock
    # across read-seen, write-history, update-seen.
    with open(SEEN_FILE, "a+", encoding="utf-8") as seen_f:
        fcntl.flock(seen_f, fcntl.LOCK_EX)
        seen_f.seek(0)
        seen = seen_f.read().split()
        seen_set = set(seen)

        new = [c for c in bang_commands(transcript_path) if c[0] not in seen_set]
        if not new:
            return
        new.sort(key=lambda c: c[1])

        histfile = os.environ.get("CLAUDE_ZSH_HISTFILE") or os.path.expanduser("~/.zsh_history")
        with open(histfile, "ab") as f:
            f.write(b"".join(history_line(epoch, cmd) for _, epoch, cmd in new))

        seen = (seen + [uuid for uuid, _, _ in new])[-MAX_SEEN:]
        seen_f.seek(0)
        seen_f.truncate()
        seen_f.write("\n".join(seen) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
