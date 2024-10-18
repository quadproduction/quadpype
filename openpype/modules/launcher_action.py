import os

from openpype import PLUGINS_DIR, AYON_SERVER_ENABLED
from openpype.modules import (
    OpenPypeModule,
    ITrayAction,
)

from openpype.widgets import PasswordDialog
from openpype.lib import is_admin_password_required

class LauncherAction(OpenPypeModule, ITrayAction):
    label = "Launcher"
    name = "launcher_tool"

    def initialize(self, _modules_settings):
        # This module is always enabled
        self.enabled = True

        # Tray attributes
        self._window = None

    def tray_init(self):
        self._create_window()

        self.add_doubleclick_callback(self._show_launcher)

    def tray_start(self):
        return

    def connect_with_modules(self, enabled_modules):
        # Register actions
        if not self.tray_initialized:
            return

        from openpype.pipeline.actions import register_launcher_action_path

        actions_dir = os.path.join(PLUGINS_DIR, "actions")
        if os.path.exists(actions_dir):
            register_launcher_action_path(actions_dir)

        actions_paths = self.manager.collect_plugin_paths()["actions"]
        for path in actions_paths:
            if path and os.path.exists(path):
                register_launcher_action_path(path)

    def on_action_trigger(self):
        """Implementation for ITrayAction interface.

        Show launcher tool on action trigger.
        """

        self._show_launcher()

    def _create_window(self):
        if self._window:
            return
        if AYON_SERVER_ENABLED:
            from openpype.tools.ayon_launcher.ui import LauncherWindow
        else:
            from openpype.tools.launcher import LauncherWindow
        self._window = LauncherWindow()

    def _show_launcher(self):
        password_required = is_admin_password_required(admin_bypass_enabled=False)
        if password_required:
            dialog = PasswordDialog(allow_remember=False)
            dialog.setModal(True)
            dialog.exec_()
            if not dialog.result():
                return

        if self.window:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
