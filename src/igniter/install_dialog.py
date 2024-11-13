# -*- coding: utf-8 -*-
"""Show dialog for choosing central pype repository."""
import os
import sys
import re
import collections

from pathlib import Path
from qtpy import QtCore, QtGui, QtWidgets

from .install_thread import InstallThread
from .tools import (
    validate_database_connection,
    get_app_icon_path,
    get_fonts_dir_path
)

from .nice_progress_bar import NiceProgressBar
from .user_settings import QuadPypeSecureRegistry
from .tools import load_stylesheet
from .version import __version__


class ButtonWithOptions(QtWidgets.QFrame):
    option_clicked = QtCore.Signal(str)

    def __init__(self, commands, parent=None):
        super().__init__(parent)

        self.setObjectName("ButtonWithOptions")

        options_btn = QtWidgets.QToolButton(self)
        options_btn.setArrowType(QtCore.Qt.DownArrow)
        options_btn.setIconSize(QtCore.QSize(12, 12))

        default = None
        default_label = None
        options_menu = QtWidgets.QMenu(self)
        for option, option_label in commands.items():
            if default is None:
                default = option
                default_label = option_label
                continue
            action = QtWidgets.QAction(option_label, options_menu)
            action.setData(option)
            options_menu.addAction(action)

        main_btn = QtWidgets.QPushButton(default_label, self)
        main_btn.setFlat(True)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(1)

        main_layout.addWidget(main_btn, 1, QtCore.Qt.AlignVCenter)
        main_layout.addWidget(options_btn, 0, QtCore.Qt.AlignVCenter)

        main_btn.clicked.connect(self._on_main_button)
        options_btn.clicked.connect(self._on_options_click)
        options_menu.triggered.connect(self._on_trigger)

        self.main_btn = main_btn
        self.options_btn = options_btn
        self.options_menu = options_menu

        options_btn.setEnabled(not options_menu.isEmpty())

        self._default_value = default

    def resizeEvent(self, event):
        super(ButtonWithOptions, self).resizeEvent(event)
        self.options_btn.setFixedHeight(self.main_btn.height())

    def _on_options_click(self):
        pos = self.main_btn.rect().bottomLeft()
        point = self.main_btn.mapToGlobal(pos)
        self.options_menu.popup(point)

    def _on_trigger(self, action):
        self.option_clicked.emit(action.data())

    def _on_main_button(self):
        self.option_clicked.emit(self._default_value)


class ConsoleWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # style for normal and error console text
        default_console_style = QtGui.QTextCharFormat()
        error_console_style = QtGui.QTextCharFormat()
        default_console_style.setForeground(
            QtGui.QColor.fromRgb(72, 200, 150)
        )
        error_console_style.setForeground(
            QtGui.QColor.fromRgb(184, 54, 19)
        )

        label = QtWidgets.QLabel("Console:", self)

        console_output = QtWidgets.QPlainTextEdit(self)
        console_output.setMinimumSize(QtCore.QSize(300, 200))
        console_output.setReadOnly(True)
        console_output.setCurrentCharFormat(default_console_style)
        console_output.setObjectName("Console")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(label, 0)
        main_layout.addWidget(console_output, 1)

        self.default_console_style = default_console_style
        self.error_console_style = error_console_style

        self.label = label
        self.console_output = console_output

        self.hide_console()

    def hide_console(self):
        self.label.setVisible(False)
        self.console_output.setVisible(False)

        self.updateGeometry()

    def show_console(self):
        self.label.setVisible(True)
        self.console_output.setVisible(True)

        self.updateGeometry()

    def update_console(self, msg: str, error: bool = False) -> None:
        if not error:
            self.console_output.setCurrentCharFormat(
                self.default_console_style
            )
        else:
            self.console_output.setCurrentCharFormat(
                self.error_console_style
            )
        self.console_output.appendPlainText(msg)


class DatabaseUriInput(QtWidgets.QLineEdit):
    """Widget to input database URI."""

    def set_valid(self):
        """Set valid state on database URI input."""
        self.setProperty("state", "valid")
        self.style().polish(self)

    def remove_state(self):
        """Set invalid state on database URI input."""
        self.setProperty("state", "")
        self.style().polish(self)

    def set_invalid(self):
        """Set invalid state on database URI input."""
        self.setProperty("state", "invalid")
        self.style().polish(self)


class InstallDialog(QtWidgets.QDialog):
    """Main Igniter dialog window."""

    database_uri_regex = re.compile(r"^mongodb(\+srv)?://[\w.-]+:\d{1,5}$")

    _width = 500
    _height = 200
    commands = collections.OrderedDict([
        ("run", "Start"),
        ("run_from_code", "Run from code")
    ])

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            f"QuadPype"
        )
        self.setWindowFlags(
            QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )

        fonts_dir = Path(get_fonts_dir_path())
        roboto_font_path = str(fonts_dir.joinpath("RobotoMono-Regular.ttf"))
        poppins_font_path = str(fonts_dir.joinpath("Poppins"))

        # Install fonts
        QtGui.QFontDatabase.addApplicationFont(roboto_font_path)
        for filename in os.listdir(poppins_font_path):
            if os.path.splitext(filename)[1] == ".ttf":
                QtGui.QFontDatabase.addApplicationFont(filename)

        # Load logo
        icon_path = get_app_icon_path()
        pixmap_app_logo = QtGui.QPixmap(icon_path)
        # Set logo as icon of the window
        self.setWindowIcon(QtGui.QIcon(pixmap_app_logo))

        secure_registry = QuadPypeSecureRegistry("Database")
        database_uri = ""
        try:
            database_uri = (
                os.getenv("QUADPYPE_DB_URI", "")
                or secure_registry.get_item("DatabaseUri")
            )
        except ValueError:
            pass

        self.database_uri = database_uri
        self._pixmap_app_logo = pixmap_app_logo

        self._secure_registry = secure_registry
        self._controls_disabled = False
        self._install_thread = None

        self.resize(QtCore.QSize(self._width, self._height))
        self._init_ui()

        # Set stylesheet
        self.setStyleSheet(load_stylesheet())

        # Trigger Database URI validation
        self._database_input.setText(self.database_uri)

    def _init_ui(self):
        # Main info
        # --------------------------------------------------------------------
        main_label = QtWidgets.QLabel("Welcome to <b>QuadPype</b>", self)
        main_label.setWordWrap(True)
        main_label.setObjectName("MainLabel")

        # Database box | OK button
        # --------------------------------------------------------------------
        database_input = DatabaseUriInput(self)
        database_input.setPlaceholderText(
            "Enter your database Address. Example: mongodb://192.168.1.10:27017"
        )

        database_messages_widget = QtWidgets.QWidget(self)

        database_connection_msg = QtWidgets.QLabel(database_messages_widget)
        database_connection_msg.setVisible(True)
        database_connection_msg.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )

        database_messages_layout = QtWidgets.QVBoxLayout(database_messages_widget)
        database_messages_layout.setContentsMargins(0, 0, 0, 0)
        database_messages_layout.addWidget(database_connection_msg)

        # Progress bar
        # --------------------------------------------------------------------
        progress_bar = NiceProgressBar(self)
        progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        progress_bar.setTextVisible(False)

        # Console
        # --------------------------------------------------------------------
        console_widget = ConsoleWidget(self)

        # Bottom button bar
        # --------------------------------------------------------------------
        bottom_widget = QtWidgets.QWidget(self)

        btns_widget = QtWidgets.QWidget(bottom_widget)

        launcher_version_label = QtWidgets.QLabel(f"<i>Launcher v{__version__}</i>", bottom_widget)

        run_button = ButtonWithOptions(
            self.commands,
            btns_widget
        )
        run_button.setMinimumSize(64, 30)
        run_button.setToolTip("Run QuadPype")

        # install button - - - - - - - - - - - - - - - - - - - - - - - - - - -
        exit_button = QtWidgets.QPushButton("Exit", btns_widget)
        exit_button.setObjectName("ExitBtn")
        exit_button.setFlat(True)
        exit_button.setMinimumSize(64, 24)
        exit_button.setToolTip("Exit")

        btns_layout = QtWidgets.QHBoxLayout(btns_widget)
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.addWidget(run_button, 0)
        btns_layout.addWidget(exit_button, 0)

        bottom_layout = QtWidgets.QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setAlignment(QtCore.Qt.AlignHCenter)
        bottom_layout.addWidget(launcher_version_label, 0)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(btns_widget, 0)

        # add all to main
        main = QtWidgets.QVBoxLayout(self)
        main.addSpacing(15)
        main.addWidget(main_label, 0)
        main.addSpacing(15)
        main.addWidget(database_input, 0)
        main.addWidget(database_messages_widget, 0)

        main.addWidget(progress_bar, 0)
        main.addSpacing(15)

        main.addWidget(console_widget, 1)

        main.addWidget(bottom_widget, 0)

        run_button.option_clicked.connect(self._on_run_btn_click)
        exit_button.clicked.connect(self._on_exit_clicked)
        database_input.textChanged.connect(self._on_database_uri_change)

        self._console_widget = console_widget

        self.main_label = main_label

        self._database_input = database_input

        self._database_connection_msg = database_connection_msg

        self._run_button = run_button
        self._exit_button = exit_button
        self._progress_bar = progress_bar

    def _on_run_btn_click(self, option):
        # Disable buttons
        self._disable_buttons()
        # Set progress to any value
        self._update_progress(1)
        self._progress_bar.repaint()
        # Add label to show that is connecting to database
        self.set_invalid_database_connection(self.database_uri, True)

        # Process events to repaint changes
        QtWidgets.QApplication.processEvents()

        if not self.validate_uri():
            self._enable_buttons()
            self._update_progress(0)
            # Update any messages
            self._database_input.setText(self.database_uri)
            return

        if option == "run":
            self._run_quadpype()
        elif option == "run_from_code":
            self._run_quadpype_from_code()
        else:
            raise AssertionError("BUG: Unknown variant \"{}\"".format(option))

    def _run_quadpype_from_code(self):
        os.environ["QUADPYPE_DB_URI"] = self.database_uri
        try:
            self._secure_registry.set_item("DatabaseUri", self.database_uri)
        except ValueError:
            print("Couldn't save Database URI to keyring")

        self.done(2)

    def _run_quadpype(self):
        """Start install process.

        This will once again validate entered path and database if ok, start
        working thread that will do actual job.
        """
        # Check if install thread is not already running
        if self._install_thread and self._install_thread.isRunning():
            return

        self._database_input.set_valid()

        install_thread = InstallThread(self)
        install_thread.message.connect(self.update_console)
        install_thread.progress.connect(self._update_progress)
        install_thread.finished.connect(self._installation_finished)
        install_thread.set_database(self.database_uri)

        self._install_thread = install_thread

        install_thread.start()

    def _installation_finished(self):
        # TODO we should find out why status can be set to 'None'?
        # - 'InstallThread.run' should handle all cases so not sure where
        #       that come from
        status = self._install_thread.result()
        if status is not None and status >= 0:
            self._update_progress(100)
            QtWidgets.QApplication.processEvents()
            self.done(3)
        else:
            self._enable_buttons()
            self._show_console()

    def _update_progress(self, progress: int):
        self._progress_bar.setValue(progress)
        text_visible = self._progress_bar.isTextVisible()
        if progress == 0:
            if text_visible:
                self._progress_bar.setTextVisible(False)
        elif not text_visible:
            self._progress_bar.setTextVisible(True)

    def _on_exit_clicked(self):
        self.reject()

    def _on_database_uri_change(self, new_value):
        # Strip the value
        new_value = new_value.strip()
        # Store new database URI to variable
        self.database_uri = new_value

        msg = None
        # Change style of input
        if not new_value:
            self._database_input.remove_state()
        elif not self.database_uri_regex.match(new_value):
            self._database_input.set_invalid()
            msg = (
                "Database URI should start with"
                " <b>\"mongodb://\"</b> or <b>\"mongodb+srv://\"</b>"
            )
        else:
            self._database_input.set_valid()

        self.set_invalid_database_uri(msg)

    def validate_uri(self):
        """Validate if entered uri is ok.

        Returns:
            True if uri is valid monogo string.

        """
        if self.database_uri == "":
            return False

        is_valid, reason_str = validate_database_connection(self.database_uri)
        if not is_valid:
            self.set_invalid_database_connection(self.database_uri)
            self._database_input.set_invalid()
            self.update_console(f"!!! {reason_str}", True)
            return False

        self.set_invalid_database_connection(None)
        self._database_input.set_valid()
        return True

    def set_invalid_database_uri(self, reason):
        if reason is None:
            self._database_connection_msg.setText("")
        else:
            self._database_connection_msg.setText("- {}".format(reason))

    def set_invalid_database_connection(self, database_uri, connecting=False):
        if database_uri is None:
            self.set_invalid_database_uri(database_uri)
            return

        if connecting:
            msg = "Connecting to: <b>{}</b>".format(database_uri)
        else:
            msg = "Can't connect to: <b>{}</b>".format(database_uri)

        self.set_invalid_database_uri(msg)

    def update_console(self, msg: str, error: bool = False) -> None:
        """Display message in console.

        Args:
            msg (str): message.
            error (bool): if True, print it red.
        """
        self._console_widget.update_console(msg, error)

    def _show_console(self):
        self._console_widget.show_console()
        self.updateGeometry()

    def _disable_buttons(self):
        """Disable buttons so user interaction doesn't interfere."""
        self._exit_button.setEnabled(False)
        self._run_button.setEnabled(False)
        self._controls_disabled = True

    def _enable_buttons(self):
        """Enable buttons after operation is complete."""
        self._exit_button.setEnabled(True)
        self._run_button.setEnabled(True)
        self._controls_disabled = False

    def closeEvent(self, event):  # noqa
        """Prevent closing if window when controls are disabled."""
        if self._controls_disabled:
            return event.ignore()
        return super(InstallDialog, self).closeEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    d = InstallDialog()
    d.show()
    sys.exit(app.exec_())
