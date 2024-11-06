"""Lib access to QuadPypeVersion from igniter.

Access to logic from igniter is available only for QuadPype processes.
Is meant to be able check QuadPype versions for studio. The logic is dependent
on igniter's inner logic of versions.

Keep in mind that all functions except 'get_installed_version' does not return
QuadPype version located in build but versions available in remote versions
repository or locally available.
"""

import os
import sys

import quadpype.version

from .python_module_tools import import_filepath


# ----------------------------------------
# Functions independent on QuadPypeVersion
# ----------------------------------------
def get_quadpype_version():
    """Version of pype that is currently used."""
    return quadpype.version.__version__


def get_build_version():
    """QuadPype version of build."""

    # Return QuadPype version if is running from code
    if not is_running_from_build():
        return get_quadpype_version()

    # Import `version.py` from build directory
    version_filepath = os.path.join(
        os.environ["QUADPYPE_ROOT"],
        "quadpype",
        "version.py"
    )
    if not os.path.exists(version_filepath):
        return None

    module = import_filepath(version_filepath, "quadpype_build_version")
    return getattr(module, "__version__", None)


def is_running_from_build():
    """Determine if current process is running from build or code.

    Returns:
        bool: True if running from build.
    """
    executable_path = os.environ["QUADPYPE_EXECUTABLE"]
    executable_filename = os.path.basename(executable_path)
    if "python" in executable_filename.lower():
        return False
    return True


def is_staging_enabled():
    return os.environ.get("QUADPYPE_USE_STAGING") == "1"


def is_running_locally():
    pype_executable = os.environ["QUADPYPE_EXECUTABLE"]
    executable_filename = os.path.basename(pype_executable)
    # On development, QuadPype is launched by Python
    return "python" in executable_filename.lower()


def is_running_staging():
    """Check if QuadPype is using the staging version.

    The function is based on 4 factors:
    - env 'QUADPYPE_IS_STAGING' is set
    - current production version
    - current staging version
    - use staging is enabled

    First checks for 'QUADPYPE_IS_STAGING' environment which can be set to '1'.
    The value should be set only when a process without access to
    QuadPypeVersion is launched (e.g. in DCCs). If current version is same
    as production version it is expected that it is not staging, and it
    doesn't matter what would 'is_staging_enabled' return. If current version
    is same as staging version it is expected we're in staging. In all other
    cases 'is_staging_enabled' is used as source of output value.

    Returns:
        bool: Using staging version or not.
    """

    if os.environ.get("QUADPYPE_IS_STAGING") == "1":
        return True

    if not op_version_control_available():
        return False

    from quadpype.settings import get_core_settings

    core_settings = get_core_settings()
    production_version = core_settings["production_version"]
    latest_version = None
    if not production_version or production_version == "latest":
        latest_version = get_latest_version(local=False, remote=True)
        production_version = latest_version

    current_version = get_quadpype_version()
    if current_version == production_version:
        return False

    staging_version = core_settings["staging_version"]
    if not staging_version or staging_version == "latest":
        if latest_version is None:
            latest_version = get_latest_version(local=False, remote=True)
        staging_version = latest_version

    if current_version == staging_version:
        return True

    return is_staging_enabled()


def is_version_checking_popup_enabled():
    value = os.getenv("QUADPYPE_VERSION_CHECK_POPUP", 'False').lower()
    if value == "true" or value == "1":
        return True
    return False


# ----------------------------------------
# Functions dependent on QuadPypeVersion
#   - Make sense to call only in QuadPype process
# ----------------------------------------
def get_QuadPypeVersion():
    """Access to QuadPypeVersion class stored in sys modules."""
    return sys.modules.get("QuadPypeVersion")


def op_version_control_available():
    """Check if current process has access to QuadPypeVersion."""
    if get_QuadPypeVersion() is None:
        return False
    return True


def get_installed_version():
    """Get QuadPype version inside build.

    This version is not returned by any other functions here.
    """
    if op_version_control_available():
        return get_QuadPypeVersion().get_installed_version()
    return None


def get_available_versions(*args, **kwargs):
    """Get list of available versions."""
    if op_version_control_available():
        return get_QuadPypeVersion().get_available_versions(
            *args, **kwargs
        )
    return None


def quadpype_path_is_set():
    """QuadPype repository path is set in settings."""
    if op_version_control_available():
        return get_QuadPypeVersion().quadpype_path_is_set()
    return None


def quadpype_path_is_accessible():
    """QuadPype version repository path can be accessed."""
    if op_version_control_available():
        return get_QuadPypeVersion().quadpype_path_is_accessible()
    return None


def get_local_versions(*args, **kwargs):
    """QuadPype versions available on this workstation."""
    if op_version_control_available():
        return get_QuadPypeVersion().get_local_versions(*args, **kwargs)
    return None


def get_remote_versions(*args, **kwargs):
    """QuadPype versions in repository path."""
    if op_version_control_available():
        return get_QuadPypeVersion().get_remote_versions(*args, **kwargs)
    return None


def get_latest_version(local=None, remote=None):
    """Get latest version from repository path."""

    if op_version_control_available():
        return get_QuadPypeVersion().get_latest_version(
            local=local,
            remote=remote
        )
    return None


def get_expected_studio_version(staging=None):
    """Expected production or staging version in studio."""
    if op_version_control_available():
        if staging is None:
            staging = is_staging_enabled()
        return get_QuadPypeVersion().get_expected_studio_version(staging)
    return None


def get_expected_version(staging=None):
    expected_version = get_expected_studio_version(staging)
    if expected_version is None:
        # Look for latest if expected version is not set in settings
        expected_version = get_latest_version(
            local=False,
            remote=True
        )
    return expected_version


def is_current_version_studio_latest():
    """Is currently running QuadPype version which is defined by studio.

    It is not recommended to ask in each process as there may be situations
    when older QuadPype should be used. For example on farm. But it does make
    sense in processes that can run for a long time.

    Returns:
        None: Can't determine. e.g. when running from code or the build is
            too old.
        bool: True when is using studio
    """
    output = None
    # Skip if is not running from build or build does not support version
    #   control or path to folder with zip files is not accessible
    if (
        not is_running_from_build()
        or not op_version_control_available()
        or not quadpype_path_is_accessible()
    ):
        return output

    # Get QuadPypeVersion class
    QuadPypeVersion = get_QuadPypeVersion()
    # Convert current version to QuadPypeVersion object
    current_version = QuadPypeVersion(version=get_quadpype_version())

    # Get expected version (from settings)
    expected_version = get_expected_version()
    # Check if current version is expected version
    return current_version == expected_version


def is_current_version_higher_than_expected():
    """Is current QuadPype version higher than version defined by studio.

    Returns:
        None: Can't determine. e.g. when running from code or the build is
            too old.
        bool: True when is higher than studio version.
    """
    output = None
    # Skip if is not running from build or build does not support version
    #   control or path to folder with zip files is not accessible
    if (
        not is_running_from_build()
        or not op_version_control_available()
        or not quadpype_path_is_accessible()
    ):
        return output

    # Get QuadPypeVersion class
    QuadPypeVersion = get_QuadPypeVersion()
    # Convert current version to QuadPypeVersion object
    current_version = QuadPypeVersion(version=get_quadpype_version())

    # Get expected version (from settings)
    expected_version = get_expected_version()
    # Check if current version is expected version
    return current_version > expected_version
