import os

import bpy

from quadpype.pipeline import publish
from quadpype.hosts.blender.api import plugin, pipeline, lib

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

        asset_group = instance.data["transientData"]["instance_node"]

        data_blocks = set()
        instance_objects = lib.get_objects_in_collection(asset_group)
        correspondance_dict = {}

        animated_objects = [
            obj for obj in instance_objects if
            obj and
            obj.animation_data and
            obj.animation_data.action
        ]

        for obj in animated_objects:
            data_blocks.add(obj.animation_data.action)
            if not obj.animation_data:
                obj.animation_data_create()
            correspondance_dict[obj.name] = obj.animation_data.action.name

        avalon_data = pipeline.get_avalon_node(asset_group)
        avalon_data["correspondance"] = correspondance_dict
        lib.imprint(asset_group, avalon_data)

        data_blocks.add(asset_group)
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
