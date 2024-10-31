Param(
    [alias("d")][switch]$DEV=$false,
    [alias("m")][string]$MONGO_URI=""
)

$env:_INSIDE_QUADPYPE_TOOL = "1"

$SCRIPT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_PROJECT_DIR = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_PROJECT_DIR -Leaf) -ne "src") {
    $PATH_QUADPYPE_PROJECT_DIR = (get-item $PATH_QUADPYPE_PROJECT_DIR).Parent.FullName
}

if ($DEV) {
    $QUADPYPE_MONGO = "mongodb://localhost:27017"
} elseif ($MONGO_URI) {
    $QUADPYPE_MONGO = $MONGO_URI
} else {
    $QUADPYPE_MONGO = [System.Environment]::GetEnvironmentVariable("QUADPYPE_MONGO", [System.EnvironmentVariableTarget]::User)
}

if (($QUADPYPE_MONGO -eq "")) {
	write-output "The MongoDB Connection String isn't set in the user environment variables or passed with --mongo-uri (-m) check usage."
    exit 1
} elseIf (!(Test-Path -Path "$PATH_QUADPYPE_PROJECT_DIR")) {
    write-output "The value passed in --path-quadpype (-p) doesnt point to a valid existing directory."
    exit 1
}

[System.Environment]::SetEnvironmentVariable("QUADPYPE_MONGO", $QUADPYPE_MONGO, [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable("QUADPYPE_PROJECT_DIR", $PATH_QUADPYPE_PROJECT_DIR, [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable("PYENV_ROOT", (Resolve-Path -Path "~\.pyenv"), [System.EnvironmentVariableTarget]::User)

# Save the environments variables to a file
# Needed to ensure these will be used directly without restarting the terminal
$PATH_ADDITIONAL_ENV_FILE = "$((get-item $SCRIPT_DIR).Parent.FullName)\.env"

if (Test-Path -Path $PATH_ADDITIONAL_ENV_FILE) {
    Remove-Item $PATH_ADDITIONAL_ENV_FILE -Force -ErrorAction SilentlyContinue | Out-Null
}

New-Item "$($PATH_ADDITIONAL_ENV_FILE)" -ItemType File -Value "QUADPYPE_MONGO=$QUADPYPE_MONGO$([Environment]::NewLine)QUADPYPE_PROJECT_DIR=$PATH_QUADPYPE_PROJECT_DIR$([Environment]::NewLine)QUADPYPE_ROOT=$PATH_QUADPYPE_PROJECT_DIR\quadpype" | Out-Null


# Launch the activate script
. "$($SCRIPT_DIR)\activate.ps1"

# For dev usage, ensuring the db is running, else start it properly
if ($DEV) {
    $MONGO_START_SCRIPT_PATH = "$($SCRIPT_DIR)\local_database_start.ps1"
    Invoke-Expression "& '$MONGO_START_SCRIPT_PATH'"
}
