"""Create a Blender scene asset."""

import bpy

from quadpype.hosts.blender.api import plugin, lib


class CreateBlendScene(plugin.BlenderCreator):
    """Generic group of assets."""

    identifier = "io.quadpype.creators.blender.blendscene"
    label = "Blender Scene"
    family = "blendScene"
    icon = "cubes"

    maintain_selection = False

    def create(
        self, subset_name: str, instance_data: dict, pre_create_data: dict
    ):

        instance_node = super().create(subset_name,
                                       instance_data,
                                       pre_create_data)

        if pre_create_data.get("use_selection"):
            selection = lib.get_selection(include_collections=True)
            for data in selection:
                if isinstance(data, bpy.types.Collection):
                    instance_node.children.link(data)
                elif isinstance(data, bpy.types.Object):
                    instance_node.objects.link(data)

        return instance_node

    def remove_instances(self, instances):

        for instance in instances:
            node = instance.transient_data["instance_node"]
            bpy.data.collections.remove(node)

            self._remove_instance_from_context(instance)
