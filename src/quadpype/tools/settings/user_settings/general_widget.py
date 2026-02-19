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

        self.enable_auto_clic_scripts_input = QtWidgets.QCheckBox("", self)
        layout.addRow("Enable auto clic scripts", self.enable_auto_clic_scripts_input)

        self.register_sync_results_input = QtWidgets.QCheckBox("", self)
        self.register_sync_results_input.setEnabled(False)
        layout.addRow("Register sync results in database", self.register_sync_results_input)

    def update_user_settings(self, value):
        self._loading_user_settings = True

        username = ""
        windows_can_stay_on_top = True
        enable_auto_clic_scripts = True
        register_sync_results = False

        if value:
            username = value.get("username", username)
            windows_can_stay_on_top = value.get("windows_can_stay_on_top", windows_can_stay_on_top)
            enable_auto_clic_scripts = value.get("enable_auto_clic_scripts", enable_auto_clic_scripts)
            register_sync_results = value.get("register_sync_results", register_sync_results)

        self.username_input.setText(username)

        for input_with_attribute in [
            (self.windows_can_stay_on_top_input, windows_can_stay_on_top),
            (self.enable_auto_clic_scripts_input, enable_auto_clic_scripts),
            (self.register_sync_results_input, register_sync_results)
        ]:
            attribute, input = input_with_attribute
            if attribute.isChecked() != input:
                # Use state as `stateChanged` is connected to callbacks
                if input:
                    state = QtCore.Qt.CheckState.Checked
                else:
                    state = QtCore.Qt.CheckState.Unchecked
                attribute.setCheckState(state)

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

        enable_auto_clic_scripts = self.enable_auto_clic_scripts_input.isChecked()
        if not enable_auto_clic_scripts:
            output["enable_auto_clic_scripts"] = enable_auto_clic_scripts

        register_sync_results = self.register_sync_results_input.isChecked()
        if not register_sync_results:
            output["register_sync_results"] = register_sync_results

        return output
