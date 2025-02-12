SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")

# Execute the pre-run logic
PRE_RUN_SCRIPT_PATH="$SCRIPT_DIR/pre_run.sh"
bash -c "\"$PRE_RUN_SCRIPT_PATH\" $*"

# Make sure Poetry is in PATH
export PATH="$PATH;${POETRY_HOME}/bin"

pushd "$PATH_QUADPYPE_ROOT" || return

# Starting QuadPype
. "${POETRY_HOME}/bin/poetry" run python "${PATH_QUADPYPE_ROOT}/start.py" tray --debug

popd || return
