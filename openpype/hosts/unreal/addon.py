import os
import re
from quadpype.modules import IHostAddon, QuadPypeModule

UNREAL_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class UnrealAddon(QuadPypeModule, IHostAddon):
    name = "unreal"
    host_name = "unreal"

    def initialize(self, module_settings):
        self.enabled = True

    def get_global_environments(self):
        return {
            "AYON_UNREAL_ROOT": UNREAL_ROOT_DIR,
        }

    def add_implementation_envs(self, env, app):
        """Modify environments to contain all required for implementation."""
        # Set QUADPYPE_UNREAL_PLUGIN required for Unreal implementation
        # Imports are in this method for Python 2 compatiblity of an addon
        from pathlib import Path

        from .lib import get_compatible_integration

        from quadpype.widgets.message_window import Window

        pattern = re.compile(r'^\d+-\d+$')

        if not pattern.match(app.name):
            msg = (
                "Unreal application key in the settings must be in format"
                "'5-0' or '5-1'"
            )
            Window(
                parent=None,
                title="Unreal application name format",
                message=msg,
                level="critical")
            raise ValueError(msg)

        ue_version = app.name.replace("-", ".")
        unreal_plugin_path = os.path.join(
            UNREAL_ROOT_DIR, "integration", "UE_{}".format(ue_version), "Ayon"
        )
        if not Path(unreal_plugin_path).exists():
            compatible_versions = get_compatible_integration(
                ue_version, Path(UNREAL_ROOT_DIR) / "integration"
            )
            if compatible_versions:
                unreal_plugin_path = compatible_versions[-1] / "Ayon"
                unreal_plugin_path = unreal_plugin_path.as_posix()

        if not env.get("QUADPYPE_UNREAL_PLUGIN") or \
                env.get("QUADPYPE_UNREAL_PLUGIN") != unreal_plugin_path:
            env["QUADPYPE_UNREAL_PLUGIN"] = unreal_plugin_path

        # Set default environments if are not set via settings
        defaults = {
            "QUADPYPE_LOG_NO_COLORS": "True",
            "UE_PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        }
        for key, value in defaults.items():
            if not env.get(key):
                env[key] = value

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(UNREAL_ROOT_DIR, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".uproject"]
