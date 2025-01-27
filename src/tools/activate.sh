#!/bin/bash

SCRIPT_DIR=$(dirname "$(realpath "$0")")
PATH_QUADPYPE_ROOT=$SCRIPT_DIR

while [[ $(basename "$PATH_QUADPYPE_ROOT") != "src" ]]; do
    PATH_QUADPYPE_ROOT=$(dirname "$PATH_QUADPYPE_ROOT")
done

# Set the path to the QuadPype project and QuadPype package
export QUADPYPE_ROOT="$PATH_QUADPYPE_ROOT"

# Add QuadPype package path to the Python Path if needed
if [[ -z "$PYTHONPATH" ]]; then
    export PYTHONPATH="$QUADPYPE_ROOT"
elif [[ ":$PYTHONPATH:" != *":$QUADPYPE_ROOT:"* ]]; then
    export PYTHONPATH="$PYTHONPATH:$QUADPYPE_ROOT"
fi

# Check if the activate script exists
PATH_ACTIVATE_SCRIPT="$QUADPYPE_ROOT/.venv/bin/activate"
if [[ ! -f "$PATH_ACTIVATE_SCRIPT" ]]; then
    echo -e "\033[31m!!! \033[33mCannot find the activate script, the virtual environment seems not installed.\033[0m"
    echo -e "\033[31m!!! \033[33mYou should execute the install_environment.sh script.\033[0m"
    exit 1
fi

# Ensure the Poetry variable is available in the current environment
export POETRY_HOME="$PATH_QUADPYPE_ROOT/.poetry"

# Add poetry to the user PATH if needed
if [[ ":$PATH:" != *":$POETRY_HOME/bin:"* ]]; then
    export PATH="$PATH:$POETRY_HOME/bin"
fi

# Execute the activate script in the current process
source "$PATH_ACTIVATE_SCRIPT"
