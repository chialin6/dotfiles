#!/usr/bin/env python3
"""Claude Code hook: append every Bash command Claude runs to ~/.zsh_history.

Registered on PostToolUse / PostToolUseFailure with matcher "Bash" in
claude/settings.json. With SHARE_HISTORY on (oh-my-zsh default), open shells
pick the entries up at their next prompt, so zsh-history-substring-search
(up-arrow) finds commands Claude ran as if you had typed them.

Entries are written in EXTENDED_HISTORY format (": <epoch>:0;<cmd>"), with
multi-line commands continued by a trailing backslash and bytes metafied the
way zsh does, so the file stays readable by zsh. Set CLAUDE_ZSH_HISTFILE to
write somewhere other than ~/.zsh_history. Never fails the tool call.
"""
import json
import os
import sys
import time

# zsh stores NUL and bytes 0x83 (Meta) .. 0xa2 (Marker) as Meta, byte ^ 0x20
META = 0x83


def metafy(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b == 0 or META <= b <= 0xA2:
            out += bytes((META, b ^ 0x20))
        else:
            out.append(b)
    return bytes(out)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    command = (payload.get("tool_input") or {}).get("command", "").strip()
    if not command:
        return

    # zsh writes an embedded newline as backslash-newline
    body = command.replace("\n", "\\\n")
    line = f": {int(time.time())}:0;{body}\n".encode()

    histfile = os.environ.get("CLAUDE_ZSH_HISTFILE") or os.path.expanduser("~/.zsh_history")
    with open(histfile, "ab") as f:
        f.write(metafy(line))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
