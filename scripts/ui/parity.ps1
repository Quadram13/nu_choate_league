# Route parity harness for the UI/IA wave (#45 board).
# Capture mode saves each route's body + manifest (status, bytes, sha256).
# Check mode re-fetches and diffs against a captured manifest.
# Usage:
#   scripts/ui/parity.ps1 -Mode capture -BaseUrl http://localhost:8100 -OutDir <dir>
#   scripts/ui/parity.ps1 -Mode check   -BaseUrl http://localhost:8100 -CheckDir <dir>
param(
    [Parameter(Mandatory)][ValidateSet('capture','check')][string]$Mode,
    [string]$BaseUrl = 'http://localhost:8100',
    [string]$OutDir,
    [string]$CheckDir
)

$ProgressPreference = 'SilentlyContinue'

$routes = @(
    '/',
    '/seasons',
    '/seasons/2025',
    '/seasons/2025/trades/1269432330255081472',
    '/seasons/2025/moves',
    '/seasons/2025/draft',
    '/seasons/2025/wire/1266620574830952448',
    '/seasons/2025/week/1',
    '/seasons/2025/week/1/2025-w01-1',
    '/seasons/2025/marks',
    '/seasons/2025/desk',
    '/seasons/2025/scoring',
    '/versus',
    '/versus/alex-coletti/andrew-howey',
    '/members',
    '/members/alex-coletti',
    '/records',
    '/luck',
    '/players',
    '/players/4046'
)

function Get-Route([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 120 -ErrorAction SilentlyContinue
    } catch {
        $r = $_.Exception.Response
    }
    $status = 0; $bytes = 0; $sha = ''; $location = ''
    if ($r -and $r.StatusCode) { $status = [int]$r.StatusCode }
    if ($r -and $r.Headers) { $location = [string]$r.Headers['Location'] }
    $text = ''
    if ($r -and $status -eq 200) {
        $text = [string]$r.Content
        $raw = [System.Text.Encoding]::UTF8.GetBytes($text)
        $bytes = $raw.Length
        $sha = (Get-FileHash -InputStream ([System.IO.MemoryStream]::new($raw)) -Algorithm SHA256).Hash
        if (-not $sha) { throw "hash failed for route" }
    }
    [pscustomobject]@{ status = $status; bytes = $bytes; sha256 = $sha; location = $location; body = $text }
}

if ($Mode -eq 'capture') {
    if (-not $OutDir) { throw '-OutDir required for capture' }
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $rows = @()
    $i = 0
    foreach ($route in $routes) {
        $i++
        $res = Get-Route "$BaseUrl$route"
        $file = "r$($i.ToString('00')).html"
        if ($res.body) { [System.IO.File]::WriteAllText((Join-Path $OutDir $file), $res.body) }
        $rows += "$route`t$($res.status)`t$($res.bytes)`t$($res.sha256)`t$($res.location)`t$file"
        Write-Output ("{0,-48} {1} {2,10} {3}" -f $route, $res.status, $res.bytes, $res.sha256.Substring(0, [Math]::Min(12, $res.sha256.Length)))
    }
    [System.IO.File]::WriteAllLines((Join-Path $OutDir 'manifest.tsv'), ([string[]]@("route`tstatus`tbytes`tsha256`tlocation`tfile") + $rows))
    Write-Output "captured $($routes.Count) routes -> $OutDir"
} else {
    if (-not $CheckDir) { throw '-CheckDir required for check' }
    $manifest = Get-Content (Join-Path $CheckDir 'manifest.tsv') | Select-Object -Skip 1
    $fails = 0
    foreach ($line in $manifest) {
        $route, $expStatus, $expBytes, $expSha, $expLoc, $file = $line -split "`t"
        $res = Get-Route "$BaseUrl$route"
        $ok = ($res.status -eq [int]$expStatus) -and ($res.sha256 -eq $expSha) -and ($res.location -eq $expLoc)
        if (-not $ok) { $fails++ }
        Write-Output ("{0,-48} {1} status {2}->{3} bytes {4}->{5}" -f $route, $(if ($ok) { 'PASS' } else { 'FAIL' }), $expStatus, $res.status, $expBytes, $res.bytes)
    }
    Write-Output ($(if ($fails) { "PARITY FAIL: $fails route(s) differ" } else { "PARITY PASS: all $($manifest.Count) routes identical" }))
    exit $(if ($fails) { 1 } else { 0 })
}
