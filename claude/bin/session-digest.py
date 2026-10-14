#!/usr/bin/env python3
"""Condense recent Claude Code session transcripts into a markdown digest.

A week of transcripts in ~/.claude/projects runs to tens of megabytes, mostly
tool output, too much to hand a model whole. This keeps the signals that point
at setup improvements: what you typed, which tools and skills ran, the Bash
commands Claude ran, tool errors, interruptions, hook errors, and prompts that
read like corrections. The weekly setup-review skill reads this digest instead
of the raw transcripts.

    session-digest.py [--days 7] [--max-bytes 400000] > digest.md

Standard library only, so it runs before any venv exists.
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PROJECTS = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"
CORRECTION = re.compile(
    r"^(no\b|nope|don'?t|stop|wait|actually|instead|that'?s (wrong|not)|wrong|why did you|you (should|forgot|didn'?t))",
    re.I,
)
INTERRUPT = "[Request interrupted by user"


def clip(s, n):
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def digest_session(path):
    s = {
        "title": None, "cwd": None, "start": None, "prompts": [], "tools": Counter(),
        "bash": [], "skills": Counter(), "errors": [], "interrupts": 0, "hook_errors": [],
        "corrections": [],
    }
    tool_names = {}
    with open(path, errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t = e.get("type")
            if t == "ai-title":
                s["title"] = e.get("aiTitle")
            if e.get("isSidechain"):
                continue
            s["cwd"] = s["cwd"] or e.get("cwd")
            s["start"] = s["start"] or e.get("timestamp")
            msg = e.get("message") or {}
            if t == "assistant":
                for b in msg.get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    name, inp = b.get("name", "?"), b.get("input") or {}
                    tool_names[b.get("id")] = name
                    s["tools"][name] += 1
                    if name == "Bash":
                        s["bash"].append(clip(inp.get("command", ""), 160))
                    elif name == "Skill":
                        s["skills"][inp.get("skill", "?")] += 1
            elif t == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                            name = tool_names.get(b.get("tool_use_id"), "?")
                            s["errors"].append(f"{name}: {clip(text_of(b.get('content')) or str(b.get('content')), 200)}")
                txt = text_of(content)
                if INTERRUPT in txt:
                    s["interrupts"] += 1
                    continue
                if (e.get("origin") or {}).get("kind") == "human" and not e.get("isMeta"):
                    p = txt.strip()
                    if p:
                        s["prompts"].append(clip(p, 300))
                        if CORRECTION.match(p):
                            s["corrections"].append(clip(p, 300))
            elif t == "system" and e.get("hookErrors"):
                s["hook_errors"].extend(clip(str(h), 200) for h in e["hookErrors"])
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--max-bytes", type=int, default=400_000)
    a = ap.parse_args()

    cutoff = time.time() - a.days * 86400
    files = sorted(
        (p for p in PROJECTS.glob("*/*.jsonl") if p.stat().st_mtime >= cutoff),
        key=lambda p: p.stat().st_mtime,
    )
    sessions = [(p, digest_session(p)) for p in files]
    sessions = [(p, s) for p, s in sessions if s["prompts"]]

    tools, skills, bash_heads = Counter(), Counter(), Counter()
    by_project = defaultdict(int)
    for _, s in sessions:
        tools.update(s["tools"])
        skills.update(s["skills"])
        # Drop a leading "cd <dir> &&" so the command itself is what gets counted.
        bash_heads.update(" ".join(re.sub(r"^cd \S+ *(&&|;) *", "", c).split()[:2]) for c in s["bash"] if c)
        by_project[s["cwd"] or "?"] += 1

    out = [f"# Claude Code session digest: last {a.days:g} days\n",
           f"{len(sessions)} sessions with typed prompts.\n",
           "## Totals\n",
           "Sessions by project: " + ", ".join(f"`{k}` {v}" for k, v in sorted(by_project.items(), key=lambda x: -x[1])),
           "\nTool calls: " + ", ".join(f"{k} {v}" for k, v in tools.most_common(25)),
           "\nSkills invoked: " + (", ".join(f"{k} {v}" for k, v in skills.most_common()) or "none"),
           "\nMost common Bash command prefixes: " + ", ".join(f"`{k}` {v}" for k, v in bash_heads.most_common(30)),
           "\n"]
    body = []
    for p, s in sessions:
        sec = [f"## {s['title'] or p.stem}",
               f"`{s['cwd']}` · {s['start']} · id `{p.stem}` · {sum(s['tools'].values())} tool calls · "
               f"{s['interrupts']} interrupts · {len(s['errors'])} tool errors\n",
               "Prompts:"]
        sec += [f"- {x}" for x in s["prompts"][:40]]
        if s["corrections"]:
            sec += ["Correction-like prompts:"] + [f"- {x}" for x in s["corrections"]]
        if s["errors"]:
            sec += ["Tool errors:"] + [f"- {x}" for x in s["errors"][:15]]
        if s["hook_errors"]:
            sec += ["Hook errors:"] + [f"- {x}" for x in s["hook_errors"][:10]]
        if s["bash"]:
            sec += ["Bash (first 25):"] + [f"- `{x}`" for x in s["bash"][:25]]
        body.append("\n".join(sec) + "\n")

    text, budget = "\n".join(out), a.max_bytes
    # Newest sessions are kept first when the digest has to be cut.
    kept = []
    for sec in reversed(body):
        if len(text) + sum(map(len, kept)) + len(sec) > budget:
            kept.append(f"_{len(body) - len(kept)} older sessions omitted to fit the size cap._\n")
            break
        kept.append(sec)
    sys.stdout.write(text + "\n" + "\n".join(reversed(kept)))


if __name__ == "__main__":
    main()
