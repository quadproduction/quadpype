from qtpy import QtWidgets, QtCore, QtGui

from quadpype.widgets import BaseToolDialog
from quadpype.style import (
    load_stylesheet,
    app_icon_path
)
from quadpype.hosts.aftereffects import api


class ToolButton(QtWidgets.QPushButton):
    triggered = QtCore.Signal(str)

    def __init__(self, identifier, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._identifier = identifier

        self.clicked.connect(self._on_click)

    def _on_click(self):
        self.triggered.emit(self._identifier)


class TransferExpositionToolsDialog(BaseToolDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        app_label = "QuadPype"
        self.setWindowTitle("{} Transfer exposition".format(app_label))
        icon = QtGui.QIcon(app_icon_path())
        self.setWindowIcon(icon)
        self.setStyleSheet(load_stylesheet())

        if self.can_stay_on_top:
            self.setWindowFlags(
                self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
            )

        empty_label = QtWidgets.QLabel(
            api.get_stub().get_active_document_full_name()
        )

        # Separator line
        separator_widget = QtWidgets.QWidget(self)
        separator_widget.setObjectName("Separator")
        separator_widget.setMinimumHeight(2)
        separator_widget.setMaximumHeight(2)

        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok_click)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(empty_label)
        layout.addStretch(1)
        layout.addWidget(separator_widget)
        layout.addWidget(ok_btn)

        self.resize(600, 600)

    def _on_ok_click(self):
        self.close()
