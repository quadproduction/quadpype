import os
import logging
import re

from quadpype.hosts.blender.api.pipeline import get_path_from_template
from quadpype.pipeline.anatomy import Anatomy

import bpy


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


bl_info = {
    "name": "Update paths to last version",
    "description": "Update all concerned paths in scene to automatically target the last version existing",
    "author": "Quad",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "category": "Render",
    "location": "View 3D > UI",
}

ALEMBIC_EXTENSION = '.abc'


class VIEW3D_PT_UPDATE_PATHS(bpy.types.Panel):
    bl_label = "Select object types to update"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Quad"

    update_alembics = bpy.props.BoolProperty(default=True)
    update_shader_files = bpy.props.BoolProperty(default=True)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("paths.update_animation_paths", text="Update alembics to animation", icon="MESH_CUBE").mode = "animation"
        col.operator("paths.update_animation_paths", text="Update alembics versions", icon="MESH_CUBE").mode = "update_cache_versions"


class OBJECT_OT_UPDATE_PATHS(bpy.types.Operator):
    bl_idname = "paths.update_animation_paths"
    bl_label = "Update Animation Paths and Cache Versions in Scene Objects"

    mode: bpy.props.StringProperty()

    def execute(self, context):
        mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']

        if not mesh_objects:
            log.error("Scene does not contain Mesh objects.")
            return {'CANCELLED'}

        # Filter modifiers and get cache files directly
        mesh_sequence_caches = self.get_mesh_sequence_cache_modifiers(mesh_objects)
        modifiers_cache_files = [modifier.cache_file for modifier in mesh_sequence_caches]

        # Create library overrides in one go
        self.create_library_override_for(collections=bpy.context.scene.collection,
                                         objects=mesh_objects,
                                         modifiers_cache_files=modifiers_cache_files)

        if self.mode == 'update_cache_versions':
            self.update_versions(bpy.data.cache_files)
        else:
            # Update the sequence caches before creating overrides
            self.update_mesh_sequence_caches(mesh_objects)

            # Set Scale
            for mesh_object in mesh_objects:
                # Scale set to 0.01 to adjust different unit systems between Maya and Blender.
                # TODO : Need a scale converter
                mesh_object.scale = (0.01, 0.01, 0.01)

        # Disable UV Data Reading
        for mesh_sequence_cache in mesh_sequence_caches:
            mesh_sequence_cache.read_data = {'COLOR', 'POLY', 'VERT'}
        return {'FINISHED'}

    def update_versions(self, cache_files):
        for cache_file in cache_files:
            absolute_file_path = bpy.path.abspath(cache_file.filepath)

            if not "animation" in absolute_file_path:
                logging.warning(f'Cache file {cache_file.name} does not point to an animation file. Skipping...')
                continue

            # Detect version and directory from file_path
            version_padding = Anatomy().templates.get('version_padding', 3)
            version_pattern = re.search(rf"(.*[/\\])v(\d{{{version_padding}}})[/\\]", absolute_file_path)
            if not version_pattern:
                logging.warning(f"Unable to detect version pattern {cache_file.name}")
                continue

            versions_directory = version_pattern.group(1)
            current_version = version_pattern.group(2)

            last_version_available = self.detect_higher_version(versions_directory)
            if int(current_version) == int(last_version_available):
                log.info(f"No newer version found for alembic {cache_file.name} (current is {current_version})")
                return

            cache_file.filepath = absolute_file_path.replace(f"v{current_version}", f"v{last_version_available}")
            cache_file.name = os.path.basename(cache_file.filepath)
            log.info(f"Cache {cache_file.name} has been updated : {current_version} to {last_version_available}")

    def detect_higher_version(self, directory):
        version = None
        for folder in os.listdir(directory):
            version_folder_pattern = re.search(r"v(\d{3})", folder)
            if version_folder_pattern:
                version = version_folder_pattern.group(1)
        return version

    def update_mesh_sequence_caches(self, mesh_objects):
        updated_cache_files = []
        for modifier in self.get_mesh_sequence_cache_modifiers(mesh_objects):
            cache_file = modifier.cache_file

            # Only update if the cache file hasn't been updated
            if cache_file not in updated_cache_files:
                alembic_path = self.get_alembic_publish_path(modifier.object_path)

                # Only update if the filepath has changed
                if alembic_path != cache_file.filepath:
                    previous_name = cache_file.name
                    cache_file.filepath = alembic_path
                    cache_file.name = alembic_path.split(f'{os.path.sep}')[-1]  # Assuming Windows path separator
                    log.info(f"Alembic file '{previous_name}' updated to '{cache_file.filepath}'.")

                updated_cache_files.append(cache_file)

            # Update modifier's object path
            parts = modifier.object_path.split("/")
            parts[-1] = f"{modifier.id_data.name}ShapeDeformed"
            modifier.object_path = f'{os.path.sep}'.join(parts)

    def get_mesh_sequence_cache_modifiers(self, objects):
        """Return all MESH_SEQUENCE_CACHE modifiers from a list of objects."""
        return [mod for obj in objects for mod in obj.modifiers if mod.type == 'MESH_SEQUENCE_CACHE']

    def create_library_override_for(self, collections=None, objects=None, modifiers_cache_files=None):
        set()  # Use a set to avoid duplicate
        collections = collections if collections else bpy.context.scene.collection
        objects = objects if objects else bpy.data.objects

        self.override_collection_and_children(collections)

        # Create library overrides for objects and cache files in a single pass
        local_object_names = {obj.name for obj in objects if not obj.library}
        local_cache_names = {cache.name for cache in modifiers_cache_files if not cache.library}

        for obj in objects:
            if obj.library and obj.name not in local_object_names:
                obj.override_create(remap_local_usages=True)

        for cache_file in modifiers_cache_files:
            if cache_file.library and cache_file.name not in local_cache_names:
                cache_file.make_local()

    def get_alembic_publish_path(self, modifier_object_path):
        # Get the asset name from the modifier_object_path
        asset_name = modifier_object_path.split("/")[1].split('_')[0]  # "/" is the blender delimiter

        # Construct the animation directory path
        template_data= {
            'family': 'animation',
            'subset': f'{asset_name}_animation',
        }

        animation_directory = os.path.dirname(get_path_from_template('publish', 'folder', template_data))
        if not os.path.exists(animation_directory):
            return

        # Retrieve the highest version folder from the animation directory
        last_version = self.detect_higher_version(animation_directory)

        # If no version folder is found, return None
        if not last_version:
            return

        # Retrieve the alembic file matching the version
        version_directory = os.path.join(animation_directory, f'v{last_version}')

        alembic_file = None
        for abc_file in os.listdir(version_directory):
            if abc_file.endswith(f'{ALEMBIC_EXTENSION}'):
                alembic_file = abc_file

        if not alembic_file:
            return

        # Return the full path to the alembic file if found, otherwise None
        return os.path.join(animation_directory, last_version, alembic_file)

    def override_collection_and_children(self, collection):
        if collection.library:
            collection.override_create(remap_local_usages=True)

        for child in collection.children:
            self.override_collection_and_children(child)

def register():
        bpy.utils.register_class(VIEW3D_PT_UPDATE_PATHS)
        bpy.utils.register_class(OBJECT_OT_UPDATE_PATHS)

def unregister():
        bpy.utils.unregister_class(VIEW3D_PT_UPDATE_PATHS)
        bpy.utils.unregister_class(OBJECT_OT_UPDATE_PATHS)
