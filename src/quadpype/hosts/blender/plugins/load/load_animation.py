"""Load an animation in Blender."""

from typing import Dict, List, Optional

import bpy

from quadpype.pipeline import (
    AVALON_CONTAINER_ID,
    get_resolved_name,
    format_data,
    get_load_naming_template,
    get_current_host_name,
    get_representation_path
)
from quadpype.client import get_version_by_id

from quadpype.hosts.blender.api import plugin, pipeline, lib, constants
from quadpype.hosts.blender.api.pipeline import get_avalon_node


class BlendAnimationLoader(plugin.BlenderLoader):
    """Load animations from a .blend file.

    Warning:
        Loading the same asset more then once is not properly supported at the
        moment.
    """

    families = ["animation"]
    representations = ["blend"]

    label = "Append Action Animation"
    icon = "code-fork"
    color = "orange"

    def _process(self, libpath, group_name, namespace, container=None):

        avalon_container = bpy.data.collections.get(pipeline.AVALON_CONTAINERS)
        previous_libraries = [library.name for library in bpy.data.libraries]
        previous_actions = [action.name for action in bpy.data.actions]

        members = []
        with bpy.data.libraries.load(
                libpath, link=True, relative=False
        ) as (data_from, data_to):
            data_to.collections = data_from.collections
            data_to.actions = data_from.actions

        instance_container = pipeline.get_container(collections=data_to.collections)
        snapshot_data = pipeline.get_avalon_node(instance_container, get_property=constants.SNAPSHOT_PROPERTY)
        if container:
            instance_container = container
            if snapshot_data:
                lib.imprint(
                    instance_container,
                    snapshot_data,
                    erase=True,
                    set_property=constants.SNAPSHOT_PROPERTY
                )

        assert instance_container, "No asset group found"
        loaded_containers = (pipeline.get_container_content(avalon_container)
                             if avalon_container else []
                             )

        correspondance = get_avalon_node(instance_container).get("correspondance")
        namespace = get_avalon_node(instance_container).get('namespace', namespace)

        corresponding_instance = self._corresponding_asset_is_loaded(loaded_containers, namespace)
        if not corresponding_instance:
            for library in bpy.data.libraries:
                if library.name in previous_libraries:
                    continue
                bpy.data.libraries.remove(library)
            raise Exception(f"Corresponding rig not loaded, please load {namespace}")

        actions = data_to.actions
        assert actions, "No action found"

        for action in actions:
            if action.name in previous_actions:
                bpy.data.actions.remove(bpy.data.actions.get(action.name))
            new_action = action.make_local().copy()
            members.append(new_action)

        if not container:
            instance_container.make_local()
            instance_container.name = group_name
            avalon_container.children.link(instance_container)

        self.apply_action(corresponding_instance, correspondance)

        for library in bpy.data.libraries:
            if library.name in previous_libraries:
                continue
            bpy.data.libraries.remove(library)

        lib.restore_properties_on_instance(instance_container, corresponding_instance)

        return instance_container, members

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
        asset = context["asset"]["name"]
        subset = context["subset"]["name"]
        representation = context['representation']

        avalon_container = bpy.data.collections.get(pipeline.AVALON_CONTAINERS)
        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=pipeline.AVALON_CONTAINERS)
            bpy.context.scene.collection.children.link(avalon_container)

        if self._get_existing_container(subset, avalon_container):
            raise Exception("Anim already loaded, please update through the Manager")

        template_data = format_data(representation, True, get_current_host_name())
        asset_name_template = get_load_naming_template("assetname")
        namespace_template = get_load_naming_template("namespace")
        group_name_template = get_load_naming_template("container")

        asset_name = get_resolved_name(template_data, asset_name_template)
        unique_number = plugin.get_unique_number(asset, subset, template_data)
        template_data.update({"unique_number": unique_number})

        scene_namespace = namespace or get_resolved_name(template_data, namespace_template)
        group_name = get_resolved_name(template_data, group_name_template, namespace=namespace)

        container, members = self._process(libpath, group_name, namespace)

        project_name = context.get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        data = {
            "schema": "quadpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "sceneNamespace": scene_namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(representation["_id"]),
            "libpath": libpath,
            "asset_name": asset_name,
            "parent": str(representation["parent"]),
            "family": representation["context"]["family"],
            "members": lib.map_to_classes_and_names(members),
            "objectName": group_name,
            "unique_number": unique_number,
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', '')
        }

        lib.imprint(container, data)

    def exec_update(self, container: Dict, representation: Dict):
        """
        Update the loaded asset.
        """
        group_name = container["objectName"]
        asset_group = bpy.data.objects.get(group_name)
        if not asset_group:
            asset_group = bpy.data.collections.get(group_name)

        namespace = container["namespace"]
        libpath = get_representation_path(representation)

        self._remove(container)
        if asset_group.get(constants.SNAPSHOT_PROPERTY):
            del asset_group[constants.SNAPSHOT_PROPERTY]
        container, members = self._process(libpath, group_name, namespace, asset_group)

        project_name = representation.get('context', {}).get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."
        new_data = {
            "libpath": libpath,
            "representation": str(representation["_id"]),
            "parent": str(representation["parent"]),
            "members": lib.map_to_classes_and_names(members),
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', '')
        }
        lib.imprint(asset_group, new_data)

    def _remove(self, container):
        for family, family_members in container["members"].items():
            for member in family_members:
                data_coll = getattr(bpy.data, family)
                if data_coll.get(member):
                    bpy.data.batch_remove([data_coll.get(member)])

    def exec_remove(self, container: Dict):
        """
        Remove an existing container from a Blender scene.
        """
        self._remove(container)
        container_name = container["objectName"]
        asset_group = bpy.data.objects.get(container_name)
        if not asset_group:
            asset_group = bpy.data.collections.get(container_name)
            bpy.data.collections.remove(asset_group)
            return
        bpy.data.objects.remove(asset_group)

    def apply_action(self, corresponding_instance, correspondance):
        for obj in pipeline.get_container_content(corresponding_instance):
            if not obj.name in correspondance.keys():
                continue
            if not obj.animation_data:
                obj.animation_data_create()
            obj.animation_data.action = bpy.data.actions.get(
                correspondance.get(obj.name), f"{obj.name}Action"
            )

    @staticmethod
    def _get_existing_container(subset, avalon_container):
        for col in avalon_container.children:
            avalon_prop = get_avalon_node(col)
            if not avalon_prop:
                continue
            if avalon_prop.get("subset") == subset:
                return True
        return False

    @staticmethod
    def _corresponding_asset_is_loaded(loaded_containers, target_namespace):
        for loaded_container in loaded_containers:
            if get_avalon_node(loaded_container).get('namespace', '') == target_namespace:
                return loaded_container
        return None
