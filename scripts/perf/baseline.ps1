# Page-latency harness. Round-robin rounds, warmup discarded from the
# median, CSV of every hit, median and min-max range per page, error count.
# Median is the middle sorted sample (lower middle when the count is even),
# matching the CoS baseline. Default pages are the hub set from that baseline.
# Each hit also records size_download. A sample page whose median is over
# 1 second or 1000000 bytes fails unless scripts/perf/named-limiters.tsv
# names that page and a measured reason.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string[]]$Pages = @(
        "/",
        "/players",
        "/boards/players-career-rankings",
        "/boards/players-season-rankings",
        "/boards/players-wire-season",
        "/boards/players-wire-career",
        "/boards/players-wire-unowned",
        "/boards/players-counting-career",
        "/boards/players-counting-season",
        "/players/4046",
        "/players/6945",
        "/members",
        "/members/marcus-du",
        "/seasons/2025",
        "/seasons/2025/scoring",
        "/records",
        "/versus"
    ),
    [int]$Rounds = 7,
    [int]$Warmup = 1,
    [string]$OutCsv = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutCsv) {
    $dir = Join-Path $env:TEMP "perf"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $OutCsv = Join-Path $dir "baseline.csv"
}

function Invoke-Page([string]$Url) {
    $discard = if ($IsWindows) { "NUL" } else { "/dev/null" }
    $raw = & curl.exe -s -o $discard -w "%{http_code} %{time_total} %{size_download}" --max-time 120 $Url
    if ($LASTEXITCODE -ne 0) {
        return @{ code = "curl$LASTEXITCODE"; seconds = 0.0; bytes = 0 }
    }
    $parts = "$raw".Trim() -split "\s+"
    $seconds = 0.0
    $bytes = 0
    if ($parts.Length -ge 2) {
        $seconds = [double]$parts[1]
    }
    if ($parts.Length -ge 3) {
        $bytes = [int64]$parts[2]
    }
    return @{ code = $parts[0]; seconds = $seconds; bytes = $bytes }
}

$rows = New-Object System.Collections.Generic.List[object]
$warmupErrors = 0
for ($w = 1; $w -le $Warmup; $w++) {
    foreach ($page in $Pages) {
        $hit = Invoke-Page ($BaseUrl.TrimEnd("/") + $page)
        $rows.Add([PSCustomObject]@{
            phase = "warmup"
            round = $w
            page = $page
            code = $hit.code
            seconds = $hit.seconds
            bytes = $hit.bytes
        })
        if ($hit.code -ne "200") {
            $warmupErrors++
            Write-Output "WARMUP ERROR $page -> $($hit.code)"
        }
    }
}

for ($round = 1; $round -le $Rounds; $round++) {
    foreach ($page in $Pages) {
        $hit = Invoke-Page ($BaseUrl.TrimEnd("/") + $page)
        $rows.Add([PSCustomObject]@{
            phase = "sample"
            round = $round
            page = $page
            code = $hit.code
            seconds = $hit.seconds
            bytes = $hit.bytes
        })
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding utf8 -Path $OutCsv
$sample = @($rows | Where-Object { $_.phase -eq "sample" })
$limiters = @{}
$limiterPath = Join-Path $PSScriptRoot "named-limiters.tsv"
if (Test-Path $limiterPath) {
    Get-Content $limiterPath | ForEach-Object {
        $line = "$_".Trim()
        if (-not $line -or $line.StartsWith("#") -or $line.StartsWith("page")) {
            return
        }
        $bits = $line -split "`t", 2
        if ($bits.Length -eq 2 -and $bits[1].Trim()) {
            $limiters[$bits[0].Trim()] = $bits[1].Trim()
        }
    }
}
$summary = $sample | Group-Object page | ForEach-Object {
    $sorted = @($_.Group.seconds | Sort-Object)
    $sizes = @($_.Group.bytes | Sort-Object)
    $mid = [int](($sorted.Count - 1) / 2)
    [PSCustomObject]@{
        page = $_.Name
        n = $sorted.Count
        median = [math]::Round($sorted[$mid], 3)
        min = [math]::Round($sorted[0], 3)
        max = [math]::Round($sorted[-1], 3)
        median_bytes = [int64]$sizes[$mid]
        min_bytes = [int64]$sizes[0]
        max_bytes = [int64]$sizes[-1]
        errors = @($_.Group | Where-Object { $_.code -ne "200" }).Count
    }
}
$summary | Sort-Object median -Descending | Format-Table -AutoSize
$sampleErrors = @($sample | Where-Object { $_.code -ne "200" }).Count
$budgetErrors = 0
foreach ($row in $summary) {
    $over = ($row.median -gt 1.0) -or ($row.median_bytes -gt 1000000)
    if (-not $over) {
        continue
    }
    if ($limiters.ContainsKey($row.page)) {
        Write-Output "NAMED LIMITER $($row.page) $($row.median)s $($row.median_bytes)B :: $($limiters[$row.page])"
    } else {
        $budgetErrors++
        Write-Output "BUDGET $($row.page) median=$($row.median)s bytes=$($row.median_bytes) (cap 1s and 1000000B)"
    }
}
Write-Output "csv=$OutCsv warmup_errors=$warmupErrors sample_errors=$sampleErrors budget_errors=$budgetErrors rounds=$Rounds warmup=$Warmup"
if ($sampleErrors -gt 0 -or $budgetErrors -gt 0) {
    exit 1
}
