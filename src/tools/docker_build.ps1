$PATH_ORIGINAL_LOCATION = Get-Location

$SCRIPT_DIR=Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_ROOT = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_ROOT -Leaf) -ne "src") {
    $PATH_QUADPYPE_ROOT = (get-item $PATH_QUADPYPE_ROOT).Parent.FullName
}


# Install PSWriteColor to support colorized output to terminal
$PATH_PS_VENDOR_DIR = "$($PATH_QUADPYPE_ROOT)\tools\vendor\powershell"
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


function Restore-Cwd() {
    $tmp_current_dir = Get-Location
    if ("$tmp_current_dir" -ne "$PATH_ORIGINAL_LOCATION") {
        Write-Color -Text ">>> ", "Restoring current directory" -Color Green, Gray
        Set-Location -Path $PATH_ORIGINAL_LOCATION
    }
}


function Get-Container {
    if (-not (Test-Path -PathType Leaf -Path "$($PATH_QUADPYPE_ROOT)\build\docker-image.id")) {
        Write-Color -Text "!!! ", "Docker command failed, cannot find image id." -Color Red, Yellow
        Restore-Cwd
        Exit-WithCode 1
    }
    $id = Get-Content "$($PATH_QUADPYPE_ROOT)\build\docker-image.id"
    Write-Color -Text ">>> ", "Creating container from image id ", "[", $id, "]" -Color Green, Gray, White, Cyan, White
    $cid = docker create $id bash
    if ($LASTEXITCODE -ne 0) {
        Write-Color -Text "!!! ", "Cannot create container." -Color Red, Yellow
        Restore-Cwd
        Exit-WithCode 1
    }
    return $cid
}


function Set-Cwd() {
    Set-Location -Path $PATH_QUADPYPE_ROOT
}


function New-DockerBuild {
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

    $startTime = [int][double]::Parse((Get-Date -UFormat %s))
    Write-Color -Text ">>> ", "Building QuadPype using Docker ..." -Color Green, Gray, White
    $variant = $args[0]
    if ($variant.Length -eq 0) {
        $variant = "debian"
        $dockerfile = "$($PATH_QUADPYPE_ROOT)\Dockerfile"
    } else {
        $dockerfile = "$($PATH_QUADPYPE_ROOT)\Dockerfile.$variant"
    }
    if (-not (Test-Path -PathType Leaf -Path $dockerfile)) {
        Write-Color -Text "!!! ", "Dockerfile for specifed platform ", "[", $variant, "]", "doesn't exist." -Color Red, Yellow, Cyan, White, Cyan, Yellow
        Restore-Cwd
        Exit-WithCode 1
    }
    Write-Color -Text ">>> ", "Using Dockerfile for ", "[ ", $variant, " ]" -Color Green, Gray, White, Cyan, White

    $build_dir = "$($PATH_QUADPYPE_ROOT)\build"
    if (-not(Test-Path $build_dir)) {
        New-Item -ItemType Directory -Path $build_dir
    }

    Write-Color -Text "--- ", "Cleaning build directory ..." -Color Yellow, Gray
    try {
        Remove-Item -Recurse -Force "$($build_dir)\*"
    } catch {
        Write-Color -Text "!!! ", "Cannot clean build directory, possibly because process is using it." -Color Red, Gray
        Write-Color -Text $_.Exception.Message -Color Red
        Exit-WithCode 1
    }

    Write-Color -Text ">>> ", "Running Docker build ..." -Color Green, Gray, White

    docker build --pull --iidfile $PATH_QUADPYPE_ROOT/build/docker-image.id --build-arg BUILD_DATE=$(Get-Date -UFormat %Y-%m-%dT%H:%M:%SZ) --build-arg VERSION=$QUADPYPE_VERSION -t quad/quadpype:$QUADPYPE_VERSION -f $dockerfile .
    if ($LASTEXITCODE -ne 0) {
        Write-Color -Text "!!! ", "Docker command failed.", $LASTEXITCODE -Color Red, Yellow, Red
        Restore-Cwd
        Exit-WithCode 1
    }

    Write-Color -Text ">>> ", "Copying build from container ..." -Color Green, Gray, White
    $cid = Get-Container

    docker cp "$($cid):/opt/quadpype/src/build/exe_quadpype" "$($PATH_QUADPYPE_ROOT)/build"
    docker cp "$($cid):/opt/quadpype/src/build/build.log" "$($PATH_QUADPYPE_ROOT)/build"

    $endTime = [int][double]::Parse((Get-Date -UFormat %s))

    Write-Color -Text "*** ", "All done in ", $($endTime - $startTime), " secs. You will find OpenPype and build log in ", "'.\build'", " directory." -Color Green, Gray, White, Gray, White, Gray
}

Set-Cwd
New-DockerBuild $ARGS
Restore-Cwd
