from quadpype.modules import QuadPypeModule, ITrayAction


class PythonInterpreterAction(QuadPypeModule, ITrayAction):
    label = "Console"
    name = "python_interpreter"
    submenu = "More Tools"

    def initialize(self, modules_settings):
        self.enabled = True
        self._interpreter_window = None

    def tray_init(self):
        self.create_interpreter_window()

    def tray_exit(self):
        if self._interpreter_window is not None:
            self._interpreter_window.save_registry()

    def create_interpreter_window(self):
        """Initializa Settings Qt window."""
        if self._interpreter_window:
            return

        from quadpype_modules.python_console_interpreter.window import (
            PythonInterpreterWidget
        )

        self._interpreter_window = PythonInterpreterWidget()

    def on_action_trigger(self):
        self.show_interpreter_window()

    def show_interpreter_window(self):
        self.create_interpreter_window()

        if self._interpreter_window.isVisible():
            self._interpreter_window.activateWindow()
            self._interpreter_window.raise_()
            return

        self._interpreter_window.show()
