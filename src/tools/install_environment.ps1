$PATH_ORIGINAL_LOCATION = Get-Location

$SCRIPT_DIR=Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_PROJECT_DIR = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_PROJECT_DIR -Leaf) -ne "src") {
    $PATH_QUADPYPE_PROJECT_DIR = (get-item $PATH_QUADPYPE_PROJECT_DIR).Parent.FullName
}

$PATH_PYENV_DIR=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath("~\.pyenv")
$PATH_PYENV_BIN_DIR=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath("~\.pyenv\pyenv-win\")
$PATH_PYENV_INSTALL_FILE=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath("$SCRIPT_DIR\install-pyenv-win.ps1")

$CURR_USER_PATH = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::User)

# Add path to the source directory into the user PATH
if ($CURR_USER_PATH.IndexOf("$($PATH_QUADPYPE_PROJECT_DIR)$([IO.Path]::PathSeparator)") -Eq -1) {
    [System.Environment]::SetEnvironmentVariable("Path", "$($PATH_QUADPYPE_PROJECT_DIR)$([IO.Path]::PathSeparator)$($CURR_USER_PATH)", [System.EnvironmentVariableTarget]::User)
}

# 0. Install PSWriteColor to support colorized output to terminal
#################################################################
$PATH_PS_VENDOR_DIR = "$($SCRIPT_DIR)\vendor\powershell"
if ($env:PSModulePath.IndexOf($PATH_PS_VENDOR_DIR) -Eq -1) {
    $env:PSModulePath += ";$($PATH_PS_VENDOR_DIR)"
}


function Exit-WithCode($exitcode) {
   # Only exit this host process if it's a child of another PowerShell parent process...
   $parentPID = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" | Select-Object -Property ParentProcessId).ParentProcessId
   $parentProcName = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$parentPID" | Select-Object -Property Name).Name
   if ('powershell.exe' -eq $parentProcName) { $host.SetShouldExit($exitcode) }

   Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"

   exit $exitcode
}


# 1. Delete the PyEnv directory
###############################

if (Test-Path -Path $PATH_PYENV_DIR) {
    Remove-Item $PATH_PYENV_DIR -Recurse -Force
}

# 2. Save terminal encoding
#    Mandatory to work on Windows seesion with UTF-8 characters (like accents and foreign characters)
###########################

$PrevOutputEncoding = [console]::OutputEncoding
$PrevInputEncoding = [console]::InputEncoding

# 3. Install PyEnv, Python, and update PIP
##########################################

# 3.A Download PyEnv, Install PyEnv and clean downloaded file
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile $PATH_PYENV_INSTALL_FILE; & $PATH_PYENV_INSTALL_FILE
Remove-Item $PATH_PYENV_INSTALL_FILE -Recurse -Force

# 3.B Set the requiered environment variables related to PyEnv
[System.Environment]::SetEnvironmentVariable("PYENV", $PATH_PYENV_BIN_DIR, [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable("PYENV_ROOT", $PATH_PYENV_BIN_DIR, [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable("PYENV_HOME", $PATH_PYENV_BIN_DIR, [System.EnvironmentVariableTarget]::User)
if ($CURR_USER_PATH.IndexOf("$($PATH_PYENV_BIN_DIR)bin$([IO.Path]::PathSeparator)") -Eq -1) {
    [System.Environment]::SetEnvironmentVariable("Path", "$($PATH_PYENV_BIN_DIR)bin$([IO.Path]::PathSeparator)$($PATH_PYENV_BIN_DIR)shims$([IO.Path]::PathSeparator)$($CURR_USER_PATH)", [System.EnvironmentVariableTarget]::User)
}

# 3.C Enforce variables in current context
$env:PYENV = $PATH_PYENV_BIN_DIR
$env:PYENV_ROOT = $PATH_PYENV_BIN_DIR
$env:PYENV_HOME = $PATH_PYENV_BIN_DIR

# 3.D Ensure the VIRTUAL_ENV variable isn't present in the User env variables
[Environment]::SetEnvironmentVariable("VIRTUAL_ENV", $null, [System.EnvironmentVariableTarget]::User)

# 3.E Install the right Python version for the pipeline to run
pyenv install 3.9.13
pyenv global 3.9.13
pyenv local 3.9.13

# 3.F Update PIP for the pyenv Python
python3 -m pip install --upgrade --force-reinstall pip

# 4. Re-apply the previously saved terminal encoding
####################################################

[console]::OutputEncoding = $PrevOutputEncoding
[console]::InputEncoding = $PrevInputEncoding
$OutputEncoding = $PrevOutputEncoding

# 5. Create the virtual environment
###################################

# 5.A Set the current location to the QuadPype source directory
Set-Location -Path "$($PATH_QUADPYPE_PROJECT_DIR)"

# 5.B Check validity of the QuadPype version
$PATH_QUADPYPE_VERSION_FILE = "$($PATH_QUADPYPE_PROJECT_DIR)\quadpype\version.py"
$CONTENT_QUADPYPE_VERSION_FILE = Get-Content -Path $PATH_QUADPYPE_VERSION_FILE
$RESULT = [regex]::Matches($CONTENT_QUADPYPE_VERSION_FILE, '__version__ = "(?<version>\d+\.\d+.\d+.*)"')
$QUADPYPE_VERSION = $RESULT[0].Groups['version'].Value
if (-not $QUADPYPE_VERSION) {
  Write-Color -Text "!!! ", "Cannot determine QuadPype version." -Color Red, Yellow
  Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
  Exit-WithCode 1
}
Write-Color -Text ">>> ", "Found QuadPype version ", "[ ", $($QUADPYPE_VERSION), " ]" -Color Green, Gray, Cyan, White, Cyan

# 5.C Test if Python is properly installed and available
function Test-Python() {
    Write-Color -Text ">>> ", "Detecting host Python ... " -Color Green, Gray -NoNewline
    $PYTHON = "python"
    if (Get-Command "pyenv" -ErrorAction SilentlyContinue) {
        $PYENV_PYTHON = & pyenv which python
        if (Test-Path -PathType Leaf -Path "$($PYENV_PYTHON)") {
            $PYTHON = $PYENV_PYTHON
        }
    }
    if (-not (Get-Command $PYTHON -ErrorAction SilentlyContinue)) {
        Write-Color -Text "!!! ", "Python not detected." -Color Red, Yellow
        Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
        Exit-WithCode 1
    }
    $VERSION_COMMAND = "import sys; print('{0}.{1}'.format(sys.version_info[0], sys.version_info[1]))"

    $PYTHON_VERSION_STR = & $PYTHON -c $VERSION_COMMAND
    $env:PYTHON_VERSION = $PYTHON_VERSION_STR
    $MATCH_RESULT = $PYTHON_VERSION_STR -match '(\d+)\.(\d+)'
    if(-not $MATCH_RESULT) {
      Write-Color -Text "!!! ", "Cannot determine Python version." -Color Red, Yellow
      Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
      Exit-WithCode 1
    }

    # We are supporting python 3.9 only
    # Newer version is tolerated but at you own risks
    if (([int]$matches[1] -lt 3) -or ([int]$matches[2] -lt 9)) {
      Write-Color -Text "FAILED ", "Version ", "[", $PYTHON_VERSION_STR ,"]",  "is old and unsupported" -Color Red, Yellow, Cyan, White, Cyan, Yellow
      Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
      Exit-WithCode 1
    } elseif (([int]$matches[1] -eq 3) -and ([int]$matches[2] -gt 9)) {
        Write-Color -Text "WARNING Version ", "[",  $PYTHON_VERSION_STR, "]",  " is unsupported, use at your own risk." -Color Yellow, Cyan, White, Cyan, Yellow
        Write-Color -Text "*** ", "QuadPype supports only Python 3.9" -Color Yellow, White
    } else {
        Write-Color "OK ", "[",  $PYTHON_VERSION_STR, "]" -Color Green, Cyan, White, Cyan
    }
}

Test-Python

# 5.D Check if Poetry is installed, if not install it
Write-Color -Text ">>> ", "Check Poetry Installation ... " -Color Green, Gray -NoNewline

function Install-Poetry() {
    Write-Color -Text ">>> ", "Installing Poetry ... " -Color Green, Gray
    $PYTHON = "python"
    if (Get-Command "pyenv" -ErrorAction SilentlyContinue) {
        $PYTHON = Get-Command python | Select-Object -ExpandProperty Path
    }

    $env:POETRY_HOME="$($PATH_QUADPYPE_PROJECT_DIR)\.poetry"
    $env:POETRY_VERSION="1.3.2"
    (Invoke-WebRequest -Uri https://install.python-poetry.org/ -UseBasicParsing).Content | & $($PYTHON) -
}

if (!$env:POETRY_HOME -Or -not (Test-Path -PathType Container -Path "$($env:POETRY_HOME)\bin")) {
    Write-Color -Text "NOT FOUND" -Color Yellow
    Install-Poetry
    Write-Color -Text "INSTALLED" -Color Cyan
} else {
    Write-Color -Text "OK" -Color Green
}

# 5.E Install the project requirements specified in the Poetry file
if (-not (Test-Path -PathType Leaf -Path "$($PATH_QUADPYPE_PROJECT_DIR)\poetry.lock")) {
    Write-Color -Text ">>> ", "Installing virtual environment and creating lock." -Color Green, Gray
} else {
    Write-Color -Text ">>> ", "Installing virtual environment from lock." -Color Green, Gray
}

& "$env:POETRY_HOME\bin\poetry" install --no-root --ansi
if ($LASTEXITCODE -ne 0) {
    Write-Color -Text "!!! ", "Poetry command failed." -Color Red, Yellow
    Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
    Exit-WithCode 1
}

# 5.F Install the pre-commit hooks
Write-Color -Text ">>> ", "Installing pre-commit hooks ..." -Color Green, White
& "$env:POETRY_HOME\bin\poetry" run pre-commit install
if ($LASTEXITCODE -ne 0) {
    Write-Color -Text "!!! ", "Installation of pre-commit hooks failed." -Color Red, Yellow
    Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
    Exit-WithCode 1
}

Write-Color -Text ">>> ", "Virtual environment created." -Color Green, White

# 6. Ensure the virtual environment is activated
################################################
. "$($SCRIPT_DIR)\activate.ps1"

# 7 Update PIP for the Poetry Python
####################################
& "$env:POETRY_HOME\bin\poetry" run python -m pip install --upgrade --force-reinstall pip

# 8. Download and install all the required dependencies
#######################################################
& "$env:POETRY_HOME\bin\poetry" run python "$($SCRIPT_DIR)\_lib\install\install_additional_dependencies.py"

# 9. Set back the current location to the current script folder
###############################################################
Set-Location -Path "$($PATH_ORIGINAL_LOCATION)"
