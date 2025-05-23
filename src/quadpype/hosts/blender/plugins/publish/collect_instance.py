import bpy

import pyblish.api

from quadpype.pipeline.publish import KnownPublishError
from quadpype.hosts.blender.api.pipeline import has_avalon_node
from quadpype.hosts.blender.api import plugin

class CollectBlenderInstanceData(plugin.BlenderInstancePlugin):
    """Validator to verify that the instance is not empty"""

    order = pyblish.api.CollectorOrder
    hosts = ["blender"]
    families = ["model", "pointcache", "animation", "rig", "camera", "layout",
                "blendScene", "usd"]
    label = "Collect Instance"

    def process(self, instance):
        instance_node = instance.data["transientData"]["instance_node"]

        # Collect members of the instance
        members = [instance_node]
        if isinstance(instance_node, bpy.types.Collection):
            members.extend(instance_node.objects)
            members.extend(instance_node.children)

            # Special case for animation instances, include armatures
            if instance.data["family"] == "animation":
                for obj in instance_node.objects:
                    if obj.type == 'EMPTY' and has_avalon_node(obj):
                        members.extend(
                            child for child in obj.children
                            if child.type == 'ARMATURE'
                        )
        elif isinstance(instance_node, bpy.types.Object):
            members.extend(instance_node.children_recursive)
        else:
            raise KnownPublishError(
                f"Unsupported instance node type '{type(instance_node)}' "
                f"for instance '{instance}'"
            )

        instance[:] = members
