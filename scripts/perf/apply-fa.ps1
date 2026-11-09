# Apply one fa-chain SQL file in a single transaction, then refresh any
# materialized views in the chain before commit. Plain views are skipped.
# Readers block until commit instead of seeing a dropped or empty relation.
param(
    [Parameter(Mandatory = $true)][string]$SqlPath
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $SqlPath)) {
    throw "missing $SqlPath"
}
$sql = Get-Content -LiteralPath $SqlPath -Raw
$head = @"
\set ON_ERROR_STOP on
BEGIN;

"@
$tail = @'

DO $refresh_fa$
DECLARE
    target text;
    kind "char";
BEGIN
    FOREACH target IN ARRAY ARRAY['v_fa_weeks', 'v_fa_season', 'v_fa_career']
    LOOP
        kind := NULL;
        SELECT c.relkind INTO kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = target;
        IF kind = 'm' THEN
            EXECUTE format('REFRESH MATERIALIZED VIEW %I', target);
        END IF;
    END LOOP;
END
$refresh_fa$;
COMMIT;
'@
$script = $head + $sql + "`n" + $tail
$output = $script | & docker exec -i nu-choate-postgres psql -U nu_choate -d nu_choate -v ON_ERROR_STOP=1
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Output $output
    throw "psql exit $code applying $SqlPath"
}
return $output
