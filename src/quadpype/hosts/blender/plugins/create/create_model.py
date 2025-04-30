"""Create a model asset."""
import bpy

from quadpype.hosts.blender.api import plugin, lib


class CreateModel(plugin.BlenderCreator):
    """Polygonal static geometry."""

    identifier = "io.quadpype.creators.blender.model"
    label = "Model"
    family = "model"
    icon = "cube"

    create_as_asset_group = True

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):
        self.create_as_asset_group = pre_create_data.get("create_as_asset_group", False)

        asset_group = super().create(subset_name,
                                     instance_data,
                                     pre_create_data)

        # Add selected objects to instance
        if pre_create_data.get("use_selection"):
            bpy.context.view_layer.objects.active = asset_group
            for obj in lib.get_selection():
                if self.create_as_asset_group:
                    obj.parent = asset_group
                    continue
                asset_group.objects.link(obj)

        return asset_group
