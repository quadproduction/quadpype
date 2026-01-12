from typing import Dict, List, Optional
from pathlib import Path

import bpy
import re

from quadpype.lib.attribute_definitions import EnumDef
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

from quadpype.pipeline.create import CreateContext
from quadpype.hosts.blender.api import plugin, lib, pipeline
from quadpype.hosts.blender.api import (
    get_objects_in_collection,
    get_parents_for_collection,
    get_top_collection,
    get_corresponding_hierarchies_numbered,
    create_collections_from_hierarchy,
    create_collection
)
from quadpype.hosts.blender.api.pipeline import (
    has_avalon_node,
    get_avalon_node
)
from quadpype.hosts.blender.api.constants import AVALON_CONTAINERS, ORANGE
from quadpype.hosts.blender.api.workfile_template_builder import (
    ImportMethod
)


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
            if has_avalon_node(parent):
                parent_containers.append(parent)
            parent = self._get_parents(parent)

        return parent_containers

    @staticmethod
    def _get_parents(asset_group):
        if hasattr(asset_group, "parent"):
            return asset_group.parent
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
                    get_avalon_node(obj).get('family') == 'rig'
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

        template_data = format_data(representation, True, get_current_host_name())
        asset_name_template = get_load_naming_template("assetname")
        namespace_template = get_load_naming_template("namespace")
        group_name_template = get_load_naming_template("container")

        asset_name = get_resolved_name(template_data, asset_name_template)
        unique_number = plugin.get_unique_number(asset, subset, template_data)
        template_data.update({"unique_number":unique_number})

        namespace = namespace or get_resolved_name(template_data, namespace_template)
        group_name = get_resolved_name(template_data, group_name_template, namespace=namespace)

        import_method = ImportMethod(
            options.get(
                'import_method',
                self.defaults['import_method']
            )
        )

        container, members = self.load_assets_and_create_hierarchy(
            representation=representation,
            libpath=libpath,
            group_name=group_name,
            unique_number=unique_number,
            import_method=import_method,
            template_data=template_data
        )

        try:
            family = representation["context"]["family"]
        except ValueError:
            family = "model"

        if family == "layout":
            self._post_process_layout(container, asset, representation_id)

        project_name = context.get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

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
            "members": lib.map_to_classes_and_names(members),
            "import_method": import_method.value,
            "unique_number": unique_number,
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', '')
        }

        lib.imprint(container, data)

        objects = [
            obj for obj in bpy.data.objects
            if obj.name.startswith(f"{group_name}:")
        ]

        self[:] = objects
        return objects

    def load_assets_and_create_hierarchy(self, representation, libpath, group_name, unique_number, import_method,
                                         template_data):

        data_template = format_data(representation, True, get_current_host_name())
        collection_templates = get_task_hierarchy_templates(
            data_template,
            task=get_current_context()['task_name']
        )

        container, members, container_objects = self.import_blend_objects(libpath, group_name, import_method,
                                                                          template_data)
        if import_method is ImportMethod.APPEND:
            self.remove_library_from_blend_file(libpath)

        collections_are_created = None

        corresponding_collections_numbered = dict()
        collections_numbered_hierarchy = list()

        if collection_templates:
            collections_hierarchy = [
                get_resolved_name(
                    data=data_template,
                    template=template
                )
                for template in collection_templates
            ]
            collections_numbered_hierarchy = [
                get_resolved_name(
                    data=data_template,
                    template=template,
                    numbering=unique_number
                )
                for template in collection_templates
            ]

            corresponding_collections_numbered = get_corresponding_hierarchies_numbered(
                collections_hierarchy,
                collections_numbered_hierarchy
            )

            collections_are_created = create_collections_from_hierarchy(
                hierarchies=collections_numbered_hierarchy,
                parent_collection=bpy.context.scene.collection,
                color=ORANGE
            )

        if collections_are_created:
            default_parent_collection_name = self._get_last_collection_from_first_template(
                collections_numbered_hierarchy
            )

            for blender_object in container_objects:

                # Do not link non-objects or invisible objects from the published scene
                if not blender_object.get('visible', True):
                    continue

                collection = bpy.data.collections[default_parent_collection_name]

                object_hierarchies = blender_object.get('original_collection_parent', '')
                split_object_hierarchies = object_hierarchies.replace('\\', '/').split('/')

                for collection_number, hierarchy in enumerate(split_object_hierarchies):
                    corresponding_collection_name = corresponding_collections_numbered.get(
                        hierarchy,
                        f"{hierarchy}-{unique_number}"
                    )

                    if collection_number == 0:
                        collection = get_top_collection(
                            collection_name=corresponding_collection_name,
                            default_parent_collection_name=default_parent_collection_name
                        )

                    else:
                        parent_collection_name = split_object_hierarchies[collection_number - 1]
                        parent_collection_name_numbered = corresponding_collections_numbered.get(
                            parent_collection_name, f"{parent_collection_name}-{unique_number}")

                        collection = create_collection(
                            corresponding_collection_name,
                            parent_collection_name_numbered,
                            ORANGE
                        )

                if blender_object in list(collection.objects):
                    continue

                collection.objects.link(blender_object)

        else:
            # TODO: move this because it needs to happen when template is found and to raise error if none found
            [bpy.context.scene.collection.objects.link(member) for member in members if
             isinstance(member, bpy.types.Object)]

        pipeline.add_to_avalon_container(container)
        return container, members

    def import_blend_objects(self, libpath, group_name, import_method, template_data):
        if import_method == ImportMethod.APPEND:
            container, members, container_objects = self.append_blend_objects(libpath, group_name, template_data)
        elif import_method == ImportMethod.LINK:
            container, members, container_objects = self.link_blend_objects(libpath)
        elif import_method == ImportMethod.OVERRIDE:
            container, members, container_objects = self.link_blend_objects_with_overrides(libpath, group_name,
                                                                                           template_data)
        else:
            raise RuntimeError("No import method specified when importing blend objects.")

        return container, members, container_objects

    def append_blend_objects(self, libpath, group_name, template_data):
        data_to = self._load_from_blendfile(
            libpath,
            import_link=False,
            override=False
        )
        container = pipeline.get_container(data_to.objects, data_to.collections)
        assert container, "No asset group found"

        members = self._collect_members(data_to)

        # Needs to rename in separate block to retrieve blender object after initialisation
        full_name_template = get_load_naming_template("fullname")
        for attr in dir(data_to):
            for data in getattr(data_to, attr):
                if not isinstance(data, bpy.types.ID):
                    continue
                data.name = get_resolved_name(
                    template_data,
                    full_name_template,
                    name=data.name,
                    container=group_name
                )

        container.name = group_name

        container_objects = pipeline.get_container_content(container)
        return container, members, container_objects

    def link_blend_objects(self, libpath):
        data_to = self._load_from_blendfile(
            libpath,
            import_link=True,
            override=False
        )
        container = pipeline.get_container(data_to.objects, data_to.collections)
        assert container, "No asset group found"

        members = self._collect_members(data_to)
        container_objects = pipeline.get_container_content(container)

        return container, members, container_objects

    def link_blend_objects_with_overrides(self, libpath, group_name, template_data):
        data_to = self._load_from_blendfile(
            libpath,
            import_link=True,
            override=False
        )
        container = pipeline.get_container(data_to.objects, data_to.collections)
        members = self._collect_members(data_to)

        original_container_name = ""

        corresponding_renamed = dict()

        full_name_template = get_load_naming_template("fullname")
        for attr in dir(data_to):
            for data in getattr(data_to, attr):
                if not hasattr(data, 'override_create'):
                    continue

                new_data = data.override_create(remap_local_usages=True)
                if not new_data:
                    continue

                new_data.name = get_resolved_name(
                    template_data,
                    full_name_template,
                    name=data.name,
                    container=group_name
                )
                corresponding_renamed[data.name] = new_data.name

                # We need to add newly linked objects to members
                # in order to be effectively removed or updated later.
                members.append(new_data)

                if data == container:
                    original_container_name = container.name
                    container = new_data

        assert container, "No asset group found"
        container.name = group_name

        container_objects = pipeline.get_container_content(container)

        # If the container is an empty, no parent value is stored in the loaded obj
        # So we retrieve the corresponding renamed overrided obj imported except the original container
        if not container_objects:
            container_objects = [bpy.data.objects.get(corresponding_renamed.get(obj.name)) for obj in data_to.objects
                                 if obj.name != original_container_name]

        # Remap parent
        for obj in container_objects:
            if not obj.parent:
                continue

            if obj.parent.name not in corresponding_renamed.keys() and obj.parent.name in corresponding_renamed.values():
                self.log.warning(f"Parent {obj.parent.name} already set")
                continue

            obj.parent = bpy.data.objects.get(corresponding_renamed.get(obj.parent.name))

        for new_obj in corresponding_renamed.values():
            obj = bpy.data.objects.get(new_obj)

            if obj and obj.override_library:
                if not obj.data or not obj.data.library:
                    continue

                # Remap override data
                data_type = lib.get_data_type_name(obj.data)
                corresponding_renamed_data_name = corresponding_renamed.get(obj.data.name)
                if not corresponding_renamed_data_name:
                    self.log.warning(f"No corresponding data found for {obj.data.name}")
                for data in getattr(bpy.data, data_type):
                    if data.name == corresponding_renamed_data_name:
                        obj.data = data

                # Remap bones custom shapes
                if data_type == "armatures":
                    for bone in obj.pose.bones:
                        old_shape = bone.custom_shape
                        if not old_shape:
                            continue
                        corresponding_renamed_shape_name = corresponding_renamed.get(old_shape.name)
                        if not corresponding_renamed_shape_name:
                            self.log.warning(f"No corresponding data found for {old_shape.name}")
                        bone.custom_shape = bpy.data.objects.get(corresponding_renamed_shape_name)

                # Remap override data in deformers
                if not obj.modifiers:
                    continue

                for mod in obj.modifiers:
                    mod_object = getattr(mod, "object", None)
                    if not mod_object:
                        continue

                    mod_object_name = mod_object.name
                    new_mod_object = bpy.data.objects.get(corresponding_renamed.get(mod_object_name), mod_object_name)
                    mod.object = new_mod_object

        return container, members, container_objects

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
    def _collect_members(data_attributes):
        members = []
        # Needs to rename in separate block to retrieve blender object after initialisation
        for attr in dir(data_attributes):
            for data in getattr(data_attributes, attr):
                if isinstance(data, str):
                    continue

                members.append(data)

        return members

    @staticmethod
    def _get_new_name(name, group_name, truncate_occurrence=False):
        if truncate_occurrence:
            name = re.sub(r".\d{3}$", "", name)
        new_name = f"{group_name}:{name}"
        return new_name

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
    def _get_last_collection_from_first_template(hierarchies):
        return split_hierarchy(hierarchies[0])[-1]

    def exec_update(self, container: Dict, representation: Dict):
        """
        Update the loaded asset.
        """
        group_name = container["objectName"]
        asset_group = self._retrieve_undefined_asset_group(group_name)
        libpath = Path(get_representation_path(representation))

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}"
        )

        project_name = representation.get('context', {}).get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        avalon_data = pipeline.get_avalon_node(asset_group)

        import_method = ImportMethod(
            avalon_data.get(
                'import_method',
                self.defaults['import_method']
            )
        )
        if import_method != ImportMethod.APPEND:
            old_linked_lib = lib.get_library_from_path(avalon_data["libpath"])
            if old_linked_lib:
                old_linked_lib.filepath = bpy.path.abspath(libpath.as_posix())
                old_linked_lib.reload()

            new_linked_lib = lib.get_library_from_path(libpath.as_posix())
            if not new_linked_lib:
                return
            new_linked_lib.reload()

            new_data = {
                "libpath": libpath.as_posix(),
                "representation": str(representation["_id"]),
                "parent": str(representation["parent"]),
                "version": get_version_by_id(project_name, str(representation["parent"])).get('name', '')
            }
            lib.imprint(asset_group, new_data)
            return

        if isinstance(asset_group, bpy.types.Object):
            transform = asset_group.matrix_basis.copy()
            asset_group_parent = asset_group.parent
            all_objects_from_asset = asset_group.children_recursive
        else:
            all_objects_from_asset = get_objects_in_collection(asset_group)

        objects_with_anim = [
            obj for obj in all_objects_from_asset
            if obj.animation_data
        ]
        objects_with_no_anim = [
            obj for obj in all_objects_from_asset
            if not obj.animation_data
        ]

        materials_by_objects = {}
        for obj in all_objects_from_asset:
            materials_by_objects[obj.name] = [slot.material for slot in obj.material_slots if slot.material]

        actions = {}
        for obj in objects_with_anim:
            # Check if the object has an action and, if so, add it to a dict
            # so we can restore it later. Save and restore the action only
            # if it wasn't originally loaded from the current asset.
            if not obj.animation_data.action:
                continue
            if obj.animation_data.action.name not in avalon_data.get("members", []).get("actions", []):
                actions[obj.name] = obj.animation_data.action.name

        snap_properties = {}
        for obj in objects_with_no_anim:
            snap_properties[obj.name] = lib.get_properties_on_object(obj)

        asset = representation.get('asset', '')
        subset = representation.get('subset', '')
        template_data = format_data(representation, True, get_current_host_name())
        template_data.update({"unique_number": container.get("unique_number", "00")})
        self.exec_remove(container)

        container, members = self.load_assets_and_create_hierarchy(
            representation=representation,
            libpath=libpath.as_posix(),
            group_name=group_name,
            unique_number=avalon_data.get("unique_number", plugin.get_unique_number(asset, subset)),
            import_method=ImportMethod(
                avalon_data.get(
                    'import_method',
                    self.defaults['import_method']
                )
            ),
            template_data=template_data
        )

        asset_group = self._retrieve_undefined_asset_group(group_name)

        if isinstance(asset_group, bpy.types.Object):
            asset_group.matrix_basis = transform
            asset_group.parent = asset_group_parent

            all_objects_from_asset = asset_group.children_recursive

        else:
            all_objects_from_asset = get_objects_in_collection(asset_group)

        # Restore the actions
        for obj in all_objects_from_asset:
            if obj.name in actions:
                if not actions.get(obj.name):
                    continue
                if not obj.animation_data:
                    obj.animation_data_create()

                action = bpy.data.actions.get(actions.get(obj.name))
                if not action:
                    continue
                obj.animation_data.action = action

            elif obj.name in snap_properties:
                lib.set_properties_on_object(obj, snap_properties[obj.name])

            if obj.name in materials_by_objects:
                for mat in materials_by_objects[obj.name]:
                    if not mat:
                        continue
                    obj.data.materials.append(mat)

        # Restore the old data, but reset members, as they don't exist anymore,
        # This avoids a crash, because the memory addresses of those members
        # are not valid anymore
        # TODO: We lose asset in scene inventory if we comment the following lines.
        # TODO: It would be great to understand why ? Moving the erase arg after doesn't work.
        avalon_data["members"] = []
        lib.imprint(asset_group, avalon_data, erase=True)

        new_data = {
            "libpath": libpath.as_posix(),
            "representation": str(representation["_id"]),
            "parent": str(representation["parent"]),
            "members": lib.map_to_classes_and_names(members),
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', '')
        }
        lib.imprint(asset_group, new_data)

        # We need to update all the parent container members
        parent_containers = self.get_all_container_parents(asset_group)

        for parent_container in parent_containers:
            parent_avalon_node = pipeline.get_avalon_node(parent_container)
            parent_members = lib.get_objects_from_mapped(parent_avalon_node["members"])
            lib.imprint(parent_container, {'members': lib.map_to_classes_and_names(parent_members + members)})

    def exec_remove(self, container: Dict):
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

        avalon_node = pipeline.get_avalon_node(asset_group)
        members = lib.get_objects_from_mapped(avalon_node.get('members', []))

        collections_parents = [
            collection for collection in bpy.data.collections
            if set(members).intersection(set(collection.objects))
            and not pipeline.get_avalon_node(asset_group)
        ]

        parent_containers = self.get_all_container_parents(asset_group)

        for parent in parent_containers:
            parent_members = list(filter(
                lambda i: i not in members,
                lib.get_objects_from_mapped(pipeline.get_avalon_node(parent)['members'])))

            lib.imprint(parent, {'members': parent_members})

        deleted_collections = list()
        obj_to_delete = self.get_unique_members(group_name, members, container)

        for attr in attrs:
            for data in getattr(bpy.data, attr):
                if data not in obj_to_delete:
                    continue

                # Skip the asset group
                if data == asset_group:
                    continue

                attribute = getattr(bpy.data, attr)
                if not hasattr(attribute, 'remove'):
                    continue

                if isinstance(data, bpy.types.Collection):
                    deleted_collections.append(data)

                attribute.remove(data)

        if isinstance(asset_group, bpy.types.Object):
            bpy.data.objects.remove(asset_group)
        else:
            bpy.data.collections.remove(asset_group)

        self._remove_collection_recursively(collections_parents, deleted_collections)
        lib.purge_library()

    def get_unique_members(self, collection_name, current_members, container):
        if container.get('import_method', None) == ImportMethod.APPEND.value:
            return current_members

        asset_name = container.get('asset_name', None)
        version = container.get('version', None)

        for collection in self._get_other_collection_with_name_and_version(collection_name, version, asset_name):
            coll_members = lib.get_objects_from_mapped(pipeline.get_avalon_node(collection).get('members', []))
            for coll_member in coll_members:
                if coll_member not in current_members:
                    continue

                current_members.remove(coll_member)

        return current_members

    @staticmethod
    def _get_other_collection_with_name_and_version(collection_name, version, asset_name):
        return [
            coll for coll in bpy.data.collections if
            pipeline.get_avalon_node(coll).get('version', None) == version and
            pipeline.get_avalon_node(coll).get('asset_name', None) == asset_name and
            coll.name != collection_name
        ]

    @staticmethod
    def _retrieve_undefined_asset_group(group_name):
        asset_group = bpy.data.objects.get(group_name)

        if not asset_group:
            return bpy.data.collections.get(group_name)

        return asset_group

    def _remove_collection_recursively(self, collections, deleted_collections=None):
        if deleted_collections is None:
            deleted_collections = []
        for collection in collections:
            if collection in deleted_collections:
                continue

            if collection.objects or collection.children:
                continue

            parents = get_parents_for_collection(collection)

            deleted_collections.append(collection)
            bpy.data.collections.remove(collection)

            self._remove_collection_recursively(
                collections=parents,
                deleted_collections=deleted_collections
            )
