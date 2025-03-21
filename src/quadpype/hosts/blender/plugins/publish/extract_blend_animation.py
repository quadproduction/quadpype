import os

import bpy

from quadpype.pipeline import publish
from quadpype.hosts.blender.api import plugin

class ExtractBlendAnimation(
    plugin.BlenderExtractor,
    publish.OptionalPyblishPluginMixin,
):
    """Extract a blend file."""

    label = "Extract Blend"
    hosts = ["blender"]
    families = ["animation"]
    optional = True

    # From settings
    compress = False

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        # Define extract output file path

        stagingdir = self.staging_dir(instance)
        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        instance_name = f"{asset_name}_{subset}"
        filename = f"{instance_name}.blend"
        filepath = os.path.join(stagingdir, filename)

        # Perform extraction
        self.log.info("Performing extraction..")

        data_blocks = set()

        for obj in self.get_empties(instance):
            for armature in self.get_armatures_with_animation(obj.children):
                if not obj.animation_data:
                    obj.animation_data_create()
                obj.animation_data.action = armature.animation_data.action
                obj.animation_data_clear()
                data_blocks.add(armature.animation_data.action)
                data_blocks.add(obj)
        bpy.data.libraries.write(filepath, data_blocks, compress=self.compress)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'blend',
            'ext': 'blend',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        self.log.info("Extracted instance '%s' to: %s",
                       instance.name, representation)

    @staticmethod
    def get_empties(instance):
        return [obj for obj in instance if isinstance(obj, bpy.types.Object) and obj.type == 'EMPTY']

    @staticmethod
    def get_armatures_with_animation(children):
        return [
            child for child in children if
            child and
            child.type == 'ARMATURE' and
            child.animation_data and
            child.animation_data.action
        ]
