"""Create a camera asset."""

import bpy

from quadpype.hosts.blender.api import plugin, lib
from quadpype.hosts.blender.api.pipeline import AVALON_INSTANCES


class CreateCamera(plugin.BlenderCreator):
    """Polygonal static geometry."""

    identifier = "io.quadpype.creators.blender.camera"
    label = "Camera"
    family = "camera"
    icon = "video-camera"

    create_as_asset_group = True

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):

        asset_group = super().create(subset_name,
                                     instance_data,
                                     pre_create_data)

        bpy.context.view_layer.objects.active = asset_group
        if pre_create_data.get("use_selection"):
            for obj in lib.get_selection():
                obj.parent = asset_group
        else:
            plugin.deselect_all()
            camera = bpy.data.cameras.new(subset_name)
            camera_obj = bpy.data.objects.new(subset_name, camera)

            instances = bpy.data.collections.get(AVALON_INSTANCES)
            instances.objects.link(camera_obj)

            bpy.context.view_layer.objects.active = asset_group
            camera_obj.parent = asset_group

        return asset_group

    def get_instance_attr_defs(self):
        defs = lib.collect_animation_defs(self.create_context)
        return defs