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
│   2) Test user data directory                         │  │
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

Attributes:
    silent_commands (set): list of commands for which we won't print QuadPype
        info header.
"""
import os
import re
import sys
import platform
import traceback
import subprocess
from pathlib import Path

silent_mode = False

# QUADPYPE_ROOT is a variable pointing to build (or code) directory
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


term = blessed.Terminal() if sys.__stdout__ else None


def _print(msg: str, force=False):
    if silent_mode and not force:
        return

    if not term:
        header = ""
    elif msg.startswith("!!! "):
        header = term.orangered2("!!! ")
        msg = msg[4:]
    elif msg.startswith(">>> "):
        header = term.aquamarine3(">>> ")
        msg = msg[4:]
    elif msg.startswith("--- "):
        header = term.darkolivegreen3("--- ")
        msg = msg[4:]
    elif msg.startswith("*** "):
        header = term.gold("*** ")
        msg = msg[4:]
    elif msg.startswith("  - "):
        header = term.wheat("  - ")
        msg = msg[4:]
    elif msg.startswith("  . "):
        header = term.tan("  . ")
        msg = msg[4:]
    elif msg.startswith("     - "):
        header = term.seagreen3("     - ")
        msg = msg[7:]
    elif msg.startswith("     ! "):
        header = term.goldenrod("     ! ")
        msg = msg[7:]
    elif msg.startswith("     * "):
        header = term.aquamarine1("     * ")
        msg = msg[7:]
    elif msg.startswith("    "):
        header = term.darkseagreen3("    ")
        msg = msg[4:]
    else:
        header = term.darkolivegreen3("--- ")

    print("{}{}".format(header, msg))


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
    verbose_elem_index = sys.argv.index("--verbose")
    sys.argv.pop(verbose_elem_index)
    if verbose_elem_index < len(sys.argv):
        value = sys.argv.pop(verbose_elem_index)
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
    elem_index = sys.argv.index("--additional-env-file")
    sys.argv.pop(elem_index)
    if elem_index < len(sys.argv):
        env_file_path = sys.argv.pop(elem_index)
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

import igniter
from igniter.version_classes import (
    PackageHandler,
    PackageVersion
)
from igniter.registry import (
    QuadPypeSecureRegistry
)
from igniter.zxp_utils import (
    get_zxp_extensions_to_update,
    update_zxp_extensions
)

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


def run_disk_mapping_commands(global_settings):
    """ Run disk mapping command

        Used to map shared disk for QuadPype to pull codebase.
    """

    low_platform = platform.system().lower()
    disk_mapping = global_settings.get("disk_mapping")
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


def set_avalon_environments():
    """Set avalon specific environments.

    These are non-modifiable environments for avalon workflow that must be set
    before avalon module is imported because avalon works with globals set with
    environment variables.
    """

    avalon_db = os.getenv("AVALON_DB") or "avalon"  # for tests
    os.environ.update({
        # Mongo DB name where avalon docs are stored
        "AVALON_DB": avalon_db,
        # Name of config
        "AVALON_LABEL": "QuadPype"
    })


def _update_zxp_extensions(quadpype_version, global_settings):
    zxp_hosts_to_update = get_zxp_extensions_to_update(quadpype_version, global_settings)
    if not zxp_hosts_to_update:
        return

    in_headless_mode = os.getenv("QUADPYPE_HEADLESS_MODE") == "1"
    if in_headless_mode:
        update_zxp_extensions(quadpype_version, zxp_hosts_to_update)
    else:
        igniter.open_zxp_update_window(quadpype_version, zxp_hosts_to_update)


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


def validate_thirdparty_binaries():
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
    """Check the existence of third party executables."""
    low_platform = platform.system().lower()
    binary_vendors_dir = Path(os.environ["QUADPYPE_ROOT"]).joinpath("vendor", "bin")

    ext_list = [""]  # Add no extension (for linux)
    ext_list.extend(os.environ['PATHEXT'].lower().split(os.pathsep))

    error_msg = (
        "Missing binary dependency {}. Please fetch thirdparty dependencies."
    )
    # Validate existence of FFMPEG
    ffmpeg_dir_path = binary_vendors_dir.joinpath("ffmpeg", low_platform)
    if low_platform == "windows":
        ffmpeg_dir_path = ffmpeg_dir_path.joinpath("bin")

    ffmpeg_binary_path = ffmpeg_dir_path.joinpath("ffmpeg")

    binary_exists = False
    for ext in ext_list:
        test_ffmpeg_binary_path = ffmpeg_binary_path.with_suffix(ext)
        if test_ffmpeg_binary_path.exists():
            binary_exists = True
            break
    if not binary_exists:
        raise RuntimeError(error_msg.format("FFMPEG"))

    # Validate existence of OpenImageIO (not on macOS)
    if low_platform == "darwin":
        return

    oiiotool_dir_path = binary_vendors_dir.joinpath("oiio", low_platform)
    if low_platform == "linux":
        oiiotool_dir_path = oiiotool_dir_path.joinpath("bin")

    oiiotool_binary_path = oiiotool_dir_path.joinpath("oiiotool")

    binary_exists = False
    for ext in ext_list:
        test_oiiotool_binary_path = oiiotool_binary_path.with_suffix(ext)
        if test_oiiotool_binary_path.exists():
            binary_exists = True
            break

    if not binary_exists:
        raise RuntimeError(error_msg.format("OpenImageIO"))


def _process_arguments() -> tuple:
    """Process command line arguments.

    Returns:
        tuple: Return tuple with specific version to use (if any) and flag
            to prioritize staging (if set)
    """
    # check for `--use-version=3.0.0` argument
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

        return_code = igniter.ask_database_connection_string(_print)
        if return_code != 7:
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
    secure_registry = QuadPypeSecureRegistry("mongodb")
    quadpype_mongo = os.getenv("QUADPYPE_MONGO", None)
    if not quadpype_mongo:
        # try system keyring
        try:
            quadpype_mongo = secure_registry.get_item(
                "quadpypeMongo"
            )
        except ValueError:
            pass

    if quadpype_mongo:
        from quadpype.client.mongo import validate_mongo_connection
        try:
            validate_mongo_connection(quadpype_mongo)
        except Exception as e:
            _print(str(e))
            quadpype_mongo = None

    if not quadpype_mongo:
        _print("*** No DB connection string specified.")
        if os.getenv("QUADPYPE_HEADLESS_MODE") == "1":
            _print("!!! Cannot open Igniter dialog in headless mode.", True)
            _print(("!!! Please use `QUADPYPE_MONGO` to specify "
                    "server address."), True)
            sys.exit(1)
        _print("--- launching setup UI ...")

        result = igniter.ask_database_connection_string(_print)
        if result != 7:
            raise RuntimeError("MongoDB URL was not defined")

        quadpype_mongo = os.getenv("QUADPYPE_MONGO")
        if not quadpype_mongo:
            try:
                quadpype_mongo = secure_registry.get_item(
                    "quadpypeMongo")
            except ValueError as e:
                raise RuntimeError("Missing MongoDB url") from e

    return quadpype_mongo


def _initialize_environment(quadpype_version: PackageVersion) -> None:
    version_path = quadpype_version.path
    if not version_path:
        _print(f"!!! Version {quadpype_version} doesn't have path set.")
        raise ValueError("No path set in specified QuadPype version.")
    os.environ["QUADPYPE_VERSION"] = str(quadpype_version)
    # set QUADPYPE_REPOS_ROOT to point to currently used QuadPype version.
    os.environ["QUADPYPE_REPOS_ROOT"] = os.path.normpath(
        version_path.as_posix()
    )
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


def _boot_print_versions(quadpype_package):
    versions = quadpype_package.get_available_versions()

    compatible_with = quadpype_package.running_version
    if "--all" in sys.argv:
        _print("--- Showing all version (even those not compatible).")
    else:
        _print(("--- Showing only compatible versions "
                f"with [ {compatible_with.major}.{compatible_with.minor} ]"))

    versions_to_display = [
        version for version in versions
        if version.is_compatible(compatible_with)
    ]

    list_versions(versions_to_display, compatible_with)


def _initialize_package_manager(database_url, version_str):
    """Initialize the Package Manager and add the registered AddOns."""
    from quadpype.lib.version import create_package_manager, PackageHandler
    from quadpype.settings.lib import (
        get_core_settings_no_handler,
        get_quadpype_local_dir_path,
        get_quadpype_remote_dir_paths
    )

    core_settings = get_core_settings_no_handler(database_url)

    package_manager = create_package_manager()

    quadpype_package = PackageHandler(
        pkg_name="quadpype",
        local_dir_path=get_quadpype_local_dir_path(core_settings),
        remote_dir_paths=get_quadpype_remote_dir_paths(core_settings),
        running_version_str=version_str,
        retrieve_locally=True,
        install_dir_path=os.getenv("QUADPYPE_ROOT")
    )
    package_manager.add_package(quadpype_package)

    return package_manager


def _load_addons(package_manager, global_settings, use_staging):
    from quadpype.lib.version import AddOnHandler, MODULES_SETTINGS_KEY
    from appdirs import user_data_dir

    addon_settings = global_settings.get(MODULES_SETTINGS_KEY, {}).get("custom_addons", {})
    local_dir = Path(user_data_dir("quadpype", "quad")) / "addons"

    if not local_dir.exists():
        local_dir.mkdir(parents=True, exist_ok=True)

    for addon_setting in addon_settings:
        addon_package_name = addon_setting.get("package_name", "").strip()
        if not addon_package_name:
            _print("!!! A custom add-on package name is empty, add-on skipped.")
            continue

        addon_local_dir = local_dir / addon_package_name
        if not addon_local_dir.exists():
            local_dir.mkdir(parents=True, exist_ok=True)

        version_key = "staging_version" if use_staging else "version"

        remote_dir_paths = addon_setting.get("package_remote_dirs", {}).get(platform.system().lower(), [])
        remote_dir_paths = [Path(curr_path_str) for curr_path_str in remote_dir_paths]

        addon_package = AddOnHandler(
            pkg_name=addon_setting.get("package_name"),
            local_dir_path=addon_local_dir,
            remote_dir_paths=remote_dir_paths,
            running_version_str=addon_setting.get(version_key, ""),
            retrieve_locally=addon_setting.get("retrieve_locally", False),
        )
        package_manager.add_package(addon_package)


def boot():
    """Bootstrap QuadPype."""
    global silent_mode
    if any(arg in silent_commands for arg in sys.argv):
        silent_mode = True

    # ------------------------------------------------------------------------
    # Set environment to QuadPype root path
    # ------------------------------------------------------------------------
    os.environ["QUADPYPE_ROOT"] = QUADPYPE_ROOT

    # set this to point either to `python` from venv in case of live code
    # or to `quadpype` or `quadpype_console` in case of frozen code
    os.environ["QUADPYPE_EXECUTABLE"] = sys.executable

    # ------------------------------------------------------------------------
    # Do necessary startup validations
    # ------------------------------------------------------------------------
    validate_thirdparty_binaries()

    # ------------------------------------------------------------------------
    # Process arguments
    # ------------------------------------------------------------------------

    use_version, commands = _process_arguments()
    use_staging = os.getenv("QUADPYPE_USE_STAGING") == "1"
    local_version = PackageHandler.get_package_version_from_dir("quadpype", os.getenv("QUADPYPE_ROOT"))
    is_dev_mode = "python" in os.path.basename(sys.executable).lower()

    if os.getenv("QUADPYPE_VERSION"):
        if use_version:
            _print(("*** environment variable QUADPYPE_VERSION"
                    "is overridden by command line argument."))
        else:
            _print(">>> Version set by environment variable")
            use_version = os.getenv("QUADPYPE_VERSION")

    # If QuadPype has been started in DEV mode and no version has been specified
    # The local code version is used
    if is_dev_mode and not use_version:
        use_version = local_version

    # ------------------------------------------------------------------------
    # Determine mongodb connection
    # ------------------------------------------------------------------------

    try:
        quadpype_mongo = _determine_mongodb()
    except RuntimeError as e:
        # without mongodb url we are done.
        _print(f"!!! {e}", True)
        sys.exit(1)

    os.environ["QUADPYPE_MONGO"] = quadpype_mongo
    # name of QuadPype database
    os.environ["QUADPYPE_DATABASE_NAME"] = \
        os.getenv("QUADPYPE_DATABASE_NAME") or "quadpype"

    if os.getenv("IS_TEST") == "1":
        # change source DBs to predefined ones set for automatic testing
        if "_tests" not in os.environ["QUADPYPE_DATABASE_NAME"]:
            os.environ["QUADPYPE_DATABASE_NAME"] += "_tests"
        avalon_db = os.getenv("AVALON_DB") or "avalon"
        if "_tests" not in avalon_db:
            os.environ["AVALON_DB"] = avalon_db + "_tests"

    from quadpype.settings.lib import (
        get_global_settings_and_version_no_handler,
        get_expected_studio_version_str,
    )

    if not use_version:
        # Check if a specific version as been saved in the core settings
        use_version = get_expected_studio_version_str(use_staging)

    # Create the Package Manager and add the QuadPype package & the registered AddOns
    package_manager = _initialize_package_manager(quadpype_mongo, use_version)

    # Ensure the settings will be retrieved from the correct running version
    running_version = package_manager["quadpype"].running_version

    # Get the full settings with the final version that will be used
    global_settings = get_global_settings_and_version_no_handler(
        quadpype_mongo,
        str(running_version)
    )

    # Add the Add-ons to the Package Manager
    _load_addons(package_manager, global_settings, use_staging)

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

    if "validate" in commands:
        valid = package_manager["quadpype"].validate_checksums(QUADPYPE_ROOT)[0]
        sys.exit(0 if valid else 1)

    if not package_manager["quadpype"].remote_dir_paths:
        _print("*** Cannot get QuadPype patches directory path from database.")

    if not os.getenv("QUADPYPE_PATH") and package_manager["quadpype"].remote_dir_paths:
        os.environ["QUADPYPE_PATH"] = str(package_manager["quadpype"].get_accessible_remote_dir_path())

    if "print_versions" in commands:
        _boot_print_versions(package_manager["quadpype"])
        sys.exit(0)

    _print(">>> Dev Mode Enabled: {}".format(is_dev_mode))
    if is_dev_mode:
        _print(">>> [DEV] The version used is the current local code.")

    _initialize_environment(running_version)

    # delete QuadPype module and it's submodules from cache so it is used from
    # specific version
    modules_to_del = [
        module_name
        for module_name in sys.modules.keys()
        if module_name == "quadpype" or module_name.startswith("quadpype.")
    ]

    try:
        for module_name in modules_to_del:
            del sys.modules[module_name]
    except AttributeError:
        pass
    except KeyError:
        pass

    # Since we clear the Python modules caches,
    # we need to re-set the package manager global variable
    from quadpype.lib.version import set_package_manager
    set_package_manager(package_manager)

    from quadpype.lib.user import update_user_profile_on_startup

    # Do the program display popups to the users regarding updates or incompatibilities
    _print(">>> Loading user profile ...")
    update_user_profile_on_startup()
    _print(">>> Loading environments ...")
    # Avalon environments must be set before avalon module is imported
    _print("  - for Avalon ...")
    set_avalon_environments()
    _print("  - global QuadPype ...")
    set_quadpype_global_environments()
    _print("  - for modules ...")
    set_modules_environments()

    if not os.getenv("QUADPYPE_IGNORE_ZXP_UPDATE"):
        _print(">>> Check ZXP extensions ...")
        _update_zxp_extensions(package_manager["quadpype"].running_version, global_settings)

    # print info when not running scripts defined in 'silent commands'
    if all(arg not in silent_commands for arg in sys.argv):
        from quadpype.lib import terminal as t
        from quadpype.version import __version__

        info = get_info(use_staging)
        running_version_fullpath = str(package_manager["quadpype"].running_version.path.resolve())
        info.insert(0, f">>> Using QuadPype from [ {running_version_fullpath} ]")

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
    from quadpype.lib.log import Logger

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
