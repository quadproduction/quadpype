from qtpy import QtWidgets, QtCore, QtGui

from quadpype.widgets import BaseToolDialog
from quadpype.style import (
    load_stylesheet,
    app_icon_path
)
from quadpype.hosts.aftereffects import api
from quadpype.pipeline import (
    get_current_host_name,
    get_current_project_name
)
from quadpype.settings import get_project_settings


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
        self.stub = api.get_stub()
        self.generate_window()

    def generate_window(self):
        app_label = "QuadPype"
        self.setWindowTitle("{} Transfer exposition".format(app_label))
        icon = QtGui.QIcon(app_icon_path())
        self.setWindowIcon(icon)
        self.setStyleSheet(load_stylesheet())

        project_settings = get_project_settings(get_current_project_name())
        host_settings = project_settings.get(get_current_host_name(), {})
        disable_stay_on_top = host_settings.get('load', {}).get('auto_clic_import_dialog', False)

        if self.can_stay_on_top and not disable_stay_on_top:
            self.setWindowFlags(
                self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
            )

        # Left list
        self.left_list = QtWidgets.QListWidget()
        self.left_list.setSelectionMode(QtWidgets.QListWidget.MultiSelection)
        left_label = QtWidgets.QLabel("Options disponibles:")
        clear_left_btn = QtWidgets.QPushButton("Clear selection")
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(left_label)
        left_layout.addWidget(self.left_list)
        left_layout.addWidget(clear_left_btn)

        # Right list
        self.right_list = QtWidgets.QListWidget()
        self.right_list.setSelectionMode(QtWidgets.QListWidget.MultiSelection)
        right_label = QtWidgets.QLabel("Options sélectionnées:")
        clear_right_btn = QtWidgets.QPushButton("Clear selection")
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(right_label)
        right_layout.addWidget(self.right_list)
        right_layout.addWidget(clear_right_btn)

        # Center buttons
        center_layout = QtWidgets.QVBoxLayout()
        connect_btn = QtWidgets.QPushButton("Connect >")
        unconnect_btn = QtWidgets.QPushButton("< Disconnect")
        center_layout.addStretch()
        center_layout.addWidget(connect_btn)
        center_layout.addWidget(unconnect_btn)
        center_layout.addStretch()

        # Separator line
        separator_widget = QtWidgets.QWidget(self)
        separator_widget.setObjectName("Separator")
        separator_widget.setMinimumHeight(2)
        separator_widget.setMaximumHeight(2)

        # Bottom button
        bottom_layout = QtWidgets.QVBoxLayout()
        ok_btn = QtWidgets.QPushButton("OK")
        bottom_layout.addWidget(separator_widget)
        bottom_layout.addWidget(ok_btn)

        # Combine all layouts
        lists_layout = QtWidgets.QHBoxLayout()
        lists_layout.addLayout(left_layout, 40)
        lists_layout.addLayout(center_layout, 20)
        lists_layout.addLayout(right_layout, 40)

        main_vlayout = QtWidgets.QVBoxLayout(self)
        main_vlayout.addLayout(lists_layout, 90)
        main_vlayout.addLayout(bottom_layout, 10)

        # Populate lists with sample data
        self.populate_lists()

        # Connect signals
        connect_btn.clicked.connect(self.connect_items)
        unconnect_btn.clicked.connect(self.disconnect_items)
        clear_left_btn.clicked.connect(self.left_list.clearSelection)
        clear_right_btn.clicked.connect(self.right_list.clearSelection)
        ok_btn.clicked.connect(self.on_ok)

        self.resize(600, 600)

    def populate_lists(self):
        """Fill the lists with sample data"""
        for item in self.stub.get_items(True):
            self.left_list.addItem(item.name)

        for item in ["Selected 1", "Selected 2"]:
            self.right_list.addItem(item)

    def connect_items(self):
        """Move selected items from left to right list"""
        selected_items = self.left_list.selectedItems()
        for item in selected_items:
            row = self.left_list.row(item)
            self.right_list.addItem(self.left_list.takeItem(row))

    def disconnect_items(self):
        """Move selected items from right to left list"""
        selected_items = self.right_list.selectedItems()
        for item in selected_items:
            row = self.right_list.row(item)
            self.left_list.addItem(self.right_list.takeItem(row))

    def on_ok(self):
        self.close()
