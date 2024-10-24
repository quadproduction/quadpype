<#
.SYNOPSIS
  Download and extract third-party dependencies for QuadPype.

.DESCRIPTION
  This will download third-party dependencies specified in pyproject.toml
  and extract them to vendor/bin folder.

.EXAMPLE

PS> .\install_runtime_dependencies.ps1

#>
$current_dir = Get-Location
$script_dir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$quadpype_root = (Get-Item $script_dir).parent.FullName

# Install PSWriteColor to support colorized output to terminal
$env:PSModulePath = $env:PSModulePath + ";$($quadpype_root)\tools\modules\powershell"

$env:_INSIDE_QUADPYPE_TOOL = "1"

if (-not (Test-Path 'env:POETRY_HOME')) {
    $env:POETRY_HOME = "$quadpype_root\.poetry"
}

Set-Location -Path $quadpype_root

Write-Color -Text ">>> ", "Reading Poetry ... " -Color Green, Gray -NoNewline
if (-not (Test-Path -PathType Container -Path "$($env:POETRY_HOME)\bin")) {
    Write-Color -Text "NOT FOUND" -Color Yellow
    Write-Color -Text "*** ", "We need to install Poetry create virtual env first ..." -Color Yellow, Gray
    & "$quadpype_root\tools\create_env.ps1"
} else {
    Write-Color -Text "OK" -Color Green
}
Write-Color -Text ">>> ", "Installing Additional Dependencies ..." -Color Green, Gray
$startTime = [int][double]::Parse((Get-Date -UFormat %s))
& "$($env:POETRY_HOME)\bin\poetry" run python "$($quadpype_root)\tools\install_additional_dependencies.py"
$endTime = [int][double]::Parse((Get-Date -UFormat %s))
Set-Location -Path $current_dir
try
{
    New-BurntToastNotification -AppLogo "$quadpype_root/quadpype/resources/icons/quadpype_icon_default.png" -Text "QuadPype", "Dependencies downloaded", "All done in $( $endTime - $startTime ) secs."
} catch {}
