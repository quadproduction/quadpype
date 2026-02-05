import os.path
import uuid
import hashlib
import math
from enum import Enum

from quadpype.pipeline import registered_host, Creator
from quadpype.tools.workfile_template_build import WorkfileBuildPlaceholderDialog
from quadpype.client import get_asset_by_name

from quadpype.lib import (
    attribute_definitions,
    StringTemplate
)

from quadpype.pipeline.workfile.workfile_template_builder import (
    AbstractTemplateBuilder,
    PlaceholderPlugin,
    LoadPlaceholderItem,
    CreatePlaceholderItem,
    PlaceholderLoadMixin,
    PlaceholderCreateMixin,
    should_apply_settings_on_build_first_workfile
)

from .lib import (
    get_layers_data,
    lock_layer,
    get_layer_position_and_size,
    get_project_size,
    transform_layer,
    execute_george_through_file,
    remove_layer,
    rename_layer,
    get_active_layer,
    get_layer_position,
    show_warning,
    set_layer_post_behavior,
    set_layer_position
)
from quadpype.hosts.tvpaint.api import pipeline


PLACEHOLDER_ID = "quadpype.placeholder"

class TextColor(Enum):
    RED = ([255, 0, 0], "Red")
    GREEN = ([0, 255, 0], "Green")
    BLUE = ([0, 0, 255], "Blue")
    YELLOW = ([255, 255, 0], "Yellow")
    ORANGE = ([255, 165, 0], "Orange")

    def __init__(self, rgb, label):
        self.rgb = rgb
        self.label = label

class PostBehavior(Enum):
    NONE = ("none", "None")
    REPEAT = ("repeat", "Repeat")
    PINGPONG = ("pingpong", "PingPong")
    HOLD = ("hold", "Hold")

    def __init__(self, behavior, label):
        self.behavior = behavior
        self.label = label

class TVPTemplateBuilder(AbstractTemplateBuilder):
    """Concrete implementation of AbstractTemplateBuilder for TVP"""

    def import_template(self, path):
        """Import template into current scene.

        Args:
            path (str): A path to current template (usually given by
            get_template_preset implementation)

        Returns:
            bool: Whether the template was successfully imported or not
        """

        for plugin in self.placeholder_plugins.values():
            plugin.update_all_placeholders_ids()

        if not os.path.exists(path):
            self.log.info(f"Template file on {path} doesn't exist.")
            return

        workfile_path = self.host.get_current_workfile()

        if not workfile_path:
            workfile_path = os.getenv("AVALON_LAST_WORKFILE")
            if not workfile_path:
                self.log.warning((
                    "Last workfile was not collected."
                    " Can't add it to launch arguments or determine if should"
                    " copy template."
                ))
                return False

        if os.path.exists(workfile_path) and self.compare_current_workfile_and_template(path, workfile_path):
            show_warning("V001 already exists, build abort.")
            return False

        if not os.path.exists(workfile_path):
            self.host.open_workfile(path)
            self.host.save_workfile(workfile_path)

        data = {
            'project_name': os.getenv("AVALON_PROJECT"),
            'asset_name': os.getenv("AVALON_ASSET"),
            'task_name': os.getenv("AVALON_TASK")
        }

        #Update context necessary
        pipeline.write_workfile_metadata(pipeline.SECTION_NAME_CONTEXT, data)
        self._current_asset_doc = get_asset_by_name(
                self.project_name, self.current_asset_name
            )

        if should_apply_settings_on_build_first_workfile():
            pipeline.set_context_settings(os.getenv("AVALON_PROJECT"), self._current_asset_doc, only_frame_range=True)

        return True

    def compare_current_workfile_and_template(self, template_path, workfile_path=None):
        if workfile_path is None:
            workfile_path = self.host.get_current_workfile()
            if not workfile_path:
                workfile_path = os.getenv("AVALON_LAST_WORKFILE")
                if not workfile_path:
                    self.log.warning((
                        "Last workfile was not collected."
                        " Can't add it to launch arguments or determine if should"
                        " copy template."
                    ))

        if not os.path.exists(workfile_path):
            return False

        if template_path == workfile_path:
            print ("Current file is template file, build abort.")
            return True

        if self.hash_file(template_path) != self.hash_file(workfile_path):
            print ("File already build, build abort.")
            return True

        return False

    @staticmethod
    def hash_file(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for bloc in iter(lambda: f.read(4096), b""):
                h.update(bloc)
        return h.hexdigest()

    def collect_placeholder_metadata(self):
        return pipeline.get_workfile_metadata(pipeline.SECTION_NAME_PLACEHOLDERS)


class TVPPlaceholderPlugin(PlaceholderPlugin):
    """Contains generic methods for all PlaceholderPlugins."""
    placeholder_name_template = "PH<_{builder_type}><_{family}><_{representation}><_{subset}><_{create}>"

    def collect_placeholders(self):
        """Collect info from file metadata about created placeholders.

        Returns:
            (list) (LoadPlaceholderItem)
        """
        output = []
        scene_placeholders = self._collect_scene_placeholders()
        for item in scene_placeholders:
            if item.get("plugin_identifier") != self.identifier:
                continue

            if isinstance(self, TVPPlaceholderLoadPlugin):
                item = LoadPlaceholderItem(item["uuid"],
                                           item["data"],
                                           self)
            elif isinstance(self, TVPPlaceholderCreatePlugin):
                item = CreatePlaceholderItem(item["uuid"],
                                             item["data"],
                                             self)
            else:
                raise NotImplementedError(f"Not implemented for {type(self)}")

            output.append(item)

        return output

    def update_placeholder(self, placeholder_item, placeholder_data):
        """Resave changed properties for placeholders"""
        item_id, metadata_item = self._get_item(placeholder_item)
        placeholder_name = StringTemplate.format_template(
            template=self.placeholder_name_template,
            data=placeholder_data,
        )

        if not item_id:
            show_warning("Cannot find item for "
                           f"{placeholder_item.scene_identifier}")
            return

        rename_layer(item_id, placeholder_name)
        metadata_item["data"] = placeholder_data
        self._imprint_item(item_id, placeholder_name, placeholder_data, refresh=True, metadata=metadata_item)

    def _get_item(self, placeholder_item):
        """Returns item id and item metadata for placeholder from file meta"""
        placeholder_uuid = placeholder_item.scene_identifier
        for metadata_item in self.collect_placeholder_metadata():
            if not metadata_item.get("is_placeholder"):
                continue
            if placeholder_uuid in metadata_item.get("uuid"):
                return metadata_item["members"][0], metadata_item
        return None, None

    def _collect_scene_placeholders(self):
        """Cache placeholder data to shared data.
        Returns:
            (list) of dicts
        """
        # Clean metadata
        self._unimprint_item()

        placeholder_items = self.builder.get_shared_populate_data(
            "placeholder_items"
        )
        if not placeholder_items:
            placeholder_items = []
            for item in self.collect_placeholder_metadata():
                if not item.get("is_placeholder"):
                    continue
                placeholder_items.append(item)

            self.builder.set_shared_populate_data(
                "placeholder_items", placeholder_items
            )
        return placeholder_items

    def collect_placeholder_metadata(self):
        return pipeline.get_workfile_metadata(pipeline.SECTION_NAME_PLACEHOLDERS)

    def update_all_placeholders_ids(self):
        self._unimprint_item()
        placeholder_metadata = self.collect_placeholder_metadata()
        layers_data = get_layers_data(only_names=True)
        layers_by_name = {layer_data["name"]: layer_data for layer_data in layers_data}
        for metadata in placeholder_metadata:
            new_id = layers_by_name.get(metadata["name"], {}).get("layer_id", None)
            self._imprint_item(new_id, metadata["name"], metadata["data"], refresh=True, metadata=metadata)

    def _imprint_item(self, item_id, name, placeholder_data, refresh=False, metadata=None):
        if refresh:
            self._unimprint_item(metadata)
        if not item_id:
            raise ValueError("Couldn't create a placeholder")
        current_placeholders = self.collect_placeholder_metadata()
        container_data = {
            "id": PLACEHOLDER_ID,
            "name": name,
            "is_placeholder": True,
            "plugin_identifier": self.identifier,
            "uuid": str(uuid.uuid4()),  # scene_identifier
            "data": placeholder_data,
            "members": [item_id]
        }
        current_placeholders.append(container_data)
        # Store data to metadata
        pipeline.write_workfile_metadata(pipeline.SECTION_NAME_PLACEHOLDERS, current_placeholders)

    def _unimprint_item(self, metadata=None):
        if metadata is None:
            metadata = dict()
        members = metadata.get("members", [])

        layers_data = get_layers_data(only_names=True)
        layers_by_name = [layer_data["name"] for layer_data in layers_data]
        current_placeholders = self.collect_placeholder_metadata()

        removed_placeholders = []
        for cur_ph in current_placeholders:
            cur_name = cur_ph["name"]
            if cur_name not in layers_by_name:
                removed_placeholders.append(cur_ph)

        for rem_ph in removed_placeholders:
            current_placeholders.remove(rem_ph)

        pop_idx = None

        for idx, cur_ph in enumerate(current_placeholders):
            cur_members = cur_ph["members"]
            if cur_members == members:
                pop_idx = idx
                break

        if pop_idx is None:
            self.log.warning(
                "Didn't find container in workfile metadata. {}".format(
                    metadata.get("name", "")
                )
            )

        else:
            current_placeholders.pop(pop_idx)

        pipeline.write_workfile_metadata(pipeline.SECTION_NAME_PLACEHOLDERS, current_placeholders)


class TVPPlaceholderCreatePlugin(TVPPlaceholderPlugin, PlaceholderCreateMixin):
    """Adds Create placeholder.
    """
    identifier = "tvpaint.create"
    label = "TvPaint create"

    def create_placeholder(self, placeholder_data):
        pass

    def populate_placeholder(self, placeholder):
        """Replace 'placeholder' with publishable instance."""
        pass

    def delete_placeholder(self, placeholder):
        pass

    def get_placeholder_options(self, options=None):
        if not options:
            options = {}
        options.update({"create_variant" : "Main"})
        attr_defs = self.get_create_plugin_options(options)
        attr_defs.append(attribute_definitions.UISeparatorDef())

        creators_by_name = self.builder.get_creators_by_name()
        for creator_name, creator in creators_by_name.items():
            if not hasattr(creator, "get_pre_create_attr_defs"):
                continue
            if not isinstance(creator, Creator):
                continue
            attr_defs.extend(creator.get_pre_create_attr_defs())

        attr_defs.extend([
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.UILabelDef("PlaceHolders Options"),
            attribute_definitions.EnumDef(
                "text_color",
                items=[
                    TextColor.RED.label,
                    TextColor.GREEN.label,
                    TextColor.BLUE.label,
                    TextColor.YELLOW.label,
                    TextColor.ORANGE.label,
                ],
                default=options.get("text_color", TextColor.RED.label),
                label="PlaceHolder Text Color",
            ),
            attribute_definitions.NumberDef(
                "text_size",
                label="PlaceHolder Text Size",
                minimum=24,
                maximum=500,
                default=options.get("text_size", 50)
            ),
            attribute_definitions.UISeparatorDef(),
        ])
        return attr_defs

    def update_all_placeholders_ids(self):
        pass

class TVPPlaceholderLoadPlugin(TVPPlaceholderPlugin, PlaceholderLoadMixin):
    identifier = "tvpaint.load"
    label = "TvPaint load"

    def create_placeholder(self, placeholder_data):
        """Creates TVP's Placeholder item in Project items list.
         """
        # Clean metadata
        self._unimprint_item()

        text_size = placeholder_data.get("text_size", 50)
        text_color = TextColor[placeholder_data.get("text_color", "Orange").upper()].rgb
        r, g, b = text_color
        placeholder_name = StringTemplate.format_template(
            template=self.placeholder_name_template,
            data=placeholder_data,
        )
        layer_name = placeholder_name

        current_placeholders = self.collect_placeholder_metadata()
        if any(item.get('data') == placeholder_data for item in current_placeholders):
            show_warning("PlaceHolder already exists with those options !")
            return

        add_placeholder(layer_name, text_size, r, g, b)

        loaded_layer = None
        layers = get_layers_data(only_names=True)
        for layer in layers:
            if layer["name"] == layer_name:
                loaded_layer = layer
                break

        if loaded_layer is None:
            show_warning(
                "Loading probably failed during execution of george script."
            )
        set_layer_post_behavior(
            loaded_layer["layer_id"],
            PostBehavior[placeholder_data.get("post_behavior", "None").upper()].behavior
        )
        self._imprint_item(loaded_layer["layer_id"], layer_name, placeholder_data)

    def populate_placeholder(self, placeholder):
        """Use QuadPype Loader from `placeholder`
        """
        # Clean metadata
        self._unimprint_item()
        self.populate_load_placeholder(placeholder)

    def delete_placeholder(self, placeholder):
        if not placeholder.data["keep_placeholder"]:
            metadata = self.collect_placeholder_metadata()
            layers_data = get_layers_data(only_names=True)
            layers_by_names = {layer_data["name"]: layer_data for layer_data in layers_data}
            for item in metadata:
                new_id = layers_by_names.get(item["name"], {}).get("layer_id", None)
                if not item.get("is_placeholder"):
                    continue
                scene_identifier = item.get("uuid")
                if (scene_identifier and
                        scene_identifier == placeholder.scene_identifier):
                    remove_layer(new_id)
                    self._unimprint_item(item)

    def get_placeholder_options(self, options=None):
        options = options or {}
        attr_defs =  self.get_load_plugin_options(options)
        attr_defs.extend([
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.UILabelDef("PlaceHolders Options"),
            attribute_definitions.EnumDef(
                "text_color",
                items=[
                    TextColor.RED.label,
                    TextColor.GREEN.label,
                    TextColor.BLUE.label,
                    TextColor.YELLOW.label,
                    TextColor.ORANGE.label,
                ],
                default=options.get("text_color", TextColor.ORANGE.label),
                label="PlaceHolder Text Color",
            ),
            attribute_definitions.NumberDef(
                "text_size",
                label="PlaceHolder Text Size",
                minimum=24,
                maximum=500,
                default=options.get("text_size", 50)
            ),
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.BoolDef(
                "move_loaded",
                label="Move loaded to PlaceHolder",
                default=options.get("move_loaded", False)
            ),
            attribute_definitions.BoolDef(
                "lock_loaded",
                label="Lock loaded",
                default=options.get("lock_loaded", False)
            ),
            attribute_definitions.NumberDef(
                "scale_loaded",
                label="Scale loaded in %",
                minimum=0,
                maximum=500,
                default=options.get("scale_loaded", 100)
            ),
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.EnumDef(
                "post_behavior",
                items=[
                    PostBehavior.NONE.label,
                    PostBehavior.REPEAT.label,
                    PostBehavior.PINGPONG.label,
                    PostBehavior.HOLD.label
                ],
                default=options.get("post_behavior", PostBehavior.NONE.label),
                label="Loaded Post Behavior",
            )
        ])
        return attr_defs

    def load_succeed(self, placeholder, container):
        placeholder_data = placeholder.data
        current_placeholders = self.collect_placeholder_metadata()
        placeholder_by_uuid = {placeholder_data["uuid"]: placeholder_data["name"] for placeholder_data in current_placeholders}
        placeholder_name = placeholder_by_uuid.get(placeholder._scene_identifier)

        layers_data = get_layers_data(only_names=True)
        layers_by_name = {layer_data["name"]: layer_data for layer_data in layers_data}
        new_id = layers_by_name.get(placeholder_name,{}).get("layer_id", None)

        width, height = get_project_size()
        position_x = math.ceil(width / 2)
        position_y = math.ceil(height / 2)

        layer_id = container["members_ids"][0]

        set_layer_post_behavior(
            layer_id,
            PostBehavior[placeholder_data.get("post_behavior", "None").upper()].behavior
        )

        placeholder_position = get_layer_position(new_id)
        set_layer_position(placeholder_position + 1)

        if not placeholder_data.get("move_loaded") and placeholder_data.get("scale_loaded", 100) == 100:
            if placeholder_data.get("lock_loaded"):
                lock_layer(layer_id)
            print(f"Load Succeed for {placeholder}, {container}")
            return True

        if placeholder_data.get("move_loaded"):
            x, y, width, height = get_layer_position_and_size(new_id)
            position_x = math.ceil(x + (width/2))
            position_y = math.ceil(y + (height/2))

        transform_layer(
            layer_id,
            placeholder_data.get("scale_loaded", 100),
            placeholder_data.get("scale_loaded", 100),
            position_x,
            position_y
        )
        if placeholder_data.get("lock_loaded"):
            lock_layer(layer_id)

        print(f"Load Succeed for {placeholder}, {container}")


def build_workfile_template(*args, **kwargs):
    host = registered_host()
    builder = TVPTemplateBuilder(registered_host())
    if builder.build_template(*args, **kwargs):
        host.save_workfile()

def update_workfile_template(*args):
    builder = TVPTemplateBuilder(registered_host())
    builder.rebuild_template()

def create_placeholder(*args):
    """Called when new workile placeholder should be created."""
    host = registered_host()
    builder = TVPTemplateBuilder(host)
    window = WorkfileBuildPlaceholderDialog(host, builder)

    window.show()
    window.raise_()
    window.activateWindow()

def update_placeholder(*args):
    """Called after placeholder item is selected to modify it."""
    host = registered_host()
    builder = TVPTemplateBuilder(host)

    for plugin in builder.placeholder_plugins.values():
        plugin.update_all_placeholders_ids()

    selected_id = get_active_layer()

    placeholder_item = None
    placeholder_items_by_id = {
        placeholder_item.scene_identifier: placeholder_item
        for placeholder_item in builder.get_placeholders()
    }

    placeholders_metadata = builder.collect_placeholder_metadata()

    for metadata_item in placeholders_metadata:
        if not metadata_item.get("is_placeholder"):
            continue

        if selected_id == metadata_item["members"][0]:
            placeholder_item = placeholder_items_by_id.get(
                metadata_item["uuid"])
            break

    if not placeholder_item:
        show_warning("Didn't find placeholder metadata."
                       "Select a placeHolder layer or"
                       "Remove and re-create placeholder")
        return

    window = WorkfileBuildPlaceholderDialog(host, builder)
    window.set_update_mode(placeholder_item)
    window.show()
    window.raise_()
    window.activateWindow()

def add_placeholder(text, size, r, g, b):
    """
    Génère un script George pour tracer du texte au centre du projet.
    Sauvegarde et restaure l'outil actif, la brush et la couleur APen.

    Args:
        text (str): Le texte à afficher
        size (int): La taille de la police
        r (int): Composante rouge (0-255)
        g (int): Composante verte (0-255)
        b (int): Composante bleue (0-255)

    """
    script = f"""
        tv_LayerCreate "{text}"
        tv_GetActiveTool
        backup_tool = result

        PARSE backup_tool tool_name rest

        tv_GetAPen
        backup_color = result

        tv_GetWidth
        project_width = result
        tv_GetHeight
        project_height = result

        center_x = project_width / 2
        center_y = project_height / 2

        tv_SetAPen {r} {g} {b}

        tv_TextTool2 "text" "{text}" "size" {size} "letter" 0 "power" 100 "opacity" 100

        tv_Dot center_x center_y 0

        tv_SetAPen backup_color

        tv_TextTool2 "reset"

        IF CMP(tool_name, "tv_penbrush") == 1
            tv_PenBrush "toolmode"
        END

        IF CMP(tool_name, "tv_airbrush") == 1
            tv_AirBrush "toolmode"
        END

        IF CMP(tool_name, "tv_oilbrush") == 1
            tv_OilBrush "toolmode"
        END

        IF CMP(tool_name, "tv_pencil") == 1
            tv_Pencil "toolmode"
        END

        IF CMP(tool_name, "tv_wetbrush") == 1
            tv_WetBrush "toolmode"
        END

        IF CMP(tool_name, "tv_eraserbrush") == 1
            tv_EraserBrush "toolmode"
        END

        IF CMP(tool_name, "tv_specialbrush") == 1
            tv_SpecialBrush "toolmode"
        END

        IF CMP(tool_name, "tv_brushrestore") == 1
            tv_BrushRestore "toolmode"
        END

        IF CMP(tool_name, "tv_propelling") == 1
            tv_Propelling "toolmode"
        END

        IF CMP(tool_name, "tv_speedfillbrush") == 1
            tv_SpeedFillBrush "toolmode"
        END

        IF CMP(tool_name, "tv_speedfilleraser") == 1
            tv_SpeedFillEraser "toolmode"
        END
        """

    return execute_george_through_file(script)
