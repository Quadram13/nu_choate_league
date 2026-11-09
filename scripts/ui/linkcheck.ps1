# One-hop link checker for the hub IA pass (#102).
# Fetches the seed routes, then every href in those documents.
# A target must return 200, or a 3xx whose Location returns 200.
# A #fragment must match an id (or name) in the final document.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/ui/linkcheck.ps1 -BaseUrl http://127.0.0.1:8118 -Manifest <manifest.tsv>
param(
    [string]$BaseUrl = 'http://127.0.0.1:8118',
    [string]$Manifest = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$defaultSeeds = @(
    '/',
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
    # Windows PowerShell 5.1 throws from Invoke-WebRequest -MaximumRedirection 0
    # and the exception has no response object. A down server throws here too.
    try {
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
    } catch {
        $web = $_.Exception
        if ($web.InnerException) { $web = $web.InnerException }
        $resp = $null
        try { $resp = $_.Exception.Response } catch { $resp = $null }
        if ($resp) {
            try {
                $location = ''
                if ($resp.Headers) { $location = [string]$resp.Headers['Location'] }
                return @{ status = [int]$resp.StatusCode; location = $location }
            } finally {
                $resp.Close()
            }
        }
        return @{ status = 0; location = '' }
    }
}

function Get-Page([string]$url) {
    $status = 0
    $location = ''
    $body = ''
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 30 -ErrorAction Stop
        $status = [int]$response.StatusCode
        $location = Read-Location $response.Headers
        if ($status -eq 200) { $body = [string]$response.Content }
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
    return @{ status = $status; location = $location; body = $body }
}

function Get-Final([string]$url) {
    $current = $url
    $carried = ''
    $guard = 0
    while ($guard -lt 5) {
        $guard++
        $page = Get-Page $current
        if ($page.status -ge 300 -and $page.status -lt 400 -and $page.location) {
            $next = (New-Object System.Uri -ArgumentList ([System.Uri]$current), $page.location).AbsoluteUri
            $hash = $next.IndexOf('#')
            if ($hash -ge 0) {
                $carried = [Uri]::UnescapeDataString($next.Substring($hash + 1))
                $current = $next.Substring(0, $hash)
            } else {
                $current = $next
            }
            continue
        }
        return @{ status = $page.status; body = $page.body; url = $current; fragment = $carried }
    }
    return @{ status = 0; body = ''; url = $current; fragment = $carried }
}

function Resolve-Href([string]$href, [string]$pageUrl) {
    if (-not $href) { return $null }
    $href = $href.Trim()
    if (-not $href) { return $null }
    $lower = $href.ToLowerInvariant()
    if ($lower.StartsWith('mailto:') -or $lower.StartsWith('javascript:') -or $lower.StartsWith('data:') -or $lower.StartsWith('tel:')) {
        return $null
    }
    $href = $href.Replace('&amp;', '&').Replace('&quot;', '"').Replace('&#39;', "'")
    $base = [System.Uri]$pageUrl
    try {
        $abs = New-Object System.Uri -ArgumentList $base, $href
    } catch {
        return @{ bad = $true; href = $href }
    }
    if ($abs.Host -ne $base.Host -or $abs.Port -ne $base.Port) {
        return @{ external = $true; url = $abs.AbsoluteUri }
    }
    $fragment = ''
    if ($abs.Fragment) { $fragment = [Uri]::UnescapeDataString($abs.Fragment.TrimStart('#')) }
    $without = $abs.GetLeftPart([System.UriPartial]::Query)
    return @{ external = $false; url = $without; fragment = $fragment }
}

$seeds = @()
if ($Manifest -and (Test-Path $Manifest)) {
    foreach ($line in (Get-Content $Manifest | Select-Object -Skip 1)) {
        if (-not $line) { continue }
        $route, $status = ($line -split "`t")[0, 1]
        if ($status -eq '200') { $seeds += $route }
    }
}
if (-not $seeds.Count) { $seeds = $defaultSeeds }

$base = $BaseUrl.TrimEnd('/')
$cache = @{}
$failures = New-Object System.Collections.Generic.List[string]
$hrefCount = 0
$external = 0
$bad = 0

function Get-Cached([string]$url, [bool]$needBody) {
    $known = $cache.ContainsKey($url)
    if (-not $known) {
        $page = Get-Final $url
        $keep = $needBody -or [bool]$page.fragment
        $page.kept = [bool]($keep -and $page.body)
        if (-not $page.kept) { $page.body = '' }
        $cache[$url] = $page
        if ($cache.Count % 100 -eq 0) {
            Write-Host ("fetched {0}" -f $cache.Count)
        }
    } elseif ($needBody -and -not $cache[$url].kept) {
        $page = Get-Final $url
        $page.kept = [bool]$page.body
        $cache[$url] = $page
    }
    return $cache[$url]
}

function Test-Anchor([string]$body, [string]$frag) {
    if (-not $frag) { return $true }
    $idDouble = 'id="' + $frag + '"'
    $idSingle = "id='" + $frag + "'"
    $nameDouble = 'name="' + $frag + '"'
    $nameSingle = "name='" + $frag + "'"
    if (-not $body) { return $false }
    return ($body.IndexOf($idDouble) -ge 0 -or $body.IndexOf($idSingle) -ge 0 -or $body.IndexOf($nameDouble) -ge 0 -or $body.IndexOf($nameSingle) -ge 0)
}

Write-Output ("seeds {0}" -f $seeds.Count)
foreach ($route in $seeds) {
    $pageUrl = "$base$route"
    $doc = Get-Cached $pageUrl $true
    $mark = 'PASS'
    if ($doc.status -ne 200) {
        $mark = 'FAIL'
        $failures.Add("SEED $route status $($doc.status)")
    }
    Write-Output ("{0,-52} {1} {2}" -f $route, $mark, $doc.status)
    if (-not $doc.body) { continue }
    $found = New-Object System.Collections.Generic.List[string]
    foreach ($match in [regex]::Matches($doc.body, 'href\s*=\s*"([^"]*)"')) { $found.Add($match.Groups[1].Value) }
    foreach ($match in [regex]::Matches($doc.body, "href\s*=\s*'([^']*)'")) { $found.Add($match.Groups[1].Value) }
    $seenOnPage = @{}
    foreach ($href in $found) {
        if ($seenOnPage.ContainsKey($href)) { continue }
        $seenOnPage[$href] = $true
        $hrefCount++
        $resolved = Resolve-Href $href $pageUrl
        if (-not $resolved) { continue }
        if ($resolved.bad) {
            $bad++
            $failures.Add("BAD $route href $href")
            continue
        }
        if ($resolved.external) { $external++; continue }
        $fragHint = [bool]$resolved.fragment
        $target = Get-Cached $resolved.url $fragHint
        if ($target.status -ne 200) {
            $failures.Add("HREF $route -> $($resolved.url) status $($target.status)")
            continue
        }
        $frag = $resolved.fragment
        if (-not $frag) { $frag = $target.fragment }
        if ($frag -and -not (Test-Anchor $target.body $frag)) {
            $failures.Add("ANCHOR $route -> $($resolved.url)#$frag missing")
        }
    }
    # The seed body is only needed while this page's own anchors are checked.
    if ($cache.ContainsKey($pageUrl)) {
        $cache[$pageUrl].body = ''
        $cache[$pageUrl].kept = $false
    }
}

Write-Output ("hrefs {0} unique {1} external {2}" -f $hrefCount, $cache.Count, $external)
if ($failures.Count) {
    Write-Output '--- failures ---'
    foreach ($row in $failures) { Write-Output $row }
    Write-Output ("LINKCHECK FAIL: {0}" -f $failures.Count)
    exit 1
}
Write-Output 'LINKCHECK PASS'
exit 0
