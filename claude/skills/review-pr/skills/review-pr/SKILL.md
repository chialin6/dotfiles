---
name: review-pr
description: Review a pull request as a code reviewer — fetch context and diff, run parallel specialist review across correctness, security, performance, tests, and quality, synthesize findings, post comments, and approve or request changes. Works with GitHub or Azure DevOps.
tags:
  Function: [Engineering]
---

# Pull Request Review

**Input:** PR number + platform
**Output:** Synthesized review posted as PR comments, with approval or change request

Provide: PR number and platform (GitHub or Azure DevOps).
Also specify ticketing system if work items should be fetched (Linear, Jira, ADO Boards, or none).

🔴 I will not proceed until the platform is confirmed.

---

## Step 1: Fetch PR Context (Parallel)

**GitHub:**
```bash
PR_NUMBER=<number>
gh pr view $PR_NUMBER --json title,author,createdAt,state,baseRefName,headRefName,body,labels,reviewDecision
gh pr view $PR_NUMBER --json closingIssuesReferences --jq '.closingIssuesReferences[] | "Issue #\(.number): \(.title)"'
gh pr diff $PR_NUMBER
```

**Azure DevOps:**
```bash
PR_ID=<id>
az repos pr show --id $PR_ID --query "{title: title, author: createdBy.displayName, source: sourceRefName, target: targetRefName, work_items: workItemRefs[].id}" -o yaml
git fetch --all && git diff origin/<target>...origin/<source>
```

If a Jira key appears in the PR title/body (e.g. `PROJ-1234`): `jira issue view PROJ-1234` or Jira REST API.
If a Linear identifier appears: fetch via Linear GraphQL or `linear issue view ENG-123`.

Also read documentation relevant to the changed files, and read surrounding code for patterns and conventions.

---

## Step 2: Parallel Specialist Review

Launch all sub agents simultaneously. Every finding must be **verified against actual code** — re-read 50+ lines of surrounding context, trace the code path, confirm the issue is real before reporting. Do not report speculative findings.

**Sub Agent A — Correctness & Acceptance Criteria**
- Do changes correctly implement the requirements?
- All acceptance criteria met?
- Logic errors, incorrect assumptions, missing edge cases?
- Error conditions handled appropriately?

**Sub Agent B — Security**
- Injection risks (SQL, command, XSS)?
- Auth/authorization bypasses introduced?
- Insecure defaults or configurations?
- Secrets or credentials accidentally committed?
- Input validation and output encoding in place?

**Sub Agent C — Performance & Scalability**
- N+1 queries, unbounded loops, or unnecessary DB calls?
- Memory leaks or resource management issues?
- Caching opportunities missed, or cache invalidation problems?
- Will this scale under load?

**Sub Agent D — Test Coverage**
- New/modified code paths covered by tests?
- Edge cases and error paths tested?
- Tests meaningful — not just coverage theater?
- All tests pass?

**Sub Agent E — Code Quality & Maintainability**
- Follows existing patterns and conventions?
- Unnecessary complexity?
- Naming clarity, function length, separation of concerns?
- Any new code duplicating functionality already in the project or available from an existing dependency? Flag where an existing utility or abstraction could have been used.

---

## Step 3: Synthesize

```
## PR Review: [PR title]

### What this PR does
[2-3 sentence summary of changes and problem solved]

### Acceptance criteria: ✅ / ⚠️ / ❌
[Each criterion and its status]

### Issues found
**Must fix (blocking):**
- [File:line] description

**Should fix (non-blocking):**
- [File:line] description

**Consider (suggestions):**
- [File:line] suggestion

### Looks good
- [Areas that are well done]
```

Present to developer. They can filter, focus, or override before anything is posted:
> "Focus on the auth layer" / "Ignore performance suggestions — low-traffic path" / "Post the caching issue but skip the naming ones"

---

## Step 4: Post Comments

**GitHub — general comment:**
```bash
gh pr comment $PR_NUMBER --body "<markdown>"
```

**GitHub — inline file/line comment:**
```bash
gh api repos/{owner}/{repo}/pulls/$PR_NUMBER/comments \
  -f body="<markdown>" \
  -f commit_id="$(gh pr view $PR_NUMBER --json headRefOid --jq '.headRefOid')" \
  -f path="<file_path>" \
  -F line=<line_number> \
  -f side="RIGHT"
```

**Azure DevOps — new thread:**
Use `az devops invoke --area git --resource pullRequestThreads` with POST.

**Azure DevOps — reply to existing thread:**
Use `az devops invoke --area git --resource pullRequestThreadComments` with POST (not `pullRequestThreads` — that creates new threads).

Use `PROJECT_ID` (GUID) not project name in ADO route parameters — get it from Step 1 output.

---

## Step 5: Approve or Request Changes

Confirm decision with developer, then:

**GitHub:**
```bash
gh pr review $PR_NUMBER --approve --body "Looks good!"
gh pr review $PR_NUMBER --request-changes --body "<feedback>"
gh pr review $PR_NUMBER --comment --body "<feedback>"   # comment only
```

**Azure DevOps:**
```bash
az repos pr set-vote --id $PR_ID --vote approve
# Other options: approve-with-suggestions | wait-for-author | reject
```

---

## Reflect & Learn

After the review:
1. Note any corrections or pushback from the developer ("that's not actually a bug", "we intentionally don't test that path")
2. If patterns appear: "My review flagged these as issues but they were dismissed: [X, Y, Z]"
3. Ask: "Would you like to record any of these as team-specific review preferences for future reviews?"
