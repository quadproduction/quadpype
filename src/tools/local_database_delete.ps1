$QUADPYPE_MONGO_CONTAINER_NAME = "quadpype-mongo-dev"

# Check if the docker container is running
# if yes stop (and kill to be sure it's stopped), then delete it
docker ps | findstr $QUADPYPE_MONGO_CONTAINER_NAME > $null
if ($? -eq $true) {
    docker stop $QUADPYPE_MONGO_CONTAINER_NAME | Out-Null
    docker kill $QUADPYPE_MONGO_CONTAINER_NAME | Out-Null
    docker rm $QUADPYPE_MONGO_CONTAINER_NAME | Out-Null
    return 0
}

# Check if the docker container exist and is not running, if delete it
docker ps -a | findstr $QUADPYPE_MONGO_CONTAINER_NAME > $null
if ($? -eq $true) {
    docker rm $QUADPYPE_MONGO_CONTAINER_NAME | Out-Null
    return 0
}
