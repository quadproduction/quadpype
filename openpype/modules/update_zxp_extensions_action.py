import os

from quadpype.modules import QuadPypeModule, ITrayAction
from quadpype.settings import get_system_settings

import igniter  # noqa: E402
from igniter import BootstrapRepos  # noqa: E402


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
        # install latest version to user data dir
        bootstrap = BootstrapRepos()

        quadpype_version = bootstrap.find_quadpype_version(os.environ["QUADPYPE_VERSION"])

        system_settings = get_system_settings()
        zxp_hosts_to_update = bootstrap.get_zxp_extensions_to_update(quadpype_version, system_settings, force=True)
        igniter.open_update_window(quadpype_version, zxp_hosts_to_update)
