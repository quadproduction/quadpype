from typing import Dict, List, Optional
import bpy
import os

from quadpype.pipeline import (
    get_representation_path,
    AVALON_CONTAINER_ID,
    registered_host,
    get_current_context,
    split_hierarchy,
    get_task_hierarchy_templates,
    get_resolved_name,
    format_data,
    get_load_naming_template,
    get_current_host_name
)
from quadpype.client import get_version_by_id

from quadpype.hosts.blender.api import plugin, lib, pipeline
from quadpype.hosts.blender.api import (
    get_objects_in_collection,
    get_parents_for_collection,
    get_top_collection,
    get_corresponding_hierarchies_numbered,
    create_collections_from_hierarchy,
    create_collection,
    get_id,
    get_objects_by_ids,
    get_targets_ids,
    get_selected_objects,
    is_collection
)


class ShadersLoader(plugin.BlenderLoader):
    """Load shaders from a .blend file."""

    families = ["look"]
    representations = ["shader"]

    label = "Append shaders to selected"
    icon = "paint-brush"
    color = "orange"

    @staticmethod
    def import_materials(filepath):
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.materials = data_from.materials
            data_to.collections = data_from.collections

        container = pipeline.get_container(data_to.objects, data_to.collections)
        return container, list(data_to.materials)

    def assign_materials(self, materials, filter_objects=None, override=True):
        cleared_objects = list()
        for material in materials:
            targets_ids = get_targets_ids(material)
            if not targets_ids:
                continue

            concerned_objects = get_objects_by_ids(targets_ids)
            if filter_objects:
                concerned_objects = list(set(concerned_objects) & set(filter_objects))

            if not concerned_objects:
                continue

            for obj in concerned_objects:

                if override and obj not in cleared_objects:
                    obj.data.materials.clear()
                    cleared_objects.append(obj)
                    self.log.info(f"Materials cleared from object named '{obj.name}'.")

                obj.data.materials.append(material)
                self.log.info(f"Material named '{material.name}' added to object named '{obj.name}'.")

    def process_asset(
            self, context: dict, name: str, namespace: Optional[str] = None,
            options: Optional[Dict] = None
    ) -> Optional[List]:
        """
        Arguments:
            name: Use pre-defined name
            namespace: Use pre-defined namespace
            context: Full parenthood of representation to load
            options: Additional settings dictionary
        """
        libpath = self.filepath_from_context(context)
        assert os.path.exists(libpath), f"File at path '{libpath}' does not exists."

        selected_objects = get_selected_objects()
        assert selected_objects, "You need to select at least one object or collection to apply shaders on it."

        project_name = context.get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        asset = context["asset"]["name"]
        representation = context['representation']

        container, imported_materials = self.import_materials(libpath)
        self.assign_materials(
            materials=imported_materials,
            filter_objects=selected_objects
        )

        template_data = format_data(representation, True, get_current_host_name())
        asset_name_template = get_load_naming_template("assetname")
        namespace_template = get_load_naming_template("namespace")
        group_name_template = get_load_naming_template("container")
        asset_name = get_resolved_name(template_data, asset_name_template)
        namespace = namespace or get_resolved_name(template_data, namespace_template)
        group_name = get_resolved_name(template_data, group_name_template, namespace=namespace)

        data = {
            "schema": "quadpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": asset_name,
            "namespace": namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(representation["_id"]),
            "libpath": libpath,
            "asset_name": asset,
            "parent": str(representation["parent"]),
            "family": representation["context"]["family"],
            "objectName": group_name,
            "members": lib.map_to_classes_and_names(imported_materials),
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', ''),
            "test": "pourvoir"
        }

        lib.imprint(container, data)

    def exec_update(self, container: Dict, representation: Dict):
        """
        Update the loaded asset.
        """
        pass

    def exec_remove(self, container: Dict):
        """
        Remove an existing container from a Blender scene.
        """
        pass
