function Generate-Checksums($folder_to_parse, $checksum_file) {
    # Get all the files in the folder and its subfolders
    $files = Get-ChildItem -Path $folder_to_parse -Recurse -File
    $output_lines = @()
    foreach ($file in $files)
    {
        # Get hash file
        $hash = Get-FileHash -Path $file.FullName -Algorithm SHA256
        # Get the relative path
        $relative_path = $file.FullName -replace [regex]::Escape($folder_to_parse), ""
        # Format checksum and file path
        $output = "$($hash.Hash):$relative_path"
        $output_lines += $output
    }
    # Write the output lines to the checksums file
    $output_lines | Out-File -FilePath $checksum_file -Encoding ASCII
    Write-Host "Checksums Written to $checksum_file"
}

function Compare-Checksums($folder_to_compare, $checksum_file) {
    # Build checksum array<filepath:hash>
    $checksums_dict = @{}
    Get-Content -Path $checksum_file | ForEach-Object {
        $parts = $_ -split ":"
        $hash = $parts[0]
        $filePath = $parts[1]
        $checksums_dict[$filePath] = $hash
    }
    # Boolean Validator
    $checksum_valid = $true
    $files = Get-ChildItem -Path $folder_to_compare -Recurse -File
    foreach ($file in $files)
    {
        $file_hash = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash
        $relative_path = $file.FullName -replace [regex]::Escape($folder_to_compare), ""
        # Check if the file exists in the saved checksums
        if ($checksums_dict.ContainsKey($relative_path))
        {
            if ($file_hash -ne $checksums_dict[$relative_path])
            {
                Write-Host "Changes have been detected for file: $folder_to_compare$relative_path"
                $checksum_valid = $false
            }
            # Indicate that this file has been found and checked
            # To do that we clear the hash value of that file
            $checksums_dict[$relative_path] = ""
        } else {
            Write-Host "New file detected: $folder_to_compare$relative_path"
            $checksum_valid = $false
        }
    }

    # Check for missing file(s)
    foreach ($file in $checksums_dict.GetEnumerator()) {
        if ($file.Value -ne "") {
            # Missing file
            Write-Host "Missing file: $folder_to_compare$($file.Key)"
            $checksum_valid = $false
        }
    }

    return $checksum_valid
}

$SCRIPT_DIR=Split-Path -Path $MyInvocation.MyCommand.Definition -Parent -Resolve
$PATH_QUADPYPE_PROJECT_DIR = $SCRIPT_DIR
while ((Split-Path $PATH_QUADPYPE_PROJECT_DIR -Leaf) -ne "src") {
    $PATH_QUADPYPE_PROJECT_DIR = (get-item $PATH_QUADPYPE_PROJECT_DIR).Parent.FullName
}

$PATH_ZXP_SIGN_SOFTWARE="$($SCRIPT_DIR)\vendor\zxp_sign_cmd\windows\win64\ZXPSignCmd.exe"
$PATH_ZXP_CERTIFICATE="$($SCRIPT_DIR)\_lib\zxp\sign_certificate.p12"

# Launch the activate script
. "$($SCRIPT_DIR)\activate.ps1"

# Generate the ZXP (if necessary)
$HOSTS="aftereffects","photoshop"
foreach ($CURR_HOST in $HOSTS) {
    $HOST_PATH="$($PATH_QUADPYPE_PROJECT_DIR)\quadpype\hosts\$CURR_HOST"
    $HOST_ZXP_SOURCE="$($HOST_PATH)\api\extension\"
    $HOST_ZXP_CHECKSUMS="$($HOST_PATH)\api\checksums"
    $HOST_ZXP_DEST="$($HOST_PATH)\api\extension.zxp"
    $HOST_ZXP_XML = $(Get-ChildItem -Path $HOST_ZXP_SOURCE -Filter *.xml -Recurse).FullName

    # Checksum file not found, generate one
    if (!(Test-Path "$($HOST_ZXP_CHECKSUMS)")){
        Write-Host "Checksum doesn't exist, creating it for host : $CURR_HOST"
        Generate-Checksums $HOST_ZXP_SOURCE $HOST_ZXP_CHECKSUMS
        # Since there wasn't yet a checksum we have nothing to compare against
        Write-Host "skipping ZXP generation"
        continue
    }

    $is_checksum_valid = Compare-Checksums $HOST_ZXP_SOURCE $HOST_ZXP_CHECKSUMS
    if ($is_checksum_valid){
         Write-Host "No change detected, skipping ZXP generation for host : $CURR_HOST"
         continue
    }

    Write-Host "Generating ZXP for $CURR_HOST, destination: $HOST_ZXP_DEST"

    # First delete previous ZXP file (if exists)
    if (Test-Path $HOST_ZXP_DEST) {
        Remove-Item $HOST_ZXP_DEST -Force
    }

    # Bump XML version
    & "$($env:POETRY_HOME)\bin\poetry" run python "$($SCRIPT_DIR)\_lib\zxp\bump_xmp_version.py" --xml-filepath $HOST_ZXP_XML

    # Generate and sign the ZXP file with the QuadPype certificate
    & $PATH_ZXP_SIGN_SOFTWARE -sign $HOST_ZXP_SOURCE $HOST_ZXP_DEST $PATH_ZXP_CERTIFICATE QuadPype

    # Generate new checksum
    Generate-Checksums $HOST_ZXP_SOURCE $HOST_ZXP_CHECKSUMS
}
