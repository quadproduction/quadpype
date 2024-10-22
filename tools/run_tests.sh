#!/usr/bin/env bash

# Run tests for QuadPype
# This will use virtual environment and pytest to run the tests

# Colors for terminal

RST='\033[0m'             # Text Reset

# Regular Colors
Black='\033[0;30m'        # Black
Red='\033[0;31m'          # Red
Green='\033[0;32m'        # Green
Yellow='\033[0;33m'       # Yellow
Blue='\033[0;34m'         # Blue
Purple='\033[0;35m'       # Purple
Cyan='\033[0;36m'         # Cyan
White='\033[0;37m'        # White

# Bold
BBlack='\033[1;30m'       # Black
BRed='\033[1;31m'         # Red
BGreen='\033[1;32m'       # Green
BYellow='\033[1;33m'      # Yellow
BBlue='\033[1;34m'        # Blue
BPurple='\033[1;35m'      # Purple
BCyan='\033[1;36m'        # Cyan
BWhite='\033[1;37m'       # White

# Bold High Intensity
BIBlack='\033[1;90m'      # Black
BIRed='\033[1;91m'        # Red
BIGreen='\033[1;92m'      # Green
BIYellow='\033[1;93m'     # Yellow
BIBlue='\033[1;94m'       # Blue
BIPurple='\033[1;95m'     # Purple
BICyan='\033[1;96m'       # Cyan
BIWhite='\033[1;97m'      # White

##############################################################################
# Clean pyc files in specified directory
# Globals:
#   None
# Arguments:
#   Optional path to clean
# Returns:
#   None
###############################################################################
clean_pyc () {
  local path
  path=$quadpype_root
  echo -e "${BIGreen}>>>${RST} Cleaning pyc at [ ${BIWhite}$path${RST} ] ... \c"
  find "$path" -path ./build -prune -o -regex '^.*\(__pycache__\|\.py[co]\)$' -delete
  echo -e "${BIGreen}DONE${RST}"
}

##############################################################################
# Return absolute path
# Globals:
#   None
# Arguments:
#   Path to resolve
# Returns:
#   None
###############################################################################
realpath () {
  echo $(cd $(dirname "$1"); pwd)/$(basename "$1")
}

# Main
main () {
  # Directories
  quadpype_root=$(realpath $(dirname $(dirname "${BASH_SOURCE[0]}")))

  _inside_quadpype_tool="1"

  if [[ -z $POETRY_HOME ]]; then
    export POETRY_HOME="$quadpype_root/.poetry"
  fi

  echo -e "${BIGreen}>>>${RST} Reading Poetry ... \c"
  if [ -f "$POETRY_HOME/bin/poetry" ]; then
    echo -e "${BIGreen}OK${RST}"
  else
    echo -e "${BIYellow}NOT FOUND${RST}"
    echo -e "${BIYellow}***${RST} We need to install Poetry and virtual env ..."
    . "$quadpype_root/tools/create_env.sh" || { echo -e "${BIRed}!!!${RST} Poetry installation failed"; return; }
  fi

  pushd "$quadpype_root" || return > /dev/null

  echo -e "${BIGreen}>>>${RST} Starting QuadPype tests ..."
  original_pythonpath=$PYTHONPATH
  export PYTHONPATH="$quadpype_root:$PYTHONPATH"
  "$POETRY_HOME/bin/poetry" run pytest -x --capture=sys --print -W ignore::DeprecationWarning "$quadpype_root/tests"
  PYTHONPATH=$original_pythonpath
}

main
