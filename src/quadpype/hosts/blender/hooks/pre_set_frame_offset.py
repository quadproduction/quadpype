from pathlib import Path

from quadpype.hosts.blender.hooks import pre_add_run_python_script_arg
from quadpype.lib import PreLaunchHook


class SetFrameOffset(PreLaunchHook):
    """Set Frame Offset calculated from Custom Frame Start from project settings
    to scene properties.
    """

    order = pre_add_run_python_script_arg.AddPythonScriptToLaunchArgs.order - 1
    app_groups = [
        "blender",
    ]
    script_file_name = 'set_frame_offset.py'

    def execute(self):
        hooks_folder_path = Path(__file__).parent
        custom_script_folder = hooks_folder_path.parent.joinpath("blender_addon", "startup", "custom_scripts")

        script_file = custom_script_folder.joinpath(self.script_file_name)
        if not script_file.exists() or not script_file.is_file():
            raise FileNotFoundError(f"Can't find {self.script_file_name} in {custom_script_folder}.")

        self.launch_context.data.setdefault("python_scripts", []).append(
            custom_script_folder.joinpath(self.script_file_name)
        )
