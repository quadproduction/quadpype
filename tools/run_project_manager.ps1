<#
.SYNOPSIS
  Helper script to run Project Manager.

.DESCRIPTION


.EXAMPLE

PS> .\run_project_manager.ps1

#>


$current_dir = Get-Location
$script_dir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$quadpype_root = (Get-Item $script_dir).parent.FullName

# Install PSWriteColor to support colorized output to terminal
$env:PSModulePath = $env:PSModulePath + ";$($quadpype_root)\tools\modules\powershell"

$env:_INSIDE_QUADPYPE_TOOL = "1"

# make sure Poetry is in PATH
if (-not (Test-Path 'env:POETRY_HOME')) {
    $env:POETRY_HOME = "$quadpype_root\.poetry"
}
$env:PATH = "$($env:PATH);$($env:POETRY_HOME)\bin"

Set-Location -Path $quadpype_root

Write-Color -Text ">>> ", "Reading Poetry ... " -Color Green, Gray -NoNewline
if (-not (Test-Path -PathType Container -Path "$($env:POETRY_HOME)\bin")) {
    Write-Color -Text "NOT FOUND" -Color Yellow
    Install-Poetry
    Write-Color -Text "INSTALLED" -Color Cyan
} else {
    Write-Color -Text "OK" -Color Green
}

& "$env:POETRY_HOME\bin\poetry" run python "$($quadpype_root)\start.py" projectmanager
Set-Location -Path $current_dir
