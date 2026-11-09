# Alternating /players timings. Side A installs the snapshot SELECT text as
# plain views. Side B installs the shipped materialized views and refreshes
# them before the hit. The page query names do not change.
# Median of the cycles, min-max range, body hash.
param(
    [string]$BaseUrl = "http://127.0.0.1:8113",
    [int]$Cycles = 5,
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent (Split-Path -Parent $here)
$matPath = Join-Path $repo "sql\analysis\99_players_index_snapshot.sql"
$matSql = Get-Content -LiteralPath $matPath -Raw
$plainSql = $matSql.Replace("CREATE MATERIALIZED VIEW", "CREATE VIEW").Replace("COMMENT ON MATERIALIZED VIEW", "COMMENT ON VIEW").Replace("WITH NO DATA;", ";")
if ($plainSql.Contains("CREATE MATERIALIZED VIEW") -or $plainSql.Contains("COMMENT ON MATERIALIZED VIEW") -or $plainSql.Contains("WITH NO DATA;")) {
    throw "plain transform left a snapshot clause in place"
}
$plainPath = Join-Path $env:TEMP "perf-p1\players_index_plain.sql"
Set-Content -LiteralPath $plainPath -Value $plainSql -Encoding utf8
if (-not $OutDir) { $OutDir = Join-Path $env:TEMP "perf-p1\ab" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$apply = Join-Path $here "apply-players.ps1"

Write-Output "CLAIM before run: /players gets faster by the five statements that recompute v_player_index, v_player_season, the volatility windows, and the v_vorp_season gap, once those reads are snapshots. Median of $Cycles alternating cycles. Noise floor is the per-side range. Jinja still renders the page, so the median should not fall to half. Host has 6 cores."
Write-Output "mat=$matPath"
Write-Output "plain=$plainPath"
Write-Output "out=$OutDir"

function Invoke-MeasuredPage([string]$Url, [string]$BodyPath) {
    $raw = & curl.exe -s -o $BodyPath -w "%{http_code} %{time_total} %{size_download}" --max-time 180 $Url
    if ($LASTEXITCODE -ne 0) {
        return @{ code = "curl$LASTEXITCODE"; seconds = 0.0; sha = ""; bytes = 0 }
    }
    $parts = "$raw".Trim() -split "\s+"
    $seconds = 0.0
    $bytes = 0
    if ($parts.Length -ge 2) { $seconds = [double]$parts[1] }
    if ($parts.Length -ge 3) { $bytes = [int]$parts[2] }
    $sha = ""
    if (Test-Path -LiteralPath $BodyPath) {
        $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $BodyPath).Hash
    }
    return @{ code = $parts[0]; seconds = $seconds; sha = $sha; bytes = $bytes }
}

$rows = New-Object System.Collections.Generic.List[object]
Write-Output "=== warmup A ==="
& $apply -SqlPath $plainPath | Out-Null
Invoke-MeasuredPage ($BaseUrl.TrimEnd("/") + "/players") (Join-Path $OutDir "warmup-a.html") | Out-Null
Write-Output "=== warmup B ==="
& $apply -SqlPath $matPath | Out-Null
Invoke-MeasuredPage ($BaseUrl.TrimEnd("/") + "/players") (Join-Path $OutDir "warmup-b.html") | Out-Null

for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    Write-Output "=== cycle $cycle side A (plain views) ==="
    & $apply -SqlPath $plainPath | Out-Null
    $bodyA = Join-Path $OutDir ("c{0}-A.html" -f $cycle)
    $hitA = Invoke-MeasuredPage ($BaseUrl.TrimEnd("/") + "/players") $bodyA
    $rows.Add([PSCustomObject]@{
        cycle = $cycle; side = "A"; code = $hitA.code; seconds = $hitA.seconds; sha256 = $hitA.sha; bytes = $hitA.bytes
    })
    Write-Output ("cycle={0} side=A code={1} seconds={2:N3} bytes={3} sha={4}" -f $cycle, $hitA.code, $hitA.seconds, $hitA.bytes, $hitA.sha)

    Write-Output "=== cycle $cycle side B (snapshots) ==="
    & $apply -SqlPath $matPath | Out-Null
    $bodyB = Join-Path $OutDir ("c{0}-B.html" -f $cycle)
    $hitB = Invoke-MeasuredPage ($BaseUrl.TrimEnd("/") + "/players") $bodyB
    $rows.Add([PSCustomObject]@{
        cycle = $cycle; side = "B"; code = $hitB.code; seconds = $hitB.seconds; sha256 = $hitB.sha; bytes = $hitB.bytes
    })
    Write-Output ("cycle={0} side=B code={1} seconds={2:N3} bytes={3} sha={4}" -f $cycle, $hitB.code, $hitB.seconds, $hitB.bytes, $hitB.sha)
}

$csv = Join-Path $OutDir "ab.csv"
$rows | Export-Csv -NoTypeInformation -Encoding utf8 -Path $csv
Write-Output "=== summary ==="
$rows | Group-Object side | ForEach-Object {
    $sorted = @($_.Group.seconds | Sort-Object)
    $mid = [int](($sorted.Count - 1) / 2)
    $hashes = @($_.Group.sha256 | Select-Object -Unique)
    [PSCustomObject]@{
        side = $_.Name
        n = $sorted.Count
        median = [math]::Round($sorted[$mid], 3)
        min = [math]::Round($sorted[0], 3)
        max = [math]::Round($sorted[-1], 3)
        errors = @($_.Group | Where-Object { $_.code -ne "200" }).Count
        distinct_sha = $hashes.Count
        sha = $hashes -join ","
    }
} | Format-List
$allSha = @($rows.sha256 | Select-Object -Unique)
Write-Output ("cross_side_distinct_sha={0}" -f $allSha.Count)
$errors = @($rows | Where-Object { $_.code -ne "200" }).Count
Write-Output "csv=$csv errors=$errors cycles=$Cycles"
if ($errors -gt 0 -or $allSha.Count -ne 1) { exit 1 }
