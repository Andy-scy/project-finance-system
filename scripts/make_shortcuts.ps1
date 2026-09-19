# Create autostart shortcut (Startup folder) + desktop URL shortcut.
# All names are built from Unicode code points to avoid encoding issues.
param(
    [Parameter(Mandatory=$true)][string]$ServerExe,
    [Parameter(Mandatory=$true)][string]$Root
)
$ErrorActionPreference = 'Stop'
# Trailing backslash from cmd args escapes the closing quote - sanitize here.
$Root = $Root.Trim().Trim('"').TrimEnd('\')
$ServerExe = $ServerExe.Trim().Trim('"')
function U { param($codes) -join ($codes | ForEach-Object { [char]$_ }) }

$sysName  = U @(0x9879,0x76EE,0x8D22,0x52A1,0x7CFB,0x7EDF)                  # "xiang mu cai wu xi tong"
$svcName  = $sysName + '-' + (U @(0x540E,0x53F0,0x670D,0x52A1)) + '.lnk'     # startup folder shortcut
$urlName  = $sysName + (U @(0x7BA1,0x7406)) + '.url'                         # desktop shortcut

$ws = New-Object -ComObject WScript.Shell

$startup = [Environment]::GetFolderPath('Startup')
$s = $ws.CreateShortcut((Join-Path $startup $svcName))
$s.TargetPath = $ServerExe
$s.Arguments = '"' + (Join-Path $Root 'app_server.py') + '"'
$s.WorkingDirectory = $Root
$s.WindowStyle = 7
$s.Save()

$desktop = [Environment]::GetFolderPath('Desktop')
$u = $ws.CreateShortcut((Join-Path $desktop $urlName))
$u.TargetPath = 'http://127.0.0.1:8000'
$u.Save()

$list = @((Join-Path $startup $svcName), (Join-Path $desktop $urlName))
$toolsDir = Join-Path $Root 'tools'
if (-not (Test-Path $toolsDir)) { New-Item -ItemType Directory -Path $toolsDir | Out-Null }
$list -join "`r`n" | Set-Content -Path (Join-Path $toolsDir 'shortcuts.txt') -Encoding Unicode
Write-Host ('STARTUP=' + $list[0])
Write-Host ('DESKTOP=' + $list[1])
Write-Host 'SHORTCUTS_OK'
