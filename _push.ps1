$git = "C:\Program Files\Git\bin\git.exe"
$env:GIT_AUTHOR_NAME = "Ben Petrihos"
$env:GIT_AUTHOR_EMAIL = "blpetrihos-hub@users.noreply.github.com"
$env:GIT_COMMITTER_NAME = "Ben Petrihos"
$env:GIT_COMMITTER_EMAIL = "blpetrihos-hub@users.noreply.github.com"

& $git add -A
$tree = (& $git write-tree).Trim()
$parent = (& $git rev-parse HEAD).Trim()
$msg = @"
Refresh report UI and fix foot-store shoe matching

Dark-mode HTML report with logo, top-15 deals table only, and improved
Wave Rider/Inspire matching with out-of-stock notes.
"@
$commit = (& $git commit-tree $tree -p $parent -m $msg).Trim()
& $git reset --hard $commit
& $git log -1 --format=%B
& $git push origin main
