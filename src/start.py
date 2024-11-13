# -*- coding: utf-8 -*-
"""Main entry point for the QuadPype application.

Bootstrapping process of QuadPype is as follows:

`QUADPYPE_PATH` is checked for existence - either one from environment or
from user settings. Precedence takes the one set by environment.

On this path we try to find QuadPype in directories version string in their
names. For example: `quadpype-v3.0.1-foo` is valid name, or
even `foo_3.0.2` - as long as version can be determined from its name
_AND_ file `quadpype/quadpype/version.py` can be found inside, it is
considered QuadPype installation.

If no QuadPype repositories are found in `QUADPYPE_PATH` (user data dir)
then **Igniter** (QuadPype's setup tool) will launch its GUI.

It can be used to specify `QUADPYPE_PATH` or if it is _not_ specified, current
*"live"* repositories will be used to create zip file and copy it to
appdata dir in user home and extract it there. Version will be determined by
version specified in QuadPype module.

If QuadPype repository directories are found in default install location
(user data dir) or in `QUADPYPE_PATH`, it will get list of those dirs
there and use latest one or the one specified with optional `--use-version`
command line argument. If the one specified doesn't exist then latest
available version will be used. All repositories in that dir will be added
to `sys.path` and `PYTHONPATH`.

If QuadPype is live (not frozen) then current version of QuadPype module
will be used. All directories under `repos` will be added to `sys.path` and
`PYTHONPATH`.

QuadPype depends on connection to `MongoDB`_. You can specify MongoDB
connection string via `QUADPYPE_MONGO` set in environment or it can be set
in user settings or via **Igniter** GUI.

So, bootstrapping QuadPype looks like this::

.. code-block:: bash

┌───────────────────────────────────────────────────────┐
│ Determine MongoDB connection:                         │
│ Use `QUADPYPE_MONGO`, system keyring `quadpypeMongo`  │
└──────────────────────────┬────────────────────────────┘
                  ┌───- Found? -─┐
                 YES             NO
                  │              │
                  │       ┌──────┴──────────────┐
                  │       │ Fire up Igniter GUI ├<-────────┐
                  │       │ and ask User        │          │
                  │       └─────────────────────┘          │
                  │                                        │
                  │                                        │
┌─────────────────┴─────────────────────────────────────┐  │
│ Get location of QuadPype:                             │  │
│   1) Test for `QUADPYPE_PATH` environment variable    │  │
│   2) Test `quadpypePath` in registry setting          │  │
│   3) Test user data directory                         │  │
│ ····················································· │  │
│ If running from frozen code:                          │  │
│   - Use latest one found in user data dir             │  │
│ If running from live code:                            │  │
│   - Use live code and install it to user data dir     │  │
│ * can be overridden with `--use-version` argument     │  │
└──────────────────────────┬────────────────────────────┘  │
              ┌─- Is QuadPype found? -─┐                   │
             YES                       NO                  │
              │                        │                   │
              │      ┌─────────────────┴─────────────┐     │
              │      │ Look in `QUADPYPE_PATH`, find │     │
              │      │ latest version and install it │     │
              │      │ to user data dir.             │     │
              │      └──────────────┬────────────────┘     │
              │         ┌─- Is QuadPype found? -─┐         │
              │        YES                       NO -──────┘
              │         │
              ├<-───────┘
              │
┌─────────────┴────────────┐
│      Run QuadPype        │
└─────══════════════───────┘


Todo:
    Move or remove bootstrapping environments out of the code.

Attributes:
    silent_commands (set): list of commands for which we won't print QuadPype
        info header.

.. _MongoDB:
   https://www.mongodb.com/

"""
import os
import re
import sys
import platform
import traceback
import subprocess
import site
import distutils.spawn
from pathlib import Path


silent_mode = False

# QUADPYPE_ROOT is variable pointing to build (or code) directory
# WARNING `QUADPYPE_ROOT` must be defined before igniter import
# - igniter changes cwd which cause that filepath of this script won't lead
#   to right directory
if not getattr(sys, 'frozen', False):
    # Code root defined by `start.py` directory
    QUADPYPE_ROOT = os.path.dirname(os.path.abspath(__file__))
else:
    QUADPYPE_ROOT = os.path.dirname(sys.executable)

    # add dependencies folder to sys.pat for frozen code
    frozen_libs = os.path.normpath(
        os.path.join(QUADPYPE_ROOT, "dependencies")
    )
    sys.path.append(frozen_libs)
    sys.path.insert(0, QUADPYPE_ROOT)
    # add stuff from `<frozen>/dependencies` to PYTHONPATH.
    pythonpath = os.getenv("PYTHONPATH", "")
    paths = pythonpath.split(os.pathsep)
    paths.append(frozen_libs)
    os.environ["PYTHONPATH"] = os.pathsep.join(paths)

# Vendored python modules that must not be in PYTHONPATH environment but
#   are required for QuadPype processes
vendor_python_path = os.path.join(QUADPYPE_ROOT, "vendor", "python")
sys.path.insert(0, vendor_python_path)

# Add common package to sys path
# - common contains common code for bootstraping and QuadPype processes
sys.path.insert(0, os.path.join(QUADPYPE_ROOT, "common"))

import blessed  # noqa: E402
import certifi  # noqa: E402


if sys.__stdout__:
    term = blessed.Terminal()

    def _print(message: str, force=False):
        if silent_mode and not force:
            return
        if message.startswith("!!! "):
            print(f'{term.orangered2("!!! ")}{message[4:]}')
            return
        if message.startswith(">>> "):
            print(f'{term.aquamarine3(">>> ")}{message[4:]}')
            return
        if message.startswith("--- "):
            print(f'{term.darkolivegreen3("--- ")}{message[4:]}')
            return
        if message.startswith("*** "):
            print(f'{term.gold("*** ")}{message[4:]}')
            return
        if message.startswith("  - "):
            print(f'{term.wheat("  - ")}{message[4:]}')
            return
        if message.startswith("  . "):
            print(f'{term.tan("  . ")}{message[4:]}')
            return
        if message.startswith("     - "):
            print(f'{term.seagreen3("     - ")}{message[7:]}')
            return
        if message.startswith("     ! "):
            print(f'{term.goldenrod("     ! ")}{message[7:]}')
            return
        if message.startswith("     * "):
            print(f'{term.aquamarine1("     * ")}{message[7:]}')
            return
        if message.startswith("    "):
            print(f'{term.darkseagreen3("    ")}{message[4:]}')
            return

        print(message)
else:
    def _print(message: str):
        if silent_mode:
            return
        print(message)


# if SSL_CERT_FILE is not set prior to QuadPype launch, we set it to point
# to certifi bundle to make sure we have reasonably new CA certificates.
if os.getenv("SSL_CERT_FILE") and \
        os.getenv("SSL_CERT_FILE") != certifi.where():
    _print("--- your system is set to use custom CA certificate bundle.")
else:
    ssl_cert_file = certifi.where()
    os.environ["SSL_CERT_FILE"] = ssl_cert_file

if "--zxp-ignore-update" in sys.argv:
    os.environ["QUADPYPE_IGNORE_ZXP_UPDATE"] = "1"
    sys.argv.remove("--zxp-ignore-update")
elif os.getenv("QUADPYPE_IGNORE_ZXP_UPDATE") != "1":
    os.environ.pop("QUADPYPE_IGNORE_ZXP_UPDATE", None)

if "--headless" in sys.argv:
    os.environ["QUADPYPE_HEADLESS_MODE"] = "1"
    sys.argv.remove("--headless")
elif os.getenv("QUADPYPE_HEADLESS_MODE") != "1":
    os.environ.pop("QUADPYPE_HEADLESS_MODE", None)

# Set builtin ocio root
os.environ["BUILTIN_OCIO_ROOT"] = os.path.join(
    QUADPYPE_ROOT,
    "vendor",
    "bin",
    "ocioconfig",
    "OpenColorIOConfigs"
)

# Enabled logging debug mode when "--debug" is passed
if "--verbose" in sys.argv:
    expected_values = (
        "Expected: notset, debug, info, warning, error, critical"
        " or integer [0-50]."
    )
    idx = sys.argv.index("--verbose")
    sys.argv.pop(idx)
    if idx < len(sys.argv):
        value = sys.argv.pop(idx)
    else:
        raise RuntimeError((
            f"Expect value after \"--verbose\" argument. {expected_values}"
        ))

    log_level = None
    low_value = value.lower()
    if low_value.isdigit():
        log_level = int(low_value)
    elif low_value == "notset":
        log_level = 0
    elif low_value == "debug":
        log_level = 10
    elif low_value == "info":
        log_level = 20
    elif low_value == "warning":
        log_level = 30
    elif low_value == "error":
        log_level = 40
    elif low_value == "critical":
        log_level = 50

    if log_level is None:
        raise RuntimeError((
            "Unexpected value after \"--verbose\" "
            f"argument \"{value}\". {expected_values}"
        ))

    os.environ["QUADPYPE_LOG_LEVEL"] = str(log_level)

# Enable debug mode, may affect log level if log level is not defined
if "--debug" in sys.argv:
    sys.argv.remove("--debug")
    os.environ["QUADPYPE_DEBUG"] = "1"

# Load additional environment variables from env file (if requested)
if "--additional-env-file" in sys.argv:
    idx = sys.argv.index("--additional-env-file")
    sys.argv.pop(idx)
    if idx < len(sys.argv):
        env_file_path = sys.argv.pop(idx)
    else:
        raise RuntimeError((
            "Expect value after \"--additional-env-file\" argument. "
            "Expected: --additional-env-file {path to env file}"
        ))

    env_file_path_obj = Path(env_file_path).resolve()

    if not env_file_path_obj.exists():
        _print("--- Path passed to argument \"--additional-env-file\" doesn't exist.")
    else:
        # Load all the key=value pairs as environment variables
        with open(env_file_path_obj, "r") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith('#') or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[8:]
                if line.startswith("set "):
                    line = line[4:]

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                os.environ[key] = value


if "--automatic-tests" in sys.argv:
    sys.argv.remove("--automatic-tests")
    os.environ["IS_TEST"] = "1"

if "--use-staging" in sys.argv:
    sys.argv.remove("--use-staging")
    os.environ["QUADPYPE_USE_STAGING"] = "1"

import igniter  # noqa: E402
from igniter import BootstrapRepos  # noqa: E402
from igniter.tools import (
    get_quadpype_global_settings,
    get_quadpype_path_from_settings,
    get_local_quadpype_path_from_settings,
    validate_mongo_connection,
    QuadPypeVersionNotFound,
    QuadPypeVersionIncompatible
)  # noqa
from igniter.bootstrap_repos import QuadPypeVersion  # noqa: E402

bootstrap = BootstrapRepos()
silent_commands = {"run", "igniter", "standalonepublisher",
                   "extractenvironments", "version"}


def list_versions(quadpype_versions: list, local_version=None) -> None:
    """Print list of detected versions."""
    _print("  - Detected versions:")
    for v in sorted(quadpype_versions):
        _print(f"     - {v}: {v.path}")
    if not quadpype_versions:
        _print("     ! none in repository detected")
    if local_version:
        _print(f"     * local version {local_version}")


def set_quadpype_global_environments() -> None:
    """Set global QuadPype's environments."""
    import acre

    from quadpype.settings import get_general_environments

    general_env = get_general_environments()

    # first resolve general environment because merge doesn't expect
    # values to be list.
    # TODO: switch to QuadPype environment functions
    merged_env = acre.merge(
        acre.compute(acre.parse(general_env), cleanup=False),
        dict(os.environ)
    )
    env = acre.compute(
        merged_env,
        cleanup=False
    )
    os.environ.clear()
    os.environ.update(env)

    # Hardcoded default values
    os.environ["PYBLISH_GUI"] = "pyblish_pype"
    # Change scale factor only if is not set
    if "QT_AUTO_SCREEN_SCALE_FACTOR" not in os.environ:
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


def run(arguments: list, env: dict = None) -> int:
    """Use correct executable to run stuff.

    This passing arguments to correct QuadPype executable. If QuadPype is run
    from live sources, executable will be `python` in virtual environment.
    If running from frozen code, executable will be `quadpype_console` or
    `quadpype_gui`. Its equivalent in live code is `python start.py`.

    Args:
        arguments (list): Argument list to pass QuadPype.
        env (dict, optional): Dictionary containing environment.

    Returns:
        int: Process return code.

    """
    if getattr(sys, 'frozen', False):
        interpreter = [sys.executable]
    else:
        interpreter = [sys.executable, __file__]

    interpreter.extend(arguments)

    p = subprocess.Popen(interpreter, env=env)
    p.wait()
    _print(f">>> done [{p.returncode}]")
    return p.returncode


def run_disk_mapping_commands(settings):
    """ Run disk mapping command

        Used to map shared disk for QuadPype to pull codebase.
    """

    low_platform = platform.system().lower()
    disk_mapping = settings.get("disk_mapping")
    if not disk_mapping:
        return

    mappings = disk_mapping.get(low_platform) or []
    for source, destination in mappings:
        if low_platform == "windows":
            destination = destination.replace("/", "\\").rstrip("\\")
            source = source.replace("/", "\\").rstrip("\\")
            # Add slash after ':' ('G:' -> 'G:\')
            if source.endswith(":"):
                source += "\\"
            if destination.endswith(":"):
                destination += "\\"
        else:
            destination = destination.rstrip("/")
            source = source.rstrip("/")

        if low_platform == "darwin":
            scr = f'do shell script "ln -s {source} {destination}" with administrator privileges'  # noqa

            args = ["osascript", "-e", scr]
        elif low_platform == "windows":
            args = ["subst", destination, source]
        else:
            args = ["sudo", "ln", "-s", source, destination]

        _print(f"*** disk mapping arguments: {args}")
        try:
            if not os.path.exists(destination):
                output = subprocess.Popen(args)
                if output.returncode and output.returncode != 0:
                    exc_msg = f'Executing was not successful: "{args}"'

                    raise RuntimeError(exc_msg)
        except TypeError as exc:
            _print(
                f"Error {str(exc)} in mapping drive {source}, {destination}")
            raise


def set_database_environments():
    """Set database specific environments.

    These are non-modifiable environments for database workflow that must be set
    before database module is imported because database works with globals set with
    environment variables.
    """

    projects_db_name = os.getenv("QUADPYPE_PROJECTS_DB_NAME") or "quadpype_projects"
    os.environ.update({
        # Mongo DB name where projects docs are stored
        "QUADPYPE_PROJECTS_DB_NAME": projects_db_name,
        # Name of config
        "QUADPYPE_LABEL": "QuadPype"
    })


def update_zxp_extensions(quadpype_version):
    from quadpype.settings import get_global_settings

    global_settings = get_global_settings()
    zxp_hosts_to_update = bootstrap.get_zxp_extensions_to_update(quadpype_version, global_settings)
    if not zxp_hosts_to_update:
        return

    in_headless_mode = os.getenv("QUADPYPE_HEADLESS_MODE") == "1"
    if in_headless_mode:
        bootstrap.update_zxp_extensions(quadpype_version, zxp_hosts_to_update)
    else:
        igniter.open_update_window(quadpype_version, zxp_hosts_to_update)


def set_modules_environments():
    """Set global environments for QuadPype modules.

    This requires to have QuadPype in `sys.path`.
    """

    from quadpype.modules import ModulesManager
    import acre

    modules_manager = ModulesManager()

    module_envs = modules_manager.collect_global_environments()

    # Merge environments with current environments and update values
    if module_envs:
        parsed_envs = acre.parse(module_envs)
        env = acre.merge(parsed_envs, dict(os.environ))
        os.environ.clear()
        os.environ.update(env)


def _startup_validations():
    """Validations before QuadPype starts."""
    try:
        _validate_thirdparty_binaries()
    except Exception as exc:
        if os.getenv("QUADPYPE_HEADLESS_MODE"):
            raise

        import tkinter
        from tkinter.messagebox import showerror

        root = tkinter.Tk()
        root.attributes("-alpha", 0.0)
        root.wm_state("iconic")
        if platform.system().lower() != "windows":
            root.withdraw()

        showerror(
            "Startup validations didn't pass",
            str(exc)
        )
        root.withdraw()
        sys.exit(1)


def _validate_thirdparty_binaries():
    """Check existence of thirdpart executables."""
    low_platform = platform.system().lower()
    binary_vendors_dir = os.path.join(
        os.environ["QUADPYPE_ROOT"],
        "vendor",
        "bin"
    )

    error_msg = (
        "Missing binary dependency {}. Please fetch thirdparty dependencies."
    )
    # Validate existence of FFmpeg
    ffmpeg_dir = os.path.join(binary_vendors_dir, "ffmpeg", low_platform)
    if low_platform == "windows":
        ffmpeg_dir = os.path.join(ffmpeg_dir, "bin")
    ffmpeg_executable = os.path.join(ffmpeg_dir, "ffmpeg")
    ffmpeg_result = distutils.spawn.find_executable(ffmpeg_executable)
    if ffmpeg_result is None:
        raise RuntimeError(error_msg.format("FFmpeg"))

    # Validate existence of OpenImageIO (not on MacOs)
    oiio_tool_path = None
    if low_platform == "linux":
        oiio_tool_path = os.path.join(
            binary_vendors_dir,
            "oiio",
            low_platform,
            "bin",
            "oiiotool"
        )
    elif low_platform == "windows":
        oiio_tool_path = os.path.join(
            binary_vendors_dir,
            "oiio",
            low_platform,
            "oiiotool"
        )
    oiio_result = None
    if oiio_tool_path is not None:
        oiio_result = distutils.spawn.find_executable(oiio_tool_path)
        if oiio_result is None:
            raise RuntimeError(error_msg.format("OpenImageIO"))


def _process_arguments() -> tuple:
    """Process command line arguments.

    Returns:
        tuple: Return tuple with specific version to use (if any) and flag
            to prioritize staging (if set)
    """
    # check for `--use-version=3.0.0` argument and `--use-staging`
    use_version = None
    commands = []

    # QuadPype version specification through arguments
    use_version_arg = "--use-version"

    for arg in sys.argv:
        if arg.startswith(use_version_arg):
            # Remove arg from sys argv
            sys.argv.remove(arg)
            # Extract string after use version arg
            use_version_value = arg[len(use_version_arg):]

            if (
                not use_version_value
                or not use_version_value.startswith("=")
            ):
                _print("!!! Please use option --use-version like:", True)
                _print("    --use-version=3.0.0", True)
                sys.exit(1)

            version_str = use_version_value[1:]
            use_version = None
            if version_str.lower() == "latest":
                use_version = "latest"
            else:
                m = re.search(
                    r"(?P<version>\d+\.\d+\.\d+(?:\S*)?)", version_str
                )
                if m and m.group('version'):
                    use_version = m.group('version')
                    _print(f">>> Requested version [ {use_version} ]")
                    break

            if use_version is None:
                _print("!!! Requested version isn't in correct format.", True)
                _print(("    Use --list-versions to find out"
                       " proper version string."), True)
                sys.exit(1)

        if arg == "--validate-version":
            _print("!!! Please use option --validate-version like:", True)
            _print("    --validate-version=3.0.0", True)
            sys.exit(1)

        if arg.startswith("--validate-version="):
            m = re.search(
                r"--validate-version=(?P<version>\d+\.\d+\.\d+(?:\S*)?)", arg)
            if m and m.group('version'):
                use_version = m.group('version')
                sys.argv.remove(arg)
                commands.append("validate")
            else:
                _print("!!! Requested version isn't in correct format.", True)
                _print(("    Use --list-versions to find out"
                        " proper version string."), True)
                sys.exit(1)

    if "--list-versions" in sys.argv:
        commands.append("print_versions")
        sys.argv.remove("--list-versions")

    if "--no-version-popup" in sys.argv:
        commands.append("disable_version_popup")
        sys.argv.remove("--no-version-popup")

    # handle igniter
    # this is helper to run igniter before anything else
    if "igniter" in sys.argv:
        if os.getenv("QUADPYPE_HEADLESS_MODE") == "1":
            _print("!!! Cannot open Igniter dialog in headless mode.", True)
            sys.exit(1)

        return_code = igniter.open_dialog()

        # this is when we want to run QuadPype without installing anything.
        # or we are ready to run.
        if return_code not in [2, 3]:
            sys.exit(return_code)

        idx = sys.argv.index("igniter")
        sys.argv.pop(idx)
        sys.argv.insert(idx, "tray")

    return use_version, commands


def _determine_mongodb() -> str:
    """Determine mongodb connection string.

    First use ``QUADPYPE_MONGO`` environment variable, then system keyring.
    Then try to run **Igniter UI** to let user specify it.

    Returns:
        str: mongodb connection URL

    Raises:
        RuntimeError: if mongodb connection url cannot by determined.

    """

    quadpype_mongo = os.getenv("QUADPYPE_MONGO", None)
    if not quadpype_mongo:
        # try system keyring
        try:
            quadpype_mongo = bootstrap.secure_registry.get_item(
                "quadpypeMongo"
            )
        except ValueError:
            pass

    if quadpype_mongo:
        result, msg = validate_mongo_connection(quadpype_mongo)
        if not result:
            _print(msg)
            quadpype_mongo = None

    if not quadpype_mongo:
        _print("*** No DB connection string specified.")
        if os.getenv("QUADPYPE_HEADLESS_MODE") == "1":
            _print("!!! Cannot open Igniter dialog in headless mode.", True)
            _print(("!!! Please use `QUADPYPE_MONGO` to specify "
                    "server address."), True)
            sys.exit(1)
        _print("--- launching setup UI ...")

        result = igniter.open_dialog()
        if result == 0:
            raise RuntimeError("MongoDB URL was not defined")

        quadpype_mongo = os.getenv("QUADPYPE_MONGO")
        if not quadpype_mongo:
            try:
                quadpype_mongo = bootstrap.secure_registry.get_item(
                    "quadpypeMongo")
            except ValueError as e:
                raise RuntimeError("Missing MongoDB url") from e

    return quadpype_mongo


def _initialize_environment(quadpype_version: QuadPypeVersion) -> None:
    version_path = quadpype_version.path
    if not version_path:
        _print(f"!!! Version {quadpype_version} doesn't have path set.")
        raise ValueError("No path set in specified QuadPype version.")
    os.environ["QUADPYPE_VERSION"] = str(quadpype_version)
    # set QUADPYPE_REPOS_ROOT to point to currently used QuadPype version.
    os.environ["QUADPYPE_REPOS_ROOT"] = os.path.normpath(
        version_path.as_posix()
    )
    # inject version to Python environment (sys.path, ...)
    _print(">>> Injecting QuadPype version to running environment  ...")
    bootstrap.add_paths_from_directory(version_path)

    # Additional sys paths related to QUADPYPE_REPOS_ROOT directory
    # TODO move additional paths to `boot` part when QUADPYPE_REPOS_ROOT will
    # point to same hierarchy from code and from frozen QuadPype
    additional_paths = [
        os.environ["QUADPYPE_REPOS_ROOT"],
        # add QuadPype tools
        os.path.join(os.environ["QUADPYPE_REPOS_ROOT"], "quadpype", "tools"),
        # add common QuadPype vendor
        # (common for multiple Python interpreter versions)
        os.path.join(
            os.environ["QUADPYPE_REPOS_ROOT"],
            "quadpype",
            "vendor",
            "python",
            "common"
        )
    ]

    split_paths = os.getenv("PYTHONPATH", "").split(os.pathsep)
    for path in additional_paths:
        split_paths.insert(0, path)
        sys.path.insert(0, path)

    os.environ["PYTHONPATH"] = os.pathsep.join(split_paths)


def _install_and_initialize_version(quadpype_version: QuadPypeVersion, delete_zip=True):
    if quadpype_version.path.is_file():
        _print(">>> Extracting zip file ...")
        try:
            version_path = bootstrap.extract_quadpype(quadpype_version)
            quadpype_version.path = version_path
        except OSError as e:
            _print("!!! failed: {}".format(str(e)), True)
            sys.exit(1)
        else:
            # cleanup zip after extraction, we don't touch prod dir
            if delete_zip and quadpype_version not in QuadPypeVersion.get_remote_versions():
                os.unlink(quadpype_version.path)

    _initialize_environment(quadpype_version)


def _find_frozen_quadpype(use_version: str = None,
                          use_staging: bool = False) -> QuadPypeVersion:
    """Find QuadPype to run from frozen code.

    This will process and modify environment variables:
    ``PYTHONPATH``, ``QUADPYPE_VERSION``, ``QUADPYPE_REPOS_ROOT``

    Args:
        use_version (str, optional): Try to use specified version.
        use_staging (bool, optional): Prefer *staging* flavor over production.

    Returns:
        QuadPypeVersion: Version to be used.

    Raises:
        RuntimeError: If no QuadPype version are found.

    """
    # Collect QuadPype versions
    installed_version = QuadPypeVersion.get_installed_version()
    # Expected version that should be used by studio settings
    #   - this option is used only if version is not explicitly set and if
    #       studio has set explicit version in settings
    studio_version = QuadPypeVersion.get_expected_studio_version(use_staging)

    if use_version is not None:
        # Specific version is defined
        if use_version.lower() == "latest":
            # Version says to use latest version
            _print(">>> Finding latest version defined by use version")
            quadpype_version = bootstrap.find_latest_quadpype_version()
        else:
            _print(f">>> Finding specified version \"{use_version}\"")
            quadpype_version = bootstrap.find_quadpype_version(use_version)

        if quadpype_version is None:
            raise QuadPypeVersionNotFound(
                f"Requested version \"{use_version}\" was not found."
            )

    elif studio_version is not None:
        # Studio has defined a version to use
        _print(f">>> Finding studio version \"{studio_version}\"")
        quadpype_version = bootstrap.find_quadpype_version(studio_version)
        if quadpype_version is None:
            raise QuadPypeVersionNotFound((
                "Requested QuadPype version "
                f"\"{studio_version}\" defined by settings"
                " was not found."
            ))

    else:
        # Default behavior to use latest version
        _print((
            ">>> Finding latest version "
            f"with [ {installed_version} ]"))
        quadpype_version = bootstrap.find_latest_quadpype_version()

        if quadpype_version is None:
            raise QuadPypeVersionNotFound("Didn't find any versions.")

    # get local frozen version and add it to detected version so if it is
    # newer it will be used instead.
    if installed_version == quadpype_version:
        quadpype_version = _bootstrap_from_code(use_version)
        _initialize_environment(quadpype_version)
        return quadpype_version

    in_headless_mode = os.getenv("QUADPYPE_HEADLESS_MODE") == "1"
    if not installed_version.is_compatible(quadpype_version):
        message = "Version {} is not compatible with installed version {}."
        # Show UI to user
        if not in_headless_mode:
            igniter.show_message_dialog(
                "Incompatible QuadPype installation",
                message.format(
                    "<b>{}</b>".format(quadpype_version),
                    "<b>{}</b>".format(installed_version)
                )
            )
        # Raise incompatible error
        raise QuadPypeVersionIncompatible(
            message.format(quadpype_version, installed_version)
        )

    # test if latest detected is installed (in user data dir)
    is_inside = False
    try:
        is_inside = quadpype_version.path.resolve().relative_to(
            bootstrap.data_dir)
    except ValueError:
        # if relative path cannot be calculated, quadpype version is not
        # inside user data dir
        pass

    if not is_inside:
        from quadpype.settings import get_global_settings

        global_settings = get_global_settings()
        # install latest version to user data dir
        zxp_hosts_to_update = bootstrap.get_zxp_extensions_to_update(quadpype_version, global_settings, force=True)
        if in_headless_mode:
            version_path = bootstrap.install_version(
                quadpype_version, force=True
            )
            bootstrap.update_zxp_extensions(quadpype_version, zxp_hosts_to_update)
        else:
            version_path = igniter.open_update_window(quadpype_version, zxp_hosts_to_update)

        quadpype_version.path = version_path
        _initialize_environment(quadpype_version)
        return quadpype_version

    _install_and_initialize_version(quadpype_version)

    return quadpype_version


def _bootstrap_from_code(use_version) -> QuadPypeVersion:
    """Bootstrap live code (or the one coming with frozen QuadPype).

    Args:
        use_version: (str): specific version to use.

    Returns:
        Path: path to sourced version.

    """
    # run through repos and add them to `sys.path` and `PYTHONPATH`
    # set root
    _quadpype_root = QUADPYPE_ROOT
    # Unset use version if latest should be used
    #   - when executed from code then code is expected as latest
    #   - when executed from build then build is already marked as latest
    #       in '_find_frozen_quadpype'
    if use_version and use_version.lower() == "latest":
        use_version = None

    if getattr(sys, 'frozen', False):
        local_version = bootstrap.get_version(Path(_quadpype_root))
        local_version_str = str(local_version)
        switch_str = f" - will switch to {use_version}" if use_version and use_version != local_version_str else ""  # noqa
        _print(f"  - booting version: {local_version_str}{switch_str}")
        if not local_version_str:
            raise QuadPypeVersionNotFound(
                f"Cannot find version at {_quadpype_root}")
    else:
        # Get current version of QuadPype
        local_version = QuadPypeVersion.get_installed_version()

    # All cases when should be used different version than build
    if use_version and use_version != str(local_version):
        if use_version:
            # Explicit version should be used
            version_to_use = bootstrap.find_quadpype_version(use_version)
            if version_to_use is None:
                raise QuadPypeVersionIncompatible(
                    f"Requested version \"{use_version}\" was not found.")
        else:
            version_to_use = bootstrap.find_latest_quadpype_version()
            if version_to_use is None:
                raise QuadPypeVersionNotFound("Didn't find any versions.")

        # Start extraction of version if needed
        if version_to_use.path.is_file():
            version_to_use.path = bootstrap.extract_quadpype(version_to_use)
        bootstrap.add_paths_from_directory(version_to_use.path)
        os.environ["QUADPYPE_VERSION"] = use_version
        version_path = version_to_use.path
        os.environ["QUADPYPE_REPOS_ROOT"] = (
            version_path / "quadpype"
        ).as_posix()
        _quadpype_root = version_to_use.path.as_posix()

    else:
        os.environ["QUADPYPE_VERSION"] = str(local_version)
        os.environ["QUADPYPE_REPOS_ROOT"] = _quadpype_root

    # add self to sys.path of current process
    # NOTE: this seems to be duplicate of 'add_paths_from_directory'
    sys.path.insert(0, _quadpype_root)
    # add venv 'site-packages' to PYTHONPATH
    python_path = os.getenv("PYTHONPATH", "")
    split_paths = python_path.split(os.pathsep)
    # add self to python paths
    split_paths.insert(0, _quadpype_root)

    # last one should be venv site-packages
    # this is slightly convoluted as we can get here from frozen code too
    # in case when we are running without any version installed.
    if not getattr(sys, 'frozen', False):
        split_paths.append(site.getsitepackages()[-1])
        # TODO move additional paths to `boot` part when QUADPYPE_ROOT will
        # point to same hierarchy from code and from frozen QuadPype
        additional_paths = [
            # add QuadPype tools
            os.path.join(_quadpype_root, "quadpype", "tools"),
            # add common QuadPype vendor
            # (common for multiple Python interpreter versions)
            os.path.join(
                _quadpype_root,
                "quadpype",
                "vendor",
                "python",
                "common"
            )
        ]
        for path in additional_paths:
            split_paths.insert(0, path)
            sys.path.insert(0, path)

    os.environ["PYTHONPATH"] = os.pathsep.join(split_paths)

    return local_version


def _boot_validate_versions(use_version, local_version):
    _print(f">>> Validating version [ {use_version} ]")
    quadpype_versions = bootstrap.find_quadpype(include_zips=True)
    v: QuadPypeVersion
    found = [v for v in quadpype_versions if str(v) == use_version]
    if not found:
        _print(f"!!! Version [ {use_version} ] not found.", True)
        list_versions(quadpype_versions, local_version)
        sys.exit(1)

    # print result
    version_path = bootstrap.get_version_path_from_list(
        use_version, quadpype_versions
    )
    valid, message = bootstrap.validate_quadpype_version(version_path)
    _print(f'{">>> " if valid else "!!! "}{message}', not valid)
    return valid


def _boot_print_versions(quadpype_root):
    if getattr(sys, 'frozen', False):
        local_version = bootstrap.get_version(Path(quadpype_root))
    else:
        local_version = QuadPypeVersion.get_installed_version_str()

    compatible_with = QuadPypeVersion(version=local_version)
    if "--all" in sys.argv:
        _print("--- Showing all version (even those not compatible).")
    else:
        _print(("--- Showing only compatible versions "
                f"with [ {compatible_with.major}.{compatible_with.minor} ]"))

    quadpype_versions = bootstrap.find_quadpype(include_zips=True)
    quadpype_versions = [
        version for version in quadpype_versions
        if version.is_compatible(
            QuadPypeVersion.get_installed_version())
    ]

    list_versions(quadpype_versions, local_version)


def _boot_handle_missing_version(local_version, message):
    _print(message, True)
    if os.getenv("QUADPYPE_HEADLESS_MODE") == "1":
        quadpype_versions = bootstrap.find_quadpype(
            include_zips=True)
        list_versions(quadpype_versions, local_version)
    else:
        igniter.show_message_dialog("Version not found", message)


def boot():
    """Bootstrap QuadPype."""
    global silent_mode
    if any(arg in silent_commands for arg in sys.argv):
        silent_mode = True

    # ------------------------------------------------------------------------
    # Set environment to QuadPype root path
    # ------------------------------------------------------------------------
    os.environ["QUADPYPE_ROOT"] = QUADPYPE_ROOT

    # ------------------------------------------------------------------------
    # Do necessary startup validations
    # ------------------------------------------------------------------------
    _startup_validations()

    # ------------------------------------------------------------------------
    # Process arguments
    # ------------------------------------------------------------------------

    use_version, commands = _process_arguments()
    use_staging = os.getenv("QUADPYPE_USE_STAGING") == "1"

    if os.getenv("QUADPYPE_VERSION"):
        if use_version:
            _print(("*** environment variable QUADPYPE_VERSION"
                    "is overridden by command line argument."))
        else:
            _print(">>> Version set by environment variable")
            use_version = os.getenv("QUADPYPE_VERSION")

    # ------------------------------------------------------------------------
    # Determine mongodb connection
    # ------------------------------------------------------------------------

    try:
        quadpype_mongo = _determine_mongodb()
    except RuntimeError as e:
        # without mongodb url we are done for.
        _print(f"!!! {e}", True)
        sys.exit(1)

    os.environ["QUADPYPE_MONGO"] = quadpype_mongo
    # name of Pype database
    os.environ["QUADPYPE_DATABASE_NAME"] = \
        os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"

    if os.getenv("IS_TEST") == "1":
        # change source DBs to predefined ones set for automatic testing
        if "_tests" not in os.environ["QUADPYPE_DATABASE_NAME"]:
            os.environ["QUADPYPE_DATABASE_NAME"] += "_tests"
        projects_db_name = os.getenv("QUADPYPE_PROJECTS_DB_NAME") or "quadpype_projects"
        if "_tests" not in projects_db_name:
            os.environ["QUADPYPE_PROJECTS_DB_NAME"] = projects_db_name + "_tests"

    global_settings = get_quadpype_global_settings(quadpype_mongo)

    _print(">>> Run disk mapping command ...")
    run_disk_mapping_commands(global_settings)

    # Logging to server enabled/disabled
    log_to_server = global_settings.get("log_to_server", True)
    if log_to_server:
        os.environ["QUADPYPE_LOG_TO_SERVER"] = "1"
        log_to_server_msg = "ON"
    else:
        os.environ.pop("QUADPYPE_LOG_TO_SERVER", None)
        log_to_server_msg = "OFF"
    _print(f">>> Logging to server is turned {log_to_server_msg}")

    # Get path to the folder containing QuadPype patch versions, then set it to
    # environment so quadpype can find its versions there and bootstrap them.
    quadpype_path = get_quadpype_path_from_settings(global_settings)

    # Check if local versions should be installed in custom folder and not in
    # user app data
    data_dir = get_local_quadpype_path_from_settings(global_settings)
    bootstrap.set_data_dir(data_dir)
    if getattr(sys, 'frozen', False):
        local_version = bootstrap.get_version(Path(QUADPYPE_ROOT))
    else:
        local_version = QuadPypeVersion.get_installed_version_str()

    if "validate" in commands:
        valid = _boot_validate_versions(use_version, local_version)
        sys.exit(0 if valid else 1)

    if not quadpype_path:
        _print("*** Cannot get QuadPype patches directory path from database.")

    if not os.getenv("QUADPYPE_PATH") and quadpype_path:
        os.environ["QUADPYPE_PATH"] = quadpype_path

    if "print_versions" in commands:
        _boot_print_versions(QUADPYPE_ROOT)
        sys.exit(0)

    # ------------------------------------------------------------------------
    # Ensure patch version of QuadPype is on the user/local dir
    # ------------------------------------------------------------------------
    curr_version = local_version
    if isinstance(local_version, str):
        curr_version = QuadPypeVersion(version=local_version)
    user_dir_version = bootstrap.find_quadpype_local_version(curr_version)
    prod_dir_version = bootstrap.find_quadpype_remote_version(curr_version)
    dev_mode = "python" in os.path.basename(sys.executable).lower()

    op_version_to_extract = None

    _print(">>> QuadPype Version Exists in User(local) Dir: {}".format(bool(user_dir_version)))
    _print(">>> QuadPype Version Exists in Prod(remote) Dir: {}".format(bool(prod_dir_version)))
    _print(">>> Dev Mode Enabled: {}".format(dev_mode))

    if prod_dir_version and not user_dir_version:
        # Need to copy the prod version into the correct user/artist directory
        # Get QuadPypeVersion() Object
        op_version_to_extract = prod_dir_version

    if not prod_dir_version and dev_mode and quadpype_path:
        # This isn't a released version, we are in developer mode
        # Generate the version, then copy it on the user/artist directory

        # Generate Zip
        debug_dir = Path(quadpype_path, "debug")
        op_version_to_extract = bootstrap.create_version_from_live_code(data_dir=debug_dir)

    if op_version_to_extract:
        _install_and_initialize_version(op_version_to_extract, delete_zip=False)

    # ------------------------------------------------------------------------
    # Find QuadPype versions
    # ------------------------------------------------------------------------
    quadpype_version = None
    # WARNING: Environment QUADPYPE_REPOS_ROOT may change if frozen QuadPype
    # is executed
    if getattr(sys, 'frozen', False):
        # find versions of QuadPype to be used with frozen code
        try:
            quadpype_version = _find_frozen_quadpype(use_version, use_staging)
        except QuadPypeVersionNotFound as exc:
            _boot_handle_missing_version(local_version, str(exc))
            sys.exit(1)
        except RuntimeError as e:
            # no version to run
            _print(f"!!! {e}", True)
            sys.exit(1)

        # validate version
        _print(f">>> Validating version in frozen [ {str(quadpype_version.path)} ]")
        result = bootstrap.validate_quadpype_version(quadpype_version.path)

        if not result[0]:
            _print(f"!!! Invalid version: {result[1]}", True)
            sys.exit(1)

        _print("--- version is valid")
    else:
        try:
            quadpype_version = _bootstrap_from_code(use_version)
        except QuadPypeVersionNotFound as exc:
            _boot_handle_missing_version(local_version, str(exc))
            sys.exit(1)

    # set this to point either to `python` from venv in case of live code
    # or to `quadpype` or `quadpype_console` in case of frozen code
    os.environ["QUADPYPE_EXECUTABLE"] = sys.executable

    # delete QuadPype module and it's submodules from cache so it is used from
    # specific version
    modules_to_del = [
        sys.modules.pop(module_name)
        for module_name in tuple(sys.modules)
        if module_name == "quadpype" or module_name.startswith("quadpype.")
    ]

    try:
        for module_name in modules_to_del:
            del sys.modules[module_name]
    except AttributeError:
        pass
    except KeyError:
        pass

    from quadpype.settings.lib import update_user_profile_on_startup

    # Do the program display popups to the users regarding updates or incompatibilities
    os.environ["QUADPYPE_VERSION_CHECK_POPUP"] = "False" if "disable_version_popup" in commands else "True"
    _print(">>> Loading user profile ...")
    user_profile = update_user_profile_on_startup()
    _print(">>> Loading environments ...")
    # QuadPype environments must be set before database module is imported
    _print("  - for the database ...")
    set_database_environments()
    _print("  - global QuadPype ...")
    set_quadpype_global_environments()
    _print("  - for modules ...")
    set_modules_environments()

    if not os.getenv("QUADPYPE_IGNORE_ZXP_UPDATE"):
        _print(">>> Check ZXP extensions ...")
        update_zxp_extensions(quadpype_version)

    assert quadpype_version, "Version path not defined."

    # print info when not running scripts defined in 'silent commands'
    if all(arg not in silent_commands for arg in sys.argv):
        from quadpype.lib import terminal as t
        from quadpype.version import __version__

        info = get_info(use_staging)
        info.insert(0, f">>> Using QuadPype from [ {str(quadpype_version.path.resolve())} ]")

        t_width = 20
        try:
            t_width = os.get_terminal_size().columns - 2
        except (ValueError, OSError):
            # running without terminal
            pass

        _header = f"*** QuadPype [{__version__}] "
        info.insert(0, _header + "-" * (t_width - len(_header)))

        for i in info:
            t.echo(i)

    from quadpype import cli
    try:
        cli.main(obj={}, prog_name="quadpype")
    except Exception:  # noqa
        exc_info = sys.exc_info()
        _print("!!! QuadPype crashed:", True)
        traceback.print_exception(*exc_info)
        sys.exit(1)


def get_info(use_staging=None) -> list:
    """Print additional information to console."""
    from quadpype.client.mongo import get_default_components
    try:
        from quadpype.lib.log import Logger
    except ImportError:
        # Backwards compatibility for 'PypeLogger'
        from quadpype.lib.log import PypeLogger as Logger

    components = get_default_components()

    inf = []
    if use_staging:
        inf.append(("QuadPype variant", "staging"))
    else:
        inf.append(("QuadPype variant", "production"))
    inf.extend([
        ("Running QuadPype from", os.getenv('QUADPYPE_REPOS_ROOT')),
        ("Using mongodb", components["host"])]
    )

    if os.getenv("FTRACK_SERVER"):
        inf.append(("Using FTrack at",
                    os.getenv("FTRACK_SERVER")))

    if os.getenv('DEADLINE_REST_URL'):
        inf.append(("Using Deadline webservice at",
                    os.getenv("DEADLINE_REST_URL")))

    if os.getenv('MUSTER_REST_URL'):
        inf.append(("Using Muster at",
                    os.getenv("MUSTER_REST_URL")))

    # Reinitialize
    Logger.initialize()

    mongo_components = get_default_components()
    if mongo_components["host"]:
        inf.extend([
            ("Logging to MongoDB", mongo_components["host"]),
            ("  - port", mongo_components["port"] or "<N/A>"),
            ("  - database", Logger.log_database_name),
            ("  - collection", Logger.log_collection_name),
            ("  - user", mongo_components["username"] or "<N/A>")
        ])
        if mongo_components["auth_db"]:
            inf.append(("  - auth source", mongo_components["auth_db"]))

    maximum = max(len(i[0]) for i in inf)
    formatted = []
    for info in inf:
        padding = (maximum - len(info[0])) + 1
        formatted.append(f'... {info[0]}:{" " * padding}[ {info[1]} ]')
    return formatted


if __name__ == "__main__":
    boot()
