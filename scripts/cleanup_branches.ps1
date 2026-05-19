git checkout main
git pull origin main
git fetch --prune

$p = git for-each-ref --format='%(refname:short)' refs/heads
$branches = $p -split "`n"
foreach ($b in $branches) {
    $bn = $b.Trim()
    if ($bn -and $bn -ne 'main') {
        Write-Host "Deleting local branch: $bn"
        git branch -D $bn
    }
}

$p2 = git for-each-ref --format='%(refname:short)' refs/remotes/origin
$rbranches = $p2 -split "`n"
foreach ($rb in $rbranches) {
    $r = $rb.Trim()
    if ($r -and $r -ne 'origin/main' -and $r -ne 'origin/HEAD') {
        $name = $r -replace '^origin/',''
        Write-Host "Deleting remote branch: $name"
        git push origin --delete $name
    }
}

Write-Host "Branch cleanup complete"
