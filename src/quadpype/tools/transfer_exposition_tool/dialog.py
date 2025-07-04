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

        self.comps_and_layers = QtWidgets.QTreeWidget()
        self.comps_and_layers.setHeaderHidden(True)
        refresh_comps_btn = QtWidgets.QPushButton("Refresh")
        refresh_comps_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.comps_and_layers)
        left_layout.addWidget(refresh_comps_btn)

        search_box = QtWidgets.QLineEdit()
        search_box.setPlaceholderText("Rechercher...")
        search_erase = QtWidgets.QPushButton()
        search_erase.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(search_box)
        search_layout.addWidget(search_erase)

        self.properties = QtWidgets.QTreeWidget()
        self.properties.setSelectionMode(QtWidgets.QTreeWidget.ExtendedSelection)
        clear_btn = QtWidgets.QPushButton("Clear selection")
        refresh_properties_btn = QtWidgets.QPushButton("Refresh")
        refresh_properties_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(clear_btn)
        buttons_layout.addWidget(refresh_properties_btn)
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addLayout(search_layout)
        right_layout.addWidget(self.properties)
        right_layout.addLayout(buttons_layout)
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
        lists_layout.addLayout(left_layout)
        lists_layout.addLayout(right_layout)

        main_vlayout = QtWidgets.QVBoxLayout(self)
        main_vlayout.addLayout(lists_layout, 90)
        main_vlayout.addLayout(bottom_layout, 10)

        self.populate_comps()
        self.populate_properties()

        self.comps_and_layers.itemClicked.connect(self.on_item_clicked)
        search_box.textChanged.connect(self.filter_items)
        search_erase.clicked.connect(lambda: search_box.setText(""))
        clear_btn.clicked.connect(self.properties.clearSelection)
        refresh_comps_btn.clicked.connect(self.populate_comps)
        refresh_properties_btn.clicked.connect(self.populate_properties)
        ok_btn.clicked.connect(self.on_ok)

        self.resize(1000, 400)

    def filter_items(self, text):
        filter_text = text.lower()

        def filter_recursive(item):
            child_visible = False

            item_text = item.text(0).lower()
            item_match = filter_text in item_text

            for i in range(item.childCount()):
                child = item.child(i)
                if filter_recursive(child) or item_match:
                    child_visible = True

            item.setHidden(not (item_match or child_visible))
            if child_visible and item.parent():
                item.parent().setExpanded(True)

            return item_match or child_visible

        for i in range(self.properties.topLevelItemCount()):
            filter_recursive(self.properties.topLevelItem(i))

    def populate_comps(self):
        self.comps_and_layers.clear()
        for comp in self.stub.get_active_comp_with_inner_layers():
            self._add_layer_to_parent(self.comps_and_layers, comp)
        self.comps_and_layers.expandAll()

    def _add_layer_to_parent(self, parent, layer):
        child = QtWidgets.QTreeWidgetItem(parent, [layer["name"]])
        child.setData(0, QtCore.Qt.UserRole, layer['id'])
        child.setData(1, QtCore.Qt.UserRole, layer['markers'])

        if layer.get('markers'):
            child.setForeground(0, QtGui.QBrush(QtGui.QColor(200, 200, 200)))
            child.setFlags(
                QtCore.Qt.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemIsDropEnabled
                | QtCore.Qt.ItemIsDragEnabled
                | QtCore.Qt.ItemIsSelectable
            )
        else:
            child.setForeground(0, QtGui.QBrush(QtGui.QColor(70, 70, 80)))
            child.setFlags(QtCore.Qt.ItemIsEnabled)
            child.flags()

        for layer in layer.get('layers', []):
            self._add_layer_to_parent(child, layer)

    def populate_properties(self):
        bold = QtGui.QFont()
        bold.setBold(True)

        self.properties.clear()
        for layer in self.stub.get_selected_layers():
            parent = QtWidgets.QTreeWidgetItem(self.properties, [layer.name])
            parent.setData(0, QtCore.Qt.UserRole, layer.id)
            for item in self.stub.get_layer_attributes_names(layer.id):
                has_marker = item.get('marker', False)
                child = QtWidgets.QTreeWidgetItem(
                    parent,
                    ["◢ " + item['name']] if has_marker else [item['name']]
                )
                child.setFont(0, bold) if has_marker else (
                    child.setForeground(0, QtGui.QBrush(QtGui.QColor(170, 170, 180)))
                )

    def on_ok(self):
        self.close()
