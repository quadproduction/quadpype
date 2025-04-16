import os
from copy import copy
import re
import bpy

from quadpype.pipeline import publish, get_current_context
from quadpype.hosts.blender.api import (
    plugin,
    pipeline,
    lib,
    ops,
    template_resolving
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

        asset_name = instance.data["assetEntity"]["name"]
        subset = instance.data["subset"]
        instance_name = f"{asset_name}_{subset}"
        instance_coll = bpy.data.collections.get(instance_name)
        objects_in_instance = pipeline.get_container_content(instance_coll)
        from_loaded_coll = self.get_collections_from_loaded(objects_in_instance)

        if not from_loaded_coll:
            self._process_instance(instance)
            return

        # if from a loaded subset, must rename before extract to avoid namespace accumulation in names
        corresponding_renaming = {}
        namespace_regex = template_resolving.get_loaded_naming_finder_template("namespace", instance.data)
        unique_number_regex = template_resolving.get_loaded_naming_finder_template("unique-number", instance.data)

        for loaded_coll in from_loaded_coll:
            avalon_data = pipeline.get_avalon_node(loaded_coll)
            members = lib.get_objects_from_mapped(avalon_data.get("members"))

            for member in members:
                old_full_name = member.name
                match = re.match(fr"{namespace_regex}", old_full_name)
                if match:
                    member.name = match.group(1)
                corresponding_renaming[member] = old_full_name
                if not member.get("original_collection_parent"):
                    continue

                real_object_hierarchies = lib.get_parent_collections_for_object(member)

                for hier_coll in real_object_hierarchies:
                    match = re.match(fr"{unique_number_regex}", hier_coll.name)
                    if match:
                        old_full_name = hier_coll.name
                        hier_coll.name = match.group(1)
                        corresponding_renaming[hier_coll] = old_full_name

        self._process_instance(instance)

        for obj, name in corresponding_renaming.items():
            obj.name = name

    def _process_instance(self, instance):
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

        instance_coll = bpy.data.collections.get(instance_name)
        objects_in_instance = pipeline.get_container_content(instance_coll)

        # If no data are in instances like in 'action' family, populate it
        if len(instance) == 0:
            instance.append(instance_coll)
            for obj in objects_in_instance:
                instance.append(obj)

        # Perform extraction
        self.log.info("Performing extraction..")

        data_blocks = set()

        templates = template_resolving.get_task_collection_templates(
            data=instance.data,
        )

        if lib.is_shot():
            instance.data['sequence'], instance.data['shot'] = lib.extract_sequence_and_shot()

        hierarchies = {}
        for template in templates:
            task_hierarchy = template_resolving.get_resolved_name(
                data=instance.data,
                template=template,
                parent=parent,
                variant=variant
            )

            parent_collection_name = task_hierarchy.replace('\\', '/').split('/')[-1]
            parent_collection = bpy.data.collections.get(parent_collection_name, instance_name)
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

    @staticmethod
    def get_collections_from_loaded(objects_in_instance):
        loaded_coll = set()
        for obj in objects_in_instance:
            for collection in [coll for coll in bpy.data.collections if obj.name in coll.objects]:
                if not pipeline.has_avalon_node(collection):
                    continue
                if not pipeline.get_avalon_node(collection).get("loader"):
                    continue
                loaded_coll.add(collection)

        return loaded_coll
