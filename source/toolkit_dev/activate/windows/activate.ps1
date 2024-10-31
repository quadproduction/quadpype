$SCRIPT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_DIR = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_DIR -Leaf) -ne "quadpype") {
    $PATH_QUADPYPE_DIR = (get-item $PATH_QUADPYPE_DIR).Parent.FullName
}

# Set the path to the QuadPype project in QUADPYPE_DIR
[System.Environment]::SetEnvironmentVariable("QUADPYPE_DIR", $PATH_QUADPYPE_DIR, [System.EnvironmentVariableTarget]::User)

# Install PSWriteColor to support colorized output to terminal
$PATH_PS_VENDOR_DIR = "$($PATH_QUADPYPE_DIR)\source\toolkit_dev\vendor\powershell"
if ($env:PSModulePath.IndexOf($PATH_PS_VENDOR_DIR) -Eq -1) {
    $env:PSModulePath += ";$($PATH_PS_VENDOR_DIR)"
}

function Exit-WithCode($exitcode) {
   # Only exit this host process if it's a child of another PowerShell parent process...
   $parentPID = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" | Select-Object -Property ParentProcessId).ParentProcessId
   $parentProcName = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$parentPID" | Select-Object -Property Name).Name
   if ('powershell.exe' -eq $parentProcName) { $host.SetShouldExit($exitcode) }

   exit $exitcode
}

# Check if the activate script exists
$PATH_ACTIVATE_SCRIPT=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath("$($PATH_QUADPYPE_DIR)\source\.venv\Scripts\activate.ps1")
if (!(Test-Path -Path $PATH_ACTIVATE_SCRIPT)) {
    Write-Color -Text "!!! ", "Cannot find the activate script, the virtual environment seems not installed." -Color Red, Yellow
    Write-Color -Text "!!! ", "You should execute the install_env.ps1 script." -Color Red, Yellow
    Exit-WithCode 1
}

# Ensure the Poetry variable is available in the current env
[System.Environment]::SetEnvironmentVariable("POETRY_HOME", "$PATH_QUADPYPE_DIR\source\.poetry", [System.EnvironmentVariableTarget]::User)

# Add poetry to the user Path if needed
$CURR_USER_PATH = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::User)
if ($CURR_USER_PATH.IndexOf("$($env:POETRY_HOME)\bin") -Eq -1) {
    [System.Environment]::SetEnvironmentVariable("Path", "$($CURR_USER_PATH)$([IO.Path]::PathSeparator)$($env:POETRY_HOME)\bin", [System.EnvironmentVariableTarget]::User)
}

# Execute the activate script in the current process
& $PATH_ACTIVATE_SCRIPT
