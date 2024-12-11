import os

from quadpype.modules import QuadPypeModule, ITrayAction
from quadpype.settings import get_global_settings
from quadpype.lib.version import get_package

import igniter
from igniter.zxp_utils import get_zxp_extensions_to_update


class UpdateZXPExtensionsAction(QuadPypeModule, ITrayAction):
    name = "update_zxp_extensions"
    label = "Update ZXP Extensions"
    submenu = "More Tools"

    def __init__(self, manager, settings):
        super().__init__(manager, settings)

    def initialize(self, _modules_settings):
        self.enabled = True
        if os.getenv("QUADPYPE_IGNORE_ZXP_UPDATE"):
            self.enabled = False

    def tray_init(self):
        return

    def tray_start(self):
        return

    def tray_exit(self):
        return

    def on_action_trigger(self):
        quadpype_version = get_package("quadpype").running_version

        global_settings = get_global_settings()
        zxp_hosts_to_update = get_zxp_extensions_to_update(quadpype_version.path, global_settings, force=True)
        igniter.open_zxp_update_window(quadpype_version.path, zxp_hosts_to_update)
