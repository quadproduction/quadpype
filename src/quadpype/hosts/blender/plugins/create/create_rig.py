"""Create a rig asset."""

import bpy

from quadpype.hosts.blender.api import plugin, lib


class CreateRig(plugin.BlenderCreator):
    """Artist-friendly rig with controls to direct motion."""

    identifier = "io.quadpype.creators.blender.rig"
    label = "Rig"
    family = "rig"
    icon = "wheelchair"

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
            if self.create_as_asset_group:
                bpy.context.view_layer.objects.active = asset_group
            for obj in lib.get_selection():
                if self.create_as_asset_group:
                    obj.parent = asset_group
                    continue
                asset_group.objects.link(obj)
        return asset_group
