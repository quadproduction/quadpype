import html

from qtpy import QtWidgets, QtCore, QtGui

from quadpype import style
from quadpype.modules.kitsu.utils.credentials import (
    clear_credentials,
    load_credentials,
    save_credentials,
    set_credentials_envs,
    validate_credentials,
    get_kitsu_user_id
)
from quadpype.resources import get_resource
from quadpype.settings import (
    get_global_settings,
    ADDONS_SETTINGS_KEY
)

from quadpype.tools.utils import PressHoverButton
from quadpype.lib.user import set_tracker_login_to_user_profile


class KitsuPasswordDialog(QtWidgets.QDialog):
    """Kitsu login dialog."""

    finished = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("QuadPype: Kitsu Login")
        window_icon = QtGui.QIcon(style.get_app_icon_path())
        self.setWindowIcon(window_icon)

        self.resize(420, 220)

        global_settings = get_global_settings()
        kitsu_settings = global_settings[ADDONS_SETTINGS_KEY].get("kitsu", {})
        user_login, user_pwd, totp_secret = load_credentials()

        self.twofa_toggle_btn = None
        self.twofa_widget = None
        self.twofa_code_input = None
        self._final_result = None
        self._connectable = bool(
            kitsu_settings.get("server")
        )
        # Server label
        server_message = (
            kitsu_settings.get("server")
            if self._connectable
            else "no server url set in Studio Settings..."
        )
        server_label = QtWidgets.QLabel(
            f"Server: {server_message}",
            self,
        )

        # Login input
        login_widget = QtWidgets.QWidget(self)

        login_label = QtWidgets.QLabel("Login:", login_widget)

        login_input = QtWidgets.QLineEdit(
            login_widget,
            text=user_login,
        )
        login_input.setPlaceholderText("Your Kitsu account login...")

        login_layout = QtWidgets.QHBoxLayout(login_widget)
        login_layout.setContentsMargins(0, 0, 0, 0)
        login_layout.addWidget(login_label)
        login_layout.addWidget(login_input)

        # Password input
        password_widget = QtWidgets.QWidget(self)

        password_label = QtWidgets.QLabel("Password:", password_widget)

        password_input = QtWidgets.QLineEdit(
            password_widget,
            text=user_pwd,
        )
        password_input.setPlaceholderText("Your password...")
        password_input.setEchoMode(QtWidgets.QLineEdit.Password)

        show_password_icon_path = get_resource("icons", "eye.png")
        show_password_icon = QtGui.QIcon(show_password_icon_path)
        show_password_btn = PressHoverButton(password_widget)
        show_password_btn.setObjectName("PasswordBtn")
        show_password_btn.setIcon(show_password_icon)
        show_password_btn.setFocusPolicy(QtCore.Qt.ClickFocus)

        password_layout = QtWidgets.QHBoxLayout(password_widget)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.addWidget(password_label)
        password_layout.addWidget(password_input)
        password_layout.addWidget(show_password_btn)

        # Message label
        message_label = QtWidgets.QLabel("", self)
        message_label.setWordWrap(True)

        settings_2fa = kitsu_settings.get("2fa", {})

        use_2fa = settings_2fa.get("enabled", True)
        optional = settings_2fa.get("optional", True)

        if use_2fa:

            twofa_widget = QtWidgets.QWidget(self)
            twofa_widget.setVisible(not optional)
            if optional:
                twofa_toggle_btn = QtWidgets.QPushButton(
                    "I use two-factor authentication",
                    self
                )
                twofa_toggle_btn.setCheckable(True)

                twofa_info_label = QtWidgets.QLabel(
                    "If your account uses 2FA, please enter your account secret.",
                    twofa_widget
                )
                twofa_info_label.setWordWrap(True)

            twofa_code_label = QtWidgets.QLabel("OTP Secret :", twofa_widget)
            twofa_code_input = QtWidgets.QLineEdit(
                twofa_widget,
                text=totp_secret,
            )
            twofa_code_input.setPlaceholderText("Enter your OTP secret...")
            twofa_code_input.setEchoMode(QtWidgets.QLineEdit.Password)

            show_twofa_btn = PressHoverButton(twofa_widget)
            show_twofa_btn.setObjectName("2faBtn")
            show_twofa_btn.setIcon(show_password_icon)
            show_twofa_btn.setFocusPolicy(QtCore.Qt.ClickFocus)

            twofa_code_widget = QtWidgets.QWidget(twofa_widget)
            twofa_code_layout = QtWidgets.QHBoxLayout(twofa_code_widget)
            twofa_code_layout.setContentsMargins(0, 0, 0, 0)
            twofa_code_layout.addWidget(twofa_code_input)
            twofa_code_layout.addWidget(show_twofa_btn)

            self.twofa_code_input = twofa_code_input

            twofa_form_layout = QtWidgets.QFormLayout()
            twofa_form_layout.setContentsMargins(0, 0, 0, 0)
            twofa_form_layout.addRow(twofa_code_label, twofa_code_widget)

            twofa_layout = QtWidgets.QVBoxLayout(twofa_widget)
            twofa_layout.setContentsMargins(0, 0, 0, 0)
            if optional:
                twofa_layout.addWidget(twofa_info_label)
                twofa_toggle_btn.clicked.connect(self._on_toggle_twofa_options)

            twofa_layout.addLayout(twofa_form_layout)

            show_twofa_btn.change_state.connect(self._on_show_twofa_code)

        kitsu_connection_help = kitsu_settings.get("connection_help", None)
        if kitsu_connection_help:
            helper_label = QtWidgets.QLabel(
                f'<a href="{kitsu_connection_help}">I have troubles connecting, please help me !</a>'
            )
            helper_label.setOpenExternalLinks(True)

        buttons_widget = QtWidgets.QWidget(self)

        remember_checkbox = QtWidgets.QCheckBox("Remember", buttons_widget)
        remember_checkbox.setObjectName("RememberCheckbox")
        remember_checkbox.setChecked(True)

        ok_btn = QtWidgets.QPushButton("Ok", buttons_widget)
        cancel_btn = QtWidgets.QPushButton("Cancel", buttons_widget)

        buttons_layout = QtWidgets.QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addWidget(remember_checkbox)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addSpacing(5)
        layout.addWidget(server_label, 0)
        layout.addSpacing(5)
        layout.addWidget(login_widget, 0)
        layout.addWidget(password_widget, 0)

        if use_2fa:
            if optional:
                layout.addWidget(twofa_toggle_btn, 0)
                self.twofa_toggle_btn = twofa_toggle_btn

            self.twofa_widget = twofa_widget
            layout.addWidget(twofa_widget, 0)

        layout.addWidget(message_label, 0)
        layout.addStretch(1)
        if kitsu_connection_help:
            layout.addWidget(helper_label, 1)
        layout.addWidget(buttons_widget, 0)

        ok_btn.clicked.connect(self._on_ok_click)
        cancel_btn.clicked.connect(self._on_cancel_click)
        show_password_btn.change_state.connect(self._on_show_password)

        self.login_input = login_input
        self.password_input = password_input
        self.remember_checkbox = remember_checkbox
        self.message_label = message_label
        self.use_2fa = use_2fa
        self.kitsu_connection_help = kitsu_connection_help

        self.kitsu_2fa_help = settings_2fa.get("2fa_help", None)

        self.setStyleSheet(style.load_stylesheet())

    def result(self):
        return self._final_result

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._on_ok_click()
            return event.accept()
        super(KitsuPasswordDialog, self).keyPressEvent(event)

    def closeEvent(self, event):
        super(KitsuPasswordDialog, self).closeEvent(event)
        self.finished.emit(self.result())

    def _on_ok_click(self):
        # Check if is connectable
        if not self._connectable:
            self.message_label.setText(
                "Please set server url in Studio Settings!"
            )
            return

        # Collect values
        login_value = self.login_input.text()
        pwd_value = self.password_input.text()
        secret_code = (
            self.twofa_code_input.text() if
            self.twofa_code_input and self.twofa_code_input.isVisible() else
            None
        )
        remember = self.remember_checkbox.isChecked()

        # Authenticate
        try:
            if not validate_credentials(login_value, pwd_value, secret_code):
                raise Exception("Invalid credentials")
            set_credentials_envs(login_value, pwd_value, secret_code)
        except Exception as e:
            self.message_label.setText("Unable to sign in.")
            self._show_connection_error_dialog()
            return

        # Remember password cases
        if remember:
            save_credentials(login_value, pwd_value, secret_code)
            set_tracker_login_to_user_profile()

        else:
            # Clear user settings
            clear_credentials()

            # Clear input fields
            self.login_input.clear()
            self.password_input.clear()

        self._final_result = True
        self._show_connection_success_dialog()
        self.close()

    def _on_show_password(self, show_password):
        if show_password:
            echo_mode = QtWidgets.QLineEdit.Normal
        else:
            echo_mode = QtWidgets.QLineEdit.Password
        self.password_input.setEchoMode(echo_mode)

    def _on_show_twofa_code(self, show_twofa_code):
        if show_twofa_code:
            echo_mode = QtWidgets.QLineEdit.Normal
        else:
            echo_mode = QtWidgets.QLineEdit.Password
        self.twofa_code_input.setEchoMode(echo_mode)

    def _set_twofa_options_visible(self, visible):
        self.twofa_widget.setVisible(visible)
        self.twofa_toggle_btn.setChecked(visible)
        if visible:
            self.twofa_toggle_btn.setText("Hide two-factor options")
        else:
            self.twofa_toggle_btn.setText("I use two-factor authentication")

    def _on_toggle_twofa_options(self, _checked=False):
        show_twofa_options = not self.twofa_widget.isVisible()
        self._set_twofa_options_visible(show_twofa_options)
        if show_twofa_options:
            self.twofa_code_input.setFocus()

    def _on_cancel_click(self):
        self.close()

    def _show_connection_error_dialog(self):
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Connection error")
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setTextFormat(QtCore.Qt.RichText)
        dialog.setText(self._get_connection_error_message())
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)

        message_label = dialog.findChild(QtWidgets.QLabel, "qt_msgbox_label")
        if message_label:
            message_label.setOpenExternalLinks(True)
            message_label.setTextInteractionFlags(
                QtCore.Qt.TextBrowserInteraction
            )

        dialog.exec_()

    def _show_connection_success_dialog(self):
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Connection successful")
        dialog.setIcon(QtWidgets.QMessageBox.Information)
        dialog.setTextFormat(QtCore.Qt.RichText)
        dialog.setText("Successfully connected to Kitsu.")
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        dialog.exec_()

    def _get_connection_error_message(self):
        help_msg = "please read the following guide if not"
        connection_kitsu_help = self._format_kitsu_help_link(
            self.kitsu_connection_help,
            help_msg
        )
        two_factor_help = self._format_kitsu_help_link(
            self.kitsu_2fa_help,
            help_msg
        )
        checklist_items = [
            "That your login and your password are correct;"
        ]

        if self.use_2fa:
            connection_help_link = f"<br />(<i>{connection_kitsu_help}</i>)" if connection_kitsu_help else ""
            two_factor_help_link = f"<br />(<i>{two_factor_help}</i>)" if two_factor_help else ""
            checklist_items.extend([
                (
                    "That you successfully activated two-factor "
                    "authentication on your Kitsu account."
                    f"{connection_help_link}"

                ),
                (
                    "That you enter the OTP SECRET code that you registered "
                    "when activating two-factor authentication on your "
                    "Kitsu account, <b>and not the generated 6-character code "
                    "delivered by your authenticator app.</b>"
                    f"{two_factor_help_link}"

                )
            ])

        if self.kitsu_connection_help is not None:
            msg = self._format_kitsu_help_link(
                self.kitsu_connection_help,
                "how to connect to kitsu guide"
            )
            checklist_items.append(
                "And that you read the "
                f"{msg}."
            )

        checklist_html = "".join(
            f"<li>{item}</li>" for item in checklist_items
        )
        return (
            "<p><b>An error has occurred when trying to connect to tracker.</b></p>"
            "<p>Please check :"
            f"<ul>{checklist_html}</ul>"
            "If none of this worked, please contact an administrator.</p>"
        )

    def _format_kitsu_help_link(self, guide_link, label):
        escaped_label = html.escape(label)
        if not guide_link:
            return ""

        escaped_url = html.escape(guide_link, quote=True)
        return f'<a href="{escaped_url}">{escaped_label}</a>'
