import os
from copy import copy
import re
import bpy

from quadpype.pipeline import (
    publish,
    get_current_context,
    get_loaded_naming_finder_template,
    get_task_hierarchy_templates,
    get_resolved_name,
    is_current_asset_shot,
    extract_sequence_and_shot
)
from quadpype.hosts.blender.api import (
    plugin,
    pipeline,
    lib,
    ops
)

DEFAULT_VARIANT_NAME = "Main"


class ExtractShaders(
    plugin.BlenderExtractor
):
    """Extract a blend file."""

    label = "Extract Shaders"
    hosts = ["blender"]
    families = ["look"]

    # From settings
    compress = False

    def process(self, instance):
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
        for data in instance:
            data_blocks.add(data)

            if not (
                isinstance(data, bpy.types.Material)
            ):
                continue

            tree = data.node_tree
            if tree.type != 'SHADER':
                continue
            for node in tree.nodes:
                if node.bl_idname != 'ShaderNodeTexImage':
                    continue
                # Check if image is not packed already
                # and pack it if not.
                if node.image and node.image.packed_file is None:
                    node.image.pack()

        bpy.data.libraries.write(filepath, data_blocks, compress=self.compress)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'shader',
            'ext': 'blend',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        self.log.info("Extracted instance '%s' to: %s",
                       instance.name, representation)
