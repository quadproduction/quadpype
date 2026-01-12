"""Load an asset in Blender from an Alembic file."""

from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional

import bpy
import os

from quadpype.client import get_version_by_id
from quadpype.lib import BoolDef, filter_profiles, StringTemplate
from quadpype.pipeline.publish.lib import get_template_name_profiles
from quadpype.pipeline.anatomy import Anatomy
from quadpype.pipeline import (
    get_representation_path,
    AVALON_CONTAINER_ID,
    get_current_context,
    split_hierarchy,
    get_task_hierarchy_templates,
    get_resolved_name,
    format_data,
    get_load_naming_template,
    get_current_host_name,

)
from quadpype.client.mongo.entities import get_assets
from quadpype.settings import get_project_settings
from quadpype.hosts.blender.api.pipeline import (
    get_avalon_node,
    add_to_avalon_container,
    is_material_from_loaded_look
)
from quadpype.hosts.blender.api.collections import (
    get_collections_numbered_hierarchy_and_correspondence,
    organize_objects_in_templated_collection
)
from quadpype.hosts.blender.api.constants import AVALON_CONTAINERS, YELLOW, ORANGE

from quadpype.hosts.blender.api.json_loader import load_content, apply_properties

from quadpype.hosts.blender.api import plugin, lib


class CacheModelLoader(plugin.BlenderLoader):
    """Load cache models.

    Stores the imported asset in a collection named after the asset.

    Note:
        At least for now it only supports Alembic files.
    """
    families = ["model", "pointcache", "animation", "usd"]
    representations = ["abc", "usd"]

    label = "Load Cache"
    icon = "code-fork"
    color = "orange"

    defaults = {
        'create_as_asset_group': False,
        'apply_subdiv': True
    }

    @classmethod
    def get_options(cls, contexts):
        return [
            BoolDef(
                "create_as_asset_group",
                default=False,
                label="Import as Asset Group"
            ),
            BoolDef(
                "apply_subdiv",
                default=True,
                label="Add a Subdiv Modifier"
            )
        ]

    @staticmethod
    def correspondence(obj1, obj2):
        return obj1.name in obj2.name or obj2.name in obj1.name

    def _update_transform_cache_path(self, asset_group, libpath, prev_filename, representation):
        """search and update path in the transform cache modifier
        If there is no transform cache modifier, it will create one
        to update the filepath of the alembic.
        """

        avalon_node = get_avalon_node(asset_group)
        apply_subdiv = avalon_node["apply_subdiv"]
        corresponding_names = avalon_node["corresponding_names"]
        members = lib.get_objects_from_mapped(avalon_node.get('members', []))

        previous_file_caches = [file for file in bpy.data.cache_files]
        # Load temp new ABC to compare with old one
        bpy.ops.wm.alembic_import(
            filepath=str(libpath)
        )
        file_caches = [file for file in bpy.data.cache_files]
        new_file_cache = [x for x in file_caches if x not in previous_file_caches or previous_file_caches.remove(x)][0]

        temp_members = lib.get_selection()


        removed_objects = [o1 for o1 in members if not any(self.correspondence(o1, o2) for o2 in temp_members)]
        new_objects = [o2 for o2 in temp_members if not any(self.correspondence(o2, o1) for o1 in members)]

        for obj in removed_objects:
            self.log.info(f"{obj.name} has been removed")
            members.remove(obj)
            del corresponding_names[obj.name]
            bpy.data.objects.remove(obj)

        if new_objects:
            template_data = format_data(representation, True, get_current_host_name())
            template_data["unique_number"] = avalon_node["unique_number"]
            full_name_template = get_load_naming_template("fullname")
            for obj in new_objects:
                old_name = obj.name
                obj.name = get_resolved_name(
                    template_data,
                    full_name_template,
                    name=obj.name,
                    container=asset_group.name
                )
                corresponding_names[obj.name] = old_name
                if obj.type != 'EMPTY':
                    obj.data.name = f"{obj.name}.data"

                parent_name = get_resolved_name(
                    template_data,
                    full_name_template,
                    name=obj.parent.name,
                    container=asset_group.name
                )
                obj_parent = bpy.data.objects.get(parent_name)
                obj.parent = obj_parent

                for coll in obj.users_collection:
                    coll.objects.unlink(obj)

                for coll in obj_parent.users_collection:
                    coll.objects.link(obj)

                temp_members.remove(obj)
                members.append(obj)
                self.log.info(f"{obj.name} has been added")

        for obj in members:
            names = [modifier.name for modifier in obj.modifiers
                     if modifier.type == "MESH_SEQUENCE_CACHE"]
            file_list = [file for file in bpy.data.cache_files
                         if file.name.startswith(asset_group.name)]
            if names:
                for name in names:
                    obj.modifiers.remove(obj.modifiers.get(name))
            if file_list:
                bpy.data.batch_remove(file_list)

            obj.modifiers.new(name='MeshSequenceCache', type='MESH_SEQUENCE_CACHE')

            subdiv_modifiers = lib.get_cache_modifiers(obj, modifier_type="SUBSURF")
            if not subdiv_modifiers and apply_subdiv:
                subdiv_modifiers[obj.name] = [obj.modifiers.new(name='Subdivision', type='SUBSURF')]

            modifiers = lib.get_cache_modifiers(obj)

            for asset_name, modifier_list in modifiers.items():
                for modifier in modifier_list:
                    if modifier.type == "MESH_SEQUENCE_CACHE":
                        modifier.cache_file = bpy.data.cache_files[-1]
                        cache_file_name = os.path.basename(libpath.as_posix())
                        modifier.cache_file.name = cache_file_name
                        modifier.cache_file.filepath = libpath.as_posix()
                        modifier.cache_file.scale = 1.0
                        bpy.context.evaluated_depsgraph_get()
                        if subdiv_modifiers:
                            subdiv = subdiv_modifiers.get(asset_name, [])
                            if subdiv:
                                modifier_index = obj.modifiers.find(subdiv[0].name)
                                obj.modifiers.move(modifier_index, len(obj.modifiers) - 1)
                        for object_path in modifier.cache_file.object_paths:
                            object_str_path = object_path.path
                            base_object_name = os.path.basename(object_path.path)
                            asset_name = asset_name.rsplit(":", 1)[-1]
                            if base_object_name.endswith(asset_name) or asset_name in object_str_path:
                                modifier.object_path = object_path.path
            bpy.context.evaluated_depsgraph_get()

        for obj in temp_members:
            bpy.data.objects.remove(obj)

        new_file_cache.name = f"{asset_group.name}.cache"
        lib.purge_orphans(is_recursive=True)
        return libpath, corresponding_names

    def _remove(self, asset_group):

        avalon_node = get_avalon_node(asset_group)
        members = lib.get_objects_from_mapped(avalon_node.get('members', []))
        collections_parents = [
            collection for collection in bpy.data.collections
            if set(members).intersection(set(collection.objects)) and collection is not asset_group
        ]

        members.extend([child for obj in members if obj.type == 'EMPTY' for child in obj.children])

        empties = []
        for obj in set(members):
            if obj.type == 'MESH':
                for material_slot in list(obj.material_slots):
                    if is_material_from_loaded_look(material_slot.material):
                        continue
                    bpy.data.materials.remove(material_slot.material)
                bpy.data.meshes.remove(obj.data)
            elif obj.type == 'EMPTY':
                empties.append(obj)

        for empty in empties:
            if bpy.data.objects.get(empty.name):
                bpy.data.objects.remove(empty)

        if isinstance(asset_group, bpy.types.Collection):
            for coll in collections_parents:
                bpy.data.collections.remove(coll)

    def _process(self, libpath, container_name, asset_group=None, apply_subdiv=False):
        plugin.deselect_all()

        relative = bpy.context.preferences.filepaths.use_relative_paths
        previous_file_caches = [file for file in bpy.data.cache_files]

        if any(libpath.lower().endswith(ext)
               for ext in [".usd", ".usda", ".usdc"]):
            # USD
            bpy.ops.wm.usd_import(
                filepath=libpath,
                relative_path=relative
            )

        else:
            # Alembic
            bpy.ops.wm.alembic_import(
                filepath=libpath,
                relative_path=relative
            )

        objects = lib.get_selection()

        for obj in objects:
            if apply_subdiv:
                obj.modifiers.new(name='Subdivision', type='SUBSURF')

            # reparent top object to asset_group
            if asset_group and not obj.parent:
                obj.parent = asset_group

            # Unlink the object from all collections
            collections = obj.users_collection
            for collection in collections:
                collection.objects.unlink(obj)

            if obj.type != 'EMPTY':
                for material_slot in obj.material_slots:
                    name_mat = material_slot.material.name
                    material_slot.material.name = f"{container_name}:{name_mat}"


        plugin.deselect_all()
        file_caches = [file for file in bpy.data.cache_files]
        new_file_cache = [x for x in file_caches if x not in previous_file_caches or previous_file_caches.remove(x)][0]
        new_file_cache.name = f"{container_name}.cache"

        return objects

    def _link_objects(self, objects, avalon_container, container):
        return


    def load_assets_and_create_hierarchy(self, container_name,
                                         template_data=None,
                                         unique_number='01',
                                         create_as_empty=True,
                                         apply_subdiv=True,
                                         libpath=None):

        # Load and rename ABC
        members = self._process(libpath=libpath,
                                container_name=container_name,
                                apply_subdiv=apply_subdiv)

        full_name_template = get_load_naming_template("fullname")
        corresponding_names = {}
        for obj in members:
            old_name = obj.name
            obj.name = get_resolved_name(
                template_data,
                full_name_template,
                name=obj.name,
                container=container_name
            )
            corresponding_names[obj.name] = old_name
            if obj.type != 'EMPTY':
                obj.data.name = f"{obj.name}.data"

        # Create the containers and organize the loaded objects
        avalon_container = bpy.data.collections.get(AVALON_CONTAINERS)

        if not avalon_container:
            avalon_container = bpy.data.collections.new(name=AVALON_CONTAINERS)
            bpy.context.scene.collection.children.link(avalon_container)
        avalon_container.color_tag = YELLOW

        if create_as_empty:
            container = bpy.data.objects.get(container_name)
            if not container:
                container = bpy.data.objects.new(container_name, object_data=None)
            container.empty_display_type = 'SINGLE_ARROW'

            collection = bpy.context.view_layer.active_layer_collection.collection
            collection.objects.link(container)

            # Link the imported objects to any collection where the asset group is
            # linked to, except the AVALON_CONTAINERS collection
            group_collections = [
                collection
                for collection in container.users_collection
                if collection != avalon_container]

            for obj in members:
                # reparent top object to asset_group
                if not obj.parent:
                    obj.parent = container
                for collection in group_collections:
                    collection.objects.link(obj)


        else:
            container = bpy.data.collections.get(container_name)
            if not container:
                container = bpy.data.collections.new(container_name)

            collections_are_created, corresponding_collections_numbered, collections_numbered_hierarchy = (
                get_collections_numbered_hierarchy_and_correspondence(template_data, unique_number, color=ORANGE)
            )
            for blender_object in members:
                container.objects.link(blender_object)
            if collections_are_created:
                organize_objects_in_templated_collection(
                    members,
                    collections_numbered_hierarchy,
                    corresponding_collections_numbered,
                    unique_number
                )


        add_to_avalon_container(container)
        return container, members, corresponding_names

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

        create_as_asset_group = options.get(
            'create_as_asset_group',
            self.defaults['create_as_asset_group']
        )
        apply_subdiv = options.get(
            'apply_subdiv',
            self.defaults['apply_subdiv']
        )

        template_data = format_data(representation, True, get_current_host_name())
        asset_name_template = get_load_naming_template("assetname")
        namespace_template = get_load_naming_template("namespace")
        group_name_template = get_load_naming_template("container")

        asset_name = get_resolved_name(template_data, asset_name_template)
        unique_number = plugin.get_unique_number(asset, subset, template_data)
        template_data.update({"unique_number": unique_number})

        namespace = namespace or get_resolved_name(template_data, namespace_template)
        container_name = get_resolved_name(template_data, group_name_template, namespace=namespace)

        container, members, corresponding_names = self.load_assets_and_create_hierarchy(
            container_name=container_name,
            template_data=template_data,
            unique_number=unique_number,
            create_as_empty=create_as_asset_group,
            apply_subdiv=apply_subdiv,
            libpath=libpath
        )

        project_name = representation.get('context', {}).get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        self.apply_json_properties(representation, corresponding_names)

        lib.imprint(
            node=container,
            data={
                "schema": "quadpype:container-2.0",
                "id": AVALON_CONTAINER_ID,
                "asset": self._get_associated_asset(context, project_name),
                "name": name,
                "namespace": namespace or '',
                "loader": str(self.__class__.__name__),
                "representation": str(context["representation"]["_id"]),
                "libpath": libpath,
                "asset_name": asset_name,
                "task": representation["context"]["task"]["name"],
                "parent": str(context["representation"]["parent"]),
                "family": context["representation"]["context"]["family"],
                "objectName": container_name,
                "unique_number": unique_number,
                "version": get_version_by_id(project_name, str(representation["parent"])).get('name', ''),
                "members": lib.map_to_classes_and_names(members),
                "create_as_asset_group": create_as_asset_group,
                "apply_subdiv": apply_subdiv,
                "corresponding_names" : corresponding_names
            },
            erase=False
        )

        self[:] = members
        return members

    @staticmethod
    def _get_associated_asset(context, project_name):
        current_project_asset_pointer = get_assets(project_name)
        project_assets = [a["name"] for a in current_project_asset_pointer if a["data"]["tasks"]]
        candidates = sorted(project_assets, key=len, reverse=True)
        subset_name = context["subset"]["name"]
        correspondence_by_subset = next((c for c in candidates if c in subset_name), None)

        representation = context["representation"]
        repre_asset = representation["context"]["asset"]
        correspondence_by_repre_asset = next((c for c in candidates if c in repre_asset), None)


        return correspondence_by_subset if correspondence_by_subset else correspondence_by_repre_asset

    def apply_json_properties(self, representation, corresponding_names):
        template_data = format_data(
            original_data=representation,
            filter_variant=False,
            app=get_current_host_name(),
            update_parent_to_prefix=False)
        project_name = representation.get('context', {}).get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        repre_task = representation.get('context', {}).get('task', {}).get('name', None)
        assert repre_task, "Can not retrieve task name from context data."

        repre_family = representation.get('context', {}).get('family', None)
        assert repre_family, "Can not retrieve family name from context data."

        profiles = get_template_name_profiles(
            project_name, get_project_settings(project_name), self.log
        )

        template_data.update(
            {
                'families': repre_family,
                'task_types': repre_task,
                'ext': 'json'
            }
        )

        profile = filter_profiles(profiles, template_data)

        anatomy = Anatomy()
        templates = anatomy.templates.get(profile['template_name'])

        json_path = StringTemplate.format_template(templates['path'], template_data)
        if not json_path:
            self.log.warning("There is no json file to apply for this asset. Abort applying properties.")
            return

        json_content = load_content(json_path, self.log)

        if not json_content:
            self.log.error("Can not load content from retrieved json. Abort applying properties.")
            return

        apply_properties(json_content, corresponding_names)

    def exec_update(self, container: Dict, representation: Dict):
        """Update the loaded asset.

        This will remove all objects of the current collection, load the new
        ones and add them to the collection.
        If the objects of the collection are used in another collection they
        will not be removed, only unlinked. Normally this should not be the
        case though.

        Warning:
            No nested collections are supported at the moment!
        """
        object_name = container["objectName"]
        asset_group = self._get_container(object_name)
        libpath = Path(get_representation_path(representation))
        extension = libpath.suffix.lower()

        self.log.info(
            "Container: %s\nRepresentation: %s",
            pformat(container, indent=2),
            pformat(representation, indent=2),
        )

        assert asset_group, (
            f"The asset is not loaded: {container['objectName']}"
        )
        assert libpath, (
            "No existing library file found for {container['objectName']}"
        )
        assert libpath.is_file(), (
            f"The file doesn't exist: {libpath}"
        )
        assert extension in plugin.VALID_EXTENSIONS, (
            f"Unsupported file: {libpath}"
        )

        metadata = get_avalon_node(asset_group)
        group_libpath = metadata["libpath"]

        normalized_group_libpath = (
            str(Path(bpy.path.abspath(group_libpath)).resolve())
        )
        normalized_libpath = (
            str(Path(bpy.path.abspath(str(libpath))).resolve())
        )
        self.log.debug(
            "normalized_group_libpath:\n  %s\nnormalized_libpath:\n  %s",
            normalized_group_libpath,
            normalized_libpath,
        )
        if normalized_group_libpath == normalized_libpath:
            self.log.info("Library already loaded, not updating...")
            return

        template_data = format_data(representation, True, get_current_host_name())
        template_data.update({"unique_number": container.get("unique_number", "00")})
        corresponding_names = metadata["corresponding_names"]

        if any(str(libpath).lower().endswith(ext)
               for ext in [".usd", ".usda", ".usdc"]):
            #ToDo rework when usd will be used
            mat = asset_group.matrix_basis.copy()
            self._remove(asset_group)

            objects = self._process(libpath=str(libpath),
                                    container_name=asset_group,
                                    asset_group=object_name)

            containers = bpy.data.collections.get(AVALON_CONTAINERS)
            self._link_objects(objects, asset_group, containers, asset_group)

            asset_group.matrix_basis = mat
        else:
            prev_filename = os.path.basename(container["libpath"])
            libpath, corresponding_names = self._update_transform_cache_path(asset_group, libpath, prev_filename, representation)

        project_name = representation.get('context', {}).get('project', {}).get('name', None)
        assert project_name, "Can not retrieve project name from context data."

        self.apply_json_properties(representation, corresponding_names)

        new_data = {
            "libpath": str(libpath),
            "representation": str(representation["_id"]),
            "parent": str(representation["parent"]),
            "version": get_version_by_id(project_name, str(representation["parent"])).get('name', ''),
            "members": lib.map_to_classes_and_names(lib.get_asset_children(asset_group)),
            "corresponding_names": corresponding_names
        }
        lib.imprint(asset_group, new_data)

        metadata["libpath"] = str(libpath)
        metadata["representation"] = representation["_id"]

    def exec_remove(self, container: Dict) -> bool:
        """Remove an existing container from a Blender scene.

        Arguments:
            container (quadpype:container-1.0): Container to remove,
                from `host.ls()`.

        Returns:
            bool: Whether the container was deleted.

        Warning:
            No nested collections are supported at the moment!
        """
        object_name = container["objectName"]
        asset_group = self._get_container(object_name)

        if not asset_group:
            return False

        self._remove(asset_group)

        if isinstance(asset_group, bpy.types.Object):
            bpy.data.objects.remove(asset_group)
        elif isinstance(asset_group, bpy.types.Collection):
            bpy.data.collections.remove(asset_group)

        lib.purge_orphans(is_recursive=True)
        return True

    @staticmethod
    def _get_container(object_name):
        if bpy.data.objects.get(object_name):
            return bpy.data.objects.get(object_name)

        elif bpy.data.collections.get(object_name):
            return bpy.data.collections.get(object_name)

        else:
            return None
