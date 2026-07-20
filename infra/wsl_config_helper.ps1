# WSL 2 Resource Optimization Script
# Run this in PowerShell as Administrator before deploying SigNoz.
# This prevents ClickHouse from crashing with EOF errors during schema migration.

$wslConfigPath = "$env:USERPROFILE\.wslconfig"

if (-not (Test-Path $wslConfigPath)) {
    Write-Host "Creating .wslconfig at $wslConfigPath ..."
    @"
[wsl2]
memory=8GB
processors=4
"@ | Set-Content -Path $wslConfigPath
    Write-Host "Done. Restarting WSL to apply changes..."
    wsl --shutdown
    Write-Host "WSL restarted. You can now deploy SigNoz."
} else {
    Write-Host ".wslconfig already exists at $wslConfigPath"
    Write-Host "Current content:"
    Get-Content $wslConfigPath
    Write-Host ""
    $choice = Read-Host "Do you want to overwrite it? (y/n)"
    if ($choice -eq "y") {
        @"
[wsl2]
memory=8GB
processors=4
"@ | Set-Content -Path $wslConfigPath
        wsl --shutdown
        Write-Host "Overwritten and WSL restarted."
    } else {
        Write-Host "Skipped. Make sure your .wslconfig has enough memory (8GB+)."
    }
}
