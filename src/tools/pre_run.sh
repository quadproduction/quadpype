#!/bin/bash

DEV=false
PROD=false
MONGO_URI=""

while getopts "dpm:" opt
do
  case "$opt" in
    d ) DEV=true ;;
    p ) PROD=true ;;
    m ) MONGO_URI="$OPTARG" ;;
    * ) return 1
  esac
done

_INSIDE_QUADPYPE_TOOL="1"

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
PATH_QUADPYPE_ROOT=$SCRIPT_DIR
while [ "$(basename "$PATH_QUADPYPE_ROOT")" != "src" ]; do
  PATH_QUADPYPE_ROOT=$(dirname "$PATH_QUADPYPE_ROOT")
done

if [ "$DEV" = true ]; then
  QUADPYPE_MONGO="mongodb://localhost:27017"
elif [ "$MONGO_URI" ]; then
  QUADPYPE_MONGO="$MONGO_URI"
elif [ "$PROD" = true ]; then
  QUADPYPE_MONGO="IGNORED"
fi

if [ "$QUADPYPE_MONGO" = "" ]; then
  echo "The MongoDB Connection String isn't set in the user environment variables or passed with -m check usage."
  return 1
fi

echo >> ~/.bashrc
echo >> ~/.zshrc
if [ "$QUADPYPE_MONGO" != "IGNORED" ]; then
  export QUADPYPE_MONGO
  echo "export QUADPYPE_MONGO=\"${QUADPYPE_MONGO}\"" >> ~/.bashrc
  echo "export QUADPYPE_MONGO=\"${QUADPYPE_MONGO}\"" >> ~/.zshrc
else
  sed -i '/^export QUADPYPE_MONGO=/d' ~/.bashrc
  sed -i '/^export QUADPYPE_MONGO=/d' ~/.zshrc
fi

export QUADPYPE_ROOT="$PATH_QUADPYPE_ROOT"
echo "export QUADPYPE_ROOT=\"${PATH_QUADPYPE_ROOT}\"" >> ~/.bashrc
echo "export QUADPYPE_ROOT=\"${PATH_QUADPYPE_ROOT}\"" >> ~/.zshrc
export PYENV_ROOT=~\.pyenv
echo "export PYENV_ROOT=\"${PYENV_ROOT}\"" >> ~/.bashrc
echo "export PYENV_ROOT=\"${PYENV_ROOT}\"" >> ~/.zshrc

# Save the environments variables to a file
# Needed to ensure these will be used directly without restarting the terminal
PATH_ADDITIONAL_ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "${PATH_ADDITIONAL_ENV_FILE}" ]; then
  rm -f "${PATH_ADDITIONAL_ENV_FILE}"
fi

ENV_FILE_CONTENT=""

if [ "$QUADPYPE_MONGO" != "IGNORED" ]; then
  ENV_FILE_CONTENT="QUADPYPE_MONGO=$QUADPYPE_MONGO\n"
fi

ENV_FILE_CONTENT+="QUADPYPE_ROOT=$PATH_QUADPYPE_ROOT\n"

echo "$ENV_FILE_CONTENT" >> "${PATH_ADDITIONAL_ENV_FILE}"

# Launch the activate script
. "${SCRIPT_DIR}/activate.sh"

# For dev usage, ensuring the db is running, else start it properly
if [ "$DEV" = true ]; then
  echo "TODO: Local DB code is not done yet for macOS"
fi
