#!/usr/bin/env bash
# PostToolUse(Bash) hook: after a git push / gh pr create that actually landed,
# record repo+branch+sha in the PR watchlist. Does no network I/O — the
# SessionStart reporter resolves branch -> PR and fetches threads later.
#
# Reads the hook payload on stdin. Silent and idempotent.
set -uo pipefail

WATCHLIST="${PR_WATCHLIST:-$HOME/.claude/pr-watchlist.json}"

payload=$(cat)

# Cheap pre-filter: no subprocess unless the raw payload mentions a push.
case "$payload" in
  *push*|*'gh pr create'*) ;;
  *) exit 0 ;;
esac

command -v jq >/dev/null 2>&1 || exit 0
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null) || exit 0

# Confirm the push is in the command itself, not merely in the tool output.
# Allows options between the subcommand and the verb (git -C <dir> push).
PUSH_RE='(^|[[:space:];&|(])(git([[:space:]]+(-C[[:space:]]+[^[:space:];&|]+|--?[^[:space:];&|]+))*[[:space:]]+push|gh[[:space:]]+pr[[:space:]]+create)([[:space:]]|[;&|)]|$)'
printf ' %s ' "$cmd" | grep -qE "$PUSH_RE" || exit 0

# Where did the push happen? The payload cwd is the *session* directory, which
# is not necessarily the repo — "cd ~/repo && git push" and "git -C ~/repo push"
# both push somewhere else. Try the command's own directory hints first.
unquote() {
  local v="${1%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  case "$v" in "~"|"~/"*) v="$HOME${v#\~}" ;; esac
  printf '%s' "$v"
}

session_cwd=$(printf '%s' "$payload" | jq -r '.cwd // ""' 2>/dev/null)
[ -n "$session_cwd" ] && [ -d "$session_cwd" ] || session_cwd="$PWD"

padded=$(printf ' %s' "$cmd")
dash_c=$(printf '%s' "$padded" \
  | sed -nE 's/.*[[:space:];&|(]git[[:space:]]+-C[[:space:]]+([^[:space:];&|)]+).*/\1/p')
cd_arg=$(printf '%s' "$padded" \
  | sed -nE 's/.*[[:space:];&|(]cd[[:space:]]+([^[:space:];&|)]+).*/\1/p')

repo_dir=""
for candidate in "$(unquote "$dash_c")" "$(unquote "$cd_arg")" "$session_cwd"; do
  [ -n "$candidate" ] || continue
  case "$candidate" in /*) ;; *) candidate="$session_cwd/$candidate" ;; esac
  [ -d "$candidate" ] || continue
  if git -C "$candidate" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    repo_dir="$candidate"
    break
  fi
done
[ -n "$repo_dir" ] || exit 0

cd "$repo_dir" 2>/dev/null || exit 0

# Push verification: after a successful push the upstream ref matches HEAD.
# On a rejected push they diverge, so a failed push never registers.
head_sha=$(git rev-parse --verify HEAD 2>/dev/null) || exit 0
up_sha=$(git rev-parse --verify '@{u}' 2>/dev/null) || exit 0
[ "$head_sha" = "$up_sha" ] || exit 0

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
[ "$branch" != "HEAD" ] || exit 0

# Never watch a push straight to a trunk branch.
case "$branch" in main|master|develop|trunk) exit 0 ;; esac

origin=$(git remote get-url origin 2>/dev/null) || exit 0
# git@host:owner/repo.git | https://host/owner/repo.git | ssh://git@host/owner/repo
slug=$(printf '%s' "$origin" \
  | sed -E -e 's#^[a-z+]+://[^/]+/##' -e 's#^[^@]*@[^:]+:##' -e 's#\.git$##' -e 's#^/+##')
case "$slug" in */*) ;; *) exit 0 ;; esac
# Reject anything that still looks like a URL or has extra path depth.
[ "$(printf '%s' "$slug" | tr -cd '/' | wc -c | tr -d ' ')" = "1" ] || exit 0

key="$slug#$branch"
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
toplevel=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$repo_dir")

mkdir -p "$(dirname "$WATCHLIST")"
[ -f "$WATCHLIST" ] || printf '{}\n' > "$WATCHLIST"

tmp=$(mktemp "${WATCHLIST}.XXXXXX") || exit 0
if jq --arg key "$key" --arg repo "$slug" --arg branch "$branch" \
      --arg sha "$head_sha" --arg now "$now" --arg dir "$toplevel" \
   '(. // {}) | .[$key] = ((.[$key] // {}) + {
        repo: $repo, branch: $branch, pushed_sha: $sha,
        pushed_at: $now, dir: $dir,
        first_seen: ((.[$key].first_seen) // $now)
      })' "$WATCHLIST" > "$tmp" 2>/dev/null; then
  mv -f "$tmp" "$WATCHLIST"
else
  rm -f "$tmp"
fi
exit 0
