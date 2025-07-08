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

        search_box_comps = QtWidgets.QLineEdit()
        search_box_comps.setPlaceholderText("Rechercher...")
        search_erase_comps = QtWidgets.QPushButton()
        search_erase_comps.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        search_layout_comps = QtWidgets.QHBoxLayout()
        search_layout_comps.addWidget(search_box_comps)
        search_layout_comps.addWidget(search_erase_comps)

        self.comps_and_layers = QtWidgets.QTreeWidget()
        refresh_comps_btn = QtWidgets.QPushButton("Refresh")
        refresh_comps_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addLayout(search_layout_comps)
        left_layout.addWidget(self.comps_and_layers)
        left_layout.addWidget(refresh_comps_btn)

        search_box_properties = QtWidgets.QLineEdit()
        search_box_properties.setPlaceholderText("Rechercher...")
        search_erase_properties = QtWidgets.QPushButton()
        search_erase_properties.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        search_layout_properties = QtWidgets.QHBoxLayout()
        search_layout_properties.addWidget(search_box_properties)
        search_layout_properties.addWidget(search_erase_properties)

        self.properties = QtWidgets.QTreeWidget()
        self.properties.setSelectionMode(QtWidgets.QTreeWidget.ExtendedSelection)
        clear_btn = QtWidgets.QPushButton("Clear selection")
        refresh_properties_btn = QtWidgets.QPushButton("Refresh")
        refresh_properties_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(clear_btn)
        buttons_layout.addWidget(refresh_properties_btn)
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addLayout(search_layout_properties)
        right_layout.addWidget(self.properties)
        right_layout.addLayout(buttons_layout)

        separator_widget = QtWidgets.QWidget(self)
        separator_widget.setObjectName("Separator")
        separator_widget.setMinimumHeight(2)
        separator_widget.setMaximumHeight(2)

        self.result_success_label = QtWidgets.QLabel("")
        self.result_errors_label = QtWidgets.QLabel("")
        self.apply_btn = QtWidgets.QPushButton("Apply Exposure")
        self.apply_btn.setFixedHeight(40)
        self.apply_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton))
        self.result_success_label.setStyleSheet("color: #038C3E;")
        self.result_errors_label.setStyleSheet("color: #BF372A;")
        font = QtGui.QFont()
        font.setItalic(True)
        self.result_success_label.setFont(font)
        self.result_errors_label.setFont(font)
        self.result_success_label.setVisible(False)
        self.result_errors_label.setVisible(False)

        results_layout = QtWidgets.QVBoxLayout()
        results_layout.addWidget(self.result_success_label)
        results_layout.addWidget(self.result_errors_label)

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addLayout(results_layout, 100)
        bottom_layout.addWidget(separator_widget)
        bottom_layout.addWidget(self.apply_btn)

        lists_layout = QtWidgets.QHBoxLayout()
        lists_layout.addLayout(left_layout)
        lists_layout.addLayout(right_layout)

        main_vlayout = QtWidgets.QVBoxLayout(self)
        main_vlayout.addLayout(lists_layout, 90)
        main_vlayout.addLayout(bottom_layout, 10)

        self.populate_comps()
        self.populate_properties()

        self.comps_and_layers.itemClicked.connect(self.update_apply_btn_state)
        self.properties.itemClicked.connect(self.update_apply_btn_state)
        search_box_comps.textChanged.connect(self.filter_comps)
        search_box_properties.textChanged.connect(self.filter_properties)
        search_erase_properties.clicked.connect(lambda: search_box_properties.setText(""))
        search_erase_comps.clicked.connect(lambda: search_box_comps.setText(""))
        clear_btn.clicked.connect(self.properties.clearSelection)
        refresh_comps_btn.clicked.connect(self.populate_comps)
        refresh_properties_btn.clicked.connect(self.populate_properties)
        self.comps_and_layers.selectionModel().selectionChanged.connect(self.update_apply_btn_state)
        self.properties.selectionModel().selectionChanged.connect(self.update_apply_btn_state)
        self.apply_btn.clicked.connect(self.on_apply)

        self.update_apply_btn_state()

        self.resize(1000, 400)

    def filter_comps(self, text):
        filter_text = text.lower()
        for i in range(self.comps_and_layers.topLevelItemCount()):
            self._filter_item(self.comps_and_layers.topLevelItem(i), filter_text)

    def filter_properties(self, text):
        filter_text = text.lower()
        for i in range(self.properties.topLevelItemCount()):
            self._filter_item(self.properties.topLevelItem(i), filter_text)

    def _filter_item(self, item, filter_text):
        child_visible = False

        item_text = item.text(0).lower()
        item_match = filter_text in item_text

        for i in range(item.childCount()):
            child = item.child(i)
            if self._filter_item(child, filter_text) or item_match:
                child_visible = True

        item.setHidden(not (item_match or child_visible))
        if child_visible and item.parent():
            item.parent().setExpanded(True)

        return item_match or child_visible

    def populate_comps(self):
        self.comps_and_layers.clear()

        comps = self.stub.get_active_comp_with_inner_layers()
        if not comps:
            self.comps_and_layers.setHeaderLabel("No layer selected yet.")

        self.comps_and_layers.setHeaderLabel(', '.join([layer['name'] for layer in comps]))

        for comp in comps:
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

        for layer in layer.get('layers', []):
            self._add_layer_to_parent(child, layer)

    def populate_properties(self):
        self.properties.clear()

        layers = self.stub.get_selected_layers()

        if not layers:
            self.properties.setHeaderLabel("No layer selected yet.")

        self.properties.setHeaderLabel(', '.join([layer.name for layer in layers]))

        bold = QtGui.QFont()
        bold.setBold(True)
        masked_brush = QtGui.QBrush(QtGui.QColor(170, 170, 180))

        for layer in layers:
            parent = QtWidgets.QTreeWidgetItem(self.properties, [layer.name])
            parent.setData(0, QtCore.Qt.UserRole, layer.id)
            parent.setFlags(QtCore.Qt.ItemIsEnabled)
            parent.setForeground(0, masked_brush)

            for item in self.stub.get_layer_attributes_names(layer.id):
                child = QtWidgets.QTreeWidgetItem(parent, [item['name']])
                child.setData(0, QtCore.Qt.UserRole, layer.id)
                child.setFont(0, bold) if item.get('marker', False) else child.setForeground(0, masked_brush)

    def on_apply(self):
        layers = self.comps_and_layers.selectedItems()
        properties = self.properties.selectedItems()
        results_success = list()
        results_errors = list()

        for layer in layers:
            parent_layer_name = layer.parent().text(0)
            for layer_property in properties:
                selected_layer_id = layer_property.data(0, QtCore.Qt.UserRole)
                property_name = layer_property.text(0)
                try:
                    success = self.stub.apply_exposure(
                        effect_layer_name=layer.text(0),
                        effect_layer_parent_name=parent_layer_name,
                        target_layer_id=selected_layer_id,
                        target_property_name=property_name
                    )
                    if success:
                        results_success.append(f"{layer_property.parent().text(0)}/{property_name}")
                    else:
                        results_errors.append(f"{layer_property.parent().text(0)}/{property_name}")

                except ValueError:
                    results_errors.append(f"{layer_property.parent().text(0)}/{property_name}")

        if results_success:
            self.result_success_label.setVisible(True)
            self.result_success_label.setText(
                f"Applied with success : {', '.join([result for result in results_success])}."
            )
        if results_errors:
            self.result_errors_label.setVisible(True)
            self.result_errors_label.setText(
                f"Couldn't apply : {', '.join([result for result in results_errors])}."
            )

    def update_apply_btn_state(self):
        self.result_success_label.setVisible(False)
        self.result_errors_label.setVisible(False)
        self.apply_btn.setEnabled(all([self.comps_and_layers.selectedItems(), self.properties.selectedItems()]))
