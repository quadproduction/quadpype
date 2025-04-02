import json
from os import unlink
from pathlib import Path
from enum import Enum
import bpy

from quadpype.pipeline import registered_host

from .workio import (
    current_file,
    save_file
)

from quadpype.client import (
    get_project
)

from quadpype.pipeline.template_data import get_template_data

from quadpype.pipeline.workfile.workfile_template_builder import (
    TemplateAlreadyImported,
    AbstractTemplateBuilder,
    PlaceholderPlugin,
    LoadPlaceholderItem,
    CreatePlaceholderItem,
    PlaceholderLoadMixin,
    PlaceholderCreateMixin,
    should_apply_settings_on_build_first_workfile
)

from quadpype.hosts.blender.api.lib import (
    read,
    imprint,
    get_selection,
    make_scene_empty,
    get_parent_collections_for_object,
    purge_orphans
)

from quadpype.hosts.blender.api import pipeline

from quadpype.lib import (
    attribute_definitions
)

AVALON_PLACEHOLDER = "AVALON_PLACEHOLDER"

class ImportMethod(Enum):
    APPEND = "Append"
    LINK = "Link"
    OVERRIDE = "Link + override"

class BlenderTemplateBuilder(AbstractTemplateBuilder):
    """Concrete implementation of AbstractTemplateBuilder for blender"""

    use_legacy_creators = False
    template_data = ""

    def import_template(self, path):
        """Import template into current scene.
        Block if a template is already loaded.
        Args:
            path (str): A path to current template (usually given by
            get_template_preset implementation)
        Returns:
            bool: Whether the template was successfully imported or not
        """

        for scene in bpy.data.scenes:
            if scene.name == self.current_asset_name:
                raise TemplateAlreadyImported((
                    "Build template already loaded\n"
                    "Clean scene if needed (File > New Scene)"
                ))

        self.template_data = get_template_data(
                                get_project(self.project_name),
                                self.current_asset_doc,
                                self.current_task_name,
                                self.host_name
                            )

        make_scene_empty()

        path = Path(path)
        tpl_element_names = self._get_elements_to_append(path)

        bpy.ops.scene.new(type='EMPTY')
        bpy.context.scene.name = self.current_asset_name

        for scene in bpy.data.scenes:
            if scene.name == self.current_asset_name:
                continue
            bpy.data.scenes.remove(scene, do_unlink=True)

        with bpy.data.libraries.load(str(path), link=False) as (data_from, data_to):
            for data_type, names in tpl_element_names.items():
                if hasattr(data_from, data_type):
                    setattr(data_to, data_type, [item for item in getattr(data_from, data_type) if item in names])

        for obj in getattr(data_to, 'objects', []):
            if obj and not obj.users_collection:
                bpy.context.scene.collection.objects.link(obj)

        for collection in getattr(data_to, 'collections', []):
            if collection:
                bpy.context.scene.collection.children.link(collection)

        for world in getattr(data_to, 'worlds', []):
            if world:
                bpy.context.scene.world = world

        cameras = [cam for cam in bpy.data.objects.values() if cam.type == 'CAMERA']
        if cameras:
            bpy.context.scene.camera = cameras[0]

        for lib in bpy.data.libraries:
            bpy.data.libraries.remove(lib, do_unlink=True)

        purge_orphans(is_recursive=True)

        if should_apply_settings_on_build_first_workfile():
            self._set_settings()

        save_file(current_file())
        return True

    @staticmethod
    def _get_elements_to_append(path):
        """List all elements to append in scene based on a templated .blend
        Will avoid the instanced collections or collections in collections.
        Args:
            path (Path): A path to current template
        Returns:
            dict: {str: list}
                A dict of element type associated to a list of names to append
        """
        return_dict = {}

        with bpy.data.libraries.load(str(path), link=False) as (data_from, data_to):
            data_to.objects = data_from.objects
            data_collections = data_from.collections
            return_dict["worlds"] = data_from.worlds

        # Retrieve specific placeholder objects
        return_dict["objects"] = [obj.name for obj in data_to.objects if
                                  pipeline.get_avalon_node(obj).get("plugin_identifier", None)]

        instanced_collections_names = set()
        for obj in data_to.objects:
            if obj.instance_type == 'COLLECTION' and obj.instance_collection:
                print(f"The collection {obj.instance_collection.name} is instanced in {obj.name}")
                instanced_collections_names.add(obj.instance_collection.name)

            bpy.data.objects.remove(obj, do_unlink=True)


        return_dict["collections"] = [coll_name for coll_name in data_collections
                                      if coll_name not in instanced_collections_names]

        return return_dict

    @staticmethod
    def _set_settings():
        data = pipeline.get_asset_data()
        pipeline.set_resolution(data)
        pipeline.set_frame_range(data)

class BlenderPlaceholderLoadPlugin(PlaceholderPlugin, PlaceholderLoadMixin):
    identifier = "blender.load"
    label = "Blender Load"
    defaults = {
        'import_method': ImportMethod.APPEND.value
    }
    def _collect_scene_placeholders(self):
        placeholder_nodes = self.builder.get_shared_populate_data(
            "placeholder_nodes"
        )
        if placeholder_nodes is None:
            empties = [obj for obj in bpy.data.objects if pipeline.get_avalon_node(obj).get("plugin_identifier", None)]
            placeholder_nodes = {}
            for empty in empties:
                node_name = empty.name
                placeholder_nodes[node_name] = (
                    self._parse_placeholder_node_data(empty)
                )

            self.builder.set_shared_populate_data(
                "placeholder_nodes", placeholder_nodes
            )
        return placeholder_nodes

    def _parse_placeholder_node_data(self, empty):
        placeholder_data = read(empty)
        parent_name = (
            empty.get("parent")
            or ""
        )

        placeholder_data.update({
            "parent": parent_name,
        })
        return placeholder_data

    def _create_placeholder_name(self, placeholder_data):
        placeholder_name_parts = placeholder_data["builder_type"].split("_")
        pos = 1

        placeholder_family = placeholder_data["family"]
        if placeholder_family:
            placeholder_name_parts.insert(pos, placeholder_family)
            pos += 1

        loader_args = placeholder_data["loader_args"]
        if loader_args:
            loader_args = json.loads(loader_args.replace('\'', '\"'))
            values = [v for v in loader_args.values()]
            for value in values:
                placeholder_name_parts.insert(str(pos), value)
                pos += 1

        placeholder_name = "_".join(placeholder_name_parts)

        return placeholder_name.capitalize()

    def _get_loaded_repre_ids(self):
        loaded_representation_ids = self.builder.get_shared_populate_data(
            "loaded_representation_ids"
        )
        if loaded_representation_ids is None:
            empties = [obj for obj in bpy.data.objects if pipeline.get_avalon_node(obj).get("representation", None)]
            loaded_representation_ids = {
                empty.get(".representation")
                for empty in empties
            }
            self.builder.set_shared_populate_data(
                "loaded_representation_ids", loaded_representation_ids
            )
        return loaded_representation_ids

    def create_placeholder(self, placeholder_data):

        avalon_placeholder_coll = bpy.data.collections.get(AVALON_PLACEHOLDER)
        if not avalon_placeholder_coll:
            avalon_placeholder_coll = bpy.data.collections.new(name=AVALON_PLACEHOLDER)
            bpy.context.scene.collection.children.link(avalon_placeholder_coll)

        placeholder_data["plugin_identifier"] = self.identifier
        placeholder_name = self._create_placeholder_name(placeholder_data)

        placeholder = bpy.data.objects.new(name=placeholder_name, object_data=None)
        placeholder.empty_display_type = 'SINGLE_ARROW'

        if avalon_placeholder_coll:
            avalon_placeholder_coll.objects.link(placeholder)
        else:
            bpy.context.scene.collection.children.link(placeholder)

        if placeholder_data.get('action', None) is None:
            placeholder_data.pop('action')

        imprint(placeholder, placeholder_data)

    def update_placeholder(self, placeholder_item, placeholder_data):
        obj = bpy.data.objects.get(placeholder_item.scene_identifier)
        if not obj:
            raise ValueError("No objects found")

        new_values = {}
        for key, value in placeholder_data.items():
            placeholder_value = placeholder_item.data.get(key)
            if value != placeholder_value:
                new_values[key] = value
                placeholder_item.data[key] = value

        placeholder_name = self._create_placeholder_name(placeholder_data)
        obj.name = placeholder_name
        imprint(obj, new_values)

    def collect_placeholders(self):
        output = []
        scene_placeholders = self._collect_scene_placeholders()
        for obj_name, placeholder_data in scene_placeholders.items():
            if placeholder_data.get("plugin_identifier") != self.identifier:
                continue

            output.append(
                LoadPlaceholderItem(obj_name, placeholder_data, self)
            )

        return output

    def populate_placeholder(self, placeholder):
        options = self.parse_loader_args(placeholder.data.get("loader_args"))
        load_blend_options = self._get_load_blend_options_data(placeholder)

        options.update(load_blend_options)
        placeholder.data["loader_args"] = options

        self.populate_load_placeholder(placeholder)

    def repopulate_placeholder(self, placeholder):
        repre_ids = self._get_loaded_repre_ids()
        self.populate_load_placeholder(placeholder, repre_ids)

    def _get_load_blend_options_data(self, placeholder):
        import_method = ImportMethod(
            placeholder.data.get(
                'import_method',
                self.defaults['import_method']
            )
        )
        #The 'template' key is needed to execute the load not as MainThreadItem later
        return{
            "import_method": import_method.value,
            "template": True
        }

    def get_placeholder_options(self, options=None):
        options = {"representation" : "blend",
                   "subset" : "Main"}
        attr_defs = self.get_load_plugin_options(options)

        attr_defs.extend([
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.UILabelDef("Load Blend Options"),
            attribute_definitions.EnumDef(
                "import_method",
                items=[
                    ImportMethod.APPEND.value,
                    ImportMethod.LINK.value,
                    ImportMethod.OVERRIDE.value
                ],
                default=ImportMethod.APPEND.value,
                label="Import method",
            ),
            attribute_definitions.UISeparatorDef()
        ])
        return attr_defs

    def post_placeholder_process(self, placeholder, failed):
        """Add the placehodlers into a dedicated storage collection"""
        placeholder_coll = bpy.data.collections.get(AVALON_PLACEHOLDER)

        if not placeholder_coll:
            placeholder_coll = bpy.data.collections.new(name=AVALON_PLACEHOLDER)
            bpy.context.scene.collection.children.link(placeholder_coll)

        obj = bpy.data.objects.get(placeholder.scene_identifier)
        if not obj:
            save_file(current_file())
            return

        parent = get_parent_collections_for_object(obj)

        if not parent:
            bpy.context.scene.collection.objects.unlink(obj)
            placeholder_coll.objects.link(obj)
            save_file(current_file())
            return

        #Get first collection
        parent = parent[0]

        parent.objects.unlink(obj)
        placeholder_coll.objects.link(obj)

        save_file(current_file())

    def delete_placeholder(self, placeholder):
        """Remove placeholder if building was successful"""
        obj = bpy.data.objects.get(placeholder.scene_identifier)
        if not obj:
            raise ValueError("No object found for {}".format(placeholder.scene_identifier))
        bpy.data.objects.remove(obj, do_unlink=True)

        placeholder_coll = bpy.data.collections.get(AVALON_PLACEHOLDER)
        if not placeholder_coll:
            raise ValueError("No AVALON_PLACEHOLDER found")
        if len(placeholder_coll.objects) == 0:
            bpy.data.collections.remove(placeholder_coll, do_unlink=True)

        save_file(current_file())


class BlenderPlaceholderCreatePlugin(PlaceholderPlugin, PlaceholderCreateMixin):
    identifier = "blender.create"
    label = "Blender Create"

    def _collect_scene_placeholders(self):
        placeholder_nodes = self.builder.get_shared_populate_data(
            "placeholder_nodes"
        )
        if placeholder_nodes is None:
            empties = [obj for obj in bpy.data.objects if pipeline.get_avalon_node(obj).get("plugin_identifier", None)]
            placeholder_nodes = {}
            for empty in empties:
                node_name = empty.name
                placeholder_nodes[node_name] = (
                    self._parse_placeholder_node_data(empty)
                )

            self.builder.set_shared_populate_data(
                "placeholder_nodes", placeholder_nodes
            )
        return placeholder_nodes

    def _parse_placeholder_node_data(self, empty):
        placeholder_data = read(empty)
        parent_name = (
            empty.get("parent")
            or ""
        )

        placeholder_data.update({
            "parent": parent_name,
        })
        return placeholder_data

    def _create_placeholder_name(self, placeholder_data):
        placeholder_name_parts = placeholder_data["create"].split(".")
        pos = 1

        placeholder_variant = placeholder_data["create_variant"]
        if placeholder_variant:
            placeholder_name_parts.insert(pos, placeholder_variant)
            pos += 1

        placeholder_name = "_".join(placeholder_name_parts)

        return placeholder_name.capitalize()

    def create_placeholder(self, placeholder_data):
        bpy.ops.object.select_all(action='DESELECT')

        placeholder_data["plugin_identifier"] = self.identifier
        placeholder_name = self._create_placeholder_name(placeholder_data)

        instances = bpy.data.collections.get(pipeline.AVALON_INSTANCES)
        if not instances:
            instances = bpy.data.collections.new(name=pipeline.AVALON_INSTANCES)
            bpy.context.scene.collection.children.link(instances)

        placeholder = bpy.data.objects.new(name=placeholder_name, object_data=None)
        placeholder.empty_display_type = 'SINGLE_ARROW'

        if instances:
            instances.objects.link(placeholder)

        imprint(placeholder, placeholder_data)

    def update_placeholder(self, placeholder_item, placeholder_data):
        obj = bpy.data.objects.get(placeholder_item.scene_identifier)
        if not obj:
            raise ValueError("No objects found")

        new_values = {}
        for key, value in placeholder_data.items():
            placeholder_value = placeholder_item.data.get(key)
            if value != placeholder_value:
                new_values[key] = value
                placeholder_item.data[key] = value

        placeholder_name = self._create_placeholder_name(placeholder_data)
        obj.name = placeholder_name
        imprint(obj, new_values)

    def collect_placeholders(self):
        output = []
        scene_placeholders = self._collect_scene_placeholders()
        for obj_name, placeholder_data in scene_placeholders.items():
            if placeholder_data.get("plugin_identifier") != self.identifier:
                continue

            output.append(
                CreatePlaceholderItem(obj_name, placeholder_data, self)
            )

        return output

    def populate_placeholder(self, placeholder):
        self.populate_create_placeholder(placeholder, self._get_pre_create_data(placeholder))

    def repopulate_placeholder(self, placeholder):
        self.populate_create_placeholder(placeholder, self._get_pre_create_data(placeholder))

    @staticmethod
    def _get_pre_create_data(placeholder):
        return{
            "create_as_asset_group": placeholder.data.get("create_as_asset_group", False),
            "create_collection_hierarchy": placeholder.data.get("create_collection_hierarchy", False),
            "use_selection": placeholder.data.get("use_selection", False)
        }

    def get_placeholder_options(self, options=None):
        options = {"create_variant": "Main"}
        attr_defs = self.get_create_plugin_options(options)

        attr_defs.extend([
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.BoolDef(
                "create_as_asset_group",
                label="Use Empty as Instance",
                default=False
            ),
            attribute_definitions.BoolDef(
                "create_collection_hierarchy",
                label="Create Collection Hierarchy",
                default=True
            ),
            attribute_definitions.UISeparatorDef()
        ])
        return attr_defs

    def post_placeholder_process(self, placeholder, failed):
        """Add the placeholders into a dedicated storage collection"""
        placeholder_coll = bpy.data.collections.get(AVALON_PLACEHOLDER)
        if not placeholder_coll:
            placeholder_coll = bpy.data.collections.new(name=AVALON_PLACEHOLDER)
            bpy.context.scene.collection.children.link(placeholder_coll)

        obj = bpy.data.objects.get(placeholder.scene_identifier)
        if not obj:
            save_file(current_file())
            return

        parent = get_parent_collections_for_object(obj)
        if not parent:
            save_file(current_file())
            return

        parent.objects.unlink(obj)
        placeholder_coll.objects.link(obj)

        save_file(current_file())

    def delete_placeholder(self, placeholder):
        """Remove placeholder if building was successful"""
        obj = bpy.data.objects.get(placeholder.scene_identifier)
        if not obj:
            raise ValueError("No object found for {}".format(placeholder.scene_identifier))
        bpy.data.objects.remove(obj, do_unlink=True)

        placeholder_coll = bpy.data.collections.get(AVALON_PLACEHOLDER)
        if not placeholder_coll:
            raise ValueError("No AVALON_PLACEHOLDER found")
        if len(placeholder_coll.objects) == 0:
            bpy.data.collections.remove(placeholder_coll, do_unlink=True)

        save_file(current_file())

def build_workfile_template(*args):
    builder = BlenderTemplateBuilder(registered_host())
    builder.build_template()


def update_workfile_template(*args):
    builder = BlenderTemplateBuilder(registered_host())
    builder.rebuild_template()


def get_placeholder_to_update(*args):
    host = registered_host()
    builder = BlenderTemplateBuilder(host)
    placeholder_items_by_id = {
        placeholder_item.scene_identifier: placeholder_item
        for placeholder_item in builder.get_placeholders()
    }
    placeholder_items = []
    for obj in get_selection():
        if obj.name in placeholder_items_by_id:
            placeholder_items.append(placeholder_items_by_id[obj.name])

    # TODO show UI at least
    if len(placeholder_items) == 0:
        raise ValueError("No node selected")

    if len(placeholder_items) > 1:
        raise ValueError("Too many selected nodes")

    placeholder_item = placeholder_items[0]

    return placeholder_item
