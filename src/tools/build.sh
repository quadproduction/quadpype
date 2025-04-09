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
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  "$POETRY_HOME/bin/poetry" run python "$PATH_QUADPYPE_ROOT/setup.py" build &> "$PATH_QUADPYPE_ROOT/build/build.log" || { echo -e "${RED}------------------------------------------${RST}"; cat "$PATH_QUADPYPE_ROOT/build/build.log"; echo -e "${RED}------------------------------------------${RST}"; echo -e "${RED}!!!${RST} Build failed, see the build log."; exit 1; }
elif [[ "$OSTYPE" == "darwin"* ]]; then
  "$POETRY_HOME/bin/poetry" run python "$PATH_QUADPYPE_ROOT/setup.py" bdist_mac &> "$PATH_QUADPYPE_ROOT/build/build.log" || { echo -e "${RED}------------------------------------------${RST}"; cat "$PATH_QUADPYPE_ROOT/build/build.log"; echo -e "${RED}------------------------------------------${RST}"; echo -e "${RED}!!!${RST} Build failed, see the build log."; exit 1; }
fi

"$POETRY_HOME/bin/poetry" run python "$PATH_QUADPYPE_ROOT/tools/_lib/build/build_dependencies.py" || { echo -e "${RED}!!!${RST} ${YELLOW}Failed to process dependencies${RST}"; exit 1; }

if [[ "$OSTYPE" == "darwin"* ]]; then
  # fix cx_Freeze libs issue
  echo -e "${GREEN}>>>${RST} Fixing libs for macOS ..."
  mv "$PATH_QUADPYPE_ROOT/build/QuadPype $QUADPYPE_VERSION.app/Contents/MacOS/dependencies/cx_Freeze" "$PATH_QUADPYPE_ROOT/build/QuadPype $QUADPYPE_VERSION.app/Contents/MacOS/lib/"  || { echo -e "${RED}!!!>${RST} ${YELLOW}Can't move cx_Freeze libs${RST}"; exit 1; }

  # force hide icon from Dock
  defaults write "$PATH_QUADPYPE_ROOT/build/QuadPype $QUADPYPE_VERSION.app/Contents/Info" LSUIElement 1

  # fix code signing issue
  echo -e "${GREEN}>>>${RST} Fixing code signatures ...\c"
  codesign --sign - --force --preserve-metadata=entitlements,requirements,flags,runtime "$PATH_QUADPYPE_ROOT/build/QuadPype $QUADPYPE_VERSION.app/Contents/MacOS/quadpype_console"
  codesign --sign - --force --preserve-metadata=entitlements,requirements,flags,runtime "$PATH_QUADPYPE_ROOT/build/QuadPype $QUADPYPE_VERSION.app/Contents/MacOS/quadpype_gui"

  echo -e "${GREEN}DONE${RST}"
  if command -v create-dmg > /dev/null 2>&1; then
    echo -e "${GREEN}>>>${RST} Creating dmg image ...\c"
    create-dmg \
      --volname "QuadPype $QUADPYPE_VERSION Installer" \
      --window-pos 200 120 \
      --window-size 600 300 \
      --app-drop-link 100 50 \
      "$PATH_QUADPYPE_ROOT/build/QuadPype-$QUADPYPE_VERSION-installer.dmg" \
      "$PATH_QUADPYPE_ROOT/build/QuadPype $QUADPYPE_VERSION.app"

    test $? -eq 0 || { echo -e "${RED}FAILED${RST}"; return 1; }
    echo -e "${GREEN}DONE${RST}"
  else
    echo -e "${YELLOW}!!!${RST} ${WHITE}create-dmg${RST} command is not available."
  fi
fi

cd "$PATH_ORIGINAL_LOCATION" || return > /dev/null

echo -e "${GREEN}***${RST} All done."
echo -e "${GREEN}***${RST} You will find the build and the log file in the ${WHITE}'src\\build\\'${RST} directory."
