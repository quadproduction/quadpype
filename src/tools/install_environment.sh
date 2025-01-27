#!/bin/bash

PATH_ORIGINAL_LOCATION=$(pwd)

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
PATH_QUADPYPE_ROOT=$SCRIPT_DIR
while [ "$(basename "$PATH_QUADPYPE_ROOT")" != "src" ]; do
  PATH_QUADPYPE_ROOT=$(dirname "$PATH_QUADPYPE_ROOT")
done

PATH_PYENV_DIR="$HOME/.pyenv"
PATH_PYENV_BIN_DIR="$HOME/.pyenv/pyenv-win/"
PATH_PYENV_INSTALL_FILE="$SCRIPT_DIR/install-pyenv-win.sh"

if [[ ":$PATH:" != *":$PATH_QUADPYPE_ROOT:"* ]]; then
  export PATH="$PATH_QUADPYPE_ROOT:$PATH"
fi

# 0. Install PyEnv, Python, and update PIP
##########################################

# 1. Delete the PyEnv directory
###############################
rm -rf "$PATH_PYENV_DIR"

# 1.A Download PyEnv, Install PyEnv and clean downloaded file
curl https://pyenv.run | bash

# 1.B Set the required environment variables related to PyEnv
if ! grep -q 'export PYENV_ROOT="$HOME/.pyenv"' ~/.bashrc; then
  echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
  echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
  echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
  echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
fi
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"

# 1.C Ensure the VIRTUAL_ENV variable isn't present in the User env variables
unset VIRTUAL_ENV

# 1.D Install the right Python version for the pipeline to run
pyenv install 3.9.13
pyenv global 3.9.13
pyenv local 3.9.13

# 1.E Update PIP for the pyenv Python
python3 -m pip install --upgrade --force-reinstall pip

# 2. Re-apply the previously saved terminal encoding
####################################################
# 2.A Set the current location to the QuadPype source directory
cd "$PATH_QUADPYPE_ROOT"

# 2.B Check validity of the QuadPype version
PATH_QUADPYPE_VERSION_FILE="$PATH_QUADPYPE_ROOT/quadpype/version.py"
QUADPYPE_VERSION=$(grep -Po '(?<=__version__ = ")[^"]+' "$PATH_QUADPYPE_VERSION_FILE")
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
POETRY_HOME="$PATH_QUADPYPE_ROOT/.poetry"
POETRY_VERSION="1.8.4"
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
"$POETRY_HOME/bin/poetry" run python "$SCRIPT_DIR/_lib/install/install_additional_dependencies.py"

# 7. Set back the current location to the current script folder
###############################################################
cd "$PATH_ORIGINAL_LOCATION"
