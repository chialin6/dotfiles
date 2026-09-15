---
name: address-pr-comments
description: Work through the unresolved review comments on a pull request — fetch every unresolved thread, triage what each one actually asks for, and apply the changes in the working tree. Use when review feedback has landed on a PR (a session-start notice, "address the PR comments", "what did the reviewer say", "fix the review feedback"), or after pushing to a PR that already has open threads.
---

# Address PR review comments

Turn review feedback into code changes, without losing track of which comments
were answered and which were deliberately declined.

## 1. Fetch

```bash
python3 ~/.claude/skills/address-pr-comments/fetch-threads.py [PR_NUMBER]
```

With no argument it resolves the PR from the current branch. Add `--all` to see
resolved threads too (rarely needed — resolved means someone already dealt with
it). Run it from inside the repo checkout.

The output has three sections: **review threads** (inline comments, the ones
that carry resolution state), **review summaries** (the body of an
approve/request-changes review), and **PR conversation comments**. All three can
contain real asks. Only the first has a resolved/unresolved flag, so the other
two are easy to miss — read them.

If the PR is in another checkout, the watchlist entry records where:
`jq . ~/.claude/pr-watchlist.json`.

## 2. Triage before editing

Sort every thread into one of four buckets and say which is which. Do this
first, as a list, before touching any file — it is the part a reviewer will
check, and it stops you from mechanically applying a suggestion that is wrong.

- **Fix** — the comment is right and the change is clear.
- **Fix differently** — the concern is real, the suggested remedy is not. Say
  what you are doing instead and why.
- **Already addressed** — a later commit fixed it. Verify by reading the
  current file, not by assuming. Common on threads flagged `OUTDATED`.
- **Decline** — the comment is mistaken, or asks for something that conflicts
  with the design. Give the reason plainly and leave the code alone. Never
  silently skip a thread; an unmentioned thread reads as an oversight.

Two things that reliably need judgment:

**`OUTDATED` threads.** The comment is anchored to a diff hunk that no longer
matches the file. Read the current code at that path before deciding — the
concern may be gone, may have moved, or may still be live with different line
numbers. Automated reviewers produce these in bulk after a rebase or force-push.

**Bot vs human.** Comments from `github-actions`, `coderabbit`, and similar are
worth reading and are often right, but they are also the source of most
false positives and they carry no authority about intent. A human reviewer's
"please don't do it this way" outranks a bot's suggestion every time. When a bot
and a human conflict, follow the human and note the conflict.

Also watch for comments that contradict each other, or that ask for something
the PR deliberately does not do. Surface the tension rather than picking a side
silently.

## 3. Apply

Group the work by file and make the edits. Match the surrounding code's idiom.
If a comment asks for a test, write the test and run it.

Where a fix is larger than the comment implies — a rename that touches twenty
call sites, a refactor the comment gestures at — do the mechanical part and flag
the scope in your report rather than expanding the PR without saying so.

Run whatever the project uses to check itself (test suite, linter, type check)
before reporting done. In a Python project that means `uv run …` per the global
convention, not bare `python3`.

## 4. Report, then stop

Give a compact table: thread, file, disposition, what changed.

Then **stop.** Do not commit, do not push, do not reply on GitHub, and do not
resolve threads unless the user asks in this session. Review comments are a
conversation with a person, and pushing an answer they have not seen turns a
disagreement into a fait accompli. Show the work and let them decide.

Close by naming the next step — commit and push, or discuss the declines first.

## 5. When the user does want it posted

Reply into a thread (thread ids come from the fetch output):

```bash
gh api graphql -f query='
  mutation($threadId:ID!, $body:String!) {
    addPullRequestReviewThreadReply(input:{
      pullRequestReviewThreadId:$threadId, body:$body
    }) { comment { url } }
  }' -f threadId=PRRT_xxx -f body='Fixed in <sha> — <one line on what changed>.'
```

Resolve a thread (do this only for threads actually dealt with, and only with
the user's go-ahead — a resolve is visible to the reviewer and dismisses their
comment):

```bash
gh api graphql -f query='
  mutation($threadId:ID!) {
    resolveReviewThread(input:{threadId:$threadId}) { thread { isResolved } }
  }' -f threadId=PRRT_xxx
```

Leave declined threads open. Reply with the reasoning and let the reviewer
respond — that is what the open state is for.

## 6. Clear the watchlist

Once the PR's comments are handled, drop it from the session-start watchlist so
it stops being reported:

```bash
python3 ~/.claude/hooks/pr-watch-report.py --drop-pr 107
```

The entry also clears itself when the PR merges or closes, and when every
thread on it is resolved. Skip this step if threads remain deliberately open —
the reminder is then doing its job.
