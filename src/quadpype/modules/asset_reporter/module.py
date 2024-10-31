import os.path

from quadpype.modules import QuadPypeModule, ITrayAction
from quadpype.lib import run_detached_process, get_quadpype_execute_args


class AssetReporterAction(QuadPypeModule, ITrayAction):

    label = "Asset Usage Report"
    name = "asset_reporter"

    def tray_init(self):
        pass

    def initialize(self, modules_settings):
        self.enabled = True

    def on_action_trigger(self):
        args = get_quadpype_execute_args()
        args += ["run",
                 os.path.join(
                     os.path.dirname(__file__),
                     "window.py")]

        print(" ".join(args))
        run_detached_process(args)
