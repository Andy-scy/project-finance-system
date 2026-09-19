# Push local repo to GitHub: check network -> create public repo via API
# (token read from Windows Credential Manager, never printed) -> push main.
# Run from repo root:  powershell -File scripts\push_to_github.ps1
$ErrorActionPreference = 'Stop'
$owner = 'Andy-scy'
$repo = 'project-finance-system'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host '[1/4] checking github.com connectivity...'
try {
    $r = Invoke-WebRequest -Uri 'https://github.com/' -UseBasicParsing -TimeoutSec 10
    Write-Host ('    github_http=' + $r.StatusCode)
} catch {
    Write-Host '[BLOCKED] github.com unreachable. Turn on your VPN/proxy and re-run.'
    exit 1
}

Write-Host '[2/4] reading stored GitHub credentials (token never printed)...'
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'git'
$psi.Arguments = 'credential fill'
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.UseShellExecute = $false
$p = [Diagnostics.Process]::Start($psi)
$p.StandardInput.WriteLine('protocol=https')
$p.StandardInput.WriteLine('host=github.com')
$p.StandardInput.WriteLine('')
$credOut = $p.StandardOutput.ReadToEnd()
$p.WaitForExit()
$token = ($credOut -split "`n" | Where-Object { $_ -like 'password=*' }) -replace '^password=', ''
$token = $token.Trim()
if (-not $token) { Write-Host '[ERROR] no stored GitHub credential found.'; exit 1 }
$headers = @{ Authorization = "token $token"; 'User-Agent' = $owner }

Write-Host '[3/4] ensuring public repo exists...'
$check = Invoke-WebRequest -Uri "https://api.github.com/repos/$owner/$repo" -Headers $headers -UseBasicParsing -TimeoutSec 20 -SkipHttpErrorCheck -ErrorAction SilentlyContinue
if ($check -and $check.StatusCode -eq 200) {
    Write-Host '    repo already exists, skip creation'
} else {
    $body = @{ name = $repo; private = $false; description = 'Local web app for project finance & contract management (FastAPI + SQLite + Vue3)' } | ConvertTo-Json
    $resp = Invoke-WebRequest -Uri 'https://api.github.com/user/repos' -Method POST -Headers $headers -Body $body -ContentType 'application/json' -UseBasicParsing -TimeoutSec 30 -SkipHttpErrorCheck
    if ($resp.StatusCode -in 201, 422) { Write-Host ('    repo created (http ' + $resp.StatusCode + ')') }
    else { Write-Host ('[ERROR] repo creation failed http ' + $resp.StatusCode + ': ' + $resp.Content.Substring(0, [Math]::Min(300, $resp.Content.Length))); exit 1 }
}

Write-Host '[4/4] pushing main branch...'
Set-Location $root
git push -u origin main 2>&1 | ForEach-Object { Write-Host "    $_" }
if ($LASTEXITCODE -ne 0) { Write-Host '[ERROR] push failed.'; exit 1 }
Write-Host "[OK] DONE. Repository: https://github.com/$owner/$repo"
