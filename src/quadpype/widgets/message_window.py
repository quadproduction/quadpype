import sys
import logging
from qtpy import QtWidgets, QtCore, QtGui

from quadpype.style import get_app_icon_path

log = logging.getLogger(__name__)


class Window(QtWidgets.QWidget):
    def __init__(self, parent, title, message, level):
        super().__init__()
        self.parent = parent
        self.title = title
        self.message = message
        self.level = level
        self._answer = None

        self.setWindowTitle(self.title)

        if self.level == "info":
            self._info()
        elif self.level == "warning":
            self._warning()
        elif self.level == "critical":
            self._critical()
        elif self.level == "ask":
            self._ask()

    def _info(self):
        self.setWindowTitle(self.title)
        rc = QtWidgets.QMessageBox.information(
            self, self.title, self.message)
        if rc:
            self.exit()

    def _warning(self):
        self.setWindowTitle(self.title)
        rc = QtWidgets.QMessageBox.warning(
            self, self.title, self.message)
        if rc:
            self.exit()

    def _critical(self):
        self.setWindowTitle(self.title)
        rc = QtWidgets.QMessageBox.critical(
            self, self.title, self.message)
        if rc:
            self.exit()

    def _ask(self):
        self._answer = None
        rc = QtWidgets.QMessageBox.question(
            self,
            self.title,
            self.message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        self._answer = False
        if rc == QtWidgets.QMessageBox.Yes:
            self.answer = True
            self.exit()

    def exit(self):
        self.hide()
        # self.parent.exec_()
        # self.parent.hide()
        return


def message(title=None, message=None, level="info", parent=None):
    """
        Produces centered dialog with specific level denoting severity
    Args:
        title: (string) dialog title
        message: (string) message
        level: (string) info|warning|critical
        parent: (QtWidgets.QApplication)

    Returns:
         None
    """
    app = parent
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    ex = Window(app, title, message, level)
    ex.show()

    # Move widget to center of screen
    try:
        desktop_rect = QtWidgets.QApplication.desktop().availableGeometry(ex)
        center = desktop_rect.center()
        ex.move(
            int(center.x() - (ex.width() * 0.5)),
            int(center.y() - (ex.height() * 0.5))
        )
    except Exception:  # noqa
        # skip all possible issues that may happen feature is not crucial
        log.warning("Couldn't center message.", exc_info=True)

    if level == "ask":
        return ex.answer


class ScrollMessageBox(QtWidgets.QDialog):
    """
        Basic version of scrollable QMessageBox. No other existing dialog
        implementation is scrollable.
        Args:
            icon: <QtWidgets.QMessageBox.Icon>
            title: <string>
            messages: <list> of messages
            cancelable: <boolean> - True if Cancel button should be added
    """
    def __init__(self, icon, title, messages, cancelable=False):
        super().__init__()

        self.setWindowTitle(title)
        window_icon = QtGui.QIcon(get_app_icon_path())
        self.setWindowIcon(window_icon)

        self.icon = icon

        self.setWindowFlags(QtCore.Qt.WindowTitleHint)

        layout = QtWidgets.QVBoxLayout(self)

        scroll_widget = QtWidgets.QScrollArea(self)
        scroll_widget.setWidgetResizable(True)
        content_widget = QtWidgets.QWidget(self)
        scroll_widget.setWidget(content_widget)

        message_len = 0
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        for msg in messages:
            label_widget = QtWidgets.QLabel(msg, content_widget)
            content_layout.addWidget(label_widget)
            message_len = max(message_len, len(msg))

        # guess size of scrollable area
        desktop = QtWidgets.QApplication.desktop()
        max_width = desktop.availableGeometry().width()
        scroll_widget.setMinimumWidth(
            min(max_width, message_len * 6)
        )
        layout.addWidget(scroll_widget)

        if not cancelable:  # if no specific buttons OK only
            buttons = QtWidgets.QDialogButtonBox.Ok
        else:
            buttons = QtWidgets.QDialogButtonBox.Ok | \
                      QtWidgets.QDialogButtonBox.Cancel

        btn_box = QtWidgets.QDialogButtonBox(buttons)
        btn_box.accepted.connect(self.accept)

        if cancelable:
            btn_box.rejected.connect(self.reject)

        btn = QtWidgets.QPushButton('Copy to clipboard')
        btn.clicked.connect(lambda: QtWidgets.QApplication.
                            clipboard().setText("\n".join(messages)))
        btn_box.addButton(btn, QtWidgets.QDialogButtonBox.NoRole)

        layout.addWidget(btn_box)
        self.show()
