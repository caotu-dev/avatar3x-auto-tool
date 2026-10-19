$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$taskPackage = Join-Path $PSScriptRoot 'dist/AvatarFishingBot'
$taskManifest = Join-Path $taskPackage 'release-files.json'
if (-not (Test-Path -LiteralPath $taskManifest)) { throw 'Run build_gui.ps1 first.' }
$taskFiles = Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
$taskOutput = Join-Path $PSScriptRoot 'dist/release'
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
$taskZip = Join-Path $taskOutput 'Avatools-3x-windows-x64.zip'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$taskStream = [IO.File]::Open($taskZip, [IO.FileMode]::Create)
$taskArchive = New-Object IO.Compression.ZipArchive($taskStream, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($taskFile in ($taskFiles + @('release-files.json'))) {
        $taskSource = [IO.Path]::GetFullPath((Join-Path $taskPackage $taskFile))
        if (-not $taskSource.StartsWith($taskPackage + '\', [StringComparison]::OrdinalIgnoreCase) -or $taskFile -match '^(runtime|debug)[\\/]') { throw "Invalid package file: $taskFile" }
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($taskArchive, $taskSource, ('Avatools3x/' + $taskFile.Replace('\', '/')), [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally {
    $taskArchive.Dispose()
    $taskStream.Dispose()
}
$taskHash = (Get-FileHash -LiteralPath $taskZip -Algorithm SHA256).Hash.ToLowerInvariant()
"$taskHash  Avatools-3x-windows-x64.zip" | Set-Content -LiteralPath (Join-Path $taskOutput 'SHA256SUMS.txt') -Encoding ascii
# Legacy names from previous builds are reproducible copies, not user state.
foreach ($taskLegacyName in @('AvatarFishingBot-windows-x64.zip','AvatarFishingBot-sale-fix-windows-x64.zip')) {
    $taskLegacyZip = [IO.Path]::GetFullPath((Join-Path $taskOutput $taskLegacyName))
    if (-not $taskLegacyZip.StartsWith($taskOutput + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive cleanup path mismatch' }
    if (Test-Path -LiteralPath $taskLegacyZip -PathType Leaf) { Remove-Item -LiteralPath $taskLegacyZip -Force }
}
Write-Host "Created $taskZip without personal runtime/debug files."
