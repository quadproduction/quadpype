"""Lib access to PackageVersion from igniter.

Access to logic from igniter is available only for QuadPype processes.
Is meant to be able to check QuadPype versions for studio. The logic is dependent
on igniter's inner logic of versions.
"""

import os
from pathlib import Path

import quadpype.version

from .python_module_tools import import_filepath

from .version import (
    PackageVersion,
    get_package
)
from igniter.settings import (
    get_expected_studio_version_str
)


# ----------------------------------------
# Functions independent on PackageVersion
# ----------------------------------------
def get_quadpype_version():
    """Version of QuadPype that is currently used."""
    return quadpype.version.__version__


def get_build_version():
    """QuadPype version of build."""

    # Return QuadPype version if it is running from code
    if is_running_locally():
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
    return os.getenv("QUADPYPE_USE_STAGING") == "1"


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
    PackageVersion is launched (e.g. in DCCs). If current version is same
    as production version it is expected that it is not staging, and it
    doesn't matter what would 'is_staging_enabled' return. If current version
    is same as staging version it is expected we're in staging. In all other
    cases 'is_staging_enabled' is used as source of output value.

    Returns:
        bool: Using staging version or not.
    """

    if os.getenv("QUADPYPE_IS_STAGING") == "1":
        return True

    from quadpype.settings import get_core_settings

    core_settings = get_core_settings()
    production_version = core_settings["production_version"]
    latest_version = None
    if not production_version or production_version == "latest":
        latest_version = get_latest_version(from_local=False, from_remote=True)
        production_version = latest_version

    current_version = get_quadpype_version()
    if current_version == production_version:
        return False

    staging_version = core_settings["staging_version"]
    if not staging_version or staging_version == "latest":
        if latest_version is None:
            latest_version = get_latest_version(from_local=False, from_remote=True)
        staging_version = latest_version

    if current_version == staging_version:
        return True

    return is_staging_enabled()


# ----------------------------------------
# Functions dependent on PackageVersion
#   - Make sense to call only in QuadPype process
# ----------------------------------------
def get_available_versions(*args, **kwargs):
    """Get the list of available versions."""
    return get_package("quadpype").get_available_versions(*args, **kwargs)


def quadpype_path_is_accessible():
    """QuadPype version repository path can be accessed."""
    return os.getenv("QUADPYPE_PATH") and Path(os.getenv("QUADPYPE_PATH")).exists()


def get_local_versions():
    """QuadPype versions available on this workstation."""
    return get_package("quadpype").get_local_versions()


def get_remote_versions():
    """QuadPype versions in repository path."""
    return get_package("quadpype").get_remote_versions()


def get_latest_version(from_local=None, from_remote=None):
    """Get latest version from repository path."""
    return get_package("quadpype").get_latest_version(from_local=from_local,from_remote=from_remote)


def get_expected_version(staging=None):
    expected_version_str = get_expected_studio_version_str(staging)
    expected_version = PackageVersion(version=expected_version_str) if expected_version_str else None
    if expected_version is None:
        # Look for latest if expected version is not set in settings
        expected_version = get_latest_version(
            from_local=False,
            from_remote=True
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
    # Skip if it is not running from build or build does not support version
    #   control or path to folder with zip files is not accessible
    if (
        is_running_locally()
        or not quadpype_path_is_accessible()
    ):
        return output

    # Convert current version to PackageVersion object
    current_version = PackageVersion(version=get_quadpype_version())

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
    # Skip if it is not running from build or build does not support version
    #   control or path to folder with zip files is not accessible
    if (
        is_running_locally()
        or not quadpype_path_is_accessible()
    ):
        return output

    # Convert current version to PackageVersion object
    current_version = PackageVersion(version=get_quadpype_version())

    # Get expected version (from settings)
    expected_version = get_expected_version()
    # Check if current version is expected version
    return current_version > expected_version
