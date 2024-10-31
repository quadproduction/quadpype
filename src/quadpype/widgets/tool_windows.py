from quadpype.settings import get_system_settings, get_local_settings, GENERAL_SETTINGS_KEY
from quadpype.pipeline import get_current_project_name
from qtpy import QtWidgets, QtCore


class BaseToolMixin:
    def __init__(self, *args, **kwargs):
        (parent,) = args

        self.project_name = get_current_project_name()

        # set a default value before trying to retrieve the value in the settings
        self.can_stay_on_top = True

        # Get value from the system settings, then check if there is a local override
        for settings in [get_system_settings(),  get_local_settings()]:
            if not settings:
                continue
            self.can_stay_on_top = settings[GENERAL_SETTINGS_KEY].get(
                "windows_can_stay_on_top", self.can_stay_on_top)

        if self.can_stay_on_top:
            # To be able to activate the "Stays On top" feature, the window need have no parent.
            parent = None

        args = (parent,)

        super().__init__(*args, **kwargs)


class BaseToolDialog(BaseToolMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

    def showEvent(self, event):
        self.setWindowState(QtCore.Qt.WindowNoState)
        super().showEvent(event)
        self.setWindowState(QtCore.Qt.WindowActive)


class BaseToolWidget(BaseToolMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def showEvent(self, event):
        self.setWindowState(QtCore.Qt.WindowNoState)
        super().showEvent(event)
        self.setWindowState(QtCore.Qt.WindowActive)
