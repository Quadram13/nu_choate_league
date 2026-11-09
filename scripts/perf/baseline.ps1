# Page-latency harness. Round-robin rounds, warmup discarded from the
# median, CSV of every hit, median and min-max range per page, error count.
# Median is the middle sorted sample (lower middle when the count is even),
# matching the CoS baseline. Default pages are the hub set from that baseline.
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
    $raw = & curl.exe -s -o NUL -w "%{http_code} %{time_total}" --max-time 120 $Url
    if ($LASTEXITCODE -ne 0) {
        return @{ code = "curl$LASTEXITCODE"; seconds = 0.0 }
    }
    $parts = "$raw".Trim() -split "\s+"
    $seconds = 0.0
    if ($parts.Length -ge 2) {
        $seconds = [double]$parts[1]
    }
    return @{ code = $parts[0]; seconds = $seconds }
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
        })
    }
}

$rows | Export-Csv -NoTypeInformation -Encoding utf8 -Path $OutCsv
$sample = @($rows | Where-Object { $_.phase -eq "sample" })
$summary = $sample | Group-Object page | ForEach-Object {
    $sorted = @($_.Group.seconds | Sort-Object)
    $mid = [int](($sorted.Count - 1) / 2)
    [PSCustomObject]@{
        page = $_.Name
        n = $sorted.Count
        median = [math]::Round($sorted[$mid], 3)
        min = [math]::Round($sorted[0], 3)
        max = [math]::Round($sorted[-1], 3)
        errors = @($_.Group | Where-Object { $_.code -ne "200" }).Count
    }
}
$summary | Sort-Object median -Descending | Format-Table -AutoSize
$sampleErrors = @($sample | Where-Object { $_.code -ne "200" }).Count
Write-Output "csv=$OutCsv warmup_errors=$warmupErrors sample_errors=$sampleErrors rounds=$Rounds warmup=$Warmup"
if ($sampleErrors -gt 0) {
    exit 1
}
