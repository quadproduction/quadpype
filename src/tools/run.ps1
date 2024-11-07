$SCRIPT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent

# Execute the pre-run logic
$PRE_RUN_SCRIPT_PATH = Join-Path -Path $SCRIPT_DIR -ChildPath "pre_run.ps1"
Invoke-Expression "& '$PRE_RUN_SCRIPT_PATH' $args"

# Retrieve path to QuadPype dir
$PATH_QUADPYPE_PROJECT_DIR = [System.Environment]::GetEnvironmentVariable("QUADPYPE_PROJECT_DIR", "User")

# Make sure Poetry is in PATH
if (-not (Test-Path 'env:POETRY_HOME')) {
    $env:POETRY_HOME = "$PATH_QUADPYPE_PROJECT_DIR\.poetry"
}
$env:PATH = "$($env:PATH);$($env:POETRY_HOME)\bin"

Set-Location -Path $PATH_QUADPYPE_PROJECT_DIR

# Starting QuadPype
& "$($env:POETRY_HOME)\bin\poetry" run python "${PATH_QUADPYPE_PROJECT_DIR}\start.py" tray --debug
