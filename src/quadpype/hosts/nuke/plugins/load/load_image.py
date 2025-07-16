import nuke
import ast
import qargparse
from quadpype.lib.attribute_definitions import (
    BoolDef,
    NumberDef
)

from quadpype.client import (
    get_version_by_id,
    get_last_version_by_subset_id,
)
from quadpype.lib import Logger
from quadpype.pipeline import (
    load,
    get_current_project_name,
    get_representation_path,
    get_current_host_name,
    get_task_hierarchy_templates,
    get_resolved_name,
    format_data,
    split_hierarchy
)
from quadpype.hosts.nuke.api.lib import (
    get_imageio_input_colorspace,
    get_layers,
    compare_layers,
    PREP_LAYER_PSD_EXT,
    PREP_LAYER_EXR_EXT
)
from quadpype.hosts.nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop
)
from quadpype.hosts.nuke.api.backdrops import (
    pre_organize_by_backdrop,
    organize_by_backdrop,
    reorganize_inside_main_backdrop,
    update_by_backdrop,
    get_nodes_in_backdrops
)
from quadpype.lib.transcoding import (
    IMAGE_EXTENSIONS
)
from quadpype.hosts.nuke.api import plugin

from src.quadpype.pipeline.editorial import frames_to_seconds

class LoadImage(plugin.NukeLoader):
    """Load still image into Nuke"""
    log = Logger.get_logger(__name__)
    families = [
        "render2d",
        "source",
        "plate",
        "render",
        "prerender",
        "review",
        "image"
    ]
    representations = ["*"]
    extensions = set(
        ext.lstrip(".") for ext in IMAGE_EXTENSIONS
    )

    label = "Load Image"
    order = -10
    icon = "image"
    color = "white"

    # Loaded from settings
    _representations = []

    node_name_template = "{class_name}_{ext}"
    defaults = {
        "prep_layers": True,
        "create_stamps": True,
        "pre_comp": True,
        "frame_number":{
            "minimum":0,
            "maximum":99999,
            "decimals":0
        }
    }

    @classmethod
    def get_representations(cls):
        return cls._representations or cls.representations

    @classmethod
    def get_options(cls, contexts):
        return [
            NumberDef(
                "frame_number",
                label="Frame Number",
                default=int(nuke.root()["first_frame"].getValue()),
                minimum=1,
                maximum=999999
            ),
            BoolDef(
                "prep_layers",
                label="Decompose Layers",
                default=cls.defaults["prep_layers"],
                tooltip="Separate each layer in shuffle nodes"
            ),
            BoolDef(
                "create_stamps",
                label="Create Stamps",
                default=cls.defaults["create_stamps"],
                tooltip="Create a stamp for each created nodes"
            ),
            BoolDef(
                "pre_comp",
                label="Create PreComp",
                default=cls.defaults["pre_comp"],
                tooltip="Generate the merge tree for generated nodes"
            )
        ]

    def load(self, context, name, namespace, options):
        self.reset_container_id()
        self.log.info("__ options: `{}`".format(options))
        frame_number = options.get("frame_number", int(nuke.root()["first_frame"].getValue()))
        prep_layers = options.get("prep_layers", True)
        create_stamps = options.get("create_stamps", True)
        pre_comp = options.get("pre_comp", True)
        ext = context["representation"]["context"]["ext"].lower()
        is_prep_layer_compatible = ext in (set(PREP_LAYER_PSD_EXT) | set(PREP_LAYER_EXR_EXT))
        if ext in PREP_LAYER_EXR_EXT:
            pre_comp = False
        if not options:
            options = {"frame_number":frame_number,
                       "prep_layers":prep_layers,
                       "create_stamps":create_stamps,
                       "pre_comp":pre_comp,
                       "is_prep_layer_compatible":is_prep_layer_compatible,
                       "ext":ext}

        version = context['version']
        version_data = version.get("data", {})
        project_name = get_current_project_name()
        version_doc = get_version_by_id(project_name, context["representation"]["parent"])
        last_version_doc = get_last_version_by_subset_id(
            project_name, version_doc["parent"], fields=["_id"]
        )
        repr_id = context["representation"]["_id"]

        self.log.info("version_data: {}\n".format(version_data))
        self.log.debug(
            "Representation id `{}` ".format(repr_id))

        last = first = int(frame_number)

        # Fallback to asset name when namespace is None
        if namespace is None:
            namespace = context['asset']['name']

        file = self.filepath_from_context(context)

        if not file:
            repr_id = context["representation"]["_id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repr_id))
            return

        file = file.replace("\\", "/")

        representation = context["representation"]

        repr_cont = representation["context"]
        frame = repr_cont.get("frame")
        if frame:
            padding = len(frame)
            file = file.replace(
                frame,
                format(frame_number, "0{}".format(padding)))

        read_name = self._get_node_name(representation)

        # Create the Loader with the filename path set
        with viewer_update_and_undo_stop():

            nodes_in_main_backdrops = pre_organize_by_backdrop()

            r = nuke.createNode(
                "Read",
                "name {}".format(read_name),
                inpanel=False
            )
            r["file"].setValue(file)
            r["xpos"].setValue(-100000)
            r["ypos"].setValue(-100000)
            # Set colorspace defined in version data
            colorspace = context["version"]["data"].get("colorspace")
            if colorspace:
                r["colorspace"].setValue(str(colorspace))

            preset_clrsp = get_imageio_input_colorspace(file)

            if preset_clrsp is not None:
                r["colorspace"].setValue(preset_clrsp)

            r["origfirst"].setValue(first)
            r["first"].setValue(first)
            r["origlast"].setValue(last)
            r["last"].setValue(last)

            # add additional metadata from the version to imprint Avalon knob
            add_keys = ["source", "colorspace", "author", "fps", "version"]

            data_imprint = {
                "frameStart": first,
                "frameEnd": last
            }
            for k in add_keys:
                if k == 'version':
                    data_imprint.update({k: context["version"]['name']})
                else:
                    data_imprint.update(
                        {k: context["version"]['data'].get(k, str(None))})

            r["tile_color"].setValue(int("0x4ecd25ff", 16))

            main_backdrop, storage_backdrop, nodes = organize_by_backdrop(context=context,
                                                                   read_node=r,
                                                                   nodes_in_main_backdrops=nodes_in_main_backdrops,
                                                                   options=options)

            if storage_backdrop:
                data_imprint["storage_backdrop"] = storage_backdrop['name'].value()
                data_imprint["main_backdrop"] = main_backdrop['name'].value()
                self.set_as_member(storage_backdrop)
                for n in nodes:
                    self.set_as_member(n)
            else:
                self.set_as_member(r)

            self.log.info("__ options: `{}`".format(options))
            data_imprint["options"] = options

            # change color of node
            if version_doc["_id"] == last_version_doc["_id"]:
                color_value = "0x4ecd25ff"
            else:
                color_value = "0xd84f20ff"
            r["tile_color"].setValue(int(color_value, 16))

            return containerise(r,
                                name=name,
                                namespace=namespace,
                                context=context,
                                loader=self.__class__.__name__,
                                data=data_imprint)

    def switch(self, container, representation):
        self.update(container, representation)

    def update(self, container, representation, ask_proceed=True):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """
        node = container["node"]
        frame_number = node["first"].value()

        assert node.Class() == "Read", "Must be Read"

        repr_cont = representation["context"]
        old_file = node["file"].value()
        file = get_representation_path(representation)

        if not file:
            repr_id = representation["_id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repr_id))
            return

        file = file.replace("\\", "/")

        frame = repr_cont.get("frame")
        if frame:
            padding = len(frame)
            file = file.replace(
                frame,
                format(frame_number, "0{}".format(padding)))

        # Get start frame from version data
        project_name = get_current_project_name()
        version_doc = get_version_by_id(project_name, representation["parent"])
        last_version_doc = get_last_version_by_subset_id(
            project_name, version_doc["parent"], fields=["_id"]
        )

        version_data = version_doc.get("data", {})

        last = first = int(frame_number)

        options = ast.literal_eval(container.get("options"))
        prep_layers = options.get("prep_layers", False)
        is_prep_layer_compatible = options.get("is_prep_layer_compatible", False)
        ext = options.get("ext", None)
        old_layers = dict()
        new_layers = dict()
        if is_prep_layer_compatible:
            old_layers = get_layers(node, ext)
            node["file"].setValue(file)
            new_layers = get_layers(node, ext)

            if prep_layers:
                if not compare_layers(old_layers, new_layers, ask_proceed=ask_proceed):
                    node["file"].setValue(old_file)
                    return

        # Set the global in to the start frame of the sequence
        read_name = self._get_node_name(representation)
        node["name"].setValue(read_name)
        node["origfirst"].setValue(first)
        node["first"].setValue(first)
        node["origlast"].setValue(last)
        node["last"].setValue(last)

        update_by_backdrop(container, old_layers, new_layers, ask_proceed=False)

        updated_dict = {}
        updated_dict.update({
            "representation": str(representation["_id"]),
            "frameStart": str(first),
            "frameEnd": str(last),
            "version": str(version_doc.get("name")),
            "colorspace": version_data.get("colorspace"),
            "source": version_data.get("source"),
            "fps": str(version_data.get("fps")),
            "author": version_data.get("author")
        })

        # change color of node
        if version_doc["_id"] == last_version_doc["_id"]:
            color_value = "0x4ecd25ff"
        else:
            color_value = "0xd84f20ff"
        node["tile_color"].setValue(int(color_value, 16))

        # Update the imprinted representation
        update_container(
            node,
            updated_dict
        )
        self.log.info("updated to version: {}".format(version_doc.get("name")))

    def remove(self, container):
        node = container["node"]
        assert node.Class() == "Read", "Must be Read"
        storage_backdrop = nuke.toNode(container["storage_backdrop"])

        main_backdrop = container["main_backdrop"]
        with viewer_update_and_undo_stop():
            members = [node for node in get_nodes_in_backdrops(storage_backdrop)]
            nuke.delete(storage_backdrop)
            for member in members:
                nuke.delete(member)
            if main_backdrop:
                reorganize_inside_main_backdrop(main_backdrop)

    def _get_node_name(self, representation):

        repre_cont = representation["context"]
        name_data = {
            "asset": repre_cont["asset"],
            "subset": repre_cont["subset"],
            "representation": representation["name"],
            "ext": repre_cont["representation"].lower(),
            "id": representation["_id"],
            "class_name": self.__class__.__name__
        }

        return self.node_name_template.format(**name_data)
