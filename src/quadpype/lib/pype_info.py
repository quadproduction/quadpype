import os
import json
from datetime import datetime, timezone

from .execute import get_quadpype_execute_args
from .user import get_user_id, get_user_profile
from .version_utils import (
    is_running_from_build,
    get_quadpype_version,
    get_build_version
)


def get_quadpype_info():
    """Information about currently used QuadPype process."""
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





def get_all_current_info():
    """All information about current process in one dictionary."""

    output = {
        "quadpype": get_quadpype_info(),
        "env": os.environ.copy(),
    }
    output.update(get_user_profile())
    return output


def extract_pype_info_to_file(dir_path):
    """Extract all current info to a file.

    It is possible to define onpy directory path. Filename is concatenated with
    QuadPype version, workstation site id and timestamp.

    Args:
        dir_path (str): Path to directory where file will be stored.

    Returns:
        filepath (str): Full path to file where data were extracted.
    """
    filename = "{}_{}_{}.json".format(
        get_quadpype_version(),
        get_user_id(),
        datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    )
    filepath = os.path.join(dir_path, filename)
    data = get_all_current_info()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    with open(filepath, "w") as file_stream:
        json.dump(data, file_stream, indent=4)
    return filepath
