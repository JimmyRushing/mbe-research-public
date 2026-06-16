param(
    [Parameter(Mandatory = $true)]
    [string]$Doi,

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

function Get-OpenAlexPagedResults {
    param([string]$BaseUrl)

    $cursor = '*'
    $all = @()
    while ($true) {
        $url = "$BaseUrl&cursor=$([uri]::EscapeDataString($cursor))"
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

function Convert-ToRecord {
    param($Work)

    [pscustomobject]@{
        openalex_id      = Normalize-OpenAlexId $Work.id
        title            = $Work.display_name
        publication_year = $Work.publication_year
        doi              = $Work.doi
        source           = Get-SourceName $Work
        landing_page     = Get-LandingPage $Work
        authors          = Get-AuthorsString $Work.authorships
        type             = $Work.type
    }
}

function Write-MarkdownSummary {
    param(
        [string]$Path,
        $Seed,
        [psobject[]]$Rows
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Papers Citing DOI $Doi")
    $lines.Add('')
    $lines.Add("Source: OpenAlex citing-works query on $(Get-Date -Format 'yyyy-MM-dd').")
    $lines.Add('')
    $lines.Add(('Seed OpenAlex ID: `{0}`' -f (Normalize-OpenAlexId $Seed.id)))
    $lines.Add("Seed title: $($Seed.display_name)")
    $lines.Add("Seed DOI: $($Seed.doi)")
    $lines.Add("OpenAlex cited_by_count: $($Seed.cited_by_count)")
    $lines.Add('')
    $lines.Add("Direct citing works returned: $($Rows.Count)")
    $lines.Add('')

    if ($Rows.Count -eq 0) {
        $lines.Add('No direct citing works were returned by OpenAlex for this DOI.')
    } else {
        foreach ($row in ($Rows | Sort-Object publication_year, title)) {
            $link = if ($row.doi) { $row.doi } elseif ($row.landing_page) { $row.landing_page } else { 'https://openalex.org/' + $row.openalex_id }
            $line = '- {0}. [{1}]({2}). {3}. *{4}*. OpenAlex: `{5}`' -f `
                $row.publication_year, $row.title, $link, $row.authors, $row.source, $row.openalex_id
            $lines.Add($line)
        }
    }

    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$seedUrl = 'https://api.openalex.org/works/doi:' + [uri]::EscapeDataString($Doi)
$seed = Invoke-RestMethod -Uri $seedUrl
$seedId = Normalize-OpenAlexId $seed.id

if (-not $Prefix) {
    $Prefix = ($Doi.ToLowerInvariant() -replace '^https?://doi\.org/', '' -replace '[^a-z0-9]+', '_').Trim('_')
}

$base = 'https://api.openalex.org/works?filter=cites:{0}&per-page=200&select=id,display_name,doi,publication_year,primary_location,authorships,type' -f $seedId
$works = Get-OpenAlexPagedResults -BaseUrl $base
$rows = @($works | ForEach-Object { Convert-ToRecord $_ })

$csvPath = Join-Path $OutDir ($Prefix + '_openalex_citing_works.csv')
$mdPath = Join-Path $OutDir ($Prefix + '_openalex_citing_works.md')
$htmlPath = Join-Path $OutDir ($Prefix + '_openalex_citing_works.html')

$rows | Sort-Object publication_year, title | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $csvPath
Write-MarkdownSummary -Path $mdPath -Seed $seed -Rows $rows

$converter = Join-Path $CodexPaths.ToolsDir 'convert_simple_markdown_to_html.ps1'
if (Test-Path -LiteralPath $converter) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $converter -InputPath $mdPath -OutputPath $htmlPath | Out-Null
}

Write-Output "DOI=$Doi"
Write-Output "SEED_OPENALEX_ID=$seedId"
Write-Output "OPENALEX_CITED_BY_COUNT=$($seed.cited_by_count)"
Write-Output "DIRECT_CITING_COUNT=$($rows.Count)"
Write-Output "CSV=$csvPath"
Write-Output "MD=$mdPath"
Write-Output "HTML=$htmlPath"
