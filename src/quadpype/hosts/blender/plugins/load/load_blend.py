from typing import Dict, List, Optional
from pathlib import Path

import bpy
from copy import deepcopy

from quadpype.pipeline import (
    get_representation_path,
    AVALON_CONTAINER_ID,
    registered_host
)
from quadpype.pipeline.create import CreateContext
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.lib import imprint
from quadpype.hosts.blender.api import (
    update_parent_data_with_entity_prefix,
    get_entity_collection_template,
    get_resolved_name
)
from quadpype.hosts.blender.api.pipeline import (
    AVALON_CONTAINERS,
    AVALON_PROPERTY,
)


class BlendLoader(plugin.BlenderLoader):
    """Load assets from a .blend file."""

    families = ["model", "rig", "layout", "camera"]
    representations = ["blend"]

    label = "Append Blend"
    icon = "code-fork"
    color = "orange"

    @staticmethod
    def _get_asset_container(objects, collections):
        for coll in collections:
            parents = [c for c in collections if c.user_of_id(coll)]
            if coll.get(AVALON_PROPERTY) and not parents:
                return coll

        for empty in [obj for obj in objects if obj.type == 'EMPTY']:
            if empty.get(AVALON_PROPERTY) and empty.parent is None:
                return empty

        return None

    @staticmethod
    def get_all_container_parents(asset_group):
        parent_containers = []
        parent = asset_group.parent
        while parent:
            if parent.get(AVALON_PROPERTY):
                parent_containers.append(parent)
            parent = parent.parent

        return parent_containers

    def _post_process_layout(self, container, asset, representation):
        rigs = [
            obj for obj in container.children_recursive
            if (
                obj.type == 'EMPTY' and
                obj.get(AVALON_PROPERTY) and
                obj.get(AVALON_PROPERTY).get('family') == 'rig'
            )
        ]
        if not rigs:
            return

        # Create animation instances for each rig
        creator_identifier = "io.quadpype.creators.blender.animation"
        host = registered_host()
        create_context = CreateContext(host)

        for rig in rigs:
            create_context.create(
                creator_identifier=creator_identifier,
                variant=rig.name.split(':')[-1],
                pre_create_data={
                    "use_selection": False,
                    "asset_group": rig
                }
            )

    def _process_data(self, libpath, group_name):
        # Append all the data from the .blend file
        with bpy.data.libraries.load(
            libpath, link=False, relative=False
        ) as (data_from, data_to):
            for attr in dir(data_to):
                setattr(data_to, attr, getattr(data_from, attr))

        members = []

        # Rename the object to add the asset name
        for attr in dir(data_to):
            for data in getattr(data_to, attr):
                data.name = f"{group_name}:{data.name}"
                members.append(data)

        container = self._get_asset_container(data_to.objects, data_to.collections)

        assert container, "No asset group found"

        container.name = group_name

        if isinstance(container, type(bpy.data.objects)):
            container.empty_display_type = 'SINGLE_ARROW'
            # Link the container to the scene
            bpy.context.scene.collection.objects.link(container)

        # Link all the container children to the collection
        for obj in container.children_recursive:
            bpy.context.scene.collection.objects.link(obj)

        # Remove the library from the blend file
        filepath = bpy.path.basename(libpath)
        # Blender has a limit of 63 characters for any data name.
        # If the filepath is longer, it will be truncated.
        if len(filepath) > 63:
            filepath = filepath[:63]
        library = bpy.data.libraries.get(filepath)
        bpy.data.libraries.remove(library)

        return container, members

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

        parent = self.get_parent(context)
        if not parent:
            self.log.warning(f"Can not retrieve parent from asset {asset} / subset {subset}")

        context["representation"]["context"]["parent"] = parent
        context["representation"]["context"]["app"] = "blender"

        try:
            family = context["representation"]["context"]["family"]
        except ValueError:
            family = "model"

        representation = str(context["representation"]["_id"])

        asset_name = plugin.prepare_scene_name(asset, subset)
        unique_number = plugin.get_unique_number(asset, subset)
        group_name = plugin.prepare_scene_name(asset, subset, unique_number)
        namespace = namespace or f"{asset}_{unique_number}"

        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=AVALON_CONTAINERS)
            bpy.context.scene.collection.children.link(avalon_container)

        #Retrieve the data for template resolving.
        #First, check the entity type prefix.
        data_for_template = deepcopy(context["representation"]["context"])
        update_parent_data_with_entity_prefix(data_for_template)

        asset_type_collection = None
        #If a difference, then it means a settings was found.
        #Get the corresponding collection then
        if parent and data_for_template["parent"] != parent:
            asset_type_collection = self.get_asset_type_collection(data_for_template)

        asset_collection = None
        asset_collection_template = get_entity_collection_template(context["representation"]["context"])
        # If a difference, then it means a settings was found.
        # Get the corresponding collection then
        if asset_collection_template:
            asset_collection = self.get_asset_numbered_collection(data_for_template,
                                                                  asset_collection_template,
                                                                  unique_number)
        container, members = self._process_data(libpath, group_name)

        #If there's both an asset_type and asset_collection, then link them
        if asset_type_collection and asset_collection:
            asset_type_collection.children.link(asset_collection)

        #if only asset collection is found, then link it to scene
        elif not asset_type_collection and asset_collection:
            bpy.context.scene.collection.children.link(asset_collection)

        # if asset_collection:
        #     [asset_collection.objects.link(member) for member in members if isinstance(member, bpy.types.Object)]

        for blender_object in members:
            collections = list(filter(None, blender_object.get('original_hierarchy', '').split('/')))
            collections = [f'{collection_name}-{unique_number}' for collection_name in collections]
            for collection_level, collection_name in enumerate(collections):
                collection = bpy.data.collections.get(collection_name, None)
                if collection:
                    continue

                collection = bpy.data.collections.new(collection_name)

                if collection_level == 0:
                    asset_collection.children.link(collection)
                else:
                    bpy.data.collections[collections[collection_level - 1]].children.link(collection)

            if collections:
                bpy.data.collections[collections[-1]].objects.link(blender_object)

        if family == "layout":
            self._post_process_layout(container, asset, representation)

        if isinstance(container, bpy.types.Object):
            avalon_container.objects.link(container)
        elif isinstance(container, bpy.types.Collection):
            avalon_container.children.link(container)

        data = {
            "schema": "quadpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "namespace": namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(context["representation"]["_id"]),
            "libpath": libpath,
            "asset_name": asset_name,
            "parent": str(context["representation"]["parent"]),
            "family": context["representation"]["context"]["family"],
            "objectName": group_name,
            "members": members,
        }

        container[AVALON_PROPERTY] = data

        objects = [
            obj for obj in bpy.data.objects
            if obj.name.startswith(f"{group_name}:")
        ]

        self[:] = objects
        return objects

    @staticmethod
    def get_parent(context):
        parent = context["representation"]["context"].get('parent', None)
        if not parent:
            hierarchy = context["representation"]["context"].get('hierarchy')

            if not hierarchy:
                return

            return hierarchy.split('/')[-1]

        return parent

    @staticmethod
    def get_asset_type_collection(context_data):
        """Search for the asset_type collection based on template and setting
        If None is found, create one"""

        asset_type_name = context_data["parent"]
        asset_type_collection = bpy.data.collections.get(asset_type_name)
        if not asset_type_collection:
            asset_type_collection = bpy.data.collections.new(name=asset_type_name)
            bpy.context.scene.collection.children.link(asset_type_collection)

        return asset_type_collection

    @staticmethod
    def get_asset_numbered_collection(context_data, template, unique_number):
        """Search for the asset collection based on template and setting
        If None is found, create one"""

        asset_collection_name = get_resolved_name(context_data, template)
        asset_collection_name = f"{asset_collection_name}-{unique_number}"
        asset_collection = bpy.data.collections.get(asset_collection_name)
        if not asset_collection:
            asset_collection = bpy.data.collections.new(name=asset_collection_name)

        return asset_collection

    def exec_update(self, container: Dict, representation: Dict):
        """
        Update the loaded asset.
        """
        group_name = container["objectName"]
        asset_group = bpy.data.objects.get(group_name)
        libpath = Path(get_representation_path(representation)).as_posix()

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}"
        )

        transform = asset_group.matrix_basis.copy()
        old_data = dict(asset_group.get(AVALON_PROPERTY))
        old_members = old_data.get("members", [])
        parent = asset_group.parent

        actions = {}
        objects_with_anim = [
            obj for obj in asset_group.children_recursive
            if obj.animation_data]
        for obj in objects_with_anim:
            # Check if the object has an action and, if so, add it to a dict
            # so we can restore it later. Save and restore the action only
            # if it wasn't originally loaded from the current asset.
            if obj.animation_data.action not in old_members:
                actions[obj.name] = obj.animation_data.action

        self.exec_remove(container)

        asset_group, members = self._process_data(libpath, group_name)

        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        avalon_container.objects.link(asset_group)

        asset_group.matrix_basis = transform
        asset_group.parent = parent

        # Restore the actions
        for obj in asset_group.children_recursive:
            if obj.name in actions:
                if not obj.animation_data:
                    obj.animation_data_create()
                obj.animation_data.action = actions[obj.name]

        # Restore the old data, but reset members, as they don't exist anymore
        # This avoids a crash, because the memory addresses of those members
        # are not valid anymore
        old_data["members"] = []
        asset_group[AVALON_PROPERTY] = old_data

        new_data = {
            "libpath": libpath,
            "representation": representation["_id"],
            "parent": representation["parent"],
            "members": members,
        }

        imprint(asset_group, new_data)

        # We need to update all the parent container members
        parent_containers = self.get_all_container_parents(asset_group)

        for parent_container in parent_containers:
            parent_members = parent_container[AVALON_PROPERTY]["members"]
            parent_container[AVALON_PROPERTY]["members"] = (
                parent_members + members)

    def exec_remove(self, container: Dict) -> bool:
        """
        Remove an existing container from a Blender scene.
        """
        group_name = container["objectName"]
        asset_group = bpy.data.objects.get(group_name)

        attrs = [
            attr for attr in dir(bpy.data)
            if isinstance(
                getattr(bpy.data, attr),
                bpy.types.bpy_prop_collection
            )
        ]

        members = asset_group.get(AVALON_PROPERTY).get("members", [])

        # We need to update all the parent container members
        parent_containers = self.get_all_container_parents(asset_group)

        for parent in parent_containers:
            parent.get(AVALON_PROPERTY)["members"] = list(filter(
                lambda i: i not in members,
                parent.get(AVALON_PROPERTY).get("members", [])))

        for attr in attrs:
            for data in getattr(bpy.data, attr):
                if data in members:
                    # Skip the asset group
                    if data == asset_group:
                        continue
                    getattr(bpy.data, attr).remove(data)

        bpy.data.objects.remove(asset_group)
