darling

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install openssl readline sqlite3 xz zlib create-dmg

./src/tools/install_environment_no_pyenv.sh

source ./src/.venv/bin/activate

./src/tools/build.sh
