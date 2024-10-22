<#
.SYNOPSIS
  Helper script to run Docusaurus for easy editing of QuadPype documentation.

.DESCRIPTION
  This script is using `yarn` package manager to run Docusaurus. If you don't
  have `yarn`, install Node.js (https://nodejs.org/) and then run:

  npm install -g yarn

  It take some time to run this script. If all is successful you should see
  new browser window with QuadPype documentation. All changes is markdown files
  under .\website should be immediately seen in browser.

.EXAMPLE

PS> .\run_documentation.ps1

#>


$script_dir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$quadpype_root = (Get-Item $script_dir).parent.FullName

Set-Location $quadpype_root/website

& yarn install
& yarn start
