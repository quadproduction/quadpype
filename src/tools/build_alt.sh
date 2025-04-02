#!/usr/bin/env bash

RST='\033[0m'             # Text Reset

# Regular Colors
RED='\033[0;31m'          # Red
GREEN='\033[0;32m'        # Green
YELLOW='\033[0;33m'       # Yellow
CYAN='\033[0;36m'         # Cyan
WHITE='\033[0;37m'        # White


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

PATH_ORIGINAL_LOCATION=$(pwd)

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
PATH_QUADPYPE_ROOT=$SCRIPT_DIR
while [ "$(basename "$PATH_QUADPYPE_ROOT")" != "src" ]; do
  PATH_QUADPYPE_ROOT=$(dirname "$PATH_QUADPYPE_ROOT")
done

# 2.A Set the current location to the QuadPype source directory
cd "$PATH_QUADPYPE_ROOT" || return > /dev/null

_INSIDE_QUADPYPE_TOOL="1"

if [[ -z $POETRY_HOME ]]; then
  export POETRY_HOME="$PATH_QUADPYPE_ROOT/.poetry"
fi

export QUADPYPE_ROOT="${PATH_QUADPYPE_ROOT}"

QUADPYPE_VERSION="$(python <<< "import os;import re;version={};exec(open(os.path.join('$PATH_QUADPYPE_ROOT', 'quadpype', 'version.py')).read(), version);print(re.search(r'(\d+\.\d+.\d+).*', version['__version__'])[1]);")"
echo -e "${GREEN}>>>${RST} QuadPype [ ${CYAN}${QUADPYPE_VERSION}${RST} ]"

echo -e "${GREEN}>>>${RST} Cleaning build directory ..."
rm -rf "$PATH_QUADPYPE_ROOT/build" && mkdir "$PATH_QUADPYPE_ROOT/build" > /dev/null

echo -e "${GREEN}>>>${RST} Reading Poetry ... \c"
if [ -f "$POETRY_HOME/bin/poetry" ]; then
  echo -e "${GREEN}OK${RST}"
else
  echo -e "${YELLOW}NOT FOUND${RST}"
  echo -e "${RED}!!!${RST} ${YELLOW}Dev environment seems not installed, starting the installation ...${RST}"
  echo -e "${RED}!!!${RST} ${YELLOW}You should execute the install_environment.sh script.${RST}"
fi

echo -e "${GREEN}>>>${RST} Cleaning cache files ... \c"
find . -regex '^.*\(__pycache__\|\.py[co]\)$' -exec rm -rf {} + &>/dev/null
echo -e "${GREEN}OK${RST}"

echo -e "${GREEN}>>>${RST} Building QuadPype ..."
"$POETRY_HOME/bin/poetry" run pyinstaller "$PATH_QUADPYPE_ROOT/tools/_lib/build/build_linux.spec"

rm -rf "$PATH_QUADPYPE_ROOT/build" && mkdir "$PATH_QUADPYPE_ROOT/build" > /dev/null

cp -r "$PATH_QUADPYPE_ROOT/dist/exe_quadpype" "$PATH_QUADPYPE_ROOT/build"

rm -rf "$PATH_QUADPYPE_ROOT/dist"

# Define the patterns to search for
mkdir -p "$PATH_QUADPYPE_ROOT/build/lib"
patterns=("libcrypt*" "libncursesw*" "libtinfo*" "libssl*")

# Loop through each pattern and copy the matching .so files to the 'lib' directory
for pattern in "${patterns[@]}"; do
    # Use find to search for matching .so files in /usr/lib64
    find /usr/lib64 -type f -name "$pattern" -exec cp --parents {} "$PATH_QUADPYPE_ROOT/build/exe_quadpype/lib" \;
done

patchelf --set-rpath "$ORIGIN/lib" "$PATH_QUADPYPE_ROOT/build/exe_quadpype/quadpype_console"
patchelf --set-rpath "$ORIGIN/lib" "$PATH_QUADPYPE_ROOT/build/exe_quadpype/quadpype_gui"

cp -r "$PATH_QUADPYPE_ROOT/igniter" "$PATH_QUADPYPE_ROOT/build/exe_quadpype"
cp -r "$PATH_QUADPYPE_ROOT/quadpype" "$PATH_QUADPYPE_ROOT/build/exe_quadpype"
cp -r "$PATH_QUADPYPE_ROOT/../LICENSE" "$PATH_QUADPYPE_ROOT/build/exe_quadpype"
cp -r "$PATH_QUADPYPE_ROOT/../README.md" "$PATH_QUADPYPE_ROOT/build/exe_quadpype"

"$POETRY_HOME/bin/poetry" run python "$PATH_QUADPYPE_ROOT/tools/_lib/build/build_dependencies.py" || { echo -e "${RED}!!!${RST} ${YELLOW}Failed to process dependencies${RST}"; exit 1; }

cd "$PATH_ORIGINAL_LOCATION" || return > /dev/null

echo -e "${GREEN}***${RST} All done."
echo -e "${GREEN}***${RST} You will find the build and the log file in the ${WHITE}'src\\build\\'${RST} directory."
