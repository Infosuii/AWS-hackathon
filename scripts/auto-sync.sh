#!/bin/bash
# Auto-commit and push all workspace changes to GitHub (macOS/Linux port of auto-sync.ps1).
# Run every 5 minutes by launchd (~/Library/LaunchAgents/com.abhit7.aws-hackathon.autosync.plist).
# Safe to run manually too. Never forces; on conflicts it stops and logs.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

repo="$(cd "$(dirname "$0")/.." && pwd)"
log="$repo/.git-autosync.log"
log_msg() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$log"; }

cd "$repo" || exit 0

# Another git process (or a parallel sync) is running - skip, the next run will catch up.
if [ -e .git/index.lock ] || [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  log_msg "skip: git busy (index.lock or rebase in progress)"
  exit 0
fi

git add -A >/dev/null 2>&1
if ! git diff --cached --quiet; then
  files="$(git diff --cached --name-only | head -3 | paste -sd ',' - | sed 's/,/, /g')"
  if ! git commit -q -m "auto-sync: $(date '+%Y-%m-%d %H:%M:%S') $files" >/dev/null 2>&1; then
    log_msg "commit failed"
    exit 0
  fi
fi

branch="$(git rev-parse --abbrev-ref HEAD)"

# Pick up commits made elsewhere (teammates, GitHub web UI) before pushing.
if git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
  if ! git pull --rebase --autostash -q origin "$branch" >/dev/null 2>&1; then
    git rebase --abort >/dev/null 2>&1
    log_msg "pull --rebase failed (conflict?) - resolve manually, then run scripts/auto-sync.sh"
    exit 0
  fi
fi

# Nothing to push? done.
ahead="$(git rev-list --count "origin/$branch..HEAD" 2>/dev/null)"
[ "$ahead" = "0" ] && exit 0

if out="$(git push -q -u origin "$branch" 2>&1)"; then
  log_msg "synced $branch"
else
  log_msg "push failed: $out"
fi
exit 0
