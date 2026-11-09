# Alternating page timings. Each cycle installs plain views (A), hits every
# page once, installs the shipped snapshots (B), hits every page once.
# Claim, printed before the first timed request: the four hub pages move by
# the fa-chain share of the request. Median of the cycles, min-max range.
# A gap inside a side's range is no measurable difference. Machine noise is
# interleaved because A and B share each cycle.
param(
    [string]$BaseUrl = "http://127.0.0.1:8112",
    [string[]]$Pages = @("/players", "/records", "/seasons/2025", "/"),
    [int]$Cycles = 5,
    [string]$PlainSql = "",
    [string]$MatSql = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent (Split-Path -Parent $here)
if (-not $PlainSql) { $PlainSql = Join-Path $here "fa_chain_plain.sql" }
if (-not $MatSql) { $MatSql = Join-Path $repo "sql\analysis\62_fa_weeks.sql" }
$MatSql = (Resolve-Path -LiteralPath $MatSql).Path
$PlainSql = (Resolve-Path -LiteralPath $PlainSql).Path
if (-not $OutDir) { $OutDir = Join-Path $env:TEMP "perf\ab" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Output "CLAIM before run: /players, /records, /seasons/2025, and / get faster by the fa-chain share once v_fa_weeks (and any still-slow season/career view) is a snapshot. Median of $Cycles alternating cycles per side. Noise floor is the per-side range. This host has 6 cores; background CPU before the session was about 10-29 percent."
Write-Output "plain=$PlainSql"
Write-Output "mat=$MatSql"
Write-Output "out=$OutDir"
$apply = Join-Path $here "apply-fa.ps1"

function Invoke-MeasuredPage([string]$Url, [string]$BodyPath) {
    $raw = & curl.exe -s -o $BodyPath -w "%{http_code} %{time_total}" --max-time 180 $Url
    if ($LASTEXITCODE -ne 0) {
        return @{ code = "curl$LASTEXITCODE"; seconds = 0.0; sha = "" }
    }
    $parts = "$raw".Trim() -split "\s+"
    $seconds = 0.0
    if ($parts.Length -ge 2) { $seconds = [double]$parts[1] }
    $sha = ""
    if (Test-Path -LiteralPath $BodyPath) {
        $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $BodyPath).Hash
    }
    return @{ code = $parts[0]; seconds = $seconds; sha = $sha }
}

function Measure-Side([string]$Side, [int]$Cycle) {
    $hits = @()
    foreach ($page in $Pages) {
        $slug = ($page.Trim("/")) -replace "[^a-zA-Z0-9]+", "_"
        if (-not $slug) { $slug = "home" }
        $body = Join-Path $OutDir ("c{0}-{1}-{2}.html" -f $Cycle, $Side, $slug)
        $hit = Invoke-MeasuredPage ($BaseUrl.TrimEnd("/") + $page) $body
        $row = [PSCustomObject]@{
            cycle = $Cycle
            side = $Side
            page = $page
            code = $hit.code
            seconds = $hit.seconds
            sha256 = $hit.sha
        }
        $script:rows.Add($row)
        $hits += $row
        Write-Output ("cycle={0} side={1} page={2} code={3} seconds={4:N3} sha={5}" -f $Cycle, $Side, $page, $hit.code, $hit.seconds, $hit.sha)
    }
    return $hits
}

$rows = New-Object System.Collections.Generic.List[object]
for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    Write-Output "=== cycle $cycle side A (plain views) ==="
    & $apply -SqlPath $PlainSql | Out-Null
    Measure-Side "A" $cycle | Out-Null
    Write-Output "=== cycle $cycle side B (shipped sql) ==="
    & $apply -SqlPath $MatSql | Out-Null
    Measure-Side "B" $cycle | Out-Null
}

$csv = Join-Path $OutDir "ab.csv"
$rows | Export-Csv -NoTypeInformation -Encoding utf8 -Path $csv
Write-Output "=== summary ==="
$summary = $rows | Group-Object side, page | ForEach-Object {
    $sorted = @($_.Group.seconds | Sort-Object)
    $mid = [int](($sorted.Count - 1) / 2)
    $hashes = @($_.Group.sha256 | Select-Object -Unique)
    [PSCustomObject]@{
        side = $_.Group[0].side
        page = $_.Group[0].page
        n = $sorted.Count
        median = [math]::Round($sorted[$mid], 3)
        min = [math]::Round($sorted[0], 3)
        max = [math]::Round($sorted[-1], 3)
        errors = @($_.Group | Where-Object { $_.code -ne "200" }).Count
        distinct_sha = $hashes.Count
    }
}
$summary | Sort-Object page, side | Format-Table -AutoSize
$errors = @($rows | Where-Object { $_.code -ne "200" }).Count
Write-Output "csv=$csv errors=$errors cycles=$Cycles"
if ($errors -gt 0) { exit 1 }
