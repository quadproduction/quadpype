<#
.SYNOPSIS
  Helper script to update QuadPype Sphinx sources.

.DESCRIPTION
  This script will run apidoc over QuadPype sources and generate new source rst
  files for documentation. Then it will run build_sphinx to create test html
  documentation build.

.EXAMPLE

PS> .\make_docs.ps1

#>

$current_dir = Get-Location
$script_dir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$quadpype_root = (Get-Item $script_dir).parent.FullName

$env:_INSIDE_QUADPYPE_TOOL = "1"

if (-not (Test-Path 'env:POETRY_HOME')) {
    $env:POETRY_HOME = "$quadpype_root\.poetry"
}

Set-Location -Path $quadpype_root

$current_dir = Get-Location
$script_dir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$quadpype_root = (Get-Item $script_dir).parent.FullName

# Install PSWriteColor to support colorized output to terminal
$env:PSModulePath = $env:PSModulePath + ";$($quadpype_root)\tools\modules\powershell"

Write-Color -Text ">>> ", "Reading Poetry ... " -Color Green, Gray -NoNewline
if (-not (Test-Path -PathType Container -Path "$($env:POETRY_HOME)\bin")) {
    Write-Color -Text "NOT FOUND" -Color Yellow
    Install-Poetry
    Write-Color -Text "INSTALLED" -Color Cyan
} else {
    Write-Color -Text "OK" -Color Green
}

Write-Color -Text "... ", "This will not overwrite existing source rst files, only scan and add new." -Color Yellow, Gray
Set-Location -Path $quadpype_root
Write-Color -Text ">>> ", "Running apidoc ..." -Color Green, Gray
& "$env:POETRY_HOME\bin\poetry" run sphinx-apidoc -M -e -d 10  --ext-intersphinx --ext-todo --ext-coverage --ext-viewcode -o "$($quadpype_root)\docs\source" igniter
& "$env:POETRY_HOME\bin\poetry" run sphinx-apidoc.exe -M -e -d 10 --ext-intersphinx --ext-todo --ext-coverage --ext-viewcode -o "$($quadpype_root)\docs\source" quadpype vendor, quadpype\vendor

Write-Color -Text ">>> ", "Building html ..." -Color Green, Gray
& "$env:POETRY_HOME\bin\poetry" run python "$($quadpype_root)\setup.py" build_sphinx
Set-Location -Path $current_dir
