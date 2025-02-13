#!/bin/bash

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

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")

# Execute the pre-run logic
PRE_RUN_SCRIPT_PATH="$SCRIPT_DIR/pre_run.sh"
. "$PRE_RUN_SCRIPT_PATH" $*

# Make sure Poetry is in PATH
export PATH="$PATH;${POETRY_HOME}/bin"

cd "${PATH_QUADPYPE_ROOT}"

# Starting QuadPype
"${POETRY_HOME}/bin/poetry" run python "${PATH_QUADPYPE_ROOT}/start.py" tray --debug
