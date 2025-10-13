from typing import Dict, List, Optional
from pathlib import Path
import bpy
import os

from quadpype.pipeline import (
    AVALON_CONTAINER_ID,
    get_representation_path,
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
from quadpype.hosts.blender.api.pipeline import AVALON_CONTAINERS
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

    @staticmethod
    def rename_materials(imported_materials, template_data, full_name_template, group_name):
        for material in imported_materials:
            material.name = get_resolved_name(
                template_data,
                full_name_template,
                name=material.name,
                container=group_name
            )

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
        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        assert avalon_container, "Can not find avalon container in scene."

        libpath = self.filepath_from_context(context)
        assert os.path.exists(libpath), f"File at path '{libpath}' does not exists."

        selected_objects = get_selected_objects()
        assert selected_objects, "You need to select at least one object or collection to apply shaders on it."

        project_name = context.get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        asset = context["asset"]["name"]
        subset = context["subset"]["name"]
        representation = context['representation']

        template_data = format_data(representation, True, get_current_host_name())
        asset_name_template = get_load_naming_template("assetname")
        namespace_template = get_load_naming_template("namespace")
        group_name_template = get_load_naming_template("container")

        namespace = namespace or get_resolved_name(template_data, namespace_template)
        group_name = get_resolved_name(template_data, group_name_template, namespace=namespace)
        asset_name = get_resolved_name(template_data, asset_name_template)
        unique_number = plugin.get_unique_number(asset, subset, template_data)
        template_data.update({"unique_number":unique_number})

        container, imported_materials = self.import_materials(libpath)
        container.name = group_name
        self.rename_materials(
            imported_materials=imported_materials,
            template_data=template_data,
            full_name_template=get_load_naming_template("fullname"),
            group_name=group_name
        )
        self.assign_materials(
            materials=imported_materials,
            filter_objects=selected_objects,
        )

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
            "selected_objects_names": [selected_object.name for selected_object in selected_objects],
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', ''),
        }
        lib.imprint(container, data)

        if isinstance(container, bpy.types.Object):
            avalon_container.objects.link(container)
        elif isinstance(container, bpy.types.Collection) and container not in list(avalon_container.children):
            avalon_container.children.link(container)

    def exec_update(self, container: Dict, representation: Dict):
        """
        Update the loaded asset.
        """
        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        assert avalon_container, "Can not find avalon container in scene."

        group_name = container["objectName"]
        selected_objects_in_scene = [
            bpy.data.objects[selected_object_name]
            for selected_object_name in container["selected_objects_names"]
            if bpy.data.objects.get(selected_object_name, None)
        ]
        #
        asset_group = self._retrieve_undefined_asset_group(group_name)
        assert asset_group, (f"The asset is not loaded: {container['objectName']}")

        libpath = Path(get_representation_path(representation)).as_posix()
        assert os.path.exists(libpath), f"File at path '{libpath}' does not exists."

        project_name = representation.get('context', {}).get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        from copy import deepcopy
        avalon_data = deepcopy(pipeline.get_avalon_node(asset_group))

        self.exec_remove(avalon_data)

        new_container, imported_materials = self.import_materials(libpath)
        self.assign_materials(
            materials=imported_materials,
            filter_objects=selected_objects_in_scene
        )

        avalon_data.update(
            {
                "representation": str(representation["_id"]),
                "members": lib.map_to_classes_and_names(imported_materials),
                "version": get_version_by_id(project_name, str(representation["parent"])).get('name', ''),
                "selected_objects": [selected_object.name for selected_object in selected_objects_in_scene],
                "libpath":  libpath
            }
        )

        lib.imprint(new_container, avalon_data, erase=True)

        if isinstance(container, bpy.types.Object):
            avalon_container.objects.link(container)
        elif isinstance(container, bpy.types.Collection) and container not in list(avalon_container.children):
            avalon_container.children.link(container)

    def exec_remove(self, container: Dict):
        """
        Remove an existing container from a Blender scene.
        """
        group_name = container["objectName"]

        asset_group = self._retrieve_undefined_asset_group(group_name)
        assert asset_group, f"Can not find asset_group with name {group_name}"

        avalon_node = pipeline.get_avalon_node(asset_group)
        members = lib.get_objects_from_mapped(avalon_node.get('members', []))
        for material in members:
            bpy.data.materials.remove(material)

        if isinstance(asset_group, bpy.types.Object):
            bpy.data.objects.remove(asset_group)
        else:
            bpy.data.collections.remove(asset_group)

    @staticmethod
    def _retrieve_undefined_asset_group(group_name):
        asset_group = bpy.data.objects.get(group_name)

        if not asset_group:
            return bpy.data.collections.get(group_name)

        return asset_group
