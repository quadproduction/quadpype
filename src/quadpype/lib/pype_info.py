import os
import json
import datetime
import platform
import getpass
import socket

from quadpype.settings.lib import get_user_profile
from .execute import get_quadpype_execute_args
from .user_settings import get_user_id
from .quadpype_version import (
    is_running_from_build,
    get_quadpype_version,
    get_build_version
)


def get_quadpype_info():
    """Information about currently used Pype process."""
    executable_args = get_quadpype_execute_args()
    if is_running_from_build():
        version_type = "build"
    else:
        version_type = "code"

    return {
        "build_version": get_build_version(),
        "version": get_quadpype_version(),
        "version_type": version_type,
        "executable": executable_args[-1],
        "pype_root": os.environ["QUADPYPE_REPOS_ROOT"],
        "mongo_url": os.environ["QUADPYPE_MONGO"]
    }


def get_workstation_info():
    """Basic information about workstation."""
    host_name = socket.gethostname()
    try:
        host_ip = socket.gethostbyname(host_name)
    except socket.gaierror:
        host_ip = "127.0.0.1"

    return {
        "workstation_name": host_name,
        "host_ip": host_ip,
        "username": getpass.getuser(),
        "system_name": platform.system()
    }


def get_all_current_info():
    """All information about current process in one dictionary."""

    output = {
        "quadpype": get_quadpype_info(),
        "env": os.environ.copy(),
    }
    output.update(get_user_profile())
    return output


def extract_pype_info_to_file(dirpath):
    """Extract all current info to a file.

    It is possible to define onpy directory path. Filename is concatenated with
    pype version, workstation site id and timestamp.

    Args:
        dirpath (str): Path to directory where file will be stored.

    Returns:
        filepath (str): Full path to file where data were extracted.
    """
    filename = "{}_{}_{}.json".format(
        get_quadpype_version(),
        get_user_id(),
        datetime.datetime.now().strftime("%y%m%d%H%M%S")
    )
    filepath = os.path.join(dirpath, filename)
    data = get_all_current_info()
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)

    with open(filepath, "w") as file_stream:
        json.dump(data, file_stream, indent=4)
    return filepath
