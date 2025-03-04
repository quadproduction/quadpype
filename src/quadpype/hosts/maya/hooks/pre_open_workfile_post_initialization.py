from quadpype.settings import PROJECT_SETTINGS_KEY
from quadpype.lib.applications import PreLaunchHook, LaunchTypes


class MayaPreOpenWorkfilePostInitialization(PreLaunchHook):
    """Define whether open last workfile should run post initialize."""

    # Before AddLastWorkfileToLaunchArgs.
    order = 9
    app_groups = {"maya"}
    launch_types = {LaunchTypes.local}

    def execute(self):

        # Ignore if there's no last workfile to start.
        if not self.data.get("start_last_workfile"):
            return

        maya_settings = self.data[PROJECT_SETTINGS_KEY]["maya"]
        enabled = maya_settings["open_workfile_post_initialization"]
        if enabled:
            # Force disable the `AddLastWorkfileToLaunchArgs`.
            self.data.pop("start_last_workfile")

            self.log.debug("Opening workfile post initialization.")
            key = "QUADPYPE_OPEN_WORKFILE_POST_INITIALIZATION"
            self.launch_context.env[key] = "1"
