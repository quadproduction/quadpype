import os.path
import uuid
import shutil
from enum import Enum

from quadpype.pipeline import registered_host, Creator
from quadpype.tools.workfile_template_build import WorkfileBuildPlaceholderDialog

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
    PlaceholderCreateMixin
)

from .launch_logic import stub as get_stub

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

class PSTemplateBuilder(AbstractTemplateBuilder):
    """Concrete implementation of AbstractTemplateBuilder for PS"""

    def import_template(self, path):
        """Import template into current scene.

        Args:
            path (str): A path to current template (usually given by
            get_template_preset implementation)

        Returns:
            bool: Whether the template was successfully imported or not
        """
        stub = get_stub()
        if not os.path.exists(path):
            stub.print_msg(f"Template file on {path} doesn't exist.")
            return

        stub.save()
        workfile_path = stub.get_active_document_full_name()

        if workfile_path == 'null':
            workfile_path = os.getenv("AVALON_LAST_WORKFILE")
            if not workfile_path:
                self.log.warning((
                    "Last workfile was not collected."
                    " Can't add it to launch arguments or determine if should"
                    " copy template."
                ))
                return

        shutil.copy2(path, workfile_path)
        stub.open(workfile_path)

        return True


class PSPlaceholderPlugin(PlaceholderPlugin):
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

            if isinstance(self, PSPlaceholderLoadPlugin):
                item = LoadPlaceholderItem(item["uuid"],
                                           item["data"],
                                           self)
            elif isinstance(self, PSPlaceholderCreatePlugin):
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
        stub = get_stub()
        if not item_id:
            stub.print_msg("Cannot find item for "
                           f"{placeholder_item.scene_identifier}")
            return
        stub.rename_layer(item_id, placeholder_name)
        stub.set_layer_text(item_id, placeholder_name)
        metadata_item["data"] = placeholder_data
        stub.imprint(item_id, metadata_item)

    def _get_item(self, placeholder_item):
        """Returns item id and item metadata for placeholder from file meta"""
        stub = get_stub()
        placeholder_uuid = placeholder_item.scene_identifier
        for metadata_item in stub.get_layers_metadata():
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
        placeholder_items = self.builder.get_shared_populate_data(
            "placeholder_items"
        )
        if not placeholder_items:
            placeholder_items = []
            for item in get_stub().get_layers_metadata():
                if not item.get("is_placeholder"):
                    continue
                placeholder_items.append(item)

            self.builder.set_shared_populate_data(
                "placeholder_items", placeholder_items
            )
        return placeholder_items

    def _imprint_item(self, item_id, name, placeholder_data, stub):
        if not item_id:
            raise ValueError("Couldn't create a placeholder")
        container_data = {
            "id": PLACEHOLDER_ID,
            "name": name,
            "is_placeholder": True,
            "plugin_identifier": self.identifier,
            "uuid": str(uuid.uuid4()),  # scene_identifier
            "data": placeholder_data,
            "members": [item_id]
        }
        stub.imprint(item_id, container_data)


class PSPlaceholderCreatePlugin(PSPlaceholderPlugin, PlaceholderCreateMixin):
    """Adds Create placeholder.
    """
    identifier = "photoshop.create"
    label = "Photoshop create"

    def create_placeholder(self, placeholder_data):
        text_size = placeholder_data.get("text_size", 50)
        text_color = TextColor[placeholder_data.get("text_color", "Orange").upper()].rgb
        r, g, b = text_color
        placeholder_name = StringTemplate.format_template(
            template=self.placeholder_name_template,
            data=placeholder_data,
        )
        stub = get_stub()
        name = placeholder_name

        placeholder_layer = stub.add_placeholder(name, text_size, r, g, b)

        self._imprint_item(placeholder_layer.id, name, placeholder_data, stub)

    def populate_placeholder(self, placeholder):
        """Replace 'placeholder' with publishable instance."""
        stub = get_stub()
        stub.create_group("Dummy")
        self.populate_create_placeholder(placeholder, placeholder.data)

    def delete_placeholder(self, placeholder):
        stub = get_stub()
        if not placeholder.data["keep_placeholder"]:
            metadata = stub.get_layers_metadata()
            for item in metadata:
                if not item.get("is_placeholder"):
                    continue
                scene_identifier = item.get("uuid")
                if (scene_identifier and
                        scene_identifier == placeholder.scene_identifier):
                    stub.delete_layer(item["members"][0])
            stub.remove_instance(placeholder.scene_identifier)

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
                default=TextColor.RED.label,
                label="PlaceHolder Text Color",
            ),
            attribute_definitions.NumberDef(
                "text_size",
                label="PlaceHolder Text Size",
                minimum=24,
                maximum=500,
                default=50
            ),
            attribute_definitions.UISeparatorDef(),
        ])
        return attr_defs


class PSPlaceholderLoadPlugin(PSPlaceholderPlugin, PlaceholderLoadMixin):
    identifier = "photoshop.load"
    label = "Photoshop load"

    def create_placeholder(self, placeholder_data):
        """Creates PS's Placeholder item in Project items list.
         """

        text_size = placeholder_data.get("text_size", 50)
        text_color = TextColor[placeholder_data.get("text_color", "Orange").upper()].rgb
        r, g, b = text_color
        placeholder_name = StringTemplate.format_template(
            template=self.placeholder_name_template,
            data=placeholder_data,
        )
        stub = get_stub()
        name = placeholder_name

        placeholder_layer = stub.add_placeholder(name, text_size, r, g, b)

        self._imprint_item(placeholder_layer.id, name, placeholder_data, stub)


    def populate_placeholder(self, placeholder):
        """Use QuadPype Loader from `placeholder`
        """
        self.populate_load_placeholder(placeholder)

    def delete_placeholder(self, placeholder):
        stub = get_stub()
        if not placeholder.data["keep_placeholder"]:
            metadata = stub.get_layers_metadata()
            for item in metadata:
                if not item.get("is_placeholder"):
                    continue
                scene_identifier = item.get("uuid")
                if (scene_identifier and
                        scene_identifier == placeholder.scene_identifier):
                    stub.delete_layer(item["members"][0])
            stub.remove_instance(placeholder.scene_identifier)

    def get_placeholder_options(self, options=None):
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
                default=TextColor.ORANGE.label,
                label="PlaceHolder Text Color",
            ),
            attribute_definitions.NumberDef(
                "text_size",
                label="PlaceHolder Text Size",
                minimum=24,
                maximum=500,
                default=50
            ),
            attribute_definitions.UISeparatorDef(),
            attribute_definitions.BoolDef(
                "move_loaded",
                label="Move loaded to PlaceHolder",
                default=True
            ),
            attribute_definitions.NumberDef(
                "scale_loaded",
                label="Scale loaded in %",
                minimum=0,
                maximum=500,
                default=100
            ),
            attribute_definitions.UISeparatorDef()
        ])
        return attr_defs

    def load_succeed(self, placeholder, container):
        stub = get_stub()
        placeholder_layer = None
        for item in get_stub().get_layers_metadata():
            if not item.get("is_placeholder"):
                continue
            if placeholder.scene_identifier == item.get("uuid"):
                placeholder_layer = stub.get_layer(item["members"][0])
                break

        placeholder_data = placeholder.data
        if placeholder_data.get("move_loaded"):
            stub.move_layer_to_text_position(placeholder_layer.id, container.id)
        stub.scale_layer_by_id(container.id, placeholder_data.get("scale_loaded", 100))
        print(f"Load Succeed for {placeholder}, {container}")


def build_workfile_template(*args, **kwargs):
    builder = PSTemplateBuilder(registered_host())
    builder.build_template(*args, **kwargs)
    get_stub().save()


def update_workfile_template(*args):
    builder = PSTemplateBuilder(registered_host())
    builder.rebuild_template()


def create_placeholder(*args):
    """Called when new workile placeholder should be created."""
    host = registered_host()
    builder = PSTemplateBuilder(host)
    window = WorkfileBuildPlaceholderDialog(host, builder)
    window.exec_()


def update_placeholder(*args):
    """Called after placeholder item is selected to modify it."""
    host = registered_host()
    builder = PSTemplateBuilder(host)

    stub = get_stub()
    selected_items = stub.get_selected_layers()

    if len(selected_items) != 1:
        stub.print_msg("Please select just 1 placeholder")
        return

    selected_id = str(selected_items[0].id)
    placeholder_item = None
    placeholder_items_by_id = {
        placeholder_item.scene_identifier: placeholder_item
        for placeholder_item in builder.get_placeholders()
    }

    for metadata_item in stub.get_layers_metadata():
        if not metadata_item.get("is_placeholder"):
            continue

        if selected_id in metadata_item.get("members"):
            placeholder_item = placeholder_items_by_id.get(
                metadata_item["uuid"])
            break

    if not placeholder_item:
        stub.print_msg("Didn't find placeholder metadata. "
                       "Remove and re-create placeholder.")
        return

    window = WorkfileBuildPlaceholderDialog(host, builder)
    window.set_update_mode(placeholder_item)
    window.exec_()
