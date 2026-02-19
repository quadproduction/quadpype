import bpy

import pyblish.api
from quadpype.hosts.blender.api import plugin


class ReassignMaterials(
    plugin.BlenderExtractor
):
    label = "Reassign Removed Materials"
    hosts = ["blender"]
    families = ["model", "rig", "layout", "blendScene", "animation", "pointcache"]
    order = pyblish.api.ExtractorOrder + 0.0011
    active = True

    def process(self, instance):

        materials_by_objects = instance.data["transientData"].get("materials_by_objects")
        if not materials_by_objects:
            self.log.info(f"No materials_by_objects found, continue...")
            return

        for obj_name, materials in materials_by_objects.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                continue
            if obj.type != 'MESH':
                continue

            for i, mat in enumerate(reversed(materials)):
                if not mat:
                    continue
                if mat in obj.data.materials[:]:
                    continue

                obj.material_slots[i].material = mat
                self.log.info(f"{mat.name} has been affected to {obj.name}.")
        return
