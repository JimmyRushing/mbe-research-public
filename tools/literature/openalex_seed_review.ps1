param(
    [Parameter(Mandatory = $true)]
    [string]$Doi,

    [string]$SeedOpenAlexId,

    [string]$Prefix,

    [string]$OutDir
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'codex_paths.ps1')
$CodexPaths = Get-CodexProjectPaths -StartDir $PSScriptRoot
if (-not $OutDir) {
    $OutDir = $CodexPaths.CitationsDir
}

function Normalize-OpenAlexId {
    param([string]$Id)
    if ([string]::IsNullOrWhiteSpace($Id)) { return $null }
    if ($Id -match 'https://openalex.org/(W\d+)') {
        return $matches[1]
    }
    return $Id
}

function Get-AuthorsString {
    param($Authorships)
    if ($null -eq $Authorships) { return '' }
    (($Authorships | ForEach-Object { $_.author.display_name }) -join '; ')
}

function Get-SourceName {
    param($Work)
    if ($Work.primary_location -and $Work.primary_location.source) {
        return $Work.primary_location.source.display_name
    }
    return ''
}

function Get-LandingPage {
    param($Work)
    if ($Work.primary_location -and $Work.primary_location.landing_page_url) {
        return $Work.primary_location.landing_page_url
    }
    return ''
}

function Get-OpenAccessStatus {
    param($Work)
    if ($Work.open_access -and $Work.open_access.oa_status) {
        return $Work.open_access.oa_status
    }
    return ''
}

function Get-ConceptsString {
    param($Concepts)
    if ($null -eq $Concepts) { return '' }
    (($Concepts | Select-Object -First 5 | ForEach-Object { $_.display_name }) -join '; ')
}

function Get-PrimaryTopic {
    param($Work)
    if ($Work.primary_topic -and $Work.primary_topic.display_name) {
        return $Work.primary_topic.display_name
    }
    return ''
}

function Get-OpenAlexJson {
    param([string]$Url)
    $response = Invoke-RestMethod -Uri $Url -Headers @{ 'User-Agent' = 'DissertationCodexOpenAlex/0.1 (mailto:research@example.invalid)' }
    if ($response -is [string]) {
        return ($response | ConvertFrom-Json)
    }
    return $response
}

function Get-OpenAlexPagedResults {
    param([string]$BaseUrl)

    $cursor = '*'
    $all = @()
    while ($true) {
        $url = "$BaseUrl&cursor=$([uri]::EscapeDataString($cursor))"
        $resp = Get-OpenAlexJson -Url $url
        if ($resp.results) {
            $all += @($resp.results)
        }
        if (-not $resp.meta.next_cursor) {
            break
        }
        $cursor = $resp.meta.next_cursor
    }
    return $all
}

function Convert-ToRecord {
    param(
        $Work,
        [string]$Relation
    )

    [pscustomobject]@{
        relation         = $Relation
        openalex_id      = Normalize-OpenAlexId $Work.id
        title            = $Work.display_name
        publication_year = $Work.publication_year
        doi              = $Work.doi
        source           = Get-SourceName $Work
        landing_page     = Get-LandingPage $Work
        authors          = Get-AuthorsString $Work.authorships
        type             = $Work.type
        cited_by_count   = $Work.cited_by_count
        open_access      = Get-OpenAccessStatus $Work
        primary_topic    = Get-PrimaryTopic $Work
        concepts         = Get-ConceptsString $Work.concepts
    }
}

function Get-WorksByOpenAlexIds {
    param(
        [string[]]$Ids,
        [string]$Relation
    )

    $rows = @()
    $cleanIds = @($Ids | ForEach-Object { Normalize-OpenAlexId $_ } | Where-Object { $_ } | Sort-Object -Unique)
    $select = 'id,display_name,doi,publication_year,primary_location,authorships,type,cited_by_count,open_access,primary_topic,concepts'
    foreach ($id in $cleanIds) {
        $url = 'https://api.openalex.org/works/{0}?select={1}' -f $id, $select
        try {
            $work = Get-OpenAlexJson -Url $url
            $rows += Convert-ToRecord -Work $work -Relation $Relation
            Start-Sleep -Milliseconds 120
        } catch {
            Write-Warning "Could not fetch referenced work ${id}: $($_.Exception.Message)"
        }
    }
    return $rows
}

function Get-LinkForRow {
    param($Row)
    if ($Row.doi) { return $Row.doi }
    if ($Row.landing_page) { return $Row.landing_page }
    if ($Row.openalex_id) { return 'https://openalex.org/' + $Row.openalex_id }
    return ''
}

function Add-WorkLines {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [psobject[]]$Rows,
        [string]$EmptyMessage
    )

    if ($Rows.Count -eq 0) {
        $Lines.Add($EmptyMessage)
        return
    }

    foreach ($row in ($Rows | Sort-Object publication_year, title)) {
        $link = Get-LinkForRow -Row $row
        $source = if ($row.source) { $row.source } else { 'source unknown' }
        $authors = if ($row.authors) { $row.authors } else { 'authors unknown' }
        $line = '- {0}. [{1}]({2}). {3}. *{4}*. Cited by OpenAlex: {5}. OpenAlex: `{6}`' -f `
            $row.publication_year, $row.title, $link, $authors, $source, $row.cited_by_count, $row.openalex_id
        $Lines.Add($line)
    }
}

function Write-MarkdownReview {
    param(
        [string]$Path,
        $Seed,
        [psobject[]]$ReferenceRows,
        [psobject[]]$CitingRows,
        [psobject[]]$CombinedRows
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $seedId = Normalize-OpenAlexId $Seed.id
    $lines.Add("# OpenAlex Literature Review: Thermal Laser Evaporation")
    $lines.Add('')
    $lines.Add("Source: OpenAlex query on $(Get-Date -Format 'yyyy-MM-dd').")
    $lines.Add('')
    $lines.Add("Seed title: $($Seed.display_name)")
    $lines.Add("Seed DOI: $($Seed.doi)")
    $lines.Add(('Seed OpenAlex ID: `{0}`' -f $seedId))
    $lines.Add("Publication year: $($Seed.publication_year)")
    $lines.Add("OpenAlex cited_by_count: $($Seed.cited_by_count)")
    $lines.Add("OpenAlex referenced_works_count: $($Seed.referenced_works_count)")
    $lines.Add('')
    $lines.Add("Backward references returned: $($ReferenceRows.Count)")
    $lines.Add("Forward citing works returned: $($CitingRows.Count)")
    $lines.Add("Combined rows written: $($CombinedRows.Count)")
    $lines.Add('')
    $lines.Add("## Working Read")
    $lines.Add('')
    $lines.Add('This seed paper is a methods paper for thermal laser evaporation/thermal laser epitaxy: laser heating of elemental sources, broad periodic-table coverage, high flux from freestanding sources, and reduced crucible/material compatibility constraints. Read the backward references as the technical lineage: laser MBE/laser evaporation, refractory-element source engineering, flux calibration, and earlier oxide/nitride/semiconductor growth methods. Read the forward citations as the adoption map: later papers using TLE as a synthesis platform, especially where conventional effusion cells, e-beam evaporation, or PLD are awkward because of source contamination, refractory elements, reactive gases, or multi-element composition control.')
    $lines.Add('')
    $lines.Add('For your MBE-material-exploration framing, the useful bridge is that TLE expands source-material choice while preserving an MBE-like vacuum/growth logic. It is not a replacement for III-V MBE in the narrow sense, but it is a platform argument for rapidly exploring difficult elemental fluxes and heterostructures. When connecting this to superconductors or Sb/III-V work, emphasize source flexibility, high-purity elemental supply, refractory/high-melting elements, and compatibility with thin-film discovery workflows.')
    $lines.Add('')
    $lines.Add('## Highest-Citation Context Works')
    $lines.Add('')
    $top = @($CombinedRows | Sort-Object @{Expression = 'cited_by_count'; Descending = $true}, publication_year | Select-Object -First 12)
    Add-WorkLines -Lines $lines -Rows $top -EmptyMessage 'No works returned.'
    $lines.Add('')
    $lines.Add('## Papers Referenced By The Seed Paper')
    $lines.Add('')
    Add-WorkLines -Lines $lines -Rows $ReferenceRows -EmptyMessage 'No backward references were returned by OpenAlex for this seed paper.'
    $lines.Add('')
    $lines.Add('## Papers Citing The Seed Paper')
    $lines.Add('')
    Add-WorkLines -Lines $lines -Rows $CitingRows -EmptyMessage 'No forward citations were returned by OpenAlex for this seed paper.'

    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$seedUrl = if ($SeedOpenAlexId) {
    'https://api.openalex.org/works/{0}?select=id,display_name,doi,publication_year,cited_by_count,referenced_works_count,referenced_works' -f (Normalize-OpenAlexId $SeedOpenAlexId)
} else {
    'https://api.openalex.org/works/doi:{0}?select=id,display_name,doi,publication_year,cited_by_count,referenced_works_count,referenced_works' -f [uri]::EscapeDataString($Doi)
}
$seed = Get-OpenAlexJson -Url $seedUrl
$seedId = Normalize-OpenAlexId $seed.id

if (-not $seedId) {
    $searchUrl = 'https://api.openalex.org/works?search={0}&per-page=1&select=id,display_name,doi,publication_year,cited_by_count,referenced_works_count,referenced_works' -f [uri]::EscapeDataString($Doi)
    $search = Get-OpenAlexJson -Url $searchUrl
    if ($search.results -and $search.results.Count -gt 0) {
        $seed = $search.results[0]
        $seedId = Normalize-OpenAlexId $seed.id
    }
}

if (-not $seedId) {
    throw "Could not resolve an OpenAlex seed work for DOI '$Doi'. Try passing -SeedOpenAlexId W..."
}

if (-not $Prefix) {
    $Prefix = ($Doi.ToLowerInvariant() -replace '^https?://doi\.org/', '' -replace '[^a-z0-9]+', '_').Trim('_')
}

$referenceRows = @(Get-WorksByOpenAlexIds -Ids $seed.referenced_works -Relation 'referenced_by_seed')

$select = 'id,display_name,doi,publication_year,primary_location,authorships,type,cited_by_count,open_access,primary_topic,concepts'
$citingBase = 'https://api.openalex.org/works?filter=cites:{0}&per-page=200&select={1}' -f $seedId, $select
$citingWorks = Get-OpenAlexPagedResults -BaseUrl $citingBase
$citingRows = @($citingWorks | ForEach-Object { Convert-ToRecord -Work $_ -Relation 'cites_seed' })
$combinedRows = @($referenceRows + $citingRows)

$referencesCsvPath = Join-Path $OutDir ($Prefix + '_openalex_references.csv')
$citingCsvPath = Join-Path $OutDir ($Prefix + '_openalex_citing_works.csv')
$combinedCsvPath = Join-Path $OutDir ($Prefix + '_openalex_lit_review_combined.csv')
$mdPath = Join-Path $OutDir ($Prefix + '_openalex_lit_review.md')
$htmlPath = Join-Path $OutDir ($Prefix + '_openalex_lit_review.html')

$referenceRows | Sort-Object publication_year, title | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $referencesCsvPath
$citingRows | Sort-Object publication_year, title | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $citingCsvPath
$combinedRows | Sort-Object relation, publication_year, title | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $combinedCsvPath
Write-MarkdownReview -Path $mdPath -Seed $seed -ReferenceRows $referenceRows -CitingRows $citingRows -CombinedRows $combinedRows

$converter = Join-Path $CodexPaths.ToolsDir 'convert_simple_markdown_to_html.ps1'
if (Test-Path -LiteralPath $converter) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $converter -InputPath $mdPath -OutputPath $htmlPath | Out-Null
}

Write-Output "DOI=$Doi"
Write-Output "SEED_OPENALEX_ID=$seedId"
Write-Output "OPENALEX_CITED_BY_COUNT=$($seed.cited_by_count)"
Write-Output "OPENALEX_REFERENCED_WORKS_COUNT=$($seed.referenced_works_count)"
Write-Output "REFERENCES_RETURNED=$($referenceRows.Count)"
Write-Output "CITING_WORKS_RETURNED=$($citingRows.Count)"
Write-Output "REFERENCES_CSV=$referencesCsvPath"
Write-Output "CITING_CSV=$citingCsvPath"
Write-Output "COMBINED_CSV=$combinedCsvPath"
Write-Output "MD=$mdPath"
Write-Output "HTML=$htmlPath"
