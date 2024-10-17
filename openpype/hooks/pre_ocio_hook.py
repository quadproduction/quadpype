from openpype.settings import PROJECT_SETTINGS_KEY, SYSTEM_SETTINGS_KEY
from openpype.lib.applications import PreLaunchHook

from openpype.pipeline.colorspace import get_imageio_config
from openpype.pipeline.template_data import get_template_data_with_names


class OCIOEnvHook(PreLaunchHook):
    """Set OCIO environment variable for hosts that use OpenColorIO."""

    order = 0
    hosts = {
        "substancepainter",
        "fusion",
        "blender",
        "aftereffects",
        "max",
        "houdini",
        "maya",
        "nuke",
        "hiero",
        "resolve",
        "openrv"
    }
    launch_types = set()

    def execute(self):
        """Hook entry method."""

        template_data = get_template_data_with_names(
            project_name=self.data["project_name"],
            asset_name=self.data["asset_name"],
            task_name=self.data["task_name"],
            host_name=self.host_name,
            system_settings=self.data[SYSTEM_SETTINGS_KEY]
        )

        config_data = get_imageio_config(
            project_name=self.data["project_name"],
            host_name=self.host_name,
            project_settings=self.data[PROJECT_SETTINGS_KEY],
            anatomy_data=template_data,
            anatomy=self.data["anatomy"],
            env=self.launch_context.env,
        )

        if config_data:
            ocio_path = config_data["path"]

            if self.host_name in ["nuke", "hiero"]:
                ocio_path = ocio_path.replace("\\", "/")

            self.log.info(
                f"Setting OCIO environment to config path: {ocio_path}")

            self.launch_context.env["OCIO"] = ocio_path
        else:
            self.log.debug("OCIO not set or enabled")
