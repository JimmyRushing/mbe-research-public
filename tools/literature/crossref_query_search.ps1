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

function Get-CrossrefResults {
    param(
        [string]$Query,
        [string]$QueryField = 'bibliographic'
    )

    $cursor = '*'
    $all = @()
    while ($true) {
        if ($QueryField -eq 'title') {
            $url = 'https://api.crossref.org/works?filter=type:journal-article&rows=100&cursor={0}&query.title={1}' -f `
                [uri]::EscapeDataString($cursor), [uri]::EscapeDataString($Query)
        } else {
            $url = 'https://api.crossref.org/works?filter=type:journal-article&rows=100&cursor={0}&query.bibliographic={1}' -f `
                [uri]::EscapeDataString($cursor), [uri]::EscapeDataString($Query)
        }

        $resp = Invoke-RestMethod -Uri $url
        if ($resp.message.items) {
            $all += @($resp.message.items)
        }
        $nextCursor = $resp.message.'next-cursor'
        if (-not $nextCursor -or $nextCursor -eq $cursor) {
            break
        }
        $cursor = $nextCursor
    }
    return $all
}

function Get-TitleText {
    param($Item)
    if ($Item.title -and $Item.title.Count -gt 0) {
        return $Item.title[0]
    }
    return ''
}

function Get-ContainerTitle {
    param($Item)
    if ($Item.'container-title' -and $Item.'container-title'.Count -gt 0) {
        return $Item.'container-title'[0]
    }
    return ''
}

function Get-AuthorText {
    param($Item)
    if (-not $Item.author) { return '' }
    (($Item.author | ForEach-Object {
        $parts = @()
        if ($_.given) { $parts += $_.given }
        if ($_.family) { $parts += $_.family }
        ($parts -join ' ').Trim()
    }) -join '; ')
}

function Get-Year {
    param($Item)
    $sources = @(
        $Item.issued.'date-parts',
        $Item.'published-print'.'date-parts',
        $Item.'published-online'.'date-parts',
        $Item.created.'date-parts'
    )
    foreach ($src in $sources) {
        if ($src -and $src.Count -gt 0 -and $src[0].Count -gt 0) {
            return [string]$src[0][0]
        }
    }
    return ''
}

function Get-Key {
    param($Title, $DOI)
    if ($DOI) { return $DOI.ToLowerInvariant() }
    return $Title.ToLowerInvariant()
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
    $lines.Add("Source: Crossref article search on $(Get-Date -Format 'yyyy-MM-dd').")
    $lines.Add('')
    $lines.Add("Count: $($Rows.Count)")
    $lines.Add('')
    $lines.Add('Queries used:')
    foreach ($q in $Queries) {
        $lines.Add(('- `{0}`' -f $q))
    }
    $lines.Add('')
    foreach ($row in ($Rows | Sort-Object year, title)) {
        $link = if ($row.doi) { 'https://doi.org/' + $row.doi } else { $row.url }
        $line = '- {0}. [{1}]({2}). {3}. *{4}*. Query hits: ``{5}``' -f `
            $row.year, $row.title, $link, $row.authors, $row.journal, $row.matched_queries
        $lines.Add($line)
    }
    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
}

switch ($Mode) {
    'sb111_iiiv' {
        $summaryTitle = 'Crossref search: Sb(111) and III-V'
        $prefix = 'crossref_sb111_iiiv'
        $queryField = 'bibliographic'
        $queries = @(
            'Sb(111) GaSb',
            'Sb(111) InSb',
            'Sb(111) GaAs',
            'Sb(111) InP',
            'Sb(111) InAs',
            'Sb(111) AlSb',
            'Sb/GaSb(111)',
            'Sb on InSb(111)',
            'antimony(111) GaSb',
            'antimony(111) InSb',
            'elemental Sb quantum wells GaSb',
            'Sb thin film GaSb(111)',
            'Sb epitaxy GaSb(111)',
            'Sb(111) semiconductor substrate'
        )
    }
    'antimonene' {
        $summaryTitle = 'Crossref search: antimonene'
        $prefix = 'crossref_antimonene'
        $queryField = 'title'
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

$byKey = @{}
foreach ($query in $queries) {
    $items = Get-CrossrefResults -Query $query -QueryField $queryField
    foreach ($item in $items) {
        $title = Get-TitleText -Item $item
        $doi = if ($item.DOI) { $item.DOI } else { '' }
        if (-not $title) { continue }
        $key = Get-Key -Title $title -DOI $doi
        if (-not $byKey.ContainsKey($key)) {
            $byKey[$key] = [ordered]@{
                title = $title
                doi = $doi
                year = Get-Year -Item $item
                journal = Get-ContainerTitle -Item $item
                authors = Get-AuthorText -Item $item
                url = $item.URL
                matched = New-Object System.Collections.Generic.List[string]
            }
        }
        if (-not $byKey[$key].matched.Contains($query)) {
            $null = $byKey[$key].matched.Add($query)
        }
    }
}

$rows = foreach ($entry in $byKey.GetEnumerator()) {
    [pscustomobject]@{
        title = $entry.Value.title
        doi = $entry.Value.doi
        year = $entry.Value.year
        journal = $entry.Value.journal
        authors = $entry.Value.authors
        url = $entry.Value.url
        matched_queries = ($entry.Value.matched -join ' | ')
    }
}

$csvPath = Join-Path $OutDir ($prefix + '.csv')
$mdPath = Join-Path $OutDir ($prefix + '.md')
$htmlPath = Join-Path $OutDir ($prefix + '.html')

$rows | Sort-Object year, title | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $csvPath
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
