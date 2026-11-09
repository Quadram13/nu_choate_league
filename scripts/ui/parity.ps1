# Route parity harness for the UI/IA wave (#45 board).
# Capture mode saves each route's body + manifest (status, bytes, sha256).
# Check mode re-fetches and diffs against a captured manifest.
#
# Check mode strips the shell switcher before hashing. The switcher is the
# one <nav class="theme-switch">...</nav> element, including the newline and
# indent in front of it. On the modern shell that slice is 194 UTF-8 bytes.
# A switcher whose slice is any other length is an error. Capture mode keeps
# the raw body. The strip is logged per route.
#
# Redirects: PowerShell 7 puts the response on HttpResponseException, and
# .Headers.Location is the relative target (fragment included). The string
# indexer on that header collection stringifies empty. Windows PowerShell 5.1
# throws InvalidOperationException from Invoke-WebRequest -MaximumRedirection 0
# and the exception has no response object, so those routes fall back to
# WebRequest with AllowAutoRedirect false. 200 bodies still come from
# Invoke-WebRequest, which is what the baseline hashes were captured with.
# Usage:
#   scripts/ui/parity.ps1 -Mode capture -BaseUrl http://127.0.0.1:8100 -OutDir <dir>
#   scripts/ui/parity.ps1 -Mode check   -BaseUrl http://127.0.0.1:8100 -CheckDir <dir>
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

function Read-Location($headers) {
    if (-not $headers) { return '' }
    $direct = $null
    try { $direct = $headers.Location } catch { $direct = $null }
    if ($direct) { return [string]$direct }
    try {
        $indexed = $headers['Location']
        if ($indexed) { return [string]$indexed }
    } catch {}
    return ''
}

function Get-RedirectViaWebRequest([string]$url) {
    # PS 5.1 never hands back the 302 from Invoke-WebRequest -MaximumRedirection 0.
    $req = [System.Net.WebRequest]::Create($url)
    $req.AllowAutoRedirect = $false
    $req.Timeout = 120000
    $resp = $req.GetResponse()
    try {
        $location = ''
        if ($resp.Headers) {
            $location = [string]$resp.Headers['Location']
            if (-not $location) { $location = [string]$resp.GetResponseHeader('Location') }
        }
        return @{ status = [int]$resp.StatusCode; location = $location }
    } finally {
        $resp.Close()
    }
}

function Remove-ThemeSwitch([string]$text, [string]$route) {
    $match = [regex]::Match($text, '(?s)\r?\n[ \t]*<nav class="theme-switch".*?</nav>')
    if (-not $match.Success) {
        return @{ text = $text; stripped = $false }
    }
    $raw = [System.Text.Encoding]::UTF8.GetBytes($match.Value)
    if ($raw.Length -ne 194) {
        throw "theme-switch on $route stripped $($raw.Length) bytes, expected 194"
    }
    return @{ text = $text.Remove($match.Index, $match.Length); stripped = $true }
}

function Get-Route([string]$url) {
    $status = 0
    $location = ''
    $text = ''
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 120 -ErrorAction Stop
        $status = [int]$r.StatusCode
        $location = Read-Location $r.Headers
        if ($status -eq 200) { $text = [string]$r.Content }
    } catch {
        $resp = $_.Exception.Response
        if (-not $resp -and $_.Exception.InnerException) {
            $resp = $_.Exception.InnerException.Response
        }
        if ($resp) {
            $status = [int]$resp.StatusCode
            $location = Read-Location $resp.Headers
        } else {
            $fallback = Get-RedirectViaWebRequest $url
            $status = $fallback.status
            $location = $fallback.location
        }
    }
    $bytes = 0
    $sha = ''
    if ($status -eq 200) {
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
        $stripped = $false
        $gotBytes = $res.bytes
        $gotSha = $res.sha256
        if ($res.status -eq 200 -and $res.body) {
            $clean = Remove-ThemeSwitch $res.body $route
            if ($clean.stripped) {
                $stripped = $true
                $raw = [System.Text.Encoding]::UTF8.GetBytes($clean.text)
                $gotBytes = $raw.Length
                $gotSha = (Get-FileHash -InputStream ([System.IO.MemoryStream]::new($raw)) -Algorithm SHA256).Hash
            }
        }
        $ok = ($res.status -eq [int]$expStatus) -and ($gotSha -eq $expSha) -and ($res.location -eq $expLoc)
        if (-not $ok) { $fails++ }
        $note = ''
        if ($stripped) { $note = ' stripped theme-switch 194' }
        Write-Output ("{0,-48} {1} status {2}->{3} bytes {4}->{5}{6}" -f $route, $(if ($ok) { 'PASS' } else { 'FAIL' }), $expStatus, $res.status, $expBytes, $gotBytes, $note)
    }
    Write-Output ($(if ($fails) { "PARITY FAIL: $fails route(s) differ" } else { "PARITY PASS: all $($manifest.Count) routes identical" }))
    exit $(if ($fails) { 1 } else { 0 })
}
