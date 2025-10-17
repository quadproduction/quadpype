import logging

from qtpy import QtWidgets, QtCore

from quadpype.tools.utils.models import TreeModel
from quadpype.tools.utils.lib import (
    preserve_expanded_rows,
    preserve_selection,
)

from .models import (
    AssetModel,
    LookModel
)

from .actions import get, display

from .views import View


class AssetOutliner(QtWidgets.QWidget):
    refreshed = QtCore.Signal()
    selection_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        title = QtWidgets.QLabel("Assets", self)
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")

        model = AssetModel()
        view = View(self)
        view.setModel(model)
        view.customContextMenuRequested.connect(self.right_mouse_menu)
        view.setSortingEnabled(False)
        view.setHeaderHidden(True)
        view.setIndentation(10)

        from_all_asset_btn = QtWidgets.QPushButton(
            "Get All Assets", self
        )
        from_selection_btn = QtWidgets.QPushButton(
            "Get Assets From Selection", self
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(from_all_asset_btn)
        layout.addWidget(from_selection_btn)
        layout.addWidget(view)

        # Build connections
        from_selection_btn.clicked.connect(self.get_selected_assets)
        from_all_asset_btn.clicked.connect(self.get_all_assets)

        selection_model = view.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)

        self.view = view
        self.model = model

        self.log = logging.getLogger(__name__)

    @display.error
    def clear(self):
        self.model.clear()
        self.selection_changed.emit()

    def add_items(self, items):
        """Add new items to the outliner"""

        self.model.add_items(items)
        self.refreshed.emit()

    @display.error
    def get_selected_items(self):
        """Get current selected items from view

        Returns:
            list: list of dictionaries
        """

        selection_model = self.view.selectionModel()
        return [row.data(TreeModel.ItemRole)
                for row in selection_model.selectedRows(0)]

    def get_all_assets(self):
        @display.error
        def _process():
            self.clear()
            items = get.all_assets()
            self.add_items(items)

        """Add all items from the current scene"""
        with preserve_expanded_rows(self.view):
            with preserve_selection(self.view):
                _process()

    def get_selected_assets(self):
        """Add all selected items from the current scene"""

        @display.error
        def _process():
            self.clear()
            items = get.selected_assets()

            self.add_items(items)
            return len(items) > 0

        with preserve_expanded_rows(self.view):
            with preserve_selection(self.view):
                return _process()

    def get_nodes(self, selection=False):
        """Find the nodes in the current scene per asset."""
        return

    @display.error
    def select_asset_from_items(self):
        """Select nodes from listed asset"""
        items = self.get_nodes(selection=False)
        nodes = []
        for item in items.values():
            nodes.extend(item["nodes"])

    def right_mouse_menu(self, pos):
        """Build RMB menu for asset outliner"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        menu = QtWidgets.QMenu(self.view)

        # Direct assignment
        apply_action = QtWidgets.QAction(menu, text="Select nodes")
        apply_action.triggered.connect(self.select_asset_from_items)

        if not active.isValid():
            apply_action.setEnabled(False)

        menu.addAction(apply_action)

        menu.exec_(globalpos)


class LookOutliner(QtWidgets.QWidget):
    menu_apply_action = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Looks from database
        title = QtWidgets.QLabel("Looks", self)
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 12px")
        title.setAlignment(QtCore.Qt.AlignCenter)

        model = LookModel()

        # Proxy for dynamic sorting
        proxy = QtCore.QSortFilterProxyModel()
        proxy.setSourceModel(model)

        view = View(self)
        view.setModel(proxy)
        view.setMinimumHeight(180)
        view.setToolTip("Use right mouse button menu for direct actions")
        view.customContextMenuRequested.connect(self.right_mouse_menu)
        view.sortByColumn(0, QtCore.Qt.AscendingOrder)

        # look manager layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(view)

        self.view = view
        self.model = model

    def clear(self):
        self.model.clear()

    def add_items(self, items):
        self.model.add_items(items)

    @display.error
    def get_selected_items(self):
        """Get current selected items from view

        Returns:
            list: list of dictionaries
        """

        items = [i.data(TreeModel.ItemRole) for i in self.view.get_indices()]
        return [item for item in items if item is not None]

    @display.error
    def right_mouse_menu(self, pos):
        """Build RMB menu for look view"""

        active = self.view.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column
        globalpos = self.view.viewport().mapToGlobal(pos)

        if not active.isValid():
            return

        menu = QtWidgets.QMenu(self.view)

        # Direct assignment
        apply_action = QtWidgets.QAction(menu, text="Assign looks..")
        apply_action.triggered.connect(self.menu_apply_action)

        menu.addAction(apply_action)

        menu.exec_(globalpos)
