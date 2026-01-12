import bpy

import pyblish.api
from quadpype.hosts.blender.api import (
    plugin,
    pipeline
)
from quadpype.pipeline import publish


class RemoveLooksTemporarily(
    plugin.BlenderExtractor, publish.OptionalPyblishPluginMixin
):
    """Remove all shaders on objects"""

    label = "Remove All Applied Materials"
    hosts = ["blender"]
    families = ["model", "rig", "layout", "blendScene", "animation", "pointcache"]
    order = pyblish.api.ExtractorOrder - 0.000001
    optional = True
    active = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        instance_name = f"{asset_name}_{subset}"
        instance_coll = bpy.data.collections.get(instance_name)
        objects_in_instance = pipeline.get_container_content(instance_coll)
        materials_by_objects = {}
        for obj in objects_in_instance:
            mats = []
            indices_to_remove = [i for i, slot in enumerate(obj.material_slots) if slot.material]
            for i in reversed(indices_to_remove):
                mat = obj.material_slots[i].material
                if mat:
                    mats.append(mat)
                    self.log.info(f"{mat.name} on {obj.name} will be temporarily removed.")
                obj.material_slots[i].material = None

            if mats:
                materials_by_objects[obj.name] = mats

            if len(obj.material_slots) == 0:
                obj.data.materials.append(None)
                obj.material_slots[-1].link = "OBJECT"

        if not materials_by_objects:
            self.log.info(f"No materials from object found, continue...")
            return
        instance.data["transientData"]["materials_by_objects"] = materials_by_objects
