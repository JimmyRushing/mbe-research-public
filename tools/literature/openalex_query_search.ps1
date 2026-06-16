param(
    [ValidateSet('sb111_iiiv','antimonene')]
    [string]$Mode,

    [string]$OutDir
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'codex_paths.ps1')
$CodexPaths = Get-CodexProjectPaths -StartDir $PSScriptRoot
if (-not $OutDir) {
    $OutDir = $CodexPaths.CitationsDir
}

function Get-OpenAlexSearchResults {
    param([string]$SearchQuery)

    $cursor = '*'
    $all = @()
    $base = 'https://api.openalex.org/works?filter=type:article&search={0}&per-page=200&select=id,display_name,doi,publication_year,primary_location,authorships,type' -f ([uri]::EscapeDataString($SearchQuery))
    while ($true) {
        $url = "$base&cursor=$([uri]::EscapeDataString($cursor))"
        $resp = Invoke-RestMethod -Uri $url
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

function New-Record {
    param(
        $Work,
        [string[]]$MatchedQueries
    )

    [pscustomobject]@{
        openalex_id      = Normalize-OpenAlexId $Work.id
        title            = $Work.display_name
        publication_year = $Work.publication_year
        doi              = $Work.doi
        source           = Get-SourceName $Work
        landing_page     = Get-LandingPage $Work
        authors          = Get-AuthorsString $Work.authorships
        matched_queries  = ($MatchedQueries -join ' | ')
    }
}

function Write-MarkdownSummary {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Queries,
        [psobject[]]$Rows
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# $Title")
    $lines.Add('')
    $lines.Add("Source: OpenAlex article search on $(Get-Date -Format 'yyyy-MM-dd').")
    $lines.Add('')
    $lines.Add("Count: $($Rows.Count)")
    $lines.Add('')
    $lines.Add('Queries used:')
    foreach ($q in $Queries) {
        $lines.Add(('- `{0}`' -f $q))
    }
    $lines.Add('')
    foreach ($row in ($Rows | Sort-Object publication_year, title)) {
        $link = if ($row.doi) { $row.doi } else { $row.landing_page }
        $line = '- {0}. [{1}]({2}). {3}. *{4}*. Query hits: ``{5}``' -f `
            $row.publication_year, $row.title, $link, $row.authors, $row.source, $row.matched_queries
        $lines.Add($line)
    }

    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
}

switch ($Mode) {
    'sb111_iiiv' {
        $summaryTitle = 'OpenAlex search: Sb(111) and III-V'
        $prefix = 'openalex_sb111_iiiv'
        $queries = @(
            'Sb(111) III-V',
            'Sb(111) III V',
            'Sb(111) III/V',
            'Sb (111) III-V',
            'Sb (111) III V',
            'antimony(111) III-V',
            'antimony (111) III-V',
            'antimony(111) III V',
            'antimony (111) III V',
            'Sb(111) III-V semiconductor',
            'Sb(111) III-V substrate',
            'Sb(111) III-V epitaxy'
        )
    }
    'antimonene' {
        $summaryTitle = 'OpenAlex search: antimonene'
        $prefix = 'openalex_antimonene'
        $queries = @(
            'antimonene',
            'alpha-antimonene',
            'beta-antimonene',
            'alpha antimonene',
            'beta antimonene'
        )
    }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$byId = @{}
foreach ($query in $queries) {
    $works = Get-OpenAlexSearchResults -SearchQuery $query
    foreach ($work in $works) {
        $id = Normalize-OpenAlexId $work.id
        if (-not $id) { continue }
        if (-not $byId.ContainsKey($id)) {
            $byId[$id] = [ordered]@{
                work = $work
                queries = New-Object System.Collections.Generic.List[string]
            }
        }
        if (-not $byId[$id].queries.Contains($query)) {
            $null = $byId[$id].queries.Add($query)
        }
    }
}

$rows = foreach ($entry in $byId.GetEnumerator()) {
    New-Record -Work $entry.Value.work -MatchedQueries $entry.Value.queries
}

$csvPath = Join-Path $OutDir ($prefix + '.csv')
$mdPath = Join-Path $OutDir ($prefix + '.md')
$htmlPath = Join-Path $OutDir ($prefix + '.html')

$rows | Sort-Object publication_year, title | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $csvPath
Write-MarkdownSummary -Path $mdPath -Title $summaryTitle -Queries $queries -Rows $rows

$converter = Join-Path $CodexPaths.ToolsDir 'convert_simple_markdown_to_html.ps1'
if (Test-Path -LiteralPath $converter) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $converter -InputPath $mdPath -OutputPath $htmlPath | Out-Null
}

Write-Output "MODE=$Mode"
Write-Output "COUNT=$($rows.Count)"
Write-Output "CSV=$csvPath"
Write-Output "MD=$mdPath"
Write-Output "HTML=$htmlPath"
