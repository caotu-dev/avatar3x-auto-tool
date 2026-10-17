$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# Stage first, then update only package-owned files. Keep runtime and logs.
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath build/release-stage --workpath build/pyinstaller AvatarFishingBot.spec
if ($LASTEXITCODE -ne 0) { throw 'Đóng gói thất bại' }
$taskStage = Join-Path $PSScriptRoot 'build/release-stage/AvatarFishingBot'
$taskRelease = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'dist/AvatarFishingBot'))
$taskManifest = Join-Path $taskRelease 'release-files.json'
New-Item -ItemType Directory -Path $taskRelease -Force | Out-Null
$taskFiles = @(Get-ChildItem -LiteralPath $taskStage -File -Recurse | ForEach-Object { $_.FullName.Substring($taskStage.Length + 1) })
if (Test-Path -LiteralPath $taskManifest) {
    $taskPreviousFiles = Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
    foreach ($taskOld in $taskPreviousFiles) {
        $taskOldPath = [IO.Path]::GetFullPath((Join-Path $taskRelease $taskOld))
        if (-not $taskOldPath.StartsWith($taskRelease + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest chứa đường dẫn ngoài package' }
        if ($taskOld -match '^(runtime|debug)[\\/]' -or $taskOld -in $taskFiles) { continue }
        if (Test-Path -LiteralPath $taskOldPath -PathType Leaf) { Remove-Item -LiteralPath $taskOldPath -Force }
    }
}
foreach ($taskFile in $taskFiles) {
    if ($taskFile -match '^(runtime|debug)[\\/]') { throw 'Package không được ghi đè dữ liệu runtime/debug' }
    $taskDestination = Join-Path $taskRelease $taskFile
    New-Item -ItemType Directory -Path (Split-Path $taskDestination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $taskStage $taskFile) -Destination $taskDestination -Force
}
ConvertTo-Json -InputObject $taskFiles | Set-Content -LiteralPath $taskManifest -Encoding utf8
Write-Host 'Mở dist\AvatarFishingBot\AvatarFishingBot.exe. Giữ nguyên cả thư mục. runtime/debug được giữ khi build lại.'
$taskBuildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'build'))
if ($taskBuildRoot -ne ([IO.Path]::GetFullPath($PSScriptRoot) + '\build')) { throw 'Build cleanup path mismatch' }
Remove-Item -LiteralPath $taskBuildRoot -Recurse -Force
