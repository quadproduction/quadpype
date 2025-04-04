#!/usr/bin/env bash

# Colors for terminal
RST='\033[0m'             # Text Reset
BIRed='\033[1;91m'        # Red
BIGreen='\033[1;92m'      # Green
BIYellow='\033[1;93m'     # Yellow
BIWhite='\033[1;97m'      # White


realpath() (
  OURPWD=$PWD
  cd "$(dirname "$1")"
  LINK=$(readlink "$(basename "$1")")
  while [ "$LINK" ]; do
    cd "$(dirname "$LINK")"
    LINK=$(readlink "$(basename "$1")")
  done
  REALPATH="$PWD/$(basename "$1")"
  cd "$OURPWD"
  echo "$REALPATH"
)


get_container () {
  if [ ! -f "$PATH_QUADPYPE_ROOT/build/docker-image.id" ]; then
    echo -e "${BIRed}!!!${RST} Docker command failed, cannot find image id."
    exit 1
  fi
  local id=$(<"$PATH_QUADPYPE_ROOT/build/docker-image.id")
  echo -e "${BIYellow}---${RST} Creating container from $id ..."
  cid="$(docker create $id bash)"
  if [ $? -ne 0 ] ; then
    echo -e "${BIRed}!!!${RST} Cannot create container."
    exit 1
  fi
}


retrieve_build_log () {
  get_container
  echo -e "${BIYellow}***${RST} Copying build log to ${BIWhite}$PATH_QUADPYPE_ROOT/build/build.log${RST}"
  docker cp "$cid:/opt/quadpype/build/build.log" "$PATH_QUADPYPE_ROOT/build"
}


SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
PATH_QUADPYPE_ROOT=$SCRIPT_DIR
while [ "$(basename "$PATH_QUADPYPE_ROOT")" != "src" ]; do
  PATH_QUADPYPE_ROOT=$(dirname "$PATH_QUADPYPE_ROOT")
done

if [ -z $1 ]; then
    dockerfile="Dockerfile"
else
  dockerfile="Dockerfile.$1"
  if [ ! -f "$PATH_QUADPYPE_ROOT/$dockerfile" ]; then
    echo -e "${BIRed}!!!${RST} Dockerfile for specified platform ${BIWhite}$1${RST} doesn't exist."
    exit 1
  else
    echo -e "${BIGreen}>>>${RST} Using Dockerfile for ${BIWhite}$1${RST} ..."
  fi
fi

# Main
main () {
  pushd "$PATH_QUADPYPE_ROOT" > /dev/null || return > /dev/null

  echo -e "${BIYellow}---${RST} Cleaning build directory ..."
  rm -rf "$PATH_QUADPYPE_ROOT/build" && mkdir "$PATH_QUADPYPE_ROOT/build" > /dev/null

  local version_command="import os;exec(open(os.path.join('$PATH_QUADPYPE_ROOT', 'quadpype', 'version.py')).read());print(__version__);"
  local QUADPYPE_VERSION="$(python3 <<< ${version_command})"

  echo -e "${BIGreen}>>>${RST} Running Docker build ..."
  docker build --pull --iidfile $PATH_QUADPYPE_ROOT/build/docker-image.id --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') --build-arg VERSION=$QUADPYPE_VERSION -t quad/quadpype:$QUADPYPE_VERSION -f $dockerfile .
  if [ $? -ne 0 ] ; then
    echo $?
    echo -e "${BIRed}!!!${RST} Docker command failed."
    retrieve_build_log
    return 1
  fi

  echo -e "${BIGreen}>>>${RST} Copying build from container ..."
  get_container
  echo -e "${BIYellow}---${RST} Copying ..."
  docker cp "$cid:/opt/quadpype/src/build/exe_quadpype" "$PATH_QUADPYPE_ROOT/build"
  docker cp "$cid:/opt/quadpype/src/build/build.log" "$PATH_QUADPYPE_ROOT/build"
  if [ $? -ne 0 ] ; then
    echo -e "${BIRed}!!!${RST} Copying failed."
    return 1
  fi

  echo -e "${BIGreen}>>>${RST} Fixing user ownership ..."
  local username="$(logname)"
  chown -R $username ./build

  echo -e "${BIGreen}>>>${RST} All done, you can delete container:"
  echo -e "${BIYellow}$cid${RST}"
}

return_code=0
main || return_code=$?
exit $return_code
