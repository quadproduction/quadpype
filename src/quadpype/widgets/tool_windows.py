from quadpype.lib import get_user_settings
from quadpype.settings import (
    get_global_settings,
    CORE_SETTINGS_KEY,
    GENERAL_SETTINGS_KEY
)
from quadpype.pipeline import get_current_project_name
from qtpy import QtWidgets, QtCore


class BaseToolMixin:
    def __init__(self, *args, **kwargs):
        (parent,) = args

        self.project_name = get_current_project_name()

        # set a default value before trying to retrieve the value in the settings
        self.can_stay_on_top = True

        # Get value from the global settings, then check if there is a local override
        for settings in [get_global_settings(),  get_user_settings()]:
            if not settings:
                continue

            for section_name in [CORE_SETTINGS_KEY, GENERAL_SETTINGS_KEY]:
                if section_name in settings:
                    self.can_stay_on_top = settings[section_name].get(
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
