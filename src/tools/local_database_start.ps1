﻿$QUADPYPE_MONGO_CONTAINER_NAME = "quadpype-mongo-dev"
$QUADPYPE_MONGO_CONTAINER_PORT = 27017

# Check if the docker container is already running
docker ps | findstr $QUADPYPE_MONGO_CONTAINER_NAME > $null
if ($? -eq $true) {
    return 0
}

# Check if the docker container exist and is not running, if yes run it
docker ps -a | findstr $QUADPYPE_MONGO_CONTAINER_NAME > $null
if ($? -eq $true) {
    docker start $QUADPYPE_MONGO_CONTAINER_NAME
    return 0
}

# Check if there is already a Docker container using the required port
docker ps -a | findstr $QUADPYPE_MONGO_CONTAINER_PORT > $null
if ($? -eq $true) {
    write-output "Port 27017 is already used by Docker, operation aborted."
    return 1
}

# Check if there is already a process using the required port
$PORT_TCP_CONNECTION = Get-NetTCPConnection | Where-Object Localport -eq 27017
if ($PORT_TCP_CONNECTION) {
    $OWNING_PROCESS_NAME = (Get-Process -Id $PORT_TCP_CONNECTION.OwningProcess).Name
    write-output "Port 27017 is already used by $OWNING_PROCESS_NAME, operation aborted."
    return 1
}

docker run -p "${QUADPYPE_MONGO_CONTAINER_PORT}:${QUADPYPE_MONGO_CONTAINER_PORT}" --name $QUADPYPE_MONGO_CONTAINER_NAME -d mongo > $null