from typing import Dict, List, Optional
from pathlib import Path

import bpy
from copy import deepcopy

from quadpype.pipeline import (
    get_representation_path,
    AVALON_CONTAINER_ID,
    registered_host,
    get_current_context
)
# from quadpype.pipeline.context_tools import , get_project_settings
from quadpype.pipeline.create import CreateContext
from quadpype.hosts.blender.api import plugin
from quadpype.hosts.blender.api.lib import imprint
from quadpype.hosts.blender.api import (
    update_parent_data_with_entity_prefix,
    get_task_collection_templates,
    get_resolved_name,
    get_parents_for_collection
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
            if coll.get(AVALON_PROPERTY):
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

        parent = self.get_parent_data(context)
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

        data_for_template = deepcopy(context["representation"]["context"])
        update_parent_data_with_entity_prefix(data_for_template)

        asset_collection_templates = get_task_collection_templates(
            context["representation"]["context"],
            task=get_current_context()['task_name']
        )

        container, members = self._process_data(libpath, group_name)

        collections_are_created = None
        corresponding_hierarchies_numbered = {}

        if self.is_shot():
            data_for_template['sequence'], data_for_template['shot'] = get_current_context()['asset_name'].split('_')

        if asset_collection_templates:
            corresponding_hierarchies_numbered = {
                get_resolved_name(
                    data=data_for_template,
                    template=hierarchies
                ).replace('\\', '/').split('/')[-1]: get_resolved_name(
                    data=data_for_template,
                    template=hierarchies,
                    numbering=unique_number
                ).replace('\\', '/').split('/')[-1]
                for hierarchies in asset_collection_templates
            }

            collections_are_created = self.create_collections_from_template(
                data=data_for_template,
                templates=asset_collection_templates,
                unique_number=unique_number,
                parent_collection=bpy.context.scene.collection
            )

        if collections_are_created:
            default_parent_collection_name = self._extract_last_collection_from_first_template(
                data=data_for_template,
                templates=asset_collection_templates,
                unique_number=unique_number
            )

            for blender_object in members:
                if not isinstance(blender_object, bpy.types.Object):
                    continue

                object_hierarchies = blender_object.get('original_collection_parent')

                if not object_hierarchies:
                    bpy.data.collections[default_parent_collection_name].objects.link(blender_object)
                    continue

                split_object_hierarchies = object_hierarchies.replace('\\', '/').split('/')

                for collection_number, hierarchy in enumerate(split_object_hierarchies):
                    hierarchy = get_resolved_name(
                        data=data_for_template,
                        template=hierarchy,
                        numbering=unique_number
                    )
                    corresponding_collection_name = corresponding_hierarchies_numbered.get(
                        hierarchy,
                        f"{hierarchy}-{unique_number}"
                    )

                    if collection_number == 0:
                        collection = self.get_top_collection(
                            collection_name=corresponding_collection_name,
                            default_parent_collection_name=default_parent_collection_name
                        )

                    else:
                        collection = self.create_collection_from_hierarchy(
                            parent_collection_name=split_object_hierarchies[collection_number - 1],
                            collection_name=corresponding_collection_name,
                            corresponding_hierarchies_numbered=corresponding_hierarchies_numbered
                        )

                    collection.objects.link(blender_object)

        else:
            # TODO: move this because it needs to happen when template is found and to raise error if none found
            [bpy.context.scene.collection.objects.link(member) for member in members if isinstance(member, bpy.types.Object)]

        if isinstance(container, bpy.types.Object):
            avalon_container.objects.link(container)
        elif isinstance(container, bpy.types.Collection):
            avalon_container.children.link(container)

        if family == "layout":
            self._post_process_layout(container, asset, representation)

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
    def _extract_last_collection_from_first_template(data, templates, unique_number):
        return get_resolved_name(
            data=data,
            template=templates[0],
            numbering=unique_number
        ).replace('\\', '/').split('/')[-1]

    @staticmethod
    def _create_collection(collection_name, link_to=None):
        collection = bpy.data.collections.get(collection_name)

        if not collection:
            collection = bpy.data.collections.new(collection_name)
            if link_to and collection not in list(link_to.children):
                link_to.children.link(collection)

        return collection

    @staticmethod
    def is_shot():
        return len(get_current_context()['asset_name'].split('_')) > 1

    @staticmethod
    def get_parent_data(context):
        parent = context["representation"]["context"].get('parent', None)
        if not parent:
            hierarchy = context["representation"]["context"].get('hierarchy')

            if not hierarchy:
                return

            return hierarchy.split('/')[-1]

        return parent

    @staticmethod
    def get_top_collection(collection_name, default_parent_collection_name):
        parent_collection = bpy.data.collections.get(collection_name, None)
        if not parent_collection:
            parent_collection = bpy.data.collections[default_parent_collection_name]

        return parent_collection if parent_collection else bpy.context.scene.collection

    def create_collection_from_hierarchy(
        self,
        parent_collection_name,
        collection_name,
        corresponding_hierarchies_numbered
    ):
        corresponding_parent_collection_name = bpy.data.collections.get(
            corresponding_hierarchies_numbered.get(parent_collection_name, parent_collection_name)
        )
        collection = self._create_collection(
            collection_name=collection_name,
            link_to=corresponding_parent_collection_name
        )

        return collection

    def create_collections_from_template(self, data, templates, parent_collection, unique_number):
        all_hierarchies = [
            get_resolved_name(
                data=data,
                template=hierarchies,
                numbering=unique_number
            ).replace('\\', '/').split('/')
            for hierarchies in templates
        ]

        top_hierarchies = set(
            collection[0] for collection in all_hierarchies
        )

        try:
            top_collection_name = next(iter(top_hierarchies))

        except StopIteration:
            self.log.warning(
                "Can not extract top collection from retrieved templates. "
                "No collection will be used for later process."
            )
            return None

        if len(top_hierarchies) > 1:
            self.log.warning(
                f"Multiple top collections have been found. "
                f"Only the first one ({top_collection_name}) will be used."
            )

        for single_template in all_hierarchies:
            for level, collection_name in enumerate(single_template):
                if level == 0:
                    parent = parent_collection
                else:
                    parent = bpy.data.collections[single_template[level - 1]]

                self._create_collection(
                    collection_name=collection_name,
                    link_to=parent
                )

        return True

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
