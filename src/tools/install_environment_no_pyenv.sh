#!/bin/bash

PATH_ORIGINAL_LOCATION=$(pwd)

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
PATH_QUADPYPE_ROOT=$SCRIPT_DIR
while [ "$(basename "$PATH_QUADPYPE_ROOT")" != "src" ]; do
  PATH_QUADPYPE_ROOT=$(dirname "$PATH_QUADPYPE_ROOT")
done

# Add path to the source directory into the user PATH
if [[ ":$PATH:" != *":$PATH_QUADPYPE_ROOT:"* ]]; then
  export PATH="$PATH_QUADPYPE_ROOT:$PATH"
fi

ping_google() {
  ping -q -c1 google.com &>/dev/null && return 0 || return 1
}
ping_google

if [ $? -ne 0 ]; then
  echo "No Internet connection, aborting."
  exit 1
fi

# 0. Install PyEnv, Python, and update PIP
##########################################


# 1.C Ensure the VIRTUAL_ENV variable isn't present in the User env variables
unset VIRTUAL_ENV

# 1.D Install the right Python version for the pipeline to run

# 1.E Update PIP for the pyenv Python
python3 -m pip install --upgrade --force-reinstall pip

# 2. Re-apply the previously saved terminal encoding
####################################################
# 2.A Set the current location to the QuadPype source directory
cd "$PATH_QUADPYPE_ROOT" || return > /dev/null

# 2.B Check validity of the QuadPype version
PATH_QUADPYPE_VERSION_FILE="$PATH_QUADPYPE_ROOT/quadpype/version.py"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  QUADPYPE_VERSION=$(grep -Po '(?<=__version__ = ")[^"]+' "$PATH_QUADPYPE_VERSION_FILE")
elif [[ "$OSTYPE" == "darwin"* ]]; then
  QUADPYPE_VERSION=$(perl -nle'print for m{(?<=__version__ = ")[^"]+}g' $PATH_QUADPYPE_VERSION_FILE)
fi

if [[ -z "$QUADPYPE_VERSION" ]]; then
  echo "Cannot determine QuadPype version. Aborting."
  exit 1
fi
echo ">>> Found QuadPype version [ $QUADPYPE_VERSION ]"

# 2.C Test if Python is properly installed and available
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')")
if [[ ! "$PYTHON_VERSION" =~ 3\.9 ]]; then
  echo "Python version $PYTHON_VERSION is unsupported. Aborting."
  exit 1
fi
echo ">>> Python version OK [ $PYTHON_VERSION ]"

# 2.D Clear and re-install Poetry
echo ">>> Installing Poetry ..."
export POETRY_HOME="$PATH_QUADPYPE_ROOT/.poetry"
export POETRY_VERSION="1.8.4"
rm -rf "$POETRY_HOME"
curl -sSL https://install.python-poetry.org | POETRY_HOME="$PATH_QUADPYPE_ROOT/.poetry" python -

# 2.E Remove the potentially existing .venv
rm -rf "$PATH_QUADPYPE_ROOT/.venv"

# 2.F Install the project requirements specified in the Poetry file
if [[ ! -f "$PATH_QUADPYPE_ROOT/poetry.lock" ]]; then
  echo ">>> Installing virtual environment and creating lock."
else
  echo ">>> Installing virtual environment from lock."
fi
"$POETRY_HOME/bin/poetry" install --no-root --ansi
if [[ $? -ne 0 ]]; then
  echo "Poetry command failed. Aborting."
  exit 1
fi

# 3. Install the git pre-commit hooks
#####################################
echo ">>> Installing pre-commit hooks ..."
"$POETRY_HOME/bin/poetry" run pre-commit install
if [[ $? -ne 0 ]]; then
  echo "Installation of pre-commit hooks failed. Aborting."
  exit 1
fi

echo ">>> Virtual environment created."

# 4. Ensure the virtual environment is activated
################################################
source "$SCRIPT_DIR/activate.sh"

# 5. Update PIP for the Poetry Python
####################################
"$POETRY_HOME/bin/poetry" run python -m pip install --upgrade --force-reinstall pip

# 6. Download and install all the required dependencies
#######################################################
"$POETRY_HOME/bin/poetry" run python -m pip install distro
"$POETRY_HOME/bin/poetry" run python "$SCRIPT_DIR/_lib/install/install_additional_dependencies.py"

# 7. Set back the current location to the current script folder
###############################################################
cd "$PATH_ORIGINAL_LOCATION" || return > /dev/null
