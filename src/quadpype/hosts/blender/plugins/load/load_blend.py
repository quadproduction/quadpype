from typing import Dict, List, Optional
from pathlib import Path

import bpy
from enum import Enum
import re
from copy import deepcopy

from quadpype.lib.attribute_definitions import BoolDef, EnumDef
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


class ImportMethod(Enum):
    APPEND = "Append"
    LINK = "Link"
    OVERRIDE = "Link + override"


class BlendLoader(plugin.BlenderLoader):
    """Load assets from a .blend file."""

    families = ["model", "rig", "layout", "camera"]
    representations = ["blend"]

    label = "Append Blend"
    icon = "code-fork"
    color = "orange"

    defaults = {
        'import_method': ImportMethod.APPEND.value
    }

    @classmethod
    def get_options(cls, contexts):
        return [
            EnumDef(
                "import_method",
                items=[
                    ImportMethod.APPEND.value,
                    ImportMethod.LINK.value,
                    ImportMethod.OVERRIDE.value
                ],
                default=cls.defaults['import_method'],
                label="Import method",
            )
        ]

    def get_all_container_parents(self, asset_group):
        parent_containers = []
        parent = self._get_parents(asset_group)
        while parent:
            if parent.get(AVALON_PROPERTY):
                parent_containers.append(parent)
            parent = self._get_parents(parent)

        return parent_containers

    @staticmethod
    def _get_parents(asset_group):
        if hasattr(asset_group, "parent"):
            return [asset_group.parent]
        else:
            for collection in bpy.data.collections:
                if asset_group in list(collection.objects):
                    return collection

        return None

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

        representation_id = str(representation["_id"])

        asset_name = plugin.prepare_scene_name(asset, subset)
        unique_number = plugin.get_unique_number(asset, subset)
        group_name = plugin.prepare_scene_name(asset, subset, unique_number)
        namespace = namespace or f"{asset}_{unique_number}"

        container, members = self.load_assets_and_create_hierarchy(
            representation=representation,
            libpath=libpath,
            group_name=group_name,
            unique_number=unique_number,
            import_method=ImportMethod(
                options.get(
                    'import_method',
                    self.defaults['import_method']
                )
            )
        )

        try:
            family = representation["context"]["family"]
        except ValueError:
            family = "model"

        if family == "layout":
            self._post_process_layout(container, asset, representation_id)

        data = {
            "schema": "quadpype:container-2.0",
            "id": AVALON_CONTAINER_ID,
            "name": name,
            "namespace": namespace or '',
            "loader": str(self.__class__.__name__),
            "representation": str(representation["_id"]),
            "libpath": libpath,
            "asset_name": asset_name,
            "parent": str(representation["parent"]),
            "family": representation["context"]["family"],
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

    def load_assets_and_create_hierarchy(self, representation, libpath, group_name, unique_number, import_method):
        parent = self.get_parent_data(representation)
        if not parent:
            self.log.warning(f"Can not retrieve parent from asset {group_name}")

        representation["context"]["parent"] = parent
        representation["context"]["app"] = "blender"

        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)
        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=AVALON_CONTAINERS)
            bpy.context.scene.collection.children.link(avalon_container)

        data_for_template = deepcopy(representation["context"])
        update_parent_data_with_entity_prefix(data_for_template)

        asset_collection_templates = get_task_collection_templates(
            representation["context"],
            task=get_current_context()['task_name']
        )

        container, members = self.import_blend_objects(libpath, group_name, import_method)
        if import_method is ImportMethod.APPEND:
            self.remove_library_from_blend_file(libpath)

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

            for blender_object in container.objects:

                # Do not link non-objects or invisible objects from published scene
                if not blender_object.get('visible', True):
                    continue

                collection = bpy.data.collections[default_parent_collection_name]

                object_hierarchies = blender_object.get('original_collection_parent', '')
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

                if blender_object in list(collection.objects):
                    continue

                collection.objects.link(blender_object)

                # If override, we need to add newly linked objects to members
                # in order to be effectively removed or updated later.
                if import_method is import_method.OVERRIDE:
                    members.append(blender_object)

        else:
            # TODO: move this because it needs to happen when template is found and to raise error if none found
            [bpy.context.scene.collection.objects.link(member) for member in members if
             isinstance(member, bpy.types.Object)]

        if isinstance(container, bpy.types.Object):
            avalon_container.objects.link(container)
        elif isinstance(container, bpy.types.Collection) and container not in list(avalon_container.children):
            avalon_container.children.link(container)

        return container, members

    def import_blend_objects(self, libpath, group_name, import_method):
        if import_method == ImportMethod.APPEND:
            container, members = self.append_blend_objects(libpath, group_name)
        elif import_method == ImportMethod.LINK:
            container, members = self.link_blend_objects(libpath)
        elif import_method == ImportMethod.OVERRIDE:
            container, members = self.link_blend_objects_with_overrides(libpath, group_name)
        else:
            raise RuntimeError("No import method specified when importing blend objects.")

        container['import_method'] = import_method.value
        return container, members

    @staticmethod
    def get_parent_data(representation):
        parent = representation["context"].get('parent', None)
        if not parent:
            hierarchy = representation["context"].get('hierarchy')

            if not hierarchy:
                return

            return hierarchy.split('/')[-1]

        return parent

    def append_blend_objects(self, libpath, group_name):
        data_to = self._load_from_blendfile(
            libpath,
            import_link=False,
            override=False
        )
        container = self._get_asset_container(data_to.objects, data_to.collections)
        assert container, "No asset group found"

        members = self._collect_members(data_to)

        # Needs to rename in separate block to retrieve blender object after initialisation
        self._rename_all(
            data_list=members,
            group_name=group_name
        )

        container.name = group_name
        return container, members

    def link_blend_objects(self, libpath):
        data_to = self._load_from_blendfile(
            libpath,
            import_link=True,
            override=False
        )
        container = self._get_asset_container(data_to.objects, data_to.collections)
        assert container, "No asset group found"

        members = self._collect_members(data_to)

        return container, members

    def link_blend_objects_with_overrides(self, libpath, group_name):
        data_to = self._load_from_blendfile(
            libpath,
            import_link=True,
            override=True
        )
        container = self._get_asset_container(data_to.objects, data_to.collections)
        for obj in container.objects:
            obj.override_create(remap_local_usages=True)

        assert container, "No asset group found"

        members = self._collect_members(data_to)

        container.name = group_name

        # Needs to rename in separate block to retrieve blender object after initialisation
        self._rename_all(
            data_list=container.objects,
            group_name=group_name,
            truncate_occurrence=True
        )

        return container, members

    @staticmethod
    def _load_from_blendfile(libpath, import_link, override):
        with bpy.data.libraries.load(
                libpath,
                link=import_link,
                create_liboverrides=override,
                relative=False
        ) as (data_from, data_to):
            for attr in dir(data_to):
                setattr(data_to, attr, getattr(data_from, attr))

        return data_to

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
    def _collect_members(data_attributes):
        members = []
        # Needs to rename in separate block to retrieve blender object after initialisation
        for attr in dir(data_attributes):
            for data in getattr(data_attributes, attr):
                members.append(data)

        return members

    @staticmethod
    def _rename_all(data_list, group_name, truncate_occurrence=False):
        for blender_object in data_list:
            object_name = blender_object.name
            if truncate_occurrence:
                object_name = re.sub('.\d{3}$', '', blender_object.name)
            blender_object.name = f"{group_name}:{object_name}"

    @staticmethod
    def remove_library_from_blend_file(libpath):
        # Blender has a limit of 63 characters for any data name.
        # If the filepath is longer, it will be truncated.
        filepath = bpy.path.basename(libpath)
        if len(filepath) > 63:
            filepath = filepath[:63]
        library = bpy.data.libraries.get(filepath)
        bpy.data.libraries.remove(library)

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
        asset_group = self._retrieve_undefined_asset_group(group_name)
        libpath = Path(get_representation_path(representation)).as_posix()

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}"
        )

        import_method = ImportMethod(asset_group['import_method'])

        old_data = dict(asset_group.get(AVALON_PROPERTY))
        old_members = old_data.get("members", [])

        if isinstance(asset_group, bpy.types.Object):
            transform = asset_group.matrix_basis.copy()
            asset_group_parent = asset_group.parent
            actions = {}
            objects_with_anim = [
                obj for obj in asset_group.children_recursive
                if obj.animation_data
            ]

            for obj in objects_with_anim:
                # Check if the object has an action and, if so, add it to a dict
                # so we can restore it later. Save and restore the action only
                # if it wasn't originally loaded from the current asset.
                if obj.animation_data.action not in old_members:
                    actions[obj.name] = obj.animation_data.action

        asset = representation.get('asset', '')
        subset = representation.get('subset', '')

        parent = self.get_parent_data(representation)
        if not parent:
            self.log.warning(f"Can not retrieve parent from asset {asset} / subset {subset}")

        representation["context"]["parent"] = parent

        self.exec_remove(container)

        container, members = self.load_assets_and_create_hierarchy(
            representation=representation,
            libpath=libpath,
            group_name=group_name,
            unique_number=plugin.get_unique_number(asset, subset),
            import_method=import_method
        )

        if isinstance(asset_group, bpy.types.Object):
            asset_group.matrix_basis = transform
            asset_group.parent = asset_group_parent

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

        asset_group = self._retrieve_undefined_asset_group(group_name)
        asset_group[AVALON_PROPERTY] = old_data

        new_data = {
            "libpath": libpath,
            "representation": str(representation["_id"]),
            "parent": str(representation["parent"]),
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

        asset_group = self._retrieve_undefined_asset_group(group_name)
        assert asset_group, f"Can not find asset_group with name {group_name}"

        attrs = [
            attr for attr in dir(bpy.data)
            if isinstance(
                getattr(bpy.data, attr),
                bpy.types.bpy_prop_collection
            )
        ]

        members = asset_group.get(AVALON_PROPERTY).get("members", [])

        collections_parents = [
            collection for collection in bpy.data.collections
            if set(data for data in members).intersection(set(collection.objects))
            and collection is not asset_group
        ]

        parent_containers = self.get_all_container_parents(asset_group)

        for parent in parent_containers:
            parent.get(AVALON_PROPERTY)["members"] = list(filter(
                lambda i: i not in members,
                parent.get(AVALON_PROPERTY).get("members", [])))
        print('\n\n\nATTRIBUTE')
        for attr in attrs:
            print(attr)
            print([data for data in getattr(bpy.data, attr)])
            for data in getattr(bpy.data, attr):
                print(data)
                print(data in members)
                if not data in members:
                    continue

                # Skip the asset group
                if data == asset_group:
                    continue

                attribute = getattr(bpy.data, attr)
                if not hasattr(attribute, 'remove'):
                    continue

                attribute.remove(data)

        if isinstance(asset_group, bpy.types.Object):
            bpy.data.objects.remove(asset_group)
        else:
            bpy.data.collections.remove(asset_group)

        self._remove_collection_recursively(collections_parents)

    @staticmethod
    def _retrieve_undefined_asset_group(group_name):
        asset_group = bpy.data.objects.get(group_name)

        if not asset_group:
            return bpy.data.collections.get(group_name)

        return asset_group

    @staticmethod
    def _get_collections_parents(collection):
        return [
            parent for parent in bpy.data.collections
            if collection in list(parent.children)
        ]

    def _remove_collection_recursively(self, collections, deleted_collections=[]):
        for collection in collections:
            if collection in deleted_collections:
                continue

            if collection.objects or collection.children:
                continue

            parents = self._get_collections_parents(collection)

            deleted_collections.append(collection)
            bpy.data.collections.remove(collection)

            self._remove_collection_recursively(
                collections=parents,
                deleted_collections=deleted_collections
            )
