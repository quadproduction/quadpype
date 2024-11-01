import getpass

from qtpy import QtWidgets, QtCore
from quadpype.lib import is_admin_password_required
from quadpype.widgets import PasswordDialog
from quadpype.tools.utils import PlaceholderLineEdit


class LocalGeneralWidgets(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self._loading_user_settings = False

        self.username_input = PlaceholderLineEdit(self)
        self.username_input.setPlaceholderText(getpass.getuser())

        self.is_admin_input = QtWidgets.QCheckBox(self)

        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addRow("QuadPype Username", self.username_input)
        layout.addRow("Admin permissions", self.is_admin_input)

        self.is_admin_input.stateChanged.connect(self._on_admin_check_change)

        self.windows_can_stay_on_top_input = QtWidgets.QCheckBox(self)
        layout.addRow("Allow Pipeline Windows to Stay On Top", self.windows_can_stay_on_top_input)

    def update_user_settings(self, value):
        self._loading_user_settings = True

        username = ""
        is_admin = False
        windows_can_stay_on_top = True

        if value:
            username = value.get("username", username)
            is_admin = value.get("is_admin", is_admin)
            windows_can_stay_on_top = value.get("windows_can_stay_on_top", windows_can_stay_on_top)

        self.username_input.setText(username)

        if self.is_admin_input.isChecked() != is_admin:
            # Use state as `stateChanged` is connected to callbacks
            if is_admin:
                state = QtCore.Qt.Checked
            else:
                state = QtCore.Qt.Unchecked
            self.is_admin_input.setCheckState(state)

        if self.windows_can_stay_on_top_input.isChecked() != windows_can_stay_on_top:
            # Use state as `stateChanged` is connected to callbacks
            if windows_can_stay_on_top:
                state = QtCore.Qt.Checked
            else:
                state = QtCore.Qt.Unchecked
            self.windows_can_stay_on_top_input.setCheckState(state)

        self._loading_user_settings = False

    def _on_admin_check_change(self):
        if self._loading_user_settings:
            return

        if not self.is_admin_input.isChecked():
            return

        if not is_admin_password_required():
            return

        dialog = PasswordDialog(self, False)
        dialog.setModal(True)
        dialog.exec_()
        result = dialog.result()
        if self.is_admin_input.isChecked() != result:
            # Use state as `stateChanged` is connected to callbacks
            if result:
                state = QtCore.Qt.Checked
            else:
                state = QtCore.Qt.Unchecked
            self.is_admin_input.setCheckState(state)

    def settings_value(self):
        # Add only diffs compared with default values
        output = {}
        username = self.username_input.text()
        if username:
            output["username"] = username

        is_admin = self.is_admin_input.isChecked()
        if is_admin:
            output["is_admin"] = is_admin

        windows_can_stay_on_top = self.windows_can_stay_on_top_input.isChecked()
        if not windows_can_stay_on_top:
            output["windows_can_stay_on_top"] = windows_can_stay_on_top

        return output
