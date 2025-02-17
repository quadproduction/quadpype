import os

import bpy

from quadpype.pipeline import publish
from quadpype.hosts.blender.api import plugin

class ExtractBlend(
    plugin.BlenderExtractor, publish.OptionalPyblishPluginMixin
):
    """Extract a blend file."""

    label = "Extract Blend"
    hosts = ["blender"]
    families = ["model", "camera", "rig", "action", "layout", "blendScene"]
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

        hierarchies = {}
        self.retrieve_objects_hierarchy(
            collections=self.scene_collections(),
            selection=self.get_blender_objects_from(instance),
            result=hierarchies
        )
        for data in instance:
            object_hierarchy = hierarchies.get(data.name, None)
            if object_hierarchy:
                data['original_hierarchy'] = object_hierarchy

            data_blocks.add(data)
            # Pack used images in the blend files.
            if not (
                isinstance(data, bpy.types.Object) and data.type == 'MESH'
            ):
                continue
            for material_slot in data.material_slots:
                mat = material_slot.material
                if not (mat and mat.use_nodes):
                    continue
                tree = mat.node_tree
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
            'name': 'blend',
            'ext': 'blend',
            'files': filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)

        self.log.info("Extracted instance '%s' to: %s",
                       instance.name, representation)


    @staticmethod
    def scene_collections():
        return [coll for coll in bpy.context.scene.collection.children if coll.objects and not 'AVALON' in coll.name]


    @staticmethod
    def get_blender_objects_from(instance):
        return [
            data for data in instance if
            isinstance(data, bpy.types.Object) or
            (hasattr(data, "type") and data.type == "CAMERA")
        ]

    def retrieve_objects_hierarchy(self, collections, selection, result, hierarchy=None):

        def _format_hierarchy_label(collection, hierarchy):
            return f'{hierarchy}/{collection.name}' if hierarchy else f'{collection.name}'

        for collection in collections:
            if collection.children:
                self.retrieve_objects_hierarchy(
                    collections=collection.children,
                    selection=selection,
                    result=result,
                    hierarchy=_format_hierarchy_label(collection, hierarchy),
                )
            for obj in collection.objects:
                if obj not in selection:
                    continue

                result[obj.name] = _format_hierarchy_label(collection, hierarchy)
