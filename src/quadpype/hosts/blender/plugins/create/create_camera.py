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

        parent_collection = self.get_parent_collection(cameras)
        target_collection = self.get_parent_collection(asset_group) if self.create_as_asset_group else asset_group

        if parent_collection:
            self.link_to_collection_recursively(
                collections_to_look_in=parent_collection,
                link_to=target_collection
            )

        return asset_group

    def link_to_collection_recursively(self, collections_to_look_in, link_to):
        for children in collections_to_look_in.children:
            self.link_to_collection_recursively(children, link_to)

        for blender_object in collections_to_look_in.objects:
            if blender_object in list(link_to.objects):
                continue

            link_to.objects.link(blender_object)

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
