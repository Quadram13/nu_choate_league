# Repeat the fa leader statements round-robin and print each Time line.
# One sample is a ballpark. The season/career materialize decision wants
# the median of these runs. Optional -Refresh times REFRESH instead.
param(
    [int]$Runs = 5,
    [string[]]$Names = @("weeks", "season", "career"),
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"
$queries = @{
    weeks = @"
SELECT year, week, player_id, player_name, position, points, vorp
FROM v_fa_weeks
ORDER BY points DESC, vorp DESC, year, week, player_name
LIMIT 10;
"@
    season = @"
SELECT year, player_id, player_name, fa_vorp
FROM v_fa_season
ORDER BY fa_vorp DESC
LIMIT 10;
"@
    career = @"
SELECT player_id, player_name, fa_vorp
FROM v_fa_career
ORDER BY fa_vorp DESC
LIMIT 10;
"@
}
$refreshSql = @{
    weeks = "REFRESH MATERIALIZED VIEW v_fa_weeks;"
    season = "REFRESH MATERIALIZED VIEW v_fa_season;"
    career = "REFRESH MATERIALIZED VIEW v_fa_career;"
}

$samples = New-Object System.Collections.Generic.List[object]
for ($run = 1; $run -le $Runs; $run++) {
    foreach ($name in $Names) {
        $body = if ($Refresh) { $refreshSql[$name] } else { $queries[$name] }
        if (-not $body) { throw "no statement for $name" }
        $sql = "\timing on`n" + $body
        $output = $sql | & docker exec -i nu-choate-postgres psql -U nu_choate -d nu_choate -v ON_ERROR_STOP=1
        if ($LASTEXITCODE -ne 0) {
            Write-Output $output
            throw "psql failed on $name run $run"
        }
        $line = @($output | Select-String -Pattern "Time:\s+[0-9.]+ ms" | Select-Object -Last 1)
        if (-not $line -or $line[0].Line -notmatch "Time:\s+([0-9.]+)\s+ms") {
            Write-Output $output
            throw "no timing line for $name run $run"
        }
        $ms = [double]$Matches[1]
        $samples.Add([PSCustomObject]@{ run = $run; name = $name; ms = $ms })
        Write-Output ("{0} run={1} ms={2}" -f $name, $run, $ms)
    }
}

$samples | Group-Object name | ForEach-Object {
    $sorted = @($_.Group.ms | Sort-Object)
    $mid = [int](($sorted.Count - 1) / 2)
    [PSCustomObject]@{
        name = $_.Name
        n = $sorted.Count
        median_ms = [math]::Round($sorted[$mid], 1)
        min_ms = [math]::Round($sorted[0], 1)
        max_ms = [math]::Round($sorted[-1], 1)
    }
} | Format-Table -AutoSize
