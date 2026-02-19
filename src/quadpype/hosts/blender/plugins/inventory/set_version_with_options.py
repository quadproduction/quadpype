from quadpype.lib import Logger, BoolDef, UILabelDef, UISeparatorDef
from quadpype.tools.attribute_defs import AttributeDefinitionsDialog
from quadpype.pipeline import InventoryAction
from qtpy.QtWidgets import QApplication

OPTIONS = [
            UILabelDef("Keep on Objects:"),
            BoolDef(
                "copy_materials",
                default=True,
                label="Materials"
            ),
            BoolDef(
                "copy_modifiers",
                default=True,
                label="Modifiers"
            ),
            BoolDef(
                "copy_constraints",
                default=True,
                label="Constraints"
            ),
            BoolDef(
                "copy_vertex_groups",
                default=True,
                label="Vertex Groups"
            ),
            BoolDef(
                "copy_parents",
                default=True,
                label="Parents"
            ),
            BoolDef(
                "copy_actions",
                default=True,
                label="Actions"
            ),
            UISeparatorDef(),
            UILabelDef("Keep on Meshes:"),
            BoolDef(
                "copy_shape_key",
                default=True,
                label="Shape Keys"
            ),
            BoolDef(
                "copy_uv_maps",
                default=True,
                label="UV Maps"
            ),
            BoolDef(
                "copy_vertex_color",
                default=True,
                label="Vertex Color"
            ),
        ]

class SetVersionWithOptions(InventoryAction):

    label = "Set Version with Options"
    icon = "hashtag"
    color = "#cc0000"

    log = Logger.get_logger(__name__)

    def process(self, containers):
        active = QApplication.instance().activeWindow()
        dialog = AttributeDefinitionsDialog(OPTIONS, active)
        dialog.setWindowTitle(self.label + " Options")

        if not dialog.exec_():
            return None

        options = dialog.get_values()
        active._view._show_version_dialog(containers, options)


class SetLastVersionWithOptions(InventoryAction):

    label = "Update to Latest with Options"
    icon = "angle-double-up"
    color = "#cc0000"
    log = Logger.get_logger(__name__)

    def process(self, containers):
        active = QApplication.instance().activeWindow()
        dialog = AttributeDefinitionsDialog(OPTIONS, active)
        dialog.setWindowTitle(self.label + " Options")

        if not dialog.exec_():
            return None

        options = dialog.get_values()
        active._view._update_containers(containers, version=-1, options=options)
