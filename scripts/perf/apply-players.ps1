# Apply the players-index snapshot file, or a plain-view stand-in, in one
# transaction. Refresh any of the five names that are materialized views
# before commit. Plain views are skipped. Readers of these names block
# until commit instead of seeing a dropped or empty relation.
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

DO $refresh_players_index$
DECLARE
    target text;
    kind "char";
BEGIN
    FOREACH target IN ARRAY ARRAY[
        'v_players_index_vol_season',
        'v_players_index_vol_career',
        'v_players_index_career',
        'v_players_index_season',
        'v_players_index_gap'
    ]
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
$refresh_players_index$;
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
