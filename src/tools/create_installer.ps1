<#
.SYNOPSIS
  Helper script to build QuadPype Installer.

.DESCRIPTION
  This script will use already built QuadPype (in `build` directory) and
  create Windows installer from it using Inno Setup (https://jrsoftware.org/)

.EXAMPLE

PS> .\build_win_installer.ps1

#>
$PATH_ORIGINAL_LOCATION = Get-Location

$SCRIPT_DIR=Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_ROOT = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_ROOT -Leaf) -ne "src") {
    $PATH_QUADPYPE_ROOT = (get-item $PATH_QUADPYPE_ROOT).Parent.FullName
}

# Install PSWriteColor to support colorized output to terminal
$PATH_PS_VENDOR_DIR = "$($SCRIPT_DIR)\vendor\powershell"
if ($env:PSModulePath.IndexOf($PATH_PS_VENDOR_DIR) -Eq -1) {
    $env:PSModulePath += ";$($PATH_PS_VENDOR_DIR)"
}

function Start-Progress {
    param([ScriptBlock]$code)
    $scroll = "/-\|/-\|"
    $idx = 0
    $job = Invoke-Command -ComputerName $env:ComputerName -ScriptBlock { $code } -AsJob

    $origpos = $host.UI.RawUI.CursorPosition

    # $origpos.Y -= 1

    while (($job.State -eq "Running") -and ($job.State -ne "NotStarted")) {
        $host.UI.RawUI.CursorPosition = $origpos
        Write-Host $scroll[$idx] -NoNewline
        $idx++
        if ($idx -ge $scroll.Length) {
            $idx = 0
        }
        Start-Sleep -Milliseconds 100
    }
    # It's over - clear the activity indicator.
    $host.UI.RawUI.CursorPosition = $origpos
    Write-Host ' '
  <#
  .SYNOPSIS
  Display spinner for running job
  .PARAMETER code
  Job to display spinner for
  #>
}


function Exit-WithCode($exitcode) {
   # Only exit this host process if it's a child of another PowerShell parent process...
   $parentPID = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" | Select-Object -Property ParentProcessId).ParentProcessId
   $parentProcName = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$parentPID" | Select-Object -Property Name).Name
   if ('powershell.exe' -eq $parentProcName) { $host.SetShouldExit($exitcode) }

   Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"

   exit $exitcode
}


# Set the current location to the QuadPype source directory
Set-Location -Path "$($PATH_QUADPYPE_ROOT)"


$PATH_VERSION_FILE = Get-Content -Path "$($PATH_QUADPYPE_ROOT)\quadpype\version.py"
$MATCH_OBJ = [regex]::Matches($PATH_VERSION_FILE, '__version__ = "(?<version>\d+\.\d+.\d+.*)"')
$QUADPYPE_VERSION = $null

if ($MATCH_OBJ) {
    $QUADPYPE_VERSION = $MATCH_OBJ[0].Groups['version'].Value
}

if (-not $QUADPYPE_VERSION) {
    Write-Color -Text "!!! ", "Cannot determine QuadPype version." -Color Yellow, Gray
    Exit-WithCode 1
}

Write-Color -Text ">>> ", "QuadPype [ ", $QUADPYPE_VERSION, " ]" -Color Green, White, Cyan, White
$env:BUILD_VERSION = $QUADPYPE_VERSION

Write-Color -Text ">>> ", "Creating QuadPype installer ... " -Color Green, White

$QUADPYPE_BUILD_DIR = "$($PATH_QUADPYPE_ROOT)\build\exe_quadpype"
if (-not (Test-Path -PathType Container -Path "$($QUADPYPE_BUILD_DIR)")) {
    Write-Color -Text "!!! ", "Cannot find the build folder named ", "exe-quadpype" -Color Red, Yellow, White
    Write-Color -Text "!!! ", "Ensure you properly called the build script ", ".\tools\build.ps1" -Color Red, Yellow, White
    Exit-WithCode 1
}

Write-Color -Text "--- ", "Build directory ", "${build_dir}" -Color Green, Gray, White
$env:BUILD_DIR = "$QUADPYPE_BUILD_DIR"

if (-not (Get-Command iscc -errorAction SilentlyContinue -ErrorVariable ProcessError)) {
    Write-Color -Text "!!! ", "Cannot find Inno Setup command" -Color Red, Yellow
    Write-Color -Text "!!! ", "You can download it at ", "https://jrsoftware.org/" -Color Red, Yellow, White
    Exit-WithCode 1
}

& iscc "$PATH_QUADPYPE_ROOT\inno_setup.iss"

if ($LASTEXITCODE -ne 0) {
    Write-Color -Text "!!! ", "Creating installer failed." -Color Red, Yellow
    Exit-WithCode 1
}

# Set back the current location to the current script folder
Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"

Write-Color -Text "*** ", "All done. You will find the installer in ", "'src\build'", " directory." -Color Green, Gray, White, Gray
