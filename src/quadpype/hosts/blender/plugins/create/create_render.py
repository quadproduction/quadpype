"""Create render."""
import bpy

from quadpype.lib import version_up, EnumDef, BoolDef, UISeparatorDef
from quadpype.pipeline import get_current_project_name
from quadpype.settings import get_project_settings
from quadpype.hosts.blender.api import plugin, lib
from quadpype.hosts.blender.api.render_lib import prepare_rendering
from quadpype.hosts.blender.api.workio import save_file


class CreateRenderlayer(plugin.BlenderCreator):
    """Single baked camera."""

    identifier = "io.quadpype.creators.blender.render"
    label = "Render"
    family = "render"
    icon = "eye"

    auto_connect_nodes_default = False
    connect_to_all_outputs = False

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        try:
            # Run parent create method
            collection = super().create(
                subset_name, instance_data, pre_create_data
            )
            prepare_rendering(
                asset_group=collection,
                auto_connect_nodes=pre_create_data.get('auto_connect_nodes', self.auto_connect_nodes_default),
                connect_to_all_outputs=pre_create_data.get('connect_to_all_outputs', self.connect_to_all_outputs)
            )
        except Exception:
            # Remove the instance if there was an error
            bpy.data.collections.remove(collection)
            raise

        # TODO: this is undesirable, but it's the only way to be sure that
        # the file is saved before the render starts.
        # Blender, by design, doesn't set the file as dirty if modifications
        # happen by script. So, when creating the instance and setting the
        # render settings, the file is not marked as dirty. This means that
        # there is the risk of sending to deadline a file without the right
        # settings. Even the validator to check that the file is saved will
        # detect the file as saved, even if it isn't. The only solution for
        # now it is to force the file to be saved.
        if bpy.data.filepath:
            filepath = version_up(bpy.data.filepath)
            save_file(filepath, copy=False)

        return collection

    def get_instance_attr_defs(self):
        defs = lib.collect_animation_defs()
        project_settings = get_project_settings(get_current_project_name())
        instance_per_layer = project_settings["blender"].get("RenderSettings", {}).get("instance_per_layer", None)
        if instance_per_layer:
            defs.extend(
                [
                    UISeparatorDef(),
                    EnumDef(
                        "render_layers",
                        items=[view_layer.name for view_layer in bpy.context.scene.view_layers],
                        default=[
                            view_layer.name for view_layer in bpy.context.scene.view_layers
                            if view_layer.use
                        ],
                        label="Layer(s) to render",
                        multiselection=True
                    ),
                    BoolDef(
                        "publish_global",
                        label="Also publish global render",
                        default=False
                    )
                ]
            )
        defs.extend(
            [
                UISeparatorDef(),
                EnumDef(
                    "device",
                    label="Device",
                    items=["CPU", "GPU"],
                    default="CPU"
                ),
                BoolDef(
                    "use_single_layer",
                    label="Use single layer",
                    default=False
                ),
                BoolDef(
                    "use_simplify",
                    label="Use simplify",
                    default=False
                ),
                BoolDef(
                    "use_motion_blur",
                    label="Use motion blur",
                    default=True
                ),
                BoolDef(
                    "use_border",
                    label="Render region",
                    default=False
                ),
                BoolDef(
                    "use_nodes",
                    label="Use nodes",
                    default=True
                )
            ]
        )
        return defs

    def get_pre_create_attr_defs(self):
        defs = super().get_pre_create_attr_defs()
        defs.extend(
            [
                UISeparatorDef(),
                BoolDef(
                    "auto_connect_nodes",
                    label="Auto connect already created nodes",
                    default=self.auto_connect_nodes_default
                ),
                BoolDef(
                    "connect_to_all_outputs",
                    label="Connect to individual layers in each output",
                    default=self.connect_to_all_outputs
                ),
            ]
        )
        return defs
