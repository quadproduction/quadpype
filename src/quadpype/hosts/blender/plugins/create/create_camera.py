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

        self.create_as_asset_group = pre_create_data.get("create_as_asset_group", False)

        asset_group = super().create(subset_name,
                                     instance_data,
                                     pre_create_data)

        # bpy.context.view_layer.objects.active = asset_group
        cameras = _get_selection() if pre_create_data.get("use_selection") else _create_camera(subset_name, asset_group)

        for camera in cameras:
            if self.create_as_asset_group:
                camera.parent = asset_group
                continue
            asset_group.objects.link(camera)


        return asset_group

    def get_instance_attr_defs(self):
        defs = lib.collect_animation_defs(step=False)

        return defs


def _get_selection():
    return lib.get_selection()


def _create_camera(subset_name, asset_group):
    plugin.deselect_all()
    camera = bpy.data.cameras.new(subset_name)
    camera_obj = bpy.data.objects.new(subset_name, camera)

    instances = bpy.data.collections.get(AVALON_INSTANCES)
    instances.objects.link(camera_obj)

    bpy.context.view_layer.objects.active = asset_group

    return [camera]
