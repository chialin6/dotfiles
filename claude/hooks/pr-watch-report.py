#!/usr/bin/env python3
"""SessionStart hook: report unresolved review comments on watched PRs.

Reads ~/.claude/pr-watchlist.json (written by pr-watch-register.sh), resolves
each watched branch to its PR, and emits a compact summary as SessionStart
additionalContext. Exits silently and touches the network zero times when the
watchlist is empty.

Also usable by hand:
    pr-watch-report.py --list          human-readable, always prints
    pr-watch-report.py --drop KEY      forget one entry (KEY is "owner/repo#branch")
    pr-watch-report.py --drop-pr N     forget whichever entry resolved to PR #N
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

WATCHLIST = os.environ.get(
    "PR_WATCHLIST", os.path.expanduser("~/.claude/pr-watchlist.json")
)
STALE_DAYS = 30          # forget a branch that never got a PR after this long
MAX_QUERIES = 10         # bound session-start latency
GH_TIMEOUT = 12          # seconds per gh call

QUERY = """
query($owner:String!, $name:String!, $branch:String!) {
  repository(owner:$owner, name:$name) {
    pullRequests(headRefName:$branch, first:1,
                 orderBy:{field:CREATED_AT, direction:DESC}) {
      nodes {
        number url title state isDraft reviewDecision
        reviewThreads(first:100) {
          nodes {
            isResolved isOutdated
            comments(first:1) {
              nodes { author { login } path line createdAt }
            }
          }
        }
        reviews(last:15) {
          nodes { author { login } state body submittedAt }
        }
        comments(last:15) {
          nodes { author { login } body createdAt }
        }
      }
    }
  }
}
"""


def load():
    try:
        with open(WATCHLIST) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    tmp = WATCHLIST + ".tmp"
    try:
        os.makedirs(os.path.dirname(WATCHLIST), exist_ok=True)
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, WATCHLIST)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(repo, branch):
    """Return the PR dict for repo/branch, or None. Never raises."""
    if "/" not in repo:
        return None
    owner, name = repo.split("/", 1)
    try:
        out = subprocess.run(
            ["gh", "api", "graphql",
             "-f", "query=" + QUERY,
             "-f", "owner=" + owner,
             "-f", "name=" + name,
             "-f", "branch=" + branch],
            capture_output=True, text=True, timeout=GH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        nodes = (json.loads(out.stdout)["data"]["repository"]
                 ["pullRequests"]["nodes"])
    except (ValueError, KeyError, TypeError):
        return None
    return nodes[0] if nodes else None


def summarize(pr, pushed_at):
    """Return (unresolved_threads, fresh_top_level, detail_lines)."""
    since = parse_ts(pushed_at)
    threads = []
    for node in (pr.get("reviewThreads") or {}).get("nodes") or []:
        if node.get("isResolved"):
            continue
        comments = (node.get("comments") or {}).get("nodes") or []
        first = comments[0] if comments else {}
        threads.append({
            "author": ((first.get("author") or {}).get("login") or "?"),
            "path": first.get("path") or "",
            "line": first.get("line"),
            "outdated": bool(node.get("isOutdated")),
        })

    fresh = []
    for node in (pr.get("comments") or {}).get("nodes") or []:
        created = parse_ts(node.get("createdAt"))
        if since and created and created <= since:
            continue
        login = (node.get("author") or {}).get("login") or "?"
        fresh.append(login)
    for node in (pr.get("reviews") or {}).get("nodes") or []:
        if not (node.get("body") or "").strip():
            continue
        submitted = parse_ts(node.get("submittedAt"))
        if since and submitted and submitted <= since:
            continue
        login = (node.get("author") or {}).get("login") or "?"
        state = (node.get("state") or "").replace("_", " ").lower()
        fresh.append("%s (%s)" % (login, state) if state else login)

    lines = []
    if threads:
        authors = sorted({t["author"] for t in threads})
        paths = []
        for t in threads:
            label = t["path"] or "(no file)"
            if label not in paths:
                paths.append(label)
        shown = ", ".join(paths[:3])
        if len(paths) > 3:
            shown += ", +%d more" % (len(paths) - 3)
        stale = sum(1 for t in threads if t["outdated"])
        note = " (%d on outdated lines)" % stale if stale else ""
        lines.append("  %d unresolved thread%s from %s%s — %s"
                     % (len(threads), "" if len(threads) == 1 else "s",
                        ", ".join(authors), note, shown))
    if fresh:
        uniq = sorted(set(fresh))
        lines.append("  new comment%s since your last push: %s"
                     % ("" if len(uniq) == 1 else "s", ", ".join(uniq)))
    return len(threads), len(fresh), lines


def emit(context):
    json.dump({
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
    }, sys.stdout)
    sys.stdout.write("\n")


def main():
    args = sys.argv[1:]
    watchlist = load()

    if args and args[0] == "--drop":
        if len(args) > 1:
            watchlist.pop(args[1], None)
            save(watchlist)
        return
    if args and args[0] == "--drop-pr":
        if len(args) > 1:
            want = re.sub(r"\D", "", args[1])
            for key, entry in list(watchlist.items()):
                if str(entry.get("pr_number") or "") == want:
                    watchlist.pop(key, None)
            save(watchlist)
        return

    human = bool(args and args[0] == "--list")

    if not watchlist:
        if human:
            print("PR watchlist is empty.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    reports, keep, queried = [], {}, 0

    for key, entry in sorted(watchlist.items()):
        repo = entry.get("repo") or ""
        branch = entry.get("branch") or ""
        pushed_at = entry.get("pushed_at")
        seen = parse_ts(entry.get("first_seen")) or parse_ts(pushed_at)

        if not repo or not branch:
            continue
        if queried >= MAX_QUERIES:
            keep[key] = entry
            continue

        queried += 1
        pr = fetch(repo, branch)

        if pr is None:
            # No PR yet (or the lookup failed) — hold the branch until stale.
            if seen and seen < cutoff:
                continue
            keep[key] = entry
            continue

        if (pr.get("state") or "").upper() != "OPEN":
            continue  # merged or closed: stop watching

        entry = dict(entry, pr_number=pr.get("number"), pr_url=pr.get("url"))
        keep[key] = entry

        n_threads, n_fresh, lines = summarize(pr, pushed_at)
        if not (n_threads or n_fresh):
            continue

        title = (pr.get("title") or "").strip()
        if len(title) > 72:
            title = title[:69] + "..."
        header = "%s#%s %s" % (repo, pr.get("number"), title)
        if pr.get("isDraft"):
            header += " [draft]"
        reports.append("\n".join([header] + lines + ["  " + (pr.get("url") or "")]))

    save(keep)

    if human:
        if reports:
            print("Watched PRs with outstanding review comments:\n")
            print("\n\n".join(reports))
        else:
            print("Watching %d PR branch(es); no outstanding review comments."
                  % len(keep))
        return

    if not reports:
        return

    emit(
        "Pull requests you pushed have review comments that are not yet "
        "addressed:\n\n"
        + "\n\n".join(reports)
        + "\n\nTo work through them, run the address-pr-comments skill "
          "(/address-pr-comments, optionally with a PR number). Mention this "
          "to the user at the start of your first reply, but do not begin "
          "changing code for it unless they ask."
    )


if __name__ == "__main__":
    main()
