from quadpype.modules import QuadPypeModule, ITrayAction
from quadpype.settings import get_system_settings, GENERAL_SETTINGS_KEY
from quadpype.settings.lib import get_user_profile


class SettingsAction(QuadPypeModule, ITrayAction):
    """Action to show Settings tool."""
    name = "settings"
    label = "Studio Settings"
    submenu = "Admin"

    def __init__(self, manager, settings):
        self.settings_window = None
        self.user_role = "user"

        super().__init__(manager, settings)

    def initialize(self, _modules_settings):
        self.enabled = True

        user_profile = get_user_profile()
        self.user_role = user_profile["role"]

        system_settings = get_system_settings()
        #if user_id in system_settings[GENERAL_SETTINGS_KEY]["administrators"]:
        #    self.user_role = "administrator"

        if system_settings[GENERAL_SETTINGS_KEY]["access_restricted"]:
             if self.user_role != "administrator":
                 self.enabled = False

    def tray_init(self):
        """Initialization in tray implementation of ITrayAction."""
        pass

    def tray_exit(self):
        # Close settings UI to remove settings lock
        if self.settings_window:
            self.settings_window.close()

    def on_action_trigger(self):
        """Implementation for action trigger of ITrayAction."""
        self.show_settings_window()

    def create_settings_window(self):
        """Initialize Settings Qt window."""
        if self.settings_window:
            return
        from quadpype.tools.settings import MainWidget

        self.settings_window = MainWidget(self.user_role, reset_on_show=False)
        self.settings_window.trigger_restart.connect(self._on_trigger_restart)

    def _on_trigger_restart(self):
        self.manager.restart_tray()

    def show_settings_window(self):
        """Show the settings tool window.

        Raises:
            AssertionError: Window must be already created. Call
                `create_settings_window` before calling this method.
        """
        if not self.settings_window:
            self.create_settings_window()

        # Store if was visible
        was_visible = self.settings_window.isVisible()
        was_minimized = self.settings_window.isMinimized()

        # Show settings gui
        self.settings_window.show()

        if was_minimized:
            self.settings_window.showNormal()

        # Pull the window to the front
        self.settings_window.raise_()
        self.settings_window.activateWindow()

        # Reset content if was not visible
        if not was_visible and not was_minimized:
            self.settings_window.reset()


class LocalSettingsAction(QuadPypeModule, ITrayAction):
    """Action to show Settings tool."""
    name = "user_settings"
    label = "User Settings"

    def __init__(self, manager, settings):
        self.settings_window = None
        self._first_trigger = True

        super().__init__(manager, settings)

    def initialize(self, _modules_settings):
        # This action is always enabled
        self.enabled = True

    def tray_init(self):
        """Initialization in tray implementation of ITrayAction."""
        pass

    def on_action_trigger(self):
        """Implementation for action trigger of ITrayAction."""
        self.show_settings_window()

    def create_settings_window(self):
        """Initialize Settings Qt window."""
        if self.settings_window:
            return
        from quadpype.tools.settings import LocalSettingsWindow
        self.settings_window = LocalSettingsWindow()

    def show_settings_window(self):
        """Show the settings tool window.
        """
        if not self.settings_window:
            self.create_settings_window()

        # Store if was visible
        was_visible = self.settings_window.isVisible()

        # Show settings gui
        self.settings_window.show()

        # Pull window to the front.
        self.settings_window.raise_()
        self.settings_window.activateWindow()

        # Do not reset if it's first trigger of action
        if self._first_trigger:
            self._first_trigger = False
        elif not was_visible:
            # Reset content if was not visible
            self.settings_window.reset()
