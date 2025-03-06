import os
from copy import copy

import bpy

from quadpype.pipeline import publish, get_current_context
from quadpype.hosts.blender.api import (
    plugin,
    get_task_collection_templates,
    get_resolved_name
)
from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS,
    AVALON_INSTANCES,
    AVALON_PROPERTY,
)


DEFAULT_VARIANT_NAME = "Main"


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

        parent = instance.data.get('parent')
        if not parent:
            parent = instance.data.get('anatomyData', []).get('parent', None)

        # We remove variant data if equal to Main to avoid the info in the final name
        variant = instance.data.get('variant')
        if variant == 'Main':
            variant = None

        # Perform extraction
        self.log.info("Performing extraction..")

        data_blocks = set()

        templates = get_task_collection_templates(
            data=instance.data,
        )

        if self.is_shot():
            instance.data['sequence'], instance.data['shot'] = get_current_context()['asset_name'].split('_')

        hierarchies = {}
        for template in templates:
            task_hierarchy = get_resolved_name(
                data=instance.data,
                template=template,
                parent=parent,
                variant=variant
            )

            parent_collection_name = task_hierarchy.replace('\\', '/').split('/')[-1]
            parent_collection = bpy.data.collections[parent_collection_name]
            self.retrieve_objects_hierarchy(
                collections=[parent_collection],
                selection=[data for data in instance],
                result=hierarchies
            )

        for blender_object in bpy.context.scene.objects:
            blender_object['visible'] = blender_object.visible_get()

        for blender_object, hierarchy_for_object in hierarchies.items():
            blender_object['original_collection_parent'] = hierarchy_for_object

        for data in instance:
            data_blocks.add(data)

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
    def is_shot():
        return len(get_current_context()['asset_name'].split('_')) > 1

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
                result[obj] = _format_hierarchy_label(collection, hierarchy)
