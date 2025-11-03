import sys
import logging

import bpy

from qtpy import QtWidgets, QtCore

from quadpype import style
from quadpype.tools.utils.lib import qt_app_context
from quadpype.pipeline.load.utils import get_repres_contexts
from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS,
    get_avalon_node,
    has_avalon_node
)
from quadpype.hosts.blender.api.lib import get_objects_from_mapped
from quadpype.hosts.blender.plugins.load.load_shaders import ShadersLoader

from .widgets import (
    AssetOutliner,
    LookOutliner
)
from .actions import display, filter_by, get


module = sys.modules[__name__]
module.window = None


class BlenderLookAssignerWindow(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.log = logging.getLogger(__name__)

        self.setObjectName("lookManager")
        self.setWindowTitle("Look Manager 1.4.0")
        window_flags = QtCore.Qt.Window \
                       | QtCore.Qt.WindowStaysOnTopHint

        self.setWindowFlags(window_flags)
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

        reuse_materials = QtWidgets.QCheckBox(
            "Use already loaded materials", looks_widget
        )
        reuse_materials.setToolTip(
            "If checked, will avoid loading new materials if "
            "previous materials with identical ids have been loaded before."
        )
        reuse_materials.setChecked(True)
        remove_unused_btn = QtWidgets.QPushButton(
            "Remove Unused Looks", looks_widget
        )

        looks_layout = QtWidgets.QVBoxLayout(looks_widget)
        looks_layout.addWidget(look_outliner)
        looks_layout.addWidget(reuse_materials)
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
        remove_unused_btn.clicked.connect(self.remove_unused_looks)

        # Open widgets
        self.asset_outliner = asset_outliner
        self.look_outliner = look_outliner
        self.status = status
        self.warn_layer = warn_layer

        # Buttons
        self.remove_unused = remove_unused_btn
        self.reuse_materials = reuse_materials

        self._first_show = True

    def showEvent(self, event):
        super(BlenderLookAssignerWindow, self).showEvent(event)
        self.asset_outliner.get_all_assets()
        if self._first_show:
            self._first_show = False
            self.setStyleSheet(style.load_stylesheet())

    def closeEvent(self, event):
        super(BlenderLookAssignerWindow, self).closeEvent(event)

    def echo(self, message):
        self.status.showMessage(message, 1500)

    @display.error
    def refresh(self):
        """Refresh the content"""

        # Get all containers and information
        self.asset_outliner.clear()
        found_items = self.asset_outliner.get_all_assets()
        if not found_items:
            self.look_outliner.clear()

    @display.error
    def on_asset_selection_changed(self):
        """Get selected items from asset loader and fill look outliner"""

        items = self.asset_outliner.get_selected_items()
        self.look_outliner.clear()
        self.look_outliner.add_items(items)

    @display.error
    def on_process_selected(self):
        """Process all selected looks for the selected assets"""

        selected_looks = self.look_outliner.get_selected_items()
        selected_assets = self.asset_outliner.get_selected_items()
        grouped_assets = filter_by.identical_assets(selected_assets)

        for single_look in selected_looks:
            repr_id = str(single_look['repr_id'])
            shader_repr = get_repres_contexts([repr_id])

            assert shader_repr, f"Can not retrieve asset representation with id '{repr_id}'"

            shader_repr = next(iter(shader_repr.values()))

            for grouped_items in grouped_assets:
                first_item = next(iter(grouped_items))
                label = first_item['name']

                if self._selected_is_asset(grouped_items):
                    for namespace in first_item.children():
                        ShadersLoader().process_asset(
                            name=label,
                            context=shader_repr,
                            options={
                                'selected_objects': get.objects_from_collection_name(namespace['collection_name']),
                                'reuse_materials': self.reuse_materials.isChecked()
                            }
                        )
                    continue

                for item in grouped_items:
                    collection_name = item.get('collection_name')
                    assert collection_name, f"Can not retrieve collection named '{collection_name}' in scene."

                    ShadersLoader().process_asset(
                        name=label,
                        context=shader_repr,
                        options={
                            'selected_objects': get.objects_from_collection_name(collection_name),
                            'reuse_materials': self.reuse_materials.isChecked()
                        }
                    )
        self.echo(f"{len(selected_looks)} look(s) applied on {len(selected_assets)} asset(s).")

    @display.error
    def remove_unused_looks(self):
        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        assert avalon_container, "Can not found avalon container which contains scene assets."
        look_instances = [col for col in avalon_container.children if has_avalon_node(col)
                          and get_avalon_node(col).get("family") == "look"]

        for look_col in look_instances:
            avalon_node = get_avalon_node(look_col)
            members = get_objects_from_mapped(avalon_node.get('members', []))
            images_to_check = set()
            for material in members:
                if not material.use_nodes:
                    continue
                for node in material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        images_to_check.add(node.image)

                if material.users != 0:
                    continue

                bpy.data.materials.remove(material)

            for img in images_to_check:
                if img.users != 0:
                    continue
                bpy.data.images.remove(img)

            if any(m not in bpy.data.materials[:] for m in members):
                bpy.data.collections.remove(look_col)
                continue

    @staticmethod
    def _selected_is_asset(grouped_items):
        return len(grouped_items) == 1 and not grouped_items[0].get('namespace', None)


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
