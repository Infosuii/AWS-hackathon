# Auto-commit and push all workspace changes to GitHub.
# Invoked by Kiro hooks (.kiro/hooks/auto-sync-*.json). Safe to run manually too.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $repo '.git-autosync.log'

function Write-Log($msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Out-File -FilePath $log -Append -Encoding utf8
}

try {
    Set-Location $repo

    # Another git process (or a parallel sync) is running - skip this round, the next trigger will catch up.
    if (Test-Path (Join-Path $repo '.git\index.lock')) { Write-Log 'skip: index.lock present'; exit 0 }

    git add -A 2>&1 | Out-Null
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        $files = (git diff --cached --name-only | Select-Object -First 3) -join ', '
        git commit -q -m "auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $files" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Log 'commit failed'; exit 0 }
    }

    # Nothing to push? done.
    $branch = git rev-parse --abbrev-ref HEAD
    $ahead  = git rev-list --count "origin/$branch..HEAD" 2>$null
    if ($LASTEXITCODE -eq 0 -and $ahead -eq '0') { exit 0 }

    # Pick up commits made from elsewhere (teammates, GitHub web UI) before pushing.
    # (Skipped on the very first push, when the remote branch doesn't exist yet.)
    git ls-remote --exit-code --heads origin $branch 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        git pull --rebase --autostash -q origin $branch 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            git rebase --abort 2>&1 | Out-Null
            Write-Log 'pull --rebase failed (conflict?) - resolve manually, then run scripts/auto-sync.ps1'
            exit 0
        }
    }

    $out = git push -q -u origin $branch 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Log "push failed: $out"; exit 0 }
    Write-Log "synced $branch"
}
catch {
    Write-Log "error: $_"
    exit 0   # never block Kiro on a sync failure
}
