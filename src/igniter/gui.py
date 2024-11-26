# -*- coding: utf-8 -*-
"""Show dialog for choosing central QuadPype repository."""
import os
import re
import logging as log

from pathlib import Path
from qtpy import QtCore, QtGui, QtWidgets

from .tools import (
    load_stylesheet,
    get_app_icon_path,
    get_fonts_dir_path
)

from .registry import QuadPypeSecureRegistry
from .version import __version__
from .module_importer import load_quadpype_module
from .zxp_utils import ZXPExtensionData, ZXPUpdateThread
from.version_classes import PackageVersion


mongo_module = load_quadpype_module("quadpype/client/mongo/mongo.py", "quadpype.client.mongo.mongo")


class NiceProgressBar(QtWidgets.QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._real_value = 0

    def setValue(self, value):
        self._real_value = value
        if value != 0 and value < 11:
            value = 11

        super(NiceProgressBar, self).setValue(value)

    def value(self):
        return self._real_value

    def text(self):
        return "{} %".format(self._real_value)


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


class MongoUrlInput(QtWidgets.QLineEdit):
    """Widget to input mongodb URL."""

    def set_valid(self):
        """Set valid state on mongo url input."""
        self.setProperty("state", "valid")
        self.style().polish(self)

    def remove_state(self):
        """Set invalid state on mongo url input."""
        self.setProperty("state", "")
        self.style().polish(self)

    def set_invalid(self):
        """Set invalid state on mongo url input."""
        self.setProperty("state", "invalid")
        self.style().polish(self)


class DatabaseStringDialog(QtWidgets.QDialog):
    """Ask database string dialog window."""

    mongo_url_regex = re.compile(r"^mongodb(\+srv)?://([\w.%-]+:[\w.%-]+@)?[\w.%-]+(:\d{1,5})?/?$")

    _width = 500
    _height = 200

    def __init__(self, log=None, parent=None):
        super().__init__(parent)

        self._log = log

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
        self._pixmap_app_logo = pixmap_app_logo

        secure_registry = QuadPypeSecureRegistry("mongodb")
        mongo_url = ""
        try:
            mongo_url = (
                os.getenv("QUADPYPE_MONGO", "")
                or secure_registry.get_item("quadpypeMongo")
            )
        except ValueError:
            pass

        self.mongo_url = mongo_url


        self._secure_registry = secure_registry
        self._controls_disabled = False
        self._install_thread = None

        self.resize(QtCore.QSize(self._width, self._height))
        self._init_ui()

        # Set stylesheet
        self.setStyleSheet(load_stylesheet())

        # Trigger Mongo URL validation
        self._mongo_input.setText(self.mongo_url)

    def _init_ui(self):
        # Main info
        # --------------------------------------------------------------------
        main_label = QtWidgets.QLabel("Welcome to <b>QuadPype</b>", self)
        main_label.setWordWrap(True)
        main_label.setObjectName("MainLabel")

        # Mongo box | OK button
        # --------------------------------------------------------------------
        mongo_input = MongoUrlInput(self)
        mongo_input.setPlaceholderText(
            "Enter your database Address. Example: mongodb://192.168.1.10:27017"
        )

        mongo_messages_widget = QtWidgets.QWidget(self)

        mongo_connection_msg = QtWidgets.QLabel(mongo_messages_widget)
        mongo_connection_msg.setVisible(True)
        mongo_connection_msg.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )

        mongo_messages_layout = QtWidgets.QVBoxLayout(mongo_messages_widget)
        mongo_messages_layout.setContentsMargins(0, 0, 0, 0)
        mongo_messages_layout.addWidget(mongo_connection_msg)

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

        # install button
        # --------------------------------------------------------------------
        run_button = QtWidgets.QPushButton("Start", btns_widget)
        run_button.setObjectName("RunBtn")
        run_button.setFlat(True)
        run_button.setMinimumSize(64, 30)
        run_button.setToolTip("Start QuadPype")

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
        main.addWidget(mongo_input, 0)
        main.addWidget(mongo_messages_widget, 0)

        main.addWidget(progress_bar, 0)
        main.addSpacing(15)

        main.addWidget(console_widget, 1)

        main.addWidget(bottom_widget, 0)

        run_button.clicked.connect(self._on_run_btn_clicked)
        exit_button.clicked.connect(self._on_exit_clicked)
        mongo_input.textChanged.connect(self._on_mongo_url_change)

        self._console_widget = console_widget

        self.main_label = main_label

        self._mongo_input = mongo_input

        self._mongo_connection_msg = mongo_connection_msg

        self._run_button = run_button
        self._exit_button = exit_button
        self._progress_bar = progress_bar

    def _on_run_btn_clicked(self):
        # Disable the buttons
        self._disable_buttons()
        # Set progress to any value
        self._update_progress(50)
        self._progress_bar.repaint()
        # Add label to show that is connecting to mongo
        self.set_invalid_mongo_connection(self.mongo_url, True)

        # Process events to repaint changes
        QtWidgets.QApplication.processEvents()

        if not self.validate_url():
            self._enable_buttons()
            self._update_progress(0)
            # Update any messages
            self._mongo_input.setText(self.mongo_url)
            return

        self._update_progress(100)
        QtWidgets.QApplication.processEvents()

        os.environ["QUADPYPE_MONGO"] = self.mongo_url
        try:
            self._secure_registry.set_item("quadpypeMongo", self.mongo_url)
        except ValueError:
            print("Couldn't save Mongo URL to keyring")

        self.done(7)

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

    def _on_mongo_url_change(self, new_value):
        # Strip the value
        new_value = new_value.strip()
        # Store new mongo url to variable
        self.mongo_url = new_value

        msg = None
        # Change style of input
        if not new_value:
            self._mongo_input.remove_state()
        elif not self.mongo_url_regex.match(new_value):
            self._mongo_input.set_invalid()
            msg = (
                "Mongo URL should start with"
                " <b>\"mongodb://\"</b> or <b>\"mongodb+srv://\"</b>"
            )
        else:
            self._mongo_input.set_valid()

        self.set_invalid_mongo_url(msg)

    def validate_url(self):
        """Validate if entered url is ok.

        Returns:
            True if url is valid mongo string.

        """
        if not self.mongo_url:
            is_valid = False
            reason_str = "No connection string specified"
        else:
            is_valid, reason_str = mongo_module.validate_mongo_connection_with_info(self.mongo_url)

        if not is_valid:
            self.set_invalid_mongo_connection(self.mongo_url)
            self._mongo_input.set_invalid()
            self.update_console(reason_str, True)
            self._show_console()
            return False

        self.set_invalid_mongo_connection(None)
        self._mongo_input.set_valid()
        return True

    def set_invalid_mongo_url(self, reason):
        if reason is None:
            self._mongo_connection_msg.setText("")
        else:
            self._mongo_connection_msg.setText("{}".format(reason))

    def set_invalid_mongo_connection(self, mongo_url, connecting=False):
        if not mongo_url:
            self.set_invalid_mongo_url("<b>No connection string specified</b>")
            return

        if connecting:
            msg = "Connecting to: <b>{}</b>".format(mongo_url)
        else:
            msg = "Can't connect to: <b>{}</b>".format(mongo_url)

        self.set_invalid_mongo_url(msg)

    def update_console(self, msg: str, error: bool = False) -> None:
        """Display message in console.

        Args:
            msg (str): message.
            error (bool): if True, print it red.
        """
        self._console_widget.update_console(msg, error)
        if self._log:
            header = "!!! " if error else ">>> "
            self._log(f"{header}{msg}")

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
        return super(DatabaseStringDialog, self).closeEvent(event)


class MessageDialog(QtWidgets.QDialog):
    """Simple message dialog with title, message and OK button."""
    def __init__(self, title, message):
        super().__init__()

        # Set logo as icon of the window
        icon_path = get_app_icon_path()
        pixmap_app_logo = QtGui.QPixmap(icon_path)
        self.setWindowIcon(QtGui.QIcon(pixmap_app_logo))

        # Set title
        self.setWindowTitle(title)

        # Set message
        label_widget = QtWidgets.QLabel(message, self)

        ok_btn = QtWidgets.QPushButton("OK", self)
        btns_layout = QtWidgets.QHBoxLayout()
        btns_layout.addStretch(1)
        btns_layout.addWidget(ok_btn, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label_widget, 1)
        layout.addLayout(btns_layout, 0)

        ok_btn.clicked.connect(self._on_ok_clicked)

        self._label_widget = label_widget
        self._ok_btn = ok_btn

    def _on_ok_clicked(self):
        self.close()

    def showEvent(self, event):
        super(MessageDialog, self).showEvent(event)
        self.setStyleSheet(load_stylesheet())


class ZXPUpdateWindow(QtWidgets.QDialog):
    """QuadPype update window."""

    _width = 500
    _height = 100

    def __init__(self, version: PackageVersion, zxp_hosts: [ZXPExtensionData], parent=None):
        super().__init__(parent)
        self._quadpype_version = version
        self._zxp_hosts = zxp_hosts
        self._log = log.getLogger(str(__class__))

        self.setWindowTitle(
            f"QuadPype is updating ..."
        )
        self.setModal(True)
        self.setWindowFlags(
            QtCore.Qt.WindowMinimizeButtonHint
        )

        fonts_dir = Path(get_fonts_dir_path())
        roboto_font_path = str(fonts_dir.joinpath("RobotoMono-Regular.ttf"))
        poppins_font_path = str(fonts_dir.joinpath("Poppins"))
        icon_path = get_app_icon_path()

        # Install fonts
        QtGui.QFontDatabase.addApplicationFont(roboto_font_path)
        for filename in os.listdir(poppins_font_path):
            if os.path.splitext(filename)[1] == ".ttf":
                QtGui.QFontDatabase.addApplicationFont(filename)

        # Load logo
        pixmap_app_logo = QtGui.QPixmap(icon_path)
        # Set logo as icon of the window
        self.setWindowIcon(QtGui.QIcon(pixmap_app_logo))

        self._pixmap_app_logo = pixmap_app_logo

        self._update_thread = None

        self._init_ui()

        # Set stylesheet
        self.setStyleSheet(load_stylesheet())
        self._run_update()

    def _init_ui(self):

        # Main info
        # --------------------------------------------------------------------
        main_label = QtWidgets.QLabel(
            f"<b>QuadPype</b> is updating to {self._quadpype_version}", self)
        main_label.setWordWrap(True)
        main_label.setObjectName("MainLabel")

        # Progress bar
        # --------------------------------------------------------------------
        progress_bar = NiceProgressBar(self)
        progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        progress_bar.setTextVisible(False)

        # add all to main
        main = QtWidgets.QVBoxLayout(self)
        main.addSpacing(15)
        main.addWidget(main_label, 0)
        main.addSpacing(15)
        main.addWidget(progress_bar, 0)
        main.addSpacing(15)

        self._main_label = main_label
        self._progress_bar = progress_bar

    def showEvent(self, event):
        super().showEvent(event)
        current_size = self.size()
        new_size = QtCore.QSize(
            max(current_size.width(), self._width),
            max(current_size.height(), self._height)
        )
        if current_size != new_size:
            self.resize(new_size)

    def _run_update(self):
        """Start install process.

        This will once again validate entered path and mongo if ok, start
        working thread that will do actual job.
        """
        # Check if install thread is not already running
        if self._update_thread and self._update_thread.isRunning():
            return
        self._progress_bar.setRange(0, 0)
        update_thread = ZXPUpdateThread(self)
        update_thread.set_version(self._quadpype_version)
        update_thread.set_zxp_hosts(self._zxp_hosts)
        update_thread.log_signal.connect(self._print)
        update_thread.step_text_signal.connect(self.update_step_text)
        update_thread.finished.connect(self._installation_finished)

        self._update_thread = update_thread

        update_thread.start()

    def _installation_finished(self):
        self._update_thread.result()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(100)
        QtWidgets.QApplication.processEvents()
        self.done(int(QtWidgets.QDialog.Accepted))
        if self._update_thread.isRunning():
            self._update_thread.quit()
        self.close()

    def _print(self, message: str, error: bool = False) -> None:
        """Print the message in the console.

        Args:
            message (str): message.
            error (bool): if True, print it red.
        """
        if error:
            self._log.error(message)
        else:
            self._log.info(message)

    def update_step_text(self, text: str) -> None:
        """Print the message in the console.

        Args:
            text (str): Text describing the current step.
        """
        self._main_label.setText(text)
