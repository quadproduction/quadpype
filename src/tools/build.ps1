$PATH_ORIGINAL_LOCATION = Get-Location

$SCRIPT_DIR=Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_PROJECT_DIR = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_PROJECT_DIR -Leaf) -ne "src") {
    $PATH_QUADPYPE_PROJECT_DIR = (get-item $PATH_QUADPYPE_PROJECT_DIR).Parent.FullName
}

# Install PSWriteColor to support colorized output to terminal
$PATH_PS_VENDOR_DIR = "$($SCRIPT_DIR)\vendor\powershell"
if ($env:PSModulePath.IndexOf($PATH_PS_VENDOR_DIR) -Eq -1) {
    $env:PSModulePath += ";$($PATH_PS_VENDOR_DIR)"
}

$env:_INSIDE_QUADPYPE_TOOL = "1"

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
Set-Location -Path "$($PATH_QUADPYPE_PROJECT_DIR)"

if (-not (Test-Path 'env:POETRY_HOME')) {
    $env:POETRY_HOME = "$($PATH_QUADPYPE_PROJECT_DIR)\.poetry"
}

$PATH_VERSION_FILE = Get-Content -Path "$($PATH_QUADPYPE_PROJECT_DIR)\quadpype\version.py"
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

# Create build directory if not exist
if (-not (Test-Path -PathType Container -Path "$($PATH_QUADPYPE_PROJECT_DIR)\build")) {
    New-Item -ItemType Directory -Force -Path "$($PATH_QUADPYPE_PROJECT_DIR)\build"
}

Write-Color -Text ">>> ", "Cleaning build directory ... " -Color Green, Gray -NoNewline
try {
    Remove-Item -Recurse -Force "$($PATH_QUADPYPE_PROJECT_DIR)\build\*"
    Write-Color -Text "OK" -Color Green
}
catch {
    Write-Color -Text "!!! ", "Cannot clean build directory, possibly because another process is using it." -Color Red, Yellow
    Write-Color -Text $_.Exception.Message -Color Red
    Exit-WithCode 1
}

Write-Color -Text ">>> ", "Reading Poetry ... " -Color Green, Gray -NoNewline
if (-not (Test-Path -PathType Container -Path "$($env:POETRY_HOME)\bin")) {
    Write-Color -Text "NOT FOUND" -Color Yellow
    Write-Color -Text "*** ", "Dev environment seems not installed, starting the installation ..." -Color Yellow, Gray
    & "$($SCRIPT_DIR)\install_environment.ps1"
} else {
    Write-Color -Text "OK" -Color Green
}

Write-Color -Text ">>> ", "Cleaning cache files ... " -Color Green, Gray -NoNewline
Get-ChildItem "$($PATH_QUADPYPE_PROJECT_DIR)" -Filter "__pycache__" -Force -Recurse|  Where-Object {( $_.FullName -inotmatch '\\build\\' ) -and ( $_.FullName -inotmatch '\\.venv' )} | Remove-Item -Force -Recurse
Get-ChildItem "$($PATH_QUADPYPE_PROJECT_DIR)" -Filter "*.pyc" -Force -Recurse | Where-Object {( $_.FullName -inotmatch '\\build\\' ) -and ( $_.FullName -inotmatch '\\.venv' )} | Remove-Item -Force
Get-ChildItem "$($PATH_QUADPYPE_PROJECT_DIR)" -Filter "*.pyo" -Force -Recurse | Where-Object {( $_.FullName -inotmatch '\\build\\' ) -and ( $_.FullName -inotmatch '\\.venv' )} | Remove-Item -Force
Write-Color -Text "OK" -Color Green

Write-Color -Text ">>> ", "Building QuadPype ..." -Color Green, White
$INSTALL_START_TIME = [int][double]::Parse((Get-Date -UFormat %s))

$out = & "$($env:POETRY_HOME)\bin\poetry" run python setup.py build 2>&1
Set-Content -Path "$($PATH_QUADPYPE_PROJECT_DIR)\build\build.log" -Value $out

if ($LASTEXITCODE -ne 0) {
    Write-Color -Text "------------------------------------------" -Color Red
    Get-Content "$($PATH_QUADPYPE_PROJECT_DIR)\build\build.log"
    Write-Color -Text "------------------------------------------" -Color Yellow
    Write-Color -Text "!!! ", "Build failed. Check the log: ", ".\build\build.log" -Color Red, Yellow, White
    Exit-WithCode $LASTEXITCODE
}

& "$($env:POETRY_HOME)\bin\poetry" run python "$($SCRIPT_DIR)\_lib\build\build_dependencies.py"

# Set back the current location to the current script folder
Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"

$INSTALL_END_TIME = [int][double]::Parse((Get-Date -UFormat %s))
Write-Color -Text "*** ", "All done in ", $($INSTALL_END_TIME - $INSTALL_START_TIME), " secs. You will find the build and the log in the ", "'src\build\'", " directory." -Color Green, Gray, White, Gray, White, Gray
