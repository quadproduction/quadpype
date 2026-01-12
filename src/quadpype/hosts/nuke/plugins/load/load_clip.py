import nuke
import ast
from pprint import pformat
from copy import deepcopy
from quadpype.lib import Logger
from quadpype.client import (
    get_version_by_id,
    get_last_version_by_subset_id,
)
from quadpype.pipeline import (
    get_current_project_name,
    get_representation_path,
)
from quadpype.settings import get_project_settings
from quadpype.lib.attribute_definitions import (
    BoolDef,
    NumberDef
)
from quadpype.pipeline.workfile.workfile_template_builder import (
    TemplateProfileNotFound
)
from quadpype.pipeline.colorspace import (
    get_imageio_file_rules_colorspace_from_filepath
)
from quadpype.hosts.nuke.api.lib import (
    get_imageio_input_colorspace,
    maintained_selection,
    get_layers,
    compare_layers,
    get_unique_name_and_number,
    PREP_LAYER_PSD_EXT,
    PREP_LAYER_EXR_EXT
)
from quadpype.hosts.nuke.api.backdrops import (
    pre_organize_by_backdrop,
    organize_by_backdrop,
    reorganize_inside_main_backdrop,
    update_by_backdrop,
    get_nodes_in_backdrops
)
from quadpype.hosts.nuke.api.constants import (
    COLOR_GREEN,
    COLOR_RED
)
from quadpype.hosts.nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop,
    colorspace_exists_on_node
)
from quadpype.lib.transcoding import (
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS
)
from quadpype.hosts.nuke.api import plugin


class LoadClip(plugin.NukeLoader):
    """Load clip into Nuke

    Either it is image sequence or video file.
    """
    log = Logger.get_logger(__name__)

    families = [
        "source",
        "plate",
        "render",
        "prerender",
        "review"
    ]
    representations = ["*"]
    extensions = set(
        ext.lstrip(".") for ext in IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)
    )

    label = "Load Clip"
    order = -20
    icon = "file-video-o"
    color = "white"

    # Loaded from settings
    _representations = []

    script_start = int(nuke.root()["first_frame"].value())

    node_name_template = "{class_name}_{ext}"
    # option gui
    defaults = {
        "start_at_workfile": True,
        "add_retime": True,
        "prep_layers": True,
        "create_stamps": True,
        "pre_comp": False
    }

    @classmethod
    def get_options(cls, *args):
        return [
            BoolDef(
                "start_at_workfile",
                label="Start at Workfile",
                tooltip="Load at workfile start frame",
                default=cls.defaults["start_at_workfile"]
            ),
            BoolDef(
                "add_retime",
                label="Add Retime",
                tooltip="Load with retime",
                default=cls.defaults["add_retime"]
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

    @classmethod
    def get_representations(cls):
        return cls._representations or cls.representations

    def load(self, context, name, namespace, options):
        """Load asset via database
        """
        settings = get_project_settings(get_current_project_name()).get("nuke")
        use_backdrop = settings["general"].get("use_backdrop_loader_creator", True)

        representation = context["representation"]
        # reset container id so it is always unique for each instance
        self.reset_container_id()

        is_sequence = len(representation["files"]) > 1

        if is_sequence:
            context["representation"] = \
                self._representation_with_hash_in_frame(
                    representation
            )

        filepath = self.filepath_from_context(context)
        filepath = filepath.replace("\\", "/")

        start_at_workfile = options.get("start_at_workfile", self.defaults["start_at_workfile"])
        add_retime = options.get("add_retime", self.defaults["add_retime"])
        ext = context["representation"]["context"]["ext"].lower()
        pre_comp = options.get("pre_comp", self.defaults["pre_comp"])

        if ext in PREP_LAYER_EXR_EXT:
            pre_comp = False
        if not options:
            options = {}

        options["start_at_workfile"] = start_at_workfile
        options["add_retime"] = add_retime
        options["prep_layers"] = options.get("prep_layers", self.defaults["prep_layers"])
        options["create_stamps"] = options.get("create_stamps", self.defaults["create_stamps"])
        options["pre_comp"] = pre_comp
        options["is_prep_layer_compatible"] = ext in (set(PREP_LAYER_PSD_EXT) | set(PREP_LAYER_EXR_EXT))
        options["ext"] = ext
        options["subset_group"] = context["subset"]["data"].get("subsetGroup")

        version = context['version']
        version_data = version.get("data", {})
        repre_id = representation["_id"]
        project_name = get_current_project_name()
        version_doc = get_version_by_id(project_name, context["representation"]["parent"])
        last_version_doc = get_last_version_by_subset_id(
            project_name, version_doc["parent"], fields=["_id"]
        )

        self.log.debug("_ version_data: {}\n".format(
            pformat(version_data)))
        self.log.debug(
            "Representation id `{}` ".format(repre_id))

        self.handle_start = version_data.get("handleStart", 0)
        self.handle_end = version_data.get("handleEnd", 0)

        first = version_data.get("frameStart", None)
        last = version_data.get("frameEnd", None)
        first -= self.handle_start
        last += self.handle_end

        if not is_sequence:
            duration = last - first
            first = 1
            last = first + duration

        # Fallback to asset name when namespace is None
        if namespace is None:
            namespace = context['asset']['name']

        if not filepath:
            self.log.warning(
                "Representation id `{}` is failing to load".format(repre_id))
            return

        # Get unique name
        read_name, unique_number = get_unique_name_and_number(representation=representation,
                                                              template=self.node_name_template,
                                                              unique_number=None,
                                                              node_type="Read",
                                                              class_name = self.__class__.__name__)

        # Create the Loader with the filename path set
        read_node = nuke.createNode(
            "Read",
            "name {}".format(read_name),
            inpanel=False
        )

        # to avoid multiple undo steps for rest of process
        # we will switch off undo-ing
        with viewer_update_and_undo_stop():
            if use_backdrop:
                nodes_in_main_backdrops = pre_organize_by_backdrop()

            read_node["file"].setValue(filepath)

            if use_backdrop:
                read_node["xpos"].setValue(-100000)
                read_node["ypos"].setValue(-100000)

            self.set_colorspace_to_node(
                read_node, filepath, version, representation)

            self._set_range_to_node(read_node, first, last, start_at_workfile)

            # add additional metadata from the version to imprint Avalon knob
            add_keys = ["frameStart", "frameEnd",
                        "source", "colorspace", "author", "fps", "version",
                        "handleStart", "handleEnd"]

            data_imprint = {}
            for key in add_keys:
                if key == 'version':
                    version_doc = context["version"]
                    if version_doc["type"] == "hero_version":
                        version = "hero"
                    else:
                        version = version_doc.get("name")

                    if version:
                        data_imprint[key] = version

                elif key == 'colorspace':
                    colorspace = representation["data"].get(key)
                    colorspace = colorspace or version_data.get(key)
                    data_imprint["db_colorspace"] = colorspace
                else:
                    value_ = context["version"]['data'].get(
                        key, str(None))
                    if isinstance(value_, (str)):
                        value_ = value_.replace("\\", "/")
                    data_imprint[key] = value_

            if add_retime and version_data.get("retime", None):
                data_imprint["addRetime"] = True

            read_node["tile_color"].setValue(int(COLOR_GREEN, 16))
            storage_backdrop = None
            if use_backdrop:
                try:
                    nodes_before = list(nuke.allNodes())
                    main_backdrop, storage_backdrop, subset_group, nodes = organize_by_backdrop(
                        data=context,
                        node=read_node,
                        nodes_in_main_backdrops=nodes_in_main_backdrops,
                        options=options,
                        unique_number=unique_number
                    )
                except TemplateProfileNotFound:
                    for n in nuke.allNodes():
                        if n not in nodes_before:
                            nuke.delete(n)
                    nuke.delete(read_node)
                    raise Exception(f"No template found in loader for "
                                    f"{context['representation']['context']['task']['name']}")

            if add_retime and version_data.get("retime", None):
                self._make_retimes(read_node, version_data)

            if subset_group:
                data_imprint["subset_group"] = subset_group

            if storage_backdrop:
                data_imprint["storage_backdrop"] = storage_backdrop['name'].value()
                data_imprint["main_backdrop"] = main_backdrop['name'].value()
                self.set_as_member(storage_backdrop)
                for n in nodes:
                    self.set_as_member(n)
            else:
                self.set_as_member(read_node)

            self.log.info("__ options: `{}`".format(options))
            data_imprint["options"] = options
            self.log.info("__ unique_number: `{}`".format(unique_number))
            data_imprint["unique_number"] = unique_number

            container = containerise(
                read_node,
                name=name,
                namespace=namespace,
                context=context,
                loader=self.__class__.__name__,
                data=data_imprint)

        # change color of node
        if version_doc["_id"] == last_version_doc["_id"]:
            color_value = COLOR_GREEN
        else:
            color_value = COLOR_RED
        read_node["tile_color"].setValue(int(color_value, 16))

        return container

    def switch(self, container, representation):
        self.update(container, representation)

    def _representation_with_hash_in_frame(self, representation):
        """Convert frame key value to padded hash

        Args:
            representation (dict): representation data

        Returns:
            dict: altered representation data
        """
        representation = deepcopy(representation)
        context = representation["context"]

        # Get the frame from the context and hash it
        frame = context["frame"]
        hashed_frame = "#" * len(str(frame))

        # Replace the frame with the hash in the originalBasename
        if (
            "{originalBasename}" in representation["data"]["template"]
        ):
            origin_basename = context["originalBasename"]
            context["originalBasename"] = origin_basename.replace(
                frame, hashed_frame
            )

        # Replace the frame with the hash in the frame
        representation["context"]["frame"] = hashed_frame
        return representation

    def update(self, container, representation, ask_proceed=True):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """
        settings = get_project_settings(get_current_project_name()).get("nuke")
        use_backdrop = settings["general"].get("use_backdrop_loader_creator", True)

        is_sequence = len(representation["files"]) > 1

        read_node = container["node"]
        old_file = read_node["file"].value()

        if is_sequence:
            representation = self._representation_with_hash_in_frame(
                representation
            )

        filepath = get_representation_path(representation).replace("\\", "/")
        self.log.debug("_ filepath: {}".format(filepath))

        start_at_workfile = "start at" in read_node['frame_mode'].value()

        add_retime = [
            key for key in read_node.knobs().keys()
            if "addRetime" in key
        ]

        project_name = get_current_project_name()
        version_doc = get_version_by_id(project_name, representation["parent"])

        version_data = version_doc.get("data", {})
        repre_id = representation["_id"]

        # colorspace profile
        colorspace = representation["data"].get("colorspace")
        colorspace = colorspace or version_data.get("colorspace")

        self.handle_start = version_data.get("handleStart", 0)
        self.handle_end = version_data.get("handleEnd", 0)

        first = version_data.get("frameStart", None)
        last = version_data.get("frameEnd", None)
        first -= self.handle_start
        last += self.handle_end

        if not is_sequence:
            duration = last - first
            first = 1
            last = first + duration

        if not filepath:
            self.log.warning(
                "Representation id `{}` is failing to load".format(repre_id))
            return

        options = ast.literal_eval(container.get("options"))
        prep_layers = options.get("prep_layers", False)
        is_prep_layer_compatible = options.get("is_prep_layer_compatible", False)
        ext = options.get("ext", None)
        old_layers = dict()
        new_layers = dict()
        if is_prep_layer_compatible:
            old_layers = get_layers(read_node, ext)
            read_node["file"].setValue(filepath)
            new_layers = get_layers(read_node, ext)

            if prep_layers:
                if not compare_layers(old_layers, new_layers, ask_proceed=ask_proceed):
                    read_node["file"].setValue(old_file)
                    return

        # Get unique name and number
        unique_number = container.get("unique_number", None)
        read_name, unique_number = get_unique_name_and_number(representation=representation,
                                                              template=self.node_name_template,
                                                              unique_number=unique_number,
                                                              node_type="Read",
                                                              class_name = self.__class__.__name__)
        read_node["name"].setValue(read_name)
        read_node["file"].setValue(filepath)

        # to avoid multiple undo steps for rest of process
        # we will switch off undo-ing
        with viewer_update_and_undo_stop():
            if use_backdrop:
                update_by_backdrop(container, old_layers, new_layers, ask_proceed=False)
            self.set_colorspace_to_node(
                read_node, filepath, version_doc, representation)

            self._set_range_to_node(read_node, first, last, start_at_workfile)

            updated_dict = {
                "representation": str(representation["_id"]),
                "frameStart": str(first),
                "frameEnd": str(last),
                "version": str(version_doc.get("name")),
                "db_colorspace": colorspace,
                "source": version_data.get("source"),
                "handleStart": str(self.handle_start),
                "handleEnd": str(self.handle_end),
                "fps": str(version_data.get("fps")),
                "author": version_data.get("author")
            }

            last_version_doc = get_last_version_by_subset_id(
                project_name, version_doc["parent"], fields=["_id"]
            )
            # change color of read_node
            if version_doc["_id"] == last_version_doc["_id"]:
                color_value = COLOR_GREEN
            else:
                color_value = COLOR_RED
            read_node["tile_color"].setValue(int(color_value, 16))

            # Update the imprinted representation
            update_container(
                read_node,
                updated_dict
            )
            self.log.info(
                "updated to version: {}".format(version_doc.get("name"))
            )

        if add_retime and version_data.get("retime", None):
            self._make_retimes(read_node, version_data)

    def set_colorspace_to_node(
            self,
            read_node,
            filepath,
            version_doc,
            representation_doc,
    ):
        """Set colorspace to read node.

        Sets colorspace with available names validation.

        Args:
            read_node (nuke.Node): The nuke's read node
            filepath (str): file path
            version_doc (dict): version document
            representation_doc (dict): representation document

        """
        used_colorspace = self._get_colorspace_data(
            version_doc, representation_doc, filepath)

        if (
            used_colorspace
            and colorspace_exists_on_node(read_node, used_colorspace)
        ):
            self.log.info(f"Used colorspace: {used_colorspace}")
            read_node["colorspace"].setValue(used_colorspace)
        else:
            self.log.info("Colorspace not set...")

    def remove(self, container):
        read_node = container["node"]
        assert read_node.Class() == "Read", "Must be Read"

        settings = get_project_settings(get_current_project_name()).get("nuke")
        use_backdrop = settings["general"].get("use_backdrop_loader_creator", True)

        main_backdrop = None
        with viewer_update_and_undo_stop():
            if use_backdrop:
                storage_backdrop = nuke.toNode(container["storage_backdrop"])
                main_backdrop = container["main_backdrop"]
                members = get_nodes_in_backdrops(storage_backdrop)
                nuke.delete(storage_backdrop)
            else:
                members = self.get_members(read_node)
                nuke.delete(read_node)
            for member in members:
                nuke.delete(member)
            if main_backdrop:
                reorganize_inside_main_backdrop(main_backdrop)

    def _set_range_to_node(self, read_node, first, last, start_at_workfile):
        read_node['origfirst'].setValue(int(first))
        read_node['first'].setValue(int(first))
        read_node['origlast'].setValue(int(last))
        read_node['last'].setValue(int(last))

        # set start frame depending on workfile or version
        self._loader_shift(read_node, start_at_workfile)

    def _make_retimes(self, parent_node, version_data):
        ''' Create all retime and timewarping nodes with copied animation '''
        speed = version_data.get('speed', 1)
        time_warp_nodes = version_data.get('timewarps', [])
        last_node = None
        source_id = self.get_container_id(parent_node)
        self.log.debug("__ source_id: {}".format(source_id))
        self.log.debug("__ members: {}".format(
            self.get_members(parent_node)))

        dependent_nodes = self.clear_members(parent_node)

        with maintained_selection():
            parent_node['selected'].setValue(True)

            if speed != 1:
                rtn = nuke.createNode(
                    "Retime",
                    "speed {}".format(speed))

                rtn["before"].setValue("continue")
                rtn["after"].setValue("continue")
                rtn["input.first_lock"].setValue(True)
                rtn["input.first"].setValue(
                    self.script_start
                )
                self.set_as_member(rtn)
                last_node = rtn

            if time_warp_nodes != []:
                start_anim = self.script_start + (self.handle_start / speed)
                for timewarp in time_warp_nodes:
                    twn = nuke.createNode(
                        timewarp["Class"],
                        "name {}".format(timewarp["name"])
                    )
                    if isinstance(timewarp["lookup"], list):
                        # if array for animation
                        twn["lookup"].setAnimated()
                        for i, value in enumerate(timewarp["lookup"]):
                            twn["lookup"].setValueAt(
                                (start_anim + i) + value,
                                (start_anim + i))
                    else:
                        # if static value `int`
                        twn["lookup"].setValue(timewarp["lookup"])

                    self.set_as_member(twn)
                    last_node = twn

            if dependent_nodes:
                # connect to original inputs
                for i, n in enumerate(dependent_nodes):
                    last_node.setInput(i, n)

    def _loader_shift(self, read_node, workfile_start=False):
        """ Set start frame of read node to a workfile start

        Args:
            read_node (nuke.Node): The nuke's read node
            workfile_start (bool): set workfile start frame if true

        """
        if workfile_start:
            read_node['frame_mode'].setValue("start at")
            read_node['frame'].setValue(str(self.script_start))

    def _get_colorspace_data(self, version_doc, representation_doc, filepath):
        """Get colorspace data from version and representation documents

        Args:
            version_doc (dict): version document
            representation_doc (dict): representation document
            filepath (str): file path

        Returns:
            Any[str,None]: colorspace name or None
        """
        # Get backward compatible colorspace key.
        colorspace = representation_doc["data"].get("colorspace")
        self.log.debug(
            f"Colorspace from representation colorspace: {colorspace}"
        )

        # Get backward compatible version data key if colorspace is not found.
        colorspace = colorspace or version_doc["data"].get("colorspace")
        self.log.debug(f"Colorspace from version colorspace: {colorspace}")

        # Get colorspace from representation colorspaceData if colorspace is
        # not found.
        colorspace_data = representation_doc["data"].get("colorspaceData", {})
        colorspace = colorspace or colorspace_data.get("colorspace")
        self.log.debug(
            f"Colorspace from representation colorspaceData: {colorspace}"
        )

        print(f"Colorspace found: {colorspace}")

        # check if any filerules are not applicable
        new_parsed_colorspace = get_imageio_file_rules_colorspace_from_filepath( # noqa
            filepath, "nuke", get_current_project_name()
        )
        self.log.debug(f"Colorspace new filerules: {new_parsed_colorspace}")

        # colorspace from `project_settings/nuke/imageio/regexInputs`
        old_parsed_colorspace = get_imageio_input_colorspace(filepath)
        self.log.debug(f"Colorspace old filerules: {old_parsed_colorspace}")

        return (
            new_parsed_colorspace
            or old_parsed_colorspace
            or colorspace
        )
