import os
from quadpype.lib.env_tools import env_value_to_bool
from quadpype.modules import QuadPypeModule, IHostAddon

BLENDER_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class BlenderAddon(QuadPypeModule, IHostAddon):
    name = "blender"
    host_name = "blender"

    def initialize(self, module_settings):
        self.enabled = True

    def add_implementation_envs(self, env, _app):
        """Modify environments to contain all required for implementation."""
        # Prepare path to implementation script
        implementation_script_path = os.path.join(
            BLENDER_ROOT_DIR,
            "blender_addon"
        )

        # Add blender implementation script path to PYTHONPATH
        python_path = env.get("PYTHONPATH") or ""
        python_path_parts = [
            path
            for path in python_path.split(os.pathsep)
            if path
        ]
        python_path_parts.insert(0, implementation_script_path)
        env["PYTHONPATH"] = os.pathsep.join(python_path_parts)

        # If `QUADPYPE_BLENDER_USE_SYSTEM_PATH` is set use `BLENDER_SYSTEM_PATH`
        # to initialize the Blender startup environment, otherwise use the
        # `BLENDER_USER_PATH`.
        use_system_path = env_value_to_bool("QUADPYPE_BLENDER_USE_SYSTEM_PATH")
        if use_system_path:
            self._configure_blender_system_paths(
                env, implementation_script_path
            )
        else:
            # Old versions of Blender had broken BLENDER_SYSTEM_SCRIPTS
            # nor supported multiple paths for it. See:
            # https://projects.blender.org/blender/blender/issues/127013
            self._configure_blender_user_paths(env, implementation_script_path)

        # Define Qt binding if not defined
        env.pop("QT_PREFERRED_BINDING", None)

    def _configure_blender_user_paths(
        self, env: dict, implementation_script_path: str
    ):
        """Modify BLENDER_USER_SCRIPTS to configure QUADPYPE startup"""
        previous_user_scripts = set()
        # Implementation path is added to set for easier paths check inside
        #   loops - will be removed at the end
        previous_user_scripts.add(implementation_script_path)

        quadpype_blender_user_scripts = (
            env.get("QUADPYPE_BLENDER_USER_SCRIPTS") or ""
        )
        for path in quadpype_blender_user_scripts.split(os.pathsep):
            if path:
                previous_user_scripts.add(os.path.normpath(path))

        blender_user_scripts = env.get("BLENDER_USER_SCRIPTS") or ""
        for path in blender_user_scripts.split(os.pathsep):
            if path:
                previous_user_scripts.add(os.path.normpath(path))

        # Remove implementation path from user script paths as is set to
        #   `BLENDER_USER_SCRIPTS`
        previous_user_scripts.remove(implementation_script_path)
        env["BLENDER_USER_SCRIPTS"] = implementation_script_path

        # Set custom user scripts env
        env["QUADPYPE_BLENDER_USER_SCRIPTS"] = os.pathsep.join(
            previous_user_scripts
        )

    def _configure_blender_system_paths(
        self, env: dict, implementation_script_path: str
    ):
        """Modify BLENDER_SYSTEM_SCRIPTS to configure QUADPYPE startup.

        This would only work with Blender 4.4+ due to new changes implemented
        to `BLENDER_SYSTEM_SCRIPTS` functionality starting with that release.
        """
        paths = [implementation_script_path]

        # Support older QUADPYPE_BLENDER_USER_SCRIPTS for compatibility
        if env.get("QUADPYPE_BLENDER_USER_SCRIPTS"):
            # Note that we `pop` the QUADPYPE_BLENDER_USER_SCRIPTS to avoid
            # the legacy post-Blender launch logic script to trigger which
            # is incompatible with Blender 4.4+
            paths.append(env.pop("QUADPYPE_BLENDER_USER_SCRIPTS"))

        # Preserve existing BLENDER_SYSTEM_SCRIPTS, append them at the end
        if env.get("BLENDER_SYSTEM_SCRIPTS"):
            paths.append(env.get("BLENDER_SYSTEM_SCRIPTS"))

        # Set custom user scripts env
        env["BLENDER_SYSTEM_SCRIPTS"] = os.pathsep.join(paths)

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(BLENDER_ROOT_DIR, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".blend"]
