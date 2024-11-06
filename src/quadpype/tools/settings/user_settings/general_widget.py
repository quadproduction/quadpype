import getpass

from qtpy import QtWidgets, QtCore
from quadpype.tools.utils import PlaceholderLineEdit


class LocalGeneralWidgets(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self._loading_user_settings = False

        self.username_input = PlaceholderLineEdit(self)
        self.username_input.setPlaceholderText(getpass.getuser())

        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addRow("Override QuadPype Username", self.username_input)

        self.windows_can_stay_on_top_input = QtWidgets.QCheckBox("", self)
        layout.addRow("Windows can Stay On Top", self.windows_can_stay_on_top_input)

    def update_user_settings(self, value):
        self._loading_user_settings = True

        username = ""
        windows_can_stay_on_top = True

        if value:
            username = value.get("username", username)
            windows_can_stay_on_top = value.get("windows_can_stay_on_top", windows_can_stay_on_top)

        self.username_input.setText(username)

        if self.windows_can_stay_on_top_input.isChecked() != windows_can_stay_on_top:
            # Use state as `stateChanged` is connected to callbacks
            if windows_can_stay_on_top:
                state = QtCore.Qt.Checked
            else:
                state = QtCore.Qt.Unchecked
            self.windows_can_stay_on_top_input.setCheckState(state)

        self._loading_user_settings = False

    def settings_value(self):
        # Add only diffs compared with default values
        output = {}
        username = self.username_input.text()
        if username:
            output["username"] = username

        windows_can_stay_on_top = self.windows_can_stay_on_top_input.isChecked()
        if not windows_can_stay_on_top:
            output["windows_can_stay_on_top"] = windows_can_stay_on_top

        return output
