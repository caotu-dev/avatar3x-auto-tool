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
    # Reuse identical bundled libraries. Windows/scanners may still hold a DLL
    # open after a diagnostic run; overwriting an unchanged binary is needless.
    $taskSource = Join-Path $taskStage $taskFile
    if (Test-Path -LiteralPath $taskDestination -PathType Leaf) {
        if ((Get-Item -LiteralPath $taskSource).Length -eq (Get-Item -LiteralPath $taskDestination).Length -and
            (Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash) { continue }
    }
    Copy-Item -LiteralPath $taskSource -Destination $taskDestination -Force
}
ConvertTo-Json -InputObject $taskFiles | Set-Content -LiteralPath $taskManifest -Encoding utf8
# The package directory stays stable so existing runtime/settings are reused.
$taskExe = Join-Path $taskRelease 'Avatools 3x.exe'
$taskShortcut = Join-Path $PSScriptRoot 'Avatools 3x.lnk'
$taskShell = New-Object -ComObject WScript.Shell
$taskLink = $taskShell.CreateShortcut($taskShortcut)
$taskLink.TargetPath = $taskExe
$taskLink.WorkingDirectory = $taskRelease
$taskLink.IconLocation = "$taskExe,0"
$taskLink.Description = 'Avatools 3x'
$taskLink.Save()
# Refresh only the changed app/shortcut entries, keeping Explorer running.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace AvatoolsBuild {
    public static class ShellIcons {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        public static extern void SHChangeNotify(int change, uint flags, string path, IntPtr unused);
    }
}
'@
foreach ($taskChangedIcon in @($taskExe, $taskShortcut, (Join-Path $taskRelease 'ui/assets/avatools.ico'))) {
    [AvatoolsBuild.ShellIcons]::SHChangeNotify(0x2000, 0x0005, $taskChangedIcon, [IntPtr]::Zero)
}
$taskOldShortcut = Join-Path $PSScriptRoot 'Avatar Fishing Bot.lnk'
if (Test-Path -LiteralPath $taskOldShortcut) { Remove-Item -LiteralPath $taskOldShortcut -Force }
Write-Host 'Mở Avatools 3x.lnk hoặc dist\AvatarFishingBot\Avatools 3x.exe. Giữ nguyên cả thư mục. runtime/debug được giữ khi build lại.'
$taskBuildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'build'))
if ($taskBuildRoot -ne ([IO.Path]::GetFullPath($PSScriptRoot) + '\build')) { throw 'Build cleanup path mismatch' }
Remove-Item -LiteralPath $taskBuildRoot -Recurse -Force
