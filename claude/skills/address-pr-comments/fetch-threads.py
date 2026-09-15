#!/usr/bin/env python3
"""Print the unresolved review feedback on a pull request as readable markdown.

    fetch-threads.py            # PR for the current branch
    fetch-threads.py 107        # PR by number
    fetch-threads.py --all      # include already-resolved threads too

Exists because the REST API cannot report thread resolution state — only the
GraphQL reviewThreads connection can, and that is the difference between "every
comment ever left" and "what still needs an answer".
"""
import json
import subprocess
import sys

QUERY = """
query($owner:String!, $name:String!, $number:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      number url title state isDraft headRefName baseRefName reviewDecision
      reviewThreads(first:100) {
        nodes {
          id isResolved isOutdated path line originalLine
          comments(first:20) {
            nodes { author { login } body createdAt diffHunk }
          }
        }
      }
      reviews(last:20) {
        nodes { author { login } state body submittedAt }
      }
      comments(last:30) {
        nodes { author { login } body createdAt }
      }
    }
  }
}
"""


def die(msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(1)


def gh(args, **kw):
    try:
        return subprocess.run(["gh"] + args, capture_output=True, text=True,
                              timeout=30, **kw)
    except FileNotFoundError:
        die("gh CLI not found on PATH.")
    except subprocess.TimeoutExpired:
        die("gh timed out.")


def resolve_target(argv):
    number = None
    for arg in argv:
        digits = arg.lstrip("#")
        if digits.isdigit():
            number = int(digits)
    if number is None:
        out = gh(["pr", "view", "--json", "number", "-q", ".number"])
        if out.returncode != 0 or not out.stdout.strip():
            die("No PR found for the current branch. Pass a PR number, or run "
                "this from a branch that has an open PR.\n" + out.stderr.strip())
        number = int(out.stdout.strip())
    repo = gh(["repo", "view", "--json", "nameWithOwner", "-q",
               ".nameWithOwner"])
    if repo.returncode != 0 or "/" not in repo.stdout:
        die("Could not determine the repository. Run this inside a git "
            "checkout with a GitHub remote.\n" + repo.stderr.strip())
    owner, name = repo.stdout.strip().split("/", 1)
    return owner, name, number


def indent(text, prefix="  > "):
    body = (text or "").strip()
    if not body:
        return prefix + "(empty)"
    return "\n".join(prefix + line for line in body.splitlines())


def main():
    argv = sys.argv[1:]
    show_all = "--all" in argv
    owner, name, number = resolve_target([a for a in argv if a != "--all"])

    out = gh(["api", "graphql",
              "-f", "query=" + QUERY,
              "-f", "owner=" + owner,
              "-f", "name=" + name,
              "-F", "number=%d" % number])
    if out.returncode != 0:
        die("GraphQL query failed:\n" + (out.stderr or out.stdout).strip())
    try:
        pr = json.loads(out.stdout)["data"]["repository"]["pullRequest"]
    except (ValueError, KeyError, TypeError):
        die("Unexpected GraphQL response.")
    if not pr:
        die("PR #%d not found in %s/%s." % (number, owner, name))

    print("# %s/%s#%d — %s" % (owner, name, pr["number"], pr.get("title") or ""))
    print()
    print("- state: %s%s   review decision: %s"
          % (pr.get("state"), " (draft)" if pr.get("isDraft") else "",
             pr.get("reviewDecision") or "none"))
    print("- branch: %s -> %s" % (pr.get("headRefName"), pr.get("baseRefName")))
    print("- url: %s" % pr.get("url"))
    print()

    threads = (pr.get("reviewThreads") or {}).get("nodes") or []
    shown = [t for t in threads if show_all or not t.get("isResolved")]
    resolved_count = sum(1 for t in threads if t.get("isResolved"))

    print("## Review threads (%d shown, %d resolved, %d total)"
          % (len(shown), resolved_count, len(threads)))
    print()
    if not shown:
        print("_No unresolved review threads._")
        print()

    for i, thread in enumerate(shown, 1):
        comments = (thread.get("comments") or {}).get("nodes") or []
        path = thread.get("path") or "(no file)"
        line = thread.get("line") or thread.get("originalLine")
        flags = []
        if thread.get("isResolved"):
            flags.append("RESOLVED")
        if thread.get("isOutdated"):
            flags.append("OUTDATED — anchored to code that has since changed; "
                         "verify whether the concern still applies")
        header = "### Thread %d — %s%s" % (
            i, path, (":%s" % line) if line else "")
        print(header)
        print()
        print("- thread id: `%s`" % thread.get("id"))
        if flags:
            print("- flags: %s" % "; ".join(flags))
        print()
        hunk = (comments[0].get("diffHunk") if comments else "") or ""
        if hunk.strip():
            print("Code under discussion:")
            print()
            print("```diff")
            print("\n".join(hunk.strip().splitlines()[-14:]))
            print("```")
            print()
        for comment in comments:
            login = (comment.get("author") or {}).get("login") or "?"
            print("**@%s** (%s):" % (login, comment.get("createdAt") or ""))
            print(indent(comment.get("body")))
            print()

    reviews = [r for r in ((pr.get("reviews") or {}).get("nodes") or [])
               if (r.get("body") or "").strip()]
    if reviews:
        print("## Review summaries")
        print()
        for review in reviews:
            login = (review.get("author") or {}).get("login") or "?"
            print("**@%s** — %s (%s):"
                  % (login, review.get("state") or "",
                     review.get("submittedAt") or ""))
            print(indent(review.get("body")))
            print()

    issue_comments = (pr.get("comments") or {}).get("nodes") or []
    if issue_comments:
        print("## PR conversation comments")
        print()
        for comment in issue_comments:
            login = (comment.get("author") or {}).get("login") or "?"
            print("**@%s** (%s):" % (login, comment.get("createdAt") or ""))
            print(indent(comment.get("body")))
            print()


if __name__ == "__main__":
    main()
