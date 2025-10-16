import json
import os.path
import shutil
import platform
from enum import Enum
import bpy

from quadpype.pipeline import registered_host, Anatomy
from .workio import (
    current_file,
    save_file,
    open_file
)

from quadpype.pipeline.workfile.workfile_template_builder import (
    TemplateAlreadyImported,
    AbstractTemplateBuilder,
    TemplateProfileNotFound,
    TemplateLoadFailed,
    TemplateNotFound,
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
    get_parent_collections_for_object,
    purge_orphans
)

from quadpype.hosts.blender.api import pipeline

from quadpype.lib import (
    attribute_definitions,
    StringTemplate
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

        if not os.path.exists(path):
            self.log.info(f"Template file on {path} doesn't exist.")
            return

        for scene in bpy.data.scenes:
            if scene.name == self.current_asset_name:
                raise TemplateAlreadyImported((
                    "Build template already loaded\n"
                    "Clean scene if needed (File > New Scene)"
                ))

        workfile_path = save_file(current_file())
        shutil.copy2(path, workfile_path)
        open_file(workfile_path)

        bpy.context.scene.name = self.current_asset_name

        purge_orphans(is_recursive=True)

        if should_apply_settings_on_build_first_workfile():
            self._set_settings()

        save_file(current_file())
        return True

    @staticmethod
    def _set_settings():
        data = pipeline.get_asset_data()
        pipeline.set_resolution(data)
        pipeline.set_frame_range(data)

    def get_render_settings_template_preset(self):

        host_name = self.host_name
        project_name = self.project_name
        task_name = self.current_task_name
        task_type = self.current_task_type

        settings_templates = (
            self.project_settings
            [self.host_name]
            ["RenderSettings"]
            ["render_settings_template"]
            ["template_path"]
        )
        template = settings_templates[platform.system().lower()]

        if not template:
            raise TemplateLoadFailed((
                                         "Template path is not set.\n"
                                         "Path need to be set in {}\\Render Settings Template "
                                         "Settings\\Profiles"
                                     ).format(host_name.title()))

        # Try to fill path with environments and anatomy roots
        anatomy = Anatomy(project_name)
        fill_data = {
            key: value
            for key, value in os.environ.items()
        }

        fill_data["root"] = anatomy.roots
        fill_data["project"] = {
            "name": project_name,
            "code": anatomy.project_code,
        }
        fill_data["task"] = {
            "type": task_type,
            "name": task_name,
        }
        result = StringTemplate.format_template(template, fill_data)
        if result.solved:
            template = result.normalized()

        if template and os.path.exists(template):
            self.log.info("Found template at: '{}'".format(template))
            return template

        solved_path = None
        while True:
            try:
                solved_path = anatomy.path_remapper(template)
            except KeyError as missing_key:
                raise KeyError(
                    "Could not solve key '{}' in template path '{}'".format(
                        missing_key, template))

            if solved_path is None:
                solved_path = template
            if solved_path == template:
                break
            template = solved_path

        solved_path = os.path.normpath(solved_path)
        if not os.path.exists(solved_path):
            raise TemplateNotFound(
                "Template found in QuadPype settings for task '{}' with host "
                "'{}' does not exists. (Not found : {})".format(
                    task_name, host_name, solved_path))

        self.log.info("Found template at: '{}'".format(solved_path))

        return solved_path

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

        parents = get_parent_collections_for_object(obj)

        if not parents:
            bpy.context.scene.collection.objects.unlink(obj)
            placeholder_coll.objects.link(obj)
            save_file(current_file())
            return

        parent = next(iter(parents))

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

        parents = get_parent_collections_for_object(obj)
        if not parents:
            save_file(current_file())
            return

        parent = next(iter(parents))

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
