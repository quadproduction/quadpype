Param(
    [alias("y")][switch]$YES_TO_ALL=$false,
    [alias("r")][switch]$FETCH_PROJECTS=$false,
    [alias("m")][string]$MONGO_URI=""
)

$SCRIPT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent


function reset_db() {
    $RESET_DB_SCRIPT_PATH = Join-Path -Path (Split-Path $SCRIPT_DIR -Parent) -ChildPath "_lib\database\drop_databases.js"
    $RET_VAL = mongosh --file $RESET_DB_SCRIPT_PATH --quiet
    return $RET_VAL
}


function dump_mongo_settings($HOST_NAME, $PORT_NUM) {
    $TMP_FOLDER_PATH = Join-Path -Path $env:TEMP -ChildPath "mongo_dump\settings"
    if (!(Test-Path -Path $TMP_FOLDER_PATH)) {
        new-item $TMP_FOLDER_PATH -ItemType Directory > $null
    } else {
        Remove-Item "${TMP_FOLDER_PATH}\*" -Recurse -Force
    }
    $RET_VAL = mongodump --host="${HOST_NAME}" --port="${PORT_NUM}" --db=quadpype --collection=settings --out $TMP_FOLDER_PATH --quiet | mongorestore --host="localhost" --port="27017" --dir $TMP_FOLDER_PATH --drop --quiet --stopOnError
    return $RET_VAL
}


function dump_projects($HOST_NAME, $PORT_NUM) {
    $TMP_FOLDER_PATH = Join-Path -Path $env:TEMP -ChildPath "mongo_dump\projects"
    if (!(Test-Path -Path $TMP_FOLDER_PATH)) {
        new-item $TMP_FOLDER_PATH -ItemType Directory > $null
    } else {
        Remove-Item "${TMP_FOLDER_PATH}\*" -Recurse -Force
    }
    $RET_VAL = mongodump --host="${HOST_NAME}" --port="${PORT_NUM}" --db=avalon --out $TMP_FOLDER_PATH --quiet | mongorestore --host="localhost" --port="27017" --dir $TMP_FOLDER_PATH --drop --quiet --stopOnError
    return $RET_VAL
}


function disable_module($MODULE_NAME) {
    $DISABLE_MODULE_SCRIPT_PATH = Join-Path -Path (Split-Path $SCRIPT_DIR -Parent) -ChildPath "_lib\database\disable_module.js"
    $RET_VAL = mongosh --file $DISABLE_MODULE_SCRIPT_PATH --quiet --eval "var moduleName='$MODULE_NAME'"
    return $RET_VAL
}


function change_root_dir($ROOT_DIR) {
    if (!(Test-Path -Path $ROOT_DIR)) {
        new-item $ROOT_DIR -ItemType Directory > $null
    }

    $CHANGE_ROOT_DIR_SCRIPT_PATH = Join-Path -Path (Split-Path $SCRIPT_DIR -Parent) -ChildPath "_lib\database\change_root_directory.js"
    $RET_VAL = mongosh --file $CHANGE_ROOT_DIR_SCRIPT_PATH --eval "var rootDir='$ROOT_DIR'" --quiet
    return $RET_VAL
}


# Main
function main {
    write-output "Checking mongodump install ... "
    if (Get-Command mongodump -errorAction SilentlyContinue) {
        write-output "OK"
    } else {
        write-output "NOT FOUND"
        return 1
    }

    write-output "Checking mongorestore install ... "
    if (Get-Command mongorestore -errorAction SilentlyContinue) {
        write-output "OK"
    } else {
        write-output "NOT FOUND"
        return 1
    }

    write-output "Checking mongosh install ... "
    if (Get-Command mongosh -errorAction SilentlyContinue) {
        write-output "OK"
    } else {
        write-output "NOT FOUND"
        return 1
    }

    write-output "Checking docker install ... "
    if (Get-Command docker -errorAction SilentlyContinue) {
        write-output "OK"
    } else {
        write-output "NOT FOUND"
        return 1
    }

    write-output "Delete already existing local QuadPype MongoDB ... "
    $MONGO_DELETE_SCRIPT_PATH = Join-Path -Path $SCRIPT_DIR -ChildPath "local_database_delete.ps1"
    powershell $MONGO_DELETE_SCRIPT_PATH
    if ($?) {
        write-output "OK"
    }

    write-output "Start MongoDB docker instance ... "
    $MONGO_START_SCRIPT_PATH = Join-Path -Path $SCRIPT_DIR -ChildPath "local_database_start.ps1"
    powershell $MONGO_START_SCRIPT_PATH
    if ($?) {
        write-output "OK"
    } else {
        write-output "NOT FOUND"
        return 1
    }

    # Get the MongoDB to fetch and put in the localhost DB
    if (!$MONGO_URI) {
        $MONGO_URI = [System.Environment]::GetEnvironmentVariable("QUADPYPE_MONGO", [System.EnvironmentVariableTarget]::User)

        # In case YES_TO_ALL we skip asking and assume we can use the registered URI
        if (!$YES_TO_ALL -And $MONGO_URI) {
            $USER_CHOICE = (Read-Host -Prompt "Fetch from: ${MONGO_URI} ? (y/n) : ").ToLower()
            if (($USER_CHOICE -eq "n") -Or ($USER_CHOICE -eq "no")) {
                $MONGO_URI = ""
            } elseif (!($USER_CHOICE -eq "y") -And !($USER_CHOICE -eq "yes")) {
                write-output "Not recognized anwser, operation aborted."
                return 1
            }
        }
    }

    # No else statement since the previous if can clear the variable
    if (!$MONGO_URI) {
        $MONGO_URI = (Read-Host -Prompt "Enter the MongoDB URI (port included) : ").ToLower()
        if (!$MONGO_URI -Or !($MONGO_URI -match "(mongodb://)?[\w.-]+:\d{1,5}")) {
            write-output "The MongoDB connection URI seems invalid."
            write-output "The format should be like: mongodb://uri.to.my.mongo-db:27017"
            write-output "operation aborted."
            return 1
        }
    }

    # Split the URI
    $HOST_NAME, $PORT_NUM = $MONGO_URI -split ":", 2
    # Remove prefix if present
    $HOST_NAME = ($HOST_NAME -split "mongodb://")[-1]

    write-output "Resetting local db ..."
    if (!(reset_db)) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }

    write-output "Fetching QuadPype settings from : mongodb://${HOST_NAME}:${PORT_NUM} ... "
    if (!(dump_mongo_settings $HOST_NAME $PORT_NUM)) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }

    # Projects Fetching
    if ($YES_TO_ALL -Or $FETCH_PROJECTS) {
        $ALSO_FETCH_PROJECTS = $true
    } else {
        $ALSO_FETCH_PROJECTS = (Read-Host -Prompt "Do you also want to fetch projects ? (y/n) : ").ToLower()
        if (($ALSO_FETCH_PROJECTS -eq "y") -Or ($ALSO_FETCH_PROJECTS -eq "yes")) {
            $ALSO_FETCH_PROJECTS = $true
        } else {
            $ALSO_FETCH_PROJECTS = $false
        }
    }

    if ($ALSO_FETCH_PROJECTS) {
        write-output "Fetching QuadPype projects from : mongodb://${HOST_NAME}:${PORT_NUM} ... "
        if (!(dump_projects $HOST_NAME $PORT_NUM)) {
            write-output "OK"
        } else {
            write-output "FAILED"
            return 1
        }
    }

    $ROOT_DIR = Join-Path -Path $HOME -ChildPath "quad\projects\$CURR_STUDIO_NAME"
    write-output "Change Projets Settings Default RootDir to ${ROOT_DIR} ... "
    if (!(change_root_dir $ROOT_DIR)) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }

    write-output "Disable Sync Server ... "
    if (!(disable_module "sync_server")) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }

    write-output "Disable FTrack ... "
    if (!(disable_module "ftrack")) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }

    write-output "Disable Kitsu ... "
    if (!(disable_module "kitsu")) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }

    write-output "Your QuadPype local MongoDB connection string is mongodb://localhost:$PORT_NUM ..."
}


main
