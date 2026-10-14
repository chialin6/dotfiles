---
name: setup-review
description: Review the last week of Claude Code sessions and propose concrete improvements to the Claude Code setup - new hooks, skills, permission allowlist entries, CLAUDE.md rules, settings. Use when the user asks to review or improve their Claude Code setup, asks "what hooks/skills should I add", or when the weekly setup-review job runs it.
---

# Weekly Claude Code setup review

You are reviewing how the user actually used Claude Code over the past week and
proposing changes to their setup. You **propose only**: never edit settings,
hooks, skills or CLAUDE.md in this skill. The user applies what they like.

## 1. Gather

1. The session digest. If the prompt names a digest file, read it. Otherwise run
   `~/.claude/bin/session-digest.py --days 7` and read its output. It lists, per
   session, the prompts typed, tool calls, Bash commands, tool errors,
   interruptions, hook errors and correction-like prompts.
2. The current setup, so you do not propose what already exists:
   - `~/.claude/settings.json` (hooks, permissions, plugins, skillOverrides)
   - `~/.claude/CLAUDE.md`
   - skill names under `~/.claude/skills/` and the skill list in your context
   - `~/.claude/hooks/`
   - the most recent previous report in `~/.claude/setup-reviews/`, if any, so
     you can say which past suggestions were adopted and avoid repeating ones
     that were not.
3. When a pattern needs more evidence, open the specific transcript
   (`~/.claude/projects/*/<session id>.jsonl`) with Grep, not Read: they are large.

## 2. Look for

- **Repeated instructions** the user types across sessions ("use uv", "make a
  branch", "push and open a PR") → a CLAUDE.md rule, or a skill if it is a
  multi-step procedure.
- **Repeated multi-step workflows** (same sequence of tools/commands in several
  sessions) → a skill or slash command.
- **Corrections and interruptions** → what Claude kept getting wrong; a
  CLAUDE.md rule or a PreToolUse hook that blocks the bad action.
- **Recurring tool errors** (wrong flags for macOS `ls`/`sed`, editing before
  reading, missing auth) → CLAUDE.md note, or a hook.
- **Things that should happen every time** (format after edit, run tests before
  stop, notify on completion) → a hook. Hooks are deterministic; memory is not.
- **Read-only commands run often** that likely trigger permission prompts →
  `permissions.allow` entries. Never suggest allowing destructive commands.
- **Hook errors** in the digest → fix the hook.
- **Skills installed but never used**, or disabled ones the user reached for →
  disable or enable.

Only propose something backed by evidence from at least two sessions, or one
painful incident. Fewer, well-evidenced suggestions beat a long list.

## 3. Write the report

Output only the report, as markdown, with this structure:

```
# Claude Code setup review — <date range>

<two-sentence summary of the week: sessions, main projects, biggest friction>

## Suggestions
### 1. <short title>  — <hook | skill | CLAUDE.md | permission | setting>
**Evidence:** <what happened, which sessions (title + short id), how often>
**Change:** <the exact snippet: settings.json JSON, CLAUDE.md text, or a SKILL.md outline>
**Where:** <file path in ~/dotfiles, e.g. claude/settings.json; these files are symlinked into ~/.claude>
**Effort / payoff:** <one line>

## Follow-up on last report
<adopted / still open / dropped — omit if no previous report>

## Noticed, not worth acting on yet
<one-liners>
```

Rank suggestions by payoff. Keep each snippet ready to paste. The user's
`~/.claude` config lives in `~/dotfiles/claude/` (symlinked), so point changes
at the dotfiles path and remind them to branch per their CLAUDE.md.
