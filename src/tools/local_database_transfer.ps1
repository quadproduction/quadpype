$SCRIPT_DIR = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent

function migrate_settings() {
    $MIGRATE_DB_SCRIPT_PATH = Join-Path -Path (Split-Path $SCRIPT_DIR -Parent) -ChildPath "tools\_lib\database\transfer_settings.js"
    $MIGRATE_VAL = mongosh --file $MIGRATE_DB_SCRIPT_PATH --quiet
    return $MIGRATE_VAL
}

function main
{
    # Get the MongoDB to fetch and put in the localhost DB
    if (!$MONGO_URI) {
        $MONGO_URI = [System.Environment]::GetEnvironmentVariable("QUADPYPE_MONGO", [System.EnvironmentVariableTarget]::User)

        # In case YES_TO_ALL we skip asking and assume we can use the registered URI
        if (!$YES_TO_ALL -And $MONGO_URI) {
            $USER_CHOICE = (Read-Host -Prompt "Fetch from: ${MONGO_URI} ? (y/n) ").ToLower()
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

    write-output "Transfer Settings & Projects: ${HOST_NAME}:${PORT_NUM} ... "
    if (migrate_settings) {
        write-output "OK"
    } else {
        write-output "FAILED"
        return 1
    }
}

main
