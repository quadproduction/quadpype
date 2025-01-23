import os

from quadpype import PLUGINS_DIR
from quadpype.pipeline import (
    register_launcher_action_path,
)


def register_actions_from_paths(paths):
    if not paths:
        return

    for path in paths:
        if not path:
            continue

        if path.startswith("."):
            print((
                "BUG: Relative paths are not allowed for security reasons. {}"
            ).format(path))
            continue

        if not os.path.exists(path):
            print("Path was not found: {}".format(path))
            continue

        register_launcher_action_path(path)


def register_config_actions():
    """Register actions from the configuration for Launcher"""

    actions_dir = os.path.join(PLUGINS_DIR, "actions")
    if os.path.exists(actions_dir):
        register_actions_from_paths([actions_dir])


def register_environment_actions():
    """Register actions from AVALON_ACTIONS for Launcher."""

    paths_str = os.getenv("AVALON_ACTIONS") or ""
    register_actions_from_paths(paths_str.split(os.pathsep))
