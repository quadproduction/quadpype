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

$env:_INSIDE_QUADPYPE_TOOL = "1"


function Exit-WithCode($exitcode) {
   # Only exit this host process if it's a child of another PowerShell parent process...
   $parentPID = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" | Select-Object -Property ParentProcessId).ParentProcessId
   $parentProcName = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$parentPID" | Select-Object -Property Name).Name
   if ('powershell.exe' -eq $parentProcName) { $host.SetShouldExit($exitcode) }

   Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"

   exit $exitcode
}


if (-not (Test-Path 'env:POETRY_HOME')) {
    $env:POETRY_HOME = "$quadpype_root\.poetry"
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


Write-Color -Text ">>> ", "Reading Poetry ... " -Color Green, Gray -NoNewline
if (-not (Test-Path -PathType Container -Path "$($env:POETRY_HOME)\bin")) {
    Write-Color -Text "NOT FOUND" -Color Yellow
    Write-Color -Text "*** ", "Dev environment seems not installed, starting the installation ..." -Color Yellow, Gray
    & "$($SCRIPT_DIR)\install_environment.ps1"
} else {
    Write-Color -Text "OK" -Color Green
}

Write-Color -Text ">>> ", "Checking ZXP files (Updating them if necessary) ..." -Color Green, Gray
& "$($SCRIPT_DIR)\generate_zxp.ps1"

Write-Color -Text ">>> ", "Cleaning cache files ... " -Color Green, Gray -NoNewline
Get-ChildItem "$($PATH_QUADPYPE_ROOT)" -Filter "__pycache__" -Force -Recurse|  Where-Object {( $_.FullName -inotmatch '\\build\\' ) -and ( $_.FullName -inotmatch '\\.venv' )} | Remove-Item -Force -Recurse
Get-ChildItem "$($PATH_QUADPYPE_ROOT)" -Filter "*.pyc" -Force -Recurse | Where-Object {( $_.FullName -inotmatch '\\build\\' ) -and ( $_.FullName -inotmatch '\\.venv' )} | Remove-Item -Force
Get-ChildItem "$($PATH_QUADPYPE_ROOT)" -Filter "*.pyo" -Force -Recurse | Where-Object {( $_.FullName -inotmatch '\\build\\' ) -and ( $_.FullName -inotmatch '\\.venv' )} | Remove-Item -Force
Write-Color -Text "OK" -Color Green

# Launch the activate script
. "$($SCRIPT_DIR)\activate.ps1"

Write-Color -Text ">>> ", "Generating patch zip archive from current sources ..." -Color Green, Gray

& "$($env:POETRY_HOME)\bin\poetry" run python "$($SCRIPT_DIR)\_lib\build\create_patch_version.py" $ARGS

# Set back the current location to the current script folder
Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
