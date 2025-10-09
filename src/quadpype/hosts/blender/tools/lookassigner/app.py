import sys
import time
import logging

from qtpy import QtWidgets, QtCore
import bpy

from quadpype import style
from quadpype.tools.utils.lib import qt_app_context
#
from .widgets import (
    AssetOutliner,
    LookOutliner
)

module = sys.modules[__name__]
module.window = None


class BlenderLookAssignerWindow(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.log = logging.getLogger(__name__)
        #
        # Store callback references
        self._callbacks = []
        self._connections_set_up = False

        # filename = get_workfile()

        self.setObjectName("lookManager")
        self.setWindowTitle("Look Manager 1.4.0 - [{}]".format("test"))
        self.setWindowFlags(QtCore.Qt.Window)
        self.setParent(parent)

        self.resize(750, 500)

        self.setup_ui()

    def setup_ui(self):
        """Build the UI"""

        main_splitter = QtWidgets.QSplitter(self)

        # Assets (left)
        asset_outliner = AssetOutliner(main_splitter)

        # Looks (right)
        looks_widget = QtWidgets.QWidget(main_splitter)

        look_outliner = LookOutliner(looks_widget)  # Database look overview

        assign_selected = QtWidgets.QCheckBox(
            "Assign to selected only", looks_widget
        )
        assign_selected.setToolTip("Whether to assign only to selected nodes "
                                   "or to the full asset")
        remove_unused_btn = QtWidgets.QPushButton(
            "Remove Unused Looks", looks_widget
        )

        looks_layout = QtWidgets.QVBoxLayout(looks_widget)
        looks_layout.addWidget(look_outliner)
        looks_layout.addWidget(assign_selected)
        looks_layout.addWidget(remove_unused_btn)

        main_splitter.addWidget(asset_outliner)
        main_splitter.addWidget(looks_widget)
        main_splitter.setSizes([350, 200])

        # Footer
        status = QtWidgets.QStatusBar(self)
        status.setSizeGripEnabled(False)
        status.setFixedHeight(25)
        warn_layer = QtWidgets.QLabel(
            "Current Layer is not defaultRenderLayer", self
        )
        warn_layer.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        warn_layer.setStyleSheet("color: #DD5555; font-weight: bold;")
        warn_layer.setFixedHeight(25)
        warn_layer.hide()

        footer = QtWidgets.QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(QtWidgets.QLabel(bpy.data.filepath))
        footer.addWidget(status)
        footer.addWidget(warn_layer)

        # Build up widgets
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.addWidget(main_splitter)
        main_layout.addLayout(footer)

        # Set column width
        asset_outliner.view.setColumnWidth(0, 200)
        look_outliner.view.setColumnWidth(0, 150)

        asset_outliner.selection_changed.connect(
            self.on_asset_selection_changed)

        asset_outliner.refreshed.connect(
            lambda: self.echo("Loaded assets..")
        )

        look_outliner.menu_apply_action.connect(self.on_process_selected)
        # remove_unused_btn.clicked.connect(remove_unused_looks)

        # Open widgets
        self.asset_outliner = asset_outliner
        self.look_outliner = look_outliner
        self.status = status
        self.warn_layer = warn_layer

        # Buttons
        self.remove_unused = remove_unused_btn
        self.assign_selected = assign_selected

        self._first_show = True

    def showEvent(self, event):
        super(BlenderLookAssignerWindow, self).showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setStyleSheet(style.load_stylesheet())

    def closeEvent(self, event):
        super(BlenderLookAssignerWindow, self).closeEvent(event)

    def echo(self, message):
        self.status.showMessage(message, 1500)

    def refresh(self):
        """Refresh the content"""

        # Get all containers and information
        self.asset_outliner.clear()
        found_items = self.asset_outliner.get_all_assets()
        if not found_items:
            self.look_outliner.clear()

    def on_asset_selection_changed(self):
        """Get selected items from asset loader and fill look outliner"""

        items = self.asset_outliner.get_selected_items()
        self.look_outliner.clear()
        self.look_outliner.add_items(items)

    def on_process_selected(self):
        """Process all selected looks for the selected assets"""

        return


self = sys.modules[__name__]
self._parent=None


def get_main_window():
    """Acquire Maya's main window"""
    from qtpy import QtWidgets
    if self._parent is None:
        self._parent = {
            widget.objectName(): widget
            for widget in QtWidgets.QApplication.topLevelWidgets()
        }["BlenderWindow"]
    return self._parent


# TODO : use same logic for this window ?
# def show_message(title, message):
#     from quadpype.widgets.message_window import Window
#     from .ops import BlenderApplication
#
#     BlenderApplication.get_app()
#
#     Window(
#         parent=None,
#         title=title,
#         message=message,
#         level="warning")
#
#
# def message_window(title, message):
#     from .ops import (
#         MainThreadItem,
#         execute_in_main_thread,
#         _process_app_events
#     )
#
#     mti = MainThreadItem(show_message, title, message)
#     execute_in_main_thread(mti)
#     _process_app_events()

def show():
    """Display Loader GUI

    Arguments:
        debug (bool, optional): Run loader in debug-mode,
            defaults to False

    """

    try:
        module.window.close()
        del module.window
    except (RuntimeError, AttributeError):
        pass

    mainwindow = get_main_window()

    with qt_app_context():
        window = BlenderLookAssignerWindow(parent=mainwindow)
        window.show()

        module.window = window
