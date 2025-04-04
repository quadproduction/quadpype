"""Create render."""
import bpy

from quadpype.lib import version_up
from quadpype.hosts.blender.api import plugin, lib
from quadpype.hosts.blender.api.render_lib import prepare_rendering
from quadpype.hosts.blender.api.workio import save_file


class CreateRenderlayer(plugin.BlenderCreator):
    """Single baked camera."""

    identifier = "io.quadpype.creators.blender.render"
    label = "Render"
    family = "render"
    icon = "eye"

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        try:
            # Run parent create method
            collection = super().create(
                subset_name, instance_data, pre_create_data
            )

            prepare_rendering(collection)
        except Exception:
            # Remove the instance if there was an error
            bpy.data.collections.remove(collection)
            raise

        # TODO: this is undesiderable, but it's the only way to be sure that
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

        return defs
